# -*- coding: utf-8 -*-
"""HSI scan lite enrichment: top-N matches get quote + news + compact LLM dashboard."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from src.services.hsi_scanner import format_scan_report, get_scan_config_from_env, scan_hsi

logger = logging.getLogger(__name__)

DEFAULT_ENRICH_TOP_N = 5


def resolve_enrich_top_n(top_n: Optional[int] = None) -> int:
    """Resolve top-N from arg or HSI_ENRICH_TOP_N (default 5, minimum 1)."""
    if top_n is not None:
        try:
            return max(1, int(top_n))
        except (TypeError, ValueError):
            return DEFAULT_ENRICH_TOP_N
    raw = os.getenv("HSI_ENRICH_TOP_N", str(DEFAULT_ENRICH_TOP_N))
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        logger.warning("Invalid HSI_ENRICH_TOP_N=%r, fallback to %s", raw, DEFAULT_ENRICH_TOP_N)
        return DEFAULT_ENRICH_TOP_N


def select_top_matches(
    matches: Sequence[Dict[str, Any]],
    top_n: int = DEFAULT_ENRICH_TOP_N,
) -> List[Dict[str, Any]]:
    """Sort matches by potential_score descending and return the top N."""
    n = max(1, int(top_n))
    ranked = sorted(
        list(matches or []),
        key=lambda m: float(m.get("potential_score") or 0.0),
        reverse=True,
    )
    return ranked[:n]


def _quote_to_dict(quote: Any) -> Optional[Dict[str, Any]]:
    if quote is None:
        return None
    if hasattr(quote, "to_dict"):
        try:
            return quote.to_dict()
        except Exception:
            pass
    if isinstance(quote, dict):
        return quote
    return None


def _format_news_context(response: Any) -> str:
    if response is None:
        return ""
    to_context = getattr(response, "to_context", None)
    if callable(to_context):
        try:
            return (to_context(max_results=5) or "").strip()
        except TypeError:
            return (to_context() or "").strip()
    results = getattr(response, "results", None) or []
    lines = []
    for item in results[:5]:
        title = getattr(item, "title", "") or ""
        snippet = getattr(item, "snippet", "") or ""
        date = getattr(item, "published_date", None) or ""
        date_bit = f" [{date}]" if date else ""
        lines.append(f"- {title}{date_bit}")
        if snippet:
            lines.append(f"  {snippet[:200]}")
    return "\n".join(lines)


def build_lite_context(
    match: Dict[str, Any],
    quote: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build analyzer context without DB daily history."""
    code = str(match.get("code") or "")
    name = str(match.get("name") or code)
    quote = quote or {}

    price = quote.get("price")
    close = match.get("close")
    pct = quote.get("change_pct")

    today = {
        "close": close if close is not None else price,
        "open": quote.get("open_price"),
        "high": quote.get("high") if quote.get("high") is not None else match.get("high"),
        "low": quote.get("low") if quote.get("low") is not None else match.get("low"),
        "pct_chg": pct,
        "volume": quote.get("volume"),
        "amount": quote.get("amount"),
    }

    hsi_signals = {
        "entry20": match.get("entry20"),
        "entry55": match.get("entry55"),
        "s1_breakout": match.get("s1_breakout"),
        "s2_breakout": match.get("s2_breakout"),
        "close_vs_entry": match.get("close_vs_entry"),
        "close_vs_s2_entry": match.get("close_vs_s2_entry"),
        "potential_score": match.get("potential_score"),
        "potential_tier": match.get("potential_tier"),
        "s1_gap_pct": match.get("s1_gap_pct"),
        "s2_gap_pct": match.get("s2_gap_pct"),
        "kline_patterns": match.get("kline_patterns"),
    }

    return {
        "code": code,
        "stock_name": name,
        "date": match.get("date") or datetime.now().date().isoformat(),
        "data_missing": False,
        "today": today,
        "yesterday": {},
        "realtime": quote,
        "hsi_signals": hsi_signals,
        "analysis_notes": (
            "HSI lite enrichment context: S1/S2 scan signals + multi-source realtime quote. "
            f"Signals={hsi_signals}"
        ),
    }


def format_quote_section(quote: Optional[Dict[str, Any]], error: Optional[str] = None) -> str:
    lines = ["### 多数据源行情", ""]
    if error:
        lines.append(f"- 行情获取失败: {error}")
        lines.append("")
        return "\n".join(lines)
    if not quote:
        lines.append("- 无实时行情数据")
        lines.append("")
        return "\n".join(lines)

    source = quote.get("source", "unknown")
    lines.append(f"- 数据源: `{source}`")
    for label, key in (
        ("现价", "price"),
        ("涨跌幅%", "change_pct"),
        ("成交量", "volume"),
        ("成交额", "amount"),
        ("量比", "volume_ratio"),
        ("换手率%", "turnover_rate"),
        ("开盘", "open_price"),
        ("最高", "high"),
        ("最低", "low"),
        ("昨收", "pre_close"),
    ):
        val = quote.get(key)
        if val is not None:
            lines.append(f"- {label}: {val}")
    lines.append("")
    return "\n".join(lines)


