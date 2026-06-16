#!/usr/bin/env python3
"""
Scan stocks from built-in HSI/US lists and report signal matches.

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
- HK tickers like "700.HK" and US tickers like "AAPL" are supported.
"""

import argparse
import json
import logging
import os
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.error import URLError
from urllib.request import Request, urlopen

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

# Built-in US large-cap watchlist
US_STOCKS = [
  {"code": "AAPL", "name": "Apple"},
  {"code": "MSFT", "name": "Microsoft"},
  {"code": "NVDA", "name": "NVIDIA"},
  {"code": "AMZN", "name": "Amazon"},
  {"code": "GOOGL", "name": "Alphabet Class A"},
  {"code": "META", "name": "Meta Platforms"},
  {"code": "TSLA", "name": "Tesla"},
  {"code": "AVGO", "name": "Broadcom"},
  {"code": "BRK-B", "name": "Berkshire Hathaway B"},
  {"code": "JPM", "name": "JPMorgan Chase"},
  {"code": "V", "name": "Visa"},
  {"code": "MA", "name": "Mastercard"},
  {"code": "UNH", "name": "UnitedHealth"},
  {"code": "XOM", "name": "Exxon Mobil"},
  {"code": "JNJ", "name": "Johnson & Johnson"},
  {"code": "WMT", "name": "Walmart"},
  {"code": "COST", "name": "Costco"},
  {"code": "PG", "name": "Procter & Gamble"},
  {"code": "HD", "name": "Home Depot"},
  {"code": "NFLX", "name": "Netflix"},
  {"code": "AMD", "name": "Advanced Micro Devices"},
  {"code": "ORCL", "name": "Oracle"},
  {"code": "CRM", "name": "Salesforce"},
  {"code": "ADBE", "name": "Adobe"},
  {"code": "KO", "name": "Coca-Cola"},
  {"code": "PEP", "name": "PepsiCo"},
  {"code": "BAC", "name": "Bank of America"},
  {"code": "ABBV", "name": "AbbVie"},
  {"code": "MRK", "name": "Merck"},
  {"code": "CVX", "name": "Chevron"},
  {"code": "PLTR", "name": "Palantir"},
  {"code": "UBER", "name": "Uber"},
  {"code": "PYPL", "name": "PayPal"},
  {"code": "INTC", "name": "Intel"},
  {"code": "SHOP", "name": "Shopify"}
]

UNIVERSE_ALIASES = {
    'hsi': 'hsi',
    'hsi_list': 'hsi',
    'us': 'us',
    'us_list': 'us',
    'both': 'both',
    'all': 'both',
}


def collatz_steps_to_one(seed: int, *, max_steps: int = 512) -> int:
    """Return Collatz steps needed for seed to reach 1 (bounded)."""
    n = max(1, int(seed))
    steps = 0
    while n != 1 and steps < max_steps:
        if n % 2 == 0:
            n //= 2
        else:
            n = (3 * n) + 1
        steps += 1
    return steps


