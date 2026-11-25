#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Write one Phase 1 candidate-screen take for HK or US.

The run is rules-only. ``--dry-run`` uses the same path: it writes the
markdown artifact and does not touch STOCK_LIST, the workbench, HSI_HOLDINGS,
notifications, or a broker.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.services.candidate_screen import CandidateScreenDataError, run_candidate_screen


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 1 US+HK close-first candidate screen")
    parser.add_argument("--market", required=True, choices=("hk", "us"))
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Write the markdown take only. No book, notification, or broker side effects.",
    )
    parser.add_argument("--reports-dir", default="reports")
    args = parser.parse_args(argv)
    try:
        result = run_candidate_screen(market=args.market, reports_dir=args.reports_dir)
    except CandidateScreenDataError as exc:
        print(f"candidate screen failed closed: {exc}", file=sys.stderr)
        return 1
    print(f"dry_run={str(bool(args.dry_run)).lower()}")
    print(f"market={args.market}")
    print(f"as_of={result.get('as_of')}")
    print(f"bar_date={result.get('bar_date')}")
    print(f"uprising={len(result.get('uprising') or [])}")
    print(f"reversal_appendix={len(result.get('reversal') or [])}")
    print(f"artifact_latest={result.get('artifact_latest')}")
    print(f"artifact_dated={result.get('artifact_dated')}")
    print(f"stable_artifact={result.get('stable_artifact')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
