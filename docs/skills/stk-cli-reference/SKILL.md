---
name: stk-cli-reference
description: "stk-cli 全部命令的参数说明和返回结构参考。覆盖 market、stock、watchlist、sync、doctor、cache 等所有子命令。用到 stk 命令时触发。"
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
| 热门个股 | `stk market hotstock` |
| 个股扫描 | `stk stock scan <symbols...>` |
| 实盘提醒 | `stk stock scan-live <symbols...>` |
| K线/指标 | `stk stock kline <symbols...>` |
| 同业对比 | `stk stock comparison <symbol>` |
| 自选管理 | `stk watchlist list/show/create/add/remove/delete` |
| 自选扫描 | `stk watchlist scan <group>` |
| 自选实盘 | `stk watchlist scan-live <group>` |
| 自选K线 | `stk watchlist kline <group>` |
| 候选入库 | `stk watchlist scoop <name>` |
| 热门入库 | `stk watchlist hot <name>` |
| 信号分流 | `stk watchlist route <src> <entry> <exit> [--replace]` |
| Zigzag 信号 | `stk watchlist zigzag <src> <dst>` |
| 同花顺同步 | `stk sync ths push/diff/list/pull` |
| 健康检查 | `stk doctor check` |
| 清缓存 | `stk cache clear` |
| 查看缓存 | `stk cache stats` |

---

## Market

### `stk market index`

市场概览，指数按 `CN` / `HK` / `US` 分组，含三地温度。

返回 `MarketOverview`：`indices`（`symbol`、`name`、`region`、`last`、`change`、`change_pct`、`volume`）、`temperature`（`score`、`level`、`valuation`、`sentiment`）、`regime`（各区域市场体制 `trending` / `ranging` / `mixed`）。

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

### `stk market hotstock`

东方财富热门个股排行。

```bash
stk market hotstock
stk market hotstock --source up
```

| 参数 | 默认 | 说明 |
|------|------|------|
| `--source` `-s` | `rank` | `rank`（热门排名）/ `up`（热度上升） |

- `rank`：来自 `stock_hot_rank_em`，当前热门个股 Top 100
- `up`：来自 `stock_hot_up_em`，热度上升最快 Top 100（含 `rank_change` 排名变动）

返回 `HotStockResult`：`source`、`total`、`items[]`（`rank`、`symbol`、`name`、`last`、`change`、`change_pct`、`rank_change`）。

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

捕获今日 THS 技术候选股到指定分组。

```bash
stk watchlist scoop 热点股              # 全量入库
stk watchlist scoop 热点股 --scan       # 扫描过滤：只入推荐信号
stk watchlist scoop 热点股 --replace    # 替换模式
```

| 参数 | 默认 | 说明 |
|------|------|------|
| `--scan` | `false` | 启用扫描过滤：只有 `strength == "推荐"` 的标的才入库 |
| `--strict` | `false` | 严格过滤（需 `--scan`）：`bars_since_signal<=2` + `overall_bias=="supportive"` + `risk_reward_ratio>=1.5` |
| `--replace` `-r` | `false` | 替换模式（清空目标再写入） |

- 默认：获取 THS 技术候选（≥3 多方 screen + 无空方冲突 + 非 ST）→ 全量加入目标分组
- `--scan`：获取候选 → batch scan 打分 → 过滤 `strength == "推荐"` → 加入
- `--scan --strict`：在推荐基础上再加三道门槛（最新信号、辅助因子全员确认、风报比≥1.5）

返回 `WorkflowResult`：`action`、`candidates_found`、`source_summary`（仅 `--scan` 时）、`destinations[]`。

### `stk watchlist hot <name>`

从东方财富热门股中选取标的入库。

```bash
stk watchlist hot 热门股                 # 全量入库
stk watchlist hot 热门股 --source up     # 热度上升榜
stk watchlist hot 热门股 --scan          # 扫描过滤：只入推荐信号
stk watchlist hot 热门股 --replace       # 替换模式
```

