# -*- coding: utf-8 -*-
"""Daily monitor buckets: trend first-cross vs turn-up. Admission is rule-based, not a forecast."""

from __future__ import annotations

import json
import logging
import os
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

INDEX_CODE = "^HSI"
INDEX_NAME = "恒生指数"
DEFAULT_MAX_EXTENSION_N = 1.0
DEFAULT_HK_MONITOR_LIMIT = 15
DEFAULT_HSI_MONITOR_LIMIT = 10
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _env_bool(name: str, default: bool) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    return default


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


def _as_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def resolve_monitor_enabled(
    env_key: str,
    *,
    default: bool = True,
    override: Optional[bool] = None,
) -> bool:
    if override is not None:
        return bool(override)
    return _env_bool(env_key, default)


def resolve_monitor_limit(
    env_key: str,
    default: int,
    override: Optional[int] = None,
) -> int:
    if override is not None:
        return max(1, int(override))
    return max(1, _env_int(env_key, default))


def resolve_max_extension_n(
    env_key: str,
    *,
    default: float = DEFAULT_MAX_EXTENSION_N,
    override: Optional[float] = None,
) -> float:
    if override is not None:
        return max(0.0, float(override))
    return max(0.0, _env_float(env_key, default))


def monitor_event_label(row: Dict[str, Any]) -> str:
    """Short Close-first-cross event for the daily table."""
    from src.services.hsi_scanner import format_recent_breakout_timing

    if row.get("s2_recent_close_breakout"):
        timing = format_recent_breakout_timing(row.get("s2_recent_close_timing"))
        return f"S2 Close {timing}首破"
    if row.get("s1_recent_close_breakout"):
        timing = format_recent_breakout_timing(row.get("s1_recent_close_timing"))
        return f"S1 Close {timing}首破"
    return "Close 首破"


def is_uprising_row(
    row: Dict[str, Any],
    *,
    max_extension_n: float = DEFAULT_MAX_EXTENSION_N,
) -> bool:
    """Trend-ok Close first-cross with volume, MA100, and not a late chase."""
    s2_close = bool(row.get("s2_recent_close_breakout"))
    s1_close = bool(row.get("s1_recent_close_breakout"))
    s1_allowed = bool(row.get("s1_entry_allowed"))
    if not (s2_close or (s1_close and s1_allowed)):
        return False
    if not bool(row.get("turtle_trend_ok")):
        return False
    if not bool(row.get("volume_confirm")):
        return False
    ext = _as_float(row.get("breakout_extension_n"))
    if ext is not None and ext > max_extension_n:
        return False
    if bool(row.get("s1_exit")) or bool(row.get("s2_exit")):
        return False
    if row.get("close_vs_ma100") is not True:
        return False
    return True


def is_reversal_row(row: Dict[str, Any]) -> bool:
    """S1 Close first-cross while Turtle trend or MA100 is still off."""
    if not bool(row.get("s1_recent_close_breakout")):
        return False
    trend_ok = bool(row.get("turtle_trend_ok"))
    ma100 = row.get("close_vs_ma100")
    if trend_ok and ma100 is not False:
        return False
    if not bool(row.get("volume_confirm")):
        return False
    if bool(row.get("s1_exit")):
        return False
    return True


