# -*- coding: utf-8 -*-
"""HSI scan lite enrichment: matches get quote + news + compact LLM dashboard."""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from src.services.hsi_scanner import (
    format_pattern_names,
    format_scan_report,
    get_scan_config_from_env,
    scan_hsi,
)

logger = logging.getLogger(__name__)

# Default enrich caps. Match: None/0/all = unlimited. ET Net: 0 = none.
DEFAULT_ENRICH_TOP_N: Optional[int] = None  # all matches
DEFAULT_ENRICH_ETNET_TOP_N: int = 10


def _resolve_enrich_cap(
    value: Optional[int],
    *,
    env_key: str,
    default: Optional[int],
) -> Optional[int]:
    """Resolve a match-style enrich cap from arg or env.

    Returns ``None`` for unlimited (``0`` / ``all`` / unset when default is None).
    """
    if value is not None:
        try:
            n = int(value)
        except (TypeError, ValueError):
            return default
        return None if n <= 0 else n

    raw = (os.getenv(env_key) or "").strip()
    if not raw:
        return default
    if raw.lower() == "all":
        return None
    try:
        n = int(raw)
    except (TypeError, ValueError):
        logger.warning("Invalid %s=%r, fallback to %s", env_key, raw, default)
        return default
    return None if n <= 0 else n


def resolve_enrich_top_n(top_n: Optional[int] = None) -> Optional[int]:
    """Resolve match enrich cap from arg or ``HSI_ENRICH_TOP_N`` (default: all)."""
    return _resolve_enrich_cap(
        top_n,
        env_key="HSI_ENRICH_TOP_N",
        default=DEFAULT_ENRICH_TOP_N,
    )


def resolve_enrich_etnet_top_n(etnet_top_n: Optional[int] = None) -> Optional[int]:
    """Resolve ET Net enrich extras cap from arg or ``HSI_ENRICH_ETNET_TOP_N``.

    Unlike match ``top_n``, ``0`` means **no** ET Net extras (not unlimited).
    Use ``all`` / ``None`` for unlimited ET Net uniques.
    """
    if etnet_top_n is not None:
        try:
            n = int(etnet_top_n)
        except (TypeError, ValueError):
            return DEFAULT_ENRICH_ETNET_TOP_N
        if n < 0:
            return DEFAULT_ENRICH_ETNET_TOP_N
        return n  # 0 = none; positive = cap

    raw = (os.getenv("HSI_ENRICH_ETNET_TOP_N") or "").strip()
    if not raw:
        return DEFAULT_ENRICH_ETNET_TOP_N
    if raw.lower() == "all":
        return None
    try:
        n = int(raw)
    except (TypeError, ValueError):
        logger.warning(
            "Invalid HSI_ENRICH_ETNET_TOP_N=%r, fallback to %s",
            raw,
            DEFAULT_ENRICH_ETNET_TOP_N,
        )
        return DEFAULT_ENRICH_ETNET_TOP_N
    if n < 0:
        return DEFAULT_ENRICH_ETNET_TOP_N
    return n  # 0 = none; positive = cap


def select_top_matches(
    matches: Sequence[Dict[str, Any]],
    top_n: Optional[int] = DEFAULT_ENRICH_TOP_N,
) -> List[Dict[str, Any]]:
    """Sort matches by potential_score descending; optionally keep only top N."""
    ranked = sorted(
        list(matches or []),
        key=lambda m: float(m.get("potential_score") or 0.0),
        reverse=True,
    )
    if top_n is None:
        return ranked
    n = int(top_n)
    if n <= 0:
        return ranked
    return ranked[:n]


def _apply_enrich_cap(
    rows: Sequence[Dict[str, Any]],
    top_n: Optional[int],
) -> List[Dict[str, Any]]:
    """Apply enrich-style cap (None = all; 0 = none; positive = top-N)."""
    items = list(rows or [])
    if top_n is None:
        return items
    n = int(top_n)
    if n <= 0:
        return []
    return items[:n]


