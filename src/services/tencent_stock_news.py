# -*- coding: utf-8 -*-
"""Tencent Finance ifzq stock news helper (HK + A-share symbols).

Unofficial endpoint used by Tencent Finance apps:
  https://web.ifzq.gtimg.cn/appstock/news/info/search?symbol=hk00700&type=2&page=1&n=10
"""

from __future__ import annotations

import logging
import os
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import requests

from data_provider.base import is_bse_code

logger = logging.getLogger(__name__)

IFZQ_NEWS_URL = "https://web.ifzq.gtimg.cn/appstock/news/info/search"
DEFAULT_NEWS_TYPE = 2
DEFAULT_PAGE = 1
DEFAULT_N = 10
DEFAULT_TIMEOUT = 10.0
DEFAULT_HSI_NEWS_MAX_AGE_DAYS = 2

_HK_SUFFIX_RE = re.compile(r"^(\d{1,5})\.hk$", re.IGNORECASE)
_HK_PREFIX_RE = re.compile(r"^hk(\d{1,5})$", re.IGNORECASE)
_A_PREFIX_RE = re.compile(r"^(sh|sz|bj)(\d{6})$", re.IGNORECASE)
_DATE_RE = re.compile(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})")


def resolve_hsi_news_max_age_days() -> int:
    """Max age (days) for HSI live news fed to DeepSeek. Default 2."""
    raw = (os.getenv("HSI_NEWS_MAX_AGE_DAYS") or str(DEFAULT_HSI_NEWS_MAX_AGE_DAYS)).strip()
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return DEFAULT_HSI_NEWS_MAX_AGE_DAYS


def parse_news_publish_date(raw: Any) -> Optional[date]:
    """Parse common news date strings to a date (local calendar day)."""
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    text = str(raw).strip()
    if not text:
        return None
    # Prefer explicit YYYY-MM-DD / YYYY/MM/DD
    m = _DATE_RE.search(text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d",
    ):
        try:
            return datetime.strptime(text[: len(fmt) + 8], fmt).date()
        except ValueError:
            continue
    return None


def filter_fresh_news_items(
    items: List[Dict[str, Any]],
    *,
    max_age_days: Optional[int] = None,
    keep_undated: bool = True,
    today: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """Keep newest items within max_age_days; drop stale dated headlines."""
    window = max_age_days if max_age_days is not None else resolve_hsi_news_max_age_days()
    window = max(1, int(window))
    cutoff = (today or date.today()) - timedelta(days=window - 1)
    kept: List[Dict[str, Any]] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        published = parse_news_publish_date(item.get("published_date") or item.get("time"))
        if published is None:
            if keep_undated:
                kept.append(item)
            continue
        if published >= cutoff:
            kept.append(item)

    def _sort_key(it: Dict[str, Any]):
        d = parse_news_publish_date(it.get("published_date") or it.get("time"))
        # Dated first (newest), then undated in original relative order.
        return (0 if d is not None else 1, -(d.toordinal()) if d else 0)

    return sorted(kept, key=_sort_key)


def is_tencent_stock_news_enabled() -> bool:
    """Return whether ifzq stock news is enabled (default true)."""
    raw = (os.getenv("TENCENT_STOCK_NEWS_ENABLED", "true") or "").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def to_ifzq_symbol(code: str) -> Optional[str]:
    """Convert repo stock codes to ifzq symbols (hk00700 / sh600519 / sz000001).

    Supports:
    - HK: ``0700.HK``, ``hk00700``, ``HK00700``, ``00700``
    - A-share: ``600519``, ``SH600519``, ``sz000001``, ``000001.SZ``
    """
    raw = (code or "").strip()
    if not raw:
        return None

    lowered = raw.lower()

    # Already-prefixed A-share / HK
    m_a = _A_PREFIX_RE.match(lowered)
    if m_a:
        return f"{m_a.group(1)}{m_a.group(2)}"

    m_hk_pref = _HK_PREFIX_RE.match(lowered)
    if m_hk_pref:
        return f"hk{m_hk_pref.group(1).zfill(5)}"

    m_hk_suf = _HK_SUFFIX_RE.match(lowered)
    if m_hk_suf:
        return f"hk{m_hk_suf.group(1).zfill(5)}"

    # Exchange suffix forms: 600519.SH / 000001.SZ / 920000.BJ
    if "." in raw:
        base, exch = raw.rsplit(".", 1)
        base = base.strip()
        exch_l = exch.strip().lower()
        if exch_l == "hk" and base.isdigit() and 1 <= len(base) <= 5:
            return f"hk{base.zfill(5)}"
        if base.isdigit() and len(base) == 6:
            if exch_l in {"sh", "ss"}:
                return f"sh{base}"
            if exch_l == "sz":
                return f"sz{base}"
            if exch_l == "bj":
                return f"bj{base}"

    # Strip common market prefixes without digits check above
    stripped = re.sub(r"^(sh|sz|bj|ss)[\.\-_]?", "", lowered, flags=re.IGNORECASE)
    if stripped != lowered and stripped.isdigit() and len(stripped) == 6:
        return _to_a_share_ifzq(stripped)

    # Bare digits
    if raw.isdigit():
        if len(raw) == 5:
            return f"hk{raw}"
        if len(raw) == 6:
            return _to_a_share_ifzq(raw)
        # 1-4 digit treated as HK pad (e.g. 700 -> hk00700) only when clearly HK context
        if 1 <= len(raw) <= 4:
            return f"hk{raw.zfill(5)}"

    return None


def _to_a_share_ifzq(base: str) -> str:
    """Map 6-digit A-share code to sh/sz/bj (same rules as Sina/Tencent quotes)."""
    if is_bse_code(base):
        return f"bj{base}"
    if base.startswith(("6", "5", "90")):
        return f"sh{base}"
    return f"sz{base}"


def _map_item(raw: Dict[str, Any], query_symbol: str) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    title = (raw.get("title") or "").strip()
    if not title:
        return None
    summary = (raw.get("summary") or "").strip()
    url = (raw.get("url") or "").strip()
    source = (raw.get("src") or "").strip() or "tencent_ifzq"
    published = (raw.get("time") or "").strip()
    return {
        "title": title,
        "snippet": summary or title,
        "url": url,
        "source": source,
        "published_date": published,
        "symbol": query_symbol,
        "provider": "tencent_ifzq",
        "id": (raw.get("id") or "").strip(),
    }


def fetch_tencent_stock_news(
    code: str,
    *,
    news_type: int = DEFAULT_NEWS_TYPE,
    page: int = DEFAULT_PAGE,
    n: int = DEFAULT_N,
    timeout: float = DEFAULT_TIMEOUT,
    session: Optional[requests.Session] = None,
) -> List[Dict[str, Any]]:
    """Fetch live stock news from ifzq. Soft-fails to [] on any error."""
    symbol = to_ifzq_symbol(code)
    if not symbol:
        logger.debug("tencent ifzq: unsupported code %r", code)
        return []

    params = {
        "symbol": symbol,
        "type": int(news_type),
        "page": max(1, int(page)),
        "n": max(1, min(50, int(n))),
    }
    url = f"{IFZQ_NEWS_URL}?{urlencode(params)}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://finance.qq.com/",
        "Accept": "application/json,text/plain,*/*",
    }

    http = session or requests
    try:
        resp = http.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        payload = resp.json()
    except Exception as exc:
        logger.warning("tencent ifzq news failed for %s (%s): %s", code, symbol, exc)
        return []

    if not isinstance(payload, dict):
        logger.warning("tencent ifzq news invalid payload for %s", symbol)
        return []

    if payload.get("code") not in (0, "0", None):
        logger.warning(
            "tencent ifzq news error for %s: code=%s msg=%s",
            symbol,
            payload.get("code"),
            payload.get("msg"),
        )
        return []

    data = payload.get("data") or {}
    items_raw = data.get("data") if isinstance(data, dict) else None
    if not isinstance(items_raw, list):
        return []

    out: List[Dict[str, Any]] = []
    for raw in items_raw:
        mapped = _map_item(raw, symbol)
        if mapped:
            out.append(mapped)
    return out


