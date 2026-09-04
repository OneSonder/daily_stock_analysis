import json
import logging
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

HSI_STOCKS = [
    {"code": "0001.HK", "name": "長和"},
    {"code": "0002.HK", "name": "中電控股"},
    {"code": "0003.HK", "name": "香港中華煤氣"},
    {"code": "0005.HK", "name": "匯豐控股"},
    {"code": "0006.HK", "name": "電能實業"},
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
    {"code": "9999.HK", "name": "網易-S"},
]

VALID_CONDITIONS = {
    'close_vs_entry', 'close_vs_s2_entry', 's1_breakout', 's2_breakout', 's1_exit', 's2_exit',
    's1_entry_allowed', 'turtle_trend_ok', 'close_vs_ma100',
    's1_recent_high_breakout', 's2_recent_high_breakout',
    's1_recent_close_breakout', 's2_recent_close_breakout',
    'w_bottom', 'm_top', 'double_bottom', 'double_top', 'head_shoulders', 'inverse_head_shoulders',
    'triangle_breakout', 'bull_flag', 'bear_flag', 'gap_up', 'gap_down',
    'bullish_engulfing', 'bearish_engulfing', 'doji', 'hammer', 'shooting_star',
    'kline_bullish', 'kline_bearish',
}

YAHOO_URL_TEMPLATE = "https://finance.yahoo.com/quote/{code}?p={code}"

_PERIOD_MAP = {
    '5d': 5, '1mo': 30, '3mo': 90, '6mo': 183,
    '1y': 365, '2y': 730, '5y': 1825, 'max': 3650,
}


def period_to_dates(period: str) -> Tuple[str, str]:
    """Convert a yfinance-style period string to (start_date, end_date) for DataFetcherManager."""
    end = date.today()
    days = _PERIOD_MAP.get(period, 365)
    start = end - timedelta(days=days + 30)  # extra buffer for weekends/holidays
    return start.isoformat(), end.isoformat()


def _code_to_manager_format(code: str) -> str:
    """Convert .HK suffix format to HK-prefix format expected by DataFetcherManager."""
    upper = code.strip().upper()
    if upper.endswith('.HK'):
        base = upper[:-3]
        if base.isdigit():
            return f"HK{base.zfill(5)}"
    return upper


def _code_to_yfinance_format(code: str) -> str:
    """Convert canonical Shanghai ``.SH`` suffixes to Yahoo's ``.SS`` form."""
    upper = code.strip().upper()
    if upper.endswith('.SH'):
        base = upper[:-3]
        if len(base) == 6 and base.isdigit():
            return f"{base}.SS"
    return upper


