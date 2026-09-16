# -*- coding: utf-8 -*-
"""Point-in-time replay of the live HSI daily monitor. Research only, not a forecast."""

from __future__ import annotations

import csv
import logging
import math
import os
import random
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd

from src.services.daily_monitor import (
    DEFAULT_HSI_MONITOR_LIMIT,
    DEFAULT_MAX_EXTENSION_N,
    INDEX_CODE,
    INDEX_NAME,
    classify_daily_monitor,
    resolve_max_extension_n,
    resolve_monitor_limit,
)
from src.services.ohlcv_cache import load_latest_cached_history, save_cached_history

logger = logging.getLogger(__name__)

DEFAULT_PERIOD = "5y"
DEFAULT_HORIZON = 20
DEFAULT_WARMUP = 100
DEFAULT_COST_BPS = 20.0
DEFAULT_SEED = 42
DEFAULT_BATCH_SIZE = 80
RESEARCH_DISCLAIMER = (
    "研究回放，不是涨跌预测。今日恒指成分向前套用，存在生存者偏差；"
    "短样本 E-ratio / 纸上盈亏会被单一行情主导。"
)

EvaluateFn = Callable[[str, str, pd.DataFrame], Dict[str, Any]]


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def resolve_sim_config(
    *,
    period: Optional[str] = None,
    horizon: Optional[int] = None,
    warmup: Optional[int] = None,
    limit: Optional[int] = None,
    max_extension_n: Optional[float] = None,
    cost_bps: Optional[float] = None,
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    return {
        "period": (period or os.getenv("MONITOR_SIM_PERIOD") or DEFAULT_PERIOD).strip() or DEFAULT_PERIOD,
        "horizon": max(1, horizon if horizon is not None else _env_int("MONITOR_SIM_HORIZON", DEFAULT_HORIZON)),
        "warmup": max(55, warmup if warmup is not None else _env_int("MONITOR_SIM_WARMUP", DEFAULT_WARMUP)),
        "limit": resolve_monitor_limit("HSI_SCAN_MONITOR_LIMIT", DEFAULT_HSI_MONITOR_LIMIT, override=limit),
        "max_extension_n": resolve_max_extension_n(
            "HSI_SCAN_MAX_EXTENSION_N",
            default=DEFAULT_MAX_EXTENSION_N,
            override=max_extension_n,
        ),
        "cost_bps": max(
            0.0,
            float(cost_bps if cost_bps is not None else _env_float("MONITOR_SIM_COST_BPS", DEFAULT_COST_BPS)),
        ),
        "seed": seed if seed is not None else _env_int("MONITOR_SIM_SEED", DEFAULT_SEED),
    }


def normalize_ohlcv_index(hist: pd.DataFrame) -> pd.DataFrame:
    """Drop timezone, normalize to calendar dates, keep last bar per day."""
    if hist is None or hist.empty:
        return hist
    work = hist.copy()
    idx = pd.to_datetime(work.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_convert("UTC").tz_localize(None)
    work.index = idx.normalize()
    work = work[~work.index.duplicated(keep="last")].sort_index()
    return work


def history_through(hist: pd.DataFrame, as_of: Any) -> pd.DataFrame:
    ts = pd.Timestamp(as_of).normalize()
    return hist.loc[hist.index <= ts]


def has_bar(hist: pd.DataFrame, as_of: Any) -> bool:
    ts = pd.Timestamp(as_of).normalize()
    return bool(ts in hist.index)


def _px(row: Any, column: str) -> Optional[float]:
    if row is None or column not in row.index:
        return None
    value = row[column]
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number):
        return None
    return number


def _as_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number):
        return None
    return number


def session_dates(*frames: pd.DataFrame) -> List[pd.Timestamp]:
    index: Optional[pd.DatetimeIndex] = None
    for frame in frames:
        if frame is None or frame.empty:
            continue
        part = pd.DatetimeIndex(frame.index).normalize().unique()
        index = part if index is None else index.union(part)
    if index is None:
        return []
    return list(pd.DatetimeIndex(index).sort_values())


