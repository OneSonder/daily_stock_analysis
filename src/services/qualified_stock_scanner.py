# -*- coding: utf-8 -*-
"""Generic qualified-stock scanner for daily reports.

Reuses S1/S2 breakout math from ``hsi_scanner`` and supports:
- built-in named conditions
- JSON rule expressions
- trusted local Python plugins
"""

from __future__ import annotations

import importlib.util
import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

from src.services.hsi_scanner import (
    HSI_STOCKS,
    VALID_CONDITIONS,
    _code_to_manager_format,
    parse_conditions,
    scan_stocks,
)

logger = logging.getLogger(__name__)

HSI_LIST_TOKEN = "HSI"
_PROJECT_ROOT = Path(__file__).resolve().parents[2]

_HSI_NAME_BY_CODE = {
    item["code"]: item.get("name", "")
    for item in HSI_STOCKS
}
_HSI_NAME_BY_MANAGER_CODE = {
    _code_to_manager_format(item["code"]): item.get("name", "")
    for item in HSI_STOCKS
}

_RULE_OPERATORS: Dict[str, Callable[[Any, Any], bool]] = {
    "eq": lambda actual, expected: actual == expected,
    "ne": lambda actual, expected: actual != expected,
    "gt": lambda actual, expected: actual is not None and actual > expected,
    "gte": lambda actual, expected: actual is not None and actual >= expected,
    "lt": lambda actual, expected: actual is not None and actual < expected,
    "lte": lambda actual, expected: actual is not None and actual <= expected,
    "in": lambda actual, expected: actual in (expected or []),
    "contains": lambda actual, expected: expected in (actual or []),
    "truthy": lambda actual, _expected: bool(actual),
    "falsy": lambda actual, _expected: not bool(actual),
}


def _to_yahoo_code(code: str) -> str:
    """Normalize HK manager codes to Yahoo ``0700.HK`` style."""
    upper = code.strip().upper()
    if upper.endswith(".HK"):
        return upper
    if upper.startswith("HK") and upper[2:].isdigit():
        return f"{int(upper[2:]):04d}.HK"
    return upper


