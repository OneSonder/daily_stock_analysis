# -*- coding: utf-8 -*-
"""Static stock universe definitions for qualified scans."""

from __future__ import annotations

from typing import Dict, List

DOW_LIST_TOKEN = "DOW"
NASDAQ_TOP_LIST_TOKEN = "NASDAQ_TOP"
US_TOP_LIST_TOKEN = "US_TOP"


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

