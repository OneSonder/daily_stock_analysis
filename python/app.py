import io
import logging
import os
import threading
import time
from typing import Tuple

from flask import Flask, jsonify, render_template, request, send_file, session
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf

from scan_signals import build_scan_payload, parse_conditions

app = Flask(__name__)
app.secret_key = os.getenv('APP_SECRET_KEY', 'a_secret_key')

logger = logging.getLogger(__name__)
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=os.getenv('LOG_LEVEL', 'INFO'),
        format='%(asctime)s %(levelname)s %(name)s - %(message)s'
    )

HISTORY_PERIOD = os.getenv('HISTORY_PERIOD', '1y')
HISTORY_CACHE_TTL_SECONDS = int(os.getenv('HISTORY_CACHE_TTL_SECONDS', '300'))
HISTORY_CACHE_MAX_ENTRIES = int(os.getenv('HISTORY_CACHE_MAX_ENTRIES', '128'))
_history_cache = {}
_history_cache_lock = threading.Lock()


def _prune_history_cache():
    if len(_history_cache) <= HISTORY_CACHE_MAX_ENTRIES:
        return
    for key, _ in sorted(_history_cache.items(), key=lambda item: item[1][0])[: len(_history_cache) - HISTORY_CACHE_MAX_ENTRIES]:
        _history_cache.pop(key, None)


def fetch_ticker_history(ticker: str, period: str = HISTORY_PERIOD) -> Tuple[pd.DataFrame, bool, float]:
    normalized_ticker = ticker.strip().upper()
    cache_key = (normalized_ticker, period)
    now = time.time()

    with _history_cache_lock:
        cached = _history_cache.get(cache_key)
        if cached:
            expires_at, cached_df = cached
            if expires_at > now:
                return cached_df.copy(), True, 0.0
            _history_cache.pop(cache_key, None)

    fetch_start = time.perf_counter()
    data = yf.Ticker(normalized_ticker).history(period=period)
    fetch_duration = time.perf_counter() - fetch_start

    with _history_cache_lock:
        _history_cache[cache_key] = (now + HISTORY_CACHE_TTL_SECONDS, data.copy())
        _prune_history_cache()

    return data, False, fetch_duration

def create_candlestick_chart(data):
    fig = go.Figure(data=[go.Candlestick(x=data.index,
                                           open=data['Open'],
                                           high=data['High'],
                                           low=data['Low'],
                                           close=data['Close'])])
    fig.update_layout(title='Candlestick Chart', xaxis_title='Date', yaxis_title='Price')
    return fig.to_html(full_html=False)

# Helper to compute signals for web display and export
def compute_signals(data: pd.DataFrame) -> pd.DataFrame:
    # Ensure timezone-naive dates for consistency
    try:
        data.index = data.index.tz_localize(None)
    except Exception:
        pass

    df = data[['Close', 'High', 'Low']].copy()
    df['Prev_Close'] = df['Close'].shift(1)

    tr1 = df['High'] - df['Low']
    tr2 = (df['High'] - df['Prev_Close']).abs()
    tr3 = (df['Low'] - df['Prev_Close']).abs()
    df['TR'] = np.maximum.reduce([tr1, tr2, tr3])

    df['N_20_Day_SMA'] = df['TR'].rolling(window=20).mean().round(2)

    df['20_Day_High_S1_Entry'] = df['High'].rolling(window=20).max().round(2)
    df['55_Day_High_S2_Entry'] = df['High'].rolling(window=55).max().round(2)
    df['10_Day_Low_S1_Exit'] = df['Low'].rolling(window=10).min().round(2)
    df['20_Day_Low_S2_Exit'] = df['Low'].rolling(window=20).min().round(2)

    df['S1_Signal'] = np.where(df['High'] > df['20_Day_High_S1_Entry'].shift(1), 'BUY S1 Breakout', '')
    df['S2_Signal'] = np.where(df['High'] > df['55_Day_High_S2_Entry'].shift(1), 'BUY S2 Breakout', df['S1_Signal'])
    df['Exit_Signal'] = np.where(
        df['Low'] < df['10_Day_Low_S1_Exit'].shift(1), 'SELL S1 Exit (10DL)',
        np.where(df['Low'] < df['20_Day_Low_S2_Exit'].shift(1), 'SELL S2 Exit (20DL)', '')
    )

    df = df.drop(columns=['Prev_Close']).reset_index()
    df.columns = [
        'Date', 'Close', 'High', 'Low', 'TR', 'N_20_Day_ATR_Proxy',
        '20_Day_High_S1_Entry', '55_Day_High_S2_Entry',
        '10_Day_Low_S1_Exit', '20_Day_Low_S2_Exit',
        'S1_Signal_Basic', 'S2_Signal_Basic', 'Exit_Signal_Basic'
    ]
    return df

