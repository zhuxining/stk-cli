---
name: stock-analysis
description: >
  stk-cli 股市分析技能。四种模式：市场总览（指数+新闻）、技术热点（8 screen 多空分析+选股入池）、个股分析（评分+技术+基本面）、分组整体分析（watchlist 批量扫描+点评）。
  触发关键词: 市场总览/市场分析/日报/技术热点/热点/选股/个股分析/股票分析/分组分析/自选分析/持仓检查。
---

# 股市分析技能

通过 `stk` CLI 采集市场数据，生成结构化分析报告。

## 前置条件

- 通过 `uv run stk <子命令>` 执行（已安装则直接用 `stk`）
- 所有命令输出 JSON，从 `{"ok": true, "data": ...}` 信封中解析 `data` 字段
- 首次运行或遇到连接问题时，先执行 `stk doctor check --quick` 验证数据源连通性

## 参考文档

- `references/commands.md` — 完整命令速查
- `references/workflows.md` — 可复用工作流模块
- `references/report-templates.md` — 报告格式模板

## 模式选择

先确认用户想要哪个模式（或从上下文推断）：

1. **市场总览** — 指数行情 + 市场温度 + 新闻提炼（快变信息）
2. **技术热点** — 8 个 screen 多空分析 + 热点行业 + Top 15 入池（日级变化）
3. **个股分析** — 单只股票评分 + 技术 + 基本面深度分析
4. **分组整体分析** — 对 watchlist 分组做批量扫描 + 逐只点评

触发映射：

- "日报/市场/盘面/新闻" → 市场总览
- "热点/选股/技术形态/入池" → 技术热点
- "分析 XXX/看看 XXX" → 个股分析
- "自选分析/分组分析/持仓检查" → 分组整体分析

## 模式一：市场总览

目标：一句话总结盘面 + 提炼重要新闻 + 标注影响板块。

1. **并行采集**: `stk market` + `stk market news`（详见 workflows.md 工作流 1）
2. **汇总分析**:
   - 一句话总结行情盘面（基于指数涨跌 + 温度）
   - 提炼 3 条重要新闻，标注影响板块/个股/概念
3. **生成报告** → `~/.stk/reports/市场总览_{date}_{time}.md`

## 模式二：技术热点

目标：分析 8 screen 多空情绪 + 归纳热点行业 + Top 15 入池。

`stk stock rank` 返回 `TechHotspot`：行业多空统计（6 个有"所属行业"的 screen）+ 交叉验证候选股（出现在 2+ 个多方 screen 的股票，同时标记空方冲突）。

1. **采集**: `stk stock rank` → TechHotspot（详见 workflows.md 工作流 2）
2. **分析归纳**:
   - 基于 industries 的 bull_count/bear_count 判断市场情绪（偏多/偏空/分化）
   - 提炼热点行业：bull_count 高的行业 = 资金涌入，bear_count 高的 = 风险
3. **批量评分**: `stk stock scan <candidates 的 code>`（候选通常 20-40 只）
4. **取 Top 15** 按 score 降序，建组 `stk watchlist create <MMDD>`
5. **生成报告** → `~/.stk/reports/技术热点_{date}_{time}.md`

## 模式三：个股分析

目标：综合评分 + 深度技术 + 同业对比。

1. **并行采集**: `stk stock scan` + `stk stock kline --count 20` + `stk stock fundamental`（详见 workflows.md 工作流 3）
2. **综合分析**:
   - 评分解读（各维度信号 + ATR 风控）
   - K 线技术面解读（均线/MACD/RSI/BOLL/量价）
   - 行业对比定位（成长性/估值/杜邦）
3. **输出结论**: 技术面展望 + 基本面优劣 + 风险提示 + 操作建议
4. **生成报告** → `~/.stk/reports/个股分析_{symbol}_{date}_{time}.md`

## 模式四：分组整体分析

目标：对 watchlist 分组批量扫描 + 异动预警 + 逐只点评。

1. **并行采集**: `stk watchlist scan --sort score` + `stk watchlist kline`（详见 workflows.md 工作流 4）
2. **分析**:
   - 评分排名 + A+/A 标注
   - 异动预警（大涨大跌/RSI 极端/MACD 信号）
   - 逐只点评：技术展望 + 操作建议
3. **可选深度**: 对评分前 3 或异动标的执行 `stk stock fundamental`
4. **生成报告** → `~/.stk/reports/分组分析_{name}_{date}_{time}.md`

## 运行规范

### 并行化

独立查询必须同时发起。仅在后续步骤依赖前置结果时串行。

### 错误处理

- 单只股票失败 → 记录错误继续处理，报告中标注数据不完整
- 大量失败 → `stk doctor check` 排查数据源，告知用户
- 缓存异常 → `stk cache clear` 后重试

### 报告存储

保存到 `~/.stk/reports/`（目录不存在时 `mkdir -p`）：

- 市场总览: `市场总览_{YYYY-MM-DD}_{HH-mm}.md`
- 技术热点: `技术热点_{YYYY-MM-DD}_{HH-mm}.md`
- 个股分析: `个股分析_{symbol}_{YYYY-MM-DD}_{HH-mm}.md`
- 分组分析: `分组分析_{name}_{YYYY-MM-DD}_{HH-mm}.md`

报告末尾注明保存路径。

### 语气与格式

- 中文，对比数据用表格，分析用要点列表
- 关键数字和预警加粗
- 聚焦"所以呢"而非罗列数据
- 方向性观点必须附依据（哪些指标、什么数值）
