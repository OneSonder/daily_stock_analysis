# -*- coding: utf-8 -*-
"""Static checks for HK Stocks Turtle Scan workflow (no LLM wiring)."""

from __future__ import annotations

from pathlib import Path

import yaml


ROOT_DIR = Path(__file__).resolve().parent.parent
HK_WORKFLOW = ROOT_DIR / ".github/workflows/hk_stocks_scan.yml"


def _load_workflow() -> dict:
    return yaml.safe_load(HK_WORKFLOW.read_text(encoding="utf-8"))


def _step_env(job_name: str, step_name: str) -> dict[str, str]:
    workflow = _load_workflow()
    steps = workflow["jobs"][job_name]["steps"]
    step = next(item for item in steps if item.get("name") == step_name)
    return step.get("env") or {}


def test_hk_stocks_workflow_is_manual_only_and_has_no_llm_or_tushare_secrets():
    workflow = _load_workflow()
    assert "workflow_dispatch" in workflow["on"]
    assert "schedule" not in workflow["on"]

    env = _step_env("hk-stocks-scan", "Run HK stocks Turtle scan")
    assert "TUSHARE_TOKEN" not in env
    assert "TENCENT_STOCK_NEWS_ENABLED" in env

    forbidden_keys = {
        "TUSHARE_TOKEN",
        "LITELLM_CONFIG",
        "LITELLM_API_KEY",
        "GEMINI_API_KEY",
        "OPENAI_API_KEY",
        "DEEPSEEK_API_KEY",
        "ANTHROPIC_API_KEY",
        "KIMI_API_KEY",
        "MOONSHOT_API_KEY",
        "LLM_PRIMARY_API_KEY",
        "ANSPIRE_API_KEYS",
        "BOCHA_API_KEYS",
        "TAVILY_API_KEYS",
    }
    for key in forbidden_keys:
        assert key not in env

    raw = HK_WORKFLOW.read_text(encoding="utf-8")
    assert "run_hk_stocks_scan" in raw
    assert "hk_all_stocks.json" in raw
    assert "TUSHARE_TOKEN" not in raw
    assert "hsi_enrichment" not in raw
    assert "DeepSeek" not in raw
    assert "Kimi" not in raw
    assert "Gemini" not in raw
