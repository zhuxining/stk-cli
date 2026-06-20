---
name: stk-cli-reference
description: "stk-cli 全部命令的参数说明和返回结构参考。覆盖 market、stock、watchlist、doctor、cache 等所有子命令。用到 stk 命令时触发。"
compatibility:
  requires: [stk-cli]
  data_source: longport
  indicators: [ta-lib]
---

# stk-cli 命令参考

所有命令通过统一 JSON envelope 输出：`{"ok": true, "data": ..., "error": null, "meta": {...}}`。

**参考文件**：
- `references/output-schema.md` — `MonitorResult`、`FocusItem`、`LiveScanResult`、`LiveFocusItem` 的完整字段说明
- `references/signal-strategy.md` — 信号类型、强弱规则、辅助因子解读、指标口径

## 快速索引

| 需求 | 命令 |
|------|------|
| 市场行情 | `stk market index` |
| 技术排名 | `stk market rank` |
| 行业热点 | `stk market hotspot` |
| 选股候选 | `stk market candidates` |
| 个股扫描 | `stk stock scan <symbols...>` |
| 实盘提醒 | `stk stock scan-live <symbols...>` |
| K线/指标 | `stk stock kline <symbols...>` |
| 同业对比 | `stk stock comparison <symbol>` |
| 自选管理 | `stk watchlist list/show/create/add/remove/delete` |
| 自选扫描 | `stk watchlist scan <group>` |
| 自选实盘 | `stk watchlist scan-live <group>` |
| 自选K线 | `stk watchlist kline <group>` |
| 候选入库 | `stk watchlist scoop <name>` |
| 信号分流 | `stk watchlist route <src> <entry> <exit> [--replace]` |
| Zigzag 信号 | `stk watchlist zigzag <src> <dst>` |
| 健康检查 | `stk doctor check` |
| 清缓存 | `stk cache clear` |

---

## Market

### `stk market index`

市场概览，指数按 `CN` / `HK` / `US` 分组，含三地温度。

返回 `MarketOverview`：`indices`（`symbol`、`name`、`region`、`last`、`change`、`change_pct`、`volume`）、`temperature`（`score`、`level`、`valuation`、`sentiment`）。

### `stk market rank`

同花顺技术 screen 排名。

| 参数 | 默认 | 说明 |
|------|------|------|
| `--screen` `-s` | `lxsz` | `lxsz` / `cxfl` / `xstp` / `ljqs` / `cxsl` / `lxxd` / `xxtp` / `ljqd` |
| `--ma` | `20日均线` | `xstp` / `xxtp` 专用 |

返回 `TechRank`：`type`、`label`、`items[]`（`code`、`name`、`metrics`）。

### `stk market hotspot`

行业多空情绪统计。

| 参数 | 默认 | 说明 |
|------|------|------|
| `--ma` | `20日均线` | `xstp` / `xxtp` 专用 |

返回 `TechIndustries`：`industries[]`（`industry`、`bull_count`、`bear_count`、`bull_screens`、`bear_screens`）。

### `stk market candidates`

跨 screen 候选股，返回出现在 ≥3 个多方 screen 且无空方冲突的股票。

| 参数 | 默认 | 说明 |
|------|------|------|
| `--ma` | `20日均线` | `xstp` / `xxtp` 专用 |

返回 `TechCandidates`：`candidates[]`（`code`、`name`、`bull_screens`）、`total`。

> `candidates` 是技术初筛，不代表趋势确认；需要继续 `stk stock scan <symbols...>`。

---

## Stock

### `stk stock scan <symbols...>`

个股每日监控扫描。

```bash
stk stock scan 600519 000001 700.HK
stk stock scan 600519 --daily10
stk stock scan 600519 --full-context
```

| 参数 | 默认 | 说明 |
|------|------|------|
| `--daily10` | `false` | 推荐信号标的补充最近 10 根日线 |
| `--full-context` | `false` | 输出完整辅助因子（含 `neutral`/`none`） |

返回 `MonitorResult`：`run_date`、`universe`、`summary`、`focus[]`、`ignored`、`errors[]`。`focus[]` 含 `decision`、`primary_signal`、`context`、`risk`，详细字段见 `references/output-schema.md`。

### `stk stock scan-live <symbols...>`

实盘提醒扫描。日线过滤 + 5m/15m K 线判触发。

```bash
stk stock scan-live 600519 300750
stk stock scan-live 600519 --timeframe 5m
```

