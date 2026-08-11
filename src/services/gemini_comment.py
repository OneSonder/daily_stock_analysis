# -*- coding: utf-8 -*-
"""Optional Gemini trading comments for HSI enrichment."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

import litellm

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-3.6-flash"
DEFAULT_TIMEOUT = 180.0
DEFAULT_MAX_TOKENS = 800

_COMMENT_SYSTEM = (
    "你是港股交易点评助手（模型标识：Gemini）。"
    "根据给定的恒指扫描信号、技术指标、形态与新闻，用简洁中文给出独立点评。"
    "不要输出 JSON；不要复述为决策仪表盘字段；不要冒充 DeepSeek、Kimi 或其他模型。"
    "开篇第一行写：【Gemini 点评】。"
    "控制在 8～15 行 Markdown 段落，包含：观点、关键依据、风险、操作倾向。"
)


def get_gemini_api_key() -> str:
    """Return the existing Gemini key shared with other official Gemini paths."""
    return (os.getenv("GEMINI_API_KEY") or "").strip()


def get_gemini_comment_model() -> str:
    model = (os.getenv("GEMINI_COMMENT_MODEL") or DEFAULT_MODEL).strip()
    if model.startswith("gemini/"):
        return model
    return f"gemini/{model}"


def is_gemini_comment_enabled() -> bool:
    """Opt-in: enabled only when the flag is truthy and a key is configured."""
    raw = (os.getenv("GEMINI_COMMENT_ENABLED") or "").strip().lower()
    if raw not in {"1", "true", "yes", "on"}:
        return False
    return bool(get_gemini_api_key())


def _build_user_prompt(context: Dict[str, Any], news_text: str) -> str:
    payload = {
        "code": context.get("code"),
        "stock_name": context.get("stock_name"),
        "date": context.get("date"),
        "today": context.get("today"),
        "realtime": context.get("realtime"),
        "hsi_signals": context.get("hsi_signals"),
        "holding": context.get("holding"),
        "technicals": context.get("technicals"),
        "patterns": context.get("patterns"),
        "news": (news_text or "").strip()[:4000],
    }
    return (
        "请根据以下 HSI lite 增强上下文写一段独立「Gemini 点评」：\n\n"
        f"```json\n{json.dumps(payload, ensure_ascii=False, indent=2, default=str)}\n```"
    )


def _extract_content(response: Any) -> str:
    choices = (
        response.get("choices", [])
        if isinstance(response, dict)
        else getattr(response, "choices", [])
    )
    if not choices:
        return ""
    choice = choices[0]
    message = (
        choice.get("message", {})
        if isinstance(choice, dict)
        else getattr(choice, "message", None)
    )
    if isinstance(message, dict):
        return str(message.get("content") or "").strip()
    return str(getattr(message, "content", "") or "").strip()


def generate_gemini_comment(
    context: Dict[str, Any],
    news_text: str = "",
    *,
    timeout: float = DEFAULT_TIMEOUT,
) -> str:
    """Generate a standalone Gemini comment and soft-fail to an empty string."""
    if not is_gemini_comment_enabled():
        return ""

    api_key = get_gemini_api_key()
    if not api_key:
        return ""

    try:
        response = litellm.completion(
            model=get_gemini_comment_model(),
            api_key=api_key,
            messages=[
                {"role": "system", "content": _COMMENT_SYSTEM},
                {
                    "role": "user",
                    "content": _build_user_prompt(context or {}, news_text or ""),
                },
            ],
            max_tokens=DEFAULT_MAX_TOKENS,
            temperature=0.3,
            timeout=timeout,
        )
        content = _extract_content(response)
        if not content:
            logger.warning("Gemini comment returned empty content")
        return content
    except Exception as exc:
        logger.warning("Gemini comment request failed: %s", exc)
        return ""
