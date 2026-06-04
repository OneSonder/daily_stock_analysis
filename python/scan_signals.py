#!/usr/bin/env python3
"""
Scan stocks from a built-in HSI list and report which ones have Close >= 20_Day_High_S1_Entry.

JSON format example:
[
  {"code": "700.HK", "name": "Tencent"},
  {"code": "9988.HK", "name": "BABA-W"}
]

Usage:
  python3 scan_signals.py --period 1y --output table
  python3 scan_signals.py --output json

Notes:
- 20_Day_High_S1_Entry is computed as a 20-day rolling max of High prices.
- If insufficient data is available (fewer than 20 days) or the ticker returns no data, that ticker is skipped.
- HK tickers like "700.HK" are supported.
"""

import argparse
import json
import logging
import os
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Set

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=os.getenv('LOG_LEVEL', 'INFO'),
        format='%(asctime)s %(levelname)s %(name)s - %(message)s'
    )

# Built-in HSI constituents (embedded from HSI.json)
HSI_STOCKS = [
  {"code": "0001.HK", "name": "長和"},
  {"code": "0002.HK", "name": "中電控股"},
  {"code": "0003.HK", "name": "香港中華煤氣"},
  {"code": "0005.HK", "name": "匯豐控股"},
  {"code": "0006.HK", "name": "電能實業"},
  {"code": "0011.HK", "name": "恒生銀行"},
  {"code": "0012.HK", "name": "恒地"},
  {"code": "0016.HK", "name": "新鴻基地產"},
  {"code": "0027.HK", "name": "銀河娛樂"},
  {"code": "0066.HK", "name": "港鐵公司"},
  {"code": "0083.HK", "name": "信和置業"},
  {"code": "0101.HK", "name": "恒隆地產"},
  {"code": "0151.HK", "name": "中國旺旺"},
  {"code": "0175.HK", "name": "吉利汽車"},
  {"code": "0241.HK", "name": "阿里健康"},
  {"code": "0267.HK", "name": "中信股份"},
  {"code": "0285.HK", "name": "比亞迪電子"},
  {"code": "0288.HK", "name": "萬洲國際"},
  {"code": "0291.HK", "name": "華潤啤酒"},
  {"code": "0300.HK", "name": "美的集團"},
  {"code": "0316.HK", "name": "東方海外"},
  {"code": "0322.HK", "name": "康師傅控股"},
  {"code": "0386.HK", "name": "中國石油化工股份"},
  {"code": "0388.HK", "name": "香港交易所"},
  {"code": "0522.HK", "name": "ASMPT"},
  {"code": "0669.HK", "name": "創科實業"},
  {"code": "0688.HK", "name": "中國海外發展"},
  {"code": "0700.HK", "name": "騰訊控股"},
  {"code": "0728.HK", "name": "中國電信"},
  {"code": "0762.HK", "name": "中國聯通"},
  {"code": "0823.HK", "name": "領展"},
  {"code": "0836.HK", "name": "華潤電力"},
  {"code": "0857.HK", "name": "中國石油股份"},
  {"code": "0868.HK", "name": "信義玻璃"},
  {"code": "0881.HK", "name": "中升控股"},
  {"code": "0883.HK", "name": "中國海洋石油"},
  {"code": "0939.HK", "name": "建設銀行"},
  {"code": "0941.HK", "name": "中國移動"},
  {"code": "0960.HK", "name": "龍湖集團"},
  {"code": "0968.HK", "name": "信義光能"},
  {"code": "0981.HK", "name": "中芯國際"},
  {"code": "0992.HK", "name": "聯想集團"},
  {"code": "1024.HK", "name": "快手-W"},
  {"code": "1038.HK", "name": "長江基建集團"},
  {"code": "1044.HK", "name": "恒安國際"},
  {"code": "1088.HK", "name": "中國神華"},
  {"code": "1093.HK", "name": "石藥集團"},
  {"code": "1099.HK", "name": "國藥控股"},
  {"code": "1109.HK", "name": "華潤置地"},
  {"code": "1113.HK", "name": "長實集團"},
  {"code": "1177.HK", "name": "中國生物製藥"},
  {"code": "1193.HK", "name": "華潤燃氣"},
  {"code": "1209.HK", "name": "華潤萬象生活"},
  {"code": "1211.HK", "name": "比亞迪股份"},
  {"code": "1299.HK", "name": "友邦保險"},
  {"code": "1378.HK", "name": "中國宏橋"},
  {"code": "1398.HK", "name": "工商銀行"},
  {"code": "1810.HK", "name": "小米集團-W"},
  {"code": "1876.HK", "name": "百威亞太"},
  {"code": "1880.HK", "name": "中國中免"},
  {"code": "1928.HK", "name": "金沙中國"},
  {"code": "1929.HK", "name": "周大福"},
  {"code": "1997.HK", "name": "九龍倉置業"},
  {"code": "2015.HK", "name": "理想汽車-W"},
  {"code": "2020.HK", "name": "安踏體育"},
  {"code": "2057.HK", "name": "中通快遞-W"},
  {"code": "2269.HK", "name": "藥明生物"},
  {"code": "2313.HK", "name": "申洲國際"},
  {"code": "2318.HK", "name": "中國平安"},
  {"code": "2319.HK", "name": "蒙牛乳業"},
  {"code": "2331.HK", "name": "李寧"},
  {"code": "2333.HK", "name": "長城汽車"},
  {"code": "2359.HK", "name": "藥明康德"},
  {"code": "2382.HK", "name": "舜宇光學科技"},
  {"code": "2388.HK", "name": "中銀香港"},
  {"code": "2618.HK", "name": "京東物流"},
  {"code": "2628.HK", "name": "中國人壽"},
  {"code": "2688.HK", "name": "新奧能源"},
  {"code": "2899.HK", "name": "紫金礦業"},
  {"code": "3328.HK", "name": "交通銀行"},
  {"code": "3690.HK", "name": "美團-W"},
  {"code": "3692.HK", "name": "翰森製藥"},
  {"code": "3968.HK", "name": "招商銀行"},
  {"code": "3988.HK", "name": "中國銀行"},
  {"code": "6618.HK", "name": "京東健康"},
  {"code": "6690.HK", "name": "海爾智家"},
  {"code": "6862.HK", "name": "海底撈"},
  {"code": "9618.HK", "name": "京東集團-SW"},
  {"code": "9633.HK", "name": "農夫山泉"},
  {"code": "9888.HK", "name": "百度集團-SW"},
  {"code": "9901.HK", "name": "新東方-S"},
  {"code": "9961.HK", "name": "攜程集團-S"},
  {"code": "9988.HK", "name": "阿里巴巴-SW"},
  {"code": "9992.HK", "name": "泡泡瑪特"},
  {"code": "9999.HK", "name": "網易-S"}
]

