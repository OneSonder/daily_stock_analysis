# -*- coding: utf-8 -*-
"""Phase 1 candidate screen: universe, close-first S1/S2, floors, caps, schedule."""

from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from src.core.trading_calendar import get_effective_trading_date
from src.services.candidate_screen import (
    CandidateScreenDataError,
    apply_display_caps,
    correlation_profile,
    display_cap_block_reason,
    format_candidate_report,
    is_forbidden_listing,
    load_daily_universe,
    measure_liquidity,
    passes_official_floor,
    run_candidate_screen,
    select_candidates,
    validate_universe,
)
from src.services.candidate_screen_policy import (
    CAP_LOOSE_GROUP,
    CAP_ONE_DIRECTION,
    CAP_SINGLE_MARKET,
    CAP_TIGHT_GROUP,
    HK_MIN_AVG_TURNOVER_HKD,
    HK_MIN_PRICE_HKD,
    HK_SCREEN_CRON_UTC,
    US_MIN_AVG_TURNOVER_USD,
    US_MIN_PRICE_USD,
    US_SCREEN_CRON_UTC,
)
from src.services.daily_monitor import is_uprising_row
from src.services.hk_stock_scanner import DEFAULT_MIN_AVG_TURNOVER, DEFAULT_MIN_PRICE
from src.services.hsi_scanner import HSI_STOCKS, compute_signals_full
from src.services.stock_universes import US_TOP_STOCKS, load_hk_all_stocks

_AS_OF = date(2026, 11, 25)
_ROOT = Path(__file__).resolve().parents[1]


def _bars(as_of, *, n=120, close=10.0, volume=5_000_000, last_volume=None, high_extra=0.5, close_values=None):
    idx = pd.bdate_range(end=pd.Timestamp(as_of), periods=n)
    closes = [close] * n if close_values is None else list(close_values)
    volumes = [volume] * n
    if last_volume is not None:
        volumes[-1] = last_volume
    return pd.DataFrame(
        {
            "Open": closes,
            "High": [value + high_extra for value in closes],
            "Low": [value - high_extra for value in closes],
            "Close": closes,
            "Volume": volumes,
        },
        index=idx,
    )


def _ready(**overrides):
    base = {
        "status": "ok",
        "code": "0700.HK",
        "name": "腾讯",
        "market": "hk",
        "close": 400.0,
        "close_raw": 400.0,
        "n": 5.0,
        "stop_long_2n": 390.0,
        "avg_turnover_20": 50_000_000.0,
        "s1_recent_close_breakout": False,
        "s2_recent_close_breakout": True,
        "s1_recent_high_breakout": False,
        "s2_recent_high_breakout": False,
        "s1_entry_allowed": True,
        "turtle_trend_ok": True,
        "volume_confirm": True,
        "breakout_extension_n": 0.2,
        "s1_exit": False,
        "s2_exit": False,
        "close_vs_ma100": True,
        "potential_score": 0,
        "currency": "HKD",
    }
    base.update(overrides)
    return base


def _breakout_frame(as_of, *, close_breaks: bool):
    """Rise, then a flat shelf, then one close or high-only poke."""
    idx = pd.bdate_range(end=pd.Timestamp(as_of), periods=130)
    closes = []
    highs = []
    lows = []
    for i in range(100):
        price = 50 + i * 0.5
        closes.append(price)
        highs.append(price + 1.0)
        lows.append(price - 1.0)
    for _ in range(29):
        closes.append(100.0)
        highs.append(102.0)
        lows.append(98.0)
    if close_breaks:
        closes.append(102.3)
        highs.append(102.5)
        lows.append(100.0)
    else:
        closes.append(101.0)
        highs.append(102.5)
        lows.append(99.0)
    volumes = [1_000_000] * 129 + [2_000_000]
    return pd.DataFrame(
        {"Open": closes, "High": highs, "Low": lows, "Close": closes, "Volume": volumes},
        index=idx,
    )


def test_official_floors_replace_retired_defaults():
    assert HK_MIN_PRICE_HKD == 1.0
    assert HK_MIN_AVG_TURNOVER_HKD == 20_000_000.0
    assert US_MIN_PRICE_USD == 5.0
    assert US_MIN_AVG_TURNOVER_USD == 5_000_000.0
    assert DEFAULT_MIN_PRICE == HK_MIN_PRICE_HKD
    assert DEFAULT_MIN_AVG_TURNOVER == HK_MIN_AVG_TURNOVER_HKD
    assert (CAP_SINGLE_MARKET, CAP_TIGHT_GROUP, CAP_LOOSE_GROUP, CAP_ONE_DIRECTION) == (4, 6, 10, 12)


