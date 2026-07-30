# -*- coding: utf-8 -*-
"""Tests for ET Net top movers helper and HSI merge/report wiring."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.services.etnet_top_movers import (
    etnet_code_to_yahoo,
    fetch_etnet_top_movers,
    normalize_subtypes,
    parse_etnet_top_html,
    resolve_etnet_top_config_from_env,
    unique_codes_from_boards,
)
from src.services.hsi_scanner import (
    format_scan_report,
    merge_stocks_with_etnet_top,
)

_SAMPLE_HTML = """
<html><body>
<table>
<tr><td>No</td><td>Code</td><td>Name</td><td>Nominal</td><td>Change</td>
<td>%Change</td><td>Highest</td><td>Lowest</td><td>Turnover</td><td>Currency</td></tr>
<tr><td>1</td><td>00700</td><td>TENCENT</td><td>447.600</td><td>4.600</td>
<td>1.038%</td><td>452.000</td><td>441.600</td><td>6.857B</td><td>HKD</td></tr>
<tr><td>2</td><td>01810</td><td>XIAOMI-W</td><td>29.220</td><td>0.540</td>
<td>1.883%</td><td>29.660</td><td>28.580</td><td>5.650B</td><td>HKD</td></tr>
<tr><td>3</td><td>09988</td><td>BABA-W</td><td>112.300</td><td>1.300</td>
<td>1.171%</td><td>114.200</td><td>111.000</td><td>7.374B</td><td>HKD</td></tr>
</table>
</body></html>
"""

_TC_SAMPLE_HTML = """
<html><body>
<table>
<tr><td>排序</td><td>代號</td><td>名稱</td><td></td><td>按盤價</td><td>變動</td>
<td>變動率</td><td>最高價</td><td>最低價</td><td>成交金額</td><td>貨幣</td></tr>
<tr><td>1</td><td><a href="quote.php?code=03033">03033</a></td>
<td><a href="quote.php?code=03033">南方恒生科技</a></td>
<td><img alt="跌"></td><td>4.738</td><td>-0.030</td><td>-0.629%</td>
<td>4.822</td><td>4.682</td><td>157.77億</td><td>HKD</td></tr>
<tr><td>2</td><td><a href="quote.php?code=00700">00700</a></td>
<td><a href="quote.php?code=00700">騰訊控股</a>
<a href="quote_ai_analysis.php?code=700">AI 診股</a></td>
<td><img alt="升"></td><td>474.000</td><td>7.600</td><td>1.630%</td>
<td>475.000</td><td>462.800</td><td>103.07億</td><td>HKD</td></tr>
</table>
</body></html>
"""

_VOLUME_HTML = """
<html><body>
<table>
<tr><td>No</td><td>Code</td><td>Name</td><td>Nominal</td><td>Change</td>
<td>%Change</td><td>Highest</td><td>Lowest</td><td>Volume</td><td>Currency</td></tr>
<tr><td>1</td><td>03033</td><td>CSOP HS TECH</td><td>4.636</td><td>0.020</td>
<td>0.433%</td><td>4.690</td><td>4.584</td><td>3.181B</td><td>HKD</td></tr>
</table>
</body></html>
"""


def test_etnet_code_to_yahoo():
    assert etnet_code_to_yahoo("00700") == "0700.HK"
    assert etnet_code_to_yahoo("1810") == "1810.HK"
    assert etnet_code_to_yahoo("09988") == "9988.HK"
    assert etnet_code_to_yahoo("") is None
    assert etnet_code_to_yahoo("ABC") is None


def test_parse_etnet_top_html_top_n():
    rows = parse_etnet_top_html(_SAMPLE_HTML, subtype="turnover", top_n=2)
    assert len(rows) == 2
    assert rows[0]["code"] == "0700.HK"
    assert rows[0]["name"] == "TENCENT"
    assert rows[0]["metric"] == "6.857B"
    assert rows[0]["subtype"] == "turnover"
    assert rows[1]["code"] == "1810.HK"


def test_parse_etnet_tc_html_chinese_names():
    rows = parse_etnet_top_html(_TC_SAMPLE_HTML, subtype="turnover", top_n=10)
    assert len(rows) == 2
    assert rows[0]["code"] == "3033.HK"
    assert rows[0]["name"] == "南方恒生科技"
    assert rows[0]["metric"] == "157.77億"
    assert rows[0]["change_pct"] == "-0.629%"
    assert rows[1]["code"] == "0700.HK"
    assert rows[1]["name"] == "騰訊控股"
    assert "AI" not in rows[1]["name"]


def test_parse_volume_metric_label():
    rows = parse_etnet_top_html(_VOLUME_HTML, subtype="volume", top_n=10)
    assert len(rows) == 1
    assert rows[0]["code"] == "3033.HK"
    assert rows[0]["metric_label"] == "volume"


def test_normalize_subtypes_rejects_down():
    assert normalize_subtypes("turnover,volume,up,down") == ["turnover", "volume", "up"]
    assert normalize_subtypes(["down"]) == ["turnover", "volume", "up"]
    assert "down" not in normalize_subtypes("up,down,volume")


def test_resolve_etnet_top_config_from_env(monkeypatch):
    monkeypatch.setenv("HSI_ETNET_TOP_ENABLED", "true")
    monkeypatch.setenv("HSI_ETNET_TOP_N", "10")
    monkeypatch.setenv("HSI_ETNET_TOP_SUBTYPES", "turnover,volume,up,down")
    cfg = resolve_etnet_top_config_from_env()
    assert cfg["enabled"] is True
    assert cfg["top_n"] == 10
    assert cfg["subtypes"] == ["turnover", "volume", "up"]


def test_fetch_etnet_top_movers_rejects_down():
    assert fetch_etnet_top_movers(subtype="down") == []


def test_fetch_etnet_top_movers_soft_fail(monkeypatch):
    session = MagicMock()
    session.get.side_effect = RuntimeError("network down")
    assert fetch_etnet_top_movers(subtype="turnover", session=session) == []


def test_unique_codes_from_boards_dedupes():
    boards = {
        "turnover": [{"code": "0700.HK", "name": "腾讯"}],
        "volume": [{"code": "0700.HK", "name": "腾讯"}, {"code": "1810.HK", "name": "小米"}],
        "up": [{"code": "9988.HK", "name": "阿里"}],
    }
    codes = unique_codes_from_boards(boards)
    assert [c["code"] for c in codes] == ["0700.HK", "1810.HK", "9988.HK"]


def test_merge_stocks_with_etnet_top():
    base = [{"code": "0700.HK", "name": "腾讯"}, {"code": "0005.HK", "name": "汇丰"}]
    top = [{"code": "0700.HK", "name": "TENCENT"}, {"code": "2513.HK", "name": "Z.AI"}]
    merged, extra = merge_stocks_with_etnet_top(base, top)
    assert [m["code"] for m in merged] == ["0700.HK", "0005.HK", "2513.HK"]
    assert extra == 1


def test_format_scan_report_includes_three_etnet_sections_not_losers():
    payload = {
        "matches": [],
        "no_price": [],
        "stats": {"tickers": 90, "total_ms": 12},
        "skipped": False,
        "etnet_top": {
            "enabled": True,
            "merged_extra": 3,
            "boards": {
                "turnover": [
                    {
                        "rank": 1,
                        "code": "0700.HK",
                        "name": "TENCENT",
                        "nominal": "447",
                        "change_pct": "1%",
                        "metric": "6B",
                    }
                ],
                "volume": [
                    {
                        "rank": 1,
                        "code": "3033.HK",
                        "name": "CSOP",
                        "nominal": "4.6",
                        "change_pct": "0.4%",
                        "metric": "3B",
                    }
                ],
                "up": [
                    {
                        "rank": 1,
                        "code": "1940.HK",
                        "name": "CGII",
                        "nominal": "1.18",
                        "change_pct": "37%",
                        "metric": "1.5M",
                    }
                ],
            },
            "errors": {},
        },
    }
    text = format_scan_report(payload)
    assert "经济通 Top 10 成交額" in text
    assert "经济通 Top 10 成交股數" in text
    assert "经济通 Top 10 升幅" in text
    assert "Losers" not in text
    assert "subtype=down" not in text
    assert "0700.HK" in text
    assert "3033.HK" in text
    assert "+3 只代码" in text
    assert "恒指信号扫描" in text
    assert "匹配结果" in text or "没有股票符合所选条件" in text


@patch("src.services.etnet_top_movers.fetch_etnet_top_boards")
@patch("src.services.hsi_scanner.scan_stocks")
def test_scan_hsi_merges_etnet_when_enabled(mock_scan_stocks, mock_fetch, monkeypatch):
    monkeypatch.setenv("HSI_ETNET_TOP_ENABLED", "true")
    monkeypatch.setenv("HSI_ETNET_TOP_SUBTYPES", "turnover,volume,up")
    mock_fetch.return_value = {
        "boards": {
            "turnover": [{"code": "2513.HK", "name": "Z.AI"}],
            "volume": [],
            "up": [{"code": "0700.HK", "name": "TENCENT"}],
        },
        "errors": {"volume": "empty or failed"},
        "top_n": 10,
        "subtypes": ["turnover", "volume", "up"],
    }
    mock_scan_stocks.return_value = {
        "matches": [],
        "no_price": [],
        "stats": {"tickers": 1},
        "skipped": False,
        "conditions": [],
    }

    from src.services.hsi_scanner import HSI_STOCKS, scan_hsi

    result = scan_hsi(check_trading_day=False, use_multi_source=False)
    called_stocks = mock_scan_stocks.call_args.kwargs.get("stocks") or mock_scan_stocks.call_args[0][0]
    codes = {s["code"] for s in called_stocks}
    assert "2513.HK" in codes
    assert len(called_stocks) >= len(HSI_STOCKS)
    assert result["etnet_top"]["enabled"] is True
    assert result["etnet_top"]["merged_extra"] >= 1
    assert "turnover" in result["etnet_top"]["boards"]


@patch("src.services.hsi_scanner.scan_stocks")
def test_scan_hsi_skips_etnet_when_disabled(mock_scan_stocks, monkeypatch):
    monkeypatch.setenv("HSI_ETNET_TOP_ENABLED", "false")
    mock_scan_stocks.return_value = {
        "matches": [],
        "no_price": [],
        "stats": {"tickers": 1},
        "skipped": False,
        "conditions": [],
    }

    from src.services.hsi_scanner import HSI_STOCKS, scan_hsi

    result = scan_hsi(check_trading_day=False)
    called_stocks = mock_scan_stocks.call_args.kwargs.get("stocks") or mock_scan_stocks.call_args[0][0]
    assert len(called_stocks) == len(HSI_STOCKS)
    assert result["etnet_top"]["enabled"] is False
    assert result["etnet_top"]["merged_extra"] == 0
