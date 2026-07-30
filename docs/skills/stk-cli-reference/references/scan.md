# Scan 命令

```bash
stk scan <longport-group> [--daily10] [--full-context]
```

扫描 Longport 分组中的已确认日线状态：

- `focus` 是当前有效的买入信号。
- `risk` 是当前有效的卖出或退出信号。
- `--daily10` 为适合复核的 focus 附加最近 10 根压缩日线。
- `--full-context` 保留默认省略的 `neutral` / `none` 辅助因子。
- 单标的失败进入 `errors`，不会中断普通 scan。

## 输出结构

`MonitorResult` 的主要字段：

| 字段 | 含义 |
|---|---|
| `run_date` | 扫描日期 |
| `universe` | 分组名、总数、成功数和失败数 |
| `summary` | 买入、卖出、观察和风险数量 |
| `focus[]` | 当前买入信号标的 |
| `risk[]` | 当前卖出信号标的 |
| `ignored` | 未形成可行动信号的数量 |
| `errors[]` | 单标的非致命错误 |

每个 `focus` 或 `risk` 项目包含：

- `symbol`、`name`、`last`、`change_pct` 和行情 `source`。
- `routing`：当前买入、卖出和观察资格。
- `decision`：历史事件型信号及发生时间。
- `primary_signal`：EMA、Supertrend、ADX 和原因。
- `context`：辅助因子、整体态度和警告。
- `risk`：ATR、止损、目标位、移动止损和风险收益比。
- `daily10`：仅在请求 `--daily10` 且适合复核时出现。

## 解读顺序

1. 先看 `routing.state`、`entry_eligible` 和 `exit_trigger`，确认当前资格。
2. 买入标的通过 `entry_patterns` 判断属于健康延续、回踩企稳、动量恢复还是趋势启动。
3. 阅读 `routing.reasons`，确认入选、拒绝或风险原因及价格边界。
4. 再用 `decision`、`signal_date` 和 `bars_since_signal` 解释历史触发事件。
5. 用 `context` 判断辅助确认、冲突或风险，最后结合 `risk` 给出的风控边界。

`decision` 变为 `stale` 不代表当前信号失效；scan 和 route 的成员资格始终以 `routing`
为准。`overheated=true` 也不等同于立即卖出，应同时查看 `exit_trigger` 和 `reasons`。

## 关键枚举

- `routing.state`：`eligible`、`watch`、`risk`、`ignored`。
- `entry_patterns`：`healthy_continuation`、`pullback_hold`、
  `momentum_recovery`、`trend_start`。
- `decision.signal`：`趋势买入`、`趋势退出`、`超卖修复`、`观察`。
- `context.overall_bias`：`supportive`、`mixed`、`conflicting`、`risky`。

买入组和卖出组是当前快照，不表示今日首次触发，也不依赖昨日成员。