def format_news_section(news_text: str, error: Optional[str] = None) -> str:
    lines = ["### 实时新闻", ""]
    if error:
        lines.append(f"- 新闻检索失败: {error}")
        lines.append("")
        return "\n".join(lines)
    text = (news_text or "").strip()
    if not text:
        lines.append("- 未检索到有效新闻")
        lines.append("")
        return "\n".join(lines)
    lines.append(text)
    lines.append("")
    return "\n".join(lines)


def format_dashboard_section(analysis: Any, error: Optional[str] = None) -> str:
    lines = ["### LLM决策仪表盘", ""]
    if error:
        lines.append(f"- LLM 分析失败: {error}")
        lines.append("")
        return "\n".join(lines)
    if analysis is None:
        lines.append("- 未生成决策仪表盘")
        lines.append("")
        return "\n".join(lines)

    success = getattr(analysis, "success", True)
    if success is False:
        err = getattr(analysis, "error_message", None) or "unknown"
        lines.append(f"- LLM 分析不可用: {err}")
        lines.append("")
        return "\n".join(lines)

    score = getattr(analysis, "sentiment_score", None)
    advice = getattr(analysis, "operation_advice", None)
    trend = getattr(analysis, "trend_prediction", None)
    confidence = getattr(analysis, "confidence_level", None)
    summary = getattr(analysis, "analysis_summary", None) or ""
    risk = getattr(analysis, "risk_warning", None) or ""
    news_summary = getattr(analysis, "news_summary", None) or ""

    lines.append(f"- 综合评分: {score}")
    lines.append(f"- 操作建议: {advice}")
    lines.append(f"- 趋势预测: {trend}")
    lines.append(f"- 置信度: {confidence}")
    if summary:
        lines.append(f"- 摘要: {summary}")
    if news_summary:
        lines.append(f"- 消息面: {news_summary}")
    if risk:
        lines.append(f"- 风险提示: {risk}")

    dashboard = getattr(analysis, "dashboard", None) or {}
    if isinstance(dashboard, dict) and dashboard:
        core = dashboard.get("core_conclusion") or {}
        if isinstance(core, dict):
            one = core.get("one_sentence")
            signal = core.get("signal_type")
            if one:
                lines.append(f"- 核心结论: {one}")
            if signal:
                lines.append(f"- 信号类型: {signal}")
        battle = dashboard.get("battle_plan") or {}
        if isinstance(battle, dict):
            sniper = battle.get("sniper_points") or {}
            if isinstance(sniper, dict):
                for key, label in (
                    ("entry", "建议买入区"),
                    ("add", "加仓区"),
                    ("stop_loss", "止损"),
                    ("take_profit", "止盈"),
                ):
                    val = sniper.get(key)
                    if val:
                        lines.append(f"- {label}: {val}")
        intelligence = dashboard.get("intelligence") or {}
        if isinstance(intelligence, dict):
            alerts = intelligence.get("risk_alerts")
            if alerts:
                lines.append(f"- 风险警报: {alerts}")

    lines.append("")
    return "\n".join(lines)


def _service_available(obj: Any, default: bool = False) -> bool:
    if obj is None:
        return False
    value = getattr(obj, "is_available", default)
    try:
        return bool(value() if callable(value) else value)
    except Exception:
        return False


def enrich_match(
    match: Dict[str, Any],
    *,
    fetcher: Any = None,
    search: Any = None,
    analyzer: Any = None,
) -> Dict[str, Any]:
    """Enrich one match with quote, news, and lite LLM dashboard (partial OK)."""
    code = str(match.get("code") or "")
    name = str(match.get("name") or code)
    result: Dict[str, Any] = {
        "code": code,
        "name": name,
        "match": match,
        "quote": None,
        "quote_error": None,
        "news_text": "",
        "news_error": None,
        "analysis": None,
        "analysis_error": None,
    }

    quote_dict: Optional[Dict[str, Any]] = None
    if fetcher is not None:
        try:
            quote = fetcher.get_realtime_quote(code)
            quote_dict = _quote_to_dict(quote)
            result["quote"] = quote_dict
            if not quote_dict:
                result["quote_error"] = "empty quote"
        except Exception as exc:
            result["quote_error"] = str(exc)
            logger.warning("HSI enrich quote failed for %s: %s", code, exc)
    else:
        result["quote_error"] = "fetcher unavailable"

    news_text = ""
    if search is not None and _service_available(search):
        try:
            response = search.search_stock_news(code, name, max_results=5)
            if getattr(response, "success", False):
                news_text = _format_news_context(response)
                result["news_text"] = news_text
            else:
                result["news_error"] = getattr(response, "error_message", None) or "search failed"
        except Exception as exc:
            result["news_error"] = str(exc)
            logger.warning("HSI enrich news failed for %s: %s", code, exc)
    elif search is None:
        result["news_error"] = "search service unavailable"
    else:
        result["news_error"] = "no search providers configured"

    if analyzer is not None and _service_available(analyzer, default=True):
        try:
            context = build_lite_context(match, quote_dict)
            analysis = analyzer.analyze(context, news_context=news_text or None)
            result["analysis"] = analysis
            if analysis is not None and getattr(analysis, "success", True) is False:
                result["analysis_error"] = getattr(analysis, "error_message", None) or "analyze failed"
        except Exception as exc:
            result["analysis_error"] = str(exc)
            logger.warning("HSI enrich LLM failed for %s: %s", code, exc)
    elif analyzer is None:
        result["analysis_error"] = "analyzer unavailable"
    else:
        result["analysis_error"] = "LLM not configured"

    return result


