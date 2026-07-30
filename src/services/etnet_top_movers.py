# -*- coding: utf-8 -*-
"""ET Net HK Top movers (HTML tables) for HSI scan universe enrichment.

Fetches Top-N from Traditional Chinese pages (Chinese names):
  https://www.etnet.com.hk/www/tc/stocks/realtime/top20.php?subtype={turnover|volume|up}

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

ETNET_TOP20_URL = "https://www.etnet.com.hk/www/tc/stocks/realtime/top20.php"
ALLOWED_SUBTYPES: Tuple[str, ...] = ("turnover", "volume", "up")
DEFAULT_SUBTYPES: Tuple[str, ...] = ("turnover", "volume", "up")
DEFAULT_TOP_N = 10
DEFAULT_TIMEOUT = 15.0
DEFAULT_ENABLED = True

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_TR_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
_TD_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.IGNORECASE | re.DOTALL)
_A_TEXT_RE = re.compile(r"<a\b[^>]*>(.*?)</a>", re.IGNORECASE | re.DOTALL)
_CODE_RE = re.compile(r"^\d{1,5}$")
_AI_DIAG_RE = re.compile(r"AI\s*診股")
_PRICE_RE = re.compile(r"^-?\d[\d,]*\.?\d*%?$")

SUBTYPE_LABELS = {
    "turnover": "成交額",
    "volume": "成交股數",
    "up": "升幅",
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


def _cell_primary_text(td_html: str) -> str:
    """Prefer first anchor text (clean Chinese name / code), else full stripped cell."""
    m = _A_TEXT_RE.search(td_html or "")
    if m:
        return _strip_html(m.group(1))
    return _strip_html(td_html)


def _clean_etnet_name(name: str) -> str:
    text = _AI_DIAG_RE.sub("", name or "")
    return _WS_RE.sub(" ", text).strip()


def _looks_like_price(text: str) -> bool:
    return bool(_PRICE_RE.match((text or "").strip()))


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
    """Parse ET Net top20 HTML table into ranked rows (TC or ENG layout)."""
    if subtype not in ALLOWED_SUBTYPES:
        return []
    n = max(1, int(top_n))
    rows: List[Dict[str, Any]] = []
    for tr_html in _TR_RE.findall(html or ""):
        td_htmls = _TD_RE.findall(tr_html)
        if len(td_htmls) < 8:
            continue
        cells = [_strip_html(td) for td in td_htmls]
        # Header row (ENG or TC)
        head0 = cells[0].lower()
        head1 = cells[1]
        if head0 in ("no", "no.", "排序") or head1.lower() in ("code", "代號"):
            continue

        code_raw = _cell_primary_text(td_htmls[1])
        yahoo = etnet_code_to_yahoo(code_raw)
        if not yahoo:
            continue
        name = _clean_etnet_name(_cell_primary_text(td_htmls[2]))
        try:
            rank = int(cells[0])
        except (TypeError, ValueError):
            rank = len(rows) + 1

        # TC layout inserts an arrow column after name:
        # Rank Code Name Arrow Nominal Change %Change High Low Metric Currency
        # ENG layout:
        # Rank Code Name Nominal Change %Change High Low Metric Currency
        if len(cells) >= 10 and not _looks_like_price(cells[3]):
            nominal = cells[4] if len(cells) > 4 else ""
            change = cells[5] if len(cells) > 5 else ""
            change_pct = cells[6] if len(cells) > 6 else ""
            metric_val = cells[9] if len(cells) > 9 else ""
        else:
            nominal = cells[3] if len(cells) > 3 else ""
            change = cells[4] if len(cells) > 4 else ""
            change_pct = cells[5] if len(cells) > 5 else ""
            metric_val = cells[8] if len(cells) > 8 else ""

        metric_label = "volume" if subtype == "volume" else "turnover"
        rows.append(
            {
                "rank": rank,
                "etnet_code": str(code_raw).strip(),
                "code": yahoo,
                "name": name,
                "nominal": nominal,
                "change": change,
                "change_pct": change_pct,
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
                "Accept-Language": "zh-HK,zh-TW,zh;q=0.9,en;q=0.5",
            },
        )
        resp.raise_for_status()
        # Prefer UTF-8; fall back to common HK encodings.
        text = resp.text
        has_table = ("代號" in text) or ("Code" in text) or ("<tr" in text.lower())
        if (not text or not has_table) and resp.content:
            for enc in ("utf-8", "big5", "big5hkscs", "gbk"):
                try:
                    candidate = resp.content.decode(enc)
                except UnicodeDecodeError:
                    continue
                if "代號" in candidate or "Code" in candidate or "<tr" in candidate.lower():
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
