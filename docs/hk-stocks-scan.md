# 全港股海龟扫描（HK Stocks Turtle Scan）

手动 GitHub Actions 工作流，扫描 **全港股快照**，输出每日监控列表与匹配股的腾讯新闻。  
**不调用任何 LLM / AI**（无 DeepSeek / Kimi / Gemini / LiteLLM），也 **不依赖 Tushare**。

工作流文件：[`.github/workflows/hk_stocks_scan.yml`](../.github/workflows/hk_stocks_scan.yml)

## 前置条件

| 项 | 说明 |
| --- | --- |
| `resources/universes/hk_all_stocks.json` | 仓库内提交的全港股快照（`[{"code":"0700.HK","name":"..."}, ...]`）。刷新：`python scripts/generate_hk_universe.py` |
| Yahoo Finance | 历史 K 线批量下载（分块）；失败股票默认 **不** 再逐只重试，计入无行情统计。指数 banner 另取 `^HSI`。 |
| 腾讯财经 ifzq | 仅对 **列表内股票** 抓取个股新闻（默认开启，可用变量关闭）。 |

可选覆盖路径：环境变量 `HK_SCAN_UNIVERSE_PATH`。

## 运行方式

1. GitHub → Actions → **HK Stocks Turtle Scan** → Run workflow  
2. 可选输入：

| 输入 | 默认 | 说明 |
| --- | --- | --- |
| `period` | `1y` | 历史区间。监控需要约 100 根 K 线才能判定 MA100，请勿用 `3mo` |
| `monitor` | `true` | `true`：两份短名单（趋势首破 / 止跌转折）。`false`：旧版 OR 条件 dump |
| `conditions` | `s1_breakout,s2_breakout` | **仅** `monitor=false` 时生效 |
| `max_workers` | `8` | 并行评估线程 |
| `batch_size` | `80` | Yahoo 批量下载分块大小 |
| `news_max_age_days` | `2` | 腾讯新闻新鲜度窗口（天） |

也可通过环境变量覆盖：`HK_SCAN_PERIOD`、`HK_SCAN_MONITOR`、`HK_SCAN_MONITOR_LIMIT`、`HK_SCAN_MAX_EXTENSION_N`、`HK_SCAN_CONDITIONS`、`HK_SCAN_MAX_WORKERS`、`HK_SCAN_BATCH_SIZE`、`HK_NEWS_MAX_AGE_DAYS`、`HK_SCAN_UNIVERSE_PATH`、`TENCENT_STOCK_NEWS_ENABLED`、`HK_SCAN_MIN_PRICE`、`HK_SCAN_MIN_AVG_TURNOVER`、`HK_SCAN_REQUIRE_VOLUME_CONFIRM`、`HK_SCAN_REQUIRE_TREND`、`HK_SCAN_REQUIRE_MA100`。

## 报告内容

产物：`reports/hk_stocks_scan_YYYYMMDD_HHMMSS.md`（Actions Artifact：`hk-stocks-scan-report`）

默认 **每日监控** 包含：

- 扫描摘要 + **大盘**（恒指趋势 / MA100 / ATR%；恒指趋势未过则不列趋势首破）
- **趋势首破**：近 2 个交易日 Close 首次上穿 20/55 日通道，且趋势过滤通过、放量、MA100 上方、延伸 N ≤ 1.0
- **止跌转折**：S1 Close 首破，且趋势未过或收盘仍在 MA100 下方，需放量。与趋势首破互斥
- 每份名单上限 15（`HK_SCAN_MONITOR_LIMIT`）；表内是事件 + N/止损/量比，**不是**涨跌预测
- **对照**：相对上次扫描快照的 新 / 仍在 / 离开 / 换桶；跟丢 = 昨日名单上的名字今日跌破昨 2N 或收盘回到通道内。首次运行显示「无昨日对照」。Actions 用 cache 记住 `data/monitor_state`
- **持仓对照**（可选）：若设置了 `HSI_HOLDINGS`，名单标注持仓与距2N，未入名单也会列出
- **腾讯新闻（仅匹配股）**（仅上述名单）

`monitor=false` 时仍输出旧版「匹配结果 + 技术指标与形态」全量 dump。

### 监控入场规则（默认）

两份名单都 **不用** High-only 首破，也 **不把** RSI/MACD/K 线算进准入。