def load_universe_histories(
    stocks: Sequence[Dict[str, str]],
    period: str,
    *,
    include_index: bool = True,
    no_network: bool = False,
    refresh: bool = False,
    batch_size: Optional[int] = None,
) -> Dict[str, pd.DataFrame]:
    """Load HSI (+ optional ^HSI) frames from disk cache, else Yahoo once."""
    from src.services.hsi_scanner import fetch_history_batch_yfinance

    wanted: List[str] = []
    for item in stocks:
        code = str(item.get("code") or "").strip().upper()
        if code:
            wanted.append(code)
    if include_index and INDEX_CODE not in wanted:
        wanted.append(INDEX_CODE)

    loaded: Dict[str, pd.DataFrame] = {}
    missing: List[str] = []
    for code in wanted:
        frame = None if refresh else load_latest_cached_history(code, period)
        if frame is not None and not frame.empty:
            loaded[code] = normalize_ohlcv_index(frame)
        else:
            missing.append(code)

    if missing:
        if no_network:
            logger.warning("Cache miss with --no-network: %s", ",".join(missing))
        else:
            downloaded = fetch_history_batch_yfinance(
                missing,
                period,
                batch_size=batch_size if batch_size is not None else DEFAULT_BATCH_SIZE,
            )
            for code, frame in downloaded.items():
                if frame is None or frame.empty:
                    continue
                normalized = normalize_ohlcv_index(frame)
                loaded[code] = normalized
                save_cached_history(code, period, normalized)

    return loaded


def forward_excursions(
    hist: pd.DataFrame,
    signal_ts: Any,
    signal_close: float,
    n_value: Optional[float],
    horizon: int,
) -> Dict[str, Optional[float]]:
    """MAE/MFE vs signal close over the next ``horizon`` bars (not including t)."""
    later = hist.loc[hist.index > pd.Timestamp(signal_ts).normalize()]
    window = later.iloc[: max(1, int(horizon))]
    empty = {
        "mae": None,
        "mfe": None,
        "mae_n": None,
        "mfe_n": None,
        "ret_1": None,
        "ret_5": None,
        "ret_h": None,
        "forward_bars": 0,
    }
    if window.empty or signal_close is None or signal_close <= 0:
        return empty
    lows = pd.to_numeric(window["Low"], errors="coerce") if "Low" in window.columns else pd.Series(dtype=float)
    highs = pd.to_numeric(window["High"], errors="coerce") if "High" in window.columns else pd.Series(dtype=float)
    closes = pd.to_numeric(window["Close"], errors="coerce") if "Close" in window.columns else pd.Series(dtype=float)
    mae = None if lows.dropna().empty else max(0.0, float(signal_close) - float(lows.min()))
    mfe = None if highs.dropna().empty else max(0.0, float(highs.max()) - float(signal_close))
    mae_n = (mae / n_value) if mae is not None and n_value and n_value > 0 else None
    mfe_n = (mfe / n_value) if mfe is not None and n_value and n_value > 0 else None

    def _ret_at(offset: int) -> Optional[float]:
        if len(closes.dropna()) < offset:
            return None
        last = closes.iloc[offset - 1]
        if pd.isna(last):
            return None
        return float(last) / float(signal_close) - 1.0

    return {
        "mae": mae,
        "mfe": mfe,
        "mae_n": mae_n,
        "mfe_n": mfe_n,
        "ret_1": _ret_at(1),
        "ret_5": _ret_at(min(5, horizon)),
        "ret_h": _ret_at(min(len(window), horizon)),
        "forward_bars": int(len(window)),
    }


