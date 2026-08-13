# -*- coding: utf-8 -*-
"""Parse HSI holdings (code + buy price) from env / local file.

Primary source for Actions: ``HSI_HOLDINGS`` repo variable → env.
Local/dev may also use ``HSI_HOLDINGS_FILE``.

Formats (per line or comma-separated):
  9988.HK 125.50
  9988.HK:125.50
  9988.HK,125.50
  9988 125.50
  600519.SH 1500.00
  SZ000001 12.50
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_PAIR_FIND_RE = re.compile(
    r"(?P<code>[A-Za-z0-9.\-]+)\s*[,: ]\s*(?P<price>-?\d+(?:\.\d+)?)"
)
_CODE_DIGITS_RE = re.compile(r"^\d{1,5}$")
_A_SUFFIX_RE = re.compile(r"^(?P<code>\d{6})\.(?P<exchange>SH|SS|SZ)$")
_A_PREFIX_RE = re.compile(r"^(?P<exchange>SH|SS|SZ)(?P<code>\d{6})$")


def normalize_holding_code(raw: Any) -> Optional[str]:
    """Normalize HK and A-share holdings to exchange-suffix form."""
    text = str(raw or "").strip().upper()
    if not text:
        return None

    def _digits_to_hk(digits: str) -> str:
        core = digits.lstrip("0") or "0"
        return f"{core.zfill(4)}.HK"

    a_share = _A_SUFFIX_RE.match(text) or _A_PREFIX_RE.match(text)
    if a_share:
        exchange = a_share.group("exchange")
        canonical_exchange = "SH" if exchange == "SS" else exchange
        return f"{a_share.group('code')}.{canonical_exchange}"

    if text.endswith(".HK"):
        base = text[:-3]
        if base.isdigit():
            return _digits_to_hk(base)
        return text
    if text.startswith("HK") and text[2:].isdigit():
        return _digits_to_hk(text[2:])
    if _CODE_DIGITS_RE.match(text):
        return _digits_to_hk(text)
    return text


def parse_holdings_text(text: str) -> List[Dict[str, Any]]:
    """Parse holdings text into ``[{code, buy_price, raw}, ...]``.

    Soft-fails bad tokens (logged). Duplicate codes: last price wins.
    """
    raw = (text or "").strip()
    if not raw:
        return []

    by_code: Dict[str, Dict[str, Any]] = {}
    for m in _PAIR_FIND_RE.finditer(raw):
        code = normalize_holding_code(m.group("code"))
        if not code:
            logger.warning("Skip HSI holding with bad code: %r", m.group(0))
            continue
        try:
            price = float(m.group("price"))
        except (TypeError, ValueError):
            logger.warning("Skip HSI holding with bad price: %r", m.group(0))
            continue
        if price <= 0:
            logger.warning("Skip HSI holding with non-positive price: %r", m.group(0))
            continue
        by_code[code] = {
            "code": code,
            "buy_price": price,
            "raw": m.group(0).strip(),
        }

    return list(by_code.values())


def load_holdings_from_file(path: str) -> List[Dict[str, Any]]:
    """Load holdings from a local file path. Soft-fail to []."""
    text_path = str(path or "").strip()
    if not text_path:
        return []
    p = Path(text_path)
    try:
        if not p.is_file():
            logger.warning("HSI_HOLDINGS_FILE not found: %s", p)
            return []
        return parse_holdings_text(p.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed reading HSI_HOLDINGS_FILE=%s: %s", p, exc)
        return []


def load_holdings_from_env(
    *,
    holdings_env: str = "HSI_HOLDINGS",
    file_env: str = "HSI_HOLDINGS_FILE",
) -> List[Dict[str, Any]]:
    """Load holdings: ``HSI_HOLDINGS`` first, else ``HSI_HOLDINGS_FILE``.

    Empty → []. Never raises.
    """
    try:
        raw = (os.getenv(holdings_env) or "").strip()
        if raw:
            return parse_holdings_text(raw)
        file_path = (os.getenv(file_env) or "").strip()
        if file_path:
            return load_holdings_from_file(file_path)
        return []
    except Exception as exc:
        logger.warning("load_holdings_from_env failed: %s", exc)
        return []