def _yahoo_quote_url(code: str) -> str:
    yahoo_code = _code_to_yfinance_format(code)
    return YAHOO_URL_TEMPLATE.format(code=yahoo_code)


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename lowercase columns to uppercase for signal computation."""
    rename_map = {}
    for col in df.columns:
        if col.lower() in ('open', 'high', 'low', 'close') and col.islower():
            rename_map[col] = col.title()
        elif col.lower() == 'volume':
            rename_map[col] = col.title() if col.islower() else col
    if rename_map:
        df = df.rename(columns=rename_map)
    needed = {'High', 'Low', 'Close'}
    if not needed.issubset(set(df.columns)):
        missing = needed - set(df.columns)
        raise ValueError(f"Missing required columns after normalization: {missing}")
    return df


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


# English pattern ids kept in data; Chinese labels for report display.
PATTERN_LABELS_ZH: Dict[str, str] = {
    "w_bottom": "W底",
    "double_bottom": "双底",
    "inverse_head_shoulders": "头肩底",
    "bull_flag": "上升旗形",
    "gap_up": "向上跳空",
    "bullish_engulfing": "看涨吞没",
    "hammer": "锤头线",
    "m_top": "M头",
    "double_top": "双顶",
    "head_shoulders": "头肩顶",
    "bear_flag": "下降旗形",
    "gap_down": "向下跳空",
    "bearish_engulfing": "看跌吞没",
    "shooting_star": "射击之星",
    "doji": "十字星",
    "triangle_breakout": "三角形突破",
}


def pattern_label_zh(name: str) -> str:
    """Return Chinese display label for a pattern id; fall back to the raw id."""
    key = (name or "").strip()
    if not key:
        return ""
    zh = PATTERN_LABELS_ZH.get(key)
    return f"{zh}({key})" if zh else key


def format_pattern_names(patterns: Optional[List[str]]) -> str:
    """Format pattern ids as Chinese labels for reports."""
    labels = [pattern_label_zh(p) for p in (patterns or []) if p]
    return ", ".join(labels) if labels else "无"


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


def _ohlcv_for_trend_analyzer(work: pd.DataFrame) -> pd.DataFrame:
    """Build lowercase OHLCV frame expected by StockTrendAnalyzer."""
    dates = pd.to_datetime(work.index, errors='coerce')
    frame = pd.DataFrame(
        {
            'date': dates,
            'open': pd.to_numeric(work['Open'], errors='coerce'),
            'high': pd.to_numeric(work['High'], errors='coerce'),
            'low': pd.to_numeric(work['Low'], errors='coerce'),
            'close': pd.to_numeric(work['Close'], errors='coerce'),
        }
    )
    if 'Volume' in work.columns:
        frame['volume'] = pd.to_numeric(work['Volume'], errors='coerce').fillna(0.0)
    else:
        frame['volume'] = 0.0
    return frame.dropna(subset=['date', 'close']).reset_index(drop=True)


def _enum_value(value: Any) -> Any:
    return value.value if hasattr(value, 'value') else value


def _env_flag(name: str, default: bool = True) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    return default


def _true_range(work: pd.DataFrame) -> pd.Series:
    """True range: max(H-L, |H-PDC|, |PDC-L|)."""
    high = pd.to_numeric(work["High"], errors="coerce")
    low = pd.to_numeric(work["Low"], errors="coerce")
    close = pd.to_numeric(work["Close"], errors="coerce")
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (prev_close - low).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr


def _compute_n(work: pd.DataFrame, window: int = 20) -> Optional[float]:
    """Turtle N ≈ ATR of true range over ``window`` bars. Soft-fail None."""
    try:
        if work is None or len(work) < window + 1:
            return None
        tr = _true_range(work)
        atr = tr.rolling(window=window).mean()
        val = atr.iloc[-1]
        if pd.isna(val) or float(val) <= 0:
            return None
        return float(val)
    except Exception:
        return None


def _adaptive_turtle_trend_ok(work: pd.DataFrame) -> Tuple[bool, str]:
    """Adaptive Turtle trend filter: MA50>MA300 if enough bars, else MA20>MA55."""
    try:
        close = pd.to_numeric(work["Close"], errors="coerce")
        n = len(close.dropna())
        if n >= 300:
            ma50 = close.rolling(50).mean().iloc[-1]
            ma300 = close.rolling(300).mean().iloc[-1]
            if pd.isna(ma50) or pd.isna(ma300):
                return False, "ma50_ma300"
            return bool(float(ma50) > float(ma300)), "ma50_ma300"
        if n >= 55:
            ma20 = close.rolling(20).mean().iloc[-1]
            ma55 = close.rolling(55).mean().iloc[-1]
            if pd.isna(ma20) or pd.isna(ma55):
                return False, "ma20_ma55"
            return bool(float(ma20) > float(ma55)), "ma20_ma55"
        return False, "insufficient"
    except Exception:
        return False, "error"


def _close_vs_ma(
    work: pd.DataFrame,
    window: int = 100,
) -> Tuple[Optional[bool], Optional[float]]:
    """True if last close > MA(window). None when history is too short."""
    try:
        close = pd.to_numeric(work["Close"], errors="coerce")
        if len(close.dropna()) < window:
            return None, None
        ma = close.rolling(window).mean().iloc[-1]
        last = close.iloc[-1]
        if pd.isna(ma) or pd.isna(last):
            return None, None
        ma_value = float(ma)
        return bool(float(last) > ma_value), round(ma_value, 2)
    except Exception:
        return None, None


def _s1_last_breakout_was_winner(
    work: pd.DataFrame,
    n_value: Optional[float] = None,
) -> bool:
    """True if the most recent *completed* S1 (20d) breakout was a winner.

    Completed = reached winner target or hit 10d-low exit after the breakout bar.
    Winner: high reaches entry + max(0.5·N, 2% of entry) before that exit.
    Soft-fail False.
    """
    try:
        if work is None or len(work) < 35:
            return False
        high = pd.to_numeric(work["High"], errors="coerce")
        low = pd.to_numeric(work["Low"], errors="coerce")
        entry20 = high.rolling(20).max()
        exit10 = low.rolling(10).min()
        breakout_idx: List[int] = []
        # Exclude last bar — current signal may still be open.
        for i in range(20, len(work) - 1):
            prior = entry20.iloc[i - 1]
            if pd.isna(prior) or pd.isna(high.iloc[i]):
                continue
            if float(high.iloc[i]) > float(prior):
                breakout_idx.append(i)
        if not breakout_idx:
            return False

        for bi in reversed(breakout_idx):
            entry_level = float(entry20.iloc[bi - 1])
            if entry_level <= 0:
                continue
            n = float(n_value) if n_value and n_value > 0 else None
            if n is not None:
                target = entry_level + 0.5 * n
            else:
                target = entry_level * 1.02
            completed = False
            won = False
            for j in range(bi + 1, len(work)):
                if not pd.isna(high.iloc[j]) and float(high.iloc[j]) >= target:
                    won = True
                    completed = True
                    break
                prior_exit = exit10.iloc[j - 1] if j - 1 >= 0 else None
                if prior_exit is not None and not pd.isna(prior_exit):
                    if float(low.iloc[j]) < float(prior_exit):
                        completed = True
                        won = False
                        break
            if completed:
                return won
        return False
    except Exception:
        return False


def _recent_donchian_first_cross(
    price: pd.Series,
    channel: pd.Series,
) -> Tuple[bool, Optional[str]]:
    """Strict first-cross vs prior Donchian high within the last 2 trading bars.

    A bar qualifies only when price is above its own prior channel *and* the
    immediately preceding bar was not. Returns ``(flag, timing)`` where timing
    is ``'today'``, ``'previous'``, or ``None`` (prefer today when both qualify).
    """
    if price is None or channel is None or len(price) < 3:
        return False, None
    prior = channel.shift(1)

    def _is_above(idx: int) -> Optional[bool]:
        if idx < 0:
            return None
        p = price.iloc[idx]
        c = prior.iloc[idx]
        if pd.isna(p) or pd.isna(c):
            return None
        return bool(float(p) > float(c))

    def _is_first_cross(idx: int) -> bool:
        return _is_above(idx) is True and _is_above(idx - 1) is False

    n = len(price)
    if _is_first_cross(n - 1):
        return True, "today"
    if _is_first_cross(n - 2):
        return True, "previous"
    return False, None


def format_recent_breakout_timing(timing: Optional[str]) -> str:
    """Map recent-breakout timing metadata to Chinese report labels."""
    if timing == "today":
        return "今日"
    if timing == "previous":
        return "前一交易日"
    return "无"


def _recent_breakout_bar_offset(*timings: Optional[str]) -> int:
    """Pick the first-cross bar: today (−1) beats previous-only (−2)."""
    if any(t == "today" for t in timings):
        return -1
    if any(t == "previous" for t in timings):
        return -2
    return -1


def _volume_liquidity_metrics(
    work: pd.DataFrame,
    *,
    bar_offset: int = -1,
) -> Dict[str, Any]:
    """Last/breakout-bar volume vs prior 20-bar median, plus 20d average turnover."""
    empty = {
        "volume": None,
        "avg_volume_20": None,
        "volume_ratio": None,
        "avg_turnover_20": None,
        "volume_confirm": False,
    }
    if work is None or len(work) < 3 or "Volume" not in work.columns:
        return empty
    close = pd.to_numeric(work["Close"], errors="coerce")
    vol = pd.to_numeric(work["Volume"], errors="coerce")
    n = len(vol)
    idx = bar_offset if abs(int(bar_offset)) <= n else -1
    abs_idx = n + idx if idx < 0 else idx
    if abs_idx < 0 or abs_idx >= n:
        return empty
    bar_vol = vol.iloc[abs_idx]
    volume = None if pd.isna(bar_vol) else float(bar_vol)
    prior = vol.iloc[max(0, abs_idx - 20):abs_idx]
    prior_close = close.iloc[max(0, abs_idx - 20):abs_idx]
    prior_valid = prior.dropna()
    avg_volume_20 = float(prior_valid.mean()) if len(prior_valid) else None
    median_volume = float(prior_valid.median()) if len(prior_valid) else None
    volume_ratio = None
    if volume is not None and median_volume and median_volume > 0:
        volume_ratio = round(volume / median_volume, 2)
    turnover = (prior * prior_close).dropna()
    avg_turnover_20 = float(turnover.mean()) if len(turnover) else None
    return {
        "volume": round(volume, 0) if volume is not None else None,
        "avg_volume_20": round(avg_volume_20, 0) if avg_volume_20 is not None else None,
        "volume_ratio": volume_ratio,
        "avg_turnover_20": round(avg_turnover_20, 2) if avg_turnover_20 is not None else None,
        "volume_confirm": bool(volume_ratio is not None and volume_ratio >= 1.0),
    }


def _setup_quality_score_delta(
    *,
    s1_recent_high_breakout: bool,
    s2_recent_high_breakout: bool,
    s1_recent_close_breakout: bool,
    s2_recent_close_breakout: bool,
    volume_confirm: bool,
    volume_ratio: Optional[float],
    breakout_extension_n: Optional[float],
    avg_turnover_20: Optional[float],
    close: Optional[float],
    close_vs_ma100: Optional[bool] = None,
) -> float:
    """Bounded setup-quality contribution: first-cross, volume, extension, liquidity."""
    delta = 0.0
    if s2_recent_close_breakout:
        delta += 8.0
    elif s2_recent_high_breakout:
        delta += 5.0
    if s1_recent_close_breakout:
        delta += 4.0
    elif s1_recent_high_breakout:
        delta += 2.0
    if volume_confirm:
        delta += 6.0
    elif volume_ratio is not None and volume_ratio < 0.7:
        delta -= 6.0
    if breakout_extension_n is not None:
        if breakout_extension_n > 2.0:
            delta -= 8.0
        elif breakout_extension_n > 1.0:
            delta -= 3.0
        elif 0.0 <= breakout_extension_n <= 0.5:
            delta += 3.0
    if avg_turnover_20 is not None and avg_turnover_20 < 500_000:
        delta -= 8.0
    if close is not None and close < 0.1:
        delta -= 8.0
    if close_vs_ma100 is True:
        delta += 3.0
    elif close_vs_ma100 is False:
        delta -= 3.0
    return max(-18.0, min(18.0, delta))


def _potential_reason_tags(
    *,
    s1_breakout: bool,
    s1_recent_high_breakout: bool,
    s2_recent_high_breakout: bool,
    s1_recent_close_breakout: bool,
    s2_recent_close_breakout: bool,
    turtle_trend_ok: bool,
    s1_entry_allowed: bool,
    s1_last_was_winner: bool,
    volume_confirm: bool,
    volume_ratio: Optional[float],
    breakout_extension_n: Optional[float],
    close_vs_ma100: Optional[bool] = None,
) -> List[str]:
    tags: List[str] = []
    if s2_recent_close_breakout:
        tags.append("S2收盘首破")
    elif s2_recent_high_breakout:
        tags.append("S2最高价首破")
    if s1_recent_close_breakout:
        tags.append("S1收盘首破")
    elif s1_recent_high_breakout:
        tags.append("S1最高价首破")
    tags.append("趋势通过" if turtle_trend_ok else "趋势未过")
    if close_vs_ma100 is True:
        tags.append("MA100上方")
    elif close_vs_ma100 is False:
        tags.append("MA100下方")
    if s1_entry_allowed:
        tags.append("S1允许开仓")
    elif s1_breakout and s1_last_was_winner:
        tags.append("S1盈利跳过")
    if volume_confirm:
        tags.append("放量")
    elif volume_ratio is not None:
        tags.append("未放量")
    if breakout_extension_n is not None and breakout_extension_n > 2.0:
        tags.append("延伸偏大")
    return tags


def sort_matches_by_potential(matches: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Highest potential_score first; code as stable tie-break."""

    def _score(row: Dict[str, Any]) -> float:
        try:
            return float(row.get("potential_score") or 0.0)
        except (TypeError, ValueError):
            return 0.0

    return sorted(
        list(matches or []),
        key=lambda row: (-_score(row), str(row.get("code") or "")),
    )


