#!/usr/bin/env python3
"""
Run scripts/scan_trend_filter.py, then main.py --stocks <matched codes>.

Arguments after the first ``--`` are passed to the scan script. If you add a
second ``--``, everything after it is appended to the main.py command.

Examples (from repo root):

  python scripts/run_scan_then_analyze.py -- --hsi --min-score 60 --workers 4
  python scripts/run_scan_then_analyze.py -- --stocks 0700.HK,9988.HK
  python scripts/run_scan_then_analyze.py -- \\
      --hsi-json ./HSI.json --min-score 50 -- \\
      --no-market-review --force-run --no-notify
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Tuple

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _split_scan_and_main(rest: List[str]) -> Tuple[List[str], List[str]]:
    if "--" not in rest:
        return rest, []
    i = rest.index("--")
    return rest[:i], rest[i + 1 :]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Chain scan_trend_filter → main.py on filtered tickers.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run-main",
        action="store_true",
        help="Print main.py argv instead of executing",
    )
    wrapper_argv = sys.argv[1:]
    if "--" not in wrapper_argv:
        parser.error(
            "missing `--` before scan arguments "
            "(e.g. python scripts/run_scan_then_analyze.py -- --hsi --min-score 50)"
        )
    sep = wrapper_argv.index("--")
    opt_part = wrapper_argv[:sep]
    rest = wrapper_argv[sep + 1 :]
    opts = parser.parse_args(opt_part)

    scan_argv, main_argv = _split_scan_and_main(rest)
    if not scan_argv:
        parser.error("no scan arguments after `--`")

    scan_script = _REPO_ROOT / "scripts" / "scan_trend_filter.py"
    main_py = _REPO_ROOT / "main.py"

    fd, tmp_name = tempfile.mkstemp(suffix=".json", prefix="scan_then_analyze_")
    os.close(fd)
    json_path = Path(tmp_name)

    scan_cmd = [
        sys.executable,
        str(scan_script),
        "--json-out",
        str(json_path),
        *scan_argv,
    ]
    proc_scan = subprocess.run(scan_cmd, cwd=str(_REPO_ROOT))
    if proc_scan.returncode != 0:
        json_path.unlink(missing_ok=True)
        return proc_scan.returncode

    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"Failed to read scan JSON: {exc}", file=sys.stderr)
        return 3
    finally:
        json_path.unlink(missing_ok=True)

    if payload.get("skipped"):
        reason = payload.get("skip_reason", "unknown")
        print(f"Scan skipped ({reason}); not running main.py.")
        return 0

    matches = payload.get("matches") or []
    codes = [
        str(row.get("code", "")).strip()
        for row in matches
        if isinstance(row, dict) and str(row.get("code", "")).strip()
    ]
    if not codes:
        print("No matching tickers; skipping main.py.")
        return 1

    stocks_arg = ",".join(codes)
    main_cmd = [sys.executable, str(main_py), "--stocks", stocks_arg, *main_argv]

    if opts.dry_run_main:
        print("Would run:", subprocess.list2cmdline(main_cmd))
        return 0

    proc_main = subprocess.run(main_cmd, cwd=str(_REPO_ROOT))
    return proc_main.returncode


if __name__ == "__main__":
    sys.exit(main())