def simulate_paper_trade(
    hist: pd.DataFrame,
    signal_ts: Any,
    n_value: Optional[float],
    horizon: int,
    cost_bps: float,
) -> Optional[Dict[str, Any]]:
    """Next-bar open entry, 2N stop, time stop at ``horizon`` bars. No pyramids."""
    if n_value is None or n_value <= 0:
        return None
    later = hist.loc[hist.index > pd.Timestamp(signal_ts).normalize()]
    if later.empty:
        return None
    entry_row = later.iloc[0]
    entry_date = later.index[0]
    entry = _px(entry_row, "Open")
    if entry is None:
        entry = _px(entry_row, "Close")
    if entry is None or entry <= 0:
        return None
    stop = entry - 2.0 * float(n_value)
    window = later.iloc[: max(1, int(horizon))]
    exit_price: Optional[float] = None
    exit_date: Optional[pd.Timestamp] = None
    exit_reason: Optional[str] = None
    path: List[Tuple[pd.Timestamp, float, Optional[float]]] = []
    for i in range(len(window)):
        row = window.iloc[i]
        dt = pd.Timestamp(window.index[i])
        close = _px(row, "Close")
        low = _px(row, "Low")
        path.append((dt, entry if close is None else close, low))
        if low is not None and low <= stop:
            exit_price = stop
            exit_date = dt
            exit_reason = "stop"
            break
        if i >= int(horizon) - 1:
            exit_price = close if close is not None else entry
            exit_date = dt
            exit_reason = "time"
            break
    if exit_price is None:
        last = window.iloc[-1]
        exit_price = _px(last, "Close")
        if exit_price is None:
            return None
        exit_date = pd.Timestamp(window.index[-1])
        exit_reason = "data_end"
    cost = entry * max(0.0, float(cost_bps)) / 10_000.0
    net = float(exit_price) - entry - cost
    return {
        "entry_date": entry_date,
        "entry": entry,
        "stop": stop,
        "n": float(n_value),
        "exit_date": exit_date,
        "exit": float(exit_price),
        "exit_reason": exit_reason,
        "cost": cost,
        "net": net,
        "r": net / (2.0 * float(n_value)),
        "ret": net / entry,
        "path": path,
    }


def _mean(values: Iterable[Optional[float]]) -> Optional[float]:
    data = [float(v) for v in values if v is not None and not math.isnan(float(v))]
    if not data:
        return None
    return float(sum(data) / len(data))


def _median(values: Iterable[Optional[float]]) -> Optional[float]:
    data = [float(v) for v in values if v is not None and not math.isnan(float(v))]
    if not data:
        return None
    return float(statistics.median(data))


def _eratio(mfe_n: Sequence[Optional[float]], mae_n: Sequence[Optional[float]]) -> Optional[float]:
    mean_mfe = _mean(mfe_n)
    mean_mae = _mean(mae_n)
    if mean_mfe is None or mean_mae is None or mean_mae == 0:
        return None
    return mean_mfe / mean_mae


def _win_rate(returns: Sequence[Optional[float]]) -> Optional[float]:
    data = [float(v) for v in returns if v is not None]
    if not data:
        return None
    return sum(1 for v in data if v > 0) / len(data)


def summarize_alert_quality(alerts: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "n": len(alerts),
        "win_rate": _win_rate([a.get("ret_h") for a in alerts]),
        "median_5d": _median([a.get("ret_5") for a in alerts]),
        "median_h": _median([a.get("ret_h") for a in alerts]),
        "eratio": _eratio([a.get("mfe_n") for a in alerts], [a.get("mae_n") for a in alerts]),
    }


def max_drawdown_from_equity(equity: Sequence[float]) -> float:
    peak = None
    max_dd = 0.0
    for value in equity:
        if peak is None or value > peak:
            peak = value
        if peak is None:
            continue
        dd = peak - value
        if dd > max_dd:
            max_dd = dd
    return float(max_dd)


def paper_equity_curve(
    trades: Sequence[Dict[str, Any]],
    calendar: Sequence[pd.Timestamp],
    histories: Dict[str, pd.DataFrame],
) -> List[float]:
    """Cumulative 1-share mark-to-market of closed + open paper trades."""
    if not trades:
        return []
    equity: List[float] = []
    for day in calendar:
        total = 0.0
        for trade in trades:
            code = str(trade.get("code") or "")
            entry_date = pd.Timestamp(trade["entry_date"]).normalize()
            exit_date = pd.Timestamp(trade["exit_date"]).normalize()
            if day < entry_date:
                continue
            if day >= exit_date:
                total += float(trade["net"])
                continue
            hist = histories.get(code)
            if hist is None or not has_bar(hist, day):
                continue
            close = _px(hist.loc[pd.Timestamp(day).normalize()], "Close")
            if close is None:
                continue
            total += close - float(trade["entry"])
        equity.append(total)
    return equity


