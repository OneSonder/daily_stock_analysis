# -*- coding: utf-8 -*-
"""Same-day disk cache for qualified-scan OHLCV frames."""

from __future__ import annotations

import logging
import os
import re
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SAFE_KEY_RE = re.compile(r"[^A-Za-z0-9._-]+")
_FALSE_VALUES = {"0", "false", "no", "off"}


def cache_enabled() -> bool:
    """Return whether qualified-scan OHLCV caching is enabled."""
    return os.getenv("REPORT_QUALIFIED_SCAN_CACHE_ENABLED", "true").strip().lower() not in _FALSE_VALUES


def cache_dir() -> Path:
    """Return configured cache directory, relative to project root when needed."""
    raw = os.getenv("REPORT_QUALIFIED_SCAN_CACHE_DIR", "data/cache/ohlcv").strip()
    path = Path(raw).expanduser()
    return path if path.is_absolute() else (_PROJECT_ROOT / path)


def _cache_path(code: str, period: str, as_of: date) -> Path:
    safe_code = _SAFE_KEY_RE.sub("_", code.strip().upper())
    safe_period = _SAFE_KEY_RE.sub("_", period.strip().lower())
    return cache_dir() / f"{safe_code}_{safe_period}_{as_of.isoformat()}.pkl"


def load_cached_history(
    code: str,
    period: str,
    *,
    as_of: Optional[date] = None,
) -> Optional[pd.DataFrame]:
    """Load a frame cached for the given calendar day."""
    if not cache_enabled():
        return None
    path = _cache_path(code, period, as_of or date.today())
    if not path.is_file():
        return None
    try:
        frame = pd.read_pickle(path)
    except Exception as exc:
        logger.warning("Ignoring unreadable OHLCV cache %s: %s", path, exc)
        return None
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return None
    return frame.copy()


def save_cached_history(
    code: str,
    period: str,
    frame: pd.DataFrame,
    *,
    as_of: Optional[date] = None,
) -> None:
    """Atomically cache a non-empty frame for the given calendar day."""
    if not cache_enabled() or frame is None or frame.empty:
        return
    path = _cache_path(code, period, as_of or date.today())
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    try:
        frame.to_pickle(temp_path)
        temp_path.replace(path)
    finally:
        temp_path.unlink(missing_ok=True)