def etnet_boards_to_enrich_stubs(
    etnet_top: Optional[Dict[str, Any]],
    *,
    top_n: Optional[int] = DEFAULT_ENRICH_ETNET_TOP_N,
    match_by_code: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Build enrich targets from ET Net boards, capped by ``HSI_ENRICH_ETNET_TOP_N``.

    Prefer full scan match rows when available; otherwise use code/name stubs.
    """
    if not etnet_top or not etnet_top.get("enabled"):
        return []
    try:
        from src.services.etnet_top_movers import unique_codes_from_boards
    except Exception as exc:
        logger.warning("ET Net enrich stubs unavailable: %s", exc)
        return []

    boards = etnet_top.get("boards") or {}
    rows = unique_codes_from_boards(boards)
    rows = _apply_enrich_cap(rows, top_n)
    lookup = {str(k).upper(): v for k, v in (match_by_code or {}).items()}
    stubs: List[Dict[str, Any]] = []
    for row in rows:
        code = str(row.get("code") or "").strip().upper()
        if not code:
            continue
        existing = lookup.get(code)
        if existing:
            item = dict(existing)
            item["enrich_source"] = "etnet+match"
            stubs.append(item)
            continue
        stubs.append(
            {
                "code": code,
                "name": str(row.get("name") or code).strip(),
                "potential_score": 0.0,
                "potential_tier": None,
                "enrich_source": "etnet",
                "url": f"https://finance.yahoo.com/quote/{code}",
            }
        )
    return stubs


def select_enrich_targets(
    matches: Sequence[Dict[str, Any]],
    etnet_top: Optional[Dict[str, Any]] = None,
    top_n: Optional[int] = DEFAULT_ENRICH_TOP_N,
    etnet_top_n: Optional[int] = DEFAULT_ENRICH_ETNET_TOP_N,
) -> List[Dict[str, Any]]:
    """Combine score-ranked matches with ET Net movers under separate caps.

    - Matches: capped by ``top_n`` (``HSI_ENRICH_TOP_N``)
    - ET Net extras: unique codes not already selected, capped by ``etnet_top_n``
      (``HSI_ENRICH_ETNET_TOP_N``)
    """
    selected = select_top_matches(matches, top_n=top_n)
    for item in selected:
        item.setdefault("enrich_source", "match")
    seen = {str(m.get("code") or "").strip().upper() for m in selected if m.get("code")}

    match_by_code = {
        str(m.get("code") or "").strip().upper(): m
        for m in (matches or [])
        if m.get("code")
    }
    # Full ET Net list first, drop already-selected, then apply etnet_top_n.
    etnet_stubs = etnet_boards_to_enrich_stubs(
        etnet_top,
        top_n=None,
        match_by_code=match_by_code,
    )
    extras = [
        stub
        for stub in etnet_stubs
        if str(stub.get("code") or "").strip().upper() not in seen
    ]
    for stub in _apply_enrich_cap(extras, etnet_top_n):
        code = str(stub.get("code") or "").strip().upper()
        if not code or code in seen:
            continue
        selected.append(stub)
        seen.add(code)
    return selected


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


def _filter_search_news_text(text: str, *, max_age_days: int) -> str:
    """Drop dated search bullets older than the HSI live window; keep undated."""
    from src.services.tencent_stock_news import parse_news_publish_date

    text = (text or "").strip()
    if not text:
        return ""
    cutoff = date.today() - timedelta(days=max(1, int(max_age_days)) - 1)
    kept: List[str] = []
    current_block: List[str] = []

    def _flush() -> None:
        nonlocal current_block
        if not current_block:
            return
        head = current_block[0]
        published = None
        if "[" in head and "]" in head:
            meta = head[head.rfind("[") + 1 : head.rfind("]")]
            published = parse_news_publish_date(meta.split(",", 1)[0].strip())
        if published is None or published >= cutoff:
            kept.extend(current_block)
        current_block = []

    for line in text.splitlines():
        if line.strip().startswith("-"):
            _flush()
            current_block = [line]
        elif current_block:
            current_block.append(line)
    _flush()
    return "\n".join(kept)


def _build_live_news_for_deepseek(news_text: str, *, max_age_days: int) -> str:
    """Wrap live-fetched news so DeepSeek cannot fall back to training history."""
    body = (news_text or "").strip()
    if not body:
        return (
            "【消息面·本次实时抓取】未检索到近"
            f"{max_age_days}日内可用新闻。"
            "请将 news_summary 设为「近期无可用新闻」，intelligence 列表可为空。"
            "禁止用训练记忆或历史知识编造旧闻。"
        )
    return (
        f"【消息面·本次实时抓取｜仅允许使用下列近{max_age_days}日新闻】\n"
        "规则（强制）：\n"
        "1. 只允许引用下方实时抓取条目；禁止使用模型训练记忆、往期研报/财报记忆或历史知识补新闻。\n"
        "2. 不得编造未出现在下列列表中的标题、日期、业绩或事件。\n"
        "3. 必须输出 news_summary（2～4 句中文点评），并填写 "
        "dashboard.intelligence.latest_news / positive_catalysts / risk_alerts。\n"
        "4. 每条 intelligence 输出必须带列表中的日期；列表外日期一律禁止。\n\n"
        f"{body}"
    )


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
        "exit10": match.get("exit10"),
        "exit20": match.get("exit20"),
        "s1_breakout": match.get("s1_breakout"),
        "s2_breakout": match.get("s2_breakout"),
        "s1_exit": match.get("s1_exit"),
        "s2_exit": match.get("s2_exit"),
        "close_vs_entry": match.get("close_vs_entry"),
        "close_vs_s2_entry": match.get("close_vs_s2_entry"),
        "potential_score": match.get("potential_score"),
        "potential_tier": match.get("potential_tier"),
        "s1_gap_pct": match.get("s1_gap_pct"),
        "s2_gap_pct": match.get("s2_gap_pct"),
        "kline_patterns": match.get("kline_patterns"),
        "n": match.get("n"),
        "stop_long_2n": match.get("stop_long_2n"),
        "breakout_extension_n": match.get("breakout_extension_n"),
        "turtle_trend_ok": match.get("turtle_trend_ok"),
        "turtle_trend_rule": match.get("turtle_trend_rule"),
        "s1_last_was_winner": match.get("s1_last_was_winner"),
        "s1_entry_allowed": match.get("s1_entry_allowed"),
        "turtle_score": match.get("turtle_score"),
    }

    technicals = {
        "ma5": match.get("ma5"),
        "ma10": match.get("ma10"),
        "ma20": match.get("ma20"),
        "ma60": match.get("ma60"),
        "ma_alignment": match.get("ma_alignment"),
        "trend_status": match.get("trend_status"),
        "trend_strength": match.get("trend_strength"),
        "bias_ma5": match.get("bias_ma5"),
        "macd_dif": match.get("macd_dif"),
        "macd_dea": match.get("macd_dea"),
        "macd_bar": match.get("macd_bar"),
        "macd_status": match.get("macd_status"),
        "macd_signal": match.get("macd_signal"),
        "rsi_6": match.get("rsi_6"),
        "rsi_12": match.get("rsi_12"),
        "rsi_24": match.get("rsi_24"),
        "rsi_status": match.get("rsi_status"),
        "rsi_signal": match.get("rsi_signal"),
    }

    patterns = {
        "kline_patterns": match.get("kline_patterns") or [],
        "kline_bullish_patterns": match.get("kline_bullish_patterns") or [],
        "kline_bearish_patterns": match.get("kline_bearish_patterns") or [],
        "double_top": match.get("double_top"),
        "double_bottom": match.get("double_bottom"),
        "head_shoulders": match.get("head_shoulders"),
        "inverse_head_shoulders": match.get("inverse_head_shoulders"),
        "triangle_breakout": match.get("triangle_breakout"),
        "bull_flag": match.get("bull_flag"),
        "bear_flag": match.get("bear_flag"),
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
        "technicals": technicals,
        "patterns": patterns,
        "analysis_notes": (
            "HSI lite enrichment: S1/S2 signals + RSI/MACD/MAs + chart patterns + realtime quote. "
            "You MUST also comment on news/message flow: fill news_summary (2-4 Chinese sentences) "
            "and dashboard.intelligence.latest_news / positive_catalysts / risk_alerts from the injected news. "
            "If no news is provided, set news_summary to「近期无可用新闻」and keep intelligence lists empty. "
            f"Signals={hsi_signals}; Technicals={technicals}; Patterns={patterns}"
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


def format_technical_section(match: Optional[Dict[str, Any]] = None) -> str:
    """Format MA / RSI / MACD / chart-pattern block for enriched reports."""
    lines = ["### 技术指标与形态", ""]
    match = match or {}
    has_tech = any(match.get(k) is not None for k in ("ma20", "rsi_12", "macd_dif", "ma_alignment"))
    patterns = match.get("kline_patterns") or []
    if not has_tech and not patterns:
        lines.append("- 无技术指标/形态数据")
        lines.append("")
        return "\n".join(lines)

    if match.get("ma_alignment") or match.get("trend_status"):
        lines.append(
            f"- 趋势: {match.get('ma_alignment') or match.get('trend_status')}"
            + (f" (strength={match.get('trend_strength')})" if match.get("trend_strength") is not None else "")
        )
    ma_bits = []
    for key in ("ma5", "ma10", "ma20", "ma60"):
        if match.get(key) is not None:
            ma_bits.append(f"{key.upper()}={match.get(key)}")
    if ma_bits:
        lines.append(f"- 均线: {', '.join(ma_bits)}")
    if match.get("bias_ma5") is not None:
        lines.append(f"- 乖离率 MA5: {match.get('bias_ma5')}%")
    if any(match.get(k) is not None for k in ("rsi_6", "rsi_12", "rsi_24")):
        lines.append(
            f"- RSI: 6={match.get('rsi_6', 'n/a')}, 12={match.get('rsi_12', 'n/a')}, "
            f"24={match.get('rsi_24', 'n/a')} ({match.get('rsi_status') or 'n/a'})"
        )
        if match.get("rsi_signal"):
            lines.append(f"  - {match.get('rsi_signal')}")
    if any(match.get(k) is not None for k in ("macd_dif", "macd_dea", "macd_bar")):
        lines.append(
            f"- MACD: status={match.get('macd_status') or 'n/a'}, "
            f"DIF={match.get('macd_dif', 'n/a')}, DEA={match.get('macd_dea', 'n/a')}, "
            f"BAR={match.get('macd_bar', 'n/a')}"
        )
        if match.get("macd_signal"):
            lines.append(f"  - {match.get('macd_signal')}")
    lines.append(f"- 形态: {format_pattern_names(patterns)}")
    if any(
        match.get(k) is not None
        for k in ("n", "stop_long_2n", "turtle_trend_ok", "s1_entry_allowed")
    ):
        lines.append(
            f"- 海龟: N={match.get('n', '暂无')}, "
            f"2N止损参考={match.get('stop_long_2n', '暂无')}, "
            f"突破延伸N={match.get('breakout_extension_n', '暂无')}, "
            f"turtle分={match.get('turtle_score', '暂无')}"
        )
        lines.append(
            f"- 趋势过滤: {'通过' if match.get('turtle_trend_ok') else '未通过'}"
            f"（{match.get('turtle_trend_rule') or '暂无'}）"
            f" | S1上次盈利跳过: {'是' if match.get('s1_last_was_winner') else '否'}"
            f" | S1允许开仓: {'是' if match.get('s1_entry_allowed') else '否'}"
        )
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


def _format_intel_items(value: Any) -> str:
    """Normalize intelligence list/str fields for report display."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)):
        parts = [str(item).strip() for item in value if str(item).strip()]
        return "；".join(parts)
    return str(value).strip()


def format_dashboard_section(analysis: Any, error: Optional[str] = None) -> str:
    lines = [
        "### DeepSeek 决策仪表盘",
        "",
        "> 来源: **DeepSeek**（主分析 LLM / 结构化决策仪表盘）",
        "",
    ]
    if error:
        lines.append(f"- [DeepSeek] 分析失败: {error}")
        lines.append("")
        return "\n".join(lines)
    if analysis is None:
        lines.append("- [DeepSeek] 未生成决策仪表盘")
        lines.append("")
        return "\n".join(lines)

    success = getattr(analysis, "success", True)
    if success is False:
        err = getattr(analysis, "error_message", None) or "unknown"
        lines.append(f"- [DeepSeek] 分析不可用: {err}")
        lines.append("")
        return "\n".join(lines)

    score = getattr(analysis, "sentiment_score", None)
    advice = getattr(analysis, "operation_advice", None)
    trend = getattr(analysis, "trend_prediction", None)
    confidence = getattr(analysis, "confidence_level", None)
    summary = getattr(analysis, "analysis_summary", None) or ""
    risk = getattr(analysis, "risk_warning", None) or ""
    news_summary = getattr(analysis, "news_summary", None) or ""

    lines.append(f"- [DeepSeek] 综合评分: {score}")
    lines.append(f"- [DeepSeek] 操作建议: {advice}")
    lines.append(f"- [DeepSeek] 趋势预测: {trend}")
    lines.append(f"- [DeepSeek] 置信度: {confidence}")
    if summary:
        lines.append(f"- [DeepSeek] 摘要: {summary}")
    if news_summary:
        lines.append(f"- [DeepSeek] 消息面点评: {news_summary}")
    else:
        lines.append("- [DeepSeek] 消息面点评: （未输出）")
    if risk:
        lines.append(f"- [DeepSeek] 风险提示: {risk}")

    dashboard = getattr(analysis, "dashboard", None) or {}
    if isinstance(dashboard, dict) and dashboard:
        core = dashboard.get("core_conclusion") or {}
        if isinstance(core, dict):
            one = core.get("one_sentence")
            signal = core.get("signal_type")
            if one:
                lines.append(f"- [DeepSeek] 核心结论: {one}")
            if signal:
                lines.append(f"- [DeepSeek] 信号类型: {signal}")
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
                        lines.append(f"- [DeepSeek] {label}: {val}")
        intelligence = dashboard.get("intelligence") or {}
        if isinstance(intelligence, dict):
            latest = _format_intel_items(intelligence.get("latest_news"))
            catalysts = _format_intel_items(intelligence.get("positive_catalysts"))
            alerts = _format_intel_items(intelligence.get("risk_alerts"))
            if latest:
                lines.append(f"- [DeepSeek] 最新消息: {latest}")
            if catalysts:
                lines.append(f"- [DeepSeek] 利好催化: {catalysts}")
            if alerts:
                lines.append(f"- [DeepSeek] 风险警报: {alerts}")

    lines.append("")
    return "\n".join(lines)


def format_kimi_comment_section(comment: str = "", error: Optional[str] = None) -> str:
    """Format separate Kimi commentary block (after DeepSeek dashboard)."""
    lines = [
        "### Kimi 独立点评",
        "",
        "> 来源: **Kimi / Moonshot**（独立点评 LLM，与 DeepSeek 仪表盘分开，互不替代）",
        "",
    ]
    text = (comment or "").strip()
    if text:
        # Ensure body lines are visibly attributed even if model omits a label.
        body_lines = text.splitlines()
        if not any(line.strip().startswith("[Kimi]") for line in body_lines[:3]):
            lines.append("[Kimi]")
        lines.extend(body_lines)
        lines.append("")
        return "\n".join(lines)
    if error:
        lines.append(f"- [Kimi] 点评不可用: {error}")
    else:
        lines.append("- [Kimi] 未生成点评")
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
        "news_provider": None,
        "analysis": None,
        "analysis_error": None,
        "kimi_comment": "",
        "kimi_comment_error": None,
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
    news_provider: Optional[str] = None
    search_text = ""
    search_error: Optional[str] = None
    max_age_days = 2
    try:
        from src.services.tencent_stock_news import resolve_hsi_news_max_age_days

        max_age_days = resolve_hsi_news_max_age_days()
    except Exception:
        max_age_days = 2

    # Prefer Tencent ifzq live symbol news (no API key); soft-fail if empty/disabled.
    try:
        from src.services.tencent_stock_news import (
            fetch_tencent_stock_news,
            filter_fresh_news_items,
            format_tencent_news_context,
            is_tencent_stock_news_enabled,
            merge_news_contexts,
        )

        if is_tencent_stock_news_enabled():
            ifzq_items = filter_fresh_news_items(
                fetch_tencent_stock_news(code, n=10),
                max_age_days=max_age_days,
                keep_undated=True,
            )
            if ifzq_items:
                news_text = format_tencent_news_context(ifzq_items, max_items=10)
                news_provider = "tencent_ifzq"
                result["news_text"] = news_text
                result["news_provider"] = news_provider
    except Exception as exc:
        logger.warning("HSI enrich tencent ifzq news failed for %s: %s", code, exc)

    if search is not None and _service_available(search):
        try:
            response = search.search_stock_news(code, name, max_results=5)
            if getattr(response, "success", False):
                search_text = _filter_search_news_text(
                    _format_news_context(response),
                    max_age_days=max_age_days,
                )
            else:
                search_error = getattr(response, "error_message", None) or "search failed"
        except Exception as exc:
            search_error = str(exc)
            logger.warning("HSI enrich news failed for %s: %s", code, exc)
    elif search is None:
        search_error = "search service unavailable"
    else:
        search_error = "no search providers configured"

    # Keep live ifzq body separate so DeepSeek does not ingest merged search history.
    ifzq_news = news_text
    if news_text and search_text:
        result["news_text"] = merge_news_contexts(news_text, search_text, max_secondary_lines=2)
        result["news_provider"] = f"{news_provider}+search" if news_provider else "search"
        result["news_error"] = None
    elif news_text:
        result["news_error"] = None
    elif search_text:
        result["news_text"] = search_text
        result["news_provider"] = "search"
        result["news_error"] = None
    else:
        result["news_text"] = ""
        result["news_error"] = search_error or "no news results"

    # DeepSeek: prefer live ifzq only; fall back to age-filtered search.
    deepseek_news = ifzq_news or search_text or ""

    context: Optional[Dict[str, Any]] = None
    if analyzer is not None and _service_available(analyzer, default=True):
        try:
            context = build_lite_context(match, quote_dict)
            context["news_window_days"] = max_age_days
            news_for_llm = _build_live_news_for_deepseek(
                deepseek_news,
                max_age_days=max_age_days,
            )
            analysis = analyzer.analyze(context, news_context=news_for_llm)
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

    # Separate Kimi commentary (does not replace DeepSeek dashboard).
    try:
        from src.services.kimi_comment import generate_kimi_comment, is_kimi_comment_enabled

        if is_kimi_comment_enabled():
            if context is None:
                context = build_lite_context(match, quote_dict)
            comment = generate_kimi_comment(context, deepseek_news or result.get("news_text") or "")
            if comment:
                result["kimi_comment"] = comment
                result["kimi_comment_error"] = None
            else:
                result["kimi_comment_error"] = "empty or failed Kimi comment"
        else:
            result["kimi_comment_error"] = "kimi comment disabled or no API key"
    except Exception as exc:
        result["kimi_comment_error"] = str(exc)
        logger.warning("HSI enrich Kimi comment failed for %s: %s", code, exc)

    return result


def build_enriched_report(
    scan_payload: Dict[str, Any],
    enrichments: Sequence[Dict[str, Any]],
    top_n: Optional[int] = DEFAULT_ENRICH_TOP_N,
    etnet_top_n: Optional[int] = DEFAULT_ENRICH_ETNET_TOP_N,
) -> str:
    """Combine full match table with enrichment sections (matches + ET Net movers)."""
    parts: List[str] = [format_scan_report(scan_payload).rstrip(), ""]
    match_label = (
        "全部匹配股"
        if top_n is None or int(top_n) <= 0
        else f"匹配股 Top {top_n}"
    )
    etnet_label = (
        "全部经济通"
        if etnet_top_n is None
        else (
            "经济通额外 0"
            if int(etnet_top_n) <= 0
            else f"经济通额外 Top {etnet_top_n}"
        )
    )
    parts.append(f"## 增强分析（{match_label} + {etnet_label}，按潜力分）")
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
        source = match.get("enrich_source") or "match"
        source_label = {
            "etnet": "经济通",
            "etnet+match": "经济通 + 匹配",
            "match": "匹配",
        }.get(str(source), str(source))
        parts.append(f"## {idx}. {name} ({code})")
        parts.append("")
        parts.append(
            f"- 来源: {source_label} | 潜力分: {score} | 档位: {tier} "
            f"| RSI/MACD分: {match.get('rsi_macd_score')}"
        )
        parts.append("")
        parts.append(format_quote_section(item.get("quote"), item.get("quote_error")))
        parts.append(format_technical_section(match))
        parts.append(format_news_section(item.get("news_text") or "", item.get("news_error")))
        parts.append(format_dashboard_section(item.get("analysis"), item.get("analysis_error")))
        parts.append(
            format_kimi_comment_section(
                item.get("kimi_comment") or "",
                item.get("kimi_comment_error"),
            )
        )

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
    etnet_top_n: Optional[int] = None,
    fetcher: Any = None,
    search: Any = None,
    analyzer: Any = None,
    reports_dir: Optional[Path] = None,
    save_report: bool = True,
) -> Dict[str, Any]:
    """Scan HSI, enrich matches + ET Net extras under separate caps, save report."""
    env_cfg = get_scan_config_from_env()
    resolved_top_n = resolve_enrich_top_n(top_n)
    resolved_etnet_top_n = resolve_enrich_etnet_top_n(etnet_top_n)

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
            "etnet_top_n": resolved_etnet_top_n,
            "report_text": report_text,
            "report_path": report_path,
        }

    top_matches = select_enrich_targets(
        payload.get("matches") or [],
        etnet_top=payload.get("etnet_top"),
        top_n=resolved_top_n,
        etnet_top_n=resolved_etnet_top_n,
    )

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

    report_text = build_enriched_report(
        payload,
        enrichments,
        top_n=resolved_top_n,
        etnet_top_n=resolved_etnet_top_n,
    )
    report_path = None
    if save_report:
        report_path = str(save_enriched_report(report_text, reports_dir=reports_dir))
        logger.info("HSI enriched report saved: %s", report_path)

    return {
        "payload": payload,
        "enrichments": enrichments,
        "top_n": resolved_top_n,
        "etnet_top_n": resolved_etnet_top_n,
        "report_text": report_text,
        "report_path": report_path,
    }