def build_collatz_seed(close_value: float, entry_value: float, *, bucket_bps: float = 25.0) -> int:
    """
    Map distance to breakout level into an integer seed:
    - 1 means at/above entry level
    - each 25 bps gap adds one seed bucket
    """
    if close_value <= 0 or entry_value <= 0:
        return 1
    gap_ratio = max(0.0, (entry_value - close_value) / close_value)
    gap_bps = gap_ratio * 10000.0
    return max(1, int(gap_bps // bucket_bps) + 1)


def normalize_collatz_step_limit(value: Any) -> int:
    """Parse collatz step limit and clamp to non-negative integer."""
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("collatz_step_limit must be an integer.") from exc
    return max(0, parsed)


def normalize_min_score(value: Any) -> float:
    """Parse minimum potential score and clamp to the scanner's 0-100 range."""
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("min_score must be a number between 0 and 100.") from exc
    return max(0.0, min(100.0, parsed))


def normalize_top_n(value: Any) -> Optional[int]:
    """Parse top_n; None means no cap."""
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("top_n must be a positive integer.") from exc
    if parsed <= 0:
        raise ValueError("top_n must be a positive integer.")
    return parsed


def normalize_stock_code(raw: Any) -> str:
    code = str(raw or "").strip().upper()
    if code.startswith("0") and code.endswith(".HK") and len(code) > 5:
        # Keep canonical Yahoo HK format as seen in the built-in universe.
        return code
    return code


def normalize_stock_name(raw: Any, fallback_code: str) -> str:
    name = str(raw or "").strip()
    return name if name else fallback_code


def dedupe_stock_items(items: List[Dict[str, str]]) -> List[Dict[str, str]]:
    deduped: List[Dict[str, str]] = []
    seen: Set[str] = set()
    for item in items:
        code = normalize_stock_code(item.get('code'))
        if not code or code in seen:
            continue
        seen.add(code)
        deduped.append({'code': code, 'name': normalize_stock_name(item.get('name'), code)})
    return deduped


def _stock_from_raw_entry(raw: Any) -> Optional[Dict[str, str]]:
    if isinstance(raw, str):
        code = normalize_stock_code(raw)
        if not code:
            return None
        return {'code': code, 'name': code}
    if isinstance(raw, dict):
        code = normalize_stock_code(raw.get('code') or raw.get('ticker') or raw.get('symbol'))
        if not code:
            return None
        return {'code': code, 'name': normalize_stock_name(raw.get('name'), code)}
    return None


def load_watchlist_file(watchlist_file: str) -> List[Dict[str, str]]:
    path = Path(watchlist_file).expanduser().resolve()
    if not path.exists():
        raise ValueError(f"watchlist_file not found: {path}")
    if not path.is_file():
        raise ValueError(f"watchlist_file must be a file: {path}")

    suffix = path.suffix.lower()
    items: List[Dict[str, str]] = []

    if suffix == '.json':
        try:
            raw = json.loads(path.read_text(encoding='utf-8'))
        except Exception as exc:
            raise ValueError(f"Failed to parse watchlist JSON: {path}") from exc

        if isinstance(raw, list):
            for entry in raw:
                parsed = _stock_from_raw_entry(entry)
                if parsed:
                    items.append(parsed)
        elif isinstance(raw, dict):
            # Supports {"stocks": [...]} or {"AAPL":"Apple"} style maps.
            if isinstance(raw.get('stocks'), list):
                for entry in raw.get('stocks', []):
                    parsed = _stock_from_raw_entry(entry)
                    if parsed:
                        items.append(parsed)
            else:
                for code, name in raw.items():
                    parsed = _stock_from_raw_entry({'code': code, 'name': name})
                    if parsed:
                        items.append(parsed)
        else:
            raise ValueError("watchlist_file JSON must be a list or an object.")
    elif suffix in {'.csv', '.txt'}:
        if suffix == '.txt':
            for line in path.read_text(encoding='utf-8').splitlines():
                parsed = _stock_from_raw_entry(line)
                if parsed:
                    items.append(parsed)
        else:
            try:
                df = pd.read_csv(path)
            except Exception as exc:
                raise ValueError(f"Failed to parse watchlist CSV: {path}") from exc
            if not df.empty:
                lower_col_map = {str(col).strip().lower(): col for col in df.columns}
                code_col = (
                    lower_col_map.get('code') or
                    lower_col_map.get('ticker') or
                    lower_col_map.get('symbol') or
                    df.columns[0]
                )
                name_col = lower_col_map.get('name')
                for _, row in df.iterrows():
                    parsed = _stock_from_raw_entry({
                        'code': row.get(code_col),
                        'name': row.get(name_col) if name_col else row.get(code_col),
                    })
                    if parsed:
                        items.append(parsed)
    else:
        raise ValueError("watchlist_file must be .json, .csv, or .txt")

    deduped = dedupe_stock_items(items)
    if not deduped:
        raise ValueError(f"watchlist_file did not contain valid tickers: {path}")
    return deduped


def resolve_scan_universe(universe: str, watchlist_file: Optional[str]) -> Tuple[str, List[Dict[str, str]]]:
    if watchlist_file:
        watchlist = load_watchlist_file(watchlist_file)
        return f"watchlist:{Path(watchlist_file).name}", watchlist
    resolved_universe, stocks = parse_universe(universe)
    return resolved_universe, dedupe_stock_items(stocks)

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


def _safe_pct(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return (numerator / denominator) * 100.0


def _safe_ratio(numerator: float, denominator: float) -> Optional[float]:
    if denominator <= 0:
        return None
    return numerator / denominator


def _win_rate_pct(signal: pd.Series, forward_returns: pd.Series) -> Tuple[int, Optional[float]]:
    valid = signal.fillna(False) & forward_returns.notna()
    sample_size = int(valid.sum())
    if sample_size <= 0:
        return 0, None
    wins = int((forward_returns[valid] > 0).sum())
    return sample_size, round((wins / sample_size) * 100.0, 2)


def _swing_points(series: pd.Series, span: int = 3) -> Tuple[List[int], List[int]]:
    highs: List[int] = []
    lows: List[int] = []
    values = series.reset_index(drop=True)
    if len(values) < (span * 2) + 1:
        return highs, lows
    for idx in range(span, len(values) - span):
        center = values.iloc[idx]
        if pd.isna(center):
            continue
        window = values.iloc[idx - span:idx + span + 1]
        if center == window.max() and int((window == center).sum()) == 1:
            highs.append(idx)
        if center == window.min() and int((window == center).sum()) == 1:
            lows.append(idx)
    return highs, lows


def _detect_w_bottom(high: pd.Series, low: pd.Series, close: pd.Series) -> bool:
    _, low_points = _swing_points(low, span=3)
    if len(low_points) < 2:
        return False
    left_idx, right_idx = low_points[-2], low_points[-1]
    if right_idx - left_idx < 4:
        return False
    left_low = float(low.iloc[left_idx])
    right_low = float(low.iloc[right_idx])
    avg_low = (left_low + right_low) / 2.0
    if avg_low <= 0:
        return False
    similar_bottoms = abs(left_low - right_low) / avg_low <= 0.06
    neckline = float(high.iloc[left_idx:right_idx + 1].max())
    close_now = float(close.iloc[-1])
    breakout = close_now >= neckline * 0.99
    recent = (len(close) - 1 - right_idx) <= 20
    return bool(similar_bottoms and breakout and recent)


def _detect_m_top(high: pd.Series, low: pd.Series, close: pd.Series) -> bool:
    high_points, _ = _swing_points(high, span=3)
    if len(high_points) < 2:
        return False
    left_idx, right_idx = high_points[-2], high_points[-1]
    if right_idx - left_idx < 4:
        return False
    left_high = float(high.iloc[left_idx])
    right_high = float(high.iloc[right_idx])
    avg_high = (left_high + right_high) / 2.0
    if avg_high <= 0:
        return False
    similar_tops = abs(left_high - right_high) / avg_high <= 0.06
    neckline = float(low.iloc[left_idx:right_idx + 1].min())
    close_now = float(close.iloc[-1])
    breakdown = close_now <= neckline * 1.01
    recent = (len(close) - 1 - right_idx) <= 20
    return bool(similar_tops and breakdown and recent)


def _detect_head_shoulders(high: pd.Series, low: pd.Series, close: pd.Series) -> bool:
    high_points, _ = _swing_points(high, span=3)
    if len(high_points) < 3:
        return False
    left_idx, head_idx, right_idx = high_points[-3:]
    if not (left_idx < head_idx < right_idx):
        return False
    left_high = float(high.iloc[left_idx])
    head_high = float(high.iloc[head_idx])
    right_high = float(high.iloc[right_idx])
    shoulders_similar = abs(left_high - right_high) / max(left_high, right_high, 1e-9) <= 0.08
    head_clear = head_high > max(left_high, right_high) * 1.03
    neckline_left = float(low.iloc[left_idx:head_idx + 1].min())
    neckline_right = float(low.iloc[head_idx:right_idx + 1].min())
    neckline = (neckline_left + neckline_right) / 2.0
    close_now = float(close.iloc[-1])
    breakdown = close_now <= neckline * 1.01
    recent = (len(close) - 1 - right_idx) <= 25
    return bool(shoulders_similar and head_clear and breakdown and recent)


def _detect_inverse_head_shoulders(high: pd.Series, low: pd.Series, close: pd.Series) -> bool:
    _, low_points = _swing_points(low, span=3)
    if len(low_points) < 3:
        return False
    left_idx, head_idx, right_idx = low_points[-3:]
    if not (left_idx < head_idx < right_idx):
        return False
    left_low = float(low.iloc[left_idx])
    head_low = float(low.iloc[head_idx])
    right_low = float(low.iloc[right_idx])
    shoulders_similar = abs(left_low - right_low) / max(left_low, right_low, 1e-9) <= 0.08
    head_clear = head_low < min(left_low, right_low) * 0.97
    neckline_left = float(high.iloc[left_idx:head_idx + 1].max())
    neckline_right = float(high.iloc[head_idx:right_idx + 1].max())
    neckline = (neckline_left + neckline_right) / 2.0
    close_now = float(close.iloc[-1])
    breakout = close_now >= neckline * 0.99
    recent = (len(close) - 1 - right_idx) <= 25
    return bool(shoulders_similar and head_clear and breakout and recent)


def _detect_triangle_breakout(high: pd.Series, low: pd.Series, close: pd.Series) -> Tuple[bool, Optional[str]]:
    if len(close) < 32:
        return False, None
    high_recent = high.iloc[-30:].reset_index(drop=True)
    low_recent = low.iloc[-30:].reset_index(drop=True)
    close_recent = close.iloc[-30:].reset_index(drop=True)
    x = np.arange(len(high_recent), dtype=float)
    high_slope = float(np.polyfit(x, high_recent.values, 1)[0])
    low_slope = float(np.polyfit(x, low_recent.values, 1)[0])
    start_range = float(high_recent.iloc[0] - low_recent.iloc[0])
    end_range = float(high_recent.iloc[-1] - low_recent.iloc[-1])
    compressed = start_range > 0 and end_range < start_range * 0.8
    converging = high_slope < 0 and low_slope > 0
    if not (compressed and converging):
        return False, None
    upper_bound = float(high_recent.iloc[:-1].max())
    lower_bound = float(low_recent.iloc[:-1].min())
    close_now = float(close_recent.iloc[-1])
    if close_now > upper_bound * 1.002:
        return True, "up"
    if close_now < lower_bound * 0.998:
        return True, "down"
    return False, None


def _detect_bull_flag(high: pd.Series, low: pd.Series, close: pd.Series) -> bool:
    if len(close) < 36:
        return False
    impulse_start = float(close.iloc[-35])
    impulse_peak = float(close.iloc[-15])
    if impulse_start <= 0:
        return False
    impulse_gain = (impulse_peak - impulse_start) / impulse_start
    pullback_start = float(close.iloc[-15])
    pullback_end = float(close.iloc[-1])
    pullback_return = (pullback_end - pullback_start) / max(pullback_start, 1e-9)
    channel_range = (float(high.iloc[-15:].max()) - float(low.iloc[-15:].min())) / max(pullback_end, 1e-9)
    breakout = float(close.iloc[-1]) > float(high.iloc[-15:-1].max()) * 1.001
    return bool(impulse_gain >= 0.08 and pullback_return > -0.08 and channel_range < 0.12 and breakout)


def _detect_bear_flag(high: pd.Series, low: pd.Series, close: pd.Series) -> bool:
    if len(close) < 36:
        return False
    impulse_start = float(close.iloc[-35])
    impulse_trough = float(close.iloc[-15])
    if impulse_start <= 0:
        return False
    impulse_drop = (impulse_trough - impulse_start) / impulse_start
    pullback_start = float(close.iloc[-15])
    pullback_end = float(close.iloc[-1])
    pullback_return = (pullback_end - pullback_start) / max(pullback_start, 1e-9)
    channel_range = (float(high.iloc[-15:].max()) - float(low.iloc[-15:].min())) / max(pullback_end, 1e-9)
    breakdown = float(close.iloc[-1]) < float(low.iloc[-15:-1].min()) * 0.999
    return bool(impulse_drop <= -0.08 and pullback_return < 0.08 and channel_range < 0.12 and breakdown)


def _detect_candlestick_patterns(work: pd.DataFrame) -> Dict[str, bool]:
    if len(work) < 2:
        return {
            'gap_up': False,
            'gap_down': False,
            'bullish_engulfing': False,
            'bearish_engulfing': False,
            'doji': False,
            'hammer': False,
            'shooting_star': False,
        }
    open_now = float(work['Open'].iloc[-1])
    close_now = float(work['Close'].iloc[-1])
    high_now = float(work['High'].iloc[-1])
    low_now = float(work['Low'].iloc[-1])
    open_prev = float(work['Open'].iloc[-2])
    close_prev = float(work['Close'].iloc[-2])
    high_prev = float(work['High'].iloc[-2])
    low_prev = float(work['Low'].iloc[-2])

    gap_up = low_now > high_prev * 1.002
    gap_down = high_now < low_prev * 0.998

    prev_body_low = min(open_prev, close_prev)
    prev_body_high = max(open_prev, close_prev)
    curr_body_low = min(open_now, close_now)
    curr_body_high = max(open_now, close_now)
    bullish_engulfing = (
        close_prev < open_prev and
        close_now > open_now and
        curr_body_low <= prev_body_low and
        curr_body_high >= prev_body_high
    )
    bearish_engulfing = (
        close_prev > open_prev and
        close_now < open_now and
        curr_body_low <= prev_body_low and
        curr_body_high >= prev_body_high
    )

    candle_range = max(high_now - low_now, 1e-9)
    body_size = abs(close_now - open_now)
    upper_wick = high_now - max(open_now, close_now)
    lower_wick = min(open_now, close_now) - low_now
    doji = body_size <= candle_range * 0.1
    hammer = lower_wick >= body_size * 2.0 and upper_wick <= body_size * 1.2 and close_now >= open_now * 0.98
    shooting_star = upper_wick >= body_size * 2.0 and lower_wick <= body_size * 1.2 and close_now <= open_now * 1.02

    return {
        'gap_up': bool(gap_up),
        'gap_down': bool(gap_down),
        'bullish_engulfing': bool(bullish_engulfing),
        'bearish_engulfing': bool(bearish_engulfing),
        'doji': bool(doji),
        'hammer': bool(hammer),
        'shooting_star': bool(shooting_star),
    }


def _kline_pattern_summary(flags: Dict[str, bool], triangle_direction: Optional[str]) -> Tuple[List[str], List[str], List[str], float]:
    bullish_weights = {
        'w_bottom': 4.0,
        'double_bottom': 3.0,
        'inverse_head_shoulders': 5.0,
        'bull_flag': 3.0,
        'gap_up': 2.0,
        'bullish_engulfing': 2.0,
        'hammer': 2.0,
    }
    bearish_weights = {
        'm_top': -4.0,
        'double_top': -3.0,
        'head_shoulders': -5.0,
        'bear_flag': -3.0,
        'gap_down': -2.0,
        'bearish_engulfing': -2.0,
        'shooting_star': -2.0,
    }

    bullish_patterns = [name for name in bullish_weights if flags.get(name)]
    bearish_patterns = [name for name in bearish_weights if flags.get(name)]
    neutral_patterns: List[str] = []
    if flags.get('doji'):
        neutral_patterns.append('doji')
    if flags.get('triangle_breakout'):
        if triangle_direction == 'up':
            bullish_patterns.append('triangle_breakout')
        elif triangle_direction == 'down':
            bearish_patterns.append('triangle_breakout')
        else:
            neutral_patterns.append('triangle_breakout')

    pattern_score = sum(bullish_weights.get(name, 0.0) for name in bullish_patterns)
    pattern_score += sum(bearish_weights.get(name, 0.0) for name in bearish_patterns)
    pattern_score = max(-20.0, min(20.0, pattern_score))

    all_patterns: List[str] = []
    for name in bullish_patterns + bearish_patterns + neutral_patterns:
        if name not in all_patterns:
            all_patterns.append(name)
    return all_patterns, bullish_patterns, bearish_patterns, pattern_score


def compute_signals_full(df: pd.DataFrame, collatz_step_limit: int = 12) -> Dict[str, Any]:
    """Compute S1/S2, Collatz, volume/trend, risk and backtest metrics."""
    needed = {'High', 'Low', 'Close'}
    missing = needed - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    try:
        df.index = df.index.tz_localize(None)
    except Exception:
        pass

    work = df.copy()
    if 'Open' not in work.columns:
        work['Open'] = work['Close'].shift(1).fillna(work['Close'])
    if 'Volume' not in work.columns:
        work['Volume'] = 0.0
    work = work[['Open', 'High', 'Low', 'Close', 'Volume']].copy()

    entry20 = work['High'].rolling(window=20).max()
    entry55 = work['High'].rolling(window=55).max()
    exit10 = work['Low'].rolling(window=10).min()
    exit20 = work['Low'].rolling(window=20).min()
    ma50 = work['Close'].rolling(window=50).mean()
    ma200 = work['Close'].rolling(window=200).mean()
    volume20_avg = work['Volume'].rolling(window=20).mean()
    volume20_max = work['Volume'].rolling(window=20).max()

    if any(pd.isna(s.iloc[-1]) for s in [entry20, entry55, exit10, exit20]):
        raise ValueError('Not enough data to compute one or more levels')

    s1_breakout = bool(work['High'].iloc[-1] > entry20.shift(1).iloc[-1])
    s2_breakout = bool(work['High'].iloc[-1] > entry55.shift(1).iloc[-1])
    s1_exit = bool(work['Low'].iloc[-1] < exit10.shift(1).iloc[-1])
    s2_exit = bool(work['Low'].iloc[-1] < exit20.shift(1).iloc[-1])
    close_vs_entry = bool(work['Close'].iloc[-1] >= entry20.iloc[-1])
    close_vs_s2_entry = bool(work['Close'].iloc[-1] >= entry55.iloc[-1])

    close_value = float(work['Close'].iloc[-1])
    entry20_value = float(entry20.iloc[-1])
    entry55_value = float(entry55.iloc[-1])
    exit10_value = float(exit10.iloc[-1])
    exit20_value = float(exit20.iloc[-1])
    volume_value = float(work['Volume'].iloc[-1])
    volume20_avg_value = float(volume20_avg.iloc[-1]) if not pd.isna(volume20_avg.iloc[-1]) else 0.0

    s1_gap_pct = 0.0
    s2_gap_pct = 0.0
    if close_value > 0:
        s1_gap_pct = max(0.0, _safe_pct(entry20_value - close_value, close_value))
        s2_gap_pct = max(0.0, _safe_pct(entry55_value - close_value, close_value))

    collatz_seed_s1 = build_collatz_seed(close_value, entry20_value)
    collatz_seed_s2 = build_collatz_seed(close_value, entry55_value)
    collatz_steps_s1 = collatz_steps_to_one(collatz_seed_s1)
    collatz_steps_s2 = collatz_steps_to_one(collatz_seed_s2)
    effective_step_limit = normalize_collatz_step_limit(collatz_step_limit)
    collatz_s1_ready = bool(close_vs_entry or collatz_steps_s1 <= effective_step_limit)
    collatz_s2_ready = bool(close_vs_s2_entry or collatz_steps_s2 <= effective_step_limit)
    collatz_dual_ready = bool(collatz_s1_ready and collatz_s2_ready)

    w_bottom = _detect_w_bottom(work['High'], work['Low'], work['Close'])
    m_top = _detect_m_top(work['High'], work['Low'], work['Close'])
    double_bottom = w_bottom
    double_top = m_top
    head_shoulders = _detect_head_shoulders(work['High'], work['Low'], work['Close'])
    inverse_head_shoulders = _detect_inverse_head_shoulders(work['High'], work['Low'], work['Close'])
    triangle_breakout, triangle_direction = _detect_triangle_breakout(work['High'], work['Low'], work['Close'])
    bull_flag = _detect_bull_flag(work['High'], work['Low'], work['Close'])
    bear_flag = _detect_bear_flag(work['High'], work['Low'], work['Close'])
    candle_patterns = _detect_candlestick_patterns(work)
    pattern_flags = {
        'w_bottom': w_bottom,
        'm_top': m_top,
        'double_bottom': double_bottom,
        'double_top': double_top,
        'head_shoulders': head_shoulders,
        'inverse_head_shoulders': inverse_head_shoulders,
        'triangle_breakout': triangle_breakout,
        'bull_flag': bull_flag,
        'bear_flag': bear_flag,
        **candle_patterns,
    }
    kline_patterns, kline_bullish_patterns, kline_bearish_patterns, kline_pattern_score = _kline_pattern_summary(
        pattern_flags,
        triangle_direction
    )

    close_above_ma50 = bool(not pd.isna(ma50.iloc[-1]) and close_value >= float(ma50.iloc[-1]))
    close_above_ma200 = bool(not pd.isna(ma200.iloc[-1]) and close_value >= float(ma200.iloc[-1]))
    ma50_above_ma200 = bool(
        not pd.isna(ma50.iloc[-1]) and
        not pd.isna(ma200.iloc[-1]) and
        float(ma50.iloc[-1]) >= float(ma200.iloc[-1])
    )
    trend_bullish = bool(close_above_ma50 and close_above_ma200 and ma50_above_ma200)

    volume_above_20d_avg = bool(
        volume20_avg_value > 0 and
        volume_value >= volume20_avg_value
    )
    volume_breakout = bool(
        not pd.isna(volume20_max.shift(1).iloc[-1]) and
        volume_value > float(volume20_max.shift(1).iloc[-1])
    )
    price_breakout_with_volume = bool((s1_breakout or s2_breakout) and volume_above_20d_avg)

    risk_to_exit10_pct = max(0.0, _safe_pct(close_value - exit10_value, close_value))
    risk_to_exit20_pct = max(0.0, _safe_pct(close_value - exit20_value, close_value))
    reward_to_s1_entry_pct = max(0.0, _safe_pct(entry20_value - close_value, close_value))
    reward_to_s2_entry_pct = max(0.0, _safe_pct(entry55_value - close_value, close_value))
    reward_risk_s1 = _safe_ratio(reward_to_s1_entry_pct, risk_to_exit10_pct)
    reward_risk_s2 = _safe_ratio(reward_to_s2_entry_pct, risk_to_exit20_pct)

    forward_days = 10
    forward_returns = (work['Close'].shift(-forward_days) / work['Close']) - 1.0
    s1_hist_signal = work['High'] > entry20.shift(1)
    s2_hist_signal = work['High'] > entry55.shift(1)
    volume_hist_above_20d = work['Volume'] >= volume20_avg
    price_with_volume_hist = (s1_hist_signal | s2_hist_signal) & volume_hist_above_20d

    collatz_seed_s1_hist = (
        np.floor(
            np.maximum(0.0, (entry20 - work['Close']) / work['Close'].replace(0, np.nan))
            * 10000.0 / 25.0
        ).fillna(0) + 1
    ).astype(int).clip(lower=1)
    collatz_seed_s2_hist = (
        np.floor(
            np.maximum(0.0, (entry55 - work['Close']) / work['Close'].replace(0, np.nan))
            * 10000.0 / 25.0
        ).fillna(0) + 1
    ).astype(int).clip(lower=1)
    collatz_steps_s1_hist = collatz_seed_s1_hist.apply(collatz_steps_to_one)
    collatz_steps_s2_hist = collatz_seed_s2_hist.apply(collatz_steps_to_one)
    collatz_s1_hist_signal = (work['Close'] >= entry20) | (collatz_steps_s1_hist <= effective_step_limit)
    collatz_s2_hist_signal = (work['Close'] >= entry55) | (collatz_steps_s2_hist <= effective_step_limit)

    s1_signal_count, s1_win_rate_pct = _win_rate_pct(s1_hist_signal, forward_returns)
    s2_signal_count, s2_win_rate_pct = _win_rate_pct(s2_hist_signal, forward_returns)
    collatz_s1_signal_count, collatz_s1_win_rate_pct = _win_rate_pct(collatz_s1_hist_signal, forward_returns)
    price_with_volume_count, price_with_volume_win_rate_pct = _win_rate_pct(price_with_volume_hist, forward_returns)

    win_rates_for_edge = [
        rate for rate in [
            s1_win_rate_pct,
            s2_win_rate_pct,
            collatz_s1_win_rate_pct,
            price_with_volume_win_rate_pct,
        ]
        if rate is not None
    ]
    historical_edge_adjust = 0.0
    if win_rates_for_edge:
        average_win_rate = sum(win_rates_for_edge) / len(win_rates_for_edge)
        historical_edge_adjust = max(-10.0, min(10.0, (average_win_rate - 50.0) / 3.0))

    base_score = (
        (20 if close_vs_entry else 0) +
        (20 if close_vs_s2_entry else 0) +
        (16 if s1_breakout else 0) +
        (16 if s2_breakout else 0) +
        (10 if collatz_s1_ready else 0) +
        (10 if collatz_s2_ready else 0) +
        (8 if trend_bullish else 0) +
        (6 if price_breakout_with_volume else 0) +
        (4 if volume_breakout else 0) +
        (4 if volume_above_20d_avg else 0) -
        (12 if s1_exit else 0) -
        (12 if s2_exit else 0)
    )
    distance_penalty = min(20.0, s1_gap_pct + s2_gap_pct)
    risk_penalty = min(15.0, risk_to_exit10_pct * 1.2)
    potential_score = max(
        0.0,
        min(
            100.0,
            base_score + kline_pattern_score + historical_edge_adjust - distance_penalty - risk_penalty
        )
    )

    if potential_score >= 80:
        potential_tier = 'A'
    elif potential_score >= 60:
        potential_tier = 'B'
    elif potential_score >= 40:
        potential_tier = 'C'
    else:
        potential_tier = 'D'

    last_date = work.index[-1]
    try:
        date_iso = last_date.strftime('%Y-%m-%d')
    except Exception:
        date_iso = str(last_date)

    return {
        'date': date_iso,
        'close': round(close_value, 2),
        'high': round(float(work['High'].iloc[-1]), 2),
        'low': round(float(work['Low'].iloc[-1]), 2),
        'volume': int(round(volume_value)),
        'entry20': round(entry20_value, 2),
        'entry55': round(entry55_value, 2),
        'exit10': round(exit10_value, 2),
        'exit20': round(exit20_value, 2),
        'ma50': round(float(ma50.iloc[-1]), 2) if not pd.isna(ma50.iloc[-1]) else None,
        'ma200': round(float(ma200.iloc[-1]), 2) if not pd.isna(ma200.iloc[-1]) else None,
        'volume20_avg': round(volume20_avg_value, 2) if volume20_avg_value else None,
        's1_gap_pct': round(s1_gap_pct, 2),
        's2_gap_pct': round(s2_gap_pct, 2),
        'close_vs_entry': close_vs_entry,
        'close_vs_s2_entry': close_vs_s2_entry,
        's1_breakout': s1_breakout,
        's2_breakout': s2_breakout,
        's1_exit': s1_exit,
        's2_exit': s2_exit,
        'w_bottom': w_bottom,
        'm_top': m_top,
        'double_bottom': double_bottom,
        'double_top': double_top,
        'head_shoulders': head_shoulders,
        'inverse_head_shoulders': inverse_head_shoulders,
        'triangle_breakout': triangle_breakout,
        'triangle_breakout_direction': triangle_direction,
        'bull_flag': bull_flag,
        'bear_flag': bear_flag,
        'gap_up': candle_patterns['gap_up'],
        'gap_down': candle_patterns['gap_down'],
        'bullish_engulfing': candle_patterns['bullish_engulfing'],
        'bearish_engulfing': candle_patterns['bearish_engulfing'],
        'doji': candle_patterns['doji'],
        'hammer': candle_patterns['hammer'],
        'shooting_star': candle_patterns['shooting_star'],
        'kline_patterns': kline_patterns,
        'kline_bullish_patterns': kline_bullish_patterns,
        'kline_bearish_patterns': kline_bearish_patterns,
        'kline_pattern_score': round(kline_pattern_score, 2),
        'volume_breakout': volume_breakout,
        'volume_above_20d_avg': volume_above_20d_avg,
        'price_breakout_with_volume': price_breakout_with_volume,
        'close_above_ma50': close_above_ma50,
        'close_above_ma200': close_above_ma200,
        'ma50_above_ma200': ma50_above_ma200,
        'trend_bullish': trend_bullish,
        'collatz_seed_s1': collatz_seed_s1,
        'collatz_seed_s2': collatz_seed_s2,
        'collatz_steps_s1': collatz_steps_s1,
        'collatz_steps_s2': collatz_steps_s2,
        'collatz_s1_ready': collatz_s1_ready,
        'collatz_s2_ready': collatz_s2_ready,
        'collatz_dual_ready': collatz_dual_ready,
        'risk_to_exit10_pct': round(risk_to_exit10_pct, 2),
        'risk_to_exit20_pct': round(risk_to_exit20_pct, 2),
        'reward_to_s1_entry_pct': round(reward_to_s1_entry_pct, 2),
        'reward_to_s2_entry_pct': round(reward_to_s2_entry_pct, 2),
        'reward_risk_s1': round(float(reward_risk_s1), 2) if reward_risk_s1 is not None else None,
        'reward_risk_s2': round(float(reward_risk_s2), 2) if reward_risk_s2 is not None else None,
        'backtest_forward_days': forward_days,
        's1_signal_count': s1_signal_count,
        's1_win_rate_pct': s1_win_rate_pct,
        's2_signal_count': s2_signal_count,
        's2_win_rate_pct': s2_win_rate_pct,
        'collatz_s1_signal_count': collatz_s1_signal_count,
        'collatz_s1_win_rate_pct': collatz_s1_win_rate_pct,
        'price_with_volume_count': price_with_volume_count,
        'price_with_volume_win_rate_pct': price_with_volume_win_rate_pct,
        'historical_edge_adjust': round(historical_edge_adjust, 2),
        'potential_score': round(potential_score, 2),
        'potential_tier': potential_tier,
    }


def evaluate_ticker(
    code: str,
    name: str,
    period: str = '1y',
    retries: int = 5,
    collatz_step_limit: int = 12
) -> Dict[str, Any]:
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
        signal_columns = ['High', 'Low', 'Close']
        if 'Open' in hist.columns:
            signal_columns.insert(0, 'Open')
        if 'Volume' in hist.columns:
            signal_columns.append('Volume')
        sig = compute_signals_full(
            hist[signal_columns],
            collatz_step_limit=collatz_step_limit
        )
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


def evaluate_ticker_timed(
    code: str,
    name: str,
    period: str,
    retries: int,
    collatz_step_limit: int
) -> Dict[str, Any]:
    started = time.perf_counter()
    result = evaluate_ticker(
        code,
        name,
        period=period,
        retries=retries,
        collatz_step_limit=collatz_step_limit
    )
    result['elapsed_ms'] = round((time.perf_counter() - started) * 1000, 2)
    return result


def parse_conditions(raw_conditions: str) -> Set[str]:
    wanted = {c.strip() for c in raw_conditions.split(',') if c.strip()}
    valid = {
        'close_vs_entry',
        'close_vs_s2_entry',
        's1_breakout',
        's2_breakout',
        's1_exit',
        's2_exit',
        'w_bottom',
        'm_top',
        'double_bottom',
        'double_top',
        'head_shoulders',
        'inverse_head_shoulders',
        'triangle_breakout',
        'bull_flag',
        'bear_flag',
        'gap_up',
        'gap_down',
        'bullish_engulfing',
        'bearish_engulfing',
        'doji',
        'hammer',
        'shooting_star',
        'volume_breakout',
        'volume_above_20d_avg',
        'price_breakout_with_volume',
        'close_above_ma50',
        'close_above_ma200',
        'ma50_above_ma200',
        'trend_bullish',
        'collatz_s1_ready',
        'collatz_s2_ready',
        'collatz_dual_ready',
    }
    unknown = wanted - valid
    if unknown:
        raise ValueError(f"Unknown conditions specified: {sorted(unknown)}")
    return wanted


def parse_universe(raw_universe: str) -> Tuple[str, List[Dict[str, str]]]:
    requested = (raw_universe or 'hsi').strip().lower()
    normalized = UNIVERSE_ALIASES.get(requested)
    if normalized is None:
        raise ValueError(
            "Unknown universe specified. Use one of: hsi, us, both "
            "(aliases: hsi_list, us_list, all)."
        )
    if normalized == 'hsi':
        return normalized, list(HSI_STOCKS)
    if normalized == 'us':
        return normalized, list(US_STOCKS)
    return normalized, list(HSI_STOCKS) + list(US_STOCKS)


def build_scan_payload(
    period: str = '1y',
    retries: int = 5,
    max_workers: int = 8,
    conditions: str = 'close_vs_entry',
    universe: str = 'hsi',
    collatz_step_limit: int = 12,
    min_score: float = 0.0,
    top_n: Optional[int] = None,
    watchlist_file: Optional[str] = None
) -> Dict[str, Any]:
    wanted = parse_conditions(conditions)
    resolved_universe, stocks = resolve_scan_universe(universe, watchlist_file)
    started = time.perf_counter()
    results: List[Dict[str, Any]] = [None] * len(stocks)
    worker_count = max(1, max_workers)
    effective_step_limit = normalize_collatz_step_limit(collatz_step_limit)
    effective_min_score = normalize_min_score(min_score)
    effective_top_n = normalize_top_n(top_n)

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_to_idx = {
            executor.submit(
                evaluate_ticker_timed,
                item.get('code'),
                item.get('name', ''),
                period,
                retries,
                effective_step_limit
            ): idx
            for idx, item in enumerate(stocks)
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            results[idx] = future.result()

    total_ms = round((time.perf_counter() - started) * 1000, 2)
    logger.info(
        "scan_complete tickers=%s universe=%s max_workers=%s min_score=%.2f top_n=%s watchlist=%s total_ms=%.2f",
        len(stocks),
        resolved_universe,
        worker_count,
        effective_min_score,
        effective_top_n,
        bool(watchlist_file),
        total_ms
    )

    matches = [
        r for r in results
        if (
            r.get('status') == 'ok' and
            any(r.get(cond) for cond in wanted) and
            float(r.get('potential_score', 0.0)) >= effective_min_score
        )
    ]
    matches.sort(
        key=lambda row: (
            -float(row.get('potential_score', 0.0)),
            float(row.get('collatz_steps_s1', 10**9)),
            row.get('code', ''),
        )
    )
    if effective_top_n is not None:
        matches = matches[:effective_top_n]
    no_price = [r for r in results if r.get('status') == 'empty']

    return {
        'matches': matches,
        'no_price': no_price,
        'stats': {
            'tickers': len(stocks),
            'universe': resolved_universe,
            'conditions': sorted(list(wanted)),
            'collatz_step_limit': effective_step_limit,
            'min_score': effective_min_score,
            'top_n': effective_top_n,
            'watchlist_file': watchlist_file,
            'max_workers': worker_count,
            'total_ms': total_ms,
        }
    }


def write_json_output(path: Optional[str], payload: Dict[str, Any]) -> Optional[str]:
    if not path:
        return None
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    return str(target)


def write_csv_output(path: Optional[str], matches: List[Dict[str, Any]]) -> Optional[str]:
    if not path:
        return None
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(matches).to_csv(target, index=False)
    return str(target)


def build_alert_payload(scan_payload: Dict[str, Any], alert_min_score: float) -> Optional[Dict[str, Any]]:
    matches = scan_payload.get('matches', [])
    qualifying = [
        row for row in matches
        if float(row.get('potential_score', 0.0)) >= alert_min_score
    ]
    if not qualifying:
        return None
    top = [
        {
            'code': row.get('code'),
            'name': row.get('name'),
            'potential_score': row.get('potential_score'),
            'potential_tier': row.get('potential_tier'),
            'kline_pattern_score': row.get('kline_pattern_score'),
            'kline_patterns': row.get('kline_patterns'),
            's1_breakout': row.get('s1_breakout'),
            's2_breakout': row.get('s2_breakout'),
            'collatz_s1_ready': row.get('collatz_s1_ready'),
            'collatz_s2_ready': row.get('collatz_s2_ready'),
            'trend_bullish': row.get('trend_bullish'),
            'price_breakout_with_volume': row.get('price_breakout_with_volume'),
            'w_bottom': row.get('w_bottom'),
            'm_top': row.get('m_top'),
            'head_shoulders': row.get('head_shoulders'),
            'inverse_head_shoulders': row.get('inverse_head_shoulders'),
            'bullish_engulfing': row.get('bullish_engulfing'),
            'bearish_engulfing': row.get('bearish_engulfing'),
        }
        for row in qualifying[:10]
    ]
    return {
        'event': 'scan_alert',
        'generated_at_epoch': int(time.time()),
        'alert_min_score': alert_min_score,
        'stats': scan_payload.get('stats', {}),
        'qualifying_count': len(qualifying),
        'top_matches': top,
    }


def send_alert_webhook(webhook_url: str, payload: Dict[str, Any], timeout_seconds: int = 8) -> bool:
    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    request = Request(
        webhook_url,
        data=body,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return 200 <= int(getattr(response, 'status', 0)) < 300
    except URLError as exc:
        logger.warning("alert_webhook_failed reason=%s", exc)
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Check stock universes for breakout/exit and Collatz readiness conditions'
    )
    # parser.add_argument('json_path', help='Path to JSON file containing stock list')
    parser.add_argument('--period', default='1y', help='History period to fetch from Yahoo (e.g., 6mo, 1y, 2y)')
    parser.add_argument('--output', choices=['table', 'json'], default='table', help='Output format')
    parser.add_argument('--retries', type=int, default=5, help='Number of retries on fetch errors (default: 5)')
    parser.add_argument('--max-workers', type=int, default=8, help='Max parallel workers for Yahoo fetches (default: 8)')
    parser.add_argument(
        '--universe',
        default='hsi',
        help='Stock universe: hsi, us, both (aliases: hsi_list, us_list, all)'
    )
    parser.add_argument('--conditions', default='close_vs_entry',
                        help=(
                            'Comma-separated conditions to match: '
                            'close_vs_entry,close_vs_s2_entry,s1_breakout,s2_breakout,s1_exit,s2_exit,'
                            'w_bottom,m_top,double_bottom,double_top,head_shoulders,inverse_head_shoulders,'
                            'triangle_breakout,bull_flag,bear_flag,gap_up,gap_down,bullish_engulfing,'
                            'bearish_engulfing,doji,hammer,shooting_star,'
                            'volume_breakout,volume_above_20d_avg,price_breakout_with_volume,'
                            'close_above_ma50,close_above_ma200,ma50_above_ma200,trend_bullish,'
                            'collatz_s1_ready,collatz_s2_ready,collatz_dual_ready'
                        ))
    parser.add_argument(
        '--collatz-step-limit',
        type=int,
        default=12,
        help='Max Collatz steps used by collatz_*_ready conditions (default: 12)'
    )
    parser.add_argument(
        '--min-score',
        type=float,
        default=0.0,
        help='Minimum potential_score required for matches, 0-100 (default: 0)'
    )
    parser.add_argument(
        '--top-n',
        type=int,
        default=None,
        help='Keep only top N matches after ranking (default: no cap)'
    )
    parser.add_argument(
        '--watchlist-file',
        default=None,
        help='Optional .json/.csv/.txt file of tickers; when set, overrides built-in universe'
    )
    parser.add_argument('--json-out', default=None, help='Optional path to write full payload JSON')
    parser.add_argument('--csv-out', default=None, help='Optional path to write matches CSV')
    parser.add_argument(
        '--alert-webhook',
        default=None,
        help='Optional webhook URL to receive top scored matches (or env SCAN_ALERT_WEBHOOK_URL)'
    )
    parser.add_argument(
        '--alert-min-score',
        type=float,
        default=70.0,
        help='Minimum potential_score for webhook alert payload (default: 70)'
    )
    args = parser.parse_args()

    try:
        wanted = parse_conditions(args.conditions)
        if args.watchlist_file:
            load_watchlist_file(args.watchlist_file)
        else:
            parse_universe(args.universe)
        normalize_min_score(args.min_score)
        normalize_top_n(args.top_n)
        normalize_min_score(args.alert_min_score)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)

    payload = build_scan_payload(
        period=args.period,
        retries=args.retries,
        max_workers=args.max_workers,
        conditions=args.conditions,
        universe=args.universe,
        collatz_step_limit=args.collatz_step_limit,
        min_score=args.min_score,
        top_n=args.top_n,
        watchlist_file=args.watchlist_file,
    )
    matches = payload['matches']
    no_price = payload['no_price']
    stats = payload['stats']

    artifacts: Dict[str, str] = {}

    webhook_url = (args.alert_webhook or os.getenv('SCAN_ALERT_WEBHOOK_URL', '')).strip()
    if webhook_url:
        alert_payload = build_alert_payload(payload, normalize_min_score(args.alert_min_score))
        if alert_payload is not None:
            sent = send_alert_webhook(webhook_url, alert_payload)
            stats['alert_sent'] = sent
            stats['alert_min_score'] = normalize_min_score(args.alert_min_score)
            stats['alert_candidate_count'] = alert_payload.get('qualifying_count', 0)
        else:
            stats['alert_sent'] = False
            stats['alert_candidate_count'] = 0

    csv_out_path = write_csv_output(args.csv_out, matches)
    if csv_out_path:
        artifacts['csv_out'] = csv_out_path
    if artifacts:
        payload['artifacts'] = artifacts
    json_out_path = write_json_output(args.json_out, payload)
    if json_out_path:
        artifacts['json_out'] = json_out_path
        payload['artifacts'] = artifacts

    if args.output == 'json':
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    # Table output
    if matches:
        cols = [
            'code', 'name', 'date', 'potential_score', 'potential_tier', 'kline_pattern_score', 'kline_patterns',
            'close', 'high', 'low',
            'entry20', 'entry55', 'exit10', 'exit20',
            'ma50', 'ma200', 'volume', 'volume20_avg',
            's1_gap_pct', 's2_gap_pct',
            'risk_to_exit10_pct', 'risk_to_exit20_pct',
            'reward_to_s1_entry_pct', 'reward_to_s2_entry_pct',
            'reward_risk_s1', 'reward_risk_s2',
            'collatz_seed_s1', 'collatz_seed_s2',
            'collatz_steps_s1', 'collatz_steps_s2',
            's1_win_rate_pct', 's2_win_rate_pct',
            'collatz_s1_win_rate_pct', 'price_with_volume_win_rate_pct',
        ] + sorted(list(wanted))
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

    print(
        f"\nScan runtime: {stats['total_ms']} ms using {stats['max_workers']} worker(s) "
        f"for universe {stats['universe']} (min_score={stats['min_score']}, top_n={stats['top_n']})"
    )
    if artifacts:
        for key, value in artifacts.items():
            print(f"{key}: {value}")


if __name__ == '__main__':
    main()