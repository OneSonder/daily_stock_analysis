# -*- coding: utf-8 -*-
"""Daily monitor buckets: trend first-cross vs turn-up. Admission is rule-based, not a forecast."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

INDEX_CODE = "^HSI"
INDEX_NAME = "恒生指数"
DEFAULT_MAX_EXTENSION_N = 1.0
DEFAULT_HK_MONITOR_LIMIT = 15
DEFAULT_HSI_MONITOR_LIMIT = 10


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
    return payload


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
        "| 代号 | 名称 | 收盘 | 事件 | S1开 | 趋势 | MA100 | 延伸N | 量比 | 均额 | ATR% | S1近C | S2近C |",
        "|------|------|------|------|------|------|------|------|------|------|------|------|------|",
    ]
    for row in rows or []:
        event = row.get("monitor_event") or monitor_event_label(row)
        lines.append(
            f"| [{row.get('code', '')}]({row.get('url', '')}) | {row.get('name', '')} "
            f"| {_report_cell(row.get('close'))} "
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


def format_monitor_list_sections(payload: Dict[str, Any]) -> List[str]:
    """Render 趋势首破 / 止跌转折 tables plus short fact lines."""
    uprising = list(payload.get("uprising") or [])
    reversal = list(payload.get("reversal") or [])
    suppressed = bool(payload.get("uprising_suppressed"))
    stats = payload.get("stats") or {}
    cap = stats.get("monitor_limit")
    lines: List[str] = []

    lines.append("## 趋势首破\n")
    if suppressed:
        lines.append("大盘趋势未过，今日不列趋势首破。\n")
    elif uprising:
        total = stats.get("uprising_total", len(uprising))
        if cap and total > len(uprising):
            lines.append(f"显示 {len(uprising)} / {total}（上限 {cap}）\n")
        lines.extend(format_monitor_table_lines(uprising))
        lines.append("")
        lines.append("### 要点\n")
        for row in uprising:
            lines.extend(format_monitor_fact_lines(row))
            lines.append("")
    else:
        lines.append("没有股票符合趋势首破条件。\n")

    lines.append("## 止跌转折\n")
    if reversal:
        total = stats.get("reversal_total", len(reversal))
        if cap and total > len(reversal):
            lines.append(f"显示 {len(reversal)} / {total}（上限 {cap}）\n")
        lines.extend(format_monitor_table_lines(reversal))
        lines.append("")
        lines.append("### 要点\n")
        for row in reversal:
            lines.extend(format_monitor_fact_lines(row))
            lines.append("")
    else:
        lines.append("没有股票符合止跌转折条件。\n")

    return lines