def test_floors_are_native_currency_and_ignore_lower_env(monkeypatch):
    monkeypatch.setenv("HK_SCAN_MIN_PRICE", "0.1")
    monkeypatch.setenv("HK_SCAN_MIN_AVG_TURNOVER", "2000000")
    assert passes_official_floor(1.0, 20_000_000, "hk") is True
    assert passes_official_floor(0.99, 50_000_000, "hk") is False
    assert passes_official_floor(10.0, 19_999_999, "hk") is False
    assert passes_official_floor(5.0, 5_000_000, "us") is True
    assert passes_official_floor(4.99, 5_000_000, "us") is False
    assert passes_official_floor(1.5, 20_000_000, "us") is False
    assert passes_official_floor(1.5, 20_000_000, "hk") is True


def test_daily_universe_is_hsi_plus_us_top_only():
    hk = load_daily_universe("hk")
    us = load_daily_universe("us")
    assert [item["code"] for item in hk] == [item["code"] for item in HSI_STOCKS]
    assert [item["code"] for item in us] == [item["code"] for item in US_TOP_STOCKS]
    hk_all = {item["code"] for item in load_hk_all_stocks()}
    hsi = {item["code"] for item in hk}
    assert len(hk_all) > len(hsi)
    assert hk_all - hsi
    assert all(code.endswith(".HK") for code in hsi)
    assert all(not code.endswith(".HK") for code in (item["code"] for item in us))
    for code in ("600519", "600519.SH", "000001.SZ", "BTC-USD", "BTC", "GC=F", "GLD", "BRONZE", "HG=F"):
        assert is_forbidden_listing(code)
    assert is_forbidden_listing("GS") is False
    assert is_forbidden_listing("0700.HK") is False
    assert is_forbidden_listing("AAPL") is False
    outside = next(iter(hk_all - hsi))
    try:
        validate_universe([{"code": outside, "name": "x", "market": "hk"}], market="hk")
    except CandidateScreenDataError as exc:
        assert "outside" in str(exc)
    else:
        raise AssertionError("HK_ALL-only code was accepted")
    try:
        validate_universe([{"code": "BTC-USD", "name": "Bitcoin", "market": "us"}], market="us")
    except CandidateScreenDataError as exc:
        assert "forbidden" in str(exc)
    else:
        raise AssertionError("BTC was accepted")


def test_close_first_breakout_admits_and_high_only_does_not():
    close_sig = compute_signals_full(_breakout_frame(_AS_OF, close_breaks=True))
    high_sig = compute_signals_full(_breakout_frame(_AS_OF, close_breaks=False))
    assert close_sig["s2_recent_close_breakout"] is True
    assert is_uprising_row(close_sig) is True
    assert high_sig["s2_recent_close_breakout"] is False
    assert high_sig["s1_recent_close_breakout"] is False
    assert high_sig["s2_recent_high_breakout"] or high_sig["s1_recent_high_breakout"]
    assert is_uprising_row(high_sig) is False
    assert abs(close_sig["stop_long_2n"] - (close_sig["close"] - 2 * close_sig["n"])) < 0.05


def test_score_and_macd_do_not_admit_or_reorder():
    high_only = _ready(
        code="HIGH.HK",
        s2_recent_close_breakout=False,
        s1_recent_close_breakout=False,
        s2_recent_high_breakout=True,
        potential_score=100,
        macd_status="金叉",
    )
    death = _ready(code="DEAD.HK", potential_score=0, macd_status="死叉", breakout_extension_n=0.2)
    later = _ready(code="LATE.HK", potential_score=100, breakout_extension_n=0.9)
    selected = select_candidates([high_only, later, death], market="hk", index_trend_ok=True)
    codes = [row["code"] for row in selected["uprising"]]
    assert "HIGH.HK" not in codes
    assert codes[0] == "DEAD.HK"
    text = format_candidate_report({**selected, "as_of": "2026-11-25", "bar_date": "2026-11-25", "universe_label": "恒指成分"})
    assert "MACD" not in text
    assert "金叉" not in text
    assert "死叉" not in text


