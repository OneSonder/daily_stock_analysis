# -*- coding: utf-8 -*-
"""Phase 1 daily US+HK candidate screen.

A rules-only Yahoo scan. The main take is the close-first S1/S2 trend
first-break list from the daily monitor. It is a candidate list, not a buy
list and not a position size.

Liquidity floors live in ``candidate_screen_policy``. Missing or incomplete
prints fail the run closed and do not write a list. Display caps are separate
and are not unit limits.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import pandas as pd

from src.core.trading_calendar import get_effective_trading_date
from src.services.candidate_screen_policy import (
    CAP_LOOSE_GROUP,
    CAP_ONE_DIRECTION,
    CAP_SINGLE_MARKET,
    CAP_TIGHT_GROUP,
    HK_ARTIFACT_LATEST,
    MIN_VALID_TURNOVER_SESSIONS,
    OFFICIAL_FLOORS,
    TURNOVER_WINDOW,
    US_ARTIFACT_LATEST,
)
from src.services.daily_monitor import (
    format_uprising_suppression_banner,
    is_reversal_row,
    is_uprising_row,
    monitor_event_label,
    uprising_suppressed_by_index,
)
from src.services.hsi_scanner import HSI_STOCKS, evaluate_ticker_from_history
from src.services.stock_universes import US_TOP_STOCKS

logger = logging.getLogger(__name__)

STABLE_ARTIFACTS = {"hk": HK_ARTIFACT_LATEST, "us": US_ARTIFACT_LATEST}
INDEX_BY_MARKET = {
    "hk": ("^HSI", "恒生指数"),
    "us": ("^GSPC", "标普500"),
}
SCHEDULE_LABEL = {
    "hk": "港股工作日 16:20 Asia/Shanghai（16:08–16:10 收市竞价之后）",
    "us": "美股周二至周六 05:20 Asia/Shanghai（美东常规收盘之后，EST 与 EDT 都已收盘）",
}
RINGFENCE_ENV_KEYS = (
    "STOCK_LIST",
    "HSI_HOLDINGS",
    "HSI_HOLDINGS_FILE",
    "MONITOR_SIM_EQUITY",
)
_FORBIDDEN_EXACT = frozenset({
    "BTC",
    "BTC-USD",
    "XBT",
    "XBT-USD",
    "ETH",
    "ETH-USD",
    "GC=F",
    "MGC=F",
    "SI=F",
    "HG=F",
    "GOLD",
    "GLD",
    "IAU",
    "SGOL",
    "BRONZE",
    "COPPER",
})
# Dual listings share one company id. Both prints stay in their own currency.
_DUAL_COMPANY = {
    "GOOG": "alphabet",
    "GOOGL": "alphabet",
    "9988.HK": "alibaba",
    "BABA": "alibaba",
    "0700.HK": "tencent",
    "TCEHY": "tencent",
    "9618.HK": "jd",
    "JD": "jd",
    "9888.HK": "baidu",
    "BIDU": "baidu",
    "9999.HK": "netease",
    "NTES": "netease",
    "1211.HK": "byd",
    "BYDDY": "byd",
    "1810.HK": "xiaomi",
    "3690.HK": "meituan",
    "2015.HK": "li_auto",
    "LI": "li_auto",
    "9961.HK": "trip",
    "TCOM": "trip",
    "9901.HK": "new_oriental",
    "EDU": "new_oriental",
    "1024.HK": "kuaishou",
    "2057.HK": "zto",
    "ZTO": "zto",
    "0981.HK": "smic",
    "0005.HK": "hsbc",
    "HSBC": "hsbc",
}
_TIGHT_MEMBERS = {
    "hk_internet": [
        "0700.HK", "9988.HK", "3690.HK", "9618.HK", "9888.HK", "9999.HK",
        "1024.HK", "9961.HK", "9901.HK", "6618.HK", "0241.HK", "BABA", "JD",
        "BIDU", "NTES", "TCEHY", "TCOM", "EDU",
    ],
    "hk_banks": ["0005.HK", "0939.HK", "1398.HK", "3988.HK", "3328.HK", "3968.HK", "2388.HK", "HSBC"],
    "hk_insurance": ["1299.HK", "2318.HK", "2628.HK"],
    "hk_property": [
        "0001.HK", "0012.HK", "0016.HK", "0066.HK", "0688.HK", "0823.HK",
        "0960.HK", "1109.HK", "1113.HK", "1209.HK", "1997.HK",
    ],
    "hk_energy": ["0386.HK", "0836.HK", "0857.HK", "0883.HK", "1088.HK", "1193.HK", "2688.HK"],
    "hk_autos": ["0175.HK", "0881.HK", "1211.HK", "2015.HK", "2333.HK", "BYDDY", "LI"],
    "hk_health": ["1093.HK", "1099.HK", "1177.HK", "2269.HK", "2359.HK", "3692.HK"],
    "hk_consumer": [
        "0151.HK", "0288.HK", "0291.HK", "0322.HK", "1044.HK", "1876.HK",
        "1880.HK", "1929.HK", "2020.HK", "2313.HK", "2319.HK", "2331.HK",
        "6862.HK", "9633.HK", "9992.HK",
    ],
    "hk_hardware": ["0285.HK", "0522.HK", "0669.HK", "0981.HK", "0992.HK", "1810.HK", "2382.HK"],
    "hk_telecom": ["0728.HK", "0762.HK", "0941.HK"],
    "hk_utilities": ["0002.HK", "0003.HK", "0006.HK", "1038.HK"],
    "hk_materials": ["1378.HK", "2899.HK"],
    "hk_casinos": ["0027.HK", "1928.HK"],
    "us_platforms": ["AAPL", "MSFT", "AMZN", "GOOG", "GOOGL", "META", "NFLX"],
    "us_semis": ["NVDA", "AVGO", "AMD", "ASML", "QCOM", "TXN"],
    "us_software": ["ADBE", "CRM", "CSCO", "IBM", "INTU"],
    "us_consumer_disc": ["DIS", "HD", "MCD", "NKE", "TSLA"],
    "us_staples": ["COST", "KO", "PEP", "PG", "WMT"],
    "us_health": ["AMGN", "JNJ", "MRK", "UNH"],
    "us_financials": ["AXP", "GS", "JPM", "TRV", "V"],
    "us_industrials": ["BA", "CAT", "DOW", "HON", "MMM"],
    "us_energy": ["CVX"],
    "us_telecom": ["TMUS"],
    "us_materials": ["SHW"],
}
_LOOSE_OF_TIGHT = {
    "hk_internet": "communication",
    "hk_telecom": "communication",
    "us_platforms": "communication",
    "us_telecom": "communication",
    "hk_hardware": "technology",
    "us_semis": "technology",
    "us_software": "technology",
    "hk_consumer": "consumer",
    "hk_autos": "consumer",
    "hk_casinos": "consumer",
    "us_consumer_disc": "consumer",
    "us_staples": "consumer",
    "hk_banks": "financials",
    "hk_insurance": "financials",
    "us_financials": "financials",
    "hk_health": "health",
    "us_health": "health",
    "hk_energy": "energy",
    "us_energy": "energy",
    "hk_property": "properties",
    "hk_utilities": "utilities",
    "hk_materials": "materials",
    "us_materials": "materials",
    "us_industrials": "industrials",
}
_TIGHT_OF_CODE = {
    code: tight
    for tight, members in _TIGHT_MEMBERS.items()
    for code in members
}


class CandidateScreenDataError(RuntimeError):
    """Missing or incomplete data. The markdown take must not be written."""


@dataclass(frozen=True)
class LiquidityFloors:
    currency: str
    min_price: float
    min_avg_turnover: float


def official_floors(market: str) -> LiquidityFloors:
    """Return the Risk Officer floors for one market. No env override."""
    key = str(market or "").strip().lower()
    raw = OFFICIAL_FLOORS.get(key)
    if raw is None:
        raise CandidateScreenDataError(f"no official liquidity floors for market {market!r}")
    return LiquidityFloors(
        currency=str(raw["currency"]),
        min_price=float(raw["min_price"]),
        min_avg_turnover=float(raw["min_avg_turnover"]),
    )


def passes_official_floor(close: float, avg_turnover: float, market: str) -> bool:
    """Compare native-currency close and turnover with the official floors."""
    floors = official_floors(market)
    return float(close) >= floors.min_price and float(avg_turnover) >= floors.min_avg_turnover


def is_forbidden_listing(code: str) -> bool:
    """A-shares, gold, bronze, and BTC never enter this routine."""
    raw = str(code or "").strip().upper()
    if not raw or raw in _FORBIDDEN_EXACT:
        return True
    if raw.endswith((".SH", ".SZ", ".SS")):
        return True
    if raw.startswith(("SH", "SZ")) and raw[2:].isdigit():
        return True
    if raw.isdigit() and len(raw) == 6:
        return True
    if "BTC" in raw or raw.startswith("XBT"):
        return True
    return False


def correlation_profile(code: str) -> Dict[str, str]:
    """Company / tight / loose ids. Dual listings share one company id."""
    key = str(code or "").strip().upper()
    company = _DUAL_COMPANY.get(key, key)
    tight = _TIGHT_OF_CODE.get(key) or f"solo:{company}"
    loose = _LOOSE_OF_TIGHT.get(tight) or f"solo:{company}"
    return {"company_id": company, "tight_group": tight, "loose_group": loose}


def display_cap_block_reason(
    *,
    market_count: int,
    tight_count: int,
    loose_count: int,
    direction_count: int,
) -> Optional[str]:
    """Why one more company cannot be shown. None means the slot is free."""
    if market_count >= CAP_SINGLE_MARKET:
        return "single_market"
    if tight_count >= CAP_TIGHT_GROUP:
        return "tight_group"
    if loose_count >= CAP_LOOSE_GROUP:
        return "loose_group"
    if direction_count >= CAP_ONE_DIRECTION:
        return "one_direction"
    return None


def load_daily_universe(market: str) -> List[Dict[str, str]]:
    """Hang Seng constituents or US_TOP. Not HK_ALL and not an open US universe."""
    key = str(market or "").strip().lower()
    if key == "hk":
        source = HSI_STOCKS
    elif key == "us":
        source = US_TOP_STOCKS
    else:
        raise CandidateScreenDataError(f"Phase 1 market must be hk or us, got {market!r}")
    stocks = [
        {
            "code": str(item.get("code") or "").strip().upper(),
            "name": str(item.get("name") or "").strip(),
            "market": key,
        }
        for item in source
    ]
    validate_universe(stocks, market=key)
    return stocks


def validate_universe(stocks: Sequence[Mapping[str, str]], *, market: str) -> None:
    """Reject anything outside the Phase 1 list or on the forbidden denylist."""
    allowed = {
        str(item.get("code") or "").strip().upper()
        for item in (HSI_STOCKS if market == "hk" else US_TOP_STOCKS)
    }
    extras: List[str] = []
    banned: List[str] = []
    for item in stocks or []:
        code = str(item.get("code") or "").strip().upper()
        if not code or code not in allowed:
            extras.append(code or "?")
        if is_forbidden_listing(code):
            banned.append(code)
    if banned:
        raise CandidateScreenDataError(
            "forbidden listing in candidate screen: " + ", ".join(banned)
        )
    if extras:
        raise CandidateScreenDataError(
            "universe is outside the Phase 1 daily set: " + ", ".join(extras[:12])
        )


def resolve_as_of(market: str, current_time: Optional[datetime] = None) -> date:
    """Session date for this scan. Every path goes through get_effective_trading_date."""
    return get_effective_trading_date(market, current_time=current_time)


def _is_finite_positive(value: Any) -> bool:
    try:
        if value is None or pd.isna(value):
            return False
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def _bar_date(value: Any, market: str) -> date:
    """Session date stamped on the bar.

    Yahoo labels a daily bar with the session date in the timestamp's own
    timezone. Converting that instant into another zone can move the date
    backward and fail a complete print.
    """
    del market
    ts = pd.Timestamp(value)
    if pd.isna(ts):
        raise CandidateScreenDataError("bar date missing")
    return ts.date()


def _normalize_ohlcv(hist: pd.DataFrame) -> pd.DataFrame:
    frame = hist.copy()
    rename = {}
    for col in frame.columns:
        lowered = str(col).lower()
        if lowered in {"open", "high", "low", "close", "volume"}:
            rename[col] = lowered.title()
    if rename:
        frame = frame.rename(columns=rename)
    if "Close" not in frame.columns:
        raise CandidateScreenDataError("missing price")
    return frame


def prepare_session_frame(
    hist: pd.DataFrame,
    *,
    market: str,
    as_of: date,
) -> pd.DataFrame:
    """Keep bars through the effective session. Missing as-of print fails closed."""
    if hist is None or hist.empty:
        raise CandidateScreenDataError("missing price")
    frame = _normalize_ohlcv(hist)
    frame = frame.dropna(how="all")
    if frame.empty:
        raise CandidateScreenDataError("missing price")
    while len(frame):
        last_date = _bar_date(frame.index[-1], market)
        if last_date > as_of:
            frame = frame.iloc[:-1]
            continue
        break
    if frame.empty:
        raise CandidateScreenDataError("missing price")
    last_date = _bar_date(frame.index[-1], market)
    if last_date != as_of:
        raise CandidateScreenDataError(
            f"as-of bar missing: last bar {last_date.isoformat()} != session {as_of.isoformat()}"
        )
    if not _is_finite_positive(frame["Close"].iloc[-1]):
        raise CandidateScreenDataError("as-of close missing")
    return frame


def measure_liquidity(
    hist: pd.DataFrame,
    *,
    market: str,
    as_of: date,
) -> Dict[str, Any]:
    """Native-currency close and 20-day turnover. Incomplete prints raise.

    The average uses only sessions inside the last 20 that have a valid close
    and positive turnover, and only when at least 15 of those 20 qualify.
    The as-of bar itself must have positive turnover. No FX conversion.
    """
    frame = prepare_session_frame(hist, market=market, as_of=as_of)
    if "Volume" not in frame.columns:
        raise CandidateScreenDataError("20-day average turnover cannot be computed")
    close = float(frame["Close"].iloc[-1])
    volume = frame["Volume"].iloc[-1]
    if not _is_finite_positive(volume):
        raise CandidateScreenDataError("as-of bar has zero turnover or is suspended")
    as_of_turnover = close * float(volume)
    if as_of_turnover <= 0:
        raise CandidateScreenDataError("as-of bar has zero turnover or is suspended")
    if len(frame) < TURNOVER_WINDOW:
        raise CandidateScreenDataError("20-day average turnover cannot be computed")
    window = frame.iloc[-TURNOVER_WINDOW:]
    valid: List[float] = []
    for _, row in window.iterrows():
        if _is_finite_positive(row.get("Close")) and _is_finite_positive(row.get("Volume")):
            turnover = float(row["Close"]) * float(row["Volume"])
            if turnover > 0:
                valid.append(turnover)
    if len(valid) < MIN_VALID_TURNOVER_SESSIONS:
        raise CandidateScreenDataError(
            f"only {len(valid)} of the last {TURNOVER_WINDOW} sessions have a valid close and positive turnover"
        )
    floors = official_floors(market)
    return {
        "close_raw": close,
        "as_of_turnover": as_of_turnover,
        "avg_turnover_20": sum(valid) / len(valid),
        "turnover_valid_sessions": len(valid),
        "currency": floors.currency,
        "bar_date": as_of.isoformat(),
    }


def _sort_key(row: Mapping[str, Any]) -> tuple:
    s2_first = 0 if row.get("s2_recent_close_breakout") else 1
    try:
        ext = float(row["breakout_extension_n"]) if row.get("breakout_extension_n") is not None else 10_000.0
    except (TypeError, ValueError):
        ext = 10_000.0
    return (s2_first, ext, str(row.get("code") or ""))


def apply_display_caps(rows: Sequence[Mapping[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Cap shown companies at 4 / 6 / 10 / 12. Dual listings count once.

    Every qualifying listing of an admitted company is shown, in its own
    currency. A second listing does not take another cap slot.
    """
    ordered = sorted((dict(row) for row in rows or []), key=_sort_key)
    by_company: Dict[str, List[Dict[str, Any]]] = {}
    order: List[str] = []
    for row in ordered:
        profile = correlation_profile(str(row.get("code") or ""))
        company = str(row.get("company_id") or profile["company_id"])
        row["company_id"] = company
        row["tight_group"] = str(row.get("tight_group") or profile["tight_group"])
        row["loose_group"] = str(row.get("loose_group") or profile["loose_group"])
        if company not in by_company:
            by_company[company] = []
            order.append(company)
        by_company[company].append(row)

    market_counts: Dict[str, int] = {}
    tight_counts: Dict[str, int] = {}
    loose_counts: Dict[str, int] = {}
    direction = 0
    shown: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []
    for company in order:
        listings = by_company[company]
        primary = listings[0]
        market = str(primary.get("market") or "")
        tight = str(primary.get("tight_group") or "")
        loose = str(primary.get("loose_group") or "")
        reason = display_cap_block_reason(
            market_count=market_counts.get(market, 0),
            tight_count=tight_counts.get(tight, 0),
            loose_count=loose_counts.get(loose, 0),
            direction_count=direction,
        )
        if reason:
            for row in listings:
                rejected.append({**row, "cap_reason": reason})
            continue
        market_counts[market] = market_counts.get(market, 0) + 1
        tight_counts[tight] = tight_counts.get(tight, 0) + 1
        loose_counts[loose] = loose_counts.get(loose, 0) + 1
        direction += 1
        for offset, row in enumerate(listings):
            shown.append({**row, "cap_role": "primary" if offset == 0 else "dual"})
    return shown, rejected


