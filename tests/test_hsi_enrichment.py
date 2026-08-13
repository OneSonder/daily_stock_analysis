# -*- coding: utf-8 -*-
"""Tests for HSI lite enrichment helpers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from src.services.hsi_enrichment import (
    _MarketAwareQuoteFetcher,
    _default_analyzer,
    build_enriched_report,
    build_lite_context,
    enrich_match,
    format_dashboard_section,
    format_gemini_comment_section,
    format_kimi_comment_section,
    format_news_section,
    format_quote_section,
    format_technical_section,
    resolve_enrich_etnet_top_n,
    resolve_enrich_top_n,
    run_hsi_scan_enriched,
    select_enrich_targets,
    select_top_matches,
)


def test_market_aware_quote_fetcher_routes_a_share_to_tencent():
    yahoo = MagicMock()
    tencent = MagicMock()
    tencent_quote = SimpleNamespace(price=1501.0, source="tencent")
    tencent.get_realtime_quote.return_value = tencent_quote
    fetcher = _MarketAwareQuoteFetcher(yahoo, tencent)

    assert fetcher.get_realtime_quote("600519.SH") is tencent_quote
    tencent.get_realtime_quote.assert_called_once_with("600519.SH", source="tencent")
    yahoo.get_realtime_quote.assert_not_called()


def test_market_aware_quote_fetcher_uses_yahoo_for_hk_and_a_share_fallback():
    yahoo = MagicMock()
    tencent = MagicMock()
    yahoo.get_realtime_quote.side_effect = ["hk quote", "a quote"]
    tencent.get_realtime_quote.return_value = None
    fetcher = _MarketAwareQuoteFetcher(yahoo, tencent)

    assert fetcher.get_realtime_quote("0700.HK") == "hk quote"
    assert fetcher.get_realtime_quote("000001.SZ") == "a quote"
    tencent.get_realtime_quote.assert_called_once_with("000001.SZ", source="tencent")
    assert yahoo.get_realtime_quote.call_args_list == [
        call("0700.HK"),
        call("000001.SZ"),
    ]


def test_select_top_matches_orders_by_potential_score():
    matches = [
        {"code": "A", "potential_score": 40},
        {"code": "B", "potential_score": 90},
        {"code": "C", "potential_score": 70},
        {"code": "D"},
    ]
    top = select_top_matches(matches, top_n=2)
    assert [m["code"] for m in top] == ["B", "C"]
    all_ranked = select_top_matches(matches, top_n=None)
    assert [m["code"] for m in all_ranked] == ["B", "C", "A", "D"]
    assert [m["code"] for m in select_top_matches(matches, top_n=0)] == []


def test_select_enrich_targets_includes_etnet_capped_by_top_n():
    matches = [
        {"code": "0700.HK", "name": "腾讯", "potential_score": 90},
        {"code": "9988.HK", "name": "阿里", "potential_score": 50},
    ]
    etnet_top = {
        "enabled": True,
        "boards": {
            "turnover": [
                {"code": "0700.HK", "name": "TENCENT"},
                {"code": "2513.HK", "name": "Z.AI"},
                {"code": "3033.HK", "name": "CSOP"},
            ],
            "volume": [{"code": "1810.HK", "name": "XIAOMI"}],
            "up": [],
        },
    }
    # top_n=1 + etnet_top_n=1 → 1 match (0700) + 1 etnet unique (0700 skipped) → 2513
    selected = select_enrich_targets(
        matches, etnet_top=etnet_top, top_n=1, etnet_top_n=1
    )
    assert [m["code"] for m in selected] == ["0700.HK", "2513.HK"]
    assert selected[0]["enrich_source"] == "match"
    assert selected[1]["enrich_source"] == "etnet"

    # Separate caps: 1 match + 2 etnet extras
    split = select_enrich_targets(
        matches, etnet_top=etnet_top, top_n=1, etnet_top_n=2
    )
    assert [m["code"] for m in split] == ["0700.HK", "2513.HK", "3033.HK"]

    # etnet_top_n=0 → no ET Net extras
    matches_only = select_enrich_targets(
        matches, etnet_top=etnet_top, top_n=1, etnet_top_n=0
    )
    assert [m["code"] for m in matches_only] == ["0700.HK"]

    # all → both matches + remaining etnet uniques
    all_sel = select_enrich_targets(
        matches, etnet_top=etnet_top, top_n=None, etnet_top_n=None
    )
    codes = [m["code"] for m in all_sel]
    assert codes[:2] == ["0700.HK", "9988.HK"]
    assert "2513.HK" in codes
    assert "3033.HK" in codes
    assert "1810.HK" in codes


def test_select_enrich_targets_skips_etnet_when_disabled():
    matches = [{"code": "0700.HK", "potential_score": 80}]
    selected = select_enrich_targets(
        matches,
        etnet_top={"enabled": False, "boards": {"turnover": [{"code": "2513.HK", "name": "Z"}]}},
        top_n=None,
        etnet_top_n=None,
    )
    assert [m["code"] for m in selected] == ["0700.HK"]


def test_resolve_enrich_top_n_from_env(monkeypatch):
    monkeypatch.setenv("HSI_ENRICH_TOP_N", "3")
    assert resolve_enrich_top_n() == 3
    monkeypatch.setenv("HSI_ENRICH_TOP_N", "0")
    assert resolve_enrich_top_n() == 0
    monkeypatch.setenv("HSI_ENRICH_TOP_N", "all")
    assert resolve_enrich_top_n() is None
    monkeypatch.setenv("HSI_ENRICH_TOP_N", "bad")
    assert resolve_enrich_top_n() is None  # default = all
    assert resolve_enrich_top_n(7) == 7
    assert resolve_enrich_top_n(0) == 0
    monkeypatch.delenv("HSI_ENRICH_TOP_N", raising=False)
    assert resolve_enrich_top_n() is None  # default = all


def test_resolve_enrich_etnet_top_n_from_env(monkeypatch):
    monkeypatch.setenv("HSI_ENRICH_ETNET_TOP_N", "4")
    assert resolve_enrich_etnet_top_n() == 4
    monkeypatch.setenv("HSI_ENRICH_ETNET_TOP_N", "0")
    assert resolve_enrich_etnet_top_n() == 0  # none, not unlimited
    monkeypatch.setenv("HSI_ENRICH_ETNET_TOP_N", "all")
    assert resolve_enrich_etnet_top_n() is None
    monkeypatch.setenv("HSI_ENRICH_ETNET_TOP_N", "bad")
    assert resolve_enrich_etnet_top_n() == 10
    assert resolve_enrich_etnet_top_n(2) == 2
    assert resolve_enrich_etnet_top_n(0) == 0
    monkeypatch.delenv("HSI_ENRICH_ETNET_TOP_N", raising=False)
    assert resolve_enrich_etnet_top_n() == 10

def test_build_lite_context_uses_quote_and_signals():
    match = {
        "code": "0700.HK",
        "name": "腾讯",
        "close": 400,
        "high": 405,
        "low": 395,
        "entry20": 390,
        "entry55": 380,
        "s1_breakout": True,
        "s2_breakout": False,
        "potential_score": 82,
        "potential_tier": "A",
        "ma20": 395.0,
        "rsi_12": 58.2,
        "macd_dif": 1.2,
        "macd_status": "bullish",
        "kline_patterns": ["hammer"],
        "double_top": False,
    }
    quote = {"price": 401.5, "change_pct": 1.2, "source": "akshare"}
    ctx = build_lite_context(match, quote)
    assert ctx["code"] == "0700.HK"
    assert ctx["stock_name"] == "腾讯"
    assert ctx["realtime"]["price"] == 401.5
    assert ctx["today"]["pct_chg"] == 1.2
    assert ctx["hsi_signals"]["s1_breakout"] is True
    assert ctx["technicals"]["ma20"] == 395.0
    assert ctx["technicals"]["rsi_12"] == 58.2
    assert ctx["patterns"]["kline_patterns"] == ["hammer"]
    assert "RSI/MACD/MAs" in ctx["analysis_notes"]


def test_enrich_match_passes_news_comment_instruction_to_deepseek():
    from datetime import date

    today = date.today().isoformat()
    match = {"code": "0700.HK", "name": "腾讯", "close": 400, "potential_score": 80}
    fetcher = MagicMock()
    fetcher.get_realtime_quote.return_value = None
    search = MagicMock()
    search.is_available = False
    analyzer = MagicMock()
    analyzer.is_available = MagicMock(return_value=True)
    analyzer.analyze.return_value = SimpleNamespace(success=True, news_summary="消息面偏暖")

    with patch(
        "src.services.tencent_stock_news.is_tencent_stock_news_enabled",
        return_value=True,
    ), patch(
        "src.services.tencent_stock_news.fetch_tencent_stock_news",
        return_value=[
            {
                "title": "腾讯发布新品",
                "published_date": f"{today} 10:00:00",
                "url": "https://example.com/n1",
                "source": "腾讯新闻",
            }
        ],
    ), patch(
        "src.services.kimi_comment.is_kimi_comment_enabled",
        return_value=False,
    ):
        enrich_match(match, fetcher=fetcher, search=search, analyzer=analyzer)

    assert analyzer.analyze.called
    args, kwargs = analyzer.analyze.call_args
    news_ctx = kwargs.get("news_context") or ""
    assert "本次实时抓取" in news_ctx
    assert "禁止使用模型训练记忆" in news_ctx
    assert "news_summary" in news_ctx
    assert "腾讯发布新品" in news_ctx
    assert args[0].get("news_window_days") == 2
    hsi_context = kwargs.get("analysis_context_pack_summary") or ""
    assert "HSI 扫描专用上下文" in hsi_context
    assert "hsi_signals" in hsi_context


def test_enrich_match_partial_failure_resilience():
    from datetime import date

    today = date.today().isoformat()
    match = {"code": "0700.HK", "name": "腾讯", "close": 400, "potential_score": 80}

    fetcher = MagicMock()
    fetcher.get_realtime_quote.side_effect = RuntimeError("quote down")

    search = MagicMock()
    search.is_available = True
    search.search_stock_news.return_value = SimpleNamespace(
        success=True,
        results=[
            SimpleNamespace(
                title="腾讯新闻",
                snippet="摘要",
                published_date=today,
            )
        ],
        to_context=lambda max_results=5: f"- 腾讯新闻 [{today}]\n  摘要",
    )

    analyzer = MagicMock()
    analyzer.is_available = MagicMock(return_value=True)
    analyzer.analyze.side_effect = RuntimeError("llm down")

    with patch(
        "src.services.tencent_stock_news.fetch_tencent_stock_news",
        return_value=[],
    ), patch(
        "src.services.tencent_stock_news.is_tencent_stock_news_enabled",
        return_value=True,
    ), patch(
        "src.services.kimi_comment.is_kimi_comment_enabled",
        return_value=False,
    ):
        result = enrich_match(match, fetcher=fetcher, search=search, analyzer=analyzer)
    assert result["quote_error"] == "quote down"
    assert "腾讯新闻" in result["news_text"]
    assert result["news_provider"] == "search"
    assert result["analysis_error"] == "llm down"


def test_enrich_match_prefers_tencent_ifzq_news():
    from datetime import date

    today = date.today().isoformat()
    match = {"code": "0700.HK", "name": "腾讯", "close": 400, "potential_score": 80}
    fetcher = MagicMock()
    fetcher.get_realtime_quote.return_value = None
    search = MagicMock()
    search.is_available = True
    search.search_stock_news.return_value = SimpleNamespace(
        success=True,
        results=[],
        to_context=lambda max_results=5: "- 搜索新闻",
    )
    analyzer = MagicMock()
    analyzer.is_available = MagicMock(return_value=False)

    ifzq_items = [
        {
            "title": "腾讯营收领先",
            "snippet": "腾讯营收领先",
            "url": "https://gu.qq.com/x",
            "source": "智研咨询",
            "published_date": f"{today} 13:46:12",
            "provider": "tencent_ifzq",
            "symbol": "hk00700",
        }
    ]
    with patch(
        "src.services.tencent_stock_news.fetch_tencent_stock_news",
        return_value=ifzq_items,
    ), patch(
        "src.services.tencent_stock_news.is_tencent_stock_news_enabled",
        return_value=True,
    ), patch(
        "src.services.kimi_comment.is_kimi_comment_enabled",
        return_value=False,
    ):
        result = enrich_match(match, fetcher=fetcher, search=search, analyzer=analyzer)

    assert "腾讯营收领先" in result["news_text"]
    assert result["news_error"] is None
    assert result["news_provider"] in {"tencent_ifzq", "tencent_ifzq+search"}


def test_enrich_match_falls_back_to_search_when_ifzq_empty():
    from datetime import date

    today = date.today().isoformat()
    match = {"code": "0700.HK", "name": "腾讯", "close": 400}
    fetcher = MagicMock()
    fetcher.get_realtime_quote.return_value = None
    search = MagicMock()
    search.is_available = True
    search.search_stock_news.return_value = SimpleNamespace(
        success=True,
        results=[SimpleNamespace(title="备用新闻", snippet="s", published_date=today)],
        to_context=lambda max_results=5: f"- 备用新闻 [{today}]",
    )
    analyzer = MagicMock()
    analyzer.is_available = MagicMock(return_value=False)

    with patch(
        "src.services.tencent_stock_news.fetch_tencent_stock_news",
        return_value=[],
    ), patch(
        "src.services.tencent_stock_news.is_tencent_stock_news_enabled",
        return_value=True,
    ), patch(
        "src.services.kimi_comment.is_kimi_comment_enabled",
        return_value=False,
    ):
        result = enrich_match(match, fetcher=fetcher, search=search, analyzer=analyzer)

    assert "备用新闻" in result["news_text"]
    assert result["news_provider"] == "search"


def test_build_enriched_report_contains_section_headings():
    scan_payload = {
        "matches": [
            {
                "code": "0700.HK",
                "name": "腾讯",
                "close": 400,
                "url": "https://example.com",
                "s1_breakout": True,
                "s2_breakout": False,
                "close_vs_entry": True,
                "close_vs_s2_entry": False,
                "potential_score": 88,
                "potential_tier": "A",
            }
        ],
        "no_price": [],
        "stats": {"tickers": 1, "total_ms": 12},
    }
    analysis = SimpleNamespace(
        success=True,
        sentiment_score=75,
        operation_advice="买入",
        trend_prediction="看多",
        confidence_level="高",
        analysis_summary="突破有效",
        risk_warning="注意回撤",
        news_summary="有利好",
        dashboard={
            "core_conclusion": {"one_sentence": "偏多", "signal_type": "buy"},
            "battle_plan": {"sniper_points": {"stop_loss": "390"}},
        },
    )
    enrichments = [
        {
            "code": "0700.HK",
            "name": "腾讯",
            "match": {
                **scan_payload["matches"][0],
                "ma20": 395.0,
                "rsi_12": 55.0,
                "macd_dif": 0.5,
                "macd_status": "bullish",
                "kline_patterns": ["hammer"],
            },
            "quote": {"price": 401, "source": "akshare", "change_pct": 1.1},
            "quote_error": None,
            "news_text": "- 腾讯相关新闻",
            "news_error": None,
            "analysis": analysis,
            "analysis_error": None,
            "kimi_comment": "Kimi：短线关注回踩支撑。",
            "kimi_comment_error": None,
            "gemini_comment": "Gemini：突破有效但需防回撤。",
            "gemini_comment_error": None,
        }
    ]
    report = build_enriched_report(scan_payload, enrichments, top_n=None, etnet_top_n=None)
    assert "增强分析（持仓 0 + 全部匹配股 + 全部经济通）" in report
    assert "多数据源行情" in report
    assert "技术指标与形态" in report
    assert "RSI" in report or "rsi" in report.lower() or "MA20" in report
    assert "实时新闻" in report
    assert "DeepSeek 决策仪表盘" in report
    assert "来源: **DeepSeek**" in report
    assert "Kimi 独立点评" in report
    assert "来源: **Kimi / Moonshot**" in report
    assert "短线关注回踩支撑" in report
    assert "Gemini 独立点评" in report
    assert "来源: **Gemini**" in report
    assert "突破有效但需防回撤" in report
    assert "腾讯" in report
    assert "401" in report
    capped = build_enriched_report(
        scan_payload, enrichments, top_n=5, etnet_top_n=3
    )
    assert "增强分析（持仓 0 + 匹配股 Top 5 + 经济通额外 Top 3）" in capped

def test_format_technical_section_renders_indicators():
    text = format_technical_section(
        {
            "ma20": 100.0,
            "rsi_12": 45.0,
            "macd_dif": 0.1,
            "macd_status": "bullish",
            "kline_patterns": ["double_top"],
        }
    )
    assert "技术指标与形态" in text
    assert "MA20=100.0" in text
    assert "双顶(double_top)" in text


def test_format_sections_with_errors():
    assert "行情获取失败" in format_quote_section(None, "boom")
    assert "新闻检索失败" in format_news_section("", "boom")
    assert "[DeepSeek] 分析失败" in format_dashboard_section(None, "boom")
    assert "无技术指标" in format_technical_section({})
    assert "[Kimi] 点评不可用" in format_kimi_comment_section("", "boom")
    labeled = format_kimi_comment_section("观点偏多")
    assert "Kimi 独立点评" in labeled
    assert "[Kimi]" in labeled
    assert "来源: **Kimi / Moonshot**" in labeled
    assert "[Gemini] 点评不可用" in format_gemini_comment_section("", "boom")
    gemini_labeled = format_gemini_comment_section("观点偏多")
    assert "Gemini 独立点评" in gemini_labeled
    assert "[Gemini]" in gemini_labeled
    assert "来源: **Gemini**" in gemini_labeled
    deep = format_dashboard_section(
        SimpleNamespace(
            success=True,
            sentiment_score=70,
            operation_advice="买入",
            trend_prediction="看多",
            confidence_level="中",
            analysis_summary="突破",
            risk_warning="",
            news_summary="公司发布利好合同，情绪偏暖。",
            dashboard={
                "intelligence": {
                    "latest_news": ["2026-07-23 签订大单"],
                    "positive_catalysts": ["合同落地"],
                    "risk_alerts": ["注意获利回吐"],
                }
            },
        )
    )
    assert "[DeepSeek] 综合评分: 70" in deep
    assert "来源: **DeepSeek**" in deep
    assert "[DeepSeek] 消息面点评: 公司发布利好合同" in deep
    assert "[DeepSeek] 最新消息: 2026-07-23 签订大单" in deep
    assert "[DeepSeek] 利好催化: 合同落地" in deep
    assert "[DeepSeek] 风险警报: 注意获利回吐" in deep
    empty_news = format_dashboard_section(
        SimpleNamespace(
            success=True,
            sentiment_score=50,
            operation_advice="观望",
            trend_prediction="震荡",
            confidence_level="低",
            analysis_summary="",
            risk_warning="",
            news_summary="",
            dashboard={},
        )
    )
    assert "[DeepSeek] 消息面点评: （未输出）" in empty_news


def test_enrich_match_adds_kimi_comment():
    match = {"code": "0700.HK", "name": "腾讯", "close": 400}
    fetcher = MagicMock()
    fetcher.get_realtime_quote.return_value = None
    search = MagicMock()
    search.is_available = False
    analyzer = MagicMock()
    analyzer.is_available = MagicMock(return_value=False)

    with patch(
        "src.services.tencent_stock_news.is_tencent_stock_news_enabled",
        return_value=False,
    ), patch(
        "src.services.kimi_comment.is_kimi_comment_enabled",
        return_value=True,
    ), patch(
        "src.services.kimi_comment.generate_kimi_comment",
        return_value="独立点评内容",
    ):
        result = enrich_match(match, fetcher=fetcher, search=search, analyzer=analyzer)

    assert result["kimi_comment"] == "独立点评内容"
    assert result["kimi_comment_error"] is None


def test_enrich_match_adds_gemini_comment():
    match = {"code": "0700.HK", "name": "腾讯", "close": 400}
    fetcher = MagicMock()
    fetcher.get_realtime_quote.return_value = None
    search = MagicMock()
    search.is_available = False
    analyzer = MagicMock()
    analyzer.is_available = MagicMock(return_value=False)

    with patch(
        "src.services.tencent_stock_news.is_tencent_stock_news_enabled",
        return_value=False,
    ), patch(
        "src.services.kimi_comment.is_kimi_comment_enabled",
        return_value=False,
    ), patch(
        "src.services.gemini_comment.is_gemini_comment_enabled",
        return_value=True,
    ), patch(
        "src.services.gemini_comment.generate_gemini_comment",
        return_value="Gemini 独立点评内容",
    ):
        result = enrich_match(match, fetcher=fetcher, search=search, analyzer=analyzer)

    assert result["gemini_comment"] == "Gemini 独立点评内容"
    assert result["gemini_comment_error"] is None


def test_default_analyzer_is_pinned_to_deepseek(monkeypatch):
    from src.config import Config

    monkeypatch.setenv("HSI_DEEPSEEK_MODEL", "deepseek-v4-flash")
    base_config = Config(
        litellm_model="gemini/gemini-3.6-flash",
        litellm_fallback_models=["gemini/gemini-3.1-pro"],
        litellm_config_path="litellm.yaml",
        llm_models_source="llm_channels",
        llm_channels=[{"name": "gemini"}],
        llm_model_list=[{"model_name": "gemini/gemini-3.6-flash"}],
        deepseek_api_keys=["test-deepseek-key"],
    )

    with patch("src.config.get_config", return_value=base_config), patch(
        "src.analyzer.GeminiAnalyzer"
    ) as analyzer_cls:
        analyzer = _default_analyzer()

    assert analyzer is analyzer_cls.return_value
    pinned = analyzer_cls.call_args.kwargs["config"]
    assert pinned.litellm_model == "deepseek/deepseek-v4-flash"
    assert pinned.litellm_fallback_models == []
    assert pinned.llm_channels == []
    assert pinned.llm_model_list == []
    assert pinned.litellm_config_path is None


@patch("src.services.hsi_enrichment.scan_hsi")
def test_run_hsi_scan_enriched_saves_report(mock_scan, tmp_path: Path):
    mock_scan.return_value = {
        "matches": [
            {
                "code": "0700.HK",
                "name": "腾讯",
                "close": 400,
                "url": "",
                "s1_breakout": True,
                "s2_breakout": False,
                "close_vs_entry": False,
                "close_vs_s2_entry": False,
                "potential_score": 90,
                "potential_tier": "A",
            },
            {
                "code": "9988.HK",
                "name": "阿里",
                "close": 100,
                "url": "",
                "s1_breakout": True,
                "s2_breakout": False,
                "close_vs_entry": False,
                "close_vs_s2_entry": False,
                "potential_score": 50,
                "potential_tier": "C",
            },
        ],
        "no_price": [],
        "stats": {"tickers": 2, "total_ms": 1},
        "skipped": False,
        "etnet_top": {
            "enabled": True,
            "boards": {
                "turnover": [
                    {"code": "0700.HK", "name": "TENCENT"},
                    {"code": "2513.HK", "name": "Z.AI"},
                ],
                "volume": [],
                "up": [],
            },
            "errors": {},
        },
    }

    fetcher = MagicMock()
    fetcher.get_realtime_quote.return_value = SimpleNamespace(
        to_dict=lambda: {"price": 401, "source": "test"}
    )
    search = MagicMock()
    search.is_available = False
    analyzer = MagicMock()
    analyzer.is_available = MagicMock(return_value=False)

    with patch(
        "src.services.tencent_stock_news.fetch_tencent_stock_news",
        return_value=[],
    ), patch(
        "src.services.tencent_stock_news.is_tencent_stock_news_enabled",
        return_value=False,
    ), patch(
        "src.services.kimi_comment.is_kimi_comment_enabled",
        return_value=False,
    ):
        result = run_hsi_scan_enriched(
            period="3mo",
            conditions="s1_breakout",
            check_trading_day=False,
            top_n=1,
            etnet_top_n=1,
            fetcher=fetcher,
            search=search,
            analyzer=analyzer,
            reports_dir=tmp_path,
            save_report=True,
        )
    assert result["top_n"] == 1
    assert result["etnet_top_n"] == 1
    assert len(result["enrichments"]) == 2
    assert result["enrichments"][0]["code"] == "0700.HK"
    assert result["enrichments"][1]["code"] == "2513.HK"
    assert result["report_path"]
    path = Path(result["report_path"])
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "多数据源行情" in text
    assert "增强分析（持仓 0 + 匹配股 Top 1 + 经济通额外 Top 1）" in text
    assert "来源: 匹配" in text or "来源: 经济通" in text
    assert "2513.HK" in text
