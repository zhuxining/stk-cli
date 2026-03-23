# 工作流

四个可复用的工作流模块，对应技能的四种模式。

---

## 工作流 1: 市场总览

目标：指数行情 + 市场温度 + 新闻提炼。

```
步骤 1 — 并行:
  ├─ stk market               → 指数 + 温度
  └─ stk market news --count 20 → 新闻（cls+ths 合并）

步骤 2 — 按 report-templates.md 模板 1 生成报告
  └─ 保存到 ~/.stk/reports/市场总览_{YYYY-MM-DD}_{HH-mm}.md
```

**注意事项：**

- 两个命令完全独立，必须并行执行

---

## 工作流 2: 技术热点

目标：8 screen 多空分析 + 热点行业 + Top 15 入池。

```
步骤 1 — 采集:
  └─ stk stock rank                           → TechHotspot（行业统计 + 候选股）

步骤 2 — 批量评分:
  └─ stk stock scan <candidates 的 code>      → 评分 + 估值（候选通常 20-40 只）

步骤 3 — 取 Top 15（按 score 降序）

步骤 4 — 建组:
  └─ stk watchlist create <MMDD> --symbol S1 --symbol S2 ... --symbol S15

步骤 5 — 按 report-templates.md 模板 2 生成报告
  └─ 保存到 ~/.stk/reports/技术热点_{YYYY-MM-DD}_{HH-mm}.md
```

**注意事项：**

- 步骤 4 建组前先 `stk watchlist list` 检查同名组是否已存在，存在则先 `stk watchlist delete <MMDD>` 再创建
- candidates 已经过交叉验证（出现在 2+ 多方 screen），通常 20-40 只，scan 时全部传入即可
- 分析时用 TechHotspot 的 industries 做行业多空判断，candidates 的 bear_screens 标记冲突

---

## 工作流 3: 个股分析

目标：单只股票的评分 + 技术 + 基本面深度分析。

```
步骤 1 — 全部并行:
  ├─ stk stock scan <symbol>              → 评分 + 估值 + 信号 + ATR 风控
  ├─ stk stock kline <symbol> --count 20  → 近 20 日 K 线 + 全部指标
  └─ stk stock fundamental <symbol>       → 全部行业对比（growth + valuation + dupont）

步骤 2 — 按 report-templates.md 模板 3 综合分析生成报告
  └─ 保存到 ~/.stk/reports/个股分析_{symbol}_{YYYY-MM-DD}_{HH-mm}.md
```

**注意事项：**

- 三个命令完全独立，必须并行执行
- fundamental 的 dupont 仅 A 股支持，港股/美股自动跳过（服务层已处理）

---

## 工作流 4: 分组整体分析

目标：对整个 watchlist 分组做批量扫描 + 逐只点评。

```
步骤 1 — 并行:
  ├─ stk watchlist scan <name> --sort score  → 全组评分排名
  └─ stk watchlist kline <name> --count 10   → 全组 K 线

步骤 2 — 分析:
  - 按评分排序，标注 A+/A 级别标的
  - 标注异动（涨幅>5% / 跌幅>3% / RSI 超买超卖 / MACD 金叉死叉）
  - 每只标的给出技术展望（看多/看空/中性）+ 操作建议

步骤 3 — 可选深度（对评分前 3 或异动标的）:
  └─ stk stock fundamental <symbol>  → 行业对比补充

步骤 4 — 按 report-templates.md 模板 4 生成报告
  └─ 保存到 ~/.stk/reports/分组分析_{name}_{YYYY-MM-DD}_{HH-mm}.md
```

**注意事项：**

- 步骤 1 的两个命令独立，必须并行
- 步骤 3 为可选项，仅在评分突出或异动显著时执行
- 如用户未指定分组名称，用 `stk watchlist list` 列出供选择