def compute_20_day_high_entry(df: pd.DataFrame) -> pd.DataFrame:
    # Ensure necessary columns
    needed = {'High', 'Close'}
    missing = needed - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Make index timezone-naive if needed
    try:
        df.index = df.index.tz_localize(None)
    except Exception:
        pass

    out = df.copy()
    out['20_Day_High_S1_Entry'] = out['High'].rolling(window=20).max()
    return out


def fetch_history_with_retries(
    code: str,
    period: str,
    retries: int = 5,
    delay: float = 1.0,
    backoff: float = 2.0,
    max_delay: float = 8.0,
    jitter_ratio: float = 0.25
) -> pd.DataFrame:
    """Fetch ticker history with retry on exceptions.
    Retries on errors up to `retries` times with exponential backoff.
    """
    current_delay = delay
    for attempt in range(1, retries + 1):
        try:
            hist = yf.Ticker(code).history(period=period)
            return hist
        except Exception as e:
            if attempt < retries:
                bounded_delay = min(current_delay, max_delay)
                sleep_seconds = bounded_delay + random.uniform(0.0, bounded_delay * jitter_ratio)
                logger.warning(
                    "retrying code=%s attempt=%s/%s sleep=%.2fs reason=%s",
                    code,
                    attempt + 1,
                    retries,
                    sleep_seconds,
                    str(e)
                )
                time.sleep(sleep_seconds)
                current_delay = min(current_delay * backoff, max_delay)
            else:
                # Exhausted retries; re-raise
                raise e
    # Fallback (should not reach here)
    return pd.DataFrame()