def _sort_monitor_rows(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def _key(row: Dict[str, Any]) -> tuple:
        s2_first = 0 if row.get("s2_recent_close_breakout") else 1
        ext = _as_float(row.get("breakout_extension_n"))
        ext_key = ext if ext is not None else 10_000.0
        score = _as_float(row.get("potential_score")) or 0.0
        code = str(row.get("code") or "")
        return (s2_first, ext_key, -score, code)

    return sorted(list(rows or []), key=_key)


def _is_evaluable_row(row: Dict[str, Any]) -> bool:
    status = row.get("status")
    return status in (None, "ok")


def classify_daily_monitor(
    rows: Sequence[Dict[str, Any]],
    *,
    limit: int = DEFAULT_HK_MONITOR_LIMIT,
    max_extension_n: float = DEFAULT_MAX_EXTENSION_N,
    index_trend_ok: Optional[bool] = None,
) -> Dict[str, Any]:
    """Split evaluated rows into capped uprising / reversal lists.

    Uprising is omitted when ``index_trend_ok`` is False. Missing index
    (``None``) does not suppress. A code appears in one list only (uprising wins).
    """
    cap = max(1, int(limit))
    uprising: List[Dict[str, Any]] = []
    reversal: List[Dict[str, Any]] = []
    seen: set[str] = set()

    for row in rows or []:
        if not _is_evaluable_row(row):
            continue
        code = str(row.get("code") or "").strip().upper()
        if not code or code in seen:
            continue
        if is_uprising_row(row, max_extension_n=max_extension_n):
            tagged = dict(row)
            tagged["monitor_bucket"] = "uprising"
            tagged["monitor_event"] = monitor_event_label(row)
            uprising.append(tagged)
            seen.add(code)
            continue
        if is_reversal_row(row):
            tagged = dict(row)
            tagged["monitor_bucket"] = "reversal"
            tagged["monitor_event"] = monitor_event_label(row)
            reversal.append(tagged)
            seen.add(code)

    uprising = _sort_monitor_rows(uprising)
    reversal = _sort_monitor_rows(reversal)
    suppressed = index_trend_ok is False
    uprising_shown = [] if suppressed else uprising[:cap]
    reversal_shown = reversal[:cap]
    return {
        "uprising": uprising_shown,
        "reversal": reversal_shown,
        "uprising_all": uprising,
        "reversal_all": reversal,
        "uprising_total": len(uprising),
        "reversal_total": len(reversal),
        "uprising_suppressed": suppressed,
        "matches": uprising_shown + reversal_shown,
        "limit": cap,
        "max_extension_n": max_extension_n,
    }


def fetch_hsi_index_regime(
    period: str = "1y",
    *,
    evaluate_fn: Any = None,
) -> Dict[str, Any]:
    """Evaluate ``^HSI`` for the report banner. Soft-fail; never raises."""
    try:
        if evaluate_fn is None:
            from src.services.hsi_scanner import evaluate_ticker

            evaluate_fn = evaluate_ticker
        result = evaluate_fn(
            INDEX_CODE,
            INDEX_NAME,
            period=period,
            retries=2,
            use_multi_source=False,
        )
    except Exception as exc:
        logger.warning("HSI index regime fetch failed: %s", exc)
        return {
            "status": "error",
            "code": INDEX_CODE,
            "name": INDEX_NAME,
            "message": str(exc),
            "turtle_trend_ok": None,
            "close_vs_ma100": None,
            "atr_pct": None,
            "close": None,
        }

    if not isinstance(result, dict):
        return {
            "status": "error",
            "code": INDEX_CODE,
            "name": INDEX_NAME,
            "message": "invalid index result",
            "turtle_trend_ok": None,
            "close_vs_ma100": None,
            "atr_pct": None,
            "close": None,
        }

    status = str(result.get("status") or "empty")
    trend = result.get("turtle_trend_ok")
    return {
        "status": status,
        "code": INDEX_CODE,
        "name": result.get("name") or INDEX_NAME,
        "message": result.get("message"),
        "turtle_trend_ok": bool(trend) if status == "ok" else None,
        "close_vs_ma100": result.get("close_vs_ma100") if status == "ok" else None,
        "atr_pct": result.get("atr_pct") if status == "ok" else None,
        "close": result.get("close") if status == "ok" else None,
        "row": result,
    }


def apply_monitor_to_scan_payload(
    payload: Dict[str, Any],
    *,
    period: str,
    limit: int,
    max_extension_n: float = DEFAULT_MAX_EXTENSION_N,
    rows: Optional[Sequence[Dict[str, Any]]] = None,
    index_regime: Optional[Dict[str, Any]] = None,
    fetch_index: bool = True,
    market: Optional[str] = None,
    as_of: Optional[date] = None,
    persist_state: Optional[bool] = None,
    delta_enabled: Optional[bool] = None,
) -> Dict[str, Any]:
    """Classify ``results`` into monitor lists and attach them on ``payload``."""
    if payload.get("skipped"):
        payload["monitor"] = True
        payload["uprising"] = []
        payload["reversal"] = []
        payload["uprising_suppressed"] = False
        payload["index_regime"] = None
        return payload

    source = list(rows if rows is not None else (payload.get("results") or payload.get("matches") or []))
    if index_regime is None and fetch_index:
        index_regime = fetch_hsi_index_regime(period)
    payload["index_regime"] = index_regime

    index_ok = None
    if isinstance(index_regime, dict) and index_regime.get("status") == "ok":
        flag = index_regime.get("turtle_trend_ok")
        index_ok = bool(flag) if flag is not None else None

    classified = classify_daily_monitor(
        source,
        limit=limit,
        max_extension_n=max_extension_n,
        index_trend_ok=index_ok,
    )
    payload["monitor"] = True
    payload["uprising"] = classified["uprising"]
    payload["reversal"] = classified["reversal"]
    payload["uprising_suppressed"] = classified["uprising_suppressed"]
    payload["matches"] = classified["matches"]
    stats = dict(payload.get("stats") or {})
    stats["uprising"] = len(classified["uprising"])
    stats["reversal"] = len(classified["reversal"])
    stats["uprising_total"] = classified["uprising_total"]
    stats["reversal_total"] = classified["reversal_total"]
    stats["uprising_suppressed"] = classified["uprising_suppressed"]
    stats["monitor_limit"] = classified["limit"]
    stats["max_extension_n"] = classified["max_extension_n"]
    payload["stats"] = stats
    apply_monitor_delta(
        payload,
        market=market,
        as_of=as_of,
        source_rows=source,
        persist=persist_state if persist_state is not None else bool(market),
        enabled=delta_enabled,
    )
    return payload


def monitor_state_dir() -> Path:
    raw = (os.getenv("MONITOR_STATE_DIR") or "data/monitor_state").strip()
    path = Path(raw).expanduser()
    return path if path.is_absolute() else (_PROJECT_ROOT / path)


def resolve_monitor_delta_enabled(override: Optional[bool] = None) -> bool:
    if override is not None:
        return bool(override)
    return _env_bool("MONITOR_DELTA", True)


def _code_key(row: Dict[str, Any]) -> str:
    return str(row.get("code") or "").strip().upper()


def _payload_as_of(payload: Dict[str, Any], fallback: Optional[date] = None) -> date:
    for row in list(payload.get("uprising") or []) + list(payload.get("reversal") or []) + list(
        payload.get("results") or []
    ):
        raw = row.get("date")
        if not raw:
            continue
        try:
            return date.fromisoformat(str(raw)[:10])
        except ValueError:
            continue
    regime = payload.get("index_regime") or {}
    nested = regime.get("row") if isinstance(regime, dict) else None
    raw = (nested or {}).get("date") if isinstance(nested, dict) else None
    if raw:
        try:
            return date.fromisoformat(str(raw)[:10])
        except ValueError:
            pass
    return fallback or date.today()


def _snapshot_name(row: Dict[str, Any], bucket: str) -> Dict[str, Any]:
    return {
        "code": _code_key(row),
        "name": row.get("name") or _code_key(row),
        "bucket": bucket,
        "close": row.get("close"),
        "low": row.get("low"),
        "n": row.get("n"),
        "stop_long_2n": row.get("stop_long_2n"),
        "s1_recent_close_breakout": bool(row.get("s1_recent_close_breakout")),
        "s2_recent_close_breakout": bool(row.get("s2_recent_close_breakout")),
        "monitor_event": row.get("monitor_event") or monitor_event_label(row),
    }


def build_monitor_snapshot(
    payload: Dict[str, Any],
    *,
    market: str,
    as_of: date,
) -> Dict[str, Any]:
    names: List[Dict[str, Any]] = []
    for bucket in ("uprising", "reversal"):
        for row in payload.get(bucket) or []:
            code = _code_key(row)
            if code:
                names.append(_snapshot_name(row, bucket))
    index_ok = None
    regime = payload.get("index_regime")
    if isinstance(regime, dict) and regime.get("status") == "ok":
        flag = regime.get("turtle_trend_ok")
        index_ok = bool(flag) if flag is not None else None
    return {
        "as_of": as_of.isoformat(),
        "market": market,
        "index_trend_ok": index_ok,
        "names": names,
    }


def save_monitor_snapshot(snapshot: Dict[str, Any], *, market: str, as_of: date) -> Path:
    directory = monitor_state_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{market}_{as_of.isoformat()}.json"
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_previous_monitor_snapshot(market: str, as_of: date) -> Optional[Dict[str, Any]]:
    directory = monitor_state_dir()
    if not directory.is_dir():
        return None
    found: List[tuple[date, Path]] = []
    prefix = f"{market}_"
    for path in directory.glob(f"{prefix}*.json"):
        stamp = path.name[len(prefix) : -5]
        try:
            day = date.fromisoformat(stamp)
        except ValueError:
            continue
        if day < as_of:
            found.append((day, path))
    if not found:
        return None
    found.sort(key=lambda item: item[0], reverse=True)
    path = found[0][1]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Ignoring unreadable monitor snapshot %s: %s", path, exc)
        return None
    if not isinstance(data, dict):
        return None
    return data


def is_follow_through_failed(
    yesterday: Dict[str, Any],
    today_row: Optional[Dict[str, Any]],
) -> bool:
    if not today_row:
        return False
    stop = _as_float(yesterday.get("stop_long_2n"))
    low = _as_float(today_row.get("low"))
    close = _as_float(today_row.get("close"))
    if stop is not None:
        if low is not None and low <= stop:
            return True
        if close is not None and close <= stop:
            return True
    if yesterday.get("s2_recent_close_breakout"):
        return today_row.get("close_vs_s2_entry") is False
    if yesterday.get("s1_recent_close_breakout"):
        return today_row.get("close_vs_entry") is False
    return False


def apply_monitor_delta(
    payload: Dict[str, Any],
    *,
    market: Optional[str] = None,
    as_of: Optional[date] = None,
    source_rows: Optional[Sequence[Dict[str, Any]]] = None,
    persist: bool = False,
    enabled: Optional[bool] = None,
) -> Dict[str, Any]:
    """Attach New/Still/Left/换桶 plus follow-through-failed tags."""
    if not resolve_monitor_delta_enabled(enabled) or payload.get("skipped"):
        payload["monitor_delta"] = {"available": False, "reason": "disabled"}
        return payload
    if not market:
        payload["monitor_delta"] = {"available": False, "reason": "no_market"}
        return payload

    session = as_of or _payload_as_of(payload)
    snapshot = load_previous_monitor_snapshot(market, session)
    results_by_code = {
        _code_key(row): row
        for row in (source_rows or payload.get("results") or [])
        if _code_key(row)
    }
    today_bucket = {}
    for bucket in ("uprising", "reversal"):
        for row in payload.get(bucket) or []:
            code = _code_key(row)
            if code:
                today_bucket[code] = bucket

    if not snapshot:
        for bucket in ("uprising", "reversal"):
            for row in payload.get(bucket) or []:
                row["monitor_delta"] = None
                row["follow_through_failed"] = False
        payload["monitor_delta"] = {"available": False, "reason": "no_yesterday", "as_of": session.isoformat()}
    else:
        yesterday_names = [
            item for item in (snapshot.get("names") or []) if isinstance(item, dict) and item.get("code")
        ]
        yesterday_by_code = {str(item.get("code") or "").strip().upper(): item for item in yesterday_names}
        left: List[Dict[str, Any]] = []
        follow_failed: List[Dict[str, Any]] = []
        for code, yest in yesterday_by_code.items():
            today_row = results_by_code.get(code)
            ft = is_follow_through_failed(yest, today_row)
            yest_bucket = str(yest.get("bucket") or "")
            if code not in today_bucket:
                left.append(
                    {
                        **yest,
                        "from_bucket": yest_bucket,
                        "follow_through_failed": ft,
                    }
                )
            if ft:
                follow_failed.append(
                    {
                        **yest,
                        "from_bucket": yest_bucket,
                        "today_bucket": today_bucket.get(code),
                        "follow_through_failed": True,
                    }
                )
        for bucket in ("uprising", "reversal"):
            for row in payload.get(bucket) or []:
                code = _code_key(row)
                yest = yesterday_by_code.get(code)
                if not yest:
                    row["monitor_delta"] = "新"
                elif str(yest.get("bucket") or "") == bucket:
                    row["monitor_delta"] = "仍在"
                else:
                    row["monitor_delta"] = "换桶"
                row["follow_through_failed"] = is_follow_through_failed(yest, row) if yest else False
        payload["monitor_delta"] = {
            "available": True,
            "as_of": snapshot.get("as_of"),
            "left": left,
            "follow_through_failed": follow_failed,
        }

    if persist:
        save_monitor_snapshot(build_monitor_snapshot(payload, market=market, as_of=session), market=market, as_of=session)
    return payload


def apply_holdings_monitor_overlay(
    payload: Dict[str, Any],
    holdings: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Tag listed names that are holdings and attach a compact overlay."""
    rows = list(holdings if holdings is not None else (payload.get("holdings") or []))
    by_code = {_code_key(row): row for row in rows if _code_key(row)}
    listed: Dict[str, str] = {}
    for bucket, label in (("uprising", "趋势首破"), ("reversal", "止跌转折")):
        for row in payload.get(bucket) or []:
            code = _code_key(row)
            if not code:
                continue
            listed[code] = label
            holding = by_code.get(code)
            if holding:
                row["is_holding"] = True
                row["distance_to_stop_n"] = holding.get("distance_to_stop_n")
                row["turtle_action"] = holding.get("turtle_action")
            else:
                row.setdefault("is_holding", False)
    overlay: List[Dict[str, Any]] = []
    for row in rows:
        code = _code_key(row)
        if not code:
            continue
        item = dict(row)
        item["monitor_location"] = listed.get(code) or "未入名单"
        overlay.append(item)
    payload["holdings_overlay"] = overlay
    return payload


def format_holdings_overlay_lines(payload: Dict[str, Any]) -> List[str]:
    overlay = list(payload.get("holdings_overlay") or [])
    if not overlay:
        return []
    action_label = {"sell": "卖出", "keep": "持有", "buy": "加仓"}
    lines = ["## 持仓对照", ""]
    for row in overlay:
        code = row.get("code") or ""
        name = row.get("name") or code
        loc = row.get("monitor_location") or "未入名单"
        action = action_label.get(str(row.get("turtle_action") or "keep"), row.get("turtle_action") or "持有")
        dist = row.get("distance_to_stop_n")
        dist_txt = f"{dist}" if dist is not None else "暂无"
        lines.append(f"- **{name} ({code})**: {loc} | {action} | 距2N={dist_txt}")
    lines.append("")
    return lines


def format_index_regime_lines(index_regime: Optional[Dict[str, Any]]) -> List[str]:
    from src.services.hsi_scanner import format_atr_pct_cell, format_ma100_cell

    lines = ["## 大盘", ""]
    if not index_regime:
        lines.append("- 恒指数据不足")
        lines.append("")
        return lines
    status = index_regime.get("status")
    if status != "ok":
        message = index_regime.get("message") or status or "暂无"
        lines.append(f"- 恒指数据不足: {message}")
        lines.append("")
        return lines
    trend = "通过" if index_regime.get("turtle_trend_ok") else "未过"
    ma100 = format_ma100_cell(index_regime.get("close_vs_ma100"))
    atr = format_atr_pct_cell(index_regime.get("atr_pct"))
    close = index_regime.get("close")
    close_bit = f" | 收盘 {close}" if close is not None else ""
    lines.append(f"- 恒生指数: 趋势{trend} | MA100 {ma100} | ATR% {atr}{close_bit}")
    lines.append("")
    return lines


def format_monitor_table_lines(rows: Sequence[Dict[str, Any]]) -> List[str]:
    """Compact daily-monitor table: event + risk/liquidity, no potential grade."""
    from src.services.hsi_scanner import (
        _report_cell,
        format_atr_pct_cell,
        format_ma100_cell,
        format_recent_breakout_timing,
        format_turnover_cell,
    )

    lines = [
        "| 代号 | 名称 | 收盘 | 对照 | 持仓 | 距2N | 事件 | S1开 | 趋势 | MA100 | 延伸N | 量比 | 均额 | ATR% | S1近C | S2近C |",
        "|------|------|------|------|------|------|------|------|------|------|------|------|------|------|------|------|",
    ]
    for row in rows or []:
        event = row.get("monitor_event") or monitor_event_label(row)
        delta = row.get("monitor_delta") or "—"
        if row.get("follow_through_failed"):
            delta = f"{delta}·跟丢" if delta and delta != "—" else "跟丢"
        holding = "是" if row.get("is_holding") else "—"
        dist = row.get("distance_to_stop_n")
        dist_txt = _report_cell(dist) if dist is not None else "—"
        lines.append(
            f"| [{row.get('code', '')}]({row.get('url', '')}) | {row.get('name', '')} "
            f"| {_report_cell(row.get('close'))} "
            f"| {delta} "
            f"| {holding} "
            f"| {dist_txt} "
            f"| {event} "
            f"| {'是' if row.get('s1_entry_allowed') else '否'} "
            f"| {'通过' if row.get('turtle_trend_ok') else '未过'} "
            f"| {format_ma100_cell(row.get('close_vs_ma100'))} "
            f"| {_report_cell(row.get('breakout_extension_n'))} "
            f"| {_report_cell(row.get('volume_ratio'))} "
            f"| {format_turnover_cell(row.get('avg_turnover_20'))} "
            f"| {format_atr_pct_cell(row.get('atr_pct'))} "
            f"| {format_recent_breakout_timing(row.get('s1_recent_close_timing'))} "
            f"| {format_recent_breakout_timing(row.get('s2_recent_close_timing'))} |"
        )
    return lines


def format_monitor_fact_lines(row: Dict[str, Any]) -> List[str]:
    from src.services.hsi_scanner import format_atr_pct_cell, format_turnover_cell

    code = row.get("code", "")
    name = row.get("name") or code
    event = row.get("monitor_event") or monitor_event_label(row)
    n_val = row.get("n")
    stop_2n = row.get("stop_long_2n")
    ext_n = row.get("breakout_extension_n")
    vol_ratio = row.get("volume_ratio")
    turnover = format_turnover_cell(row.get("avg_turnover_20"))
    atr = format_atr_pct_cell(row.get("atr_pct"))
    return [
        f"- **{name} ({code})**: {event}",
        (
            f"  - N={n_val if n_val is not None else '暂无'}"
            f" | 2N止损={stop_2n if stop_2n is not None else '暂无'}"
            f" | 延伸N={ext_n if ext_n is not None else '暂无'}"
            f" | 量比={vol_ratio if vol_ratio is not None else '暂无'}"
            f" | 均额={turnover}"
            f" | ATR%={atr}"
        ),
    ]


def _format_delta_follow_section(payload: Dict[str, Any], bucket: str) -> List[str]:
    delta = payload.get("monitor_delta") or {}
    if not delta.get("available"):
        if delta.get("reason") == "no_yesterday":
            return ["无昨日对照。\n"]
        return []
    left = [
        item for item in (delta.get("left") or [])
        if str(item.get("from_bucket") or item.get("bucket") or "") == bucket
    ]
    failed = [
        item for item in (delta.get("follow_through_failed") or [])
        if str(item.get("from_bucket") or item.get("bucket") or "") == bucket
        or str(item.get("today_bucket") or "") == bucket
    ]
    lines = ["### 离开 / 跟丢\n"]
    if not left and not failed:
        lines.append("无。\n")
        return lines
    for item in left:
        tag = "跟丢" if item.get("follow_through_failed") else "离开"
        lines.append(
            f"- {tag}: {item.get('name') or ''} ({item.get('code')}) "
            f"{item.get('monitor_event') or ''}".rstrip()
        )
    seen = {str(item.get("code") or "") for item in left}
    for item in failed:
        code = str(item.get("code") or "")
        if code in seen:
            continue
        lines.append(f"- 跟丢: {item.get('name') or ''} ({code})")
    lines.append("")
    return lines


def format_monitor_list_sections(payload: Dict[str, Any]) -> List[str]:
    """Render 趋势首破 / 止跌转折 tables plus short fact lines."""
    uprising = list(payload.get("uprising") or [])
    reversal = list(payload.get("reversal") or [])
    suppressed = bool(payload.get("uprising_suppressed"))
    stats = payload.get("stats") or {}
    cap = stats.get("monitor_limit")
    delta = payload.get("monitor_delta") or {}
    lines: List[str] = []
    lines.extend(format_holdings_overlay_lines(payload))

    if delta.get("available") is False and delta.get("reason") == "no_yesterday":
        lines.append("- 无昨日对照\n")

    lines.append("## 趋势首破\n")
    if suppressed:
        lines.append("大盘趋势未过，今日不列趋势首破。\n")
        lines.extend(_format_delta_follow_section(payload, "uprising"))
    elif uprising:
        total = stats.get("uprising_total", len(uprising))
        if cap and total > len(uprising):
            lines.append(f"显示 {len(uprising)} / {total}（上限 {cap}）\n")
        lines.extend(format_monitor_table_lines(uprising))
        lines.append("")
        lines.extend(_format_delta_follow_section(payload, "uprising"))
        lines.append("### 要点\n")
        for row in uprising:
            lines.extend(format_monitor_fact_lines(row))
            lines.append("")
    else:
        lines.append("没有股票符合趋势首破条件。\n")
        lines.extend(_format_delta_follow_section(payload, "uprising"))

    lines.append("## 止跌转折\n")
    if reversal:
        total = stats.get("reversal_total", len(reversal))
        if cap and total > len(reversal):
            lines.append(f"显示 {len(reversal)} / {total}（上限 {cap}）\n")
        lines.extend(format_monitor_table_lines(reversal))
        lines.append("")
        lines.extend(_format_delta_follow_section(payload, "reversal"))
        lines.append("### 要点\n")
        for row in reversal:
            lines.extend(format_monitor_fact_lines(row))
            lines.append("")
    else:
        lines.append("没有股票符合止跌转折条件。\n")
        lines.extend(_format_delta_follow_section(payload, "reversal"))

    return lines
