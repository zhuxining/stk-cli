---
name: stk-cli-reference
description: >
  使用 `stk` JSON CLI 请求 K 线与技术指标、管理 Longport 分组、查看与同步
  同花顺分组、扫描日线信号、执行 ETF 双池轮动，以及生成每日信号分组快照。凡是用户要求
  调用 stk、查询股票指标、维护或同步股票分组、扫描买卖信号、执行 group route，
  或解读 stk JSON 输出时，都应使用本 Skill。
---

# stk-cli 命令参考

使用本 Skill 选择并调用 `stk` 命令，然后根据结构化输出继续处理。不要将它当作
交易执行工具：它只提供数据、信号和分组管理，不生成订单或仓位建议。

## 输出约定

所有命令只向 stdout 输出一个 JSON envelope，日志写入 stderr。成功格式：

```json
{
  "ok": true,
  "status": "success",
  "data": {},
  "meta": {"generated_at": "2026-01-01T00:00:00+00:00"}
}
```

失败格式：

```json
{
  "ok": false,
  "status": "failed",
  "error": {"code": "error_code", "message": "错误说明"},
  "meta": {"generated_at": "2026-01-01T00:00:00+00:00"}
}
```

不要依赖空占位字段：无值字段会被省略。顶层状态语义：

- `ok: true, status: success`：操作完整成功。
- `ok: true, status: partial`：操作已经执行，但 `data.failures[]` 中有单项失败。
- `ok: false, status: failed`：配置、认证、源对象或请求级错误导致操作无法执行。

批量操作遇到个别失败时继续处理其他项。调用方应先检查 `ok`，再检查 `status`；
`partial` 不应按整体失败重试，只处理 `data.failures[]` 中的项目。

## ETF rotation

分析多个独立 ETF 来源池，不修改任何分组：

```bash
stk rotate 主题ETF 资产ETF
```

分析完成后完整替换三个共享阶段快照：

```bash
stk group rotate --source 主题ETF --source 资产ETF \
  --emerging ETF启动 --strong ETF强势 --fading ETF退潮
```

输出使用 `rotation_v2`，包含
`sources/summary/emerging/strong/fading/failures`。来源池和目标组必须
全部不同，来源池间不得重复代码；目标组只支持 replace。

阶段由绝对价格结构决定，池内百分位只用于同阶段排序，不要跨池比较 `rank_score`。
每个成功标的属于一个公开阶段或内部 inactive：

- `emerging`：反弹改善或最近两根确认日线内 Supertrend 翻多。
- `strong`：Supertrend 多头、站上上行 EMA20 且 20 日收益为正。
- `fading`：最近十日曾确认启动或强势，当前出现结构或动量退潮。
- `inactive`：只计入 summary，不展开明细，也不写入目标组。

每项包含 `previous_state`、`stage_changed`、`rank_score`、`action` 和 `trend`；启动项
另有 `setup=rebound|confirmed`，退潮项另有 `fade_severity`。action 的使用方式：

- `rotate_in`：confirmed 启动且通过 RSI 与 ATR 介入过滤。
- `watch`：反弹启动，或 confirmed 启动因过热、偏离过大而不宜介入。
- `hold`：当前处于 strong。
- `reduce`：轻度 fading。
- `exit`：确认或严重 fading。

阶段不代表交易订单。优先使用 `action` 判断当前技术状态，再查看 `setup`、
`fade_severity`、`rank_score`、`factors`、`indicators` 和 `warnings` 解释原因。
`low_liquidity` 表示 20 日平均成交额处于对应池后 20%，只作提示，不会剔除标的或
改变 action。

每只 ETF 请求 90 根日线，至少需要 70 根确认日线；每个来源池至少需要 5 只成功标的。
任一池整体失败时三个目标组均不刷新。个别失败时其余标的继续，响应为 `partial`。
完整算法见 `docs/design/etf-rotation.md`。

## K 线与指标

```bash
stk data kline <symbols...> [--period day|week|month] [--count N]
```

Symbol 可使用简写，例如 `600519`；输出中的 Symbol 会被标准化。`data` 包含：

- `period`：实际请求周期。
- `requested`：请求标的数量。
- `series[]`：成功标的，每项包含 `symbol` 和 `bars`。
- `failures[]`：失败标的，每项包含 `symbol`、`code` 和 `message`。

`bars` 按时间从旧到新排列，每根 bar 使用 snake_case 字段，包含 OHLCV 与可用的
EMA、MACD、RSI、KDJ、WR、BOLL、ATR、Supertrend 等指标；尚未形成的指标字段会被
省略。

## Longport 分组

```bash
stk group longport list
stk group longport show <group>
stk group longport create <group> [--symbol SYMBOL ...]
stk group longport add <group> <symbols...>
stk group longport remove <group> <symbols...>
stk group longport delete <group>
```

`list` 返回分组摘要，`show` 返回单个分组及成员。修改命令返回明确的 `operation`、
`platform`、`group`，以及适用时的 `requested_symbols`。

## 同花顺分组

```bash
stk group ths list
```

该命令用于查看同花顺分组；同花顺分组写入由 `group sync` 完成。

## 雪球自选

先从已登录浏览器的 Cookie 中复制 `u`、`xq_a_token`、`xq_id_token`，分别写入
`XUEQIU_UID`、`XUEQIU_A_TOKEN`、`XUEQIU_ID_TOKEN`。支持默认“我的自选”和股票
自定义分组，系统动态分组只读：

