# -*- coding: utf-8 -*-
"""Tests for Tencent ifzq stock news helper."""

from __future__ import annotations

from unittest.mock import MagicMock

from src.services.tencent_stock_news import (
    fetch_tencent_stock_news,
    format_tencent_news_context,
    is_tencent_stock_news_enabled,
    merge_news_contexts,
    to_ifzq_symbol,
)


def test_to_ifzq_symbol_hk_and_a_share():
    assert to_ifzq_symbol("0700.HK") == "hk00700"
    assert to_ifzq_symbol("hk00700") == "hk00700"
    assert to_ifzq_symbol("HK00700") == "hk00700"
    assert to_ifzq_symbol("00700") == "hk00700"
    assert to_ifzq_symbol("700") == "hk00700"
    assert to_ifzq_symbol("600519") == "sh600519"
    assert to_ifzq_symbol("SH600519") == "sh600519"
    assert to_ifzq_symbol("600519.SH") == "sh600519"
    assert to_ifzq_symbol("000001") == "sz000001"
    assert to_ifzq_symbol("sz000001") == "sz000001"
    assert to_ifzq_symbol("AAPL") is None
    assert to_ifzq_symbol("") is None


def test_is_tencent_stock_news_enabled_default_true(monkeypatch):
    monkeypatch.delenv("TENCENT_STOCK_NEWS_ENABLED", raising=False)
    assert is_tencent_stock_news_enabled() is True
    monkeypatch.setenv("TENCENT_STOCK_NEWS_ENABLED", "false")
    assert is_tencent_stock_news_enabled() is False
    monkeypatch.setenv("TENCENT_STOCK_NEWS_ENABLED", "1")
    assert is_tencent_stock_news_enabled() is True


def test_fetch_tencent_stock_news_maps_items():
    session = MagicMock()
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {
        "code": 0,
        "msg": "",
        "data": {
            "data": [
                {
                    "time": "2026-07-21 13:46:12",
                    "id": "nes1",
                    "title": "腾讯营收领先",
                    "url": "https://gu.qq.com/x",
                    "src": "智研咨询",
                    "summary": "",
                },
                {
                    "time": "2026-07-21 12:00:00",
                    "id": "nes2",
                    "title": "",
                    "url": "https://gu.qq.com/y",
                    "src": "x",
                    "summary": "",
                },
            ]
        },
    }
    session.get.return_value = resp

    items = fetch_tencent_stock_news("0700.HK", n=10, session=session)
    assert len(items) == 1
    assert items[0]["title"] == "腾讯营收领先"
    assert items[0]["snippet"] == "腾讯营收领先"
    assert items[0]["source"] == "智研咨询"
    assert items[0]["provider"] == "tencent_ifzq"
    assert items[0]["symbol"] == "hk00700"
    called_url = session.get.call_args[0][0]
    assert "symbol=hk00700" in called_url
    assert "type=2" in called_url


def test_fetch_tencent_stock_news_soft_fails_on_error_code():
    session = MagicMock()
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"code": 1, "msg": "fail", "data": {}}
    session.get.return_value = resp
    assert fetch_tencent_stock_news("0700.HK", session=session) == []


def test_fetch_tencent_stock_news_soft_fails_on_http_error():
    session = MagicMock()
    session.get.side_effect = RuntimeError("network down")
    assert fetch_tencent_stock_news("600519", session=session) == []


def test_format_and_merge_news_context():
    text = format_tencent_news_context(
        [
            {
                "title": "标题A",
                "snippet": "标题A",
                "published_date": "2026-07-21",
                "source": "财联社",
                "url": "https://example.com/a",
            }
        ]
    )
    assert "标题A" in text
    assert "财联社" in text

    merged = merge_news_contexts(
        "- 标题A [2026-07-21]",
        "- 标题B [2026-07-20]\n- 标题A [dup]\n- 标题C",
        max_secondary_lines=2,
    )
    assert "标题A" in merged
    assert "标题B" in merged
    assert "标题C" in merged
    assert merged.count("标题A") == 1


def test_filter_fresh_news_items_drops_stale():
    from datetime import date

    from src.services.tencent_stock_news import filter_fresh_news_items

    today = date(2026, 7, 24)
    items = [
        {"title": "旧闻", "published_date": "2026-07-20"},
        {"title": "今日", "published_date": "2026-07-24 09:00:00"},
        {"title": "昨日", "published_date": "2026-07-23"},
        {"title": "无日期"},
    ]
    kept = filter_fresh_news_items(items, max_age_days=2, keep_undated=True, today=today)
    titles = [i["title"] for i in kept]
    assert titles[0] == "今日"
    assert "昨日" in titles
    assert "无日期" in titles
    assert "旧闻" not in titles
