# -*- coding: utf-8 -*-
"""Tests for all-HK Turtle scan orchestration (no LLM)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.services.hk_stock_scanner import (
    HkUniverseError,
    apply_hk_liquidity_gates,
    fetch_tencent_news_for_matches,
    format_hk_scan_report,
    load_hk_stocks_universe,
    normalize_hk_code,
    run_hk_stocks_scan,
)
from src.services.stock_universes import HK_ALL_STOCKS_PATH


def test_normalize_hk_code_forms():
    assert normalize_hk_code("00001.HK") == "0001.HK"
    assert normalize_hk_code("00700.HK") == "0700.HK"
    assert normalize_hk_code("0700.HK") == "0700.HK"
    assert normalize_hk_code("hk00700") == "0700.HK"
    assert normalize_hk_code("600519.SH") is None
    assert normalize_hk_code("") is None


def test_load_hk_stocks_universe_from_json(tmp_path: Path):
    path = tmp_path / "hk.json"
    path.write_text(
        json.dumps(
            [
                {"code": "00001.HK", "name": "长和"},
                {"code": "0700.HK", "name": "腾讯控股"},
                {"code": "0001.HK", "name": "长和-dup"},
                {"code": "bad", "name": "x"},
            ]
        ),
        encoding="utf-8",
    )
    stocks = load_hk_stocks_universe(universe_path=path)
    assert stocks == [
        {"code": "0001.HK", "name": "长和"},
        {"code": "0700.HK", "name": "腾讯控股"},
    ]


def test_load_hk_stocks_universe_missing_file(tmp_path: Path):
    missing = tmp_path / "missing.json"
    with pytest.raises(HkUniverseError, match="not found"):
        load_hk_stocks_universe(universe_path=missing)


def test_load_hk_stocks_universe_empty_file(tmp_path: Path):
    path = tmp_path / "empty.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(HkUniverseError, match="empty|No valid"):
        load_hk_stocks_universe(universe_path=path)


def test_load_default_committed_universe_has_expected_shape():
    stocks = load_hk_stocks_universe(universe_path=HK_ALL_STOCKS_PATH, force_reload=True)
    assert len(stocks) > 1000
    assert stocks[0]["code"].endswith(".HK")
    assert "name" in stocks[0]


def test_fetch_tencent_news_for_matches_only_and_soft_fails():
    matches = [
        {"code": "0700.HK", "name": "腾讯"},
        {"code": "9988.HK", "name": "阿里"},
    ]
    with patch(
        "src.services.tencent_stock_news.fetch_tencent_stock_news",
        side_effect=[
            [{"title": "腾讯新闻", "published_date": "2099-01-01", "source": "x"}],
            RuntimeError("boom"),
        ],
    ) as mock_fetch, patch(
        "src.services.tencent_stock_news.is_tencent_stock_news_enabled",
        return_value=True,
    ):
        rows = fetch_tencent_news_for_matches(matches, max_age_days=7)

    assert mock_fetch.call_count == 2
    assert rows[0]["code"] == "0700.HK"
    assert "腾讯新闻" in rows[0]["news_text"]
    assert rows[0]["news_error"] is None
    assert rows[1]["code"] == "9988.HK"
    assert rows[1]["news_error"] == "boom"
    assert rows[1]["news_text"] == ""


def test_format_hk_scan_report_keeps_sections_and_omits_ai():
    payload = {
        "matches": [
            {
                "code": "0700.HK",
                "name": "腾讯",
                "close": 400,
                "url": "https://finance.yahoo.com/quote/0700.HK",
                "s1_breakout": True,
                "s2_breakout": False,
                "close_vs_entry": True,
                "close_vs_s2_entry": False,
                "n": 5.0,
                "stop_long_2n": 390.0,
                "breakout_extension_n": 1.2,
                "turtle_trend_ok": True,
                "turtle_trend_rule": "ma20_ma55",
                "s1_last_was_winner": False,
                "s1_entry_allowed": True,
                "s1_recent_high_timing": "today",
                "s1_recent_close_timing": None,
                "s2_recent_high_timing": "previous",
                "s2_recent_close_timing": None,
                "potential_score": 81,
                "potential_tier": "A",
                "potential_reasons": ["S1最高价首破", "趋势通过"],
                "volume_ratio": 1.4,
                "volume_confirm": True,
                "avg_turnover_20": 8_000_000,
                "ma20": 395,
                "rsi_12": 55,
                "macd_status": "多头",
                "kline_patterns": [],
            }
        ],
        "no_price": [{"code": "0001.HK", "name": "长和", "message": "empty"}],
        "stats": {
            "tickers": 2,
            "total_ms": 12,
            "cache_hits": 0,
            "batch_downloaded": 1,
            "unavailable_without_fallback": 1,
        },
        "conditions": ["s1_breakout", "s2_breakout"],
        "universe_source": "resources/universes/hk_all_stocks.json",
        "skipped": False,
    }
    news = {
        "0700.HK": {
            "code": "0700.HK",
            "news_text": "- 腾讯营收领先 [2099-01-01]",
            "news_error": None,
        }
    }
    text = format_hk_scan_report(payload, news_by_code=news)
    assert "## 匹配结果（1）" in text
    assert "### 技术指标与形态" in text
    assert "海龟: N=5.0" in text
    assert "| S1近H | S2近H | S1近C | S2近C |" in text
    assert "| 档 | 分 | S1开 | 趋势 | 延伸N | 量比 |" in text
    assert "| A | 81 | 是 | 通过 | 1.2 | 1.4 |" in text
    assert "| 今日 | 前一交易日 | 无 | 无 |" in text
    assert "近期突破: S1 High=今日 / Close=无 | S2 High=前一交易日 / Close=无" in text
    assert "潜力: A 81" in text
    assert "流动性过滤: 0" in text
    assert "按潜力分降序" in text
    assert "resources/universes/hk_all_stocks.json" in text
    assert "## 腾讯新闻（仅匹配股）" in text
    assert "腾讯营收领先" in text
    assert "DeepSeek" not in text
    assert "Kimi" not in text
    assert "Gemini" not in text
    assert "LLM" not in text
    assert "Tushare" not in text
    assert "持仓止损参考" not in text
    assert "经济通" not in text
    assert "无行情数据的代码" not in text


@patch("src.services.hk_stock_scanner.fetch_tencent_news_for_matches")
@patch("src.services.hk_stock_scanner.scan_stocks")
@patch("src.services.hk_stock_scanner.load_hk_stocks_universe")
def test_run_hk_stocks_scan_loads_json_universe_no_llm(
    mock_universe,
    mock_scan,
    mock_news,
    tmp_path: Path,
):
    mock_universe.return_value = [{"code": "0700.HK", "name": "腾讯"}]
    mock_scan.return_value = {
        "matches": [{"code": "0700.HK", "name": "腾讯", "s1_breakout": True}],
        "results": [{"code": "0700.HK", "status": "ok"}],
        "no_price": [],
        "stats": {"tickers": 1, "total_ms": 1, "cache_hits": 0, "batch_downloaded": 1},
        "skipped": False,
        "conditions": ["s1_breakout"],
    }
    mock_news.return_value = [
        {"code": "0700.HK", "name": "腾讯", "news_text": "- n", "news_error": None}
    ]

    result = run_hk_stocks_scan(
        period="3mo",
        conditions="s1_breakout",
        max_workers=4,
        batch_size=50,
        check_trading_day=False,
        allow_per_ticker_fallback=False,
        reports_dir=tmp_path,
        save_report=True,
    )

    mock_universe.assert_called_once()
    mock_scan.assert_called_once()
    kwargs = mock_scan.call_args.kwargs
    assert kwargs["batch_size"] == 50
    assert kwargs["allow_per_ticker_fallback"] is False
    assert kwargs["use_multi_source"] is False
    mock_news.assert_called_once()
    assert "hk_all_stocks.json" in result["payload"]["universe_source"].replace("\\", "/")
    assert result["report_path"]
    assert Path(result["report_path"]).exists()
    assert "匹配结果" in result["report_text"]
    assert "DeepSeek" not in result["report_text"]


def test_apply_hk_liquidity_gates_drops_penny_and_thin_turnover():
    kept, dropped = apply_hk_liquidity_gates(
        [
            {"code": "PENNY.HK", "close": 0.05, "avg_turnover_20": 2_000_000},
            {"code": "THIN.HK", "close": 10.0, "avg_turnover_20": 1_000},
            {"code": "0700.HK", "close": 400.0, "avg_turnover_20": 8_000_000, "potential_score": 80},
            {"code": "NODATA.HK", "close": 12.0},
        ],
        min_price=0.1,
        min_avg_turnover=500_000,
        require_volume_confirm=False,
    )
    codes = {row["code"] for row in kept}
    assert codes == {"0700.HK", "NODATA.HK"}
    reasons = {row["code"]: row["liquidity_filter_reason"] for row in dropped}
    assert "PENNY.HK" in reasons
    assert "THIN.HK" in reasons


@patch("src.services.hk_stock_scanner.fetch_tencent_news_for_matches")
@patch("src.services.hk_stock_scanner.scan_stocks")
@patch("src.services.hk_stock_scanner.load_hk_stocks_universe")
def test_run_hk_stocks_scan_filters_then_ranks_before_news(
    mock_universe,
    mock_scan,
    mock_news,
    tmp_path: Path,
):
    mock_universe.return_value = [{"code": "0700.HK", "name": "腾讯"}]
    mock_scan.return_value = {
        "matches": [
            {
                "code": "THIN.HK",
                "name": "薄",
                "close": 10.0,
                "avg_turnover_20": 100.0,
                "potential_score": 99,
                "s1_breakout": True,
            },
            {
                "code": "0700.HK",
                "name": "腾讯",
                "close": 400.0,
                "avg_turnover_20": 9_000_000,
                "potential_score": 70,
                "s1_breakout": True,
            },
            {
                "code": "9988.HK",
                "name": "阿里",
                "close": 90.0,
                "avg_turnover_20": 7_000_000,
                "potential_score": 88,
                "s1_breakout": True,
            },
        ],
        "results": [],
        "no_price": [],
        "stats": {"tickers": 3, "total_ms": 1, "cache_hits": 0, "batch_downloaded": 3},
        "skipped": False,
        "conditions": ["s1_breakout"],
    }
    mock_news.return_value = []

    result = run_hk_stocks_scan(
        check_trading_day=False,
        reports_dir=tmp_path,
        save_report=False,
        min_price=0.1,
        min_avg_turnover=500_000,
        require_volume_confirm=False,
    )
    codes = [m["code"] for m in result["payload"]["matches"]]
    assert codes == ["9988.HK", "0700.HK"]
    assert result["payload"]["stats"]["liquidity_filtered"] == 1
    news_matches = mock_news.call_args.args[0]
    assert [m["code"] for m in news_matches] == ["9988.HK", "0700.HK"]
