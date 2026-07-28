# -*- coding: utf-8 -*-
"""ET Net HK Top movers (HTML tables) for HSI scan universe enrichment.

Fetches Top-N from:
  http://stocks.etnet.com.hk/www/eng/stocks/realtime/top20.php?subtype={turnover|volume|up}

Losers (subtype=down) are intentionally unsupported.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlencode

import requests

logger = logging.getLogger(__name__)

ETNET_TOP20_URL = "http://stocks.etnet.com.hk/www/eng/stocks/realtime/top20.php"
ALLOWED_SUBTYPES: Tuple[str, ...] = ("turnover", "volume", "up")
DEFAULT_SUBTYPES: Tuple[str, ...] = ("turnover", "volume", "up")
DEFAULT_TOP_N = 10
DEFAULT_TIMEOUT = 15.0
DEFAULT_ENABLED = True

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_TR_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
_TD_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.IGNORECASE | re.DOTALL)
_CODE_RE = re.compile(r"^\d{1,5}$")

SUBTYPE_LABELS = {
    "turnover": "Turnover",
    "volume": "Volume",
    "up": "Gainers",
}


def etnet_code_to_yahoo(raw_code: Any) -> Optional[str]:
    """Map ET Net code ``00700`` to Yahoo/HSI form ``0700.HK``."""
    text = str(raw_code or "").strip()
    if not text or not _CODE_RE.match(text):
        return None
    try:
        return f"{int(text):04d}.HK"
    except (TypeError, ValueError):
        return None


def _strip_html(text: str) -> str:
    cleaned = _TAG_RE.sub("", text or "")
    cleaned = cleaned.replace("&nbsp;", " ").replace("&amp;", "&")
    cleaned = cleaned.replace(",", "")
    return _WS_RE.sub(" ", cleaned).strip()


def _parse_bool_env(raw: str, default: bool) -> bool:
    text = (raw or "").strip().lower()
    if not text:
        return default
    if text in ("1", "true", "yes", "on"):
        return True
    if text in ("0", "false", "no", "off"):
        return False
    return default


def normalize_subtypes(raw: Optional[Sequence[str] | str]) -> List[str]:
    """Keep only allowed subtypes; drop losers (`down`) and unknowns."""
    if raw is None:
        return list(DEFAULT_SUBTYPES)
    if isinstance(raw, str):
        parts = [p.strip().lower() for p in raw.split(",")]
    else:
        parts = [str(p or "").strip().lower() for p in raw]
    out: List[str] = []
    for part in parts:
        if not part:
            continue
        if part == "down":
            logger.warning("Ignoring ET Net subtype=down (losers not supported)")
            continue
        if part not in ALLOWED_SUBTYPES:
            logger.warning("Ignoring unsupported ET Net subtype=%r", part)
            continue
        if part not in out:
            out.append(part)
    return out or list(DEFAULT_SUBTYPES)


def resolve_etnet_top_config_from_env() -> Dict[str, Any]:
    """Resolve enabled / top_n / subtypes from env."""
    enabled = _parse_bool_env(
        os.getenv("HSI_ETNET_TOP_ENABLED", "true"),
        DEFAULT_ENABLED,
    )
    raw_n = (os.getenv("HSI_ETNET_TOP_N") or str(DEFAULT_TOP_N)).strip()
    try:
        top_n = max(1, int(raw_n))
    except (TypeError, ValueError):
        logger.warning("Invalid HSI_ETNET_TOP_N=%r, fallback to %s", raw_n, DEFAULT_TOP_N)
        top_n = DEFAULT_TOP_N
    subtypes = normalize_subtypes(os.getenv("HSI_ETNET_TOP_SUBTYPES", ",".join(DEFAULT_SUBTYPES)))
    return {
        "enabled": enabled,
        "top_n": top_n,
        "subtypes": subtypes,
    }


def parse_etnet_top_html(
    html: str,
    *,
    subtype: str,
    top_n: int = DEFAULT_TOP_N,
) -> List[Dict[str, Any]]:
    """Parse ET Net top20 HTML table into ranked rows."""
    if subtype not in ALLOWED_SUBTYPES:
        return []
    n = max(1, int(top_n))
    rows: List[Dict[str, Any]] = []
    for tr_html in _TR_RE.findall(html or ""):
        cells = [_strip_html(td) for td in _TD_RE.findall(tr_html)]
        if len(cells) < 8:
            continue
        # Header row
        if cells[0].lower() in ("no", "no.") or cells[1].lower() == "code":
            continue
        rank_raw, code_raw, name = cells[0], cells[1], cells[2]
        yahoo = etnet_code_to_yahoo(code_raw)
        if not yahoo:
            continue
        try:
            rank = int(rank_raw)
        except (TypeError, ValueError):
            rank = len(rows) + 1
        metric_label = "volume" if subtype == "volume" else "turnover"
        # Columns: No Code Name Nominal Change %Change Highest Lowest Turnover|Volume Currency
        metric_val = cells[8] if len(cells) > 8 else ""
        rows.append(
            {
                "rank": rank,
                "etnet_code": str(code_raw).strip(),
                "code": yahoo,
                "name": name,
                "nominal": cells[3] if len(cells) > 3 else "",
                "change": cells[4] if len(cells) > 4 else "",
                "change_pct": cells[5] if len(cells) > 5 else "",
                "metric": metric_val,
                "metric_label": metric_label,
                "subtype": subtype,
                "source": "etnet",
            }
        )
        if len(rows) >= n:
            break
    return rows


def fetch_etnet_top_movers(
    subtype: str = "turnover",
    top_n: int = DEFAULT_TOP_N,
    timeout: float = DEFAULT_TIMEOUT,
    session: Optional[requests.Session] = None,
) -> List[Dict[str, Any]]:
    """Fetch one ET Net top board. Soft-fail to []. Never supports down/losers."""
    key = (subtype or "").strip().lower()
    if key == "down":
        logger.warning("ET Net losers (subtype=down) are not supported")
        return []
    if key not in ALLOWED_SUBTYPES:
        logger.warning("Unsupported ET Net subtype=%r", subtype)
        return []
    url = f"{ETNET_TOP20_URL}?{urlencode({'subtype': key})}"
    http = session or requests
    try:
        resp = http.get(
            url,
            timeout=timeout,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; daily-stock-analysis/1.0)",
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        resp.raise_for_status()
        # ET Net pages are often big5 / utf-8; requests may mis-detect — try content decode.
        text = resp.text
        if (not text or "Code" not in text) and resp.content:
            for enc in ("utf-8", "big5", "big5hkscs", "gbk"):
                try:
                    candidate = resp.content.decode(enc)
                except UnicodeDecodeError:
                    continue
                if "Code" in candidate or "<tr" in candidate.lower():
                    text = candidate
                    break
        return parse_etnet_top_html(text, subtype=key, top_n=top_n)
    except Exception as exc:
        logger.warning("ET Net top movers fetch failed subtype=%s: %s", key, exc)
        return []


def fetch_etnet_top_boards(
    subtypes: Sequence[str] = DEFAULT_SUBTYPES,
    top_n: int = DEFAULT_TOP_N,
    timeout: float = DEFAULT_TIMEOUT,
    session: Optional[requests.Session] = None,
) -> Dict[str, Any]:
    """Fetch multiple boards. Returns boards dict + per-board errors."""
    wanted = normalize_subtypes(subtypes)
    boards: Dict[str, List[Dict[str, Any]]] = {}
    errors: Dict[str, str] = {}
    for subtype in wanted:
        try:
            items = fetch_etnet_top_movers(
                subtype=subtype,
                top_n=top_n,
                timeout=timeout,
                session=session,
            )
            boards[subtype] = items
            if not items:
                errors[subtype] = "empty or failed"
        except Exception as exc:
            boards[subtype] = []
            errors[subtype] = str(exc)
            logger.warning("ET Net board %s failed: %s", subtype, exc)
    return {
        "boards": boards,
        "errors": errors,
        "top_n": max(1, int(top_n)),
        "subtypes": wanted,
    }


def unique_codes_from_boards(
    boards: Dict[str, List[Dict[str, Any]]] | Iterable[List[Dict[str, Any]]],
) -> List[Dict[str, str]]:
    """Flatten boards into unique ``{code, name}`` rows (first-seen wins)."""
    if isinstance(boards, dict):
        sequences: List[List[Dict[str, Any]]] = [boards.get(k) or [] for k in ALLOWED_SUBTYPES]
        # Also include any extra keys in insertion order
        for key, rows in boards.items():
            if key not in ALLOWED_SUBTYPES:
                sequences.append(rows or [])
    else:
        sequences = list(boards)

    seen: set = set()
    out: List[Dict[str, str]] = []
    for rows in sequences:
        for row in rows or []:
            code = str(row.get("code") or "").strip().upper()
            if not code or code in seen:
                continue
            seen.add(code)
            out.append({"code": code, "name": str(row.get("name") or "").strip()})
    return out
