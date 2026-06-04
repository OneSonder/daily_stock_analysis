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
```

Note: table output uses `pandas.to_markdown()` which requires `tabulate` (included in `requirements.txt`). If `tabulate` is not installed, the script falls back to plain text output.

## JSON API

Run the Flask app and request the scanner payload over HTTP:

```bash
python3 app.py
curl "http://127.0.0.1:5000/api/scan?period=1y&retries=2&max_workers=4&conditions=close_vs_entry"
```

The API returns the same payload shape as `python3 scan_signals.py --output json`.

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
