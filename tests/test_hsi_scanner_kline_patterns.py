import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.services.hsi_scanner import compute_signals_full


def _build_base_df(length: int = 80, start: float = 100.0, step: float = 0.05) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=length, freq="D")
    close = pd.Series([start + (step * i) for i in range(length)], index=idx)
    open_ = close - 0.2
    high = np.maximum(open_, close) + 1.0
    low = np.minimum(open_, close) - 1.0
    return pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close}, index=idx)


def _rebuild_from_close(df: pd.DataFrame) -> None:
    close = df["Close"]
    open_ = close - 0.2
    df["Open"] = open_
    df["High"] = np.maximum(open_, close) + 1.0
    df["Low"] = np.minimum(open_, close) - 1.0


def _set_last_row(df: pd.DataFrame, *, offset: int, open_v: float, high_v: float, low_v: float, close_v: float) -> None:
    idx = df.index[offset]
    df.at[idx, "Open"] = open_v
    df.at[idx, "High"] = high_v
    df.at[idx, "Low"] = low_v
    df.at[idx, "Close"] = close_v


class TestHSIScannerKlinePatterns(unittest.TestCase):
    def test_detects_w_bottom(self):
        df = _build_base_df()
        close_tail = [112, 109, 106, 104, 106, 109, 112, 110, 107, 104.5, 107, 111, 114, 116, 117, 118, 119, 120]
        for i, value in enumerate(close_tail):
            df.iloc[-len(close_tail) + i, df.columns.get_loc("Close")] = value
        _rebuild_from_close(df)

        out = compute_signals_full(df)
        self.assertTrue(out["w_bottom"])
        self.assertTrue(out["double_bottom"])
        self.assertIn("w_bottom", out["kline_patterns"])
        self.assertTrue(out["kline_bullish"])

    def test_detects_m_top(self):
        df = _build_base_df(start=120.0, step=-0.04)
        close_tail = [108, 111, 114, 117, 114, 111, 108, 110, 114, 117.2, 114, 110, 106, 103, 101, 100, 99, 98]
        for i, value in enumerate(close_tail):
            df.iloc[-len(close_tail) + i, df.columns.get_loc("Close")] = value
        _rebuild_from_close(df)

        out = compute_signals_full(df)
        self.assertTrue(out["m_top"])
        self.assertTrue(out["double_top"])
        self.assertIn("m_top", out["kline_patterns"])
        self.assertTrue(out["kline_bearish"])

    def test_detects_bullish_engulfing(self):
        df = _build_base_df()
        _set_last_row(df, offset=-2, open_v=110.0, high_v=111.0, low_v=107.0, close_v=108.0)
        _set_last_row(df, offset=-1, open_v=107.0, high_v=113.0, low_v=106.0, close_v=112.0)

        out = compute_signals_full(df)
        self.assertTrue(out["bullish_engulfing"])
        self.assertIn("bullish_engulfing", out["kline_patterns"])

    def test_detects_gap_up(self):
        df = _build_base_df()
        _set_last_row(df, offset=-2, open_v=100.0, high_v=101.5, low_v=99.5, close_v=101.0)
        _set_last_row(df, offset=-1, open_v=103.0, high_v=104.5, low_v=102.5, close_v=104.0)

        out = compute_signals_full(df)
        self.assertTrue(out["gap_up"])
        self.assertIn("gap_up", out["kline_patterns"])

    def test_detects_doji(self):
        df = _build_base_df()
        _set_last_row(df, offset=-2, open_v=104.5, high_v=106.0, low_v=103.5, close_v=105.2)
        _set_last_row(df, offset=-1, open_v=105.0, high_v=106.0, low_v=104.0, close_v=105.02)

        out = compute_signals_full(df)
        self.assertTrue(out["doji"])
        self.assertIn("doji", out["kline_patterns"])

    def test_no_pattern_case(self):
        df = _build_base_df(length=90, start=100.0, step=0.03)
        _set_last_row(df, offset=-2, open_v=102.2, high_v=103.0, low_v=101.8, close_v=102.5)
        _set_last_row(df, offset=-1, open_v=102.7, high_v=103.4, low_v=102.2, close_v=103.0)

        out = compute_signals_full(df)
        self.assertEqual(out["kline_patterns"], [])
        self.assertEqual(out["kline_pattern_score"], 0.0)
        self.assertFalse(out["kline_bullish"])
        self.assertFalse(out["kline_bearish"])

    def test_attaches_rsi_macd_and_mas(self):
        df = _build_base_df(length=90, start=100.0, step=0.2)
        df["Volume"] = 1_000_000
        out = compute_signals_full(df)
        self.assertIsNotNone(out.get("ma20"))
        self.assertIsNotNone(out.get("rsi_12"))
        self.assertIsNotNone(out.get("macd_dif"))
        self.assertTrue(np.isfinite(out["ma20"]))
        self.assertTrue(np.isfinite(out["rsi_12"]))
        self.assertTrue(np.isfinite(out["macd_dif"]))
        self.assertIn("kline_patterns", out)
        self.assertIn("rsi_macd_score", out)
        self.assertTrue(np.isfinite(out["rsi_macd_score"]))

    def test_rsi_macd_indicator_score_weights(self):
        from src.services.hsi_scanner import _rsi_macd_indicator_score

        bullish = _rsi_macd_indicator_score({"macd_status": "金叉", "rsi_status": "强势买入"})
        bearish = _rsi_macd_indicator_score({"macd_status": "死叉", "rsi_status": "超买"})
        self.assertGreater(bullish, 0)
        self.assertLess(bearish, 0)
        self.assertEqual(_rsi_macd_indicator_score({}), 0.0)
        self.assertEqual(_rsi_macd_indicator_score({"macd_status": "零轴上金叉", "rsi_status": "超卖"}), 12.0)


if __name__ == "__main__":
    unittest.main()
