# -*- coding: utf-8 -*-
"""HSI daily-monitor simulator: point-in-time replay, no Yahoo in tests."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import pytest

from src.services.daily_monitor import INDEX_CODE, is_uprising_row
from src.services.hsi_scanner import compute_signals_full, evaluate_ticker_from_history
from src.services.monitor_simulator import (
    RESEARCH_DISCLAIMER,
    format_sim_report,
    forward_excursions,
    history_through,
    replay_monitor,
    run_hsi_monitor_simulation,
    simulate_paper_trade,
)
from src.services.ohlcv_cache import load_latest_cached_history, save_cached_history


def _frame(closes, highs=None, lows=None, opens=None, volumes=None, start="2020-01-02") -> pd.DataFrame:
    closes = np.asarray(closes, dtype=float)
    n = len(closes)
    highs = closes + 0.4 if highs is None else np.asarray(highs, dtype=float)
    lows = closes - 0.4 if lows is None else np.asarray(lows, dtype=float)
    opens = closes - 0.1 if opens is None else np.asarray(opens, dtype=float)
    volumes = np.full(n, 1_000_000.0) if volumes is None else np.asarray(volumes, dtype=float)
    idx = pd.date_range(start, periods=n, freq="B")
    return pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": volumes},
        index=idx,
    )


def _trending(n_bars: int = 160, start: float = 100.0, step: float = 0.4) -> pd.DataFrame:
    closes = start + np.arange(n_bars) * step
    return _frame(closes, highs=closes + 1.2, lows=closes - 0.8)


def _pullback_then_close_breakout(n_bars: int = 160, breakout_i: int = 115) -> pd.DataFrame:
    closes = np.zeros(n_bars)
    highs = np.zeros(n_bars)
    lows = np.zeros(n_bars)
    volumes = np.full(n_bars, 1_000_000.0)
    pullback_start = 100
    for i in range(pullback_start):
        closes[i] = 100.0 + i * 0.4
        highs[i] = closes[i] + 0.3
        lows[i] = closes[i] - 0.3
    peak_high = float(highs[pullback_start - 1])
    for i in range(pullback_start, breakout_i):
        closes[i] = closes[pullback_start - 1] - (i - pullback_start + 1) * 0.08
        highs[i] = min(closes[i] + 0.2, peak_high - 0.02)
        lows[i] = closes[i] - 0.3
    closes[breakout_i] = peak_high + 0.25
    highs[breakout_i] = closes[breakout_i] + 0.05
    lows[breakout_i] = closes[breakout_i] - 0.2
    volumes[breakout_i] = 3_000_000.0
    for i in range(breakout_i + 1, n_bars):
        closes[i] = closes[breakout_i] + (i - breakout_i) * 0.05
        highs[i] = closes[i] + 0.15
        lows[i] = closes[i] - 0.15
    return _frame(closes, highs=highs, lows=lows, volumes=volumes)


def _downtrend(n_bars: int = 160) -> pd.DataFrame:
    return _trending(n_bars, start=200.0, step=-0.5)


def _uprising_stub(code: str, name: str, **overrides) -> Dict[str, Any]:
    row = {
        "code": code,
        "name": name,
        "status": "ok",
        "s2_recent_close_breakout": True,
        "s1_recent_close_breakout": False,
        "s1_entry_allowed": True,
        "turtle_trend_ok": True,
        "volume_confirm": True,
        "breakout_extension_n": 0.2,
        "s1_exit": False,
        "s2_exit": False,
        "close_vs_ma100": True,
        "potential_score": 70,
        "n": 2.0,
        "close": 100.0,
        "s2_recent_close_timing": "today",
    }
    row.update(overrides)
    return row


def _quiet_stub(code: str, name: str, hist: pd.DataFrame) -> Dict[str, Any]:
    return {
        "code": code,
        "name": name,
        "status": "ok",
        "s2_recent_close_breakout": False,
        "s1_recent_close_breakout": False,
        "s1_entry_allowed": False,
        "turtle_trend_ok": True,
        "volume_confirm": True,
        "breakout_extension_n": 0.0,
        "s1_exit": False,
        "s2_exit": False,
        "close_vs_ma100": True,
        "potential_score": 10,
        "n": 2.0,
        "close": float(hist["Close"].iloc[-1]),
    }


def test_evaluate_ticker_from_history_keeps_volume_confirm():
    df = _pullback_then_close_breakout()
    row = evaluate_ticker_from_history("0700.HK", "Tencent", df.iloc[:116])
    assert row["status"] == "ok"
    assert row["volume_confirm"] is True
    assert is_uprising_row(row) is True


def test_breakout_frame_is_uprising_on_signal_bar():
    df = _pullback_then_close_breakout()
    out = compute_signals_full(df.iloc[:116])
    assert out["s2_recent_close_breakout"] or out["s1_recent_close_breakout"]
    assert is_uprising_row({"status": "ok", **out}) is True


def test_continuation_highs_are_not_uprising_after_warmup():
    df = _trending(160)
    out = compute_signals_full(df.iloc[:130])
    assert out.get("s1_recent_close_breakout") is False
    assert out.get("s2_recent_close_breakout") is False
    assert is_uprising_row({"status": "ok", **out}) is False


def test_paper_2n_stop_hits_before_time_stop():
    closes = [100.0] * 10
    highs = [101.0] * 10
    lows = [99.0] * 10
    opens = [100.0] * 10
    lows[2] = 94.0
    hist = _frame(closes, highs=highs, lows=lows, opens=opens)
    trade = simulate_paper_trade(hist, hist.index[0], n_value=2.0, horizon=8, cost_bps=0.0)
    assert trade is not None
    assert trade["exit_reason"] == "stop"
    assert trade["exit"] == pytest.approx(trade["entry"] - 4.0)
    assert pd.Timestamp(trade["exit_date"]) == pd.Timestamp(hist.index[2])


def test_forward_excursions_use_bars_after_signal_only():
    closes = [10.0, 10.0, 12.0, 9.0, 11.0]
    highs = [10.5, 10.5, 15.0, 12.0, 11.5]
    lows = [9.5, 9.5, 11.0, 8.0, 10.0]
    hist = _frame(closes, highs=highs, lows=lows)
    fwd = forward_excursions(hist, hist.index[1], signal_close=10.0, n_value=2.0, horizon=3)
    assert fwd["mfe"] == pytest.approx(5.0)
    assert fwd["mae"] == pytest.approx(2.0)
    assert fwd["mae_n"] == pytest.approx(1.0)


def test_replay_ignores_future_bars_for_signals():
    hist = _trending(130)
    breakout_date = hist.index[120]
    seen_ends: List[pd.Timestamp] = []

    def evaluate(code: str, name: str, sliced: pd.DataFrame) -> Dict[str, Any]:
        seen_ends.append(pd.Timestamp(sliced.index[-1]))
        last = pd.Timestamp(sliced.index[-1])
        close = float(sliced["Close"].iloc[-1])
        if code == INDEX_CODE:
            return _quiet_stub(code, name, sliced)
        if code == "0700.HK" and last == pd.Timestamp(breakout_date):
            return _uprising_stub(code, name, close=close)
        return _quiet_stub(code, name, sliced)

    stocks = [
        {"code": "0700.HK", "name": "Tencent"},
        {"code": "0005.HK", "name": "HSBC"},
    ]
    result = replay_monitor(
        {INDEX_CODE: hist, "0700.HK": hist, "0005.HK": hist},
        stocks,
        horizon=5,
        warmup=100,
        limit=10,
        evaluate_fn=evaluate,
    )
    assert all(end <= hist.index[124] for end in seen_ends)
    alert_dates = {a["signal_date"] for a in result["alerts"] if a["code"] == "0700.HK"}
    assert alert_dates == {pd.Timestamp(breakout_date).strftime("%Y-%m-%d")}


def test_replay_dedups_two_bar_flag():
    hist = _trending(130)

    def evaluate(code: str, name: str, sliced: pd.DataFrame) -> Dict[str, Any]:
        last_i = len(sliced) - 1
        close = float(sliced["Close"].iloc[-1])
        if code == INDEX_CODE:
            return _quiet_stub(code, name, sliced)
        if code == "0700.HK" and last_i in (118, 119):
            timing = "today" if last_i == 118 else "previous"
            return _uprising_stub(code, name, close=close, s2_recent_close_timing=timing)
        return _quiet_stub(code, name, sliced)

    result = replay_monitor(
        {INDEX_CODE: hist, "0700.HK": hist, "0005.HK": hist},
        [{"code": "0700.HK", "name": "Tencent"}, {"code": "0005.HK", "name": "HSBC"}],
        horizon=5,
        warmup=100,
        evaluate_fn=evaluate,
    )
    dates = [a["signal_date"] for a in result["alerts"] if a["code"] == "0700.HK"]
    assert len(dates) == 1


def test_weak_index_suppresses_uprising():
    hist = _trending(130)
    down = _downtrend(130)

    def evaluate(code: str, name: str, sliced: pd.DataFrame) -> Dict[str, Any]:
        close = float(sliced["Close"].iloc[-1])
        if code == INDEX_CODE:
            quiet = _quiet_stub(code, name, sliced)
            quiet["turtle_trend_ok"] = False
            return quiet
        if code == "0700.HK":
            return _uprising_stub(code, name, close=close)
        return _quiet_stub(code, name, sliced)

    result = replay_monitor(
        {INDEX_CODE: down, "0700.HK": hist, "0005.HK": hist},
        [{"code": "0700.HK", "name": "Tencent"}, {"code": "0005.HK", "name": "HSBC"}],
        horizon=5,
        warmup=100,
        evaluate_fn=evaluate,
    )
    assert result["uprising_suppressed_days"] == result["days_replayed"]
    assert all(a["bucket"] != "uprising" for a in result["alerts"])


def test_live_evaluate_first_cross_alerts_once_continuation_does_not():
    breakout = _pullback_then_close_breakout()
    continuation = _trending(160)
    index = _trending(160, start=200.0, step=0.3)
    quiet = _trending(160, start=50.0, step=0.05)
    stocks = [
        {"code": "0700.HK", "name": "Tencent"},
        {"code": "0005.HK", "name": "HSBC"},
    ]
    first = replay_monitor(
        {INDEX_CODE: index, "0700.HK": breakout, "0005.HK": quiet},
        stocks,
        horizon=5,
        warmup=100,
        limit=10,
    )
    codes = {a["code"] for a in first["alerts"] if a["bucket"] == "uprising"}
    assert "0700.HK" in codes
    cont = replay_monitor(
        {INDEX_CODE: index, "0700.HK": continuation, "0005.HK": quiet},
        stocks,
        horizon=5,
        warmup=100,
        limit=10,
    )
    assert all(a["code"] != "0700.HK" or a["bucket"] != "uprising" for a in cont["alerts"])


def test_history_through_drops_later_bars():
    hist = _trending(10)
    sliced = history_through(hist, hist.index[4])
    assert sliced.index.max() == hist.index[4]
    assert len(sliced) == 5


def test_load_latest_cache_uses_yesterday_when_today_missing(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("REPORT_QUALIFIED_SCAN_CACHE_ENABLED", "true")
    monkeypatch.setenv("REPORT_QUALIFIED_SCAN_CACHE_DIR", str(tmp_path))
    frame = _trending(30)
    yesterday = date.today() - timedelta(days=1)
    save_cached_history("0700.HK", "5y", frame, as_of=yesterday)
    loaded = load_latest_cached_history("0700.HK", "5y")
    assert loaded is not None
    pd.testing.assert_frame_equal(loaded, frame)


def test_report_is_labeled_research_not_forecast():
    hist = _trending(120)
    result = replay_monitor(
        {INDEX_CODE: hist, "0700.HK": hist},
        [{"code": "0700.HK", "name": "Tencent"}],
        horizon=5,
        warmup=100,
        evaluate_fn=lambda code, name, sliced: _quiet_stub(code, name, sliced),
    )
    text = format_sim_report(
        result,
        period="5y",
        horizon=5,
        warmup=100,
        limit=10,
        max_extension_n=1.0,
        cost_bps=20.0,
        universe_size=1,
    )
    assert RESEARCH_DISCLAIMER in text
    assert "不是涨跌预测" in text


def test_run_simulation_accepts_injected_histories():
    hist = _trending(120)
    result = run_hsi_monitor_simulation(
        period="2y",
        horizon=5,
        warmup=100,
        stocks=[{"code": "0700.HK", "name": "Tencent"}],
        histories={INDEX_CODE: hist, "0700.HK": hist},
        evaluate_fn=lambda code, name, sliced: _quiet_stub(code, name, sliced),
        no_network=True,
    )
    assert "report" in result
    assert result["days_replayed"] > 0
