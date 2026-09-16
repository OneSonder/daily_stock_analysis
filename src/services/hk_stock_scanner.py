# -*- coding: utf-8 -*-
"""All-HK Turtle signal scan (no LLM): committed universe + matches + Tencent news."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from src.services.daily_monitor import (
    DEFAULT_HK_MONITOR_LIMIT,
    apply_monitor_to_scan_payload,
    format_index_regime_lines,
    format_monitor_list_sections,
    resolve_max_extension_n,
    resolve_monitor_enabled,
    resolve_monitor_limit,
)
from src.services.hsi_holdings import normalize_holding_code
from src.services.hsi_scanner import (
    format_match_result_table_lines,
    format_match_technical_lines,
    get_scan_config_from_env,
    scan_stocks,
    sort_matches_by_potential,
)
from src.services.stock_universes import HK_ALL_STOCKS_PATH, load_hk_all_stocks

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 80
DEFAULT_MAX_WORKERS = 8
DEFAULT_NEWS_MAX_AGE_DAYS = 2
DEFAULT_PERIOD = "1y"
DEFAULT_CONDITIONS = "s1_breakout,s2_breakout"
DEFAULT_MIN_PRICE = 0.1
DEFAULT_MIN_AVG_TURNOVER = 2_000_000.0


class HkUniverseError(RuntimeError):
    """Raised when the committed HK universe cannot be loaded."""


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def resolve_hk_scan_batch_size(batch_size: Optional[int] = None) -> int:
    """Yahoo bulk chunk size for all-HK scans (default 80)."""
    if batch_size is not None:
        return max(1, int(batch_size))
    return max(1, _env_int("HK_SCAN_BATCH_SIZE", DEFAULT_BATCH_SIZE))


def resolve_hk_news_max_age_days(max_age_days: Optional[int] = None) -> int:
    """Freshness window for match-only Tencent news (default 2 days)."""
    if max_age_days is not None:
        return max(1, int(max_age_days))
    return max(1, _env_int("HK_NEWS_MAX_AGE_DAYS", DEFAULT_NEWS_MAX_AGE_DAYS))


def _env_float(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def resolve_hk_min_price(min_price: Optional[float] = None) -> float:
    """Minimum last close for HK matches (0 disables). Default 0.1."""
    if min_price is not None:
        return max(0.0, float(min_price))
    return max(0.0, _env_float("HK_SCAN_MIN_PRICE", DEFAULT_MIN_PRICE))


def resolve_hk_min_avg_turnover(min_avg_turnover: Optional[float] = None) -> float:
    """Minimum 20-day average turnover for HK matches (0 disables). Default 2000000."""
    if min_avg_turnover is not None:
        return max(0.0, float(min_avg_turnover))
    return max(0.0, _env_float("HK_SCAN_MIN_AVG_TURNOVER", DEFAULT_MIN_AVG_TURNOVER))


def _env_bool(name: str, default: bool) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    return default


def resolve_hk_require_volume_confirm(require_volume_confirm: Optional[bool] = None) -> bool:
    """When true, drop names with volume data that fail volume_confirm."""
    if require_volume_confirm is not None:
        return bool(require_volume_confirm)
    return _env_bool("HK_SCAN_REQUIRE_VOLUME_CONFIRM", False)


def resolve_hk_require_trend(require_trend: Optional[bool] = None) -> bool:
    """When true, drop matches that fail turtle_trend_ok. Default true (legacy dump only)."""
    if require_trend is not None:
        return bool(require_trend)
    return _env_bool("HK_SCAN_REQUIRE_TREND", True)


def resolve_hk_monitor_enabled(monitor: Optional[bool] = None) -> bool:
    """Daily two-list monitor. Default true; false restores the OR-conditions dump."""
    return resolve_monitor_enabled("HK_SCAN_MONITOR", default=True, override=monitor)


def resolve_hk_require_ma100(require_ma100: Optional[bool] = None) -> bool:
    """When true, drop names with close_vs_ma100 is False. Missing MA100 does not drop.

    Needs ~100 trading days (use ``period=1y``). On ``3mo`` this gate is a no-op.
    """
    if require_ma100 is not None:
        return bool(require_ma100)
    return _env_bool("HK_SCAN_REQUIRE_MA100", False)


def _as_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def liquidity_filter_reason(
    row: Dict[str, Any],
    *,
    min_price: float,
    min_avg_turnover: float,
    require_volume_confirm: bool,
    require_trend: bool,
    require_ma100: bool,
) -> Optional[str]:
    """Return a reason if the match fails HK quality gates; missing optional data does not fail."""
    close = _as_float(row.get("close"))
    if min_price > 0 and close is not None and close < min_price:
        return f"close {close} < min_price {min_price}"
    turnover = _as_float(row.get("avg_turnover_20"))
    if min_avg_turnover > 0 and turnover is not None and turnover < min_avg_turnover:
        return f"avg_turnover_20 {turnover} < {min_avg_turnover}"
    if require_volume_confirm:
        ratio = _as_float(row.get("volume_ratio"))
        if ratio is not None and not bool(row.get("volume_confirm")):
            return "volume not confirmed"
    if require_trend and not bool(row.get("turtle_trend_ok")):
        return "turtle_trend_ok is false"
    if require_ma100 and row.get("close_vs_ma100") is False:
        return "close below MA100"
    return None


def apply_hk_liquidity_gates(
    matches: Sequence[Dict[str, Any]],
    *,
    min_price: Optional[float] = None,
    min_avg_turnover: Optional[float] = None,
    require_volume_confirm: Optional[bool] = None,
    require_trend: Optional[bool] = None,
    require_ma100: Optional[bool] = None,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Split matches into kept vs quality-filtered (missing volume/MA100 does not drop)."""
    price_floor = resolve_hk_min_price(min_price)
    turnover_floor = resolve_hk_min_avg_turnover(min_avg_turnover)
    require_vol = resolve_hk_require_volume_confirm(require_volume_confirm)
    require_trend_ok = resolve_hk_require_trend(require_trend)
    require_above_ma100 = resolve_hk_require_ma100(require_ma100)
    kept: List[Dict[str, Any]] = []
    dropped: List[Dict[str, Any]] = []
    for row in matches or []:
        reason = liquidity_filter_reason(
            row,
            min_price=price_floor,
            min_avg_turnover=turnover_floor,
            require_volume_confirm=require_vol,
            require_trend=require_trend_ok,
            require_ma100=require_above_ma100,
        )
        if reason:
            dropped.append({**row, "liquidity_filter_reason": reason})
        else:
            kept.append(row)
    return kept, dropped


