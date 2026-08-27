# 全港股海龟扫描（HK Stocks Turtle Scan）

手动 GitHub Actions 工作流，扫描 **全港股快照**，输出海龟/技术匹配结果与匹配股的腾讯新闻。  
**不调用任何 LLM / AI**（无 DeepSeek / Kimi / Gemini / LiteLLM），也 **不依赖 Tushare**。

工作流文件：[`.github/workflows/hk_stocks_scan.yml`](../.github/workflows/hk_stocks_scan.yml)

## 前置条件

| 项 | 说明 |
| --- | --- |
| `resources/universes/hk_all_stocks.json` | 仓库内提交的全港股快照（`[{"code":"0700.HK","name":"..."}, ...]`）。刷新：`python scripts/generate_hk_universe.py` |
| Yahoo Finance | 历史 K 线批量下载（分块）；失败股票默认 **不** 再逐只重试，计入无行情统计。 |
| 腾讯财经 ifzq | 仅对 **匹配股** 抓取个股新闻（默认开启，可用变量关闭）。 |

可选覆盖路径：环境变量 `HK_SCAN_UNIVERSE_PATH`。

## 运行方式

1. GitHub → Actions → **HK Stocks Turtle Scan** → Run workflow  
2. 可选输入：

| 输入 | 默认 | 说明 |
| --- | --- | --- |
| `period` | `3mo` | 历史区间 |
| `conditions` | `s1_breakout,s2_breakout` | 匹配条件（与 HSI 扫描同一套 Turtle S1/S2 字段） |
| `max_workers` | `8` | 并行评估线程 |
| `batch_size` | `80` | Yahoo 批量下载分块大小 |
| `news_max_age_days` | `2` | 腾讯新闻新鲜度窗口（天） |

也可通过环境变量覆盖：`HK_SCAN_PERIOD`、`HK_SCAN_CONDITIONS`、`HK_SCAN_MAX_WORKERS`、`HK_SCAN_BATCH_SIZE`、`HK_NEWS_MAX_AGE_DAYS`、`HK_SCAN_UNIVERSE_PATH`、`TENCENT_STOCK_NEWS_ENABLED`。

## 报告内容

产物：`reports/hk_stocks_scan_YYYYMMDD_HHMMSS.md`（Actions Artifact：`hk-stocks-scan-report`）

包含：

- 扫描摘要（池大小、来源、匹配数、缓存/批量统计）
- **匹配结果**（S1/S2 突破与收盘相对入场位）
- **技术指标与形态**（均线 / RSI / MACD / K 线形态 + 海龟 N、2N 止损参考、趋势过滤、S1 盈利跳过）
- **腾讯新闻（仅匹配股）**（原文条目；抓取失败时软降级）

**不包含**：持仓止损表、经济通榜单、LLM 点评 / 决策仪表盘、全市场无行情明细列表。

## 与 HSI Signal Scan 的关系

| | HSI Signal Scan | HK Stocks Turtle Scan |
| --- | --- | --- |
| 股票池 | 恒指成分 + 可选持仓 / ET Net | `resources/universes/hk_all_stocks.json` |
| LLM | DeepSeek / 可选 Kimi·Gemini | **无** |
| 新闻 | 匹配增强路径（可含搜索兜底） | 仅腾讯 ifzq，且仅匹配股 |
| 定时 | 已禁用（可手动） | 仅 `workflow_dispatch` |

两者独立；本工作流不修改 HSI 流程。股票池与 `HK_ALL` / 技术筛选共用同一快照文件。

## 局限与风险

- 全市场体量大，Yahoo 分块下载仍可能耗时长或偶发缺数；缺数股票记为无行情，不拖垮整次扫描。
- JSON 快照会随 IPO/退市过期，需定期运行 `scripts/generate_hk_universe.py` 刷新。
- 腾讯 ifzq 为非官方接口，个别代码可能无新闻或短暂不可用。
- 输出为技术/规则信号参考，**不是**投资建议。
