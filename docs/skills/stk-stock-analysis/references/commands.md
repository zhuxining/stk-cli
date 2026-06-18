# 命令速查

所有命令通过统一 JSON envelope 输出：`{"ok": true, "data": ..., "error": null, "meta": {...}}`。技能报告只读取 `data`。技术指标含义和报告解释口径见 `references/indicator-guide.md`。

---

## Market

### `stk market`

市场概览：主要指数按 `CN` / `HK` / `US` 分组，并返回三地市场温度。

返回 `MarketOverview`：

- `indices`: `{region: [IndexQuote]}`，含 `symbol`、`name`、`region`、`last`、`change`、`change_pct`、`volume`。
- `temperature`: `{region: MarketTemperature}`，含 `score`、`level`、`valuation`、`sentiment`。

---

## Stock

### `stk stock rank`

单个同花顺技术 screen 排名。

| 参数 | 默认 | 说明 |
|------|------|------|
| `--screen` / `-s` | `lxsz` | `lxsz` / `cxfl` / `xstp` / `ljqs` / `cxsl` / `lxxd` / `xxtp` / `ljqd` |
| `--ma` | `20日均线` | `xstp` / `xxtp` 专用均线 |

返回 `TechRank`：

- `type`
- `label`
- `items[]`: `code`、`name`、`metrics`

### `stk stock hotspot`

行业多空情绪统计，基于带“所属行业”的技术 screen 汇总。

| 参数 | 默认 | 说明 |
|------|------|------|
| `--ma` | `20日均线` | `xstp` / `xxtp` 专用均线 |

返回 `TechIndustries`：

- `industries[]`: `industry`、`bull_count`、`bear_count`、`bull_screens`、`bear_screens`

### `stk stock candidates`

跨 screen 技术候选股，返回出现在 2 个及以上多方 screen 的股票。

| 参数 | 默认 | 说明 |
|------|------|------|
| `--ma` | `20日均线` | `xstp` / `xxtp` 专用均线 |

返回 `TechCandidates`：

- `candidates[]`: `code`、`name`、`bull_screens`
- `total`

注意：`candidates` 是技术 screen 初筛，不代表趋势信号确认；需要继续执行 `stk stock scan <symbols...>`。

### `stk stock scan <symbols...>`

对一个或多个 symbol 做每日监控扫描，返回需要重点关注的信号标的。

示例：

```bash
stk stock scan 600519 000001 700.HK
stk stock scan 600519 --daily10
stk stock scan 600519 --full-context
```

| 参数 | 默认 | 说明 |
|------|------|------|
| `--daily10` | `false` | 为强信号且辅助态度不冲突的标的补充最近 10 根压缩完整日线。默认关闭，避免批量扫描输出过大。 |
| `--full-context` | `false` | 输出完整辅助因子，包括 `neutral` 和 `none`。默认仅保留有判断价值的因子，减少批量扫描输出。 |

返回 `MonitorResult`：

- `run_date`: 本次运行日期。
- `universe`: `name`、`total`、`scanned`、`failed`。
- `summary`: `focus_count`、`strong_signal_count`、`entry_signal_count`、`exit_signal_count`、`watch_signal_count`。
- `focus[]`: 重点关注标的列表，默认只包含可行动的买入或退出信号。
- `ignored`: `no_signal_count`。
- `errors[]`: 单标的非致命错误。

`focus[]` 中每个 `FocusItem` 含：

- 展示字段：`symbol`、`name`、`last`、`change_pct`、`source`。
- `decision`: `signal`、`strength`、`signal_status`、`signal_date`、`bars_since_signal`。
- `primary_signal`: `ema_cross`、`ema9`、`ema26`、`supertrend`、`supertrend_direction`、`adx`、`reasons`。
- `context`: `overall_bias`、`factors[]`、`warnings[]`；默认省略 `neutral` / `none` 因子，需要完整复盘时加 `--full-context`。
- `risk`: `atr`、`stop_loss`、`take_profit`、`risk_reward_ratio`、`risk_level`。
- `daily10`: 仅在传入 `--daily10` 且标的为强信号、辅助态度不冲突时出现，用于复核价格结构和指标变化。

