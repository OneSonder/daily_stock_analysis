# -*- coding: utf-8 -*-
"""Tests for batched Yahoo history fetching and same-day OHLCV caching."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.services.hsi_scanner import (
    _split_yfinance_batch,
    fetch_history_batch_yfinance,
    scan_stocks,
)
from src.services.ohlcv_cache import load_cached_history, save_cached_history


def _history_frame(*, breakout: bool = False) -> pd.DataFrame:
    index = pd.date_range("2026-01-01", periods=70, freq="B")
    highs = [float(100 + idx) for idx in range(70)]
    if breakout:
        highs[-1] = 500.0
    return pd.DataFrame(
        {
            "Open": [value - 1 for value in highs],
            "High": highs,
            "Low": [value - 2 for value in highs],
            "Close": [value - 0.5 for value in highs],
        },
        index=index,
    )


class TestHsiOhlcvCache(unittest.TestCase):
    def test_split_yfinance_batch_supports_ticker_first_columns(self):
        first = _history_frame()
        second = _history_frame(breakout=True)
        raw = pd.concat({"0001.HK": first, "0700.HK": second}, axis=1)

        result = _split_yfinance_batch(raw, ["0001.HK", "0700.HK"])

        self.assertEqual(set(result), {"0001.HK", "0700.HK"})
        self.assertEqual(list(result["0001.HK"].columns), ["Open", "High", "Low", "Close"])

    @patch("yfinance.download")
    def test_fetch_history_batch_uses_one_download(self, mock_download):
        mock_download.return_value = _history_frame()

        result = fetch_history_batch_yfinance(["0700.HK"], "3mo")

        self.assertIn("0700.HK", result)
        mock_download.assert_called_once()
        self.assertEqual(mock_download.call_args.kwargs["tickers"], ["0700.HK"])
        self.assertFalse(mock_download.call_args.kwargs["threads"])

    def test_same_day_cache_round_trip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(
                os.environ,
                {
                    "REPORT_QUALIFIED_SCAN_CACHE_ENABLED": "true",
                    "REPORT_QUALIFIED_SCAN_CACHE_DIR": temp_dir,
                },
            ):
                frame = _history_frame()
                save_cached_history("0700.HK", "3mo", frame)

                cached = load_cached_history("0700.HK", "3mo")

        self.assertIsNotNone(cached)
        pd.testing.assert_frame_equal(cached, frame)

    @patch("src.services.hsi_scanner.fetch_history_batch_yfinance")
    def test_scan_cache_hit_skips_batch_download(self, mock_batch):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(
                os.environ,
                {
                    "REPORT_QUALIFIED_SCAN_CACHE_ENABLED": "true",
                    "REPORT_QUALIFIED_SCAN_CACHE_DIR": temp_dir,
                },
            ):
                save_cached_history("0700.HK", "3mo", _history_frame(breakout=True))

                payload = scan_stocks(
                    [{"code": "0700.HK", "name": "Tencent"}],
                    period="3mo",
                    conditions="s1_breakout,s2_breakout",
                    use_multi_source=False,
                )

        mock_batch.assert_not_called()
        self.assertEqual(payload["stats"]["cache_hits"], 1)
        self.assertEqual(payload["stats"]["batch_downloaded"], 0)
        self.assertEqual(payload["matches"][0]["code"], "0700.HK")

    @patch("src.services.hsi_scanner.fetch_history_batch_yfinance")
    def test_scan_uses_batch_frame_for_signals(self, mock_batch):
        mock_batch.return_value = {"0700.HK": _history_frame(breakout=True)}
        with patch.dict(
            os.environ,
            {"REPORT_QUALIFIED_SCAN_CACHE_ENABLED": "false"},
        ):
            payload = scan_stocks(
                [{"code": "0700.HK", "name": "Tencent"}],
                period="3mo",
                conditions="s1_breakout,s2_breakout",
                use_multi_source=False,
            )

        mock_batch.assert_called_once_with(["0700.HK"], "3mo")
        self.assertEqual(payload["stats"]["batch_downloaded"], 1)
        self.assertEqual(payload["matches"][0]["code"], "0700.HK")


if __name__ == "__main__":
    unittest.main()
