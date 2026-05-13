# 命令速查

所有命令通过统一 JSON envelope 输出：`{"ok": true, "data": ..., "error": null, "meta": {...}}`。技能报告只读取 `data`。

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
- `summary`: `focus_count`、`high_priority_count`、`entry_signal_count`、`exit_signal_count`、`watch_signal_count`。
- `focus[]`: 重点关注标的列表。
- `ignored`: `no_signal_count`。
- `errors[]`: 单标的非致命错误。

`focus[]` 中每个 `FocusItem` 含：

- 展示字段：`symbol`、`name`、`priority`、`last`、`change_pct`、`source`。
- `decision`: `action`、`level`、`direction`、`confidence`、`signal_status`、`signal_date`、`bars_since_signal`、`summary`。
- `primary_signal`: `strategy`、`ema_cross`、`ema9`、`ema26`、`supertrend`、`supertrend_direction`、`adx`、`reasons`。
- `context`: `overall_bias`、`factors[]`、`warnings[]`。
- `risk`: `atr`、`stop_loss`、`take_profit`、`risk_reward_ratio`、`risk_level`。

有效信号口径：

- 主策略：`EMA9/EMA26 + Supertrend(ATR10 x2.5)`。
- `level`: `strong_buy` / `buy` / `hold` / `sell` / `strong_sell`。
- `action`: `focus_buy` / `focus_sell` / `watch`。
- `sell` 与 `strong_sell` 表示减仓、退出或风险预警，不表达做空建议。

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
- ATR：`ATR14`
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