有效信号口径：

- 主策略：趋势共振和超卖修复两类，完整日线确认。
- 盘前和盘中扫描使用上一根完整日线；盘后超过市场确认缓冲时间后才纳入当天日线。实时 `last` / `change_pct` 只用于展示，不参与信号、辅助因子和风控计算。
- `signal`: `趋势买入` / `趋势退出` / `超卖修复` / `观察`。
- `strength`: `强信号` / `普通信号` / `观察`。
- 退出类信号表示减仓、退出或风险预警，不表达做空建议。
- `primary_signal.adx < 20` 表示趋势强度偏弱，`>=25` 表示趋势质量较好；ADX 不直接改变 `strength`。
- 退出类信号中的 `risk.stop_loss` 表示上方失效线，`risk.take_profit` 表示下行风险参考，不代表做空建议。
- `观察` 默认不进入 `focus`，只计入 `ignored.no_signal_count`；不要升级成买入、卖出或加仓建议。

辅助因子读取口径：

| factor | 主要 metrics | 分析用途 |
|--------|--------------|----------|
| `momentum` | `rsi14`、`rsi_zone`、`k`、`d`、`j`、`kdj_bias` | 判断动量是否支持主方向，以及是否过热/过冷。 |
| `macd` | `dif`、`dea`、`hist`、`bias` | 判断 MACD 多空状态与主信号是否一致。 |
| `boll` | `upper`、`middle`、`lower`、`position_pct`、`bandwidth_pct` | 判断价格在布林区间中的位置，以及是否处于波动收敛。 |
| `volume_price` | `volume_ratio_5d`、`price_change_pct` | 基于完整日线判断上涨/下跌是否有量能确认。 |
| `ema_trend` | `ema5`、`ema10`、`ema20`、`arrangement` | 判断短周期均线排列是否顺势。 |
| `money_flow` | `mfi14`、`mfi_zone` | 结合主方向判断资金流强弱和过热风险。 |
| `divergence` | `type`、`lookback`、`price_distance_pct`、`hist_delta` | 判断 MACD 顶/底背离，只作为风险或机会提示。 |

`daily10` 压缩完整日线字段（需显式传入 `--daily10`）：

- 价格量能：`date`、`open`、`high`、`low`、`close`、`volume`、`turnover`、`change_pct`。
- 主信号：`ema9`、`ema26`、`supertrend`、`supertrend_direction`。
- 辅助指标：`macd`、`macd_signal`、`macd_hist`、`rsi14`、`j`、`boll_position_pct`、`atr10`。
- 使用方式：复核信号出现在第几根 K 线、触发后是否延续、是否放量、是否过热，不用 `daily10` 重新计算 `decision.strength`。

### `stk stock scan-live <symbols...>`

对一个或多个 symbol 做实盘提醒扫描。它先用 `stk stock scan` 同源的完整日线信号做底层过滤，再用完整的 5m/15m K 线判断盘中触发。

示例：

```bash
stk stock scan-live 600519 300750
stk stock scan-live 600519 --timeframe 5m
```

| 参数 | 默认 | 说明 |
|------|------|------|
| `--timeframe` / `-t` | `15m` | 实盘 K 线周期：`5m` / `15m`。 |
| `--count` / `-c` | `80` | 读取的分钟 K 线根数。 |

返回 `LiveScanResult`：

- `mode`: 固定为 `live`。
- `as_of`: 本次扫描时间。
- `timeframe`: 实盘 K 线周期。
- `summary`: `focus_count`、`follow_count`、`weaken_count`、`overheated_count`、`observe_count`。
- `focus[]`: 盘中触发提醒标的。
- `ignored.no_live_signal_count`: 日线背景或分钟线未触发的数量。
- `errors[]`: 单标的非致命错误。

`focus[]` 中每个 `LiveFocusItem` 含：

- `daily_signal` / `daily_strength`: 日线背景。
- `live_signal`: `实时跟随`、`实时转弱`、`实时过热`。
- `strength`: `强提醒` 或 `普通提醒`。
- `trigger`: 触发原因。
- `risk_line`: 分钟触发失效线或观察线。
- `volume_ratio`: 最新完整分钟 K 成交额相对最近分钟均值。
- `vwap`、`ema20`、`rsi14`: 实盘判断用的分钟指标。

