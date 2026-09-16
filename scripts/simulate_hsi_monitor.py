#!/usr/bin/env python3
"""Replay the daily monitor on cached/Yahoo history. No LLM.

Examples (from repo root):
  python scripts/simulate_hsi_monitor.py
  python scripts/simulate_hsi_monitor.py --period 2y --horizon 20 --limit 10
  python scripts/simulate_hsi_monitor.py --book turtle
  python scripts/simulate_hsi_monitor.py --universe hk --codes 0700.HK,0005.HK --period 2y
  python scripts/simulate_hsi_monitor.py --no-network
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.services.monitor_simulator import (  # noqa: E402
    DEFAULT_BATCH_SIZE,
    run_hsi_monitor_simulation,
    write_sim_outputs,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Daily-monitor research replay (not a forecast).")
    parser.add_argument("--period", default=None, help="Yahoo period (default MONITOR_SIM_PERIOD or 5y)")
    parser.add_argument("--horizon", type=int, default=None, help="Forward bars for MAE/MFE and time stop")
    parser.add_argument("--warmup", type=int, default=None, help="Minimum bars before the first replay day")
    parser.add_argument("--limit", type=int, default=None, help="Per-list cap")
    parser.add_argument("--max-extension-n", type=float, default=None, dest="max_extension_n")
    parser.add_argument("--cost-bps", type=float, default=None, dest="cost_bps", help="Round-trip cost on paper returns")
    parser.add_argument("--seed", type=int, default=None, help="RNG seed for random-control sampling")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, dest="batch_size")
    parser.add_argument("--universe", choices=("hsi", "hk"), default="hsi")
    parser.add_argument("--codes", default=None, help="Comma-separated subset, e.g. 0700.HK,0005.HK")
    parser.add_argument("--book", choices=("simple", "turtle"), default="simple")
    parser.add_argument("--equity", type=float, default=None, help="Notional for --book turtle (default 1e6)")
    parser.add_argument("--progress-every", type=int, default=20, dest="progress_every")
    parser.add_argument("--no-network", action="store_true", help="Use disk cache only")
    parser.add_argument("--refresh", action="store_true", help="Ignore cache and re-download")
    parser.add_argument("--output-dir", default="reports", help="Directory for markdown/CSV")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if args.no_network and args.refresh:
        parser.error("--no-network and --refresh cannot be combined")

    codes = None
    if args.codes:
        codes = [part.strip() for part in args.codes.split(",") if part.strip()]

    result = run_hsi_monitor_simulation(
        period=args.period,
        horizon=args.horizon,
        warmup=args.warmup,
        limit=args.limit,
        max_extension_n=args.max_extension_n,
        cost_bps=args.cost_bps,
        seed=args.seed,
        no_network=args.no_network,
        refresh=args.refresh,
        batch_size=args.batch_size,
        progress_every=args.progress_every,
        universe=args.universe,
        codes=codes,
        book=args.book,
        equity=args.equity,
    )
    paths = write_sim_outputs(result, result["report"], reports_dir=Path(args.output_dir))
    print(result["report"])
    for label, path in paths.items():
        print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