def normalize_hk_code(raw: Any) -> Optional[str]:
    """Normalize HK codes to Yahoo-style ``0700.HK``."""
    text = str(raw or "").strip().upper()
    if not text:
        return None
    code = normalize_holding_code(text)
    if not code or not code.endswith(".HK"):
        return None
    base = code[:-3]
    if not base.isdigit():
        return None
    return code


def resolve_hk_universe_path(universe_path: Optional[Path | str] = None) -> Path:
    """Resolve the committed HK universe JSON path (env override supported)."""
    if universe_path is not None:
        return Path(universe_path)
    env_path = (os.getenv("HK_SCAN_UNIVERSE_PATH") or "").strip()
    if env_path:
        return Path(env_path)
    return HK_ALL_STOCKS_PATH


def load_hk_stocks_universe(
    *,
    universe_path: Optional[Path | str] = None,
    force_reload: bool = False,
) -> List[Dict[str, str]]:
    """Load HK stocks from the committed JSON snapshot (default ``hk_all_stocks.json``)."""
    path = resolve_hk_universe_path(universe_path)
    try:
        if path.resolve() == HK_ALL_STOCKS_PATH.resolve():
            stocks = load_hk_all_stocks(force_reload=force_reload)
        else:
            stocks = _load_universe_json(path)
    except FileNotFoundError as exc:
        raise HkUniverseError(
            f"HK universe snapshot not found: {path}. "
            "Run: python scripts/generate_hk_universe.py"
        ) from exc
    except Exception as exc:
        raise HkUniverseError(f"Failed to load HK universe from {path}: {exc}") from exc

    if not stocks:
        raise HkUniverseError(f"HK universe is empty: {path}")

    normalized: List[Dict[str, str]] = []
    seen: set[str] = set()
    for item in stocks:
        code = normalize_hk_code(item.get("code"))
        if not code or code in seen:
            continue
        seen.add(code)
        name = str(item.get("name") or "").strip() or code
        normalized.append({"code": code, "name": name})

    if not normalized:
        raise HkUniverseError(f"No valid HK codes in universe: {path}")

    logger.info("Loaded %s HK stocks from %s", len(normalized), path)
    return normalized


