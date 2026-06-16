# Trae Market Signal Scanner

Small Flask and CLI tool that fetches Yahoo Finance history, computes breakout/exit signals, and exports the latest signal table.

## Run locally

```bash
pip install -r requirements.txt
python3 app.py
```

## CLI scan

```bash
python3 scan_signals.py --period 1y --output table --max-workers 8 --retries 5
python3 scan_signals.py --universe both --conditions close_vs_entry,collatz_s1_ready --collatz-step-limit 12 --min-score 70
python3 scan_signals.py --watchlist-file ./my_watchlist.json --conditions trend_bullish,price_breakout_with_volume --top-n 20 --csv-out ./scan_top20.csv
python3 scan_signals.py --universe both --conditions w_bottom,trend_bullish,volume_above_20d_avg --top-n 20 --output table
python3 scan_signals.py --universe both --conditions m_top,bearish_engulfing,gap_down --top-n 20 --output table
python3 scan_signals.py --universe both --conditions inverse_head_shoulders,price_breakout_with_volume --min-score 65 --output table
```

Note: table output uses `pandas.to_markdown()` which requires `tabulate` (included in `requirements.txt`). If `tabulate` is not installed, the script falls back to plain text output.

## JSON API

Run the Flask app and request the scanner payload over HTTP:

```bash
python3 app.py
curl "http://127.0.0.1:5000/api/scan?period=1y&retries=2&max_workers=4&universe=both&conditions=close_vs_entry,collatz_s1_ready&collatz_step_limit=12&min_score=70"
curl "http://127.0.0.1:5000/api/scan?watchlist_file=./my_watchlist.json&conditions=trend_bullish,price_breakout_with_volume&top_n=20"
curl "http://127.0.0.1:5000/api/scan?universe=both&conditions=w_bottom,trend_bullish,volume_above_20d_avg&top_n=20"
```

The API returns the same payload shape as `python3 scan_signals.py --output json`.

## Universes and Collatz conditions

- `--universe` (or `universe=` in API): `hsi`, `us`, `both` (aliases: `hsi_list`, `us_list`, `all`).
- `--watchlist-file` (or `watchlist_file=` in API): override universe with a custom `.json`, `.csv`, or `.txt` ticker list.
- New Collatz-inspired conditions:
  - `collatz_s1_ready`
  - `collatz_s2_ready`
  - `collatz_dual_ready`
- K-line pattern conditions:
  - `w_bottom`, `m_top`, `double_bottom`, `double_top`
  - `head_shoulders`, `inverse_head_shoulders`, `triangle_breakout`
  - `bull_flag`, `bear_flag`
  - `gap_up`, `gap_down`
  - `bullish_engulfing`, `bearish_engulfing`
  - `doji`, `hammer`, `shooting_star`
- Volume confirmation conditions:
  - `volume_breakout`
  - `volume_above_20d_avg`
  - `price_breakout_with_volume`
- Trend filter conditions:
  - `close_above_ma50`
  - `close_above_ma200`
  - `ma50_above_ma200`
  - `trend_bullish`
- Ranking fields:
  - `potential_score` (0-100)
  - `potential_tier` (`A`/`B`/`C`/`D`)
- `--min-score` (or `min_score=` in API): filters matches by minimum `potential_score`.
- `--top-n` (or `top_n=` in API): keep only highest-ranked matches.
- Risk/positioning fields in results:
  - `risk_to_exit10_pct`, `risk_to_exit20_pct`
  - `reward_to_s1_entry_pct`, `reward_to_s2_entry_pct`
  - `reward_risk_s1`, `reward_risk_s2`
- Built-in backtest metrics (10-day forward win rate):
  - `s1_win_rate_pct`, `s2_win_rate_pct`
  - `collatz_s1_win_rate_pct`
  - `price_with_volume_win_rate_pct`
- Output artifacts:
  - `--json-out ./scan.json`
  - `--csv-out ./matches.csv`
- Alert webhook:
  - `--alert-webhook <url>` (or env `SCAN_ALERT_WEBHOOK_URL`)
  - `--alert-min-score 70`
- Logic summary:
  - Convert S1/S2 gap-to-entry into integer seeds (25 bps per bucket, minimum seed `1`).
  - Run Collatz steps-to-1 on each seed.
  - Mark `collatz_*_ready` when either price already crosses the entry line or steps are `<= collatz_step_limit`.

## Environment configuration

- `APP_SECRET_KEY`: Flask session secret.
- `FLASK_DEBUG`: set `true` only for local debugging.
- `LOG_LEVEL`: logging level for app and scanner (`INFO` by default).
- `HISTORY_PERIOD`: Yahoo history period used by web paths (`1y` by default).
- `HISTORY_CACHE_TTL_SECONDS`: in-memory cache TTL for ticker history (`300` by default).
- `HISTORY_CACHE_MAX_ENTRIES`: max in-memory cache entries (`128` by default).

## Production run example

Use a production WSGI server instead of Flask's debug server:

```bash
FLASK_DEBUG=false APP_SECRET_KEY=change-me gunicorn -w 2 -b 0.0.0.0:8000 app:app
```

## iOS app

- Open `StocksAlertIOS.xcodeproj` in Xcode.
- The app starts in `Mock JSON` mode using the bundled `StocksAlertIOS/Resources/mock_scan.json`.
- Switch to `Live API` in Settings and point the base URL at your running Flask server, for example `http://localhost:5000`.

## Performance notes

- Baseline metrics are recorded in `baseline_metrics.json`.
- Post-change metrics are recorded in `post_change_metrics.json`.
- Measured scanner runtime improved from about `12.17s` sequential to about `4.70s` with `8` workers in the latest run.