| 名单 | 必须满足 |
| --- | --- |
| 趋势首破 | `s2_recent_close_breakout`，或 (`s1_recent_close_breakout` 且 `s1_entry_allowed`)；`turtle_trend_ok`；`volume_confirm`；`close_vs_ma100 is True`；延伸 N 缺失或 ≤ `HK_SCAN_MAX_EXTENSION_N`（默认 1.0）；非 S1/S2 离场 |
| 止跌转折 | `s1_recent_close_breakout`；`turtle_trend_ok` 为假 **或** `close_vs_ma100` 为假；`volume_confirm`；非 S1 离场；且未进入趋势首破 |

`potential_score` 只做名单内并列时的次序，**不是**预测。

### 流动性（抓新闻前）

| 环境变量 | 默认 | 说明 |
| --- | --- | --- |
| `HK_SCAN_MIN_PRICE` | `0.1` | 最低收盘价（港币）；`0` 关闭 |
| `HK_SCAN_MIN_AVG_TURNOVER` | `2000000` | 近 20 日均成交额下限；缺数据不剔除；`0` 关闭 |
| `HK_SCAN_REQUIRE_VOLUME_CONFIRM` | `false` | 仅 `monitor=false` 的全局闸门；监控模式由分类器强制放量 |
| `HK_SCAN_REQUIRE_TREND` | `true` | 仅 `monitor=false` 时剔除趋势未过的匹配。监控模式下趋势只约束「趋势首破」 |
| `HK_SCAN_REQUIRE_MA100` | `false` | 仅 `monitor=false`。监控的趋势首破本身要求 MA100 上方 |
| `HK_SCAN_MONITOR_LIMIT` | `15` | 每份名单上限 |
| `HK_SCAN_MAX_EXTENSION_N` | `1.0` | 趋势首破允许的最大突破延伸（N 的倍数） |

### 近期突破字段

| 条件 | 含义 |
| --- | --- |
| `s1_recent_high_breakout` | 近 2 个交易日 High 首次上穿前 20 日最高价（监控名单不用） |
| `s2_recent_high_breakout` | 近 2 个交易日 High 首次上穿前 55 日最高价（监控名单不用） |
| `s1_recent_close_breakout` | 近 2 个交易日 Close 首次上穿前 20 日最高价 |
| `s2_recent_close_breakout` | 近 2 个交易日 Close 首次上穿前 55 日最高价 |

“首次”指该交易日相对其自身前一根 K 线从「未上穿」变为「上穿」；已在通道上方继续运行的不算。

**不包含**：持仓止损表（HSI 扫描那套 sell/keep/buy 主表）、经济通榜单、LLM 点评 / 决策仪表盘、全市场无行情明细列表。昨日对照与跟丢见上文「对照」。研究回放（非 Actions）见 [HSI 每日监控回放](hsi-monitor-sim.md) 与 [路线图](monitor-roadmap.md)。

## 与 HSI Signal Scan 的关系

| | HSI Signal Scan | HK Stocks Turtle Scan |
| --- | --- | --- |
| 股票池 | 恒指成分 + 可选持仓 / ET Net | `resources/universes/hk_all_stocks.json` |
| 默认报告 | 同一套每日监控两名单（上限 10）+ 恒指 banner | 每日监控两名单（上限 15）+ 恒指 banner |
| LLM | DeepSeek / 可选 Kimi·Gemini，只增强监控名单 + 持仓（默认不再把经济通额外代码送进 LLM） | **无** |
| 新闻 | 匹配增强路径（可含搜索兜底） | 仅腾讯 ifzq，且仅名单内 |
| 定时 | 已禁用（可手动） | 仅 `workflow_dispatch` |

两者独立；股票池与 `HK_ALL` / 技术筛选共用同一快照文件。HSI 可用 `HSI_SCAN_MONITOR=false` 恢复旧 OR dump。本地研究回放可用 `python scripts/simulate_hsi_monitor.py --universe hk --codes ...`，不要接到本 workflow。

## 局限与风险

- 全市场体量大，默认 `1y` 下载比 `3mo` 更重；Yahoo 分块仍可能耗时长或偶发缺数；缺数股票记为无行情，不拖垮整次扫描。
- 恒指 `^HSI` 拉取失败时 banner 显示数据不足，**不**因此压制趋势首破。
- JSON 快照会随 IPO/退市过期，需定期运行 `scripts/generate_hk_universe.py` 刷新。
- 腾讯 ifzq 为非官方接口，个别代码可能无新闻或短暂不可用。
- 输出为技术/规则信号参考，**不是**投资建议。海龟突破短线胜率本来就不高，名单短是为了少看假突破，不是保证上涨。
