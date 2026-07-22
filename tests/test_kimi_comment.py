# -*- coding: utf-8 -*-
"""Tests for Kimi/Moonshot HSI comment helper."""

from __future__ import annotations

from unittest.mock import MagicMock

from src.services.kimi_comment import (
    generate_kimi_comment,
    is_kimi_comment_enabled,
)


def test_kimi_comment_disabled_without_key(monkeypatch):
    monkeypatch.delenv("KIMI_API_KEY", raising=False)
    monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)
    monkeypatch.delenv("KIMI_COMMENT_ENABLED", raising=False)
    assert is_kimi_comment_enabled() is False
    assert generate_kimi_comment({"code": "0700.HK"}, "") == ""


def test_kimi_comment_explicitly_disabled(monkeypatch):
    monkeypatch.setenv("KIMI_API_KEY", "sk-test")
    monkeypatch.setenv("KIMI_COMMENT_ENABLED", "false")
    assert is_kimi_comment_enabled() is False


def test_generate_kimi_comment_success(monkeypatch):
    monkeypatch.setenv("KIMI_API_KEY", "sk-test")
    monkeypatch.setenv("KIMI_COMMENT_ENABLED", "true")
    monkeypatch.setenv("KIMI_MODEL", "kimi-k2.5")
    monkeypatch.setenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1")

    session = MagicMock()
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {
        "choices": [{"message": {"content": "短线偏多，关注回踩支撑。"}}]
    }
    session.post.return_value = resp

    text = generate_kimi_comment(
        {"code": "0700.HK", "stock_name": "腾讯", "technicals": {"rsi_12": 55}},
        news_text="- 新闻A",
        session=session,
    )
    assert "短线偏多" in text
    called_url = session.post.call_args[0][0]
    assert called_url.endswith("/chat/completions")
    kwargs = session.post.call_args.kwargs
    assert kwargs["json"]["temperature"] == 0.6
    assert kwargs["json"]["model"] == "kimi-k2.5"


def test_generate_kimi_comment_soft_fails(monkeypatch):
    monkeypatch.setenv("KIMI_API_KEY", "sk-test")
    monkeypatch.setenv("KIMI_COMMENT_ENABLED", "true")
    session = MagicMock()
    session.post.side_effect = RuntimeError("network")
    assert generate_kimi_comment({"code": "0700.HK"}, "", session=session) == ""
