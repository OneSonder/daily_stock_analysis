# -*- coding: utf-8 -*-
"""Daily monitor classifier: uprising vs reversal, fewer continuation highs."""

from __future__ import annotations

from src.services.daily_monitor import (
    apply_monitor_to_scan_payload,
    classify_daily_monitor,
    format_index_regime_lines,
    format_monitor_list_sections,
    is_reversal_row,
    is_uprising_row,
    monitor_event_label,
)


def _row(**overrides):
    base = {
        "status": "ok",
        "code": "0700.HK",
        "name": "腾讯",
        "close": 400,
        "url": "https://finance.yahoo.com/quote/0700.HK",
        "s1_recent_close_breakout": False,
        "s2_recent_close_breakout": False,
        "s1_recent_high_breakout": False,
        "s2_recent_high_breakout": False,
        "s1_recent_close_timing": None,
        "s2_recent_close_timing": None,
        "s1_entry_allowed": True,
        "turtle_trend_ok": True,
        "volume_confirm": True,
        "volume_ratio": 1.4,
        "breakout_extension_n": 0.3,
        "s1_exit": False,
        "s2_exit": False,
        "close_vs_ma100": True,
        "avg_turnover_20": 8_000_000,
        "potential_score": 70,
        "n": 5.0,
        "stop_long_2n": 390.0,
        "atr_pct": 1.2,
        "s1_breakout": True,
        "s2_breakout": True,
    }
    base.update(overrides)
    return base


def test_uprising_requires_close_first_cross_not_high_only():
    high_only = _row(s1_recent_high_breakout=True, s2_recent_high_breakout=True)
    assert is_uprising_row(high_only) is False
    s2_close = _row(s2_recent_close_breakout=True, s2_recent_close_timing="today")
    assert is_uprising_row(s2_close) is True
    s1_only = _row(s1_recent_close_breakout=True, s1_entry_allowed=False)
    assert is_uprising_row(s1_only) is False
    s1_allowed = _row(s1_recent_close_breakout=True, s1_entry_allowed=True)
    assert is_uprising_row(s1_allowed) is True


def test_uprising_rejects_no_volume_late_extension_exit_and_missing_ma100():
    assert is_uprising_row(_row(s2_recent_close_breakout=True, volume_confirm=False)) is False
    assert is_uprising_row(_row(s2_recent_close_breakout=True, breakout_extension_n=1.5)) is False
    assert is_uprising_row(_row(s2_recent_close_breakout=True, s1_exit=True)) is False
    assert is_uprising_row(_row(s2_recent_close_breakout=True, close_vs_ma100=None)) is False
    assert is_uprising_row(_row(s2_recent_close_breakout=True, close_vs_ma100=False)) is False
    assert is_uprising_row(_row(s2_recent_close_breakout=True, turtle_trend_ok=False)) is False


def test_reversal_is_s1_close_while_trend_or_ma100_off():
    down = _row(
        s1_recent_close_breakout=True,
        turtle_trend_ok=False,
        close_vs_ma100=False,
    )
    assert is_reversal_row(down) is True
    still_trend = _row(s1_recent_close_breakout=True, turtle_trend_ok=True, close_vs_ma100=True)
    assert is_reversal_row(still_trend) is False
    below_ma = _row(s1_recent_close_breakout=True, turtle_trend_ok=True, close_vs_ma100=False)
    assert is_reversal_row(below_ma) is True
    no_vol = _row(s1_recent_close_breakout=True, turtle_trend_ok=False, volume_confirm=False)
    assert is_reversal_row(no_vol) is False


def test_classify_uprising_wins_over_reversal_and_caps():
    uprising = _row(
        code="0700.HK",
        s2_recent_close_breakout=True,
        s1_recent_close_breakout=True,
        turtle_trend_ok=True,
        close_vs_ma100=True,
        breakout_extension_n=0.2,
        potential_score=50,
    )
    reversal = _row(
        code="9988.HK",
        s1_recent_close_breakout=True,
        turtle_trend_ok=False,
        close_vs_ma100=False,
        s2_recent_close_breakout=False,
        potential_score=90,
    )
    continuation = _row(code="0005.HK", s1_breakout=True, s1_recent_close_breakout=False)
    late = _row(
        code="3690.HK",
        s2_recent_close_breakout=True,
        breakout_extension_n=2.0,
    )
    extras = [
        _row(
            code=f"{i:04d}.HK",
            s2_recent_close_breakout=True,
            breakout_extension_n=0.4 + i * 0.01,
            potential_score=10,
        )
        for i in range(1, 12)
    ]
    classified = classify_daily_monitor(
        [uprising, reversal, continuation, late, *extras],
        limit=3,
    )
    assert [r["code"] for r in classified["uprising"]] == ["0700.HK", "0001.HK", "0002.HK"]
    assert classified["uprising_total"] == 12
    assert [r["code"] for r in classified["reversal"]] == ["9988.HK"]
    assert "0005.HK" not in {r["code"] for r in classified["matches"]}
    assert "3690.HK" not in {r["code"] for r in classified["matches"]}
    assert classified["matches"][0]["monitor_bucket"] == "uprising"


