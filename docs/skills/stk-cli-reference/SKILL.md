---
name: stk-cli-reference
description: >
  使用 `stk` JSON CLI 请求 K 线与技术指标、管理 Longport 分组、查看与同步
  同花顺分组、扫描日线信号，以及生成每日 buy/sell 分组快照。凡是用户要求
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
  "data": {},
  "meta": {"generated_at": "2026-01-01T00:00:00+00:00"}
}
```

失败格式：

```json
{
  "ok": false,
  "error": {"code": "error_code", "message": "错误说明"},
  "meta": {"generated_at": "2026-01-01T00:00:00+00:00"}
}
```

不要依赖空占位字段：无值字段会被省略。先检查顶层 `ok`；批量命令即使整体成功，
也可能在 `data.failures` 中包含单项失败。

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

## 跨平台同步

先配置 `THS_USERNAME` 和 `THS_PASSWORD`：

```bash
stk group sync diff <longport-group> [ths-group]
stk group sync push <longport-group> [ths-group] [--replace]
stk group sync pull <ths-group> [longport-group] [--replace]
```

- `diff` 比较 Longport 源组与同花顺目标组，不写入。
- `push` 固定为 Longport → 同花顺。
- `pull` 固定为同花顺 → Longport。
- 省略目标分组名时，使用源分组名。
- 默认 merge，只添加目标缺少的成员；`--replace` 同时移除目标多出的成员。
- 跨平台同步会转换 Symbol，并过滤同花顺不支持的资产。

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
- `signal.triggers`：适合机器判断的稳定英文触发码。
- `signal.reasons`：包含数值语义的中文说明。
- `indicators`：本次判断使用的核心指标快照。
- `quality`：辅助态度、警告和可选 factors。
- buy 项可有 `risk`，用于表达止损和跟踪线；sell 项不生成做空目标。
- 使用 `--recent-bars` 时出现的 `recent_bars`。

先用 `buy[]` / `sell[]` 判断方向，再用 `triggers` 做稳定分支判断、用 `reasons`
解释原因。`watch` 和 `ignored` 只计入 summary，不展开明细。扫描规则的具体阈值属于
策略实现，不要根据字段名称自行推断或覆写。

## 生成每日信号分组

```bash
stk group route <src> <buy-dst> <sell-dst> [--replace|--append]
```

- 三个参数都是 Longport 分组，并且名称必须互不相同。
- 默认 `--replace`：分别将当前仍满足条件的 buy 和 sell 标的写为两个完整快照。
- 两个目标组都由源分组的当前已确认日线重新计算，不依赖昨日目标组成员。
- 任一标的扫描失败时，整个 route 在写入前中止，两个目标组均保持不变。
- `--append` 只追加本次结果，不移除历史成员；每日快照通常使用默认 replace。

返回的 `data` 包含 `operation`、`mode`、`source` 和 `targets`。`targets` 直接表示
本次写入 buy、sell 分组的 Symbol，不代表交易订单。

## 常用工作流

请求多个标的的确认日线与指标：

```bash
stk data kline 600519 0700.HK AAPL.US --count 60
```

比较并同步两端分组：

```bash
stk group longport list
stk group ths list
stk group sync diff 长桥组 同花顺组
stk group sync push 长桥组 同花顺组
```

扫描源分组并刷新每日信号快照：

```bash
stk scan 长桥组 --recent-bars 10 --include-factors
stk group route 长桥组 买入信号 卖出信号
```

Longport 是行情与主要分组平台；同花顺是分组同步对端。扫描和 route 的分组均为
Longport 分组。
