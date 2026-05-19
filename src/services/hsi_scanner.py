import json
import logging
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

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
    {"code": "9999.HK", "name": "網易-S"},
]

VALID_CONDITIONS = {'close_vs_entry', 'close_vs_s2_entry', 's1_breakout', 's2_breakout', 's1_exit', 's2_exit'}

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
        if col.lower() in ('high', 'low', 'close') and col.islower():
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

    work = df[['High', 'Low', 'Close']].copy()

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

    if hist is None or hist.empty:
        return {
            'code': code, 'name': name, 'status': 'empty',
            'message': 'No data found (possibly invalid or delisted)',
            'url': yahoo_url,
        }

    try:
        sig = compute_signals_full(hist[['High', 'Low', 'Close']])
    except Exception as e:
        return {
            'code': code, 'name': name, 'status': 'insufficient_data',
            'message': str(e), 'url': yahoo_url,
        }

    return {
        'code': code, 'name': name, 'status': 'ok',
        'url': yahoo_url, **sig,
    }


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


def scan_hsi(
    period: str = '1y',
    conditions: str = 'close_vs_entry',
    max_workers: int = 8,
    retries: int = 5,
    check_trading_day: bool = True,
    use_multi_source: bool = False,
) -> Dict[str, Any]:
    wanted = parse_conditions(conditions)
    stocks = HSI_STOCKS

    # Trading day check
    if check_trading_day:
        if not is_hk_market_open():
            return {
                'matches': [],
                'no_price': [],
                'stats': {'tickers': len(stocks), 'max_workers': max_workers, 'total_ms': 0},
                'skipped': True,
                'skip_reason': 'HK market closed today',
            }

    started = time.perf_counter()

    results: List[Dict[str, Any]] = [None] * len(stocks)
    worker_count = max(1, max_workers)

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_to_idx = {
            executor.submit(
                evaluate_ticker_timed, item['code'], item['name'], period, retries, use_multi_source,
            ): idx
            for idx, item in enumerate(stocks)
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            results[idx] = future.result()

    total_ms = round((time.perf_counter() - started) * 1000, 2)
    logger.info("scan_hsi tickers=%s max_workers=%s total_ms=%.2f", len(stocks), worker_count, total_ms)

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
        },
        'skipped': False,
    }


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


def format_scan_report(payload: Dict[str, Any]) -> str:
    lines = []
    matches = payload.get('matches', [])
    no_price = payload.get('no_price', [])
    stats = payload.get('stats', {})

    if payload.get('skipped'):
        return f"# HSI Signal Scan Skipped\n\n{padding.get('skip_reason', 'Market closed')}"

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    lines.append(f"# HSI Signal Scan — {stats.get('tickers', '?')} tickers in {stats.get('total_ms', '?')}ms")
    lines.append(f"*Scanned at: {timestamp}*\n")

    if matches:
        lines.append(f"## Matches ({len(matches)})\n")
        lines.append("| Code | Name | Close | S1 | S2 | Cls≥S1 | Cls≥S2 |")
        lines.append("|------|------|-------|----|----|--------|--------|")
        for m in matches:
            lines.append(
                f"| [{m['code']}]({m.get('url', '')}) | {m['name']} | {m['close']} "
                f"| {'✅' if m['s1_breakout'] else '❌'} "
                f"| {'✅' if m['s2_breakout'] else '❌'} "
                f"| {'✅' if m['close_vs_entry'] else '❌'} "
                f"| {'✅' if m['close_vs_s2_entry'] else '❌'} |"
            )
        lines.append("")
    else:
        lines.append("No stocks matched the selected conditions.\n")

    if no_price:
        lines.append(f"### Tickers with no price data ({len(no_price)})\n")
        for np in no_price:
            lines.append(f"- {np['code']} ({np['name']}): {np['message']}")
        lines.append("")

    return "\n".join(lines)
