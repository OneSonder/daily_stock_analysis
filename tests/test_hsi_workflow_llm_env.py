# -*- coding: utf-8 -*-
"""Static checks for HSI LLM secrets and optional commentary workflow wiring."""

from __future__ import annotations

from pathlib import Path

import yaml


ROOT_DIR = Path(__file__).resolve().parent.parent
HSI_WORKFLOW = ROOT_DIR / ".github/workflows/hsi_scan.yml"
DAILY_WORKFLOW = ROOT_DIR / ".github/workflows/00-daily-analysis.yml"


def _step_env(path: Path, job_name: str, step_name: str) -> dict[str, str]:
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    steps = workflow["jobs"][job_name]["steps"]
    step = next(item for item in steps if item.get("name") == step_name)
    return step["env"]


def test_hsi_scan_reads_llm_api_keys_only_from_repository_secrets():
    env = _step_env(HSI_WORKFLOW, "hsi-scan", "Run HSI scan + lite enrichment")

    assert env["GEMINI_API_KEY"] == "${{ secrets.GEMINI_API_KEY }}"
    assert env["DEEPSEEK_API_KEY"] == "${{ secrets.DEEPSEEK_API_KEY }}"
    assert env["DEEPSEEK_API_KEYS"] == "${{ secrets.DEEPSEEK_API_KEYS }}"
    assert "vars.GEMINI_API_KEY" not in env["GEMINI_API_KEY"]
    assert "vars.DEEPSEEK_API_KEY" not in env["DEEPSEEK_API_KEY"]


def test_hsi_scan_maps_optional_gemini_commentary_default_off():
    env = _step_env(HSI_WORKFLOW, "hsi-scan", "Run HSI scan + lite enrichment")

    assert "vars.GEMINI_COMMENT_ENABLED" in env["GEMINI_COMMENT_ENABLED"]
    assert "secrets.GEMINI_COMMENT_ENABLED" in env["GEMINI_COMMENT_ENABLED"]
    assert "'false'" in env["GEMINI_COMMENT_ENABLED"]
    assert "vars.GEMINI_COMMENT_MODEL" in env["GEMINI_COMMENT_MODEL"]
    assert "secrets.GEMINI_COMMENT_MODEL" in env["GEMINI_COMMENT_MODEL"]
    assert "gemini-3.6-flash" in env["GEMINI_COMMENT_MODEL"]
    assert "deepseek-v4-flash" in env["HSI_DEEPSEEK_MODEL"]


def test_daily_analysis_maps_same_secure_hsi_llm_settings():
    env = _step_env(DAILY_WORKFLOW, "analyze", "执行股票分析")

    assert env["GEMINI_API_KEY"] == "${{ secrets.GEMINI_API_KEY }}"
    assert env["DEEPSEEK_API_KEY"] == "${{ secrets.DEEPSEEK_API_KEY }}"
    assert env["DEEPSEEK_API_KEYS"] == "${{ secrets.DEEPSEEK_API_KEYS }}"
    assert "'false'" in env["GEMINI_COMMENT_ENABLED"]
    assert "gemini-3.6-flash" in env["GEMINI_COMMENT_MODEL"]
    assert "deepseek-v4-flash" in env["HSI_DEEPSEEK_MODEL"]
