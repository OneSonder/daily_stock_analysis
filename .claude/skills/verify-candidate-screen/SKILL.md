---
name: verify-candidate-screen
description: Verify the Phase 1 US+HK close-first candidate screen. Use when checking universe, S1/S2 close breaks, liquidity fail-closed rules, as-of stamps, N/2N prices, group caps, currency isolation, the book ring-fence, or the Actions schedule.
---

# Verify the candidate screen

规则真源是仓库根目录 `AGENTS.md`。本 skill 只核对 Phase 1 每日候选筛选，不改交易规则，也不放宽 `src/services/candidate_screen_policy.py` 里的流动性门槛。

## 核对范围

- 每日池只有恒指成分和 `US_TOP`。不是 `HK_ALL`，不含 A 股、黄金、青铜、BTC。
- 主名单只用收盘价 S1/S2 首次突破。High-only、分数、交叉标签、新闻、LLM 不能放行。
- 收盘或 20 日成交额缺失、当日零成交、最近 20 日里有效样本少于 15，则失败关闭，不写 markdown。
- 每次扫描都调用 `get_effective_trading_date`，报告同时写下 as-of session 和 bar date。
- N 与 2N 止损只以价格出现，没有股数或名义金额。
- 显示上限 4 / 6 / 10 / 12。双重上市算一家公司。
- 港元和美元各自比较，不换算。
- 不写 `STOCK_LIST`、工作台、`HSI_HOLDINGS`，不用 `MONITOR_SIM_EQUITY` 当账本。
- 定时是上海时间港股工作日 16:20、美股周二至周六 05:20。不是 18:00，也不是旧的 15:00 恒指 cron。

## 命令

```bash
python -m pytest tests/test_candidate_screen.py -q
python -m py_compile src/services/candidate_screen.py src/services/candidate_screen_policy.py scripts/run_candidate_screen.py
python scripts/run_candidate_screen.py --market hk --dry-run
python scripts/run_candidate_screen.py --market us --dry-run
```

Dry-run 成功时，标准输出里的 `artifact_latest` 应为：

- `reports/candidate_screen/hk/latest.md`
- `reports/candidate_screen/us/latest.md`

失败关闭时进程退出码为 1，并且这两个文件不应在这次失败中被新建。不要为了让 dry-run 通过而调低门槛。