def test_fx_field_does_not_convert_prices():
    row = _ready(close=10, close_raw=10, n=1, stop_long_2n=8, avg_turnover_20=50_000_000, fx_rate=7.8, currency="USD")
    selected = select_candidates([row], market="hk", index_trend_ok=True)
    text = format_candidate_report({**selected, "as_of": "2026-11-25", "bar_date": "2026-11-25", "universe_label": "恒指成分"})
    assert "10.00 HKD" in text
    assert "8.00 HKD" in text
    assert "1.0000 HKD" in text
    assert "78.00" not in text
    table = text.split("## 趋势首破", 1)[1].split("## 附录", 1)[0]
    assert "USD" not in table
    assert "10.00 HKD" in table
    assert "不含买卖数量" in text
    assert "MONITOR_SIM" not in text
    main, _, appendix = text.partition("## 附录：止跌转折")
    assert "0700.HK" in main
    assert "0700.HK" not in appendix


def test_reversal_stays_in_the_appendix():
    up = _ready(code="UP.HK", turtle_trend_ok=True, s2_recent_close_breakout=True)
    rev = _ready(
        code="REV.HK",
        turtle_trend_ok=False,
        s2_recent_close_breakout=False,
        s1_recent_close_breakout=True,
        s1_entry_allowed=True,
    )
    selected = select_candidates([up, rev], market="hk", index_trend_ok=True)
    text = format_candidate_report({**selected, "as_of": "2026-11-25", "bar_date": "2026-11-25", "universe_label": "恒指成分"})
    main, _, appendix = text.partition("## 附录：止跌转折")
    assert "UP.HK" in main
    assert "REV.HK" not in main
    assert "REV.HK" in appendix
    assert "不是本日主名单" in appendix


def test_index_trend_suppresses_only_the_main_feed():
    up = _ready(code="UP.HK")
    rev = _ready(
        code="REV.HK",
        turtle_trend_ok=False,
        s2_recent_close_breakout=False,
        s1_recent_close_breakout=True,
    )
    selected = select_candidates([up, rev], market="hk", index_trend_ok=False)
    assert selected["uprising"] == []
    assert [row["code"] for row in selected["reversal"]] == ["REV.HK"]
    text = format_candidate_report({**selected, "as_of": "2026-11-25", "bar_date": "2026-11-25", "universe_label": "恒指成分"})
    assert "不列趋势首破" in text


def test_display_caps_and_dual_listings():
    assert display_cap_block_reason(market_count=4, tight_count=0, loose_count=0, direction_count=0) == "single_market"
    assert display_cap_block_reason(market_count=0, tight_count=6, loose_count=0, direction_count=0) == "tight_group"
    assert display_cap_block_reason(market_count=0, tight_count=0, loose_count=10, direction_count=0) == "loose_group"
    assert display_cap_block_reason(market_count=0, tight_count=0, loose_count=0, direction_count=12) == "one_direction"
    assert display_cap_block_reason(market_count=3, tight_count=5, loose_count=9, direction_count=11) is None

    us_rows = [
        {"code": code, "market": "us", "breakout_extension_n": ext, "s2_recent_close_breakout": True,
         "company_id": code, "tight_group": f"solo:{code}", "loose_group": f"solo:{code}"}
        for code, ext in (("A", 0.2), ("B", 0.3), ("C", 0.4), ("D", 0.5), ("E", 0.6))
    ]
    us_rows.append({
        "code": "SCORE",
        "market": "us",
        "breakout_extension_n": 0.7,
        "s2_recent_close_breakout": True,
        "company_id": "SCORE",
        "tight_group": "solo:SCORE",
        "loose_group": "solo:SCORE",
        "potential_score": 100,
    })
    shown, rejected = apply_display_caps(us_rows)
    assert [row["code"] for row in shown] == ["A", "B", "C", "D"]
    assert {row["code"] for row in rejected} == {"E", "SCORE"}

    duals = [
        {"code": "GOOGL", "market": "us", "breakout_extension_n": 0.01, "s2_recent_close_breakout": True,
         "company_id": "alphabet", "tight_group": "us_platforms", "loose_group": "communication"},
        {"code": "GOOG", "market": "us", "breakout_extension_n": 0.01, "s2_recent_close_breakout": True,
         "company_id": "alphabet", "tight_group": "us_platforms", "loose_group": "communication"},
        {"code": "MSFT", "market": "us", "breakout_extension_n": 0.2, "s2_recent_close_breakout": True,
         "company_id": "MSFT", "tight_group": "us_platforms", "loose_group": "communication"},
        {"code": "NVDA", "market": "us", "breakout_extension_n": 0.3, "s2_recent_close_breakout": True,
         "company_id": "NVDA", "tight_group": "us_semis", "loose_group": "technology"},
        {"code": "JPM", "market": "us", "breakout_extension_n": 0.4, "s2_recent_close_breakout": True,
         "company_id": "JPM", "tight_group": "us_financials", "loose_group": "financials"},
        {"code": "CAT", "market": "us", "breakout_extension_n": 0.5, "s2_recent_close_breakout": True,
         "company_id": "CAT", "tight_group": "us_industrials", "loose_group": "industrials"},
    ]
    shown, rejected = apply_display_caps(duals)
    assert {row["code"] for row in shown} == {"GOOG", "GOOGL", "MSFT", "NVDA", "JPM"}
    assert [row["code"] for row in rejected] == ["CAT"]
    assert len({row["company_id"] for row in shown}) == 4

    mixed = []
    for offset, market in enumerate(("hk", "us", "hk", "us", "hk", "us", "hk")):
        mixed.append({
            "code": f"{market}{offset}",
            "market": market,
            "breakout_extension_n": 0.1 * (offset + 1),
            "s2_recent_close_breakout": True,
            "company_id": f"co{offset}",
            "tight_group": "same-tight",
            "loose_group": f"loose{offset}",
        })
    shown, rejected = apply_display_caps(mixed)
    assert len(shown) == 6
    assert rejected[0]["cap_reason"] == "tight_group"

    cross = [
        {"code": f"US{i}", "market": "us", "breakout_extension_n": 0.1, "s2_recent_close_breakout": True,
         "company_id": f"US{i}", "tight_group": f"t{i}", "loose_group": f"l{i}"}
        for i in range(4)
    ]
    cross.append({
        "code": "9988.HK", "market": "hk", "breakout_extension_n": 0.5, "s2_recent_close_breakout": True,
        "company_id": "alibaba", "tight_group": "hk_internet", "loose_group": "communication",
    })
    cross.append({
        "code": "BABA", "market": "us", "breakout_extension_n": 0.6, "s2_recent_close_breakout": True,
        "company_id": "alibaba", "tight_group": "hk_internet", "loose_group": "communication",
    })
    shown, _rejected = apply_display_caps(cross)
    assert any(row["code"] == "9988.HK" and row["cap_role"] == "primary" for row in shown)
    assert any(row["code"] == "BABA" and row["cap_role"] == "dual" for row in shown)
    assert len([row for row in shown if row["market"] == "us" and row["cap_role"] == "primary"]) == 4
    assert correlation_profile("GOOG")["company_id"] == correlation_profile("GOOGL")["company_id"]
    assert correlation_profile("9988.HK")["company_id"] == correlation_profile("BABA")["company_id"]
    assert correlation_profile("0700.HK")["tight_group"] == correlation_profile("9988.HK")["tight_group"]


