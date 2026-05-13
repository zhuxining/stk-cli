---
name: stock-analysis
description: >
  stk-cli 每日股市监控技能。当用户询问市场行情、技术热点、自选分组、个股信号、持仓检查，
  或口语化表达如"今天有没有信号"、"帮我看看XX组"、"XX股票怎么样"时，必须使用此技能。
  输出中文报告，聚焦 focus 标的 decision、primary_signal、context、risk。
---

# 股市分析技能

使用 `stk` CLI 生成面向每日监控的中文股票分析报告。核心目标是回答：今天哪些标的需要关注，为什么，以及风险位在哪里。

## 加载资料

- 需要确认命令参数或字段契约时，读取 `references/commands.md`。
- 需要写最终报告时，读取 `references/report-templates.md`，按对应模板输出。

## 核心口径

- 主信号：`EMA9/EMA26 + Supertrend(ATR10 x2.5)`，日线收盘确认。
- 有效窗口：最近 3 根 K 线内出现 EMA 交叉或 Supertrend 翻转，且方向一致。
- 批量扫描：只展开 `MonitorResult.focus`；无信号标的只统计 `ignored.no_signal_count`。
- 单标的解读：以 `decision` 下结论，以 `primary_signal` 给依据，以 `context` 和 `risk` 做补充。
- `sell` / `strong_sell` 只表示减仓、退出或风险预警，不表达做空建议。

- 信号级别：`strong_buy`(0-1K/多头强共振) → `buy`(2-3K) → `hold`(无效/过期/冲突) → `sell`(2-3K/空头) → `strong_sell`(0-1K/空头强)

## 典型触发问法

| 用户问法 | 触发模式 |
|----------|----------|
| "今天市场怎么样"、"有什么重要新闻" | 市场总览 |
| "有没有什么热点"、"帮我找几个技术形态好的" | 技术热点 |
| "茅台有没有信号"、"600519 怎么看" | 个股信号分析 |
| "我的持仓/自选怎么样"、"检查一下ETF分组" | 分组每日监控 |
| "日报"（同时要求市场+选股） | 市场总览 → 技术热点 |

## 模式选择

| 用户意图 | 模式 | 主要命令 |
|----------|------|----------|
| 日报、市场、盘面、新闻 | 市场总览 | `stk market` + `stk market news --count 20` |
| 热点、选股、技术形态、入池 | 技术热点 | `stk stock hotspot` + `stk stock candidates` + `stk stock scan` |
| 分析某只股票、有没有信号 | 个股信号分析 | `stk stock scan <symbol>` + 可选 `kline` / `fundamental` |
| 自选、分组、持仓、每日监控 | 分组每日监控 | `stk watchlist scan <group>` |

用户同时要求“日报 + 选股”时，先做市场总览，再做技术热点或分组每日监控。

## 模式细则

### 市场总览

并行运行：

- `stk market`
- `stk market news --count 20`

输出：一句话市场状态、三地市场温度、3 条重要消息、强势方向、风险方向。

### 技术热点

先并行运行：

- `stk stock hotspot`
- `stk stock candidates`

再对候选股运行 `stk stock scan <code1> <code2> ...`。只把 `MonitorResult.focus` 作为重点候选；若 `focus` 为空，明确说明“候选池暂无趋势确认信号”。

### 个股信号分析

优先运行 `stk stock scan <symbol>`。如果用户需要解释信号来源或基本面，再并行补充：

- `stk stock kline <symbol>`
- `stk stock fundamental <symbol>`

结论必须先给 `decision.level`、`decision.action`、`confidence` 和是否进入 `focus`。未进入 `focus` 时，不要强行给买卖建议。

### 分组每日监控

运行 `stk watchlist scan <group>`，只展开 `focus`。

分组名解析：直接从文本提取分组名并扫描（”ETF分组”→”ETF”，”分析半导体组”→”半导体”); 扫描失败时 `stk watchlist list` 查找相近分组并重试；用户未给分组名时才列出供选择。

## 报告规则

- 使用中文，结论先行。
- 对比数据用表格，解释用短要点。
- 关键数字包括：`level`、`confidence`、`signal_status`、`bars_since_signal`、`stop_loss`、`take_profit`、`risk_reward_ratio`。
- 方向性观点必须引用字段或数值，避免只写“走势较好/较差”。
- 报告默认保存到 `~/.stk/reports/`，并在末尾注明保存路径。

## 错误处理

- 单只股票失败：记录到报告中并继续处理其他标的。
- 大量失败：运行 `stk doctor check` 排查数据源。
- 缓存异常：运行 `stk cache clear` 后重试。
