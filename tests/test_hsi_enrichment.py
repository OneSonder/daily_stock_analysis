# -*- coding: utf-8 -*-
"""Tests for HSI lite enrichment helpers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.services.hsi_enrichment import (
    build_enriched_report,
    build_lite_context,
    enrich_match,
    format_dashboard_section,
    format_news_section,
    format_quote_section,
    resolve_enrich_top_n,
    run_hsi_scan_enriched,
    select_top_matches,
)


def test_select_top_matches_orders_by_potential_score():
    matches = [
        {"code": "A", "potential_score": 40},
        {"code": "B", "potential_score": 90},
        {"code": "C", "potential_score": 70},
        {"code": "D"},
    ]
    top = select_top_matches(matches, top_n=2)
    assert [m["code"] for m in top] == ["B", "C"]


def test_resolve_enrich_top_n_from_env(monkeypatch):
    monkeypatch.setenv("HSI_ENRICH_TOP_N", "3")
    assert resolve_enrich_top_n() == 3
    monkeypatch.setenv("HSI_ENRICH_TOP_N", "bad")
    assert resolve_enrich_top_n() == 5
    assert resolve_enrich_top_n(7) == 7


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
    }
    quote = {"price": 401.5, "change_pct": 1.2, "source": "akshare"}
    ctx = build_lite_context(match, quote)
    assert ctx["code"] == "0700.HK"
    assert ctx["stock_name"] == "腾讯"
    assert ctx["realtime"]["price"] == 401.5
    assert ctx["today"]["pct_chg"] == 1.2
    assert ctx["hsi_signals"]["s1_breakout"] is True


def test_enrich_match_partial_failure_resilience():
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
                published_date="2026-07-21",
            )
        ],
        to_context=lambda max_results=5: "- 腾讯新闻 [2026-07-21]\n  摘要",
    )

    analyzer = MagicMock()
    analyzer.is_available = MagicMock(return_value=True)
    analyzer.analyze.side_effect = RuntimeError("llm down")

    result = enrich_match(match, fetcher=fetcher, search=search, analyzer=analyzer)
    assert result["quote_error"] == "quote down"
    assert "腾讯新闻" in result["news_text"]
    assert result["analysis_error"] == "llm down"


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
            "match": scan_payload["matches"][0],
            "quote": {"price": 401, "source": "akshare", "change_pct": 1.1},
            "quote_error": None,
            "news_text": "- 腾讯相关新闻",
            "news_error": None,
            "analysis": analysis,
            "analysis_error": None,
        }
    ]
    report = build_enriched_report(scan_payload, enrichments, top_n=5)
    assert "多数据源行情" in report
    assert "实时新闻" in report
    assert "LLM决策仪表盘" in report
    assert "腾讯" in report
    assert "401" in report


def test_format_sections_with_errors():
    assert "行情获取失败" in format_quote_section(None, "boom")
    assert "新闻检索失败" in format_news_section("", "boom")
    assert "LLM 分析失败" in format_dashboard_section(None, "boom")


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
    }

    fetcher = MagicMock()
    fetcher.get_realtime_quote.return_value = SimpleNamespace(
        to_dict=lambda: {"price": 401, "source": "test"}
    )
    search = MagicMock()
    search.is_available = False
    analyzer = MagicMock()
    analyzer.is_available = MagicMock(return_value=False)

    result = run_hsi_scan_enriched(
        period="3mo",
        conditions="s1_breakout",
        check_trading_day=False,
        top_n=1,
        fetcher=fetcher,
        search=search,
        analyzer=analyzer,
        reports_dir=tmp_path,
        save_report=True,
    )
    assert result["top_n"] == 1
    assert len(result["enrichments"]) == 1
    assert result["enrichments"][0]["code"] == "0700.HK"
    assert result["report_path"]
    path = Path(result["report_path"])
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "多数据源行情" in text
    assert "Top 1 增强分析" in text
