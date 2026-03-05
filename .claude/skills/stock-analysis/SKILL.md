---
name: stock-analysis
description: >
  stk-cli 项目的股市分析技能。从选股、扫描、盯盘、复盘四个角度生成结构化分析报告。
  当用户想要分析股票、生成市场报告、筛选股票、检查持仓、复盘交易周时使用此技能。
  触发关键词: 选股/扫描/日报/盯盘/复盘/市场分析/持仓检查/股市报告/市场概览/交易计划/组合回顾/周复盘。
---

# 股市分析技能

通过 `stk` CLI 命令采集市场数据，生成结构化分析报告的工作流技能。包含四个模式，根据用户意图选择对应流程执行。

## 前置条件

- 工作目录为 stk-cli 项目（或 `stk` 命令已在 PATH 中）
- 通过 `uv run stk <子命令>` 执行命令（已安装则直接用 `stk`）
- 所有命令输出 JSON，从 `{"ok": true, "data": ...}` 信封中解析 `data` 字段
- 扫描/盯盘/复盘默认使用用户的 watchlist 作为股票池

## 可用命令速查

| 命令 | 用途 |
|------|------|
| `stk market index` | 主要指数行情 |
| `stk market temp` | 市场温度 (0-100) |
| `stk market breadth` | 涨跌统计（上涨/下跌/涨停/跌停） |
| `stk market news` | 全球市场新闻 |
| `stk board list --type sector\|concept` | 板块排行 |
| `stk board cons <名称>` | 板块成分股 |
| `stk board flow <名称>` | 板块资金流向历史 |
| `stk board detail <名称>` | 板块内个股资金明细 |
| `stk stock rank --type hot\|tech\|flow` | 股票排行 |
| `stk stock quote <代码>` | 实时行情 |
| `stk stock profile <代码>` | 公司主营简介 |
| `stk stock fundamental <代码>` | 成长性/估值/杜邦分析 |
| `stk stock valuation <代码>` | PE/PB/PS/市值 |
| `stk stock indicator <代码> <指标名>` | 技术指标 (MA/MACD/RSI/KDJ/BOLL) |
| `stk stock history <代码>` | 历史K线 |
| `stk stock news <代码>` | 个股新闻 |
| `stk stock flow <代码>` | 个股资金流向 |
| `stk stock chip <代码>` | 筹码分布 |
| `stk watchlist list` | 列出所有自选 |
| `stk watchlist show <名称>` | 查看自选股列表 |

## 模式选择

先确认用户想要哪个模式（或从上下文推断）：

1. **选股** — 按策略筛选候选股票
2. **扫描** — 当日市场全景 + 自选股深度检查（收盘后使用）
3. **盯盘** — 盘中持仓快照 + 异动预警
4. **复盘** — 近7日报告回顾 + 最新数据对比 + 策略反思 + 下周计划（周末或需要时）

> 兼容触发："日报" → 自动映射为"扫描"模式

然后收集相关偏好：
- 使用哪个自选列表（默认取第一个）
- 选股的策略偏好（参见 `references/strategies.md` 中的策略模板）
- 关注的特定指标或阈值

## 模式一：选股

目标：从宏观市场 -> 板块方向 -> 候选筛选 -> 验证精选。

### 步骤

1. **市场环境判断** — 并行执行：
   - `stk market temp` -> 判断整体情绪
   - `stk market breadth` -> 确认市场宽度支持进场
   - `stk market index` -> 指数水平与趋势

2. **板块方向确认** — 并行执行：
   - `stk board list --type sector` -> 找到领涨行业
   - `stk board list --type concept` -> 找到热门概念
   - 挑选前 2-3 个板块，分别执行 `stk board flow <名称>` 验证资金持续流入

3. **板块个股提取** — 从步骤2确认的 2-3 个强势板块中挖掘候选：
   - 对每个板块并行执行：
     - `stk board cons <板块名>` -> 获取成分股列表
     - `stk board detail <板块名>` -> 板块内个股资金流明细
   - 筛选规则：从每个板块中取资金净流入前 3-5 只（通过 board detail 排序）
   - 合并去重得到**板块候选池**（约 6-15 只）

4. **技术形态筛选** — 作为板块筛选的补充/交叉路径，根据用户策略偏好选择：
   - 趋势型: `stk stock rank --type tech --screen lxsz` (连续缩量上涨)
   - 反弹型: `stk stock rank --type tech --screen cxfl` (持续放量)
   - 突破型: `stk stock rank --type tech --screen xstp` (向上突破)
   - 量价型: `stk stock rank --type tech --screen ljqs` (量价齐升)
   - 产出**技术候选池**

5. **交叉验证与合并** — 三维度交叉：
   - `stk stock rank --type flow --scope main` -> 产出**资金候选池**
   - 取步骤3(板块候选) ∩ 步骤4(技术候选) ∩ 步骤5(资金候选) 的交集
   - 交集优先，其次取至少命中两个维度的股票
   - 最终候选池控制在 5-8 只

6. **候选深度验证**（5-8 只，每只股票的查询并行执行）：
   - `stk stock quote <代码>` — 当前价格
   - `stk stock valuation <代码>` — PE/PB 合理性检查
   - `stk stock indicator <代码> MACD` + `RSI` — 确认技术信号
   - `stk stock flow <代码>` — 个股资金流向
   - `stk stock fundamental <代码> --type growth` — 成长性检查

7. **输出** — 按 `references/report-templates.md` 中的选股报告模板生成报告，排序候选股，重点分析 Top 3。

## 模式二：扫描

目标：当日市场全景 + 自选股深度检查，一站式收盘分析（合并原日报与复盘的当日部分）。

