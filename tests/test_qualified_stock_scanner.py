# -*- coding: utf-8 -*-
"""Tests for qualified stock scanner and daily report integration helpers."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.report_language import get_report_labels
from src.services.hsi_scanner import HSI_STOCKS, parse_conditions
from src.services.stock_universes import (
    DOW_STOCKS,
    NASDAQ_TOP_STOCKS,
    US_TOP_STOCKS,
    load_hk_all_stocks,
)
from src.services.qualified_stock_scanner import (
    _apply_json_rules,
    _resolve_name,
    _to_yahoo_code,
    annotate_matched_conditions,
    format_qualified_scan_section,
    resolve_universe,
    run_qualified_scan,
    to_tradingview_chart_url,
    to_tradingview_symbol,
)


class TestQualifiedStockScanner(unittest.TestCase):
    def test_parse_conditions_accepts_kline_patterns(self):
        wanted = parse_conditions("w_bottom,m_top,bullish_engulfing")
        self.assertEqual(wanted, {"w_bottom", "m_top", "bullish_engulfing"})

    def test_parse_conditions_accepts_recent_turtle_breakouts(self):
        wanted = parse_conditions(
            "s1_recent_high_breakout,s2_recent_close_breakout,close_vs_ma100"
        )
        self.assertEqual(
            wanted,
            {"s1_recent_high_breakout", "s2_recent_close_breakout", "close_vs_ma100"},
        )

    def test_to_yahoo_code_from_manager_format(self):
        self.assertEqual(_to_yahoo_code("HK00700"), "0700.HK")

    def test_to_tradingview_symbol_for_hk(self):
        self.assertEqual(to_tradingview_symbol("0700.HK"), "HKEX:0700")
        self.assertEqual(to_tradingview_symbol("HK00700"), "HKEX:0700")

    def test_to_tradingview_symbol_for_us(self):
        self.assertEqual(to_tradingview_symbol("JPM"), "JPM")
        self.assertEqual(to_tradingview_symbol("AAPL"), "AAPL")

    def test_to_tradingview_chart_url(self):
        self.assertEqual(
            to_tradingview_chart_url("0700.HK"),
            "https://www.tradingview.com/chart/?symbol=HKEX:0700",
        )
        self.assertEqual(
            to_tradingview_chart_url("JPM"),
            "https://www.tradingview.com/chart/?symbol=JPM",
        )

    def test_annotate_matched_conditions_adds_tradingview_url(self):
        matches = [{"code": "0700.HK", "close_vs_entry": True}]
        annotated = annotate_matched_conditions(matches, {"close_vs_entry"})
        self.assertIn("tradingview_url", annotated[0])
        self.assertIn("HKEX:0700", annotated[0]["tradingview_url"])

    def test_resolve_universe_hsi_token(self):
        stocks, label = resolve_universe("HSI")
        self.assertEqual(label, "hsi")
        self.assertEqual(len(stocks), len(HSI_STOCKS))

    def test_resolve_universe_hk_all_token(self):
        stocks, label = resolve_universe("HK_ALL")
        self.assertEqual(label, "hk_all")
        self.assertGreater(len(stocks), len(HSI_STOCKS))
        codes = {item["code"] for item in stocks}
        self.assertTrue(all(code.endswith(".HK") for code in codes))
        self.assertIn("0700.HK", codes)

    @patch("src.services.qualified_stock_scanner.load_hk_all_stocks")
    def test_resolve_name_hk_all_stock(self, mock_load_hk_all):
        mock_load_hk_all.return_value = [
            {"code": "0004.HK", "name": "九龍倉集團"},
        ]
        import src.services.qualified_stock_scanner as scanner_module
        scanner_module._HK_ALL_NAME_BY_CODE = {}

        self.assertEqual(_resolve_name("0004.HK"), "九龍倉集團")

    def test_load_hk_all_stocks_matches_committed_snapshot(self):
        stocks = load_hk_all_stocks(force_reload=True)
        self.assertGreater(len(stocks), 1000)
        self.assertEqual(stocks[0]["code"], "0001.HK")

    def test_resolve_universe_dow_token(self):
        stocks, label = resolve_universe("DOW")
        self.assertEqual(label, "dow")
        self.assertEqual(len(stocks), len(DOW_STOCKS))
        self.assertEqual(stocks[0]["code"], "AAPL")

    def test_resolve_universe_nasdaq_top_token(self):
        stocks, label = resolve_universe("NASDAQ_TOP")
        self.assertEqual(label, "nasdaq_top")
        self.assertEqual(len(stocks), len(NASDAQ_TOP_STOCKS))
        self.assertEqual(stocks[0]["code"], "NVDA")

    def test_resolve_universe_us_top_token(self):
        stocks, label = resolve_universe("US_TOP")
        self.assertEqual(label, "us_top")
        self.assertEqual(len(stocks), len(US_TOP_STOCKS))
        # merged list should keep deterministic order and remove duplicates
        self.assertEqual(stocks[0]["code"], "AAPL")
        self.assertEqual(len({item["code"] for item in stocks}), len(stocks))

    def test_resolve_universe_custom_codes(self):
        stocks, label = resolve_universe("HK00700,9988.HK")
        self.assertEqual(label, "custom")
        self.assertEqual(stocks[0]["code"], "0700.HK")
        self.assertEqual(stocks[1]["code"], "9988.HK")

    def test_resolve_universe_custom_us_codes_keeps_yahoo_style(self):
        stocks, label = resolve_universe("AAPL,MSFT,NVDA")
        self.assertEqual(label, "custom")
        self.assertEqual([item["code"] for item in stocks], ["AAPL", "MSFT", "NVDA"])

    def test_resolve_universe_json_file(self):
        payload = [{"code": "0700.HK", "name": "Tencent"}]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
            json.dump(payload, handle)
            path = handle.name
        try:
            stocks, label = resolve_universe("ignored", json_path=path)
            self.assertEqual(label, "json")
            self.assertEqual(stocks[0]["code"], "0700.HK")
            self.assertEqual(stocks[0]["name"], "Tencent")
        finally:
            Path(path).unlink(missing_ok=True)

    def test_apply_json_rules_filters_by_close(self):
        matches = [
            {"code": "0700.HK", "close": 300, "s1_breakout": True},
            {"code": "0005.HK", "close": 40, "s1_breakout": True},
        ]
        rule_json = {
            "match": "all",
            "rules": [{"field": "close", "op": "gte", "value": 100}],
        }
        filtered = _apply_json_rules(matches, rule_json)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["code"], "0700.HK")

    def test_annotate_matched_conditions(self):
        matches = [{"code": "0700.HK", "close_vs_entry": True, "s1_breakout": False}]
        annotated = annotate_matched_conditions(matches, {"close_vs_entry", "s1_breakout"})
        self.assertEqual(annotated[0]["matched_conditions"], ["close_vs_entry"])

    def test_annotate_matched_conditions_with_kline(self):
        matches = [{"code": "0700.HK", "w_bottom": True, "m_top": False}]
        annotated = annotate_matched_conditions(matches, {"w_bottom", "m_top"})
        self.assertEqual(annotated[0]["matched_conditions"], ["w_bottom"])

    @patch("src.services.qualified_stock_scanner.scan_stocks")
    def test_run_qualified_scan_disabled(self, mock_scan_stocks):
        config = MagicMock(report_qualified_scan_enabled=False)
        payload = run_qualified_scan(config)
        self.assertFalse(payload["enabled"])
        mock_scan_stocks.assert_not_called()

    @patch("src.services.qualified_stock_scanner.scan_stocks")
    def test_run_qualified_scan_enabled(self, mock_scan_stocks):
        mock_scan_stocks.return_value = {
            "matches": [
                {
                    "code": "0700.HK",
                    "name": "騰訊控股",
                    "status": "ok",
                    "close_vs_entry": True,
                    "close": 300,
                    "entry20": 290,
                    "entry55": 280,
                }
            ],
            "no_price": [],
            "stats": {"tickers": 1, "max_workers": 1, "total_ms": 10},
            "skipped": False,
        }
        config = MagicMock(
            report_qualified_scan_enabled=True,
            report_qualified_scan_stock_list="HSI",
            report_qualified_scan_period="1y",
            report_qualified_scan_conditions="close_vs_entry",
            report_qualified_scan_rule_json="",
            report_qualified_scan_plugin="",
            report_qualified_scan_max_workers=4,
            report_qualified_scan_use_multi_source=True,
            report_qualified_scan_max_results=20,
            report_qualified_scan_check_trading_day=False,
        )
        payload = run_qualified_scan(config)
        self.assertTrue(payload["enabled"])
        self.assertEqual(len(payload["matches"]), 1)
        self.assertEqual(payload["matches"][0]["matched_conditions"], ["close_vs_entry"])
        mock_scan_stocks.assert_called_once()

    def test_format_qualified_scan_section(self):
        labels = get_report_labels("zh")
        section = format_qualified_scan_section(
            {
                "enabled": True,
                "matches": [
                    {
                        "code": "0700.HK",
                        "name": "騰訊控股",
                        "close": 300,
                        "entry20": 290,
                        "entry55": 280,
                        "kline_pattern_score": 6.0,
                        "kline_patterns": ["w_bottom", "bullish_engulfing"],
                        "matched_conditions": ["close_vs_entry"],
                    }
                ],
            },
            labels,
        )
        self.assertIn("技术筛选合格股", section)
        self.assertIn("0700.HK", section)
        self.assertIn("close_vs_entry", section)
        self.assertIn("w_bottom", section)
        self.assertIn("6.0", section)
        self.assertIn("tradingview.com/chart/?symbol=HKEX:0700", section)


if __name__ == "__main__":
    unittest.main()