def test_weak_index_suppresses_uprising_keeps_reversal():
    up = _row(s2_recent_close_breakout=True)
    rev = _row(
        code="1810.HK",
        s1_recent_close_breakout=True,
        turtle_trend_ok=False,
        close_vs_ma100=False,
        s2_recent_close_breakout=False,
    )
    classified = classify_daily_monitor([up, rev], index_trend_ok=False)
    assert classified["uprising"] == []
    assert classified["uprising_suppressed"] is True
    assert classified["uprising_total"] == 1
    assert [r["code"] for r in classified["reversal"]] == ["1810.HK"]


def test_missing_index_does_not_suppress():
    up = _row(s2_recent_close_breakout=True)
    classified = classify_daily_monitor([up], index_trend_ok=None)
    assert classified["uprising_suppressed"] is False
    assert len(classified["uprising"]) == 1


def test_sort_prefers_s2_then_smaller_extension_then_score():
    a = _row(code="A.HK", s1_recent_close_breakout=True, s2_recent_close_breakout=False, breakout_extension_n=0.1, potential_score=99)
    b = _row(code="B.HK", s2_recent_close_breakout=True, breakout_extension_n=0.8, potential_score=10)
    c = _row(code="C.HK", s2_recent_close_breakout=True, breakout_extension_n=0.2, potential_score=10)
    d = _row(code="D.HK", s2_recent_close_breakout=True, breakout_extension_n=0.2, potential_score=40)
    classified = classify_daily_monitor([a, b, c, d])
    assert [r["code"] for r in classified["uprising"]] == ["D.HK", "C.HK", "B.HK", "A.HK"]


def test_apply_monitor_and_report_sections():
    payload = {
        "results": [
            _row(s2_recent_close_breakout=True, s2_recent_close_timing="today"),
            _row(
                code="9988.HK",
                name="阿里",
                s1_recent_close_breakout=True,
                s1_recent_close_timing="previous",
                turtle_trend_ok=False,
                close_vs_ma100=False,
                s2_recent_close_breakout=False,
            ),
        ],
        "matches": [],
        "stats": {"tickers": 2},
        "skipped": False,
    }
    apply_monitor_to_scan_payload(
        payload,
        period="1y",
        limit=10,
        fetch_index=False,
        index_regime={
            "status": "ok",
            "turtle_trend_ok": True,
            "close_vs_ma100": True,
            "atr_pct": 1.1,
            "close": 26000,
        },
    )
    assert payload["monitor"] is True
    assert [r["code"] for r in payload["uprising"]] == ["0700.HK"]
    assert [r["code"] for r in payload["reversal"]] == ["9988.HK"]
    assert [r["code"] for r in payload["matches"]] == ["0700.HK", "9988.HK"]
    assert "S2 Close 今日首破" in monitor_event_label(payload["uprising"][0])

    text = "\n".join(
        format_index_regime_lines(payload["index_regime"])
        + format_monitor_list_sections(payload)
    )
    assert "恒生指数: 趋势通过" in text
    assert "## 趋势首破" in text
    assert "## 止跌转折" in text
    assert "S2 Close 今日首破" in text
    assert "| 档 |" not in text
    assert "| 分 |" not in text


def test_suppressed_uprising_line_in_report():
    payload = {
        "uprising": [],
        "reversal": [],
        "uprising_suppressed": True,
        "stats": {},
        "monitor": True,
    }
    text = "\n".join(format_monitor_list_sections(payload))
    assert "大盘趋势未过，今日不列趋势首破" in text
    assert "没有股票符合止跌转折条件" in text


def test_index_insufficient_banner():
    lines = format_index_regime_lines({"status": "empty", "message": "No data found"})
    assert any("恒指数据不足" in line for line in lines)