def format_tencent_news_context(items: List[Dict[str, Any]], *, max_items: int = 10) -> str:
    """Format ifzq news items into LLM/report context text (newest first when dated)."""
    if not items:
        return ""

    def _sort_key(it: Dict[str, Any]):
        d = parse_news_publish_date(it.get("published_date")) if isinstance(it, dict) else None
        return (0 if d is not None else 1, -(d.toordinal()) if d else 0)

    ordered = sorted([i for i in items if isinstance(i, dict)], key=_sort_key)
    lines: List[str] = []
    for item in ordered[: max(1, int(max_items))]:
        title = (item.get("title") or "").strip()
        if not title:
            continue
        date = (item.get("published_date") or "").strip()
        source = (item.get("source") or "").strip()
        meta_bits = [b for b in (date, source) if b]
        meta = f" [{', '.join(meta_bits)}]" if meta_bits else ""
        lines.append(f"- {title}{meta}")
        snippet = (item.get("snippet") or "").strip()
        if snippet and snippet != title:
            lines.append(f"  {snippet[:200]}")
        url = (item.get("url") or "").strip()
        if url:
            lines.append(f"  {url}")
    return "\n".join(lines)


def merge_news_contexts(
    primary: str,
    secondary: str,
    *,
    max_secondary_lines: int = 2,
) -> str:
    """Prefer primary text; append up to N non-duplicate secondary bullet lines."""
    primary = (primary or "").strip()
    secondary = (secondary or "").strip()
    if not secondary:
        return primary
    if not primary:
        return secondary

    def _bullet_key(line: str) -> str:
        key = line.lstrip("- ").strip().lower()
        if "[" in key:
            key = key.split("[", 1)[0].strip()
        return key

    primary_keys = {
        _bullet_key(line)
        for line in primary.splitlines()
        if line.strip().startswith("-") and _bullet_key(line)
    }
    extra: List[str] = []
    for line in secondary.splitlines():
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        key = _bullet_key(stripped)
        if not key or key in primary_keys:
            continue
        primary_keys.add(key)
        extra.append(stripped)
        if len(extra) >= max(0, int(max_secondary_lines)):
            break
    if not extra:
        return primary
    return primary + "\n" + "\n".join(extra)