def build_ticker_view(ticker: str):
    chart_html = None
    signals_html = None
    error_message = None
    timings_ms = {}

    try:
        data, cache_hit, fetch_seconds = fetch_ticker_history(ticker, HISTORY_PERIOD)
        timings_ms['fetch'] = round(fetch_seconds * 1000, 2)
        timings_ms['cache_hit'] = cache_hit
        if data.empty:
            return None, None, "No data found for the given ticker. It may be invalid or delisted.", timings_ms

        signal_start = time.perf_counter()
        signals_df = compute_signals(data)
        timings_ms['compute'] = round((time.perf_counter() - signal_start) * 1000, 2)

        chart_start = time.perf_counter()
        chart_html = create_candlestick_chart(data)
        timings_ms['chart'] = round((time.perf_counter() - chart_start) * 1000, 2)

        render_start = time.perf_counter()
        signals_html = signals_df.tail(30).to_html(index=False)
        timings_ms['signals_table'] = round((time.perf_counter() - render_start) * 1000, 2)
    except Exception as exc:
        error_message = str(exc)

    return chart_html, signals_html, error_message, timings_ms


@app.route('/', methods=['GET', 'POST'])
def index():
    request_start = time.perf_counter()
    chart_html = None
    error_message = None
    signals_html = None
    ticker = None

    if request.method == 'POST':
        ticker = request.form.get('ticker', '').strip().upper()
        if ticker:
            session['ticker'] = ticker
        else:
            error_message = "Please provide a ticker symbol."
    elif 'ticker' in session:
        ticker = str(session['ticker']).strip().upper()

    if ticker and not error_message:
        chart_html, signals_html, error_message, timings_ms = build_ticker_view(ticker)
        logger.info("ticker=%s path=/ timings_ms=%s", ticker, timings_ms)

    total_ms = round((time.perf_counter() - request_start) * 1000, 2)
    logger.info("path=/ total_ms=%.2f", total_ms)
    return render_template('index.html', chart_html=chart_html, signals_html=signals_html, error_message=error_message)

@app.route('/export')
def export_excel():
    request_start = time.perf_counter()
    if 'ticker' not in session:
        return "No ticker selected", 400

    ticker = str(session['ticker']).strip().upper()
    try:
        data, cache_hit, fetch_seconds = fetch_ticker_history(ticker, HISTORY_PERIOD)
    except Exception as exc:
        return f"Error fetching data: {exc}", 400

    if data.empty:
        return "No data available for export", 400

    signal_start = time.perf_counter()
    df = compute_signals(data)
    compute_ms = round((time.perf_counter() - signal_start) * 1000, 2)

    output = io.BytesIO()
    export_start = time.perf_counter()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Signals', index=False)
    output.seek(0)
    export_ms = round((time.perf_counter() - export_start) * 1000, 2)

    logger.info(
        "ticker=%s path=/export fetch_ms=%.2f cache_hit=%s compute_ms=%.2f export_ms=%.2f total_ms=%.2f",
        ticker,
        fetch_seconds * 1000,
        cache_hit,
        compute_ms,
        export_ms,
        (time.perf_counter() - request_start) * 1000
    )

    return send_file(output,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True,
                     download_name=f'{ticker}_data.xlsx')


@app.route('/api/scan')
def api_scan():
    request_start = time.perf_counter()
    period = request.args.get('period', HISTORY_PERIOD)
    retries = request.args.get('retries', default=5, type=int)
    max_workers = request.args.get('max_workers', default=8, type=int)
    conditions = request.args.get('conditions', default='close_vs_entry', type=str)

    try:
        parse_conditions(conditions)
        payload = build_scan_payload(
            period=period,
            retries=retries,
            max_workers=max_workers,
            conditions=conditions
        )
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        logger.exception("path=/api/scan failed")
        return jsonify({'error': str(exc)}), 500

    logger.info(
        "path=/api/scan total_ms=%.2f period=%s retries=%s max_workers=%s conditions=%s",
        (time.perf_counter() - request_start) * 1000,
        period,
        retries,
        max_workers,
        conditions
    )
    return jsonify(payload)


@app.route('/api/health')
def api_health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true')