def build_enriched_report(
    scan_payload: Dict[str, Any],
    enrichments: Sequence[Dict[str, Any]],
    top_n: int = DEFAULT_ENRICH_TOP_N,
) -> str:
    """Combine full match table with top-N enrichment sections."""
    parts: List[str] = [format_scan_report(scan_payload).rstrip(), ""]
    parts.append(f"## Top {top_n} 增强分析（按 potential_score）")
    parts.append("")

    if not enrichments:
        parts.append("无增强分析结果。")
        parts.append("")
        return "\n".join(parts)

    for idx, item in enumerate(enrichments, 1):
        code = item.get("code")
        name = item.get("name")
        match = item.get("match") or {}
        score = match.get("potential_score")
        tier = match.get("potential_tier")
        parts.append(f"## {idx}. {name} ({code})")
        parts.append("")
        parts.append(f"- potential_score: {score} | tier: {tier}")
        parts.append("")
        parts.append(format_quote_section(item.get("quote"), item.get("quote_error")))
        parts.append(format_news_section(item.get("news_text") or "", item.get("news_error")))
        parts.append(format_dashboard_section(item.get("analysis"), item.get("analysis_error")))

    return "\n".join(parts).rstrip() + "\n"


def save_enriched_report(report_text: str, reports_dir: Optional[Path] = None) -> Path:
    """Write report to reports/hsi_enriched_YYYYMMDD_HHMMSS.md."""
    root = reports_dir or Path("reports")
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = root / f"hsi_enriched_{stamp}.md"
    path.write_text(report_text, encoding="utf-8")
    return path


def _default_fetcher():
    """Prefer Yahoo Finance for HSI enrichment quotes (avoid AkShare HK disconnects)."""
    from data_provider.yfinance_fetcher import YfinanceFetcher

    return YfinanceFetcher()


def _default_search():
    try:
        from src.search_service import get_search_service

        return get_search_service()
    except Exception as exc:
        logger.warning("SearchService init failed: %s", exc)
        return None


def _default_analyzer():
    try:
        from src.analyzer import GeminiAnalyzer

        return GeminiAnalyzer()
    except Exception as exc:
        logger.warning("GeminiAnalyzer init failed: %s", exc)
        return None


def run_hsi_scan_enriched(
    *,
    period: Optional[str] = None,
    conditions: Optional[str] = None,
    max_workers: Optional[int] = None,
    check_trading_day: bool = True,
    use_multi_source: bool = False,
    top_n: Optional[int] = None,
    fetcher: Any = None,
    search: Any = None,
    analyzer: Any = None,
    reports_dir: Optional[Path] = None,
    save_report: bool = True,
) -> Dict[str, Any]:
    """Scan HSI, enrich top-N matches, optionally save combined markdown report."""
    env_cfg = get_scan_config_from_env()
    resolved_top_n = resolve_enrich_top_n(top_n)

    payload = scan_hsi(
        period=period or env_cfg["period"],
        conditions=conditions or env_cfg["conditions"],
        max_workers=max_workers or env_cfg["max_workers"],
        check_trading_day=check_trading_day,
        use_multi_source=use_multi_source,
    )

    if payload.get("skipped"):
        report_text = format_scan_report(payload)
        report_path = None
        if save_report:
            report_path = str(save_enriched_report(report_text, reports_dir=reports_dir))
        return {
            "payload": payload,
            "enrichments": [],
            "top_n": resolved_top_n,
            "report_text": report_text,
            "report_path": report_path,
        }

    top_matches = select_top_matches(payload.get("matches") or [], top_n=resolved_top_n)

    active_fetcher = fetcher if fetcher is not None else _default_fetcher()
    active_search = search if search is not None else _default_search()
    active_analyzer = analyzer if analyzer is not None else _default_analyzer()

    enrichments: List[Dict[str, Any]] = []
    for match in top_matches:
        enrichments.append(
            enrich_match(
                match,
                fetcher=active_fetcher,
                search=active_search,
                analyzer=active_analyzer,
            )
        )

    report_text = build_enriched_report(payload, enrichments, top_n=resolved_top_n)
    report_path = None
    if save_report:
        report_path = str(save_enriched_report(report_text, reports_dir=reports_dir))
        logger.info("HSI enriched report saved: %s", report_path)

    return {
        "payload": payload,
        "enrichments": enrichments,
        "top_n": resolved_top_n,
        "report_text": report_text,
        "report_path": report_path,
    }
