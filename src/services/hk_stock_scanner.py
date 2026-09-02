# -*- coding: utf-8 -*-
"""All-HK Turtle signal scan (no LLM): committed universe + matches + Tencent news."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from src.services.hsi_holdings import normalize_holding_code
from src.services.hsi_scanner import (
    format_pattern_names,
    format_recent_breakout_timing,
    get_scan_config_from_env,
    scan_stocks,
)
from src.services.stock_universes import HK_ALL_STOCKS_PATH, load_hk_all_stocks

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 80
DEFAULT_MAX_WORKERS = 8
DEFAULT_NEWS_MAX_AGE_DAYS = 2
DEFAULT_PERIOD = "3mo"
DEFAULT_CONDITIONS = "s1_breakout,s2_breakout"


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


def _format_match_technical_block(match: Dict[str, Any]) -> List[str]:
    code = match.get("code", "")
    name = match.get("name", "")
    ma_bits = []
    for key in ("ma5", "ma10", "ma20", "ma60"):
        val = match.get(key)
        if val is not None:
            ma_bits.append(f"{key.upper()}={val}")
    ma_line = ", ".join(ma_bits) if ma_bits else "均线暂无"
    alignment = match.get("ma_alignment") or match.get("trend_status") or "暂无"
    rsi_line = (
        f"RSI6={match.get('rsi_6', '暂无')}, RSI12={match.get('rsi_12', '暂无')}"
        f" ({match.get('rsi_status') or '暂无'})"
    )
    macd_line = (
        f"MACD={match.get('macd_status') or '暂无'}"
        f" DIF={match.get('macd_dif', '暂无')} DEA={match.get('macd_dea', '暂无')}"
    )
    if match.get("macd_signal"):
        macd_line += f" — {match.get('macd_signal')}"
    pattern_text = format_pattern_names(match.get("kline_patterns") or [])
    n_val = match.get("n")
    stop_2n = match.get("stop_long_2n")
    ext_n = match.get("breakout_extension_n")
    trend_ok = match.get("turtle_trend_ok")
    trend_rule = match.get("turtle_trend_rule") or "暂无"
    s1_win = match.get("s1_last_was_winner")
    s1_ok = match.get("s1_entry_allowed")
    return [
        f"- **{name} ({code})**: {alignment}",
        f"  - {ma_line}",
        f"  - {rsi_line}",
        f"  - {macd_line}",
        f"  - 形态: {pattern_text}",
        (
            f"  - 海龟: N={n_val if n_val is not None else '暂无'}"
            f", 2N止损参考={stop_2n if stop_2n is not None else '暂无'}"
            f", 突破延伸N={ext_n if ext_n is not None else '暂无'}"
        ),
        (
            f"  - 趋势过滤: {'通过' if trend_ok else '未通过'}（{trend_rule}）"
            f" | S1上次盈利跳过: {'是' if s1_win else '否'}"
            f" | S1允许开仓: {'是' if s1_ok else '否'}"
        ),
        (
            "  - 近期突破: "
            f"S1 High={format_recent_breakout_timing(match.get('s1_recent_high_timing'))}"
            f" / Close={format_recent_breakout_timing(match.get('s1_recent_close_timing'))}"
            f" | S2 High={format_recent_breakout_timing(match.get('s2_recent_high_timing'))}"
            f" / Close={format_recent_breakout_timing(match.get('s2_recent_close_timing'))}"
        ),
    ]


def format_hk_scan_report(
    payload: Dict[str, Any],
    news_by_code: Optional[Dict[str, Dict[str, Any]]] = None,
) -> str:
    """Build a no-LLM HK scan report: matches + technicals + Tencent news."""
    matches = payload.get("matches") or []
    stats = payload.get("stats") or {}
    news_map = news_by_code or {}

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
        f"- 匹配条件: {', '.join(payload.get('conditions') or []) or '暂无'}",
        f"- 匹配数: {len(matches)}",
        f"- 无行情: {len(payload.get('no_price') or [])}",
        f"- 缓存命中: {stats.get('cache_hits', 0)}",
        f"- 批量下载: {stats.get('batch_downloaded', 0)}",
        (
            f"- 批量失败未回退: "
            f"{stats.get('unavailable_without_fallback', 0)}"
        ),
        "",
    ]

    if matches:
        lines.append(f"## 匹配结果（{len(matches)}）\n")
        lines.append("| 代号 | 名称 | 收盘 | S1 | S2 | 收盘≥S1 | 收盘≥S2 |")
        lines.append("|------|------|------|----|----|--------|--------|")
        for m in matches:
            lines.append(
                f"| [{m.get('code', '')}]({m.get('url', '')}) | {m.get('name', '')} "
                f"| {m.get('close', '暂无')} "
                f"| {'✅' if m.get('s1_breakout') else '❌'} "
                f"| {'✅' if m.get('s2_breakout') else '❌'} "
                f"| {'✅' if m.get('close_vs_entry') else '❌'} "
                f"| {'✅' if m.get('close_vs_s2_entry') else '❌'} |"
            )
        lines.append("")
        lines.append("### 技术指标与形态\n")
        for m in matches:
            lines.extend(_format_match_technical_block(m))
            lines.append("")
    else:
        lines.append("没有股票符合所选条件。\n")

    lines.append("## 腾讯新闻（仅匹配股）\n")
    if not matches:
        lines.append("无匹配股，未抓取新闻。\n")
    else:
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
) -> Dict[str, Any]:
    """Scan all listed HK stocks with Turtle signals + match-only Tencent news.

    Universe defaults to ``resources/universes/hk_all_stocks.json``.
    No LLM / AI analyzers are instantiated on this path.
    """
    env_cfg = get_scan_config_from_env()
    resolved_period = period or os.getenv("HK_SCAN_PERIOD") or env_cfg.get("period") or DEFAULT_PERIOD
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
    }
