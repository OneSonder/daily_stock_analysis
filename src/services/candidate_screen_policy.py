# -*- coding: utf-8 -*-
"""Risk Officer policy for the Phase 1 US+HK candidate screen.

One hook for liquidity floors and display caps. These floors are policy for
this screen, not exchange listing minima, and they are not sized off a book.
Do not loosen them. LLM output, scores, and comments must not override them.
"""

from __future__ import annotations

from typing import Dict

# Native HKD. Replaces the retired research defaults HK$0.1 / HK$2,000,000.
HK_MIN_PRICE_HKD = 1.0
HK_MIN_AVG_TURNOVER_HKD = 20_000_000.0

# Native USD. Same fail-closed routine as Hong Kong; no FX conversion.
US_MIN_PRICE_USD = 5.0
US_MIN_AVG_TURNOVER_USD = 5_000_000.0

# 20-day average is usable only when at least this many of the last 20
# sessions have a valid close and positive turnover.
TURNOVER_WINDOW = 20
MIN_VALID_TURNOVER_SESSIONS = 15

# Display caps, not position-unit limits. Turtle ladder: single market /
# tight group / loose group / one direction. Dual listings count as one group.
CAP_SINGLE_MARKET = 4
CAP_TIGHT_GROUP = 6
CAP_LOOSE_GROUP = 10
CAP_ONE_DIRECTION = 12

# Asia/Shanghai clocks, expressed as UTC cron because Actions runs in UTC.
# HK 16:20 Mon–Fri. US 05:20 Tue–Sat (after the regular close in both EST and EDT).
HK_SCREEN_CRON_UTC = "20 8 * * 1-5"
US_SCREEN_CRON_UTC = "20 21 * * 1-5"
HK_SCREEN_LOCAL_TIME = "16:20"
US_SCREEN_LOCAL_TIME = "05:20"

# Stable paths inside the Actions artifact (also the local dry-run paths).
HK_ARTIFACT_LATEST = "reports/candidate_screen/hk/latest.md"
US_ARTIFACT_LATEST = "reports/candidate_screen/us/latest.md"

OFFICIAL_FLOORS: Dict[str, Dict[str, float | str]] = {
    "hk": {
        "currency": "HKD",
        "min_price": HK_MIN_PRICE_HKD,
        "min_avg_turnover": HK_MIN_AVG_TURNOVER_HKD,
    },
    "us": {
        "currency": "USD",
        "min_price": US_MIN_PRICE_USD,
        "min_avg_turnover": US_MIN_AVG_TURNOVER_USD,
    },
}