def _report_cell(value: Any, digits: Optional[int] = None) -> str:
    if value is None or value == "":
        return "暂无"
    if digits is not None:
        try:
            return str(round(float(value), digits))
        except (TypeError, ValueError):
            return str(value)
    return str(value)


def format_turnover_cell(value: Any) -> str:
    """Compact HKD turnover for match tables."""
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "暂无"
    if amount >= 1e8:
        return f"{amount / 1e8:.1f}亿"
    if amount >= 1e4:
        return f"{amount / 1e4:.0f}万"
    return str(int(round(amount)))


def format_atr_pct_cell(value: Any) -> str:
    if value is None or value == "":
        return "暂无"
    try:
        return f"{float(value):.1f}%"
    except (TypeError, ValueError):
        return str(value)


def format_ma100_cell(close_vs_ma100: Any) -> str:
    if close_vs_ma100 is True:
        return "上"
    if close_vs_ma100 is False:
        return "下"
    return "不足"


def format_match_result_table_lines(matches: List[Dict[str, Any]]) -> List[str]:
    """Markdown table for 匹配结果, ranked by potential_score."""
    lines = [
        "| 代号 | 名称 | 收盘 | 档 | 分 | S1开 | 趋势 | MA100 | 延伸N | 量比 | 均额 | ATR% | S1 | S2 | S1近H | S2近H | S1近C | S2近C |",
        "|------|------|------|----|----|------|------|------|------|------|------|------|----|----|------|------|------|------|",
    ]
    for m in matches:
        lines.append(
            f"| [{m.get('code', '')}]({m.get('url', '')}) | {m.get('name', '')} "
            f"| {_report_cell(m.get('close'))} "
            f"| {_report_cell(m.get('potential_tier'))} "
            f"| {_report_cell(m.get('potential_score'))} "
            f"| {'是' if m.get('s1_entry_allowed') else '否'} "
            f"| {'通过' if m.get('turtle_trend_ok') else '未过'} "
            f"| {format_ma100_cell(m.get('close_vs_ma100'))} "
            f"| {_report_cell(m.get('breakout_extension_n'))} "
            f"| {_report_cell(m.get('volume_ratio'))} "
            f"| {format_turnover_cell(m.get('avg_turnover_20'))} "
            f"| {format_atr_pct_cell(m.get('atr_pct'))} "
            f"| {'✅' if m.get('s1_breakout') else '❌'} "
            f"| {'✅' if m.get('s2_breakout') else '❌'} "
            f"| {format_recent_breakout_timing(m.get('s1_recent_high_timing'))} "
            f"| {format_recent_breakout_timing(m.get('s2_recent_high_timing'))} "
            f"| {format_recent_breakout_timing(m.get('s1_recent_close_timing'))} "
            f"| {format_recent_breakout_timing(m.get('s2_recent_close_timing'))} |"
        )
    return lines


def format_match_technical_lines(match: Dict[str, Any]) -> List[str]:
    """Technical / Turtle / potential detail block for one match."""
    code = match.get("code", "")
    name = match.get("name", "")
    ma_bits = []
    for key in ("ma5", "ma10", "ma20", "ma60", "ma100"):
        val = match.get(key)
        if val is not None:
            ma_bits.append(f"{key.upper()}={val}")
    ma_line = ", ".join(ma_bits) if ma_bits else "均线暂无"
    alignment = match.get("ma_alignment") or match.get("trend_status") or "暂无"
    rsi_line = (
        f"RSI6={match.get('rsi_6', '暂无')}, RSI12={match.get('rsi_12', '暂无')}"
        f" ({match.get('rsi_status') or '暂无'})"
    )
    macd_line = (
        f"MACD={match.get('macd_status') or '暂无'}"
        f" DIF={match.get('macd_dif', '暂无')} DEA={match.get('macd_dea', '暂无')}"
    )
    if match.get("macd_signal"):
        macd_line += f" — {match.get('macd_signal')}"
    pattern_text = format_pattern_names(match.get("kline_patterns") or [])
    n_val = match.get("n")
    atr_pct = match.get("atr_pct")
    stop_2n = match.get("stop_long_2n")
    ext_n = match.get("breakout_extension_n")
    trend_ok = match.get("turtle_trend_ok")
    trend_rule = match.get("turtle_trend_rule") or "暂无"
    s1_win = match.get("s1_last_was_winner")
    s1_ok = match.get("s1_entry_allowed")
    tier = match.get("potential_tier") or "暂无"
    score = match.get("potential_score")
    reasons = match.get("potential_reasons") or []
    reason_text = " — " + ", ".join(str(r) for r in reasons) if reasons else ""
    turnover = match.get("avg_turnover_20")
    vol_ratio = match.get("volume_ratio")
    vol_ok = match.get("volume_confirm")
    return [
        f"- **{name} ({code})**: {alignment}",
        f"  - {ma_line}",
        f"  - {rsi_line}",
        f"  - {macd_line}",
        f"  - 形态: {pattern_text}",
        (
            f"  - 海龟: N={n_val if n_val is not None else '暂无'}"
            f", ATR%={format_atr_pct_cell(atr_pct)}"
            f", 2N止损参考={stop_2n if stop_2n is not None else '暂无'}"
            f", 突破延伸N={ext_n if ext_n is not None else '暂无'}"
        ),
        (
            f"  - 趋势过滤: {'通过' if trend_ok else '未通过'}（{trend_rule}）"
            f" | MA100: {format_ma100_cell(match.get('close_vs_ma100'))}"
            f" | S1上次盈利跳过: {'是' if s1_win else '否'}"
            f" | S1允许开仓: {'是' if s1_ok else '否'}"
        ),
        (
            "  - 近期突破: "
            f"S1 High={format_recent_breakout_timing(match.get('s1_recent_high_timing'))}"
            f" / Close={format_recent_breakout_timing(match.get('s1_recent_close_timing'))}"
            f" | S2 High={format_recent_breakout_timing(match.get('s2_recent_high_timing'))}"
            f" / Close={format_recent_breakout_timing(match.get('s2_recent_close_timing'))}"
        ),
        (
            f"  - 潜力: {tier} {score if score is not None else '暂无'}"
            f"{reason_text}"
        ),
        (
            f"  - 流动性: 量比={vol_ratio if vol_ratio is not None else '暂无'}"
            f" | 20日均额={turnover if turnover is not None else '暂无'}"
            f" | {'放量确认' if vol_ok else '未放量确认'}"
        ),
    ]


