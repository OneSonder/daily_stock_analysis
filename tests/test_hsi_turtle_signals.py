# -*- coding: utf-8 -*-
"""Tests for Turtle-inspired HSI S1/S2 signal helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.services.hsi_scanner import (
    _adaptive_turtle_trend_ok,
    _compute_n,
    _s1_last_breakout_was_winner,
    _turtle_score_delta,
    compute_signals_full,
    format_scan_report,
)


def _trending_df(n_bars: int = 80, start: float = 100.0, step: float = 0.8) -> pd.DataFrame:
    """Synthetic uptrend OHLCV suitable for Donchian + ATR."""
    closes = start + np.arange(n_bars) * step
    highs = closes + 1.5
    lows = closes - 1.2
    opens = closes - 0.3
    idx = pd.date_range("2025-01-01", periods=n_bars, freq="B")
    return pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": 1e6},
        index=idx,
    )


def test_compute_n_positive_on_trend():
    df = _trending_df(80)
    n = _compute_n(df, window=20)
    assert n is not None
    assert n > 0


def test_adaptive_trend_short_history_uses_ma20_ma55():
    df = _trending_df(80)
    ok, rule = _adaptive_turtle_trend_ok(df)
    assert rule == "ma20_ma55"
    assert ok is True


def test_adaptive_trend_long_history_uses_ma50_ma300():
    df = _trending_df(320)
    ok, rule = _adaptive_turtle_trend_ok(df)
    assert rule == "ma50_ma300"
    assert ok is True


def test_s1_last_breakout_was_winner_detects_prior_win():
    # Flat base → one S1 breakout → next bar hits winner target without a new breakout
    # → then exit via 10d low so the trade is completed as a winner.
    bars = 70
    closes = np.full(bars, 100.0)
    highs = np.full(bars, 100.5)
    lows = np.full(bars, 99.5)
    for i in range(0, 30):
        closes[i] = 100.0
        highs[i] = 100.5
        lows[i] = 99.5
    # Breakout at 30 (prior 20d high = 100.5)
    highs[30] = 102.0
    closes[30] = 101.5
    lows[30] = 100.8
    # Hit winner target without exceeding entry20 (no second breakout)
    # entry=100.5, N=2 → target=101.5; keep high <= 102.0
    highs[31] = 101.9
    closes[31] = 101.6
    lows[31] = 101.0
    # Pull back to complete via 10d exit
    for i in range(32, 50):
        closes[i] = 101.0 - (i - 31) * 0.5
        highs[i] = closes[i] + 0.2
        lows[i] = closes[i] - 0.9
    for i in range(50, bars):
        closes[i] = 90.0
        highs[i] = 90.3
        lows[i] = 89.7
    idx = pd.date_range("2025-01-01", periods=bars, freq="B")
    df = pd.DataFrame(
        {"Open": closes, "High": highs, "Low": lows, "Close": closes, "Volume": 1e6},
        index=idx,
    )
    assert _s1_last_breakout_was_winner(df, n_value=2.0) is True


def test_turtle_score_delta_env_toggles(monkeypatch):
    monkeypatch.setenv("HSI_TURTLE_TREND_FILTER", "true")
    monkeypatch.setenv("HSI_TURTLE_S1_SKIP_WINNER", "true")
    with_trend = _turtle_score_delta(
        s1_breakout=True,
        s2_breakout=True,
        turtle_trend_ok=True,
        s1_last_was_winner=False,
    )
    against = _turtle_score_delta(
        s1_breakout=True,
        s2_breakout=False,
        turtle_trend_ok=False,
        s1_last_was_winner=True,
    )
    assert with_trend > against

    monkeypatch.setenv("HSI_TURTLE_TREND_FILTER", "false")
    monkeypatch.setenv("HSI_TURTLE_S1_SKIP_WINNER", "false")
    disabled = _turtle_score_delta(
        s1_breakout=True,
        s2_breakout=True,
        turtle_trend_ok=False,
        s1_last_was_winner=True,
    )
    assert disabled == 0.0


def test_compute_signals_full_includes_turtle_fields():
    df = _trending_df(90)
    # Force a breakout on last bar
    df.iloc[-1, df.columns.get_loc("High")] = float(df["High"].iloc[-21:-1].max()) + 5.0
    df.iloc[-1, df.columns.get_loc("Close")] = float(df["Close"].iloc[-2]) + 4.0
    out = compute_signals_full(df)
    assert out.get("n") is not None and out["n"] > 0
    assert out.get("stop_long_2n") is not None
    assert "turtle_trend_ok" in out
    assert "turtle_trend_rule" in out
    assert "s1_entry_allowed" in out
    assert "turtle_score" in out
    assert "s1_breakout" in out


def test_format_scan_report_includes_turtle_chinese_lines():
    payload = {
        "matches": [
            {
                "code": "0700.HK",
                "name": "腾讯",
                "close": 400,
                "url": "",
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
                "ma20": 395,
                "rsi_12": 55,
                "macd_status": "多头",
                "kline_patterns": [],
            }
        ],
        "no_price": [],
        "stats": {"tickers": 1, "total_ms": 1},
        "skipped": False,
    }
    text = format_scan_report(payload)
    assert "海龟: N=5.0" in text
    assert "2N止损参考=390.0" in text
    assert "趋势过滤: 通过" in text
    assert "S1允许开仓: 是" in text
