---
name: stk-stock-analysis
description: stk-cli 每日股市监控技能。**当用户询问任何与股票市场相关的问题时，必须立即使用此技能。**包括但不限于：市场行情、技术热点、自选分组、个股信号、持仓检查、DailyReport、交易日报、每日复盘、保存到 Obsidian。即使提问是口语化的，如 "今天有没有信号"、"帮我看看XX组"、"XX股票怎么样"、"今天市场如何"、"有什么热点"、"分析一下茅台"，也必须触发此技能。关键词包括：scan JSON、MonitorResult、focus、daily10、技术指标、EMA、Supertrend、MACD、KDJ、RSI、布林带、资金流入、趋势信号、止损止盈。输出中文技术分析报告，用 decision 下结论，用 primary_signal 找触发，用 context.metrics 校验质量，用 risk 给风控。
compatibility:
  requires: [stk-cli]
  optional: [obsidian-knowledge]
  data_source: longport
  indicators: [ta-lib]
---

# 股市分析技能

使用 `stk` CLI 生成面向每日监控的中文股票分析报告。核心目标是回答：今天哪些标的需要关注，为什么，以及风险位在哪里。

## 加载资料

- 需要确认命令参数或字段契约时，读取 `references/commands.md`。
- 需要解释技术指标含义或辅助因子 metrics 时，读取 `references/indicator-guide.md`；它只解释指标，不定义交易信号。
- 需要写最终报告时，先读取 `templates/README.md`，再按分析场景读取 `templates/` 下的模板。
- 需要执行 DailyReport 时，读取 `workflow/daily-report.md`，按工作流生成并写入 Obsidian。

## 核心口径

- 主信号：`EMA9/EMA26 + Supertrend(ATR10 x2.5)`，并补充保守确认后的反转、修复形态，日线收盘确认。
- 有效窗口：最近 3 根 K 线内出现 EMA 交叉或 Supertrend 翻转，且方向一致。
- 批量扫描：只展开 `MonitorResult.focus`；`观察` 和无信号标的只统计 `ignored.no_signal_count`。
- 单标的解读：以 `decision` 下结论，以 `primary_signal` 给依据，以 `context` 和 `risk` 做补充。
- `decision.intent` 表示处理意图，取值为 `买入关注`、`风险退出`、`观察`。
- `decision.strength` 表示强弱，取值为 `强信号`、`普通信号`、`无信号`。
- `decision.pattern` 表示信号来源，取值为 `趋势共振`、`反转确认`、`趋势修复`。
- 辅助因子读取 `context.factors[].state` 与 `context.factors[].metrics`；默认扫描结果已省略 `neutral` / `none` 因子，完整复盘时给命令加 `--full-context`。
- `daily10` 默认不返回；只有命令显式传入 `--daily10` 后，强信号标的才可能包含最近 10 根压缩日线。
- `风险退出` 只表示减仓、退出或风险预警，不表达做空建议。
- `观察` 默认不会进入批量扫描 `focus`；单标的解读时也只作为风险、机会或波动提示，不写成买入、卖出或加仓建议。
- `风险退出` 的 `risk.stop_loss` 是上方失效线，`risk.take_profit` 是下行风险参考。

- 信号强弱：`强信号`(0-1K 或反转/修复确认) → `普通信号`(2-3K) → `无信号`(无效/过期/冲突)。

## 分析步骤

按固定证据链分析，避免只复述字段。

1. **先看入选理由**：`focus` 代表需要关注；非 `focus` 不展开，不把 `ignored.no_signal_count` 解释成负面基本面。
2. **先下结论**：用 `decision.intent`、`strength`、`pattern`、`signal_status` 判断今天的处理意图、强度与信号来源。
3. **验证主信号**：用 `primary_signal.ema_cross`、`ema9/ema26`、`supertrend_direction`、`reasons` 说明触发来源；`bars_since_signal` 越小，信号越新。
4. **校验辅助因子**：统计 `context.factors` 中 `confirming`、`conflicting`、`risk`、`opportunity` 的数量和名称，再读对应 `metrics` 给出原因。
5. **复核强信号标的**：有 `daily10` 时，检查最近 10 日价格是否贴近信号日、量能是否配合、RSI/J 是否过热、BOLL 位置是否过高、ATR 风险是否放大。
6. **给执行边界**：最后用 `risk.stop_loss`、`take_profit`、`risk_reward_ratio`、`risk_level` 判断是否值得跟踪；多头写止损/止盈，空头写上方失效线/下行参考，盈亏比差时结论降为观察。

## 指标解释口径

- 详细指标含义读取 `references/indicator-guide.md`；本节只保留报告口径边界。
- 指标用于解释趋势、动量、波动、量能和风险状态，不单独生成交易结论。
- `context.overall_bias=supportive`：辅助因子整体支持主方向，可以强化结论。
- `mixed`：信号可关注，但需要等待价格或量能继续确认。
- `risky`：方向未必错，但有过热、缩量、布林收窄、资金流转弱等风险，避免追高。
- `conflicting`：辅助因子明显冲突，即使主信号成立，也要降低措辞强度。
- `decision.intent=观察` 或 `decision.strength=无信号`：批量扫描中不展开；单标的解读时只解释风险或机会原因，若 `bars_since_signal` 很大或为空，明确写成陈旧趋势/左侧观察。
- `RSI` 只作为动量温度，不单独产生买卖建议；多头中 `50-70` 更健康，`>70` 偏追高风险，`<45` 动能不足。
- `ADX` 只作为趋势强度提示；`<20` 说明趋势偏弱、信号更容易反复，`>=25` 说明趋势质量更好。
- `KDJ J` 用于观察短期过热或钝化；极高的 J 值是追涨风险，不直接否定趋势。
- `MFI` 要结合方向解读：多头中强 MFI 是确认，空头中弱 MFI 是确认；极端超买/超卖优先作为风险或机会提示。
- `divergence` 是 MACD histogram 背离。顶背离是趋势减速风险，底背离是左侧机会提示；两者都不能替代主信号。
- `boll.position_pct` 接近上轨说明强势但追高风险增加，接近下轨说明弱势或修复机会；`bandwidth_pct` 很低时优先写波动收敛、等待放量选择方向。
- `volume_price.volume_ratio_5d` 用来确认突破质量；放量同向优于缩量同向，放量逆向要列为风险。

