# -*- coding: utf-8 -*-
"""Turtle paper book: 1% units, ½N adds, 4-unit cap, Donchian exits. Simulator only."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

DEFAULT_EQUITY = 1_000_000.0
MAX_UNITS_NAME = 4
MAX_UNITS_TOTAL = 12


def _px(row: Any, column: str) -> Optional[float]:
    if row is None or column not in getattr(row, "index", []):
        return None
    value = row[column]
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number):
        return None
    return number


def unit_shares(equity: float, n_value: float) -> int:
    if n_value is None or n_value <= 0 or equity <= 0:
        return 0
    return int((0.01 * float(equity)) / float(n_value))


def _system_from_alert(alert: Dict[str, Any]) -> Optional[str]:
    if alert.get("s2_recent_close_breakout"):
        return "s2"
    if alert.get("s1_recent_close_breakout") and alert.get("s1_entry_allowed"):
        return "s1"
    if str(alert.get("bucket") or "") == "reversal" and alert.get("s1_recent_close_breakout"):
        return "s1"
    return None


def _donchian_exit_hit(hist: pd.DataFrame, day: pd.Timestamp, system: str) -> bool:
    sliced = hist.loc[hist.index <= day]
    if sliced.empty or "Low" not in sliced.columns:
        return False
    window = 10 if system == "s1" else 20
    if len(sliced) < window + 1:
        return False
    prior = sliced["Low"].iloc[-(window + 1) : -1]
    last_low = sliced["Low"].iloc[-1]
    try:
        floor = float(prior.min())
        low = float(last_low)
    except (TypeError, ValueError):
        return False
    return low < floor


def simulate_turtle_book(
    alerts: Sequence[Dict[str, Any]],
    histories: Dict[str, pd.DataFrame],
    *,
    equity: float = DEFAULT_EQUITY,
    cost_bps: float = 20.0,
    max_units_name: int = MAX_UNITS_NAME,
    max_units_total: int = MAX_UNITS_TOTAL,
    bucket: str = "uprising",
) -> Dict[str, Any]:
    """Replay a Turtle long book from monitor alerts. Separate by bucket."""
    candidates = [
        dict(alert)
        for alert in alerts
        if str(alert.get("bucket") or "") == bucket and not alert.get("is_random")
    ]
    candidates.sort(key=lambda item: (str(item.get("signal_date") or ""), str(item.get("code") or "")))
    pending: Dict[str, Dict[str, Any]] = {}
    open_pos: Dict[str, Dict[str, Any]] = {}
    closed: List[Dict[str, Any]] = []
    skipped_s1_winner = 0
    skipped_cap = 0

    calendar: List[pd.Timestamp] = []
    for frame in histories.values():
        if frame is None or frame.empty:
            continue
        calendar.extend(pd.DatetimeIndex(frame.index).normalize().tolist())
    days = sorted({pd.Timestamp(d).normalize() for d in calendar})

    alerts_by_day: Dict[pd.Timestamp, List[Dict[str, Any]]] = {}
    for alert in candidates:
        try:
            day = pd.Timestamp(alert.get("signal_date")).normalize()
        except Exception:
            continue
        alerts_by_day.setdefault(day, []).append(alert)

    def _total_units() -> int:
        return sum(int(pos.get("units") or 0) for pos in open_pos.values())

    def _close_pos(code: str, day: pd.Timestamp, price: float, reason: str) -> None:
        pos = open_pos.pop(code, None)
        if not pos:
            return
        shares = int(pos["shares_per_unit"]) * int(pos["units"])
        cost = float(pos["entry_notional"]) * max(0.0, float(cost_bps)) / 10_000.0
        pnl = (float(price) - float(pos["avg_price"])) * shares - cost
        risk = 2.0 * float(pos["n"]) * int(pos["shares_per_unit"])
        r_val = pnl / risk if risk else None
        closed.append(
            {
                "code": code,
                "bucket": bucket,
                "system": pos["system"],
                "signal_date": pos["signal_date"],
                "entry_date": pos["entry_date"],
                "exit_date": day,
                "units": pos["units"],
                "avg_price": pos["avg_price"],
                "exit": float(price),
                "exit_reason": reason,
                "n": pos["n"],
                "net": pnl,
                "r": r_val,
            }
        )

    for day in days:
        ready = [code for code, item in pending.items() if pd.Timestamp(item["entry_date"]) <= day]
        for code in ready:
            item = pending.pop(code)
            if code in open_pos:
                continue
            hist = histories.get(code)
            if hist is None or day not in hist.index:
                continue
            if _total_units() >= max_units_total:
                skipped_cap += 1
                continue
            row = hist.loc[day]
            entry = _px(row, "Open") or _px(row, "Close")
            n_value = float(item["n"])
            shares = unit_shares(equity, n_value)
            if entry is None or shares <= 0:
                continue
            open_pos[code] = {
                "system": item["system"],
                "signal_date": item["signal_date"],
                "entry_date": day,
                "units": 1,
                "shares_per_unit": shares,
                "n": n_value,
                "last_fill": entry,
                "avg_price": entry,
                "stop": entry - 2.0 * n_value,
                "entry_notional": entry * shares,
            }

        for code, pos in list(open_pos.items()):
            hist = histories.get(code)
            if hist is None or day not in hist.index:
                continue
            row = hist.loc[day]
            low = _px(row, "Low")
            high = _px(row, "High")
            close = _px(row, "Close")
            stop = float(pos["stop"])
            if low is not None and low <= stop:
                _close_pos(code, day, stop, "stop")
                continue
            if _donchian_exit_hit(hist, day, pos["system"]):
                _close_pos(code, day, close if close is not None else stop, "donchian")
                continue
            if (
                high is not None
                and int(pos["units"]) < max_units_name
                and _total_units() < max_units_total
            ):
                add_level = float(pos["last_fill"]) + 0.5 * float(pos["n"])
                if high >= add_level:
                    fill = add_level
                    open_px = _px(row, "Open")
                    if open_px is not None and open_px > add_level:
                        fill = open_px
                    shares = int(pos["shares_per_unit"])
                    new_units = int(pos["units"]) + 1
                    notional = float(pos["entry_notional"]) + fill * shares
                    pos["units"] = new_units
                    pos["last_fill"] = fill
                    pos["stop"] = fill - 2.0 * float(pos["n"])
                    pos["avg_price"] = notional / (shares * new_units)
                    pos["entry_notional"] = notional

        for alert in alerts_by_day.get(day, []):
            code = str(alert.get("code") or "").strip().upper()
            if not code or code in open_pos or code in pending:
                continue
            system = _system_from_alert(alert)
            if system is None:
                if alert.get("s1_recent_close_breakout") and not alert.get("s1_entry_allowed"):
                    skipped_s1_winner += 1
                continue
            n_value = alert.get("n")
            try:
                n_value = float(n_value)
            except (TypeError, ValueError):
                continue
            if n_value <= 0:
                continue
            hist = histories.get(code)
            if hist is None:
                continue
            later = hist.loc[hist.index > day]
            if later.empty:
                continue
            pending[code] = {
                "system": system,
                "signal_date": str(alert.get("signal_date") or ""),
                "entry_date": pd.Timestamp(later.index[0]).normalize(),
                "n": n_value,
            }

    for code in list(open_pos):
        pos = open_pos[code]
        hist = histories.get(code)
        last_px = pos["avg_price"]
        last_day = days[-1] if days else pd.Timestamp.today()
        if hist is not None and not hist.empty:
            last_day = pd.Timestamp(hist.index[-1])
            last_px = _px(hist.iloc[-1], "Close") or last_px
        _close_pos(code, last_day, float(last_px), "data_end")

    rs = [t.get("r") for t in closed if t.get("r") is not None]
    return {
        "bucket": bucket,
        "trades": closed,
        "n": len(closed),
        "avg_r": (sum(rs) / len(rs)) if rs else None,
        "hit_stop_rate": (
            sum(1 for t in closed if t.get("exit_reason") == "stop") / len(closed)
            if closed
            else None
        ),
        "skipped_s1_winner": skipped_s1_winner,
        "skipped_cap": skipped_cap,
        "max_units_seen": max((t.get("units") or 0) for t in closed) if closed else 0,
    }