| 参数 | 默认 | 说明 |
|------|------|------|
| `--source` `-s` | `rank` | `rank`（热门排名）/ `up`（热度上升） |
| `--scan` | `false` | 启用扫描过滤：只有 `strength == "推荐"` 的标的才入库 |
| `--strict` | `false` | 严格过滤（需 `--scan`）：`bars_since_signal<=2` + `overall_bias=="supportive"` + `risk_reward_ratio>=1.5` |
| `--replace` `-r` | `false` | 替换模式（清空目标再写入） |

- 默认：获取 EM 热门股 Top 100 → 全量加入目标分组
- `--scan`：获取热门股 → batch scan 打分 → 过滤 `strength == "推荐"` → 加入
- `--scan --strict`：在推荐基础上再加三道门槛

返回 `WorkflowResult`：`action`（`hot`）、`candidates_found`、`source_summary`、`destinations[]`。

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

## Sync — 跨平台自选股同步

将长桥自选分组同步到同花顺。需要先配置 `.env`：

```env
THS_USERNAME=手机号
THS_PASSWORD=密码
```

### `stk sync ths list`

列出同花顺所有自选分组（含"我的自选"）。

返回 `ThsGroup[]`：`name`、`group_id`、`count`、`readonly`。

### `stk sync ths diff`

对比长桥与同花顺分组差异，不修改。

| 参数 | 默认 | 说明 |
|------|------|------|
| `--from` `-f` | 必填 | 长桥分组名 |
| `--to` `-t` | 同 `--from` | 同花顺分组名 |

返回 `SyncResult`：`action`（`diff`）、`diff`（`from_group`、`to_group`、`to_add[]`、`to_remove[]`、`unchanged`）。

### `stk sync ths push`

将长桥分组推送到同花顺（仅追加，不删除；--replace 全量覆盖）。目标分组不存在时自动创建。

| 参数 | 默认 | 说明 |
|------|------|------|
| `--from` `-f` | 必填 | 长桥分组名 |
| `--to` `-t` | 同 `--from` | 同花顺分组名 |
| `--replace` `-r` | `false` | 全量覆盖（清空目标中不在源端的标的再写入） |

返回 `SyncResult`：`action`（`push`）、`diff`、`added`、`removed`、`errors[]`。

**推送规则**：
- 默认仅追加：长桥全量标的 → 追加到同花顺，不删除目标端已有标的
- `--replace` 模式：先删除目标端不在源端的标的，再写入源端全量
- 自动跳过指数等不支持品种
- 科创板自动映射：`688xxx.SH` → `688xxx.KC`
- 创业板自动映射：`300xxx/301xxx.SZ` → `300xxx/301xxx.CYB`
- 只读分组（同花顺动态板块）不可写入，仅警告

### `stk sync ths pull`

将同花顺分组拉取到长桥（仅追加，不删除；--replace 全量覆盖）。目标长桥分组不存在时自动创建。

| 参数 | 默认 | 说明 |
|------|------|------|
| `--from` `-f` | 必填 | 同花顺分组名（源） |
| `--to` `-t` | 同 `--from` | 长桥分组名 |
| `--replace` `-r` | `false` | 全量覆盖（清空目标再写入） |

返回 `SyncResult`：`action`（`pull`）、`diff`、`added`、`removed`、`errors[]`。

**拉取规则**：
- 默认仅追加：同花顺全量标的 → 追加到长桥（LP Add 模式天然去重），不删除目标端已有标的
- `--replace` 模式：原子 Replace API 全量替换长桥分组
- 科创板自动映射：`688xxx.KC` → `688xxx.SH`
- 创业板自动映射：`300xxx/301xxx.CYB` → `300xxx/301xxx.SZ`

## Tools

| 命令 | 说明 |
|------|------|
| `stk doctor check [--quick]` | 数据源健康检查 |
| `stk cache clear [--prefix PREFIX]` | 清除缓存 |
| `stk cache stats` | 查看缓存统计（内存条目数、磁盘文件数/大小、上限） |

### 全局参数

| 参数 | 说明 |
|------|------|
| `--no-cache` | 跳过所有缓存，强制从 API 获取最新数据。所有子命令通用。 |

```bash
stk --no-cache watchlist scoop 热点股
```