def _attach_profile(row: Mapping[str, Any], *, market: str) -> Dict[str, Any]:
    item = dict(row)
    code = str(item.get("code") or "").strip().upper()
    if is_forbidden_listing(code):
        raise CandidateScreenDataError(f"forbidden listing {code}")
    item["code"] = code
    item["market"] = market
    floors = official_floors(market)
    item["currency"] = floors.currency
    item.update(correlation_profile(code))
    return item


def select_candidates(
    rows: Sequence[Mapping[str, Any]],
    *,
    market: str,
    index_trend_ok: Optional[bool] = None,
) -> Dict[str, Any]:
    """Close-first S1/S2 only. Score, MACD, and FX fields do not admit or veto."""
    floors = official_floors(market)
    below_floor: List[Dict[str, Any]] = []
    uprising: List[Dict[str, Any]] = []
    reversal: List[Dict[str, Any]] = []
    for raw in rows or []:
        row = _attach_profile(raw, market=market)
        close = row.get("close_raw", row.get("close"))
        turnover = row.get("avg_turnover_20")
        if close is None or turnover is None:
            raise CandidateScreenDataError(f"{row.get('code')}: missing price or turnover")
        try:
            close_value = float(close)
            turnover_value = float(turnover)
        except (TypeError, ValueError) as exc:
            raise CandidateScreenDataError(
                f"{row.get('code')}: missing price or turnover"
            ) from exc
        if not passes_official_floor(close_value, turnover_value, market):
            below_floor.append(row)
            continue
        if is_uprising_row(row):
            uprising.append(row)
        elif is_reversal_row(row):
            reversal.append(row)
    suppressed = uprising_suppressed_by_index(index_trend_ok)
    if suppressed:
        uprising = []
    for row in uprising + reversal:
        if row.get("n") is None or row.get("stop_long_2n") is None or row.get("close") is None:
            raise CandidateScreenDataError(f"{row.get('code')}: missing N or 2N stop")
    shown, capped = apply_display_caps(uprising)
    rev_shown, rev_capped = apply_display_caps(reversal)
    return {
        "market": market,
        "currency": floors.currency,
        "floors": {
            "min_price": floors.min_price,
            "min_avg_turnover": floors.min_avg_turnover,
            "currency": floors.currency,
        },
        "uprising": shown,
        "uprising_capped": capped,
        "reversal": rev_shown,
        "reversal_capped": rev_capped,
        "below_floor": below_floor,
        "uprising_suppressed": suppressed,
        "index_trend_ok": index_trend_ok,
    }


