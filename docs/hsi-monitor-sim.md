# HSI 每日监控回放（研究工具）

对 **当前恒指成分** 把线上「趋势首破 / 止跌转折」规则按交易日逐日重放，再量警报质量（MAE/MFE/E-ratio，对照随机抽签）和简单海龟纸上交易（次日开盘、2N 止损、无加仓）。

**不是预测，也不会改线上扫描规则。** 不含 LLM。不要接到 GitHub Actions（Yahoo 下载 + CPU 都不适合 CI）。

实现：[src/services/monitor_simulator.py](../src/services/monitor_simulator.py)  
入口：`python scripts/simulate_hsi_monitor.py`

## 怎么跑

在仓库根目录：

```text
python scripts/simulate_hsi_monitor.py
python scripts/simulate_hsi_monitor.py --period 2y --horizon 20 --limit 10
python scripts/simulate_hsi_monitor.py --book turtle
python scripts/simulate_hsi_monitor.py --universe hk --codes 0700.HK,0005.HK --period 2y
python scripts/simulate_hsi_monitor.py --no-network
python scripts/simulate_hsi_monitor.py --refresh --period 5y
```

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `--period` | `5y`（`MONITOR_SIM_PERIOD`） | Yahoo 历史窗口。`2y` 冒烟；`10y` 只作稳健性，不更“真” |
| `--horizon` | `20` | 信号后用于 MAE/MFE 与时间止损的交易日数 |
| `--warmup` | `100` | 第一根回放日之前至少要有这么多收盘（MA100） |
| `--limit` | HSI 10 / HK 15 | 与线上相同的每名单上限 |
| `--max-extension-n` | `1.0` | 与线上趋势首破延伸闸门相同 |
| `--cost-bps` | `20` | 仅从纸上收益扣的往返成本（基点） |
| `--universe` | `hsi` | `hk` 读全港股快照并套用线上流动性闸门；全市场 5y 很慢，请用 `--codes` 冒烟 |
| `--codes` | 空 | 逗号分隔子集 |
| `--book` | `simple` | `simple`：次日开盘 2N+时间止损。`turtle`：1% 单位、½N 加仓、最多 4 单位/12 总单位、Donchian 离场 |
| `--equity` | `1000000` | `--book turtle` 的名义本金 |
| `--progress-every` | `20` | 每 N 个回放日打一条日志 |
| `--no-network` | 关 | 只读 `data/cache/ohlcv/`，缺 `^HSI` 或全部个股则失败 |
| `--refresh` | 关 | 忽略缓存，重新下载（不可与 `--no-network` 同用） |

产物（`reports/`，已 gitignore）：

- `hsi_monitor_sim_YYYYMMDD_HHMMSS.md`
- `hsi_monitor_sim_YYYYMMDD_HHMMSS_alerts.csv`
- `hsi_monitor_sim_YYYYMMDD_HHMMSS_trades.csv`

OHLCV **不**写入 CSV。K 线只进 pickle 缓存。

## 本地缓存

第一次跑会向 Yahoo 批量拉恒指成分 + `^HSI`，写入 [`data/cache/ohlcv/`](../src/services/ohlcv_cache.py)（`{CODE}_{period}_{YYYY-MM-DD}.pkl`，与线上扫描同一目录）。回放只在内存里切 `iloc`，不会按日重下。

线上缓存按 **日历日** 分文件。回放会在缺少“今天”的文件时改用该代码+period **最新一份** pickle，避免隔夜研究还要再打 Yahoo。`--refresh` 强制重拉。目录 `/data/` 已在 `.gitignore`。

体量大约：2 年数 MB，5 年仍远小于 50 MB。真正的成本是 CPU（每个交易日对每只股票跑一遍与线上相同的 `compute_signals_full`）。5 年全成分可能要数十分钟到数小时。

## 为什么默认 5 年

| 窗口 | 用途 |
| --- | --- |
| 2y | 冒烟、确认脚本能跑通 |
| **5y** | 默认。比 2 年多几个涨跌段，下载仍然很小 |
| 10y | 可选对照。统计样本更大，但下面的生存者偏差也更大 |

更多年份不会让单次回放“更准”，只是多覆盖一些行情状态。

## 生存者偏差

[`HSI_STOCKS`](../src/services/hsi_scanner.py) 是 **今天的** 成分，用在过去每一天。新上市、已剔除、当时还不在指数里的名字都会被当成“一直在指数里”。这不是点-in-time 恒指回测；10 年窗口把这个问题放得更大。点-in-time 成分不在本工具范围内。

## 规则与指标

准入与线上 [`classify_daily_monitor`](../src/services/daily_monitor.py) 相同：Close 首破、放量、MA100/趋势分桶、延伸 N、恒指趋势未过则不列趋势首破。RSI/MACD/K 线不算准入。近 2 日 flag 只在股票 **第一次** 出现在当日名单时计一次警报。

**警报质量**（相对 **信号收盘**，向前 `horizon` 根 K）：

- MAE / MFE，再除以信号日 N，得到 E-ratio = mean(MFE/N) / mean(MAE/N)
- 1 / 5 / horizon 日收盘相对变化；胜率 = horizon 收盘高于信号收盘
- 随机对照：同一天、相同数量、从未进入任一名单的可评估成分股

**纸上交易**（与 E-ratio 分开，入场不是信号收盘）：

- 次一交易日开盘（无开盘则用该日收盘）
- 止损 = 入场价 − 2N（N 用信号日）
- 先触及盘中最低 ≤ 止损则按止损价出；否则持有满 `horizon` 根 K 按收盘出
- 无 ½N 加仓、无 4 单位上限、无 S1 跳过上次盈利的组合层
- 同一代码未平时忽略新警报
- 趋势首破与止跌转折 **两本账**
- 平均 R = (平仓 − 开仓 − 成本) / (2N)；最大回撤是等权 1 股账户的价格单位，不是 1% 风险组合

Faith 提醒：短周期 Donchian 样本里经常先亏；回测会撒谎（交易者效应、运气、过拟合）。把表里的 E-ratio 当成研究数字，不要当成明年的期望。

## 环境变量

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `MONITOR_SIM_PERIOD` | `5y` | 历史窗口 |
| `MONITOR_SIM_HORIZON` | `20` | 前瞻根数 |
| `MONITOR_SIM_WARMUP` | `100` | 回放预热 |
| `MONITOR_SIM_COST_BPS` | `20` | 纸上往返成本（bp） |
| `MONITOR_SIM_SEED` | `42` | 随机对照抽样 |
| `MONITOR_SIM_EQUITY` | `1000000` | `--book turtle` 名义本金 |
| `HSI_SCAN_MONITOR_LIMIT` | `10` | 每名单上限 |
| `HSI_SCAN_MAX_EXTENSION_N` | `1.0` | 趋势首破延伸 |
| `MONITOR_DELTA` | `true` | 线上扫描昨日对照 |
| `MONITOR_STATE_DIR` | `data/monitor_state` | 对照快照目录 |
| `REPORT_QUALIFIED_SCAN_CACHE_ENABLED` | `true` | 磁盘缓存开关 |
| `REPORT_QUALIFIED_SCAN_CACHE_DIR` | `data/cache/ohlcv` | 缓存目录 |

## 不在范围内

Web/API 页、把回放接到 GitHub Action、点-in-time 恒指成分、改线上扫描闸门（除非回放数字支持）、在**线上名单**上做 ½N 加仓。