def compute_signals_full(df: pd.DataFrame) -> Dict[str, Any]:
    """Compute S1/S2 breakout and exit levels and return latest flags and levels."""
    # Ensure needed columns
    needed = {'High', 'Low', 'Close'}
    missing = needed - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Normalize index
    try:
        df.index = df.index.tz_localize(None)
    except Exception:
        pass

    work = df[['High', 'Low', 'Close']].copy()
    # Levels
    entry20 = work['High'].rolling(window=20).max()
    entry55 = work['High'].rolling(window=55).max()
    exit10 = work['Low'].rolling(window=10).min()
    exit20 = work['Low'].rolling(window=20).min()

    # If we cannot compute the latest values, raise
    if any(pd.isna(s.iloc[-1]) for s in [entry20, entry55, exit10, exit20]):
        raise ValueError('Not enough data to compute one or more levels')

    # Signals (using previous day's level for breakouts/exits where applicable)
    s1_breakout = bool(work['High'].iloc[-1] > entry20.shift(1).iloc[-1])
    s2_breakout = bool(work['High'].iloc[-1] > entry55.shift(1).iloc[-1])
    s1_exit = bool(work['Low'].iloc[-1] < exit10.shift(1).iloc[-1])
    s2_exit = bool(work['Low'].iloc[-1] < exit20.shift(1).iloc[-1])
    close_vs_entry = bool(work['Close'].iloc[-1] >= entry20.iloc[-1])
    # New: Close vs 55-day S2 entry
    close_vs_s2_entry = bool(work['Close'].iloc[-1] >= entry55.iloc[-1])

    last_date = work.index[-1]
    try:
        date_iso = last_date.strftime('%Y-%m-%d')
    except Exception:
        date_iso = str(last_date)

    return {
        'date': date_iso,
        'close': round(float(work['Close'].iloc[-1]), 2),
        'high': round(float(work['High'].iloc[-1]), 2),
        'low': round(float(work['Low'].iloc[-1]), 2),
        'entry20': round(float(entry20.iloc[-1]), 2),
        'entry55': round(float(entry55.iloc[-1]), 2),
        'exit10': round(float(exit10.iloc[-1]), 2),
        'exit20': round(float(exit20.iloc[-1]), 2),
        'close_vs_entry': close_vs_entry,
        'close_vs_s2_entry': close_vs_s2_entry,
        's1_breakout': s1_breakout,
        's2_breakout': s2_breakout,
        's1_exit': s1_exit,
        's2_exit': s2_exit,
    }


def evaluate_ticker(code: str, name: str, period: str = '1y', retries: int = 5) -> Dict[str, Any]:
    yahoo_url = f"https://finance.yahoo.com/quote/{code}?p={code}"
    try:
        hist = fetch_history_with_retries(code, period, retries=retries)
    except Exception as e:
        return {
            'code': code,
            'name': name,
            'status': 'error',
            'message': str(e),
            'url': yahoo_url
        }

    if hist is None or hist.empty:
        return {
            'code': code,
            'name': name,
            'status': 'empty',
            'message': 'No data found (possibly invalid or delisted)',
            'url': yahoo_url
        }

    try:
        sig = compute_signals_full(hist[['High', 'Low', 'Close']])
    except Exception as e:
        return {
            'code': code,
            'name': name,
            'status': 'insufficient_data',
            'message': str(e),
            'url': yahoo_url
        }

    return {
        'code': code,
        'name': name,
        'status': 'ok',
        'url': yahoo_url,
        **sig,
    }


