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
| `conditions` | `s1_breakout,s2_breakout` | 匹配条件（与 HSI 扫描同一套字段）。可选近期严格首破：`s1_recent_high_breakout` / `s2_recent_high_breakout` / `s1_recent_close_breakout` / `s2_recent_close_breakout`（近 2 个交易日 High 或 Close 相对 Donchian 通道的首次上穿） |
| `max_workers` | `8` | 并行评估线程 |
| `batch_size` | `80` | Yahoo 批量下载分块大小 |
| `news_max_age_days` | `2` | 腾讯新闻新鲜度窗口（天） |

也可通过环境变量覆盖：`HK_SCAN_PERIOD`、`HK_SCAN_CONDITIONS`、`HK_SCAN_MAX_WORKERS`、`HK_SCAN_BATCH_SIZE`、`HK_NEWS_MAX_AGE_DAYS`、`HK_SCAN_UNIVERSE_PATH`、`TENCENT_STOCK_NEWS_ENABLED`、`HK_SCAN_MIN_PRICE`、`HK_SCAN_MIN_AVG_TURNOVER`、`HK_SCAN_REQUIRE_VOLUME_CONFIRM`、`HK_SCAN_REQUIRE_TREND`、`HK_SCAN_REQUIRE_MA100`。

## 报告内容

产物：`reports/hk_stocks_scan_YYYYMMDD_HHMMSS.md`（Actions Artifact：`hk-stocks-scan-report`）

包含：

- 扫描摘要（池大小、来源、匹配数、缓存/批量统计）
- **匹配结果**（按潜力分降序：档/分、S1 开仓、趋势、MA100、延伸 N、量比、20 日均额、ATR%、S1/S2、近期首破）
- **技术指标与形态**（均线 / RSI / MACD / K 线形态 + 海龟 N、2N 止损参考、趋势过滤、S1 盈利跳过、近期首破、潜力说明、流动性）
- **腾讯新闻（仅匹配股）**（原文条目；抓取失败时软降级）

### 潜力分与流动性

`potential_score` 是 **setup 质量排序**，不是涨跌预测。相对纯突破计分：

- RSI 超卖不再加分，超买不再扣分（避免把均值回归混进趋势突破）
- 近 2 日 Close/High 首破、放量确认、较小延伸 N 加分；过晚延伸、过低成交额/股价减分

全港股匹配在抓新闻前默认再过滤：

| 环境变量 | 默认 | 说明 |
| --- | --- | --- |
| `HK_SCAN_MIN_PRICE` | `0.1` | 最低收盘价（港币）；`0` 关闭 |
| `HK_SCAN_MIN_AVG_TURNOVER` | `500000` | 近 20 日均成交额下限；缺数据不剔除；`0` 关闭 |
| `HK_SCAN_REQUIRE_VOLUME_CONFIRM` | `false` | `true` 时剔除「有量比但未放量」的匹配；缺量比不剔除 |
| `HK_SCAN_REQUIRE_TREND` | `true` | 剔除 `turtle_trend_ok` 未通过的匹配（默认 MA20>MA55 或 MA50>MA300） |
| `HK_SCAN_REQUIRE_MA100` | `false` | `true` 时剔除收盘低于 MA100 的匹配；**缺 100 根 K 线不剔除**。请用 `period=1y`（默认 `3mo` 会显示 MA100=`不足`） |

可选扫描条件 `close_vs_ma100` 可写入 `conditions`（仅当历史足够时才会为 true）。

### 近期突破条件（可选）

默认仍为当日 `s1_breakout,s2_breakout`。若要筛选「刚突破」，可改用或追加：

| 条件 | 含义 |
| --- | --- |
| `s1_recent_high_breakout` | 近 2 个交易日 High 首次上穿前 20 日最高价 |
| `s2_recent_high_breakout` | 近 2 个交易日 High 首次上穿前 55 日最高价 |
| `s1_recent_close_breakout` | 近 2 个交易日 Close 首次上穿前 20 日最高价 |
| `s2_recent_close_breakout` | 近 2 个交易日 Close 首次上穿前 55 日最高价 |

“首次”指该交易日相对其自身前一根 K 线从「未上穿」变为「上穿」；已在通道上方继续运行的不算。报告中显示 `今日` / `前一交易日` / `无`。

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
