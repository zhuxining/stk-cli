# 报告模板

报告默认服务于每日监控：先给结论，再给少量关键证据。除非用户明确要求复盘完整股票池，否则不要展开无信号标的。

通用规则：

- 结论先行：第一屏必须回答“今天是否需要关注”。
- 只写关键字段：`decision`、`primary_signal`、`context`、`risk`。
- 无信号不硬凑建议：`focus` 为空时直接说明没有明确趋势触发。
- 数字要可执行：信号日期、距今 K 线数、置信度、止损、止盈、盈亏比优先。
- 观点必须有依据：每个方向性判断至少引用一个字段或指标。

---

## 模板 1: 市场总览

```markdown
# 市场总览 - {YYYY-MM-DD}

## 结论

{一句话说明今天市场状态：偏强 / 偏弱 / 分化 / 观望。}

## 市场温度

| 市场 | 核心表现 | 温度 | 判断 |
|------|----------|------|------|
| A股 | {主要指数涨跌} | {temperature_value}/{level} | {判断} |
| 港股 | {主要指数涨跌} | {temperature_value}/{level} | {判断} |
| 美股 | {主要指数涨跌} | {temperature_value}/{level} | {判断} |

## 重要消息

| 消息 | 影响方向 | 关注方向 |
|------|----------|----------|
| {标题} | {利好/利空/中性 + 理由} | {板块/概念/个股} |
| {标题} | {利好/利空/中性 + 理由} | {板块/概念/个股} |
| {标题} | {利好/利空/中性 + 理由} | {板块/概念/个股} |

## 今日观察

- **强势方向**: {从指数和新闻综合提炼；没有则写“暂无明确主线”}
- **风险方向**: {需要回避或降低仓位关注的方向}
- **后续动作**: {是否需要继续做技术热点或自选分组扫描}
```

---

## 模板 2: 技术热点

```markdown
# 技术热点 - {YYYY-MM-DD}

## 结论

{一句话说明技术 screen 是偏多、偏空还是分化。若 scan 后 focus 为空，明确写“候选池暂无趋势确认信号”。}

## 行业情绪

| 行业 | 多方 screen | 空方 screen | 判断 |
|------|-------------|-------------|------|
| {行业} | {bull_count} | {bear_count} | {强势/分化/风险} |
| {行业} | {bull_count} | {bear_count} | {强势/分化/风险} |
| {行业} | {bull_count} | {bear_count} | {强势/分化/风险} |

## 重点候选

仅列 `MonitorResult.focus` 中的标的。

| 代码 | 名称 | 优先级 | 信号 | 置信度 | 新鲜度 | 关键依据 | 风险位 |
|------|------|--------|------|--------|--------|----------|--------|
| {symbol} | {name} | {priority} | {level} | {confidence} | {signal_status}/{bars_since_signal}K | {EMA/ST原因} | {stop_loss} |

## 暂不关注

- 扫描数量: {universe.scanned}/{universe.total}
- 无明确信号: {ignored.no_signal_count}
- 失败数量: {universe.failed}

## 后续动作

- **重点跟踪**: {high priority 或 strong 信号标的}
- **加入自选**: {如用户要求，列出建议加入的分组和代码}
- **风险提示**: {空头信号、context warnings 或行业空方集中}
```

---

## 模板 3: 个股信号分析

```markdown
# 个股信号分析 - {symbol} {name} - {YYYY-MM-DD}

## 结论

**{level} / {action} / 置信度 {confidence}**

{1-2 句说明今天是否需要关注，以及核心原因。若未进入 focus，说明“当前没有明确趋势触发”。}

## 主信号

| 项目 | 当前值 |
|------|--------|
| 方向 | {direction} |
| 状态 | {signal_status} |
| 信号日期 | {signal_date} |
| 距今 | {bars_since_signal} 根 K 线 |
| EMA9 / EMA26 | {ema9} / {ema26} |
| Supertrend | {supertrend_direction} / {supertrend} |
| ADX | {adx} |

**触发依据**

- {primary_signal.reasons[0]}
- {primary_signal.reasons[1]}
- {primary_signal.reasons[2]}

## 辅助判断

- **整体偏向**: {context.overall_bias}
- **确认因素**: {supportive 或 confirming 因子，最多 3 条}
- **冲突/风险**: {warnings 或 conflicting/risk 因子，最多 3 条；没有则写“暂无主要冲突”}

## 风控

| 项目 | 数值 |
|------|------|
| 最新价 | {last} |
| 止损 | {stop_loss} |
| 止盈 | {take_profit} |
| 盈亏比 | {risk_reward_ratio} |
| 风险等级 | {risk_level} |

## 基本面补充

{只写与结论相关的成长、估值或同业位置。没有有效数据时省略本节。}
```

---

## 模板 4: 分组每日监控

```markdown
# 分组每日监控 - {group_name} - {YYYY-MM-DD}

## 结论

{一句话说明本组今天是否有重点关注标的。}

- 扫描: {universe.scanned}/{universe.total}
- 重点关注: **{summary.focus_count}**
- 高优先级: **{summary.high_priority_count}**
- 买入信号: {summary.entry_signal_count}
- 退出/风险信号: {summary.exit_signal_count}
- 无明确信号: {ignored.no_signal_count}
- 失败: {universe.failed}

## 重点关注

只列 `focus`，按系统返回顺序展示。

| 代码 | 名称 | 优先级 | 信号 | 置信度 | 新鲜度 | 方向 | 风控 | 说明 |
|------|------|--------|------|--------|--------|------|------|------|
| {symbol} | {name} | {priority} | {level} | {confidence} | {signal_status}/{bars_since_signal}K | {direction} | 止损 {stop_loss} / 风险 {risk_level} | {summary 或关键原因} |

## 高优先级提醒

- **买入关注**: {strong_buy 或 priority=high 的 focus_buy 标的；没有则写“无”}
- **风险退出**: {strong_sell 或 priority=high 的 focus_sell 标的；没有则写“无”}

## 辅助风险

- {来自 focus.context.warnings 的共性风险，例如量价背离、布林收窄、动能冲突}
- {如果没有共性风险，写“暂无集中风险提示”}

## 后续动作

- 今日优先看: {最多 3 只，说明为什么}
- 暂不展开: {ignored.no_signal_count} 只当前无明确信号，不代表基本面变差
- 需要补查基本面: {如高优先级标的需要估值或同业验证，列代码；没有则写“无”}
```