def test_liquidity_fail_closed_rules():
    ok = measure_liquidity(_bars(_AS_OF, close=2.0, volume=20_000_000), market="hk", as_of=_AS_OF)
    assert ok["avg_turnover_20"] == 2.0 * 20_000_000
    assert ok["currency"] == "HKD"
    try:
        measure_liquidity(_bars(_AS_OF, last_volume=0), market="hk", as_of=_AS_OF)
    except CandidateScreenDataError as exc:
        assert "zero turnover" in str(exc)
    else:
        raise AssertionError("zero turnover was accepted")

    sparse = _bars(_AS_OF)
    sparse.iloc[-7:-1, sparse.columns.get_loc("Volume")] = 0
    try:
        measure_liquidity(sparse, market="us", as_of=_AS_OF)
    except CandidateScreenDataError as exc:
        assert "15" in str(exc) or "sessions" in str(exc)
    else:
        raise AssertionError("14 valid sessions were accepted")

    enough = _bars(_AS_OF, close=6.0, volume=1_000_000)
    enough.iloc[-6:-1, enough.columns.get_loc("Volume")] = 0
    measured = measure_liquidity(enough, market="us", as_of=_AS_OF)
    assert measured["turnover_valid_sessions"] == 15
    assert measured["currency"] == "USD"
    assert measured["avg_turnover_20"] == 6.0 * 1_000_000

    stale = _bars(date(2026, 11, 24))
    try:
        measure_liquidity(stale, market="hk", as_of=_AS_OF)
    except CandidateScreenDataError as exc:
        assert "as-of bar missing" in str(exc)
    else:
        raise AssertionError("stale bar was accepted")

    no_volume = _bars(_AS_OF).drop(columns=["Volume"])
    try:
        measure_liquidity(no_volume, market="hk", as_of=_AS_OF)
    except CandidateScreenDataError as exc:
        assert "cannot be computed" in str(exc)
    else:
        raise AssertionError("missing volume was accepted")