def evaluate_ticker_timed(code: str, name: str, period: str, retries: int) -> Dict[str, Any]:
    started = time.perf_counter()
    result = evaluate_ticker(code, name, period=period, retries=retries)
    result['elapsed_ms'] = round((time.perf_counter() - started) * 1000, 2)
    return result


def parse_conditions(raw_conditions: str) -> Set[str]:
    wanted = {c.strip() for c in raw_conditions.split(',') if c.strip()}
    valid = {'close_vs_entry', 'close_vs_s2_entry', 's1_breakout', 's2_breakout', 's1_exit', 's2_exit'}
    unknown = wanted - valid
    if unknown:
        raise ValueError(f"Unknown conditions specified: {sorted(unknown)}")
    return wanted


def build_scan_payload(
    period: str = '1y',
    retries: int = 5,
    max_workers: int = 8,
    conditions: str = 'close_vs_entry'
) -> Dict[str, Any]:
    wanted = parse_conditions(conditions)
    stocks = HSI_STOCKS
    started = time.perf_counter()
    results: List[Dict[str, Any]] = [None] * len(stocks)
    worker_count = max(1, max_workers)

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_to_idx = {
            executor.submit(
                evaluate_ticker_timed,
                item.get('code'),
                item.get('name', ''),
                period,
                retries
            ): idx
            for idx, item in enumerate(stocks)
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            results[idx] = future.result()

    total_ms = round((time.perf_counter() - started) * 1000, 2)
    logger.info(
        "scan_complete tickers=%s max_workers=%s total_ms=%.2f",
        len(stocks),
        worker_count,
        total_ms
    )

    matches = [
        r for r in results
        if r.get('status') == 'ok' and any(r.get(cond) for cond in wanted)
    ]
    no_price = [r for r in results if r.get('status') == 'empty']

    return {
        'matches': matches,
        'no_price': no_price,
        'stats': {
            'tickers': len(stocks),
            'max_workers': worker_count,
            'total_ms': total_ms,
        }
    }


def main():
    parser = argparse.ArgumentParser(description='Check stocks for signal conditions (S1/S2 breakouts and exits)')
    # parser.add_argument('json_path', help='Path to JSON file containing stock list')
    parser.add_argument('--period', default='1y', help='History period to fetch from Yahoo (e.g., 6mo, 1y, 2y)')
    parser.add_argument('--output', choices=['table', 'json'], default='table', help='Output format')
    parser.add_argument('--retries', type=int, default=5, help='Number of retries on fetch errors (default: 5)')
    parser.add_argument('--max-workers', type=int, default=8, help='Max parallel workers for Yahoo fetches (default: 8)')
    parser.add_argument('--conditions', default='close_vs_entry',
                        help='Comma-separated conditions to match: close_vs_entry,close_vs_s2_entry,s1_breakout,s2_breakout,s1_exit,s2_exit')
    args = parser.parse_args()

    try:
        wanted = parse_conditions(args.conditions)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)

    payload = build_scan_payload(
        period=args.period,
        retries=args.retries,
        max_workers=args.max_workers,
        conditions=args.conditions
    )
    matches = payload['matches']
    no_price = payload['no_price']
    stats = payload['stats']

    if args.output == 'json':
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    # Table output
    if matches:
        cols = ['code', 'name', 'date', 'close', 'high', 'low', 'entry20', 'entry55', 'exit10', 'exit20'] + sorted(list(wanted))
        df_matches = pd.DataFrame(matches, columns=cols)
        try:
            print(df_matches.to_markdown(index=False))
        except ImportError:
            print(df_matches.to_string(index=False))
    else:
        print('No stocks matched the selected conditions based on the latest available data.')

    if no_price:
        print('\nTickers with no price data found (possibly invalid/delisted):')
        df_no = pd.DataFrame(no_price, columns=['code', 'name', 'url', 'message'])
        try:
            print(df_no.to_markdown(index=False))
        except ImportError:
            print(df_no.to_string(index=False))

    print(f"\nScan runtime: {stats['total_ms']} ms using {stats['max_workers']} worker(s)")


if __name__ == '__main__':
    main()