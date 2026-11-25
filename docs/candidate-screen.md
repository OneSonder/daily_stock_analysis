# Phase 1 daily candidate screen (US + HK)

Rules-only Yahoo scan. The main take is the close-first S1/S2 trend first-break list. It is a list of possible choices, not a buy list and not a position size.

## English summary

| Item | Value |
| --- | --- |
| Universes | Hang Seng constituents (`HSI_STOCKS`) and `US_TOP`. Not `HK_ALL`, not an open US universe, not A-shares, gold, bronze, or BTC. |
| HK schedule | 16:20 Asia/Shanghai, Monday–Friday. UTC cron `20 8 * * 1-5`. After the 16:08–16:10 closing auction. |
| US schedule | 05:20 Asia/Shanghai, Tuesday–Saturday. UTC cron `20 21 * * 1-5`. After the regular close in both EST and EDT. Saturday 28 Nov 2026 still stamps Friday 27 Nov (early close). |
| Stable artifacts | `reports/candidate_screen/hk/latest.md` and `reports/candidate_screen/us/latest.md`. The same run also writes `reports/candidate_screen/<market>/<as-of>.md`. Actions artifacts: `candidate-screen-hk`, `candidate-screen-us`. |
| HK floors | Last close ≥ HK$1. 20-day average turnover ≥ HK$20,000,000. Native HKD. |
| US floors | Last close ≥ US$5. 20-day average dollar volume ≥ US$5,000,000. Native USD. |
| Fail closed | Missing close, missing or uncomputable 20-day turnover, an as-of bar with zero turnover or no trade, or fewer than 15 of the last 20 sessions with a valid close and positive turnover. No markdown file is written. |
| Display caps | 4 / 6 / 10 / 12 (single market / tight group / loose group / one direction). Dual listings count as one company. These are not unit limits and are not share counts. |
| As-of | Every run calls `get_effective_trading_date` and stamps that session plus the bar date. |
| Out of band | No LLM, news, sentiment, Teams, or new notification tokens. `STOCK_LIST`, the workbench, and `HSI_HOLDINGS` are not read or written. `MONITOR_SIM_EQUITY` is not a book. |

Floors live in one module, `src/services/candidate_screen_policy.py`. The screen does not read `HK_SCAN_MIN_PRICE` to go back to HK$0.1 / HK$2,000,000. The all-HK research scan now uses the same HK numbers as its default, and still keeps a name when the print is missing. That research scan is not this daily take.

## 这是什么

每日候选筛选，不是买入清单，也不是交易预言。主名单只来自本叉每日监控的 **收盘价首次突破**（S1/S2 Close）：趋势过滤通过、放量、收盘在 MA100 之上、延伸 N 不超过 1。High-only 的「今日最高价相对 20/55 日高点」不入名单。止跌转折如果出现，只放在报告附录，不和主名单混表。

分数、交叉标签、新闻、情绪和 LLM 点评都不能放行或否决。

## 股票池与时间

| 市场 | 池 | 上海时间 | UTC cron |
| --- | --- | --- | --- |
| 港股 | 恒指成分 | 工作日 16:20 | `20 8 * * 1-5` |
| 美股 | `US_TOP` | 周二至周六 05:20 | `20 21 * * 1-5` |

不用 README 的 18:00 任务，也不用旧的 15:00 恒指 cron。工作流：`.github/workflows/candidate_screen.yml`，检出 `mine`。

`HK_ALL` 不是每日池。需要卫生刷新时另跑 `python scripts/generate_hk_universe.py`，不要把它接进这个定时任务。

每个上市代码只用自己的货币。港元、美元、人民币之间不做换算，也不用换算后的价格去判断突破或流动性。

## 流动性（失败关闭）

政策数字在 `src/services/candidate_screen_policy.py`。

| 市场 | 收盘 | 20 日均成交额 |
| --- | --- | --- |
| 港股 | ≥ 1 港元 | ≥ 20,000,000 港元 |
| US_TOP | ≥ 5 美元 | ≥ 5,000,000 美元 |

最近 20 个交易日里，至少 15 日要有有效收盘和正成交额，才计算这 20 日平均。当日成交额为 0、停牌、收盘缺失、样本不够，整次筛选失败，不写半份名单。

低于门槛但数据完整的名字会被排除，报告仍可写出。数据不完整则一份文件都不写。

## 显示上限

4 / 6 / 10 / 12：单市场 / 紧密组 / 松散组 / 单方向。这是名单上的家数上限，不是头寸单位，也不算出股数。双重上市（例如 `GOOG`/`GOOGL`，`9988.HK`/`BABA`）算一家公司：两个代码可以都出现，各用自己的价格，但只占一个名额。

N 是 20 日 ATR。2N 止损 = 收盘 − 2N。两者都只打印价格。

## 产物路径

稳定路径（Actions artifact 与本地 dry-run 相同）：

- `reports/candidate_screen/hk/latest.md`（artifact 名 `candidate-screen-hk`）
- `reports/candidate_screen/us/latest.md`（artifact 名 `candidate-screen-us`）

同一次运行另写 `reports/candidate_screen/<market>/<as-of>.md`。`reports/` 被 gitignore，名单不入库。

```bash
python scripts/run_candidate_screen.py --market hk --dry-run
python scripts/run_candidate_screen.py --market us --dry-run
```

`--dry-run` 与正式运行是同一条规则路径：只写 markdown，不碰 `STOCK_LIST`、工作台、`HSI_HOLDINGS`、通知或券商。

校验：

```bash
python -m pytest tests/test_candidate_screen.py -q
```

仓库内核对步骤见 `.claude/skills/verify-candidate-screen/SKILL.md`。
