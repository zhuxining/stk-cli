---
name: stock-analysis
description: >
  stk-cli 股市分析技能。四种模式：市场总览（指数+新闻）、技术热点（8 screen 多空分析+选股入池）、个股分析（评分+技术+基本面）、分组整体分析（watchlist 批量扫描+点评）。
  触发关键词: 市场总览/市场分析/日报/技术热点/热点/选股/个股分析/股票分析/分组分析/自选分析/持仓检查。
---

# 股市分析技能

通过 `stk` CLI 采集市场数据，生成结构化分析报告。

## 参考文档

- `references/commands.md` — 命令参数与返回值
- `references/report-templates.md` — 报告格式模板

## 模式选择

先确认用户想要哪个模式（或从上下文推断）：

| 触发词 | 模式 |
|--------|------|
| 日报/市场/盘面/新闻 | 市场总览 |
| 热点/选股/技术形态/入池 | 技术热点 |
| 分析 XXX/看看 XXX | 个股分析 |
| 自选分析/分组分析/持仓检查/分析XX分组 | 分组整体分析 |
| 日报（含选股意图） | 市场总览 + 技术热点（串行，两份报告） |

---

## 模式一：市场总览

目标：一句话总结盘面 + 提炼重要新闻 + 标注影响板块。

**步骤：**

```
并行:
  ├─ stk market                  → 指数 + 温度
  └─ stk market news --count 20  → 新闻（cls+ths 合并）
```

**分析要点：**
- 一句话总结行情盘面（基于指数涨跌 + 温度）
- 提炼 3 条重要新闻，标注影响板块/个股/概念

**报告** → `report-templates.md` 模板 1 → `~/.stk/reports/市场总览_{date}_{time}.md`

---

## 模式二：技术热点

目标：分析 8 screen 多空情绪 + 归纳热点行业 + Top 15 入池。

`stk stock hotspot` 返回行业多空统计，`stk stock candidates` 返回交叉验证候选股（出现在 **3+** 个多方 screen、无空方信号、无 ST）。

**步骤：**

```
步骤 1 — 并行:
  ├─ stk stock hotspot     → TechIndustries（行业情绪）
  └─ stk stock candidates  → TechCandidates（入池候选）
步骤 2: stk stock scan <code1> <code2> ...    → 批量评分（空格分隔，勿用逗号）
步骤 3: 取 Top 15（按 score 降序）
步骤 4: stk watchlist create <MMDD> --symbol S1 --symbol S2 ... --symbol S15
```

**注意：**
- `stk stock scan` 用**空格**分隔多个代码：`stk stock scan 002218 600207 688552`
- `stk watchlist create/add` 每个 symbol 单独一个 `--symbol` / 空格分隔参数，纯代码即可（自动补交易所后缀）
- 步骤 4 前先 `stk watchlist list` 检查同名组，存在则用 `stk watchlist add <group> S1 S2 ...` 批量追加
- candidates 已过交叉验证，scan 时全部传入即可

**分析要点：**
- 基于 industries 的 bull_count/bear_count 判断市场情绪（偏多/偏空/分化）
- 提炼热点行业：bull_count 高 = 资金涌入，bear_count 高 = 风险

**报告** → `report-templates.md` 模板 2 → `~/.stk/reports/技术热点_{date}_{time}.md`

---

## 模式三：个股分析

目标：综合评分 + 深度技术 + 同业对比。

**步骤：**

```
全部并行:
  ├─ stk stock scan <symbol>              → 评分 + 估值 + 信号 + ATR 风控
  ├─ stk stock kline <symbol>             → K 线 + 全部指标
  └─ stk stock fundamental <symbol>       → 行业对比（growth + valuation + dupont）
```

**注意：** fundamental 的 dupont 仅 A 股支持，港股/美股自动跳过

**分析要点：**
- 评分解读（各维度信号 + ATR 风控）
- K 线技术面（均线/MACD/RSI/BOLL/量价）
- 行业对比定位（成长性/估值/杜邦）
- 输出结论：技术面展望 + 基本面优劣 + 风险提示 + 操作建议

**报告** → `report-templates.md` 模板 3 → `~/.stk/reports/个股分析_{symbol}_{date}_{time}.md`

---

## 模式四：分组整体分析

目标：对 watchlist 分组批量扫描 + 异动预警 + 逐只点评。

**步骤：**

```
步骤 1 — 并行:
  ├─ stk watchlist scan <group>   → 全组评分排名（默认按 score 排序）
  └─ stk watchlist kline <group>  → 全组 K 线
步骤 2 — 分析（见下方要点）
步骤 3 — 可选: 对评分前 3 或异动标的执行 stk stock fundamental
```

**分组名解析（严格遵守）：**
1. 从用户消息提取分组名（如"ETF分组"→`ETF`，"分析半导体组"→`半导体`），**直接用该名称请求**，禁止先 list
2. 若请求失败（分组不存在），再 `stk watchlist list` 查找最接近的分组名，用正确名称重试
3. 仅当用户完全未提及分组名称时，才 `stk watchlist list` 列出供选择

**分析要点：**
- 评分排名，标注高分/低分标的
- 异动预警（从 ScanItem.signals 中识别 `[买]`/`[卖]`/`[警]` 前缀的信号）
- 逐只点评：技术展望 + 操作建议

**报告** → `report-templates.md` 模板 4 → `~/.stk/reports/分组分析_{name}_{date}_{time}.md`

---

## 运行规范

### 并行化

独立查询必须同时发起。仅在后续步骤依赖前置结果时串行。

### 错误处理

- 单只股票失败 → 记录错误继续处理，报告中标注数据不完整
- 大量失败 → `stk doctor check` 排查数据源，告知用户
- 缓存异常 → `stk cache clear` 后重试

### 报告存储

保存到 `~/.stk/reports/`（目录不存在时 `mkdir -p`），报告末尾注明保存路径。

### 语气与格式

- 中文，对比数据用表格，分析用要点列表
- 关键数字和预警加粗
- 聚焦"所以呢"而非罗列数据
- 方向性观点必须附依据（哪些指标、什么数值）
