# 命令速查

所有命令通过统一 JSON envelope 输出：`{"ok": true, "data": ..., "error": null, "meta": {...}}`。技能报告只读取 `data`。技术指标含义和报告解释口径见 `references/indicator-guide.md`。

---

## Market

### `stk market`

市场概览：主要指数按 `CN` / `HK` / `US` 分组，并返回三地市场温度。

返回 `MarketOverview`：

- `indices`: `{region: [IndexQuote]}`，含 `symbol`、`name`、`region`、`last`、`change`、`change_pct`、`volume`。
- `temperature`: `{region: MarketTemperature}`，含 `score`、`level`、`valuation`、`sentiment`。

### `stk market news`

全局新闻，默认合并 CLS + THS，并按时间倒序。

| 参数 | 默认 | 说明 |
|------|------|------|
| `--source` | `all` | `all` / `cls` / `ths` |
| `--count` | `20` | 新闻条数 |
| `--filter` | `全部` | CLS 专用：`全部` / `重点` |

返回 `list[NewsItem]`：`title`、`summary`、`published_at`、`source`、`url`。

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
```

返回 `MonitorResult`：

- `run_date`: 本次运行日期。
- `universe`: `name`、`total`、`scanned`、`failed`。
- `summary`: `focus_count`、`strong_signal_count`、`entry_signal_count`、`exit_signal_count`、`watch_signal_count`。
- `focus[]`: 重点关注标的列表。
- `ignored`: `no_signal_count`。
- `errors[]`: 单标的非致命错误。

`focus[]` 中每个 `FocusItem` 含：

- 展示字段：`symbol`、`name`、`last`、`change_pct`、`source`。
- `decision`: `action`、`level`、`signal_status`、`signal_date`、`bars_since_signal`。
- `primary_signal`: `ema_cross`、`ema9`、`ema26`、`supertrend`、`supertrend_direction`、`adx`、`reasons`。
- `context`: `overall_bias`、`factors[]`、`warnings[]`；每个 factor 读取 `state` 与 `metrics`。
- `risk`: `atr`、`stop_loss`、`take_profit`、`risk_reward_ratio`、`risk_level`。
- `daily10`: 仅强信号且辅助态度不冲突的标的补充最近 10 根压缩日线，用于复核价格结构和指标变化。

有效信号口径：

- 主策略：`EMA9/EMA26 + Supertrend(ATR10 x2.5)`。
- `level`: `strong_buy` / `buy` / `hold` / `sell` / `strong_sell`。
- `action`: `focus_buy` / `focus_sell` / `watch`。
- `sell` 与 `strong_sell` 表示减仓、退出或风险预警，不表达做空建议。
- `primary_signal.adx < 20` 表示趋势强度偏弱，`>=25` 表示趋势质量较好；ADX 不直接改变 `level`。
- `focus_sell` 中的 `risk.stop_loss` 表示上方失效线，`risk.take_profit` 表示下行风险参考，不代表做空建议。
- `hold` + `watch` 只表示风险、机会或预警观察；不要升级成买入、卖出或加仓建议。
- 陈旧 `hold` 只有明确上下文风险或机会时才会进入 `focus`，报告中应降为仅观察。

辅助因子读取口径：

| factor | 主要 metrics | 分析用途 |
|--------|--------------|----------|
| `momentum` | `rsi14`、`rsi_zone`、`k`、`d`、`j`、`kdj_bias` | 判断动量是否支持主方向，以及是否过热/过冷。 |
| `macd` | `dif`、`dea`、`hist`、`bias` | 判断 MACD 多空状态与主信号是否一致。 |
| `boll` | `upper`、`middle`、`lower`、`position_pct`、`bandwidth_pct` | 判断价格在布林区间中的位置，以及是否处于波动收敛。 |
| `volume_price` | `volume_ratio_5d`、`price_change_pct` | 判断上涨/下跌是否有量能确认。 |
| `ema_trend` | `ema5`、`ema10`、`ema20`、`arrangement` | 判断短周期均线排列是否顺势。 |
| `money_flow` | `mfi14`、`mfi_zone` | 结合主方向判断资金流强弱和过热风险。 |
| `divergence` | `type`、`lookback`、`price_distance_pct`、`hist_delta` | 判断 MACD 顶/底背离，只作为风险或机会提示。 |

`daily10` 压缩日线字段：

- 价格量能：`date`、`open`、`high`、`low`、`close`、`volume`、`turnover`、`change_pct`。
- 主信号：`ema9`、`ema26`、`supertrend`、`supertrend_direction`。
- 辅助指标：`macd`、`macd_signal`、`macd_hist`、`rsi14`、`j`、`boll_position_pct`、`atr10`。
- 使用方式：复核信号出现在第几根 K 线、触发后是否延续、是否放量、是否过热，不用 `daily10` 重新计算 `decision.level`。

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

注意：

- 当前命令没有 `--sort` 参数。
- 默认只展开 `focus` 重点关注标的。
- 无信号标的进入 `ignored.no_signal_count`，不返回逐只明细。

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
