# HK stock universes

## `hk_all_stocks.json`

Committed snapshot of **active HK listed equities** used by the `HK_ALL` qualified-scan token (`REPORT_QUALIFIED_SCAN_STOCK_LIST=HK_ALL`).

| Field | Description |
| --- | --- |
| Source | AkShare `stock_hk_spot_em()` (East Money spot list) |
| Format | `[{"code": "0700.HK", "name": "騰訊控股"}, ...]` |
| Refresh | Run from repo root: `python scripts/generate_hk_universe.py` |

### Notes

- `HSI` remains the ~94 Hang Seng Index constituents; `HK_ALL` is the full-market snapshot (~2,000+ symbols).
- The spot list may include instruments beyond large-cap equities; the generator keeps standard numeric HK codes (`0001`–`99999`).
- After IPOs or delistings, refresh this file periodically so scans stay current.
- Full-market scans are much slower than `HSI`; for GitHub Actions consider `REPORT_QUALIFIED_SCAN_MAX_WORKERS=8`–`16` and `ANALYSIS_TIMEOUT_MINUTES=60`+.
