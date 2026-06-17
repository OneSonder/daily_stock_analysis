# -*- coding: utf-8 -*-
"""Static stock universe definitions for qualified scans."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

DOW_LIST_TOKEN = "DOW"
NASDAQ_TOP_LIST_TOKEN = "NASDAQ_TOP"
US_TOP_LIST_TOKEN = "US_TOP"
HK_ALL_LIST_TOKEN = "HK_ALL"

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
HK_ALL_STOCKS_PATH = _PROJECT_ROOT / "resources" / "universes" / "hk_all_stocks.json"

_HK_ALL_CACHE: Optional[List[Dict[str, str]]] = None


def _to_hk_yahoo_code(code: str) -> str:
    """Normalize HK codes to Yahoo ``0700.HK`` style."""
    upper = code.strip().upper()
    if upper.endswith(".HK"):
        return upper
    if upper.startswith("HK") and upper[2:].isdigit():
        return f"{int(upper[2:]):04d}.HK"
    digits = upper.lstrip("0") or "0"
    if digits.isdigit():
        return f"{int(digits):04d}.HK"
    return upper


def load_hk_all_stocks(*, force_reload: bool = False) -> List[Dict[str, str]]:
    """Load committed HK_ALL snapshot with lazy in-process cache."""
    global _HK_ALL_CACHE
    if _HK_ALL_CACHE is not None and not force_reload:
        return list(_HK_ALL_CACHE)

    if not HK_ALL_STOCKS_PATH.is_file():
        raise FileNotFoundError(
            f"HK_ALL snapshot not found: {HK_ALL_STOCKS_PATH}. "
            "Run: python scripts/generate_hk_universe.py"
        )

    raw = json.loads(HK_ALL_STOCKS_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(
            f"HK_ALL snapshot must be a JSON list, got {type(raw).__name__}"
        )

    stocks: List[Dict[str, str]] = []
    seen_codes = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        code = _to_hk_yahoo_code(str(item.get("code", "")).strip())
        if not code or code in seen_codes:
            continue
        seen_codes.add(code)
        stocks.append({
            "code": code,
            "name": str(item.get("name", "")).strip(),
        })

    if not stocks:
        raise ValueError(f"No stocks found in {HK_ALL_STOCKS_PATH}")

    _HK_ALL_CACHE = stocks
    return list(stocks)


DOW_STOCKS: List[Dict[str, str]] = [
    {"code": "AAPL", "name": "Apple Inc."},
    {"code": "AMGN", "name": "Amgen Inc."},
    {"code": "AMZN", "name": "Amazon.com Inc."},
    {"code": "AXP", "name": "American Express Co."},
    {"code": "BA", "name": "Boeing Co."},
    {"code": "CAT", "name": "Caterpillar Inc."},
    {"code": "CRM", "name": "Salesforce Inc."},
    {"code": "CSCO", "name": "Cisco Systems Inc."},
    {"code": "CVX", "name": "Chevron Corp."},
    {"code": "DIS", "name": "The Walt Disney Co."},
    {"code": "DOW", "name": "Dow Inc."},
    {"code": "GS", "name": "Goldman Sachs Group Inc."},
    {"code": "HD", "name": "Home Depot Inc."},
    {"code": "HON", "name": "Honeywell International Inc."},
    {"code": "IBM", "name": "International Business Machines Corp."},
    {"code": "JNJ", "name": "Johnson & Johnson"},
    {"code": "JPM", "name": "JPMorgan Chase & Co."},
    {"code": "KO", "name": "Coca-Cola Co."},
    {"code": "MCD", "name": "McDonald's Corp."},
    {"code": "MMM", "name": "3M Co."},
    {"code": "MRK", "name": "Merck & Co. Inc."},
    {"code": "MSFT", "name": "Microsoft Corp."},
    {"code": "NKE", "name": "Nike Inc."},
    {"code": "NVDA", "name": "NVIDIA Corp."},
    {"code": "PG", "name": "Procter & Gamble Co."},
    {"code": "SHW", "name": "Sherwin-Williams Co."},
    {"code": "TRV", "name": "Travelers Companies Inc."},
    {"code": "UNH", "name": "UnitedHealth Group Inc."},
    {"code": "V", "name": "Visa Inc."},
    {"code": "WMT", "name": "Walmart Inc."},
]

NASDAQ_TOP_STOCKS: List[Dict[str, str]] = [
    {"code": "NVDA", "name": "NVIDIA Corp."},
    {"code": "AAPL", "name": "Apple Inc."},
    {"code": "MSFT", "name": "Microsoft Corp."},
    {"code": "AMZN", "name": "Amazon.com Inc."},
    {"code": "GOOG", "name": "Alphabet Inc. Class C"},
    {"code": "GOOGL", "name": "Alphabet Inc. Class A"},
    {"code": "AVGO", "name": "Broadcom Inc."},
    {"code": "META", "name": "Meta Platforms Inc."},
    {"code": "TSLA", "name": "Tesla Inc."},
    {"code": "COST", "name": "Costco Wholesale Corp."},
    {"code": "NFLX", "name": "Netflix Inc."},
    {"code": "AMD", "name": "Advanced Micro Devices Inc."},
    {"code": "ASML", "name": "ASML Holding N.V."},
    {"code": "ADBE", "name": "Adobe Inc."},
    {"code": "PEP", "name": "PepsiCo Inc."},
    {"code": "TMUS", "name": "T-Mobile US Inc."},
    {"code": "CSCO", "name": "Cisco Systems Inc."},
    {"code": "INTU", "name": "Intuit Inc."},
    {"code": "QCOM", "name": "QUALCOMM Inc."},
    {"code": "TXN", "name": "Texas Instruments Inc."},
]


def _merge_unique_stocks(*universes: List[Dict[str, str]]) -> List[Dict[str, str]]:
    merged: List[Dict[str, str]] = []
    seen_codes = set()
    for universe in universes:
        for item in universe:
            code = str(item.get("code", "")).strip().upper()
            if not code or code in seen_codes:
                continue
            seen_codes.add(code)
            merged.append({"code": code, "name": str(item.get("name", "")).strip()})
    return merged


US_TOP_STOCKS: List[Dict[str, str]] = _merge_unique_stocks(DOW_STOCKS, NASDAQ_TOP_STOCKS)

