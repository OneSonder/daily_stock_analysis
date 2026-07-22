# -*- coding: utf-8 -*-
"""Moonshot/Kimi short trading comments for HSI enrichment (separate from DeepSeek)."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.moonshot.cn/v1"
DEFAULT_MODEL = "kimi-k2.6"
# Moonshot Kimi k2.5/k2.6 family requires temperature=1 (thinking-default).
DEFAULT_TEMPERATURE = 1.0
DEFAULT_TIMEOUT = 60.0

_COMMENT_SYSTEM = (
    "你是港股交易点评助手（模型标识：Kimi/Moonshot）。"
    "根据给定的恒指扫描信号、技术指标、形态与新闻，用简洁中文给出独立点评。"
    "不要输出 JSON；不要复述为决策仪表盘字段；不要冒充 DeepSeek 或其他模型。"
    "开篇第一行写：【Kimi 点评】"
    "控制在 8～15 行 Markdown 段落，包含：观点、关键依据、风险、操作倾向。"
)


def get_kimi_api_key() -> str:
    return (
        (os.getenv("KIMI_API_KEY") or "").strip()
        or (os.getenv("MOONSHOT_API_KEY") or "").strip()
    )


def get_kimi_base_url() -> str:
    return (os.getenv("KIMI_BASE_URL") or DEFAULT_BASE_URL).strip().rstrip("/")


def get_kimi_model() -> str:
    return (os.getenv("KIMI_MODEL") or DEFAULT_MODEL).strip()


def is_kimi_comment_enabled() -> bool:
    """Enabled when key present, unless KIMI_COMMENT_ENABLED explicitly disables."""
    raw = (os.getenv("KIMI_COMMENT_ENABLED") or "").strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False
    if raw in {"1", "true", "yes", "on"}:
        return bool(get_kimi_api_key())
    # default: true when key present
    return bool(get_kimi_api_key())


def _build_user_prompt(context: Dict[str, Any], news_text: str) -> str:
    payload = {
        "code": context.get("code"),
        "stock_name": context.get("stock_name"),
        "date": context.get("date"),
        "today": context.get("today"),
        "realtime": context.get("realtime"),
        "hsi_signals": context.get("hsi_signals"),
        "technicals": context.get("technicals"),
        "patterns": context.get("patterns"),
        "news": (news_text or "").strip()[:4000],
    }
    return (
        "请根据以下 HSI lite 增强上下文写一段独立「Kimi 点评」：\n\n"
        f"```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```"
    )


def generate_kimi_comment(
    context: Dict[str, Any],
    news_text: str = "",
    *,
    timeout: float = DEFAULT_TIMEOUT,
    session: Optional[requests.Session] = None,
) -> str:
    """Call Moonshot/Kimi for a short comment. Soft-fails to empty string."""
    if not is_kimi_comment_enabled():
        return ""

    api_key = get_kimi_api_key()
    if not api_key:
        return ""

    base_url = get_kimi_base_url()
    model = get_kimi_model()
    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "temperature": DEFAULT_TEMPERATURE,
        "messages": [
            {"role": "system", "content": _COMMENT_SYSTEM},
            {"role": "user", "content": _build_user_prompt(context or {}, news_text or "")},
        ],
    }

    http = session or requests
    try:
        resp = http.post(url, headers=headers, json=body, timeout=timeout)
        if resp.status_code >= 400:
            # Surface API error body (no secrets) for Actions debugging.
            detail = (resp.text or "").strip()[:400]
            logger.warning(
                "Kimi comment request failed: %s %s body=%s",
                resp.status_code,
                resp.reason,
                detail,
            )
            return ""
        data = resp.json()
    except Exception as exc:
        logger.warning("Kimi comment request failed: %s", exc)
        return ""

    try:
        choices = data.get("choices") or []
        if not choices:
            logger.warning("Kimi comment empty choices: %s", data.get("error") or data)
            return ""
        message = choices[0].get("message") or {}
        content = (message.get("content") or "").strip()
        return content
    except Exception as exc:
        logger.warning("Kimi comment parse failed: %s", exc)
        return ""