def test_run_stamps_effective_date_and_does_not_touch_the_book(monkeypatch, tmp_path):
    calls = []

    def _fake(market, current_time=None):
        calls.append(market)
        return _AS_OF

    monkeypatch.setattr("src.services.candidate_screen.get_effective_trading_date", _fake)
    monkeypatch.setenv("STOCK_LIST", "600519")
    monkeypatch.setenv("HSI_HOLDINGS", "0700.HK 10")
    monkeypatch.setenv("HSI_HOLDINGS_FILE", "/tmp/holdings-should-not-be-read")
    monkeypatch.setenv("MONITOR_SIM_EQUITY", "SENTINEL-EQUITY")
    before = {key: os.environ.get(key) for key in ("STOCK_LIST", "HSI_HOLDINGS", "MONITOR_SIM_EQUITY")}
    universe = [{"code": "0700.HK", "name": "腾讯", "market": "hk"}]
    result = run_candidate_screen(
        market="hk",
        reports_dir=tmp_path,
        histories={"0700.HK": _bars(_AS_OF)},
        universe=universe,
        index_trend_ok=True,
    )
    assert calls == ["hk"]
    assert result["as_of"] == "2026-11-25"
    assert result["bar_date"] == "2026-11-25"
    text = Path(result["artifact_latest"]).read_text(encoding="utf-8")
    assert Path(result["artifact_dated"]).read_text(encoding="utf-8") == text
    assert "as-of session: 2026-11-25" in text
    assert "bar date: 2026-11-25" in text
    assert "get_effective_trading_date" in text
    assert "SENTINEL-EQUITY" not in text
    assert "600519" not in text
    assert os.environ["STOCK_LIST"] == before["STOCK_LIST"]
    assert os.environ["HSI_HOLDINGS"] == before["HSI_HOLDINGS"]
    assert os.environ["MONITOR_SIM_EQUITY"] == before["MONITOR_SIM_EQUITY"]
    assert not Path("/tmp/holdings-should-not-be-read").exists()


def test_missing_print_writes_no_artifact(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "src.services.candidate_screen.get_effective_trading_date",
        lambda market, current_time=None: _AS_OF,
    )
    universe = [{"code": "0700.HK", "name": "腾讯", "market": "hk"}]
    try:
        run_candidate_screen(
            market="hk",
            reports_dir=tmp_path,
            histories={"0700.HK": _bars(_AS_OF, last_volume=0)},
            universe=universe,
            index_trend_ok=True,
        )
    except CandidateScreenDataError as exc:
        assert "fail closed" in str(exc)
    else:
        raise AssertionError("incomplete print wrote a list")
    assert not (tmp_path / "candidate_screen" / "hk" / "latest.md").exists()


def test_schedule_and_workflow_do_not_use_the_old_jobs():
    workflow = (_ROOT / ".github" / "workflows" / "candidate_screen.yml").read_text(encoding="utf-8")
    assert HK_SCREEN_CRON_UTC in workflow
    assert US_SCREEN_CRON_UTC in workflow
    for retired in ("0 7 * * 1-5", "0 10 * * 1-5", "0 18 * * 1-5"):
        assert retired not in workflow
    for banned in ("HSI_HOLDINGS", "STOCK_LIST", "GEMINI", "TENCENT", "TEAMS", "LITELLM"):
        assert banned not in workflow
    assert "ref: mine" in workflow
    shanghai = ZoneInfo("Asia/Shanghai")
    utc = ZoneInfo("UTC")
    hk_run = datetime(2026, 11, 25, 8, 20, tzinfo=utc)
    assert hk_run.astimezone(shanghai).strftime("%H:%M %A") == "16:20 Wednesday"
    us_run = datetime(2026, 11, 27, 21, 20, tzinfo=utc)
    assert us_run.astimezone(shanghai).strftime("%H:%M %A") == "05:20 Saturday"
    screen_source = (_ROOT / "src" / "services" / "candidate_screen.py").read_text(encoding="utf-8")
    for banned in (
        "qualified_stock_scanner",
        "social_sentiment",
        "NotificationService",
        "import monitor_simulator",
        "strategies/",
    ):
        assert banned not in screen_source


def test_saturday_us_stamp_covers_friday_early_close():
    now = datetime(2026, 11, 28, 5, 20, tzinfo=ZoneInfo("Asia/Shanghai"))
    assert get_effective_trading_date("us", current_time=now) == date(2026, 11, 27)
    hk_now = datetime(2026, 11, 26, 16, 20, tzinfo=ZoneInfo("Asia/Shanghai"))
    assert get_effective_trading_date("hk", current_time=hk_now) == date(2026, 11, 26)