```bash
stk group xueqiu list
stk group xueqiu show [group]
stk group xueqiu create <group>
stk group xueqiu add <group> <symbols...>
stk group xueqiu remove <group> <symbols...>
stk group xueqiu delete <group>
```

## 跨平台同步

先配置 `THS_USERNAME` 和 `THS_PASSWORD`：

```bash
stk group sync diff <longport-group> [ths-group]
stk group sync push <longport-group> [ths-group] [--replace]
stk group sync pull <ths-group> [longport-group] [--replace]
stk group sync diff <longport-group> [xueqiu-group] --platform xueqiu
stk group sync push <longport-group> [xueqiu-group] --platform xueqiu [--replace]
stk group sync pull [xueqiu-group] [longport-group] --platform xueqiu [--replace]
```

- `diff` 比较 Longport 源组与同花顺目标组，不写入。
- `push` 固定为 Longport → 同花顺。
- `pull` 固定为同花顺 → Longport。
- 省略目标分组名时，使用源分组名。
- 默认 merge，只添加目标缺少的成员；`--replace` 同时移除目标多出的成员。
- 跨平台同步会转换 Symbol，并过滤同花顺不支持的资产。
- `--platform` 默认为 `ths`；选择 `xueqiu` 时省略远端组名即使用“我的自选”，也可
  指定自定义分组名称。
- 雪球 replace 会先新增；任一新增失败时不执行删除，避免产生破坏性半同步。

同步结果包含 `operation`、`mode`、`source`、`target`、`changes`、`failures` 和
`warnings`；写操作还包含 `applied`。`changes` 中的 Symbol 使用目标平台格式。
在继续自动化流程前检查 `failures` 和 `warnings`。

## 扫描分组信号

```bash
stk scan <longport-group> [--recent-bars N] [--include-factors]
```

- `--recent-bars N` 为每个买入或卖出项附加 1–30 根最近的已确认日线。
- `--include-factors` 展开辅助质量 factors；默认只返回精简质量结论。
- 单个标的失败进入 `failures`，不阻断其他标的扫描。

`data` 包含：

```text
group
summary: total / analyzed / failed / buy / sell / watch / ignored
buy[]
sell[]
failures[]
```

`buy[]` 和 `sell[]` 中的项目包含：

- `symbol`、`name` 和最新确认日线日期 `as_of`。
- 可选实时展示数据 `quote`。
- `signal.confirmation`：当前信号窗口的 `confirmed_at` 和 `age_bars`。buy 使用两根
  确认日线窗口，从 Supertrend 翻多事件开始；sell 同样使用两根确认日线窗口，从最近一次
  有效空头事件开始。
- `signal.triggers[]`：实际触发信号的结构化事件。buy 固定包含一个 Supertrend 翻多
  事件；sell 包含一个或两个当前有效的空头事件。每项包含稳定英文 `code`、
  `occurred_at` 和距今确认日线数 `age_bars`。
- sell 的 EMA 死叉事件仅在当前收盘价同时低于 EMA26 时有效；Supertrend 翻空路径
  不要求这一价格过滤。
- `signal.reasons`：包含数值语义的中文说明。
- `indicators`：本次判断使用的核心指标快照。
- `quality`：辅助态度、警告和可选 factors。
- buy 项可有 `risk`，用于表达止损和跟踪线；sell 项不生成做空目标。
- 使用 `--recent-bars` 时出现的 `recent_bars`。

先用 `buy[]` / `sell[]` 判断方向，再用 `signal.confirmation.age_bars` 检查相应的
两根确认日线有效期，用 `triggers[].code` 和 `occurred_at` 解读触发事件。
`reasons` 用于解释原因。
`watch` 和 `ignored` 只计入 summary，不展开明细。扫描规则的具体阈值属于策略实现，
不要根据字段名称自行推断或覆写。

## 生成每日信号分组

```bash
stk group route <src> <buy-dst> <sell-dst> [--replace|--append]
```

- 三个参数都是 Longport 分组，并且名称必须互不相同。
- 默认 `--replace`：分别将当前仍满足条件的 buy 和 sell 标的写为两个完整快照。
- 两个目标组都由源分组的当前已确认日线重新计算，不依赖昨日目标组成员。
- 个别标的扫描失败时跳过该标的，其余结果继续写入，并在成功响应中返回失败详情。
- `--append` 只追加本次结果，不移除历史成员；每日快照通常使用默认 replace。

返回的 `data` 包含 `operation`、`mode`、`source` 和 `targets`。`targets` 直接表示
本次写入 buy、sell 分组的 Symbol，不代表交易订单。`source.failed` 给出失败数量，
`failures[]` 给出每个失败标的的 `symbol`、`code` 和 `message`。

## 常用工作流

请求多个标的的确认日线与指标：

```bash
stk data kline 600519 0700.HK AAPL.US --count 60
```

比较并同步两端分组：

```bash
stk group longport list
stk group ths list
stk group xueqiu list
stk group xueqiu show
stk group sync diff 长桥组 同花顺组
stk group sync push 长桥组 同花顺组
stk group sync diff 长桥组 --platform xueqiu
```

扫描源分组并刷新每日信号快照：

```bash
stk scan 长桥组 --recent-bars 10 --include-factors
stk group route 长桥组 买入信号 卖出信号
```

Longport 是行情与主要分组平台；同花顺是分组同步对端。扫描和 route 的分组均为
Longport 分组。
