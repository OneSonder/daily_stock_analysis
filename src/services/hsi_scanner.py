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


def _rsi_macd_indicator_score(technicals: Optional[Dict[str, Any]]) -> float:
    """Bounded RSI/MACD contribution to potential_score (−12 … +12). Soft-fail to 0."""
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
    rsi_weights = {
        "超卖": 6.0,
        "强势买入": 4.0,
        "中性": 0.0,
        "弱势": -3.0,
        "超买": -4.0,
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
    potential_score = max(
        0.0,
        min(
            100.0,
            base_score
            + kline_pattern_score
            + rsi_macd_score
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
        'kline_bullish': bool(len(kline_bullish_patterns) > 0),
        'kline_bearish': bool(len(kline_bearish_patterns) > 0),
        'rsi_macd_score': round(rsi_macd_score, 2),
        'potential_score': round(potential_score, 2),
        'potential_tier': potential_tier,
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

    return yf.Ticker(code).history(period=period)


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

    fetch_fn = fetch_history_with_data_provider if use_multi_source else lambda c, p: yf.Ticker(c).history(period=p)

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
) -> Dict[str, pd.DataFrame]:
    """Download multiple Yahoo histories in one batch request."""
    if not codes:
        return {}
    import yfinance as yf

    unique_codes = list(dict.fromkeys(code.strip().upper() for code in codes if code.strip()))
    logger.info(
        "Yahoo batch download starting: tickers=%s period=%s",
        len(unique_codes),
        period,
    )
    raw = yf.download(
        tickers=unique_codes,
        period=period,
        group_by='ticker',
        threads=False,
        progress=False,
        auto_adjust=True,
    )
    histories = _split_yfinance_batch(raw, unique_codes)
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
    yahoo_url = YAHOO_URL_TEMPLATE.format(code=code)
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
    yahoo_url = YAHOO_URL_TEMPLATE.format(code=code)
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
) -> Dict[str, Any]:
    """Scan an arbitrary stock universe with S1/S2 breakout conditions."""
    wanted = parse_conditions(conditions)

    if check_trading_day and not is_hk_market_open():
        return {
            'matches': [],
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
                downloaded = fetch_history_batch_yfinance(missing_codes, period)
            except Exception as exc:
                logger.warning(
                    "Yahoo batch download failed; using per-ticker fallback for %s tickers: %s",
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
            if code in prefetched:
                future = executor.submit(
                    evaluate_ticker_from_history_timed,
                    code,
                    item.get('name', ''),
                    prefetched[code],
                )
            else:
                fallback_retries = retries if use_multi_source else min(retries, 2)
                future = executor.submit(
                    evaluate_ticker_timed,
                    code,
                    item.get('name', ''),
                    period,
                    fallback_retries,
                    use_multi_source,
                )
            future_to_idx[future] = idx
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            results[idx] = future.result()

    total_ms = round((time.perf_counter() - started) * 1000, 2)
    logger.info(
        "scan_stocks tickers=%s max_workers=%s cache_hits=%s batch_downloaded=%s total_ms=%.2f",
        len(stocks),
        worker_count,
        cache_hits,
        batch_downloaded,
        total_ms,
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
            'cache_hits': cache_hits,
            'batch_downloaded': batch_downloaded,
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

    if matches:
        lines.append(f"## 匹配结果（{len(matches)}）\n")
        lines.append("| 代号 | 名称 | 收盘 | S1 | S2 | 收盘≥S1 | 收盘≥S2 |")
        lines.append("|------|------|------|----|----|--------|--------|")
        for m in matches:
            lines.append(
                f"| [{m['code']}]({m.get('url', '')}) | {m['name']} | {m['close']} "
                f"| {'✅' if m['s1_breakout'] else '❌'} "
                f"| {'✅' if m['s2_breakout'] else '❌'} "
                f"| {'✅' if m['close_vs_entry'] else '❌'} "
                f"| {'✅' if m['close_vs_s2_entry'] else '❌'} |"
            )
        lines.append("")
        lines.append("### 技术指标与形态\n")
        for m in matches:
            code = m.get('code', '')
            name = m.get('name', '')
            ma_bits = []
            for key in ('ma5', 'ma10', 'ma20', 'ma60'):
                val = m.get(key)
                if val is not None:
                    ma_bits.append(f"{key.upper()}={val}")
            ma_line = ', '.join(ma_bits) if ma_bits else '均线暂无'
            alignment = m.get('ma_alignment') or m.get('trend_status') or '暂无'
            rsi_line = (
                f"RSI6={m.get('rsi_6', '暂无')}, RSI12={m.get('rsi_12', '暂无')}"
                f" ({m.get('rsi_status') or '暂无'})"
            )
            macd_line = (
                f"MACD={m.get('macd_status') or '暂无'}"
                f" DIF={m.get('macd_dif', '暂无')} DEA={m.get('macd_dea', '暂无')}"
            )
            if m.get('macd_signal'):
                macd_line += f" — {m.get('macd_signal')}"
            pattern_text = format_pattern_names(m.get('kline_patterns') or [])
            lines.append(f"- **{name} ({code})**: {alignment}")
            lines.append(f"  - {ma_line}")
            lines.append(f"  - {rsi_line}")
            lines.append(f"  - {macd_line}")
            lines.append(f"  - 形态: {pattern_text}")
        lines.append("")
    else:
        lines.append("没有股票符合所选条件。\n")

    if no_price:
        lines.append(f"### 无行情数据的代码（{len(no_price)}）\n")
        for np_item in no_price:
            lines.append(f"- {np_item['code']} ({np_item['name']}): {np_item['message']}")
        lines.append("")

    return "\n".join(lines)
