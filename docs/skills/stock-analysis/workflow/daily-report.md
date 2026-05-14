# DailyReport 工作流

DailyReport 是 Agent 工作流，不是独立 CLI 命令。`stk-cli` 负责生成结构化数据，`stock-analysis` 负责选择场景模板、分析和组装 Markdown，`obsidian-knowledge` 负责写入 Obsidian。

## 触发与范围

- 触发词：`DailyReport`、交易日报、每日复盘、今天日报、保存到 Obsidian。
- 默认范围：市场热点分析 + 分组信号追踪。
- 可选范围：用户明确要求“深入对比/详细比较/多股比较”时，追加多股深入对比。
- 输出位置：`14_Trading/DailyReport/{YYYY-MM-DD}.md`。

## 取数方法

1. 市场热点分析取数：

```bash
stk market
stk market news --count 20
```

1. 用户明确要求“热点/选股/候选”时，补充技术热点取数：

```bash
stk stock hotspot
stk stock candidates
stk stock scan <candidate-symbols>
```

1. 分组信号追踪取数：

```bash
stk watchlist scan <group>
```

1. 用户要求多股深入对比时，基于指定股票或分组 `focus` 追加：

```bash
stk stock scan <symbols...>
```

## 模板调用方法

| 阶段 | 模板 | 作用 |
|------|------|------|
| 市场与热点 | `templates/market-hotspot-analysis.md` | 判断市场状态、新闻影响和可选技术热点。 |
| 分组追踪 | `templates/group-signal-tracking.md` | 汇总 watchlist 分组扫描、focus 明细、高优先级复核和明日动作。 |
| 深入比较 | `templates/multi-stock-deep-comparison.md` | 仅在用户要求时，横向比较多只股票的信号质量和风控。 |

## 分析方法

### 市场热点分析

- 使用 `templates/market-hotspot-analysis.md`。
- 默认只输出市场状态和重要消息。
- 如果用户要求“热点/选股/候选”，追加技术热点；候选股必须经过 `stk stock scan` 确认。
- 三地市场方向冲突时，今日结论写“市场分化”。

### 分组信号追踪

- 使用 `templates/group-signal-tracking.md`。
- 每个 watchlist 分组生成一行统计。
- 只展开 `MonitorResult.focus`；无信号标的只进入统计。
- 合并所有分组的 focus 生成明日动作。
- high 标的若有 `daily10`，补一句近 10 日复核。

### 多股深入对比

- 使用 `templates/multi-stock-deep-comparison.md`。
- DailyReport 默认不输出本段，避免日报过长。
- 只有用户明确要求“深入对比/详细比较/多股比较”时追加。
- 对比维度固定为：信号新鲜度、置信度、辅助态度、风险收益、近 10 日复核。

## 组装方法

1. 读取 `templates/README.md` 确认通用口径。
2. 先用 `market-hotspot-analysis.md` 生成市场段。
3. 再用 `group-signal-tracking.md` 生成分组追踪段。
4. 如用户要求深入比较，再用 `multi-stock-deep-comparison.md` 生成对比段。
5. 生成 `今日结论`：
   - 1-2 句。
   - 必须包含市场状态、是否有重点关注标的、高优先级数量、主要风险方向。
   - 如果所有分组 `focus_count=0`，写“今日暂无明确趋势触发”。
6. 组装最终 Obsidian 页面：

```markdown
---
date: {YYYY-MM-DD}
type: daily-trading-report
source: stk-cli
groups:
  - {group_name}
---

# DailyReport - {YYYY-MM-DD}

## 今日结论

{今日结论}

{市场热点分析}

{分组信号追踪}

{多股深入对比；仅用户要求时输出}

## 数据限制

本报告基于日线收盘确认信号与 `stk-cli` 当前可用数据生成，不代表盘中实时信号，也不构成投资建议。
```

1. 通过 `obsidian-knowledge` 写入 `14_Trading/DailyReport/{YYYY-MM-DD}.md`。

## Obsidian 写入

- 目标目录固定为 `14_Trading/DailyReport`。
- 文件名固定为 `{YYYY-MM-DD}.md`。
- 同一交易日更新同一文件，不创建重复副本。
- Obsidian vault 根路径由 `obsidian-knowledge` 解析；本技能只传相对目录和文件名。

## 错误处理

- 单个分组扫描失败：在日报中记录该分组失败，并继续处理其他分组。
- 单个标的失败：计入 `errors` 或失败统计，不中断日报。
- 市场新闻失败：保留市场状态和分组信号，新闻部分写“新闻数据暂不可用”。
