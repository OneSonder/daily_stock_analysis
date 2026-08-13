# -*- coding: utf-8 -*-
"""Tests for HSI holdings parser and Turtle sell/keep/buy action."""

from __future__ import annotations

from src.services.hsi_holdings import (
    load_holdings_from_env,
    normalize_holding_code,
    parse_holdings_text,
)
from src.services.hsi_enrichment import select_enrich_targets
from src.services.hsi_scanner import (
    HSI_STOCKS,
    _code_to_yfinance_format,
    attach_holdings_to_results,
    format_scan_report,
    merge_stocks_with_holdings,
    turtle_holding_action,
)


def test_normalize_holding_code():
    assert normalize_holding_code("9988.HK") == "9988.HK"
    assert normalize_holding_code("700") == "0700.HK"
    assert normalize_holding_code("hk00700") == "0700.HK"
    assert normalize_holding_code("600519.SH") == "600519.SH"
    assert normalize_holding_code("SH600519") == "600519.SH"
    assert normalize_holding_code("000001.SZ") == "000001.SZ"
    assert normalize_holding_code("sz000001") == "000001.SZ"
    assert normalize_holding_code("000001.SS") == "000001.SH"


def test_parse_holdings_text_formats():
    rows = parse_holdings_text(
        "9988.HK 125.50\n0700.HK:400\n1810.HK,12.3\n"
    )
    by_code = {r["code"]: r["buy_price"] for r in rows}
    assert by_code["9988.HK"] == 125.50
    assert by_code["0700.HK"] == 400.0
    assert by_code["1810.HK"] == 12.3


def test_parse_holdings_comma_pairs():
    rows = parse_holdings_text("9988.HK 125.50, 0700.HK 400")
    codes = {r["code"] for r in rows}
    assert codes == {"9988.HK", "0700.HK"}


def test_a_share_holding_is_added_without_expanding_hsi_universe():
    holdings = parse_holdings_text("600519.SH 1500")

    merged, extra = merge_stocks_with_holdings(list(HSI_STOCKS), holdings)

    assert extra == 1
    assert len(merged) == len(HSI_STOCKS) + 1
    assert merged[-1] == {"code": "600519.SH", "name": "600519.SH"}


def test_shanghai_holding_uses_yahoo_ss_symbol_at_fetch_boundary():
    assert _code_to_yfinance_format("600519.SH") == "600519.SS"
    assert _code_to_yfinance_format("000001.SZ") == "000001.SZ"
    assert _code_to_yfinance_format("0700.HK") == "0700.HK"


def test_parse_holdings_empty_and_bad():
    assert parse_holdings_text("") == []
    assert parse_holdings_text("not-a-holding") == []
    assert parse_holdings_text("9988.HK -1") == []


def test_load_holdings_from_env(monkeypatch, tmp_path):
    monkeypatch.delenv("HSI_HOLDINGS", raising=False)
    monkeypatch.delenv("HSI_HOLDINGS_FILE", raising=False)
    assert load_holdings_from_env() == []

    monkeypatch.setenv("HSI_HOLDINGS", "9988.HK 125.50")
    rows = load_holdings_from_env()
    assert len(rows) == 1
    assert rows[0]["code"] == "9988.HK"

    monkeypatch.delenv("HSI_HOLDINGS", raising=False)
    path = tmp_path / "hold.txt"
    path.write_text("0700.HK 401\n", encoding="utf-8")
    monkeypatch.setenv("HSI_HOLDINGS_FILE", str(path))
    rows = load_holdings_from_env()
    assert rows[0]["code"] == "0700.HK"
    assert rows[0]["buy_price"] == 401.0


def test_turtle_holding_action_sell_on_2n_stop():
    signal = {
        "close": 90.0,
        "low": 89.0,
        "n": 10.0,
        "s1_exit": False,
        "s2_exit": False,
        "turtle_trend_ok": True,
    }
    # B=100, stop=80; price above stop → not sell from 2N
    mid = turtle_holding_action({**signal, "close": 95.0, "low": 94.0}, 100.0)
    assert mid["turtle_action"] in {"keep", "buy"}
    assert mid["stop_from_entry_2n"] == 80.0

    # low hits stop
    out = turtle_holding_action({**signal, "close": 81.0, "low": 79.0}, 100.0)
    assert out["turtle_action"] == "sell"
    assert "2N" in out["turtle_action_reason"]


def test_turtle_holding_action_sell_on_exit():
    signal = {
        "close": 110.0,
        "low": 109.0,
        "n": 5.0,
        "s1_exit": True,
        "s2_exit": False,
        "turtle_trend_ok": True,
    }
    out = turtle_holding_action(signal, 100.0)
    assert out["turtle_action"] == "sell"


def test_turtle_holding_action_buy_add():
    # B=100, N=10 → add at 105; close 106 + trend → buy
    signal = {
        "close": 106.0,
        "low": 105.0,
        "n": 10.0,
        "s1_exit": False,
        "s2_exit": False,
        "turtle_trend_ok": True,
    }
    out = turtle_holding_action(signal, 100.0)
    assert out["turtle_action"] == "buy"
    assert out["add_level_05n"] == 105.0


def test_turtle_holding_action_keep():
    signal = {
        "close": 102.0,
        "low": 101.0,
        "n": 10.0,
        "s1_exit": False,
        "s2_exit": False,
        "turtle_trend_ok": False,
    }
    out = turtle_holding_action(signal, 100.0)
    assert out["turtle_action"] == "keep"
    assert out["pnl_pct"] == 2.0


def test_attach_and_report_holdings():
    holdings = [{"code": "9988.HK", "buy_price": 100.0}]
    results = [
        {
            "code": "9988.HK",
            "name": "阿里",
            "status": "ok",
            "close": 110.0,
            "low": 109.0,
            "n": 5.0,
            "s1_exit": False,
            "s2_exit": False,
            "turtle_trend_ok": True,
            "url": "https://example",
        }
    ]
    attached = attach_holdings_to_results(holdings, results)
    assert len(attached) == 1
    assert attached[0]["turtle_action"] == "buy"
    report = format_scan_report(
        {
            "matches": [],
            "no_price": [],
            "stats": {"tickers": 1, "total_ms": 1},
            "holdings": attached,
        }
    )
    assert "持仓止损参考" in report
    assert "9988.HK" in report
    assert "加仓" in report


def test_select_enrich_targets_prepends_holdings():
    holdings = [
        {
            "code": "9988.HK",
            "name": "阿里",
            "buy_price": 100,
            "potential_score": 10,
            "is_holding": True,
            "turtle_action": "keep",
        }
    ]
    matches = [
        {"code": "0700.HK", "name": "腾讯", "potential_score": 90},
        {"code": "9988.HK", "name": "阿里", "potential_score": 50},
    ]
    selected = select_enrich_targets(
        matches,
        holdings=holdings,
        top_n=1,
        etnet_top_n=0,
    )
    assert selected[0]["code"] == "9988.HK"
    assert selected[0]["enrich_source"] == "holding"
    assert selected[1]["code"] == "0700.HK"
