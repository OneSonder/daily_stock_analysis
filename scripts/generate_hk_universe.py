#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate committed HK_ALL universe snapshot for qualified scans.

Fetches active HK listed symbols from AkShare (East Money spot list) and writes
``resources/universes/hk_all_stocks.json``.

Usage:
    python scripts/generate_hk_universe.py
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

OUTPUT_PATH = _REPO_ROOT / "resources" / "universes" / "hk_all_stocks.json"
_HK_CODE_RE = re.compile(r"^\d{1,5}$")


def _to_hk_yahoo_code(raw_code: str) -> str:
    digits = raw_code.strip().lstrip("0") or "0"
    if not digits.isdigit():
        return ""
    return f"{int(digits):04d}.HK"


def _is_equity_code(raw_code: str) -> bool:
    """Keep standard numeric HK equity codes; drop blanks and non-numeric symbols."""
    code = raw_code.strip()
    if not _HK_CODE_RE.match(code):
        return False
    numeric = int(code)
    return 1 <= numeric <= 99999


def fetch_hk_stocks_from_akshare() -> list[dict[str, str]]:
    try:
        import akshare as ak
    except ImportError as exc:
        raise SystemExit(
            "akshare is required. Install with: pip install akshare"
        ) from exc

    errors: list[str] = []
    for fetcher_name, fetcher in (
        ("stock_hk_spot_em", lambda: ak.stock_hk_spot_em()),
        ("stock_hk_spot", lambda: ak.stock_hk_spot()),
    ):
        try:
            df = fetcher()
        except Exception as exc:
            errors.append(f"{fetcher_name}: {exc}")
            continue
        if df is None or df.empty:
            errors.append(f"{fetcher_name}: empty response")
            continue
        stocks = _parse_akshare_hk_df(df, fetcher_name)
        if stocks:
            print(f"  Source: ak.{fetcher_name} ({len(stocks)} symbols)")
            return stocks
        errors.append(f"{fetcher_name}: no parseable rows")

    detail = "; ".join(errors) if errors else "no AkShare source succeeded"
    raise RuntimeError(f"Failed to fetch HK universe ({detail})")


def _parse_akshare_hk_df(df, source: str) -> list[dict[str, str]]:
    code_candidates = ("代码", "symbol", "code")
    name_candidates = ("名称", "name", "中文名称")
    code_col = next((col for col in code_candidates if col in df.columns), None)
    name_col = next((col for col in name_candidates if col in df.columns), None)
    if not code_col or not name_col:
        raise RuntimeError(f"{source} unexpected columns: {list(df.columns)}")

    seen: set[str] = set()
    stocks: list[dict[str, str]] = []
    for _, row in df.iterrows():
        raw_code = str(row[code_col]).strip()
        yahoo_code = _to_hk_yahoo_code(raw_code)
        if not yahoo_code or not _is_equity_code(raw_code):
            continue
        if yahoo_code in seen:
            continue
        seen.add(yahoo_code)
        stocks.append({
            "code": yahoo_code,
            "name": str(row[name_col]).strip(),
        })

    stocks.sort(key=lambda item: item["code"])
    return stocks


def _optional_tushare_count() -> None:
    token = os.getenv("TUSHARE_TOKEN", "").strip()
    if not token:
        return
    try:
        import tushare as ts
    except ImportError:
        print("  Tushare installed check skipped (package not available)")
        return

    try:
        api = ts.pro_api(token)
        df = api.hk_basic(list_status="L", fields="ts_code,name")
        if df is not None and not df.empty:
            print(f"  Tushare hk_basic(list_status=L): {len(df)} symbols (cross-check)")
    except Exception as exc:
        print(f"  Tushare cross-check skipped: {exc}")


def write_snapshot(stocks: list[dict[str, str]], output_path: Path = OUTPUT_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(stocks, ensure_ascii=False, indent=2)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        delete=False,
        dir=output_path.parent,
        suffix=".tmp",
    ) as handle:
        handle.write(payload)
        handle.write("\n")
        temp_path = Path(handle.name)
    temp_path.replace(output_path)


def main() -> int:
    print("Fetching HK market universe from AkShare...")
    stocks = fetch_hk_stocks_from_akshare()
    if not stocks:
        print("[错误] No HK stocks parsed from AkShare response")
        return 1

    write_snapshot(stocks)
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"Wrote {len(stocks)} stocks to {OUTPUT_PATH}")
    print(f"Updated: {updated}")
    print("Sample:")
    for item in stocks[:5]:
        name = item["name"].encode("ascii", "backslashreplace").decode("ascii")
        print(f"  {item['code']}  {name}")
    _optional_tushare_count()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
