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
from src.services.hsi_scanner import HSI_STOCKS
from src.services.qualified_stock_scanner import (
    _apply_json_rules,
    _to_yahoo_code,
    annotate_matched_conditions,
    format_qualified_scan_section,
    resolve_universe,
    run_qualified_scan,
)


class TestQualifiedStockScanner(unittest.TestCase):
    def test_to_yahoo_code_from_manager_format(self):
        self.assertEqual(_to_yahoo_code("HK00700"), "0700.HK")

    def test_resolve_universe_hsi_token(self):
        stocks, label = resolve_universe("HSI")
        self.assertEqual(label, "hsi")
        self.assertEqual(len(stocks), len(HSI_STOCKS))

    def test_resolve_universe_custom_codes(self):
        stocks, label = resolve_universe("HK00700,9988.HK")
        self.assertEqual(label, "custom")
        self.assertEqual(stocks[0]["code"], "0700.HK")
        self.assertEqual(stocks[1]["code"], "9988.HK")

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
                        "matched_conditions": ["close_vs_entry"],
                    }
                ],
            },
            labels,
        )
        self.assertIn("技术筛选合格股", section)
        self.assertIn("0700.HK", section)
        self.assertIn("close_vs_entry", section)


if __name__ == "__main__":
    unittest.main()