def _load_stock_list_json(path: Path) -> List[Dict[str, str]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"Stock list JSON must be a list, got {type(raw).__name__}")
    stocks: List[Dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code", "")).strip()
        if not code:
            continue
        stocks.append({
            "code": _to_yahoo_code(code),
            "name": str(item.get("name", "")).strip(),
        })
    if not stocks:
        raise ValueError(f"No stocks found in {path}")
    return stocks


def _resolve_name(code: str, explicit_name: str = "") -> str:
    if explicit_name:
        return explicit_name
    yahoo_code = _to_yahoo_code(code)
    if yahoo_code in _HSI_NAME_BY_CODE:
        return _HSI_NAME_BY_CODE[yahoo_code]
    manager_code = _code_to_manager_format(yahoo_code)
    return _HSI_NAME_BY_MANAGER_CODE.get(manager_code, "")


def resolve_universe(
    stock_list: str,
    *,
    json_path: str = "",
) -> Tuple[List[Dict[str, str]], str]:
    """Resolve scan universe from config string."""
    raw = (stock_list or "").strip()
    if not raw:
        raise ValueError("Qualified scan stock list is empty")

    if json_path:
        path = Path(json_path).expanduser()
        if not path.is_absolute():
            path = (_PROJECT_ROOT / path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Qualified scan stock list JSON not found: {path}")
        return _load_stock_list_json(path), "json"

    if raw.upper() == HSI_LIST_TOKEN:
        return list(HSI_STOCKS), "hsi"

    if raw.lower().endswith(".json"):
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = (_PROJECT_ROOT / path).resolve()
        if path.is_file():
            return _load_stock_list_json(path), "json"

    tokens = [token.strip() for token in raw.split(",") if token.strip()]
    if len(tokens) == 1 and tokens[0].upper() == HSI_LIST_TOKEN:
        return list(HSI_STOCKS), "hsi"

    stocks = [
        {
            "code": _to_yahoo_code(token),
            "name": _resolve_name(token),
        }
        for token in tokens
    ]
    return stocks, "custom"


def _parse_rule_json(raw: str) -> Dict[str, Any]:
    if not raw or not str(raw).strip():
        return {}
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Qualified scan rule JSON must be an object")
    return payload


def _eval_rule(result: Dict[str, Any], rule: Dict[str, Any]) -> bool:
    field = rule.get("field")
    if not field:
        raise ValueError("Qualified scan rule is missing field")
    operator = str(rule.get("op", "eq")).lower()
    if operator not in _RULE_OPERATORS:
        raise ValueError(f"Unknown qualified scan rule operator: {operator}")
    actual = result.get(field)
    expected = rule.get("value")
    return _RULE_OPERATORS[operator](actual, expected)


def _apply_json_rules(matches: Sequence[Dict[str, Any]], rule_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not rule_json:
        return list(matches)

    rules = rule_json.get("rules")
    if not isinstance(rules, list) or not rules:
        return list(matches)

    match_mode = str(rule_json.get("match", "all")).lower()
    filtered: List[Dict[str, Any]] = []
    for result in matches:
        evaluations = [_eval_rule(result, rule) for rule in rules if isinstance(rule, dict)]
        if not evaluations:
            continue
        passed = all(evaluations) if match_mode != "any" else any(evaluations)
        if passed:
            filtered.append(result)
    return filtered


def _load_plugin_callable(plugin_path: str) -> Callable[..., List[Dict[str, Any]]]:
    path = Path(plugin_path).expanduser()
    if not path.is_absolute():
        path = (_PROJECT_ROOT / path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Qualified scan plugin not found: {path}")

    spec = importlib.util.spec_from_file_location(f"qualified_scan_plugin_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load qualified scan plugin: {path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    for attr in ("apply_rules", "filter_matches"):
        candidate = getattr(module, attr, None)
        if callable(candidate):
            return candidate

    raise AttributeError(
        f"Qualified scan plugin must define apply_rules(matches, config) or filter_matches(matches, config): {path}"
    )


def _apply_plugin(
    matches: Sequence[Dict[str, Any]],
    plugin_path: str,
    config: Dict[str, Any],
) -> List[Dict[str, Any]]:
    if not plugin_path:
        return list(matches)
    plugin = _load_plugin_callable(plugin_path)
    filtered = plugin(list(matches), config)
    if not isinstance(filtered, list):
        raise TypeError("Qualified scan plugin must return a list of match dicts")
    return filtered


def annotate_matched_conditions(
    matches: Sequence[Dict[str, Any]],
    wanted_conditions: Set[str],
) -> List[Dict[str, Any]]:
    annotated: List[Dict[str, Any]] = []
    for item in matches:
        row = dict(item)
        row["matched_conditions"] = sorted(
            cond for cond in wanted_conditions if row.get(cond)
        )
        annotated.append(row)
    return annotated


def run_qualified_scan(config: Any) -> Dict[str, Any]:
    """Run configured qualified-stock scan for daily report embedding."""
    if not getattr(config, "report_qualified_scan_enabled", False):
        return {"enabled": False}

    stock_list = getattr(config, "report_qualified_scan_stock_list", HSI_LIST_TOKEN)
    period = getattr(config, "report_qualified_scan_period", "6mo")
    conditions = getattr(config, "report_qualified_scan_conditions", "s1_breakout,s2_breakout")
    rule_json_raw = getattr(config, "report_qualified_scan_rule_json", "") or ""
    plugin_path = getattr(config, "report_qualified_scan_plugin", "") or ""
    max_workers = int(getattr(config, "report_qualified_scan_max_workers", 4) or 4)
    use_multi_source = bool(getattr(config, "report_qualified_scan_use_multi_source", False))
    max_results = int(getattr(config, "report_qualified_scan_max_results", 20) or 20)
    check_trading_day = bool(getattr(config, "report_qualified_scan_check_trading_day", False))

    try:
        wanted = parse_conditions(conditions)
        stocks, universe_label = resolve_universe(stock_list)
        data_source = "multi-source" if use_multi_source else "yfinance"
        logger.info(
            "Qualified scan starting: universe=%s tickers=%s conditions=%s source=%s",
            universe_label,
            len(stocks),
            conditions,
            data_source,
        )
        payload = scan_stocks(
            stocks=stocks,
            period=period,
            conditions=conditions,
            max_workers=max_workers,
            check_trading_day=check_trading_day,
            use_multi_source=use_multi_source,
        )
        if payload.get("skipped"):
            return {
                "enabled": True,
                "skipped": True,
                "skip_reason": payload.get("skip_reason", ""),
                "universe": universe_label,
                "conditions": sorted(wanted),
                "matches": [],
            }

        matches = annotate_matched_conditions(payload.get("matches", []), wanted)
        rule_json = _parse_rule_json(rule_json_raw)
        if rule_json:
            matches = _apply_json_rules(matches, rule_json)
        if plugin_path:
            plugin_config = {
                "conditions": sorted(wanted),
                "rule_json": rule_json,
                "universe": universe_label,
                "period": period,
            }
            matches = _apply_plugin(matches, plugin_path, plugin_config)

        if max_results > 0:
            matches = matches[:max_results]

        stats = payload.get("stats", {})
        logger.info(
            "Qualified scan complete: matches=%s tickers=%s total_ms=%s source=%s",
            len(matches),
            stats.get("tickers", len(stocks)),
            stats.get("total_ms"),
            data_source,
        )

        return {
            "enabled": True,
            "skipped": False,
            "universe": universe_label,
            "conditions": sorted(wanted),
            "matches": matches,
            "no_price": payload.get("no_price", []),
            "stats": payload.get("stats", {}),
        }
    except Exception as exc:
        logger.warning("Qualified stock scan failed: %s", exc, exc_info=True)
        return {
            "enabled": True,
            "error": str(exc),
            "matches": [],
        }


def format_qualified_scan_section(
    payload: Dict[str, Any],
    labels: Dict[str, str],
) -> str:
    """Render qualified scan section for fallback report builders."""
    if not payload or not payload.get("enabled"):
        return ""

    lines = [
        f"## {labels.get('qualified_scan_heading', 'Qualified Stocks')}",
        "",
    ]

    if payload.get("error"):
        lines.append(labels.get("qualified_scan_error", "Qualified scan unavailable"))
        lines.append("")
        return "\n".join(lines)

    if payload.get("skipped"):
        reason = payload.get("skip_reason") or labels.get("qualified_scan_skipped", "Scan skipped")
        lines.append(reason)
        lines.append("")
        return "\n".join(lines)

    matches = payload.get("matches") or []
    if not matches:
        lines.append(labels.get("qualified_scan_none", "No qualified stocks"))
        lines.append("")
        return "\n".join(lines)

    lines.extend([
        (
            f"| {labels.get('qualified_scan_code', 'Code')} "
            f"| {labels.get('qualified_scan_name', 'Name')} "
            f"| {labels.get('qualified_scan_close', 'Close')} "
            f"| {labels.get('qualified_scan_entry20', 'Entry20')} "
            f"| {labels.get('qualified_scan_entry55', 'Entry55')} "
            f"| {labels.get('qualified_scan_matched', 'Matched')} |"
        ),
        "|------|------|-------|--------|--------|--------|",
    ])
    for item in matches:
        matched = ", ".join(item.get("matched_conditions") or [])
        lines.append(
            f"| {item.get('code', '')} | {item.get('name', '')} | {item.get('close', '')} "
            f"| {item.get('entry20', '')} | {item.get('entry55', '')} | {matched} |"
        )
    lines.append("")
    return "\n".join(lines)