### 步骤

1. **大盘概览** — 并行执行：
   - `stk market index` — 指数表现
   - `stk market temp` — 市场温度
   - `stk market breadth` — 涨跌统计

2. **板块热点** — 并行执行：
   - `stk board list --type sector` -> 行业涨跌前5
   - `stk board list --type concept` -> 热门概念
   - `stk stock rank --type flow --scope sector` -> 板块资金排行
   - 对前3板块执行 `stk board flow <名称>` — 验证资金持续性

3. **资讯摘要** — `stk market news --source cls --filter 重点 --count 10`

4. **自选股深度扫描** — `stk watchlist show <名称>` 获取股票列表，然后对每只股票并行查询：
   - `stk stock quote <代码>` — 收盘数据
   - `stk stock flow <代码>` — 资金流向
   - `stk stock history <代码> --count 10` — 近期K线走势
   - `stk stock indicator <代码> MACD` — 趋势信号
   - `stk stock indicator <代码> RSI` — 动量状态
   - `stk stock indicator <代码> KDJ` — 短周期信号
   - `stk stock indicator <代码> BOLL` — 波动通道
   - `stk stock chip <代码>` — 筹码分布

5. **综合评价** — 对每只自选股给出：
   - 今日表现小结
   - 技术展望（看多/看空/中性，附依据）
   - 风险等级评估（低/中/高）
   - 操作建议（持有/减仓/加仓及理由）

6. **明日关注** — 基于市场环境 + 持仓状态：
   - 每只股票的关键价位（支撑/压力）
   - 需关注的板块与方向
   - 潜在风险提示

## 模式三：盯盘

目标：对所有持仓做一次全面的实时快照检查，发现异动和风险。

### 步骤

1. **市场环境速览** — 并行执行：
   - `stk market index`
   - `stk market temp`

2. **加载持仓** — `stk watchlist show <名称>`（用户指定的持仓列表）

3. **逐一深度扫描** — 对每只持仓股，并行查询：
   - `stk stock quote <代码>` — 当前价格与涨跌
   - `stk stock flow <代码>` — 实时资金流向
   - `stk stock indicator <代码> MACD` — 趋势信号
   - `stk stock indicator <代码> RSI` — 超买超卖
   - `stk stock indicator <代码> KDJ` — 短周期信号

4. **异动预警** — 标记满足以下任一条件的持仓：
   - 日内跌幅 > 3% 或涨幅 > 5%
   - RSI > 80（超买）或 RSI < 30（超卖）
   - MACD 死叉或金叉
   - 主力资金大幅净流出
   - KDJ 超买(>80) / 超卖(<20)

5. **输出** — 生成盯盘报告，异动汇总置顶，逐只持仓详情在下，附操作建议。

## 模式四：复盘

目标：周级回顾 — 读取近7日历史报告，对比最新市场动态，总结趋势变化和策略得失，制定下周计划。

### 步骤

1. **读取历史报告** — 从 `~/.stk/reports/` 中读取最近7日的扫描/盯盘/选股报告：
   - 列出目录下文件，按日期筛选近7日的报告
   - 提取每日市场温度、板块排名、自选股涨跌等关键数据
   - 如无历史报告，提示用户先积累几天扫描数据

2. **采集最新市场数据** — 并行执行：
   - `stk market index` — 最新指数
   - `stk market temp` — 当前温度
   - `stk market breadth` — 涨跌统计
   - `stk board list --type sector` — 行业板块排名
   - `stk board list --type concept` — 概念板块排名

3. **趋势对比分析**：
   - **市场温度走势** — 从历史报告提取温度值，绘制7日趋势（数值列表），标注转折点
   - **板块轮动追踪** — 对比每日板块排名，识别：持续强势板块 / 由强转弱板块 / 新崛起板块
   - **自选股表现曲线** — 从历史报告提取各股涨跌数据，计算周累计涨跌，标注关键事件

4. **策略回顾**：
   - 选股报告中的候选股后续表现如何（对比推荐价与当前价）
   - 盯盘预警是否应验（触发预警后实际走势）
   - 操作建议的执行效果评估

5. **总结与计划**：
   - 本周市场主线逻辑总结
   - 持仓调整建议（加仓/减仓/换仓及理由）
   - 下周关注方向（板块、个股、事件）
   - 需要规避的风险

## 报告存储

每次生成的报告保存到 `~/.stk/reports/`：
- 文件名格式:
  - 扫描: `扫描_{YYYY-MM-DD}_{HH-mm}.md`
  - 盯盘: `盯盘_{YYYY-MM-DD}_{HH-mm}.md`
  - 选股: `选股_{YYYY-MM-DD}_{HH-mm}.md`
  - 复盘: `复盘_{YYYY-MM-DD}_周回顾.md`
- "日报"触发时生成的报告也使用 `扫描_` 前缀
- 目录不存在时自动创建: `mkdir -p ~/.stk/reports`
- 报告末尾注明保存路径，方便用户后续查阅

## 并行化原则

尽量最大化并行执行，独立的数据查询应同时发起：
- 市场级查询 -> 全部并行
- 板块级查询 -> 全部并行
- 个股查询 -> 股票之间并行，同一股票的不同指标也并行
- 仅在后续步骤依赖前置结果时串行（如需要板块列表后才能查板块资金流向）

## 语气与格式

- 报告使用中文
- 对比数据用表格呈现（板块排名、个股对比）
- 分析评论用要点列表
- 关键数字和预警信息加粗
- 评论简洁可操作 — 聚焦"所以呢"而非单纯罗列数据
- 给出方向性观点时，必须附上依据（哪些指标、什么数值）