def _turtle_score_delta(
    *,
    s1_breakout: bool,
    s2_breakout: bool,
    turtle_trend_ok: bool,
    s1_last_was_winner: bool,
) -> float:
    """Bounded Turtle-aware contribution to potential_score."""
    use_trend = _env_flag("HSI_TURTLE_TREND_FILTER", True)
    use_skip = _env_flag("HSI_TURTLE_S1_SKIP_WINNER", True)
    delta = 0.0
    any_bo = s1_breakout or s2_breakout
    if use_trend and any_bo:
        delta += 8.0 if turtle_trend_ok else -8.0
    if use_trend and s2_breakout and turtle_trend_ok:
        delta += 6.0
    if use_skip and s1_breakout and s1_last_was_winner:
        delta -= 10.0
    return max(-18.0, min(18.0, delta))


def turtle_holding_action(
    signal: Dict[str, Any],
    buy_price: float,
) -> Dict[str, Any]:
    """Turtle-inspired long holding advice: sell / keep / buy(add).

    - sell: price or low at/below entry−2N, or S1/S2 opposite-breakout exit
    - buy: not sell, trend OK, price ≥ entry+0.5N (pyramid add)
    - keep: held otherwise
    """
    try:
        b = float(buy_price)
    except (TypeError, ValueError):
        return {
            "turtle_action": "keep",
            "turtle_action_reason": "成本价无效",
            "stop_from_entry_2n": None,
            "add_level_05n": None,
            "pnl_pct": None,
            "distance_to_stop_n": None,
        }

    close = signal.get("close")
    low = signal.get("low")
    n_raw = signal.get("n")
    try:
        c = float(close) if close is not None else None
    except (TypeError, ValueError):
        c = None
    try:
        l = float(low) if low is not None else None
    except (TypeError, ValueError):
        l = None
    try:
        n = float(n_raw) if n_raw is not None and float(n_raw) > 0 else None
    except (TypeError, ValueError):
        n = None

    stop = round(b - 2.0 * n, 4) if n is not None else None
    add_level = round(b + 0.5 * n, 4) if n is not None else None
    pnl_pct = round(((c - b) / b) * 100.0, 2) if c is not None and b > 0 else None
    distance_to_stop_n = None
    if n is not None and stop is not None and c is not None:
        distance_to_stop_n = round((c - stop) / n, 2)

    s1_exit = bool(signal.get("s1_exit"))
    s2_exit = bool(signal.get("s2_exit"))
    trend_ok = bool(signal.get("turtle_trend_ok"))

    hit_stop = False
    if stop is not None:
        if l is not None and l <= stop:
            hit_stop = True
        elif c is not None and c <= stop:
            hit_stop = True

    if hit_stop or s1_exit or s2_exit:
        reasons = []
        if hit_stop:
            reasons.append(f"触及入场2N止损({stop})")
        if s1_exit:
            reasons.append("S1退出(跌破10日低)")
        if s2_exit:
            reasons.append("S2退出(跌破20日低)")
        return {
            "turtle_action": "sell",
            "turtle_action_reason": "；".join(reasons),
            "stop_from_entry_2n": stop,
            "add_level_05n": add_level,
            "pnl_pct": pnl_pct,
            "distance_to_stop_n": distance_to_stop_n,
        }

    if (
        trend_ok
        and add_level is not None
        and c is not None
        and c >= add_level
    ):
        return {
            "turtle_action": "buy",
            "turtle_action_reason": f"趋势过滤通过且现价≥入场+0.5N加仓位({add_level})",
            "stop_from_entry_2n": stop,
            "add_level_05n": add_level,
            "pnl_pct": pnl_pct,
            "distance_to_stop_n": distance_to_stop_n,
        }

    return {
        "turtle_action": "keep",
        "turtle_action_reason": "持仓中：未触发止损/退出，亦未达½N加仓",
        "stop_from_entry_2n": stop,
        "add_level_05n": add_level,
        "pnl_pct": pnl_pct,
        "distance_to_stop_n": distance_to_stop_n,
    }


