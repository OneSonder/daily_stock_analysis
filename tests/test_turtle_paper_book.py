# -*- coding: utf-8 -*-
"""Turtle paper-book unit tests (no Yahoo)."""

from __future__ import annotations

import pandas as pd

from src.services.turtle_paper_book import simulate_turtle_book, unit_shares


def _hist(n_bars: int = 40, start: float = 100.0, step: float = 1.0) -> pd.DataFrame:
    idx = pd.date_range("2020-01-02", periods=n_bars, freq="B")
    closes = [start + i * step for i in range(n_bars)]
    return pd.DataFrame(
        {
            "Open": [c - 0.2 for c in closes],
            "High": [c + 3.0 for c in closes],
            "Low": [c - 0.5 for c in closes],
            "Close": closes,
        },
        index=idx,
    )


def test_unit_shares_is_one_percent_equity_over_n():
    assert unit_shares(1_000_000, 10.0) == 1000
    assert unit_shares(1_000_000, 0) == 0


def test_add_then_stop():
    hist = _hist(30, start=100.0, step=2.0)
    # Deep low after several adds
    hist.iloc[10, hist.columns.get_loc("Low")] = 50.0
    alerts = [
        {
            "code": "0700.HK",
            "bucket": "uprising",
            "signal_date": hist.index[0].strftime("%Y-%m-%d"),
            "n": 2.0,
            "s2_recent_close_breakout": True,
            "s1_recent_close_breakout": False,
            "s1_entry_allowed": True,
        }
    ]
    book = simulate_turtle_book(
        alerts,
        {"0700.HK": hist},
        equity=1_000_000,
        cost_bps=0.0,
        bucket="uprising",
    )
    assert book["n"] == 1
    trade = book["trades"][0]
    assert trade["units"] >= 2
    assert trade["exit_reason"] == "stop"
    assert book["max_units_seen"] >= 2


def test_skip_s1_when_last_was_winner():
    hist = _hist(20)
    alerts = [
        {
            "code": "0700.HK",
            "bucket": "uprising",
            "signal_date": hist.index[0].strftime("%Y-%m-%d"),
            "n": 2.0,
            "s2_recent_close_breakout": False,
            "s1_recent_close_breakout": True,
            "s1_entry_allowed": False,
        }
    ]
    book = simulate_turtle_book(alerts, {"0700.HK": hist}, bucket="uprising")
    assert book["n"] == 0
    assert book["skipped_s1_winner"] == 1


def test_unit_cap_skips_extra_names():
    h1 = _hist(15, start=100)
    h2 = _hist(15, start=80)
    day = h1.index[0].strftime("%Y-%m-%d")
    alerts = [
        {
            "code": "0001.HK",
            "bucket": "uprising",
            "signal_date": day,
            "n": 1.0,
            "s2_recent_close_breakout": True,
            "s1_entry_allowed": True,
        },
        {
            "code": "0002.HK",
            "bucket": "uprising",
            "signal_date": day,
            "n": 1.0,
            "s2_recent_close_breakout": True,
            "s1_entry_allowed": True,
        },
    ]
    book = simulate_turtle_book(
        alerts,
        {"0001.HK": h1, "0002.HK": h2},
        equity=1_000_000,
        max_units_total=1,
        max_units_name=1,
        bucket="uprising",
    )
    assert book["n"] == 1
    assert book["skipped_cap"] >= 1