def summarize_paper_book(
    trades: Sequence[Dict[str, Any]],
    calendar: Sequence[pd.Timestamp],
    histories: Dict[str, pd.DataFrame],
) -> Dict[str, Any]:
    stops = sum(1 for t in trades if t.get("exit_reason") == "stop")
    equity = paper_equity_curve(trades, calendar, histories)
    return {
        "n": len(trades),
        "avg_r": _mean([t.get("r") for t in trades]),
        "hit_stop_rate": (stops / len(trades)) if trades else None,
        "max_dd": max_drawdown_from_equity(equity) if equity else 0.0,
    }


def _new_alert_rows(
    classified: Dict[str, Any],
    previous_codes: set[str],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for bucket in ("uprising", "reversal"):
        for row in classified.get(bucket) or []:
            code = str(row.get("code") or "").strip().upper()
            if not code or code in seen or code in previous_codes:
                continue
            tagged = dict(row)
            tagged["monitor_bucket"] = bucket
            rows.append(tagged)
            seen.add(code)
    return rows


def _listed_codes(classified: Dict[str, Any]) -> set[str]:
    codes: set[str] = set()
    for bucket in ("uprising", "reversal"):
        for row in classified.get(bucket) or []:
            code = str(row.get("code") or "").strip().upper()
            if code:
                codes.add(code)
    return codes


@dataclass
class ReplayState:
    alerts: List[Dict[str, Any]] = field(default_factory=list)
    random_alerts: List[Dict[str, Any]] = field(default_factory=list)
    trades: List[Dict[str, Any]] = field(default_factory=list)
    days_replayed: int = 0
    uprising_suppressed_days: int = 0


def replay_monitor(
    histories: Dict[str, pd.DataFrame],
    stocks: Sequence[Dict[str, str]],
    *,
    horizon: int = DEFAULT_HORIZON,
    warmup: int = DEFAULT_WARMUP,
    limit: int = DEFAULT_HSI_MONITOR_LIMIT,
    max_extension_n: float = DEFAULT_MAX_EXTENSION_N,
    cost_bps: float = DEFAULT_COST_BPS,
    seed: int = DEFAULT_SEED,
    evaluate_fn: Optional[EvaluateFn] = None,
    row_filter: Optional[Callable[[Dict[str, Any]], bool]] = None,
    progress_every: int = 20,
) -> Dict[str, Any]:
    """Classify each historical day with live rules, then score alerts and paper trades."""
    from src.services.hsi_scanner import evaluate_ticker_from_history

    evaluator = evaluate_fn or evaluate_ticker_from_history
    names = {
        str(item.get("code") or "").strip().upper(): str(item.get("name") or "")
        for item in stocks
        if str(item.get("code") or "").strip()
    }
    frames = {code: normalize_ohlcv_index(frame) for code, frame in histories.items() if frame is not None}
    index_hist = frames.get(INDEX_CODE)
    if index_hist is None or index_hist.empty:
        calendar = session_dates(*frames.values())
    else:
        calendar = session_dates(index_hist)
    if len(calendar) <= warmup + horizon:
        raise ValueError(
            f"Not enough bars to replay (calendar={len(calendar)}, warmup={warmup}, horizon={horizon})"
        )

    rng = random.Random(seed)
    state = ReplayState()
    previous_codes: set[str] = set()
    open_until: Dict[str, pd.Timestamp] = {}

    start_i = 0
    for i, day in enumerate(calendar):
        if index_hist is not None and len(history_through(index_hist, day)) >= warmup:
            start_i = i
            break
        stock_ready = False
        for code in names:
            hist = frames.get(code)
            if hist is not None and len(history_through(hist, day)) >= warmup:
                stock_ready = True
                break
        if stock_ready:
            start_i = i
            break
    end_i = len(calendar) - horizon
    if end_i <= start_i:
        raise ValueError("Warmup and horizon leave no replay days")

    replay_days = calendar[start_i:end_i]
    total_days = len(replay_days)
    logger.info("Replay starting: days=%s universe=%s", total_days, len(names))
    for day in replay_days:
        rows: List[Dict[str, Any]] = []
        evaluable: List[Dict[str, Any]] = []
        for code, name in names.items():
            hist = frames.get(code)
            if hist is None or not has_bar(hist, day):
                continue
            sliced = history_through(hist, day)
            if len(sliced) < warmup:
                continue
            row = evaluator(code, name, sliced)
            if not isinstance(row, dict):
                continue
            if row.get("status") in (None, "ok"):
                if row_filter is not None and not row_filter(row):
                    continue
                rows.append(row)
                evaluable.append(row)

        index_ok: Optional[bool] = None
        if index_hist is not None and has_bar(index_hist, day):
            index_slice = history_through(index_hist, day)
            if len(index_slice) >= warmup:
                index_row = evaluator(INDEX_CODE, INDEX_NAME, index_slice)
                if isinstance(index_row, dict) and index_row.get("status") in (None, "ok"):
                    flag = index_row.get("turtle_trend_ok")
                    index_ok = bool(flag) if flag is not None else None

        classified = classify_daily_monitor(
            rows,
            limit=limit,
            max_extension_n=max_extension_n,
            index_trend_ok=index_ok,
        )
        if classified.get("uprising_suppressed"):
            state.uprising_suppressed_days += 1

        new_rows = _new_alert_rows(classified, previous_codes)
        listed = _listed_codes(classified)
        control_pool = [
            row for row in evaluable
            if str(row.get("code") or "").strip().upper() not in listed
        ]

        def _attach_forward(row: Dict[str, Any], *, is_random: bool) -> Dict[str, Any]:
            code = str(row.get("code") or "").strip().upper()
            hist = frames.get(code)
            close = _as_float(row.get("close"))
            n_value = _as_float(row.get("n"))
            fwd = (
                forward_excursions(hist, day, close, n_value, horizon)
                if hist is not None and close is not None
                else {}
            )
            record = {
                "signal_date": pd.Timestamp(day).strftime("%Y-%m-%d"),
                "code": code,
                "name": row.get("name") or names.get(code, ""),
                "bucket": row.get("monitor_bucket") or ("random" if is_random else ""),
                "event": row.get("monitor_event"),
                "close": close,
                "n": n_value,
                "is_random": is_random,
                "index_trend_ok": index_ok,
                "s1_recent_close_breakout": bool(row.get("s1_recent_close_breakout")),
                "s2_recent_close_breakout": bool(row.get("s2_recent_close_breakout")),
                "s1_entry_allowed": bool(row.get("s1_entry_allowed")),
                **fwd,
            }
            return record

        day_alerts: List[Dict[str, Any]] = []
        for row in new_rows:
            record = _attach_forward(row, is_random=False)
            state.alerts.append(record)
            day_alerts.append(record)
            code = record["code"]
            blocked = code in open_until and pd.Timestamp(day) < open_until[code]
            hist = frames.get(code)
            n_value = record.get("n")
            if hist is not None and not blocked:
                trade = simulate_paper_trade(hist, day, n_value, horizon, cost_bps)
                if trade is not None:
                    trade["code"] = code
                    trade["name"] = record["name"]
                    trade["bucket"] = record["bucket"]
                    trade["signal_date"] = record["signal_date"]
                    state.trades.append(trade)
                    open_until[code] = pd.Timestamp(trade["exit_date"]).normalize()

        sample_n = min(len(control_pool), len(day_alerts))
        if sample_n:
            picks = rng.sample(control_pool, sample_n)
            for row in picks:
                tagged = dict(row)
                tagged["monitor_bucket"] = "random"
                state.random_alerts.append(_attach_forward(tagged, is_random=True))

        previous_codes = listed
        state.days_replayed += 1
        if progress_every and state.days_replayed % max(1, int(progress_every)) == 0:
            logger.info(
                "Replay progress %s/%s (%s) alerts=%s trades=%s",
                state.days_replayed,
                total_days,
                pd.Timestamp(day).strftime("%Y-%m-%d"),
                len(state.alerts),
                len(state.trades),
            )

    def _by_bucket(items: Sequence[Dict[str, Any]], bucket: str) -> List[Dict[str, Any]]:
        return [item for item in items if item.get("bucket") == bucket]

    random_summary = summarize_alert_quality(state.random_alerts)
    quality = {}
    paper = {}
    for bucket in ("uprising", "reversal"):
        quality[bucket] = {
            "alerts": summarize_alert_quality(_by_bucket(state.alerts, bucket)),
            "random": random_summary,
        }
        book_trades = [t for t in state.trades if t.get("bucket") == bucket]
        paper[bucket] = summarize_paper_book(book_trades, calendar[start_i:end_i], frames)

    return {
        "days_replayed": state.days_replayed,
        "uprising_suppressed_days": state.uprising_suppressed_days,
        "calendar_start": calendar[start_i].strftime("%Y-%m-%d"),
        "calendar_end": calendar[end_i - 1].strftime("%Y-%m-%d"),
        "alerts": state.alerts,
        "random_alerts": state.random_alerts,
        "trades": state.trades,
        "quality": quality,
        "paper": paper,
        "histories": frames,
        "calendar": calendar[start_i:end_i],
    }


def _pct(value: Optional[float]) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.2f}%"