## 典型触发问法

| 用户问法 | 触发模式 |
|----------|----------|
| "今天市场怎么样"、"有什么重要新闻" | 市场总览 |
| "有没有什么热点"、"帮我找几个技术形态好的" | 技术热点 |
| "茅台有没有信号"、"600519 怎么看" | 个股信号分析 |
| "我的持仓/自选怎么样"、"检查一下ETF分组" | 分组每日监控 |
| "日报"、"交易日报"、"DailyReport"、"保存到 Obsidian" | DailyReport |
| "日报 + 选股/热点/候选" | DailyReport → 技术热点 |

## 模式选择

| 用户意图 | 模式 | 主要命令 |
|----------|------|----------|
| 日报、市场、盘面、新闻 | 市场总览 | `stk market` + `stk market news --count 20` |
| DailyReport、交易日报、每日复盘、保存到 Obsidian | DailyReport | `stk market` + `stk market news --count 20` + `stk watchlist scan <group>` |
| 热点、选股、技术形态、入池 | 技术热点 | `stk stock hotspot` + `stk stock candidates` + `stk stock scan` |
| 分析某只股票、有没有信号 | 个股信号分析 | `stk stock scan <symbol>` + 可选 `kline` / `fundamental` |
| 自选、分组、持仓、每日监控 | 分组每日监控 | `stk watchlist scan <group>` |

用户要求 DailyReport 时，默认只做“市场总览 + 分组每日监控”；只有明确提到“选股、热点、候选”时才追加技术热点。

## 模式细则

### 市场总览

使用 `templates/market-hotspot-analysis.md`。

并行运行：

- `stk market`
- `stk market news --count 20`

输出：一句话市场状态、三地市场温度、3 条重要消息、强势方向、风险方向。

### DailyReport

读取 `workflow/daily-report.md`，按工作流执行：取数、分析、调用场景模板、组装 Obsidian Markdown、写入 `14_Trading/DailyReport/{YYYY-MM-DD}.md`。

规则：

- 未指定分组时，先从用户上下文提取分组名；仍无法判断时，运行 `stk watchlist list` 后让用户选择。
- 多个分组的扫描结果合并进同一篇 DailyReport，并保留分组名列。
- 同一交易日文件按 `YYYY-MM-DD.md` 更新，不创建重复副本。
- 默认不加入技术热点；用户明确要求“热点/选股/候选”时，再追加技术热点小节。
- DailyReport 只展开 `focus`，无信号标的只写统计。

### 技术热点

使用 `templates/market-hotspot-analysis.md`。

先并行运行：

- `stk stock hotspot`
- `stk stock candidates`

再对候选股运行 `stk stock scan <code1> <code2> ...`。只把 `MonitorResult.focus` 作为重点候选；若 `focus` 为空，明确说明“候选池暂无趋势确认信号”。

### 个股信号分析

优先运行 `stk stock scan <symbol>`。如果用户需要解释信号来源或基本面，再并行补充：

- `stk stock kline <symbol>`
- `stk stock fundamental <symbol>`

结论必须先给 `decision.intent`、`decision.strength`、`decision.pattern`、`signal_status` 和是否进入 `focus`。未进入 `focus` 时，不要强行给买卖建议。
如果用户一次分析多只股票，使用 `templates/multi-stock-deep-comparison.md`，表格对比信号质量、辅助态度和风控，不逐只展开长段落。
如果只分析单只股票，按“分析步骤”输出短表：结论、主信号、辅助确认、风险冲突和风控边界。

### 分组每日监控

使用 `templates/group-signal-tracking.md`。

运行 `stk watchlist scan <group>`，只展开 `focus`。

分组名解析：直接从文本提取分组名并扫描（”ETF分组”→”ETF”，”分析半导体组”→”半导体”); 扫描失败时 `stk watchlist list` 查找相近分组并重试；用户未给分组名时才列出供选择。

## 报告规则

- 使用中文，结论先行。
- 报告默认精炼：先给 1-2 句结论，再用表格呈现结果。
- 多只股票分析必须用表格，不逐只写长段落；只有用户明确要求详细拆解时才展开单只标的。
- 关键数字和判断字段包括：`intent`、`strength`、`pattern`、`signal_status`、`bars_since_signal`、`stop_loss`、`take_profit`、`risk_reward_ratio`。
- 方向性观点必须引用字段或数值，避免只写“走势较好/较差”。
- 报告可保存到 `~/.stk/reports/` 并通过 `obsidian-knowledge` 写入 `14_Trading/DailyReport/{YYYY-MM-DD-[report-name]}.md`。

## 错误处理

- 单只股票失败：记录到报告中并继续处理其他标的。
- 大量失败：运行 `stk doctor check` 排查数据源。
- 缓存异常：运行 `stk cache clear` 后重试。