def _price(value: Any, currency: str, digits: int) -> str:
    return f"{float(value):.{digits}f} {currency}"


def format_candidate_report(payload: Mapping[str, Any]) -> str:
    """One daily take. Trend first-breaks are the feed; reversal is an appendix."""
    market = str(payload.get("market") or "")
    currency = str(payload.get("currency") or official_floors(market).currency)
    floors = payload.get("floors") or {}
    as_of = payload.get("as_of") or ""
    bar_date = payload.get("bar_date") or ""
    lines: List[str] = [
        f"# 候选筛选 — {'港股' if market == 'hk' else '美股'} — 趋势首破",
        "",
        "规则筛选出的可能选择，不是买入清单，也不是交易预言。",
        "主名单只收每日监控的收盘价首次突破（S1/S2 Close）。不用 High-only 通道，不用分数、交叉标签、新闻或模型点评。",
        "",
        "## 时段",
        "",
        f"- 市场: {market}",
        f"- 日程: {SCHEDULE_LABEL.get(market, market)}",
        f"- as-of session: {as_of}（get_effective_trading_date）",
        f"- bar date: {bar_date}",
        f"- 货币: {currency}（只用该上市地价格，不把 HKD/USD/CNY 互相换算）",
        (
            f"- 流动性门槛: 收盘 ≥ {floors.get('min_price')} {currency}"
            f"；20 日均成交额 ≥ {floors.get('min_avg_turnover')} {currency}"
            f"；最近 {TURNOVER_WINDOW} 个交易日里至少 {MIN_VALID_TURNOVER_SESSIONS} 日有有效收盘和正成交额"
        ),
        (
            f"- 显示上限（不是头寸单位）: 单市场 {CAP_SINGLE_MARKET}"
            f" / 紧密组 {CAP_TIGHT_GROUP} / 松散组 {CAP_LOOSE_GROUP}"
            f" / 单方向 {CAP_ONE_DIRECTION}。双重上市按一家公司计。"
        ),
        f"- 股票池: {payload.get('universe_label')}",
        f"- 未过流动性门槛: {len(payload.get('below_floor') or [])}",
        "",
    ]
    index_regime = payload.get("index_regime") or {}
    if index_regime:
        trend = index_regime.get("turtle_trend_ok")
        trend_txt = "通过" if trend is True else ("未过" if trend is False else "数据不足")
        lines.append(f"- 指数 {index_regime.get('name') or ''}: 趋势{trend_txt}")
        lines.append("")
    if payload.get("uprising_suppressed"):
        lines.append(format_uprising_suppression_banner(payload.get("index_trend_ok")))
        lines.append("")

    def _tri_state_bool(value: Any) -> str:
        if value is True:
            return "是"
        if value is False:
            return "否"
        return "—"

    def _gate_extension(value: Any) -> str:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return "—"
        try:
            return f"{float(value):.2f}"
        except (TypeError, ValueError):
            return "—"

    def _table(rows: Sequence[Mapping[str, Any]]) -> List[str]:
        from src.services.hsi_scanner import format_ma100_cell

        out = [
            "| 代号 | 名称 | 货币 | 收盘 | N | 2N止损 | 事件 | S1开仓 | 趋势 | MA100 | 延伸N | 放量 | 公司 | 紧密组 | 松散组 |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for row in rows:
            ccy = str(row.get("currency") or currency)
            out.append(
                "| {code} | {name} | {ccy} | {close} | {n} | {stop} | {event} | {s1} | {trend} | {ma100} | {ext} | {vol} | {company} | {tight} | {loose} |".format(
                    code=row.get("code") or "",
                    name=row.get("name") or "",
                    ccy=ccy,
                    close=_price(row.get("close"), ccy, 2),
                    n=_price(row.get("n"), ccy, 4),
                    stop=_price(row.get("stop_long_2n"), ccy, 2),
                    event=row.get("monitor_event") or monitor_event_label(dict(row)),
                    s1=_tri_state_bool(row.get("s1_entry_allowed")),
                    trend=_tri_state_bool(row.get("turtle_trend_ok")),
                    ma100=format_ma100_cell(row.get("close_vs_ma100")),
                    ext=_gate_extension(row.get("breakout_extension_n")),
                    vol=_tri_state_bool(row.get("volume_confirm")),
                    company=row.get("company_id") or "",
                    tight=row.get("tight_group") or "",
                    loose=row.get("loose_group") or "",
                )
            )
        return out

    uprising = list(payload.get("uprising") or [])
    lines.append("## 趋势首破")
    lines.append("")
    lines.append("这是本日唯一主名单。N 是 20 日 ATR，2N止损 = 收盘 − 2N，两者都只是价格，不含买卖数量，也不含名义金额。")
    lines.append("")
    if uprising:
        capped = len(payload.get("uprising_capped") or [])
        lines.append(
            f"显示 {len({row.get('company_id') for row in uprising})} 家公司（{len(uprising)} 个上市代码）。"
        )
        if capped:
            lines.append(f"因显示上限未列入 {capped} 个代码。")
        lines.append("")
        lines.extend(_table(uprising))
        lines.append("")
    else:
        lines.append("没有股票符合趋势首破条件。")
        lines.append("")

    lines.append("## 附录：止跌转折")
    lines.append("")
    lines.append("附录，不是本日主名单，也不与趋势首破混在同一张表里。")
    lines.append("")
    reversal = list(payload.get("reversal") or [])
    if reversal:
        lines.extend(_table(reversal))
        lines.append("")
    else:
        lines.append("没有股票符合止跌转折条件。")
        lines.append("")
    lines.append("本筛选不读取、不写回 STOCK_LIST、工作台或 HSI_HOLDINGS，也不使用模拟权益作为账本。")
    lines.append("")
    return "\n".join(lines)


def _artifact_paths(reports_dir: Path, market: str, as_of: date) -> Tuple[Path, Path]:
    root = reports_dir / "candidate_screen" / market
    if "workbench" in {part.lower() for part in root.parts}:
        raise CandidateScreenDataError("refusing to write inside a workbench path")
    return root / f"{as_of.isoformat()}.md", root / "latest.md"


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _snapshot_book_env() -> Dict[str, Optional[str]]:
    return {key: os.environ.get(key) for key in RINGFENCE_ENV_KEYS}


def _ensure_book_unchanged(before: Mapping[str, Optional[str]]) -> None:
    after = _snapshot_book_env()
    if dict(after) != dict(before):
        raise CandidateScreenDataError("official book environment changed during the scan")


def _fetch_histories(codes: Sequence[str]) -> Dict[str, pd.DataFrame]:
    from src.services.hsi_scanner import fetch_history_batch_yfinance

    try:
        return fetch_history_batch_yfinance(list(codes), "1y", batch_size=40)
    except Exception as exc:
        raise CandidateScreenDataError(f"Yahoo history download failed: {exc}") from exc


def _index_regime(
    market: str,
    *,
    as_of: date,
    index_history: Optional[pd.DataFrame],
    fetch: bool,
) -> Dict[str, Any]:
    code, name = INDEX_BY_MARKET[market]
    hist = index_history
    if hist is None and fetch:
        try:
            downloaded = _fetch_histories([code])
            hist = downloaded.get(code)
        except CandidateScreenDataError as exc:
            logger.warning("Index history unavailable for %s: %s", code, exc)
            hist = None
    if hist is None or hist.empty:
        return {"code": code, "name": name, "status": "empty", "turtle_trend_ok": None}
    try:
        sliced = prepare_session_frame(hist, market=market, as_of=as_of)
        evaluated = evaluate_ticker_from_history(code, name, sliced)
    except Exception as exc:
        logger.warning("Index evaluation failed for %s: %s", code, exc)
        return {"code": code, "name": name, "status": "error", "turtle_trend_ok": None}
    if evaluated.get("status") != "ok":
        return {"code": code, "name": name, "status": evaluated.get("status"), "turtle_trend_ok": None}
    return {
        "code": code,
        "name": name,
        "status": "ok",
        "turtle_trend_ok": bool(evaluated.get("turtle_trend_ok")),
    }


def run_candidate_screen(
    *,
    market: str,
    current_time: Optional[datetime] = None,
    reports_dir: Path | str = "reports",
    histories: Optional[Mapping[str, pd.DataFrame]] = None,
    universe: Optional[Sequence[Mapping[str, str]]] = None,
    index_trend_ok: Optional[bool] = None,
    index_history: Optional[pd.DataFrame] = None,
    fetch: Optional[bool] = None,
) -> Dict[str, Any]:
    """Evaluate one market and write the markdown take. Fail closed writes nothing."""
    key = str(market or "").strip().lower()
    book_before = _snapshot_book_env()
    stocks = list(universe) if universe is not None else load_daily_universe(key)
    validate_universe(stocks, market=key)
    as_of = resolve_as_of(key, current_time=current_time)
    should_fetch = histories is None if fetch is None else bool(fetch)
    frames: Dict[str, pd.DataFrame] = dict(histories or {})
    index_code = INDEX_BY_MARKET[key][0]
    if should_fetch:
        codes = [str(item.get("code") or "") for item in stocks]
        if index_code not in codes:
            codes.append(index_code)
        frames = _fetch_histories(codes)

    errors: List[str] = []
    measured: List[Dict[str, Any]] = []
    for item in stocks:
        code = str(item.get("code") or "").strip().upper()
        name = str(item.get("name") or code)
        hist = frames.get(code)
        try:
            if hist is None or getattr(hist, "empty", True):
                raise CandidateScreenDataError("missing price")
            liquidity = measure_liquidity(hist, market=key, as_of=as_of)
            sliced = prepare_session_frame(hist, market=key, as_of=as_of)
            evaluated = evaluate_ticker_from_history(code, name, sliced)
            if evaluated.get("status") != "ok" or evaluated.get("close") is None:
                raise CandidateScreenDataError(evaluated.get("message") or "missing price")
            if str(evaluated.get("date") or "") != as_of.isoformat():
                raise CandidateScreenDataError(
                    f"bar date {evaluated.get('date')} != as-of session {as_of.isoformat()}"
                )
            evaluated.update(liquidity)
            evaluated["market"] = key
            evaluated["name"] = name
            measured.append(evaluated)
        except CandidateScreenDataError as exc:
            errors.append(f"{code}: {exc}")

    if errors:
        _ensure_book_unchanged(book_before)
        preview = "; ".join(errors[:12])
        extra = len(errors) - 12
        suffix = f" (+{extra} more)" if extra > 0 else ""
        raise CandidateScreenDataError(f"fail closed; no list written. {preview}{suffix}")

    if index_trend_ok is None:
        prefetched = index_history if index_history is not None else frames.get(index_code)
        regime = _index_regime(
            key,
            as_of=as_of,
            index_history=prefetched,
            fetch=should_fetch and prefetched is None,
        )
        flag = regime.get("turtle_trend_ok")
        index_flag = bool(flag) if regime.get("status") == "ok" else None
    else:
        regime = {
            "code": INDEX_BY_MARKET[key][0],
            "name": INDEX_BY_MARKET[key][1],
            "status": "override",
            "turtle_trend_ok": index_trend_ok,
        }
        index_flag = index_trend_ok

    selected = select_candidates(measured, market=key, index_trend_ok=index_flag)
    selected["as_of"] = as_of.isoformat()
    selected["bar_date"] = as_of.isoformat()
    selected["index_regime"] = regime
    selected["universe_label"] = "恒指成分" if key == "hk" else "US_TOP"
    selected["universe_size"] = len(stocks)
    text = format_candidate_report(selected)
    dated, latest = _artifact_paths(Path(reports_dir), key, as_of)
    _atomic_write(dated, text)
    _atomic_write(latest, text)
    _ensure_book_unchanged(book_before)
    selected["report_text"] = text
    selected["artifact_dated"] = str(dated)
    selected["artifact_latest"] = str(latest)
    selected["stable_artifact"] = STABLE_ARTIFACTS[key]
    return selected