def attach_holdings_to_results(
    holdings: List[Dict[str, Any]],
    results: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Join holdings with scan signal rows and Turtle action fields."""
    by_code = {
        str(r.get("code") or "").strip().upper(): r
        for r in (results or [])
        if r and r.get("code")
    }
    attached: List[Dict[str, Any]] = []
    for h in holdings or []:
        code = str(h.get("code") or "").strip().upper()
        if not code:
            continue
        buy_price = h.get("buy_price")
        base = by_code.get(code)
        if base and base.get("status") == "ok":
            row = dict(base)
        elif base:
            row = {
                "code": code,
                "name": base.get("name") or code,
                "status": base.get("status") or "unavailable",
                "message": base.get("message"),
                "url": base.get("url") or f"https://finance.yahoo.com/quote/{code}",
                "close": base.get("close"),
                "low": base.get("low"),
                "n": base.get("n"),
            }
        else:
            row = {
                "code": code,
                "name": code,
                "status": "missing",
                "message": "not in scan results",
                "url": f"https://finance.yahoo.com/quote/{code}",
            }
        row["buy_price"] = buy_price
        row["is_holding"] = True
        row["enrich_source"] = "holding"
        action = turtle_holding_action(row, float(buy_price) if buy_price is not None else 0.0)
        row.update(action)
        attached.append(row)
    return attached


def merge_stocks_with_holdings(
    base: List[Dict[str, str]],
    holdings: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, str]], int]:
    """Append holding codes not already in the universe."""
    seen = {
        str(s.get("code") or "").strip().upper()
        for s in (base or [])
        if s.get("code")
    }
    merged = list(base or [])
    extra = 0
    for h in holdings or []:
        code = str(h.get("code") or "").strip().upper()
        if not code or code in seen:
            continue
        seen.add(code)
        merged.append({"code": code, "name": code})
        extra += 1
    return merged, extra


def _rsi_macd_indicator_score(technicals: Optional[Dict[str, Any]]) -> float:
    """Bounded RSI/MACD contribution to potential_score (−12 … +12). Soft-fail to 0.

    MACD still rewards trend continuation. RSI oversold/overbought are neutral so a
    Donchian breakout rank is not mixed with mean-reversion bias.
    """
    tech = technicals or {}
    macd_weights = {
        "零轴上金叉": 8.0,
        "金叉": 6.0,
        "上穿零轴": 5.0,
        "多头": 3.0,
        "空头": -3.0,
        "下穿零轴": -5.0,
        "死叉": -6.0,
    }
    # Trend-following rank: do not treat RSI oversold as bullish or overbought as a dump.
    rsi_weights = {
        "超卖": 0.0,
        "强势买入": 2.0,
        "中性": 0.0,
        "弱势": -2.0,
        "超买": 0.0,
    }
    macd_status = str(tech.get("macd_status") or "").strip()
    rsi_status = str(tech.get("rsi_status") or "").strip()
    score = macd_weights.get(macd_status, 0.0) + rsi_weights.get(rsi_status, 0.0)
    return max(-12.0, min(12.0, score))


def _technicals_from_trend(result: Any) -> Dict[str, Any]:
    """Extract MA / MACD / RSI fields from TrendAnalysisResult."""
    if result is None:
        return {}

    def _round(val: Any, digits: int = 2) -> Optional[float]:
        try:
            if val is None or (isinstance(val, float) and pd.isna(val)):
                return None
            return round(float(val), digits)
        except (TypeError, ValueError):
            return None

    return {
        'ma5': _round(getattr(result, 'ma5', None)),
        'ma10': _round(getattr(result, 'ma10', None)),
        'ma20': _round(getattr(result, 'ma20', None)),
        'ma60': _round(getattr(result, 'ma60', None)),
        'ma_alignment': getattr(result, 'ma_alignment', None) or '',
        'trend_status': _enum_value(getattr(result, 'trend_status', None)),
        'trend_strength': _round(getattr(result, 'trend_strength', None)),
        'bias_ma5': _round(getattr(result, 'bias_ma5', None)),
        'bias_ma10': _round(getattr(result, 'bias_ma10', None)),
        'bias_ma20': _round(getattr(result, 'bias_ma20', None)),
        'macd_dif': _round(getattr(result, 'macd_dif', None), 4),
        'macd_dea': _round(getattr(result, 'macd_dea', None), 4),
        'macd_bar': _round(getattr(result, 'macd_bar', None), 4),
        'macd_status': _enum_value(getattr(result, 'macd_status', None)),
        'macd_signal': getattr(result, 'macd_signal', None) or '',
        'rsi_6': _round(getattr(result, 'rsi_6', None)),
        'rsi_12': _round(getattr(result, 'rsi_12', None)),
        'rsi_24': _round(getattr(result, 'rsi_24', None)),
        'rsi_status': _enum_value(getattr(result, 'rsi_status', None)),
        'rsi_signal': getattr(result, 'rsi_signal', None) or '',
    }


def _attach_trend_technicals(work: pd.DataFrame) -> Dict[str, Any]:
    """Soft-fail wrapper: RSI/MACD/MAs via StockTrendAnalyzer."""
    try:
        from src.stock_analyzer import StockTrendAnalyzer

        analyzer_df = _ohlcv_for_trend_analyzer(work)
        if analyzer_df.empty or len(analyzer_df) < 20:
            return {}
        trend = StockTrendAnalyzer().analyze(analyzer_df, code='hsi')
        return _technicals_from_trend(trend)
    except Exception as exc:
        logger.warning('HSI trend technicals failed: %s', exc)
        return {}


def compute_signals_full(df: pd.DataFrame) -> Dict[str, Any]:
    df = _normalize_columns(df)
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
    cols = ['Open', 'High', 'Low', 'Close']
    if 'Volume' in work.columns:
        cols.append('Volume')
    work = work[cols].copy()

    entry20 = work['High'].rolling(window=20).max()
    entry55 = work['High'].rolling(window=55).max()
    exit10 = work['Low'].rolling(window=10).min()
    exit20 = work['Low'].rolling(window=20).min()

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

    s1_recent_high_breakout, s1_recent_high_timing = _recent_donchian_first_cross(
        work['High'], entry20,
    )
    s2_recent_high_breakout, s2_recent_high_timing = _recent_donchian_first_cross(
        work['High'], entry55,
    )
    s1_recent_close_breakout, s1_recent_close_timing = _recent_donchian_first_cross(
        work['Close'], entry20,
    )
    s2_recent_close_breakout, s2_recent_close_timing = _recent_donchian_first_cross(
        work['Close'], entry55,
    )
    volume_metrics = _volume_liquidity_metrics(
        work,
        bar_offset=_recent_breakout_bar_offset(
            s1_recent_high_timing,
            s2_recent_high_timing,
            s1_recent_close_timing,
            s2_recent_close_timing,
        ),
    )

    n_value = _compute_n(work, window=20)
    turtle_trend_ok, turtle_trend_rule = _adaptive_turtle_trend_ok(work)
    close_vs_ma100, ma100_value = _close_vs_ma(work, window=100)
    s1_last_was_winner = _s1_last_breakout_was_winner(work, n_value=n_value)
    s1_entry_allowed = bool(s1_breakout and not s1_last_was_winner)

    prior_entry20 = entry20.shift(1).iloc[-1]
    breakout_extension_n = None
    if n_value and n_value > 0 and not pd.isna(prior_entry20):
        breakout_extension_n = (float(work['High'].iloc[-1]) - float(prior_entry20)) / n_value
    stop_long_2n = None
    if n_value and n_value > 0:
        stop_long_2n = close_value - 2.0 * n_value
    atr_pct = None
    if n_value and n_value > 0 and close_value > 0:
        atr_pct = round(100.0 * n_value / close_value, 2)

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

    s1_gap_pct = 0.0
    s2_gap_pct = 0.0
    if close_value > 0:
        s1_gap_pct = max(0.0, ((entry20_value - close_value) / close_value) * 100.0)
        s2_gap_pct = max(0.0, ((entry55_value - close_value) / close_value) * 100.0)
    base_score = (
        (22 if close_vs_entry else 0) +
        (22 if close_vs_s2_entry else 0) +
        (16 if s1_breakout else 0) +
        (16 if s2_breakout else 0) -
        (12 if s1_exit else 0) -
        (12 if s2_exit else 0)
    )
    technicals = _attach_trend_technicals(work)
    rsi_macd_score = _rsi_macd_indicator_score(technicals)
    turtle_score = _turtle_score_delta(
        s1_breakout=s1_breakout,
        s2_breakout=s2_breakout,
        turtle_trend_ok=turtle_trend_ok,
        s1_last_was_winner=s1_last_was_winner,
    )
    setup_score = _setup_quality_score_delta(
        s1_recent_high_breakout=s1_recent_high_breakout,
        s2_recent_high_breakout=s2_recent_high_breakout,
        s1_recent_close_breakout=s1_recent_close_breakout,
        s2_recent_close_breakout=s2_recent_close_breakout,
        volume_confirm=bool(volume_metrics.get("volume_confirm")),
        volume_ratio=volume_metrics.get("volume_ratio"),
        breakout_extension_n=breakout_extension_n,
        avg_turnover_20=volume_metrics.get("avg_turnover_20"),
        close=close_value,
        close_vs_ma100=close_vs_ma100,
    )
    potential_reasons = _potential_reason_tags(
        s1_breakout=s1_breakout,
        s1_recent_high_breakout=s1_recent_high_breakout,
        s2_recent_high_breakout=s2_recent_high_breakout,
        s1_recent_close_breakout=s1_recent_close_breakout,
        s2_recent_close_breakout=s2_recent_close_breakout,
        turtle_trend_ok=turtle_trend_ok,
        s1_entry_allowed=s1_entry_allowed,
        s1_last_was_winner=s1_last_was_winner,
        volume_confirm=bool(volume_metrics.get("volume_confirm")),
        volume_ratio=volume_metrics.get("volume_ratio"),
        breakout_extension_n=breakout_extension_n,
        close_vs_ma100=close_vs_ma100,
    )
    potential_score = max(
        0.0,
        min(
            100.0,
            base_score
            + kline_pattern_score
            + rsi_macd_score
            + turtle_score
            + setup_score
            - min(20.0, s1_gap_pct + s2_gap_pct),
        ),
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
        'close': round(float(work['Close'].iloc[-1]), 2),
        'high': round(float(work['High'].iloc[-1]), 2),
        'low': round(float(work['Low'].iloc[-1]), 2),
        'entry20': round(float(entry20.iloc[-1]), 2),
        'entry55': round(float(entry55.iloc[-1]), 2),
        'exit10': round(float(exit10.iloc[-1]), 2),
        'exit20': round(float(exit20.iloc[-1]), 2),
        'n': round(n_value, 4) if n_value is not None else None,
        'atr_pct': atr_pct,
        'stop_long_2n': round(stop_long_2n, 2) if stop_long_2n is not None else None,
        'breakout_extension_n': (
            round(breakout_extension_n, 2) if breakout_extension_n is not None else None
        ),
        'turtle_trend_ok': turtle_trend_ok,
        'turtle_trend_rule': turtle_trend_rule,
        'ma100': ma100_value,
        'close_vs_ma100': close_vs_ma100,
        's1_last_was_winner': s1_last_was_winner,
        's1_entry_allowed': s1_entry_allowed,
        'turtle_score': round(turtle_score, 2),
        'setup_score': round(setup_score, 2),
        'potential_reasons': potential_reasons,
        's1_gap_pct': round(s1_gap_pct, 2),
        's2_gap_pct': round(s2_gap_pct, 2),
        'close_vs_entry': close_vs_entry,
        'close_vs_s2_entry': close_vs_s2_entry,
        's1_breakout': s1_breakout,
        's2_breakout': s2_breakout,
        's1_recent_high_breakout': s1_recent_high_breakout,
        's2_recent_high_breakout': s2_recent_high_breakout,
        's1_recent_close_breakout': s1_recent_close_breakout,
        's2_recent_close_breakout': s2_recent_close_breakout,
        's1_recent_high_timing': s1_recent_high_timing,
        's2_recent_high_timing': s2_recent_high_timing,
        's1_recent_close_timing': s1_recent_close_timing,
        's2_recent_close_timing': s2_recent_close_timing,
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
        'kline_bullish': bool(len(kline_bullish_patterns) > 0),
        'kline_bearish': bool(len(kline_bearish_patterns) > 0),
        'rsi_macd_score': round(rsi_macd_score, 2),
        'potential_score': round(potential_score, 2),
        'potential_tier': potential_tier,
        **volume_metrics,
        **technicals,
    }


def parse_conditions(raw_conditions: str) -> Set[str]:
    wanted = {c.strip() for c in raw_conditions.split(',') if c.strip()}
    unknown = wanted - VALID_CONDITIONS
    if unknown:
        raise ValueError(f"Unknown conditions specified: {sorted(unknown)}")
    return wanted


def is_hk_market_open() -> bool:
    """Check if HK market is open today. Fail-open: returns True if exchange-calendars unavailable."""
    try:
        from src.core.trading_calendar import is_market_open
        return is_market_open("hk", date.today())
    except ImportError:
        return True
    except Exception:
        return True


def fetch_history_with_data_provider(code: str, period: str) -> pd.DataFrame:
    """Fetch history via DataFetcherManager (multi-source with fallback)."""
    import yfinance as yf
    from data_provider.base import DataFetcherManager

    try:
        start_date, end_date = period_to_dates(period)
        mgr = DataFetcherManager()
        mgr_code = _code_to_manager_format(code)
        df, _source = mgr.get_daily_data(
            stock_code=mgr_code,
            start_date=start_date,
            end_date=end_date,
            days=(date.today() - date.fromisoformat(start_date)).days,
        )
        if df is not None and not df.empty:
            return df
    except Exception as e:
        logger.debug("DataFetcherManager failed for %s, falling back to yfinance: %s", code, e)

    return yf.Ticker(_code_to_yfinance_format(code)).history(period=period)


def fetch_history_with_retries(
    code: str,
    period: str,
    retries: int = 5,
    delay: float = 1.0,
    backoff: float = 2.0,
    max_delay: float = 8.0,
    jitter_ratio: float = 0.25,
    use_multi_source: bool = False,
) -> pd.DataFrame:
    import yfinance as yf

    fetch_fn = (
        fetch_history_with_data_provider
        if use_multi_source
        else lambda c, p: yf.Ticker(_code_to_yfinance_format(c)).history(period=p)
    )

    current_delay = delay
    for attempt in range(1, retries + 1):
        try:
            hist = fetch_fn(code, period)
            return hist
        except Exception as e:
            if attempt < retries:
                bounded_delay = min(current_delay, max_delay)
                sleep_seconds = bounded_delay + random.uniform(0.0, bounded_delay * jitter_ratio)
                logger.warning(
                    "retrying code=%s attempt=%s/%s sleep=%.2fs reason=%s",
                    code, attempt + 1, retries, sleep_seconds, str(e),
                )
                time.sleep(sleep_seconds)
                current_delay = min(current_delay * backoff, max_delay)
            else:
                raise e
    return pd.DataFrame()


def _split_yfinance_batch(
    raw: pd.DataFrame,
    codes: List[str],
) -> Dict[str, pd.DataFrame]:
    """Split a yfinance batch response into one frame per requested ticker."""
    if raw is None or raw.empty:
        return {}

    histories: Dict[str, pd.DataFrame] = {}
    if not isinstance(raw.columns, pd.MultiIndex):
        if len(codes) == 1:
            frame = raw.dropna(how='all')
            if not frame.empty:
                histories[codes[0]] = frame
        return histories

    for code in codes:
        frame: Optional[pd.DataFrame] = None
        for level in range(raw.columns.nlevels):
            values = raw.columns.get_level_values(level)
            if code in values:
                frame = raw.xs(code, axis=1, level=level, drop_level=True)
                break
        if frame is None:
            continue
        if isinstance(frame.columns, pd.MultiIndex):
            frame.columns = frame.columns.get_level_values(0)
        frame = frame.dropna(how='all')
        if not frame.empty:
            histories[code] = frame
    return histories


def fetch_history_batch_yfinance(
    codes: List[str],
    period: str,
    batch_size: Optional[int] = None,
) -> Dict[str, pd.DataFrame]:
    """Download multiple Yahoo histories in one or more batch requests.

    When ``batch_size`` is a positive integer, tickers are downloaded in chunks
    to keep large universes (e.g. all HK listings) within Yahoo request limits.
    """
    if not codes:
        return {}
    import yfinance as yf

    unique_codes = list(dict.fromkeys(code.strip().upper() for code in codes if code.strip()))
    yahoo_codes = {
        code: _code_to_yfinance_format(code)
        for code in unique_codes
    }
    unique_yahoo_codes = list(dict.fromkeys(yahoo_codes.values()))
    chunk = int(batch_size) if batch_size is not None and int(batch_size) > 0 else 0
    chunks: List[List[str]] = (
        [unique_yahoo_codes[i:i + chunk] for i in range(0, len(unique_yahoo_codes), chunk)]
        if chunk
        else [unique_yahoo_codes]
    )
    logger.info(
        "Yahoo batch download starting: tickers=%s period=%s chunks=%s batch_size=%s",
        len(unique_codes),
        period,
        len(chunks),
        chunk or "all",
    )
    yahoo_histories: Dict[str, pd.DataFrame] = {}
    for part in chunks:
        raw = yf.download(
            tickers=part,
            period=period,
            group_by='ticker',
            threads=False,
            progress=False,
            auto_adjust=True,
        )
        yahoo_histories.update(_split_yfinance_batch(raw, part))
    histories = {
        code: yahoo_histories[yahoo_code]
        for code, yahoo_code in yahoo_codes.items()
        if yahoo_code in yahoo_histories
    }
    logger.info(
        "Yahoo batch download completed: requested=%s received=%s",
        len(unique_codes),
        len(histories),
    )
    return histories


def evaluate_ticker_from_history(
    code: str,
    name: str,
    hist: pd.DataFrame,
) -> Dict[str, Any]:
    """Compute one ticker result from an already-fetched history frame."""
    yahoo_url = _yahoo_quote_url(code)
    if hist is None or hist.empty:
        return {
            'code': code, 'name': name, 'status': 'empty',
            'message': 'No data found (possibly invalid or delisted)',
            'url': yahoo_url,
        }

    try:
        signal_columns = ['High', 'Low', 'Close']
        if 'Open' in hist.columns:
            signal_columns.insert(0, 'Open')
        sig = compute_signals_full(hist[signal_columns])
    except Exception as e:
        return {
            'code': code, 'name': name, 'status': 'insufficient_data',
            'message': str(e), 'url': yahoo_url,
        }

    return {
        'code': code, 'name': name, 'status': 'ok',
        'url': yahoo_url, **sig,
    }


def evaluate_ticker(
    code: str,
    name: str,
    period: str = '1y',
    retries: int = 5,
    use_multi_source: bool = False,
) -> Dict[str, Any]:
    yahoo_url = _yahoo_quote_url(code)
    try:
        hist = fetch_history_with_retries(code, period, retries=retries, use_multi_source=use_multi_source)
    except Exception as e:
        return {
            'code': code, 'name': name, 'status': 'error',
            'message': str(e), 'url': yahoo_url,
        }

    return evaluate_ticker_from_history(code, name, hist)


def evaluate_ticker_timed(
    code: str,
    name: str,
    period: str,
    retries: int,
    use_multi_source: bool = False,
) -> Dict[str, Any]:
    started = time.perf_counter()
    result = evaluate_ticker(code, name, period=period, retries=retries, use_multi_source=use_multi_source)
    result['elapsed_ms'] = round((time.perf_counter() - started) * 1000, 2)
    return result


def evaluate_ticker_from_history_timed(
    code: str,
    name: str,
    hist: pd.DataFrame,
) -> Dict[str, Any]:
    started = time.perf_counter()
    result = evaluate_ticker_from_history(code, name, hist)
    result['elapsed_ms'] = round((time.perf_counter() - started) * 1000, 2)
    return result


def get_scan_config_from_env() -> Dict[str, Any]:
    """Read HSI scan configuration from environment variables."""
    return {
        'period': os.getenv('HSI_SCAN_PERIOD', '1y'),
        'conditions': os.getenv('HSI_SCAN_CONDITIONS', 's1_breakout,s2_breakout'),
        'max_workers': int(os.getenv('HSI_SCAN_MAX_WORKERS', '8')),
        'check_trading_day': os.getenv('HSI_SCAN_CHECK_TRADING_DAY', 'false').lower() not in ('0', 'false', 'no', 'off'),
        'use_multi_source': os.getenv('HSI_SCAN_USE_MULTI_SOURCE', 'true').lower() not in ('0', 'false', 'no', 'off'),
        'schedule_time': os.getenv('HSI_SCAN_SCHEDULE_TIME', '09:30'),
    }


def scan_stocks(
    stocks: List[Dict[str, str]],
    period: str = '1y',
    conditions: str = 'close_vs_entry',
    max_workers: int = 8,
    retries: int = 5,
    check_trading_day: bool = False,
    use_multi_source: bool = False,
    batch_size: Optional[int] = None,
    allow_per_ticker_fallback: bool = True,
) -> Dict[str, Any]:
    """Scan an arbitrary stock universe with S1/S2 breakout conditions.

    ``batch_size`` chunks Yahoo bulk downloads (None = single request).
    When ``allow_per_ticker_fallback`` is False, symbols missing after bulk/cache
    are marked unavailable instead of issuing per-ticker Yahoo retries.
    """
    wanted = parse_conditions(conditions)

    if check_trading_day and not is_hk_market_open():
        return {
            'matches': [],
            'results': [],
            'no_price': [],
            'stats': {'tickers': len(stocks), 'max_workers': max_workers, 'total_ms': 0},
            'skipped': True,
            'skip_reason': 'HK market closed today',
            'conditions': sorted(wanted),
        }

    started = time.perf_counter()
    results: List[Dict[str, Any]] = [None] * len(stocks)
    worker_count = max(1, max_workers)
    prefetched: Dict[str, pd.DataFrame] = {}
    cache_hits = 0
    batch_downloaded = 0
    unavailable_without_fallback = 0

    if not use_multi_source:
        from src.services.ohlcv_cache import load_cached_history, save_cached_history

        missing_codes: List[str] = []
        for item in stocks:
            code = item.get('code', '').strip().upper()
            if not code:
                continue
            cached = load_cached_history(code, period)
            if cached is not None:
                prefetched[code] = cached
                cache_hits += 1
            else:
                missing_codes.append(code)

        if missing_codes:
            try:
                downloaded = fetch_history_batch_yfinance(
                    missing_codes,
                    period,
                    batch_size=batch_size,
                )
            except Exception as exc:
                if allow_per_ticker_fallback:
                    logger.warning(
                        "Yahoo batch download failed; using per-ticker fallback for %s tickers: %s",
                        len(missing_codes),
                        exc,
                    )
                else:
                    logger.warning(
                        "Yahoo batch download failed; marking %s tickers unavailable: %s",
                        len(missing_codes),
                        exc,
                    )
                downloaded = {}
            for code, frame in downloaded.items():
                prefetched[code] = frame
                save_cached_history(code, period, frame)
            batch_downloaded = len(downloaded)

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_to_idx = {}
        for idx, item in enumerate(stocks):
            code = item.get('code', '').strip().upper()
            name = item.get('name', '')
            if code in prefetched:
                future = executor.submit(
                    evaluate_ticker_from_history_timed,
                    code,
                    name,
                    prefetched[code],
                )
                future_to_idx[future] = idx
            elif allow_per_ticker_fallback or use_multi_source:
                fallback_retries = retries if use_multi_source else min(retries, 2)
                future = executor.submit(
                    evaluate_ticker_timed,
                    code,
                    name,
                    period,
                    fallback_retries,
                    use_multi_source,
                )
                future_to_idx[future] = idx
            else:
                unavailable_without_fallback += 1
                results[idx] = {
                    'code': code,
                    'name': name,
                    'status': 'empty',
                    'message': 'No data after bulk download (per-ticker fallback disabled)',
                    'url': _yahoo_quote_url(code),
                    'elapsed_ms': 0.0,
                }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            results[idx] = future.result()

    total_ms = round((time.perf_counter() - started) * 1000, 2)
    logger.info(
        "scan_stocks tickers=%s max_workers=%s cache_hits=%s batch_downloaded=%s "
        "unavailable_without_fallback=%s total_ms=%.2f",
        len(stocks),
        worker_count,
        cache_hits,
        batch_downloaded,
        unavailable_without_fallback,
        total_ms,
    )

    matches = sort_matches_by_potential([
        r for r in results
        if r.get('status') == 'ok' and any(r.get(cond) for cond in wanted)
    ])
    no_price = [r for r in results if r.get('status') == 'empty']
    ok_results = [r for r in results if r and r.get('status') == 'ok']

    return {
        'matches': matches,
        'results': ok_results,
        'no_price': no_price,
        'stats': {
            'tickers': len(stocks),
            'max_workers': worker_count,
            'cache_hits': cache_hits,
            'batch_downloaded': batch_downloaded,
            'unavailable_without_fallback': unavailable_without_fallback,
            'batch_size': batch_size,
            'allow_per_ticker_fallback': allow_per_ticker_fallback,
            'total_ms': total_ms,
        },
        'skipped': False,
        'conditions': sorted(wanted),
    }


def merge_stocks_with_etnet_top(
    base: List[Dict[str, str]],
    top_rows: List[Dict[str, str]],
) -> Tuple[List[Dict[str, str]], int]:
    """Preserve base order; append unique ET Net movers. Returns (merged, extra_count)."""
    merged: List[Dict[str, str]] = []
    seen: Set[str] = set()
    for item in base or []:
        code = str(item.get("code") or "").strip().upper()
        if not code or code in seen:
            continue
        seen.add(code)
        merged.append({"code": code, "name": str(item.get("name") or "").strip()})
    extra = 0
    for item in top_rows or []:
        code = str(item.get("code") or "").strip().upper()
        if not code or code in seen:
            continue
        seen.add(code)
        merged.append({"code": code, "name": str(item.get("name") or "").strip()})
        extra += 1
    return merged, extra


def scan_hsi(
    period: str = '1y',
    conditions: str = 'close_vs_entry',
    max_workers: int = 8,
    retries: int = 5,
    check_trading_day: bool = True,
    use_multi_source: bool = False,
) -> Dict[str, Any]:
    stocks: List[Dict[str, str]] = list(HSI_STOCKS)
    etnet_meta: Dict[str, Any] = {
        "enabled": False,
        "top_n": 10,
        "subtypes": [],
        "boards": {},
        "errors": {},
        "merged_extra": 0,
    }
    holdings_meta: Dict[str, Any] = {
        "count": 0,
        "merged_extra": 0,
        "source": None,
    }
    holdings_list: List[Dict[str, Any]] = []
    try:
        from src.services.hsi_holdings import load_holdings_from_env

        holdings_list = load_holdings_from_env()
        holdings_meta["count"] = len(holdings_list)
        if holdings_list:
            holdings_meta["source"] = "env"
            stocks, holdings_extra = merge_stocks_with_holdings(stocks, holdings_list)
            holdings_meta["merged_extra"] = holdings_extra
    except Exception as exc:
        logger.warning("HSI holdings merge skipped: %s", exc)
        holdings_meta["errors"] = str(exc)
        holdings_list = []

    try:
        from src.services.etnet_top_movers import (
            fetch_etnet_top_boards,
            resolve_etnet_top_config_from_env,
            unique_codes_from_boards,
        )

        cfg = resolve_etnet_top_config_from_env()
        etnet_meta["enabled"] = bool(cfg.get("enabled"))
        etnet_meta["top_n"] = cfg.get("top_n", 10)
        etnet_meta["subtypes"] = list(cfg.get("subtypes") or [])
        if cfg.get("enabled"):
            fetched = fetch_etnet_top_boards(
                subtypes=cfg.get("subtypes") or [],
                top_n=int(cfg.get("top_n") or 10),
            )
            boards = fetched.get("boards") or {}
            etnet_meta["boards"] = boards
            etnet_meta["errors"] = fetched.get("errors") or {}
            etnet_meta["subtypes"] = fetched.get("subtypes") or etnet_meta["subtypes"]
            extras, merged_extra = merge_stocks_with_etnet_top(
                stocks,
                unique_codes_from_boards(boards),
            )
            stocks = extras
            etnet_meta["merged_extra"] = merged_extra
    except Exception as exc:
        logger.warning("ET Net top movers merge skipped: %s", exc)
        etnet_meta["errors"] = {"_merge": str(exc)}

    payload = scan_stocks(
        stocks=stocks,
        period=period,
        conditions=conditions,
        max_workers=max_workers,
        retries=retries,
        check_trading_day=check_trading_day,
        use_multi_source=use_multi_source,
    )
    payload["etnet_top"] = etnet_meta
    payload["holdings_meta"] = holdings_meta
    if payload.get("skipped"):
        payload["holdings"] = []
    else:
        # Prefer all ok results; fall back to matches for older callers.
        scan_rows = payload.get("results") or payload.get("matches") or []
        payload["holdings"] = attach_holdings_to_results(holdings_list, scan_rows)
    return payload


def scan_hsi_and_notify(
    period: Optional[str] = None,
    conditions: Optional[str] = None,
    max_workers: Optional[int] = None,
    check_trading_day: bool = True,
    use_multi_source: bool = False,
) -> Dict[str, Any]:
    """Run HSI scan and send results through NotificationService to all configured channels."""
    env_cfg = get_scan_config_from_env()
    payload = scan_hsi(
        period=period or env_cfg['period'],
        conditions=conditions or env_cfg['conditions'],
        max_workers=max_workers or env_cfg['max_workers'],
        check_trading_day=check_trading_day,
        use_multi_source=use_multi_source,
    )

    if payload.get('skipped'):
        logger.info("HSI scan skipped: %s", payload.get('skip_reason'))
        return payload

    try:
        from src.notification import NotificationService
        notifier = NotificationService()
        if notifier.is_available():
            report = format_scan_report(payload)
            notifier.send(report, route_type="report")
            logger.info("HSI scan results sent via notification pipeline")
        else:
            logger.info("No notification channels configured, scan results not sent")
    except Exception as e:
        logger.warning("Failed to send HSI scan notification: %s", e)

    return payload


def _format_etnet_top_section(etnet_top: Optional[Dict[str, Any]]) -> List[str]:
    """Render 经济通 Top 10 成交額 / 成交股數 / 升幅（不含跌幅）。"""
    if not etnet_top or not etnet_top.get("enabled"):
        return []
    try:
        from src.services.etnet_top_movers import ALLOWED_SUBTYPES, SUBTYPE_LABELS
    except Exception:
        ALLOWED_SUBTYPES = ("turnover", "volume", "up")
        SUBTYPE_LABELS = {"turnover": "成交額", "volume": "成交股數", "up": "升幅"}

    boards = etnet_top.get("boards") or {}
    errors = etnet_top.get("errors") or {}
    lines: List[str] = []
    extra = etnet_top.get("merged_extra")
    if extra is not None:
        lines.append(f"*已将经济通榜单合并入扫描池：+{extra} 只代码*\n")

    for subtype in ALLOWED_SUBTYPES:
        label = SUBTYPE_LABELS.get(subtype, subtype)
        items = boards.get(subtype) or []
        lines.append(f"## 经济通 Top 10 {label}\n")
        if not items:
            err = errors.get(subtype)
            lines.append(f"无数据{f'（{err}）' if err else ''}。\n")
            continue
        metric_header = "成交股數" if subtype == "volume" else "成交金額"
        lines.append(f"| 排序 | 代号 | 名称 | 现价 | 变动率 | {metric_header} |")
        lines.append("|------|------|------|------|--------|----------|")
        for row in items:
            lines.append(
                f"| {row.get('rank', '')} | {row.get('code', '')} | {row.get('name', '')} "
                f"| {row.get('nominal', '')} | {row.get('change_pct', '')} "
                f"| {row.get('metric', '')} |"
            )
        lines.append("")
    return lines


def _format_holdings_section(holdings: Optional[List[Dict[str, Any]]]) -> List[str]:
    """Render 持仓止损参考 table (Turtle sell/keep/buy)."""
    rows = list(holdings or [])
    if not rows:
        return []
    action_label = {"sell": "卖出", "keep": "持有", "buy": "加仓"}
    lines: List[str] = [
        f"## 持仓止损参考（{len(rows)}）\n",
        "| 代号 | 名称 | 成本 | 现价 | 盈亏% | 2N止损 | 加仓½N | 建议 | 依据 |",
        "|------|------|------|------|-------|--------|--------|------|------|",
    ]
    for m in rows:
        code = m.get("code") or ""
        name = m.get("name") or code
        buy = m.get("buy_price")
        close = m.get("close")
        pnl = m.get("pnl_pct")
        stop = m.get("stop_from_entry_2n")
        add_lv = m.get("add_level_05n")
        action = m.get("turtle_action") or "keep"
        reason = (m.get("turtle_action_reason") or "").replace("|", "/")
        status = m.get("status")
        if status and status != "ok":
            reason = reason or f"信号不可用({status})"
        lines.append(
            f"| [{code}]({m.get('url', '')}) | {name} "
            f"| {buy if buy is not None else '暂无'} "
            f"| {close if close is not None else '暂无'} "
            f"| {pnl if pnl is not None else '暂无'} "
            f"| {stop if stop is not None else '暂无'} "
            f"| {add_lv if add_lv is not None else '暂无'} "
            f"| {action_label.get(str(action), str(action))} "
            f"| {reason} |"
        )
    lines.append("")
    return lines


def format_scan_report(payload: Dict[str, Any]) -> str:
    lines = []
    matches = payload.get('matches', [])
    no_price = payload.get('no_price', [])
    stats = payload.get('stats', {})

    if payload.get('skipped'):
        skip_reason = payload.get('skip_reason') or "今日休市"
        if skip_reason == "HK market closed today":
            skip_reason = "今日港股休市"
        return f"# 恒指信号扫描已跳过\n\n{skip_reason}"

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    lines.append(
        f"# 恒指信号扫描 — {stats.get('tickers', '?')} 只股票，耗时 {stats.get('total_ms', '?')}ms"
    )
    lines.append(f"*扫描时间：{timestamp}*\n")
    lines.extend(_format_etnet_top_section(payload.get("etnet_top")))
    lines.extend(_format_holdings_section(payload.get("holdings")))

    matches = sort_matches_by_potential(matches)
    if matches:
        lines.append(f"## 匹配结果（{len(matches)}）\n")
        lines.extend(format_match_result_table_lines(matches))
        lines.append("")
        lines.append("### 技术指标与形态\n")
        for m in matches:
            lines.extend(format_match_technical_lines(m))
            lines.append("")
        lines.append("")
    else:
        lines.append("没有股票符合所选条件。\n")

    if no_price:
        lines.append(f"### 无行情数据的代码（{len(no_price)}）\n")
        for np_item in no_price:
            lines.append(f"- {np_item['code']} ({np_item['name']}): {np_item['message']}")
        lines.append("")

    return "\n".join(lines)
