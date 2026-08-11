# -*- coding: utf-8 -*-
"""Tests for optional Gemini HSI commentary."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from src.services.gemini_comment import (
    generate_gemini_comment,
    get_gemini_comment_model,
    is_gemini_comment_enabled,
)


def test_gemini_comment_disabled_without_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_COMMENT_ENABLED", "true")

    assert is_gemini_comment_enabled() is False
    assert generate_gemini_comment({"code": "0700.HK"}) == ""


def test_gemini_comment_default_off_even_with_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.delenv("GEMINI_COMMENT_ENABLED", raising=False)

    assert is_gemini_comment_enabled() is False


def test_gemini_comment_model_is_provider_qualified(monkeypatch):
    monkeypatch.setenv("GEMINI_COMMENT_MODEL", "gemini-3.6-flash")
    assert get_gemini_comment_model() == "gemini/gemini-3.6-flash"

    monkeypatch.setenv("GEMINI_COMMENT_MODEL", "gemini/gemini-3.1-pro")
    assert get_gemini_comment_model() == "gemini/gemini-3.1-pro"


def test_generate_gemini_comment_success(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("GEMINI_COMMENT_ENABLED", "true")
    monkeypatch.setenv("GEMINI_COMMENT_MODEL", "gemini-3.6-flash")
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="【Gemini 点评】\n短线偏多，关注回踩。")
            )
        ]
    )

    with patch("src.services.gemini_comment.litellm.completion", return_value=response) as completion:
        text = generate_gemini_comment(
            {"code": "0700.HK", "hsi_signals": {"s1_breakout": True}},
            "- 新闻A",
        )

    assert "短线偏多" in text
    kwargs = completion.call_args.kwargs
    assert kwargs["model"] == "gemini/gemini-3.6-flash"
    assert kwargs["api_key"] == "test-gemini-key"
    assert "s1_breakout" in kwargs["messages"][1]["content"]


def test_generate_gemini_comment_soft_fails(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("GEMINI_COMMENT_ENABLED", "true")

    with patch(
        "src.services.gemini_comment.litellm.completion",
        side_effect=RuntimeError("network"),
    ):
        assert generate_gemini_comment({"code": "0700.HK"}) == ""