| 参数 | 默认 | 说明 |
|------|------|------|
| `--timeframe` `-t` | `15m` | `5m` / `15m` |
| `--count` `-c` | `80` | 分钟 K 线根数 |

返回 `LiveScanResult`：`mode`、`as_of`、`timeframe`、`summary`、`focus[]`、`ignored`、`errors[]`。`focus[]` 含 `daily_signal`、`live_signal`、`trigger`、`risk_line`、`vwap`、`ema20`、`rsi14`，详细字段见 `references/output-schema.md`。

### `stk stock kline <symbols...>`

K 线 + 全部技术指标。

| 参数 | 默认 | 说明 |
|------|------|------|
| `--type` `-t` | `stock` | `stock` / `index` |
| `--period` `-p` | `day` | `day` / `week` / `month` |
| `--count` `-c` | `20` | K 线数量 |

返回 `DailyResult[]`：`symbol`、`days[]`（OHLCV + `change_pct` + 指标）。指标含 `EMA5/9/10/20/26/60`、`MACD/signal/hist`、`RSI`、`K/D/J`（KDJ）、`upper/middle/lower`（BOLL）、`ATR10/ATR14`、`Supertrend/SupertrendDirection`。

### `stk stock comparison <symbol>`

同业业绩对比：估值、成长性、杜邦分析。

| 参数 | 默认 | 说明 |
|------|------|------|
| `--type` `-t` | `all` | `all` / `growth` / `valuation` / `dupont` |

返回 `FullComparison` 或 `IndustryComparison`。`dupont` 仅 A 股。

---

## Watchlist

### 管理命令

| 命令 | 说明 |
|------|------|
| `stk watchlist list` | 列出所有分组 |
| `stk watchlist show <group>` | 查看分组标的 |
| `stk watchlist create <group> --symbol S ...` | 创建分组 |
| `stk watchlist add <group> <symbols...>` | 批量添加 |
| `stk watchlist remove <group> <symbols...>` | 批量移除 |
| `stk watchlist delete <group>` | 删除分组 |

### `stk watchlist scoop <name>`

捕获今日市场候选股到指定分组。

```bash
stk watchlist scoop 热点股
```

获取 candidates → 扫描获取信号参考 → 全部候选股加入目标分组。

返回 `WorkflowResult`：`action`、`candidates_found`、`source_summary`、`destinations[]`。

### `stk watchlist route <src> <entry-dst> <exit-dst>`

扫描源分组，将买入/卖出信号分流到不同分组。

| 参数 | 默认 | 说明 |
|------|------|------|
| `--replace` `-r` | `false` | 替换模式（先清空再添加） |

```bash
stk watchlist route A股池 观察 预警 --replace
```

信号分类：entry（趋势买入/超卖修复）→ `entry-dst`；exit（趋势退出）→ `exit-dst`。

返回 `WorkflowResult`：`action`、`source_summary`、`destinations[]`。

### `stk watchlist zigzag <src> <dst>`

识别分组内过去 5 根 K 线出现 zigzag 高点或低点的标的。

```bash
stk watchlist zigzag ETF股池 zigzag-picks
```

算法参数：Depth=10（前后各 5 根确认 pivot），Deviation=5%（最小反转幅度）。检测到 zigzag 低点或高点且在最近 5 根 K 线内的标的加入目标分组。

返回 `WorkflowResult`：`action`、`candidates_found`、`destinations[]`。

### `stk watchlist scan <group>`

分组每日监控。

| 参数 | 默认 | 说明 |
|------|------|------|
| `--daily10` | `false` | 补充最近 10 根日线 |
| `--full-context` | `false` | 输出完整辅助因子 |

返回 `MonitorResult`，结构同 `stk stock scan`。

### `stk watchlist scan-live <group>`

分组实盘提醒。

| 参数 | 默认 | 说明 |
|------|------|------|
| `--timeframe` `-t` | `15m` | `5m` / `15m` |
| `--count` `-c` | `80` | 分钟 K 线根数 |

返回 `LiveScanResult`，结构同 `stk stock scan-live`。

### `stk watchlist kline <group>`

分组全部标的的 K 线 + 指标。

| 参数 | 默认 | 说明 |
|------|------|------|
| `--period` `-p` | `day` | `day` / `week` / `month` |
| `--count` `-c` | `20` | 每只标的 K 线数量 |

返回 `DailyResult[]`，结构同 `stk stock kline`。

---

## Tools

| 命令 | 说明 |
|------|------|
| `stk doctor check [--quick]` | 数据源健康检查 |
| `stk cache clear [--prefix PREFIX]` | 清除缓存 |