def _load_universe_json(path: Path) -> List[Dict[str, str]]:
    import json

    if not path.is_file():
        raise FileNotFoundError(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"universe must be a JSON list, got {type(raw).__name__}")
    stocks: List[Dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        stocks.append(
            {
                "code": str(item.get("code") or "").strip(),
                "name": str(item.get("name") or "").strip(),
            }
        )
    return stocks


def fetch_tencent_news_for_matches(
    matches: Sequence[Dict[str, Any]],
    *,
    max_age_days: Optional[int] = None,
    enabled: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """Fetch Tencent ifzq news only for matched symbols (soft-fail per code)."""
    from src.services.tencent_stock_news import (
        fetch_tencent_stock_news,
        filter_fresh_news_items,
        format_tencent_news_context,
        is_tencent_stock_news_enabled,
    )

    news_enabled = is_tencent_stock_news_enabled() if enabled is None else bool(enabled)
    window = resolve_hk_news_max_age_days(max_age_days)
    out: List[Dict[str, Any]] = []
    for match in matches or []:
        code = str(match.get("code") or "").strip().upper()
        name = str(match.get("name") or code).strip()
        item: Dict[str, Any] = {
            "code": code,
            "name": name,
            "news_text": "",
            "news_error": None,
            "news_count": 0,
        }
        if not code:
            item["news_error"] = "missing code"
            out.append(item)
            continue
        if not news_enabled:
            item["news_error"] = "tencent news disabled"
            out.append(item)
            continue
        try:
            raw_items = fetch_tencent_stock_news(code, n=10)
            fresh = filter_fresh_news_items(raw_items, max_age_days=window)
            text = format_tencent_news_context(fresh, max_items=10)
            item["news_text"] = text
            item["news_count"] = len(fresh)
            if not text:
                item["news_error"] = "no fresh news"
        except Exception as exc:
            logger.warning("Tencent news failed for %s: %s", code, exc)
            item["news_error"] = str(exc)
        out.append(item)
    return out


def _hk_news_section(
    matches: Sequence[Dict[str, Any]],
    news_map: Dict[str, Dict[str, Any]],
) -> List[str]:
    lines: List[str] = ["## 腾讯新闻（仅匹配股）\n"]
    if not matches:
        lines.append("无匹配股，未抓取新闻。\n")
        return lines
    for m in matches:
        code = str(m.get("code") or "").strip().upper()
        name = m.get("name") or code
        news = news_map.get(code) or {}
        lines.append(f"### {name} ({code})\n")
        err = news.get("news_error")
        text = (news.get("news_text") or "").strip()
        if err and not text:
            lines.append(f"- 新闻不可用: {err}")
        elif text:
            lines.append(text)
        else:
            lines.append("- 未检索到有效新闻")
        lines.append("")
    return lines


def format_hk_scan_report(
    payload: Dict[str, Any],
    news_by_code: Optional[Dict[str, Dict[str, Any]]] = None,
) -> str:
    """Build a no-LLM HK scan report: daily monitor lists or legacy match dump."""
    stats = payload.get("stats") or {}
    news_map = news_by_code or {}
    filtered_n = len(payload.get("filtered_illiquid") or [])
    monitor = bool(payload.get("monitor"))
    matches = list(payload.get("matches") or [])
    if not monitor:
        matches = sort_matches_by_potential(matches)

    if payload.get("skipped"):
        skip_reason = payload.get("skip_reason") or "今日休市"
        if skip_reason == "HK market closed today":
            skip_reason = "今日港股休市"
        return f"# 全港股海龟扫描已跳过\n\n{skip_reason}"

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines: List[str] = [
        (
            f"# 全港股海龟扫描 — {stats.get('tickers', '?')} 只股票，"
            f"耗时 {stats.get('total_ms', '?')}ms"
        ),
        f"*扫描时间：{timestamp}*",
        "",
        "## 扫描摘要",
        "",
        f"- 扫描池: {stats.get('tickers', '?')} 只",
        f"- 股票池来源: {payload.get('universe_source') or 'resources/universes/hk_all_stocks.json'}",
    ]
    if monitor:
        lines.append("- 模式: 每日监控（趋势首破 / 止跌转折）")
        lines.append(
            f"- 趋势首破: {len(payload.get('uprising') or [])}"
            f"（候选 {stats.get('uprising_total', 0)}）"
        )
        lines.append(
            f"- 止跌转折: {len(payload.get('reversal') or [])}"
            f"（候选 {stats.get('reversal_total', 0)}）"
        )
    else:
        lines.append(f"- 匹配条件: {', '.join(payload.get('conditions') or []) or '暂无'}")
        lines.append(f"- 匹配数: {len(matches)}（按潜力分降序）")
    lines.extend(
        [
            f"- 流动性过滤: {filtered_n}",
            f"- 无行情: {len(payload.get('no_price') or [])}",
            f"- 缓存命中: {stats.get('cache_hits', 0)}",
            f"- 批量下载: {stats.get('batch_downloaded', 0)}",
            (
                f"- 批量失败未回退: "
                f"{stats.get('unavailable_without_fallback', 0)}"
            ),
            "",
        ]
    )

    if monitor:
        lines.extend(format_index_regime_lines(payload.get("index_regime")))
        lines.extend(format_monitor_list_sections(payload))
    elif matches:
        lines.append(f"## 匹配结果（{len(matches)}）\n")
        lines.extend(format_match_result_table_lines(matches))
        lines.append("")
        lines.append("### 技术指标与形态\n")
        for m in matches:
            lines.extend(format_match_technical_lines(m))
            lines.append("")
    else:
        lines.append("没有股票符合所选条件。\n")

    lines.extend(_hk_news_section(matches, news_map))
    return "\n".join(lines).rstrip() + "\n"


def save_hk_scan_report(report_text: str, reports_dir: Optional[Path] = None) -> Path:
    """Write report to reports/hk_stocks_scan_YYYYMMDD_HHMMSS.md."""
    root = Path(reports_dir) if reports_dir is not None else Path("reports")
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = root / f"hk_stocks_scan_{stamp}.md"
    path.write_text(report_text, encoding="utf-8")
    return path


def run_hk_stocks_scan(
    *,
    period: Optional[str] = None,
    conditions: Optional[str] = None,
    max_workers: Optional[int] = None,
    batch_size: Optional[int] = None,
    news_max_age_days: Optional[int] = None,
    check_trading_day: bool = True,
    use_multi_source: bool = False,
    allow_per_ticker_fallback: bool = False,
    reports_dir: Optional[Path] = None,
    save_report: bool = True,
    stocks: Optional[List[Dict[str, str]]] = None,
    universe_path: Optional[Path | str] = None,
    min_price: Optional[float] = None,
    min_avg_turnover: Optional[float] = None,
    require_volume_confirm: Optional[bool] = None,
    require_trend: Optional[bool] = None,
    require_ma100: Optional[bool] = None,
    monitor: Optional[bool] = None,
    monitor_limit: Optional[int] = None,
    max_extension_n: Optional[float] = None,
) -> Dict[str, Any]:
    """Scan all listed HK stocks with Turtle signals + match-only Tencent news.

    Universe defaults to ``resources/universes/hk_all_stocks.json``.
    No LLM / AI analyzers are instantiated on this path.
    Default is daily-monitor mode (two short lists). Set ``monitor=False``
    to restore the OR-conditions dump.
    """
    env_cfg = get_scan_config_from_env()
    resolved_period = period or os.getenv("HK_SCAN_PERIOD") or DEFAULT_PERIOD
    resolved_conditions = (
        conditions
        or os.getenv("HK_SCAN_CONDITIONS")
        or env_cfg.get("conditions")
        or DEFAULT_CONDITIONS
    )
    resolved_workers = (
        max_workers
        if max_workers is not None
        else _env_int("HK_SCAN_MAX_WORKERS", int(env_cfg.get("max_workers") or DEFAULT_MAX_WORKERS))
    )
    resolved_batch = resolve_hk_scan_batch_size(batch_size)
    resolved_news_days = resolve_hk_news_max_age_days(news_max_age_days)
    resolved_universe_path = resolve_hk_universe_path(universe_path)
    resolved_min_price = resolve_hk_min_price(min_price)
    resolved_min_turnover = resolve_hk_min_avg_turnover(min_avg_turnover)
    resolved_monitor = resolve_hk_monitor_enabled(monitor)
    resolved_limit = resolve_monitor_limit(
        "HK_SCAN_MONITOR_LIMIT",
        DEFAULT_HK_MONITOR_LIMIT,
        override=monitor_limit,
    )
    resolved_extension = resolve_max_extension_n(
        "HK_SCAN_MAX_EXTENSION_N",
        override=max_extension_n,
    )
    if resolved_monitor:
        resolved_require_vol = False
        resolved_require_trend = False
        resolved_require_ma100 = False
    else:
        resolved_require_vol = resolve_hk_require_volume_confirm(require_volume_confirm)
        resolved_require_trend = resolve_hk_require_trend(require_trend)
        resolved_require_ma100 = resolve_hk_require_ma100(require_ma100)

    if stocks is not None:
        universe = list(stocks)
        universe_source = "provided"
    else:
        universe = load_hk_stocks_universe(universe_path=resolved_universe_path)
        universe_source = str(resolved_universe_path).replace("\\", "/")

    payload = scan_stocks(
        stocks=universe,
        period=resolved_period,
        conditions=resolved_conditions,
        max_workers=max(1, int(resolved_workers)),
        check_trading_day=check_trading_day,
        use_multi_source=use_multi_source,
        batch_size=resolved_batch,
        allow_per_ticker_fallback=allow_per_ticker_fallback,
    )
    payload["universe_source"] = universe_source
    payload["universe_size"] = len(universe)

    if not payload.get("skipped"):
        if resolved_monitor:
            source_rows = payload.get("results") or payload.get("matches") or []
        else:
            source_rows = payload.get("matches") or []
        kept, dropped = apply_hk_liquidity_gates(
            source_rows,
            min_price=resolved_min_price,
            min_avg_turnover=resolved_min_turnover,
            require_volume_confirm=resolved_require_vol,
            require_trend=resolved_require_trend,
            require_ma100=resolved_require_ma100,
        )
        payload["filtered_illiquid"] = dropped
        stats = dict(payload.get("stats") or {})
        stats["liquidity_filtered"] = len(dropped)
        stats["min_price"] = resolved_min_price
        stats["min_avg_turnover"] = resolved_min_turnover
        stats["require_volume_confirm"] = resolved_require_vol
        stats["require_trend"] = resolved_require_trend
        stats["require_ma100"] = resolved_require_ma100
        stats["monitor"] = resolved_monitor
        payload["stats"] = stats
        if resolved_monitor:
            apply_monitor_to_scan_payload(
                payload,
                period=str(resolved_period),
                limit=resolved_limit,
                max_extension_n=resolved_extension,
                rows=kept,
                market="hk",
            )
            from src.services.hsi_holdings import load_holdings_from_env
            from src.services.hsi_scanner import attach_holdings_to_results
            from src.services.daily_monitor import apply_holdings_monitor_overlay

            holdings_list = load_holdings_from_env()
            if holdings_list:
                payload["holdings"] = attach_holdings_to_results(
                    holdings_list,
                    payload.get("results") or kept,
                )
                apply_holdings_monitor_overlay(payload)
        else:
            payload["monitor"] = False
            payload["matches"] = sort_matches_by_potential(kept)

    news_items: List[Dict[str, Any]] = []
    if not payload.get("skipped"):
        news_items = fetch_tencent_news_for_matches(
            payload.get("matches") or [],
            max_age_days=resolved_news_days,
        )
    news_by_code = {
        str(item.get("code") or "").strip().upper(): item
        for item in news_items
        if item.get("code")
    }

    report_text = format_hk_scan_report(payload, news_by_code=news_by_code)
    report_path: Optional[str] = None
    if save_report:
        report_path = str(save_hk_scan_report(report_text, reports_dir=reports_dir))
        logger.info("HK stocks scan report saved: %s", report_path)

    return {
        "payload": payload,
        "news": news_items,
        "report_text": report_text,
        "report_path": report_path,
        "period": resolved_period,
        "conditions": resolved_conditions,
        "batch_size": resolved_batch,
        "news_max_age_days": resolved_news_days,
        "max_workers": max(1, int(resolved_workers)),
        "universe_path": str(resolved_universe_path),
        "min_price": resolved_min_price,
        "min_avg_turnover": resolved_min_turnover,
        "require_volume_confirm": resolved_require_vol,
        "require_trend": resolved_require_trend,
        "require_ma100": resolved_require_ma100,
        "monitor": resolved_monitor,
    }