def _num(value: Optional[float], digits: int = 3) -> str:
    if value is None:
        return "—"
    return f"{value:.{digits}f}"


def format_sim_report(
    result: Dict[str, Any],
    *,
    period: str,
    horizon: int,
    warmup: int,
    limit: int,
    max_extension_n: float,
    cost_bps: float,
    universe_size: int,
) -> str:
    lines = [
        "# HSI 每日监控回放",
        "",
        f"> {RESEARCH_DISCLAIMER}",
        "",
        "## 设定",
        "",
        f"- 标的：当前 `HSI_STOCKS`（{universe_size} 只）+ `{INDEX_CODE}`，**不是**当时的恒指成分",
        f"- period=`{period}`；回放 {result.get('calendar_start')} → {result.get('calendar_end')}（{result.get('days_replayed')} 个交易日）",
        f"- warmup={warmup}；horizon={horizon}；每名单上限 {limit}；延伸 N ≤ {max_extension_n}",
        f"- 纸上成本 {cost_bps:g} bp 往返；入场为信号次日开盘（缺开盘则用收盘），止损 2N，无加仓",
        f"- 恒指趋势未过而省略趋势首破的天数：{result.get('uprising_suppressed_days', 0)}",
        "",
        "## 警报质量（相对信号收盘）",
        "",
        "| 名单 | 警报数 | 期末收盘胜率 | 中位 5 日 | 中位 horizon | E-ratio | 随机对照 E-ratio |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    quality = result.get("quality") or {}
    for bucket, label in (("uprising", "趋势首破"), ("reversal", "止跌转折")):
        stats = (quality.get(bucket) or {}).get("alerts") or {}
        rand = (quality.get(bucket) or {}).get("random") or {}
        lines.append(
            "| {label} | {n} | {win} | {m5} | {mh} | {er} | {rer} |".format(
                label=label,
                n=stats.get("n") or 0,
                win=_pct(stats.get("win_rate")),
                m5=_pct(stats.get("median_5d")),
                mh=_pct(stats.get("median_h")),
                er=_num(stats.get("eratio")),
                rer=_num(rand.get("eratio")),
            )
        )
    lines.extend(
        [
            "",
            "E-ratio = mean(MFE/N) / mean(MAE/N)。随机对照：同一天、相同数量、从未上任一名单的可评估成分股。",
            "",
            "## 纸上交易（次日开盘，2N 止损）",
            "",
            "| 名单 | 笔数 | 平均 R | 触及止损 | 1 股账面最大回撤 |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    paper = result.get("paper") or {}
    for bucket, label in (("uprising", "趋势首破"), ("reversal", "止跌转折")):
        stats = paper.get(bucket) or {}
        lines.append(
            "| {label} | {n} | {r} | {hit} | {dd} |".format(
                label=label,
                n=stats.get("n") or 0,
                r=_num(stats.get("avg_r")),
                hit=_pct(stats.get("hit_stop_rate")),
                dd=_num(stats.get("max_dd"), 2),
            )
        )
    turtle = result.get("turtle_paper") or {}
    if turtle:
        lines.extend(
            [
                "",
                "## 海龟纸上交易（1% 单位，½N 加仓，Donchian 离场）",
                "",
                "| 名单 | 笔数 | 平均 R | 触及止损 | 最大单位 | 跳过S1盈利 |",
                "| --- | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for bucket, label in (("uprising", "趋势首破"), ("reversal", "止跌转折")):
            stats = turtle.get(bucket) or {}
            lines.append(
                "| {label} | {n} | {r} | {hit} | {units} | {skip} |".format(
                    label=label,
                    n=stats.get("n") or 0,
                    r=_num(stats.get("avg_r")),
                    hit=_pct(stats.get("hit_stop_rate")),
                    units=stats.get("max_units_seen") or 0,
                    skip=stats.get("skipped_s1_winner") or 0,
                )
            )
    lines.extend(
        [
            "",
            "R = (平仓价 − 开仓价 − 成本) / (2N)。最大回撤是等权 1 股账户的价格单位，不是 1% 风险组合。",
            "",
        ]
    )
    return "\n".join(lines)


def _csv_ready_alerts(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    keep = [
        "signal_date",
        "code",
        "name",
        "bucket",
        "event",
        "close",
        "n",
        "mae",
        "mfe",
        "mae_n",
        "mfe_n",
        "ret_1",
        "ret_5",
        "ret_h",
        "is_random",
        "index_trend_ok",
    ]
    out: List[Dict[str, Any]] = []
    for row in rows:
        item = {key: row.get(key) for key in keep}
        out.append(item)
    return out


def _csv_ready_trades(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    keep = [
        "signal_date",
        "code",
        "name",
        "bucket",
        "entry_date",
        "entry",
        "stop",
        "n",
        "exit_date",
        "exit",
        "exit_reason",
        "cost",
        "net",
        "r",
        "ret",
    ]
    out: List[Dict[str, Any]] = []
    for row in rows:
        item = {}
        for key in keep:
            value = row.get(key)
            if hasattr(value, "strftime"):
                value = value.strftime("%Y-%m-%d")
            item[key] = value
        out.append(item)
    return out


def _write_csv(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_sim_outputs(
    result: Dict[str, Any],
    report_text: str,
    *,
    reports_dir: Optional[Path] = None,
    stamp: Optional[str] = None,
) -> Dict[str, Path]:
    root = reports_dir or Path("reports")
    root.mkdir(parents=True, exist_ok=True)
    stamp = stamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = "hk_monitor_sim" if str(result.get("universe") or "hsi") == "hk" else "hsi_monitor_sim"
    md_path = root / f"{prefix}_{stamp}.md"
    alerts_path = root / f"{prefix}_{stamp}_alerts.csv"
    trades_path = root / f"{prefix}_{stamp}_trades.csv"
    md_path.write_text(report_text, encoding="utf-8")
    alerts = _csv_ready_alerts(list(result.get("alerts") or []) + list(result.get("random_alerts") or []))
    trades = _csv_ready_trades(result.get("trades") or [])
    _write_csv(alerts_path, alerts)
    _write_csv(trades_path, trades)
    paths = {"markdown": md_path, "alerts_csv": alerts_path, "trades_csv": trades_path}
    turtle_trades: List[Dict[str, Any]] = []
    for book in (result.get("turtle_paper") or {}).values():
        if isinstance(book, dict):
            turtle_trades.extend(book.get("trades") or [])
    if turtle_trades:
        turtle_path = root / f"{prefix}_{stamp}_turtle.csv"
        _write_csv(turtle_path, _csv_ready_trades(turtle_trades))
        paths["turtle_csv"] = turtle_path
    return paths


def run_hsi_monitor_simulation(
    *,
    period: Optional[str] = None,
    horizon: Optional[int] = None,
    warmup: Optional[int] = None,
    limit: Optional[int] = None,
    max_extension_n: Optional[float] = None,
    cost_bps: Optional[float] = None,
    seed: Optional[int] = None,
    no_network: bool = False,
    refresh: bool = False,
    stocks: Optional[Sequence[Dict[str, str]]] = None,
    histories: Optional[Dict[str, pd.DataFrame]] = None,
    evaluate_fn: Optional[EvaluateFn] = None,
    batch_size: Optional[int] = None,
    progress_every: int = 20,
    universe: str = "hsi",
    codes: Optional[Sequence[str]] = None,
    book: str = "simple",
    equity: Optional[float] = None,
) -> Dict[str, Any]:
    from src.services.hsi_scanner import HSI_STOCKS

    cfg = resolve_sim_config(
        period=period,
        horizon=horizon,
        warmup=warmup,
        limit=limit,
        max_extension_n=max_extension_n,
        cost_bps=cost_bps,
        seed=seed,
    )
    kind = (universe or "hsi").strip().lower()
    row_filter = None
    if stocks is not None:
        selected = list(stocks)
    elif kind == "hk":
        from src.services.hk_stock_scanner import apply_hk_liquidity_gates, load_hk_stocks_universe

        selected = load_hk_stocks_universe()
        cfg["limit"] = resolve_monitor_limit("HK_SCAN_MONITOR_LIMIT", 15, override=limit)

        def row_filter(row: Dict[str, Any]) -> bool:
            kept, _dropped = apply_hk_liquidity_gates(
                [row],
                require_volume_confirm=False,
                require_trend=False,
                require_ma100=False,
            )
            return bool(kept)

    else:
        selected = list(HSI_STOCKS)

    if codes:
        wanted = {str(code).strip().upper() for code in codes if str(code).strip()}
        selected = [item for item in selected if str(item.get("code") or "").strip().upper() in wanted]
        if not selected:
            raise RuntimeError("No tickers left after --codes filter.")

    frames = histories
    if frames is None:
        frames = load_universe_histories(
            selected,
            cfg["period"],
            include_index=True,
            no_network=no_network,
            refresh=refresh,
            batch_size=batch_size,
        )
        if INDEX_CODE not in frames:
            raise RuntimeError(
                f"Missing {INDEX_CODE} history (cache empty or Yahoo failed). "
                "Re-run without --no-network, or pass --refresh."
            )
        if not any(str(item.get("code") or "").strip().upper() in frames for item in selected):
            raise RuntimeError("No stock histories loaded.")

    result = replay_monitor(
        frames,
        selected,
        horizon=cfg["horizon"],
        warmup=cfg["warmup"],
        limit=cfg["limit"],
        max_extension_n=cfg["max_extension_n"],
        cost_bps=cfg["cost_bps"],
        seed=cfg["seed"],
        evaluate_fn=evaluate_fn,
        row_filter=row_filter,
        progress_every=progress_every,
    )
    result["config"] = cfg
    result["universe"] = kind
    result["universe_size"] = len(selected)
    if str(book or "simple").strip().lower() == "turtle":
        from src.services.turtle_paper_book import DEFAULT_EQUITY, simulate_turtle_book

        account = float(equity) if equity is not None else _env_float("MONITOR_SIM_EQUITY", DEFAULT_EQUITY)
        result["turtle_paper"] = {
            "uprising": simulate_turtle_book(
                result.get("alerts") or [],
                result.get("histories") or frames,
                equity=account,
                cost_bps=cfg["cost_bps"],
                bucket="uprising",
            ),
            "reversal": simulate_turtle_book(
                result.get("alerts") or [],
                result.get("histories") or frames,
                equity=account,
                cost_bps=cfg["cost_bps"],
                bucket="reversal",
            ),
        }
        cfg["equity"] = account
        cfg["book"] = "turtle"
    else:
        cfg["book"] = "simple"
    result["report"] = format_sim_report(
        result,
        period=cfg["period"],
        horizon=cfg["horizon"],
        warmup=cfg["warmup"],
        limit=cfg["limit"],
        max_extension_n=cfg["max_extension_n"],
        cost_bps=cfg["cost_bps"],
        universe_size=len(selected),
    )
    return result