实盘扫描口径：

- 只使用已完成的分钟 K 线；实时价只作为展示。
- 日线为 `观察`、信号过期或强度为 `观察` 的标的不会进入实盘触发计算。
- `实时跟随`：日线偏多，分钟收盘站上 VWAP 和 EMA20。
- `实时转弱`：日线偏多但分钟线跌破 VWAP/EMA20 或开盘区间低点；或日线退出信号下继续弱势。
- `实时过热`：日线偏多，但分钟 RSI 或相对 VWAP 偏离过热。

### `stk stock kline <symbols...>`

获取 K 线和全部技术指标，用于解释信号来源。

| 参数 | 默认 | 说明 |
|------|------|------|
| `--type` / `-t` | `stock` | `stock` / `index` |
| `--period` / `-p` | `day` | `day` / `week` / `month` |
| `--count` / `-c` | `20` | 返回的 K 线数量 |

返回 `list[DailyResult]`，每个 `DailyResult` 含：

- `symbol`
- `days[]`: 每日 OHLCV、`change_pct` 和指标字段

主要指标字段：

- EMA：`EMA5`、`EMA9`、`EMA10`、`EMA20`、`EMA26`、`EMA60`
- MACD：`MACD`、`signal`、`hist`
- RSI：`RSI`
- KDJ：`K`、`D`、`J`
- BOLL：`upper`、`middle`、`lower`
- ATR：`ATR10`、`ATR14`
- Supertrend：`Supertrend`、`SupertrendDirection`

### `stk stock fundamental <symbol>`

同业对比，用于补充估值、成长性和杜邦分析。

| 参数 | 默认 | 说明 |
|------|------|------|
| `--type` / `-t` | `all` | `all` / `growth` / `valuation` / `dupont` |

返回 `FullComparison` 或 `IndustryComparison`。`dupont` 仅 A 股支持，港股/美股可能无该项。

---

## Watchlist

### 管理命令

| 命令 | 说明 |
|------|------|
| `stk watchlist list` | 列出所有分组 |
| `stk watchlist show <group>` | 查看分组内标的 |
| `stk watchlist create <group> --symbol S ...` | 创建分组，可带初始标的 |
| `stk watchlist add <group> <symbols...>` | 批量添加标的 |
| `stk watchlist remove <group> <symbols...>` | 批量移除标的 |
| `stk watchlist delete <group>` | 删除分组 |

### `stk watchlist scan <group>`

对 watchlist 分组做每日监控，返回 `MonitorResult`。输出结构与 `stk stock scan <symbols...>` 相同。

| 参数 | 默认 | 说明 |
|------|------|------|
| `--daily10` | `false` | 为强信号且辅助态度不冲突的标的补充最近 10 根压缩完整日线。默认关闭。 |
| `--full-context` | `false` | 输出完整辅助因子，包括 `neutral` 和 `none`。默认精简。 |

注意：

- 当前命令没有 `--sort` 参数。
- 默认只展开 `focus` 重点关注标的。
- 观察标的进入 `ignored.no_signal_count`，不返回逐只明细。

### `stk watchlist scan-live <group>`

对 watchlist 分组做实盘提醒扫描，输出结构与 `stk stock scan-live <symbols...>` 相同。

| 参数 | 默认 | 说明 |
|------|------|------|
| `--timeframe` / `-t` | `15m` | 实盘 K 线周期：`5m` / `15m`。 |
| `--count` / `-c` | `80` | 读取的分钟 K 线根数。 |

### `stk watchlist kline <group>`

获取分组内全部标的的 K 线和技术指标。

| 参数 | 默认 | 说明 |
|------|------|------|
| `--period` / `-p` | `day` | `day` / `week` / `month` |
| `--count` / `-c` | `20` | 每只标的返回的 K 线数量 |

返回 `list[DailyResult]`，结构同 `stk stock kline <symbols...>`。

---

## Tools

- `stk doctor check [--quick]`：数据源健康检查。
- `stk cache clear [--prefix PREFIX]`：清除缓存。
