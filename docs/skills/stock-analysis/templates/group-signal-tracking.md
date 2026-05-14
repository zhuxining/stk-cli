# 分组信号追踪模板

## 适用场景

- 用户要求分析自选、持仓、ETF 分组、watchlist 分组、每日监控。
- DailyReport 默认使用本模板作为分组信号主体。

## 输入数据

- 一个或多个 `stk watchlist scan <group>` 的 `MonitorResult`。

## 分析方法

- 每个分组生成一行统计。
- 只展开 `MonitorResult.focus`；`ignored.no_signal_count` 只进入统计。
- `关键依据` 优先取 `primary_signal.reasons` 最关键 1 条；必要时补一个 `context.factors[].metrics`。
- `priority=high` 且存在 `daily10` 时，补一行近 10 日复核。
- 明日动作从全部分组的 `focus` 合并生成，每类最多 3 只。
- `focus_sell` 写风险退出和失效线，不写做空。
- `watch` 只写观察或等待确认。

## 输出结构

```markdown
## 分组信号

{一句话说明本次扫描是否有重点关注标的、高优先级数量、主要风险方向。}

| 分组 | 扫描 | 重点关注 | 高优先级 | 买入信号 | 退出/风险 | 观察 | 无信号 | 失败 |
|------|------|----------|----------|----------|-----------|------|--------|------|
| {group_name} | {scanned}/{total} | {focus_count} | {high_priority_count} | {entry_signal_count} | {exit_signal_count} | {watch_signal_count} | {no_signal_count} | {failed} |

| 分组 | 代码 | 名称 | 优先级 | 信号 | 置信度 | 新鲜度 | 方向 | 关键依据 | 风控 | 明日动作 |
|------|------|------|--------|------|--------|--------|------|----------|------|----------|
| {group_name} | {symbol} | {name} | {priority} | {level} | {confidence} | {signal_status}/{bars_since_signal}K | {direction} | {1句原因} | {按风控口径} | {固定动作口径} |

### 高优先级复核

| 分组 | 代码 | 近 10 日复核 | 状态 |
|------|------|--------------|------|
| {group_name} | {symbol} | {1句说明延续性/过热/量能} | {延续/过热/缩量/反复} |

## 明日关注

| 动作 | 标的 | 触发条件 |
|------|------|----------|
| 跟踪突破 | {focus_buy 高优先级；没有写“无”} | {放量延续/站稳关键位/风险收益比合适} |
| 等待回踩 | {买入信号但过热或 RR 一般；没有写“无”} | {回踩不破止损线或 Supertrend} |
| 风险退出 | {focus_sell 高优先级；没有写“无”} | {无法收回上方失效线} |
| 仅观察 | {watch 标的；没有写“无”} | {等待主信号确认} |
```
