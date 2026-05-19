#!/usr/bin/env python3
"""
Scan a watchlist and filter by StockTrendAnalyzer enums.

Uses the same enums as src/stock_analyzer.py:
  TrendStatus, VolumeStatus, BuySignal, MACDStatus, RSIStatus

Examples (from repo root):
  python scripts/scan_trend_filter.py
  python scripts/scan_trend_filter.py --hsi
  python scripts/scan_trend_filter.py --hsi --buy BUY,STRONG_BUY --min-score 60 --workers 8
  python scripts/scan_trend_filter.py --stocks 600519,hk00700,AAPL
  python scripts/scan_trend_filter.py --hsi-json /path/to/HSI.json --output json
  python scripts/scan_trend_filter.py --hsi --json-out /tmp/scan.json --output table
  python scripts/scan_trend_filter.py --trend 多头排列,强势多头 --volume 缩量回调
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set, Tuple

# Allow running as: python scripts/scan_trend_filter.py
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.services.hsi_scanner import (
    HSI_STOCKS,
    _code_to_manager_format,
    is_hk_market_open,
)

# Lazy imports: stock_analyzer -> config (requires Python 3.10+)
_ANALYZER_TYPES = None


def _analyzer_types():
    global _ANALYZER_TYPES
    if _ANALYZER_TYPES is None:
        from src.stock_analyzer import (
            BuySignal,
            MACDStatus,
            RSIStatus,
            StockTrendAnalyzer,
            TrendAnalysisResult,
            TrendStatus,
            VolumeStatus,
        )
        _ANALYZER_TYPES = {
            "BuySignal": BuySignal,
            "MACDStatus": MACDStatus,
            "RSIStatus": RSIStatus,
            "StockTrendAnalyzer": StockTrendAnalyzer,
            "TrendAnalysisResult": TrendAnalysisResult,
            "TrendStatus": TrendStatus,
            "VolumeStatus": VolumeStatus,
        }
    return _ANALYZER_TYPES

logger = logging.getLogger(__name__)

HSI_LIST_TOKEN = "HSI"
DEFAULT_HSI_WORKERS = 8


@dataclass(frozen=True)
class ScanTicker:
    """One row in the scan universe."""

    display_code: str
    fetch_code: str
    name: str = ""


def _parse_enum_filters(raw: Optional[str], enum_cls: type) -> Optional[Set[Any]]:
    """Accept member names (BUY) or Chinese .value labels (买入)."""
    if not raw or not str(raw).strip():
        return None
    wanted: Set[Any] = set()
    by_name = {m.name.upper(): m for m in enum_cls}
    by_value = {m.value: m for m in enum_cls}
    for token in raw.split(","):
        t = token.strip()
        if not t:
            continue
        key = t.upper()
        if key in by_name:
            wanted.add(by_name[key])
        elif t in by_value:
            wanted.add(by_value[t])
        else:
            raise ValueError(f"Unknown {enum_cls.__name__} token: {t!r}")
    return wanted or None


def _load_hsi_from_json(path: Path) -> List[ScanTicker]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"HSI JSON must be a list, got {type(raw).__name__}")
    tickers: List[ScanTicker] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code", "")).strip()
        if not code:
            continue
        name = str(item.get("name", "")).strip()
        tickers.append(
            ScanTicker(
                display_code=code,
                fetch_code=_code_to_manager_format(code),
                name=name,
            )
        )
    if not tickers:
        raise ValueError(f"No tickers found in {path}")
    return tickers


def _load_hsi_universe(hsi_json: Optional[str] = None) -> List[ScanTicker]:
    """Built-in HSI constituents (same list as hsi_scanner / STOCK_LIST=HSI)."""
    if hsi_json:
        path = Path(hsi_json).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"HSI JSON not found: {path}")
        return _load_hsi_from_json(path)

    return [
        ScanTicker(
            display_code=item["code"],
            fetch_code=_code_to_manager_format(item["code"]),
            name=str(item.get("name", "")).strip(),
        )
        for item in HSI_STOCKS
    ]


def _default_hsi_json_candidates() -> List[Path]:
    """Parent Trae repo and local copies."""
    return [
        _REPO_ROOT.parent / "HSI.json",
        _REPO_ROOT / "HSI.json",
        _REPO_ROOT / "data" / "HSI.json",
    ]


def _resolve_universe(
    *,
    cli_stocks: Optional[str],
    use_hsi: bool,
    hsi_json: Optional[str],
) -> Tuple[List[ScanTicker], str]:
    """
    Resolve scan universe.

    Returns (tickers, universe_label) where label is 'hsi', 'watchlist', or 'custom'.
    """
    if hsi_json:
        tickers = _load_hsi_universe(hsi_json)
        return tickers, "hsi-json"

    if use_hsi:
        tickers = _load_hsi_universe()
        return tickers, "hsi"

    if cli_stocks:
        tokens = [c.strip() for c in cli_stocks.split(",") if c.strip()]
        if len(tokens) == 1 and tokens[0].upper() == HSI_LIST_TOKEN:
            return _load_hsi_universe(), "hsi"
        return [
            ScanTicker(
                display_code=token,
                fetch_code=_code_to_manager_format(token)
                if token.upper().endswith(".HK") or token.upper().startswith("HK")
                else token,
            )
            for token in tokens
        ], "custom"

    from src.config import setup_env, get_config

    setup_env()
    config = get_config()
    config.refresh_stock_list()
    codes = list(config.stock_list)
    if len(codes) == 1 and codes[0].upper() == HSI_LIST_TOKEN:
        return _load_hsi_universe(), "hsi"

    return [
        ScanTicker(
            display_code=code,
            fetch_code=_code_to_manager_format(code)
            if code.upper().endswith(".HK") or code.upper().startswith("HK")
            else code,
        )
        for code in codes
    ], "watchlist"


def _analyze_one(
    ticker: ScanTicker,
    days: int,
    analyzer: Any,
) -> Dict[str, Any]:
    from src.services.history_loader import load_history_df
    row: Dict[str, Any] = {
        "code": ticker.display_code,
        "fetch_code": ticker.fetch_code,
        "name": ticker.name,
        "status": "ok",
        "data_source": None,
    }
    df, source = load_history_df(ticker.fetch_code, days=days)
    row["data_source"] = source
    if df is None or df.empty:
        row["status"] = "no_data"
        return row
    if len(df) < 20:
        row["status"] = "insufficient_data"
        row["bars"] = len(df)
        return row

    try:
        result = analyzer.analyze(df, ticker.fetch_code)
    except Exception as exc:
        row["status"] = "error"
        row["message"] = str(exc)
        return row

    row.update(_result_to_row(result))
    return row


def _result_to_row(result: Any) -> Dict[str, Any]:
    return {
        "trend_status": result.trend_status.value,
        "volume_status": result.volume_status.value,
        "macd_status": result.macd_status.value,
        "rsi_status": result.rsi_status.value,
        "buy_signal": result.buy_signal.value,
        "signal_score": result.signal_score,
        "trend_strength": result.trend_strength,
        "bias_ma5": round(result.bias_ma5, 2),
        "current_price": result.current_price,
        "signal_reasons": result.signal_reasons,
        "risk_factors": result.risk_factors,
    }


def _passes_filters(
    row: Dict[str, Any],
    *,
    trend_wanted: Optional[Set[Any]],
    volume_wanted: Optional[Set[Any]],
    buy_wanted: Optional[Set[Any]],
    macd_wanted: Optional[Set[Any]],
    rsi_wanted: Optional[Set[Any]],
    min_score: Optional[int],
    max_score: Optional[int],
) -> bool:
    if row.get("status") != "ok":
        return False

    if min_score is not None and row.get("signal_score", 0) < min_score:
        return False
    if max_score is not None and row.get("signal_score", 0) > max_score:
        return False

    types = _analyzer_types()
    checks = (
        (trend_wanted, types["TrendStatus"], "trend_status"),
        (volume_wanted, types["VolumeStatus"], "volume_status"),
        (buy_wanted, types["BuySignal"], "buy_signal"),
        (macd_wanted, types["MACDStatus"], "macd_status"),
        (rsi_wanted, types["RSIStatus"], "rsi_status"),
    )
    for wanted, enum_cls, key in checks:
        if wanted is None:
            continue
        label = row.get(key)
        member = enum_cls(label) if label in {m.value for m in enum_cls} else None
        if member not in wanted:
            return False
    return True


def scan_and_filter(
    tickers: Iterable[ScanTicker],
    *,
    days: int = 60,
    max_workers: int = 4,
    trend_wanted: Optional[Set[Any]] = None,
    volume_wanted: Optional[Set[Any]] = None,
    buy_wanted: Optional[Set[Any]] = None,
    macd_wanted: Optional[Set[Any]] = None,
    rsi_wanted: Optional[Set[Any]] = None,
    min_score: Optional[int] = None,
    max_score: Optional[int] = None,
) -> Dict[str, Any]:
    ticker_list = list(tickers)
    analyzer = _analyzer_types()["StockTrendAnalyzer"]()
    all_rows: List[Dict[str, Any]] = []

    workers = max(1, min(max_workers, len(ticker_list) or 1))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_analyze_one, ticker, days, analyzer): ticker
            for ticker in ticker_list
        }
        for future in as_completed(futures):
            all_rows.append(future.result())

    matches = [
        r for r in all_rows
        if _passes_filters(
            r,
            trend_wanted=trend_wanted,
            volume_wanted=volume_wanted,
            buy_wanted=buy_wanted,
            macd_wanted=macd_wanted,
            rsi_wanted=rsi_wanted,
            min_score=min_score,
            max_score=max_score,
        )
    ]
    matches.sort(
        key=lambda r: (-r.get("signal_score", 0), r.get("code", ""), r.get("name", ""))
    )

    return {
        "scanned": len(ticker_list),
        "matches": matches,
        "errors": [r for r in all_rows if r.get("status") != "ok"],
        "all": all_rows,
    }


def _print_table(matches: List[Dict[str, Any]], *, show_name: bool) -> None:
    if not matches:
        print("No matches.")
        return
    if show_name:
        print("code\tname\tbuy_signal\tscore\ttrend\tvolume\tmacd\trsi\tbias_ma5")
        for r in matches:
            print(
                f"{r.get('code', '')}\t{r.get('name', '')}\t{r.get('buy_signal', '')}\t"
                f"{r.get('signal_score', '')}\t{r.get('trend_status', '')}\t"
                f"{r.get('volume_status', '')}\t{r.get('macd_status', '')}\t"
                f"{r.get('rsi_status', '')}\t{r.get('bias_ma5', '')}"
            )
    else:
        print("code\tbuy_signal\tscore\ttrend\tvolume\tmacd\trsi\tbias_ma5")
        for r in matches:
            print(
                f"{r.get('code', '')}\t{r.get('buy_signal', '')}\t{r.get('signal_score', '')}\t"
                f"{r.get('trend_status', '')}\t{r.get('volume_status', '')}\t"
                f"{r.get('macd_status', '')}\t{r.get('rsi_status', '')}\t{r.get('bias_ma5', '')}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Filter a watchlist (or HSI constituents) by trend analyzer enums",
    )
    parser.add_argument("--stocks", help="Comma-separated codes, or HSI to expand index list")
    parser.add_argument(
        "--hsi",
        action="store_true",
        help=f"Scan built-in Hang Seng Index constituents ({len(HSI_STOCKS)} names)",
    )
    parser.add_argument(
        "--hsi-json",
        metavar="PATH",
        help="Load HSI-style list from JSON [{\"code\":\"0700.HK\",\"name\":\"...\"}, ...]",
    )
    parser.add_argument(
        "--check-trading-day",
        action="store_true",
        help="Skip scan when HK market is closed today (recommended with --hsi)",
    )
    parser.add_argument("--days", type=int, default=60, help="History window (default 60)")
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help=f"Thread pool size (default: {DEFAULT_HSI_WORKERS} for HSI, else 4)",
    )
    parser.add_argument("--trend", help="TrendStatus: names (BULL) or 中文值 (多头排列)")
    parser.add_argument("--volume", help="VolumeStatus filter")
    parser.add_argument("--buy", help="BuySignal filter, e.g. BUY,STRONG_BUY or 买入")
    parser.add_argument("--macd", help="MACDStatus filter")
    parser.add_argument("--rsi", help="RSIStatus filter")
    parser.add_argument("--min-score", type=int, help="Minimum signal_score (0-100)")
    parser.add_argument("--max-score", type=int, help="Maximum signal_score")
    parser.add_argument(
        "--output",
        choices=("table", "json", "both"),
        default="table",
        help="Output format",
    )
    parser.add_argument(
        "--json-out",
        metavar="PATH",
        help="Write scan summary JSON to PATH (stable machine-readable output for tooling)",
    )
    parser.add_argument("--include-all", action="store_true", help="JSON: include non-matches")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        types = _analyzer_types()
        trend_wanted = _parse_enum_filters(args.trend, types["TrendStatus"])
        volume_wanted = _parse_enum_filters(args.volume, types["VolumeStatus"])
        buy_wanted = _parse_enum_filters(args.buy, types["BuySignal"])
        macd_wanted = _parse_enum_filters(args.macd, types["MACDStatus"])
        rsi_wanted = _parse_enum_filters(args.rsi, types["RSIStatus"])
    except ValueError as exc:
        logger.error("%s", exc)
        return 2

    hsi_json = args.hsi_json
    if not hsi_json and not args.hsi and not args.stocks:
        for candidate in _default_hsi_json_candidates():
            if candidate.is_file():
                logger.debug("Found optional HSI JSON at %s (use --hsi-json to force)", candidate)

    try:
        tickers, universe = _resolve_universe(
            cli_stocks=args.stocks,
            use_hsi=args.hsi,
            hsi_json=hsi_json,
        )
    except (FileNotFoundError, ValueError) as exc:
        logger.error("%s", exc)
        return 2

    if not tickers:
        logger.error("Empty stock list. Use --hsi, --stocks, or set STOCK_LIST in .env")
        return 1

    is_hsi = universe.startswith("hsi")
    workers = args.workers
    if workers is None:
        workers = DEFAULT_HSI_WORKERS if is_hsi else 4

    json_out_path: Optional[Path] = None
    if args.json_out:
        json_out_path = Path(args.json_out).expanduser().resolve()

    if args.check_trading_day:
        if not is_hk_market_open():
            skipped = {
                "universe": universe,
                "hsi": is_hsi,
                "skipped": True,
                "skip_reason": "HK market closed today",
                "scanned": 0,
                "match_count": 0,
                "matches": [],
                "errors": [],
            }
            logger.info("HK market closed — skipping scan")
            if args.output in ("table", "both"):
                print(f"# skipped: {skipped['skip_reason']}")
            if args.output in ("json", "both"):
                print(json.dumps(skipped, ensure_ascii=False, indent=2))
            if json_out_path is not None:
                json_out_path.parent.mkdir(parents=True, exist_ok=True)
                json_out_path.write_text(
                    json.dumps(skipped, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
            return 0

    logger.info(
        "Scanning %d tickers (universe=%s, workers=%d, days=%d)",
        len(tickers),
        universe,
        workers,
        args.days,
    )

    payload = scan_and_filter(
        tickers,
        days=args.days,
        max_workers=workers,
        trend_wanted=trend_wanted,
        volume_wanted=volume_wanted,
        buy_wanted=buy_wanted,
        macd_wanted=macd_wanted,
        rsi_wanted=rsi_wanted,
        min_score=args.min_score,
        max_score=args.max_score,
    )
    payload["universe"] = universe
    payload["hsi"] = is_hsi

    show_name = is_hsi or any(t.name for t in tickers)

    if args.output in ("table", "both"):
        label = "HSI" if is_hsi else universe
        print(f"# {label}: matches {len(payload['matches'])} / {payload['scanned']}")
        if payload["errors"]:
            print(f"# errors: {len(payload['errors'])}")
        _print_table(payload["matches"], show_name=show_name)

    out: Dict[str, Any] = {
        "universe": universe,
        "hsi": is_hsi,
        "skipped": False,
        "scanned": payload["scanned"],
        "match_count": len(payload["matches"]),
        "matches": payload["matches"],
        "errors": payload["errors"],
    }
    if args.include_all:
        out["all"] = payload["all"]

    if args.output in ("json", "both"):
        print(json.dumps(out, ensure_ascii=False, indent=2))

    if json_out_path is not None:
        json_out_path.parent.mkdir(parents=True, exist_ok=True)
        json_out_path.write_text(
            json.dumps(out, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
