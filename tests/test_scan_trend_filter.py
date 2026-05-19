# -*- coding: utf-8 -*-
"""Tests for scripts/scan_trend_filter.py (HSI universe + enum filters)."""

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import sys

from scripts.scan_trend_filter import (
    HSI_LIST_TOKEN,
    ScanTicker,
    _analyzer_types,
    _load_hsi_from_json,
    _load_hsi_universe,
    _parse_enum_filters,
    _passes_filters,
    _resolve_universe,
    scan_and_filter,
)
from src.services.hsi_scanner import HSI_STOCKS

def _enum_types():
    return _analyzer_types()


class TestHsiUniverseCore(unittest.TestCase):
    """No stock_analyzer / config — runs on Python 3.8+."""

    def test_builtin_hsi_count_matches_scanner(self):
        tickers = _load_hsi_universe()
        self.assertEqual(len(tickers), len(HSI_STOCKS))

    def test_hk_code_normalization(self):
        tickers = _load_hsi_universe()
        tencent = next(t for t in tickers if t.display_code == "0700.HK")
        self.assertEqual(tencent.fetch_code, "HK00700")
        self.assertEqual(tencent.name, "騰訊控股")

    def test_resolve_stocks_hsi_token(self):
        tickers, label = _resolve_universe(cli_stocks=HSI_LIST_TOKEN, use_hsi=False, hsi_json=None)
        self.assertEqual(label, "hsi")
        self.assertEqual(len(tickers), len(HSI_STOCKS))


@unittest.skipUnless(sys.version_info >= (3, 10), "requires Python 3.10+")
class TestHsiUniverse(unittest.TestCase):
    def test_load_hsi_json_tmp(self):
        payload = [{"code": "0700.HK", "name": "Tencent"}, {"code": "0005.HK", "name": "HSBC"}]
        path = Path(self._testMethodName + "_hsi.json")
        try:
            path.write_text(json.dumps(payload), encoding="utf-8")
            tickers = _load_hsi_from_json(path)
            self.assertEqual(len(tickers), 2)
            self.assertEqual(tickers[0].fetch_code, "HK00700")
        finally:
            path.unlink(missing_ok=True)

    def test_resolve_universe_hsi_flag(self):
        tickers, label = _resolve_universe(cli_stocks=None, use_hsi=True, hsi_json=None)
        self.assertEqual(label, "hsi")
        self.assertGreater(len(tickers), 80)


@unittest.skipUnless(sys.version_info >= (3, 10), "requires Python 3.10+")
class TestEnumFilters(unittest.TestCase):
    def test_parse_buy_signal_names_and_values(self):
        BuySignal = _enum_types()["BuySignal"]
        wanted = _parse_enum_filters("BUY,买入", BuySignal)
        self.assertIn(BuySignal.BUY, wanted)

    def test_passes_filters_min_score_and_buy(self):
        BuySignal = _enum_types()["BuySignal"]
        TrendStatus = _enum_types()["TrendStatus"]
        row = {
            "status": "ok",
            "signal_score": 65,
            "buy_signal": BuySignal.BUY.value,
            "trend_status": TrendStatus.BULL.value,
            "volume_status": "量能正常",
            "macd_status": "金叉",
            "rsi_status": "中性",
        }
        self.assertTrue(
            _passes_filters(
                row,
                buy_wanted={BuySignal.BUY},
                min_score=60,
                trend_wanted=None,
                volume_wanted=None,
                macd_wanted=None,
                rsi_wanted=None,
                max_score=None,
            )
        )


@unittest.skipUnless(sys.version_info >= (3, 10), "requires Python 3.10+")
class TestScanAndFilterMocked(unittest.TestCase):
    @patch("scripts.scan_trend_filter._analyze_one")
    def test_scan_returns_matches(self, mock_analyze):
        BuySignal = _enum_types()["BuySignal"]
        TrendStatus = _enum_types()["TrendStatus"]
        mock_analyze.side_effect = [
            {
                "code": "0700.HK",
                "name": "騰訊控股",
                "status": "ok",
                "buy_signal": BuySignal.BUY.value,
                "signal_score": 70,
                "trend_status": TrendStatus.BULL.value,
                "volume_status": "量能正常",
                "macd_status": "金叉",
                "rsi_status": "中性",
            },
            {
                "code": "0005.HK",
                "name": "匯豐控股",
                "status": "ok",
                "buy_signal": BuySignal.WAIT.value,
                "signal_score": 40,
                "trend_status": TrendStatus.CONSOLIDATION.value,
                "volume_status": "量能正常",
                "macd_status": "多头",
                "rsi_status": "中性",
            },
        ]
        tickers = [
            ScanTicker("0700.HK", "HK00700", "騰訊控股"),
            ScanTicker("0005.HK", "HK00005", "匯豐控股"),
        ]
        payload = scan_and_filter(
            tickers,
            max_workers=2,
            buy_wanted={BuySignal.BUY},
            min_score=60,
        )
        self.assertEqual(payload["scanned"], 2)
        self.assertEqual(len(payload["matches"]), 1)
        self.assertEqual(payload["matches"][0]["code"], "0700.HK")


if __name__ == "__main__":
    unittest.main()
