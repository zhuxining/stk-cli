---
name: stk-cli-reference
description: >
  `stk` 是一个终端命令行工具，**核心能力是管理自选股分组（含跨平台同步）以及计算股票技术指标**。
  涉及 stk 命令语法、分组操作（增删改查/批量导入/信号分流）、
  跨平台同步（长桥↔同花顺）、技术分析（ta-lib 日线/实盘扫描、信号共振评分、ATR 风控）时触发。
  其他功能（行情查询、市场热度等）为辅助，非重点。
---

# stk-cli 命令参考

所有 `stk` 命令通过统一 JSON envelope 输出：`{"ok": true, "data": ..., "error": null, "meta": {...}}`。输出到 stdout，日志到 stderr。

---

## 🎯 触发条件

| 用户可能这样问... | 读取文件 |
|------------------|---------|
| "建个分组"、"加自选"、"批量导入"、"信号分流"、"扫描自选股"、"scoop 的 --strict 是什么意思" | `references/watchlist.md` |
| "同步到同花顺"、"长桥和同花顺保持一致"、"ths push 和 pull 区别" | `references/sync.md` |
| "扫一下 600519"、"日线信号怎么样"、"技术面分析"、"K 线"、"这个信号强不强"、scan 字段含义 | `references/stock.md` → `references/signal-strategy.md` / `references/output-schema.md` |
| "stk xxx 怎么用"、"这个参数什么意思" | 本文工作流 + 对应参考文件 |

其他辅助功能（行情查询 `market`、数据源诊断 `tools`）在有需要时按名读取对应文件。

---

## 常用工作流

以下展示命令如何串联。每步的具体参数见对应领域参考文件。

### 工作流 1：从市场筛选到自选建仓

```
stk market index          # 1. 了解大盘温度和体制，判断整体方向
stk market hotspot        # 2. 找多头集中的行业，缩小选股范围
stk market candidates     # 3. 跨 screen 多方确认的候选池
stk watchlist scoop <g> --scan  # 4. 扫描过滤后入库（只留推荐信号）
stk watchlist scan <g>    # 5. 对入库标的做完整日线监控
```

### 工作流 2：盘中实盘监控

```
stk watchlist scan <g>    # 1. 盘前/盘后确认日线信号状态
stk watchlist scan-live <g>    # 2. 盘中运行，获取实时触发提醒
                           # 3. 对触发标的读取 references/signal-strategy.md 解读信号
                           # 4. 对关注标的读取 references/output-schema.md 理解返回字段
```

### 工作流 3：信号分流与预警分离

```
stk watchlist scan <g>    # 1. 对所有标的打分
stk watchlist route <g> <观察组> <预警组>  # 2. entry 进观察组，exit 进预警组
stk watchlist kline <观察组>    # 3. 对观察组做 K 线复核
                           # 4. 结合 references/signal-strategy.md 理解退出信号含义
```

### 工作流 4：跨平台同步

```
stk sync ths list         # 1. 查看同花顺现有分组
stk sync ths diff --from <长桥组> --to <同花顺组>  # 2. 预览差异（不修改）
stk sync ths push --from <长桥组> --to <同花顺组>  # 3. 执行同步
stk sync ths pull --from <同花顺组> --to <长桥组>  # 4. 反向拉取（如需要）
```

---

## 核心概念

**标的代码格式**：A 股用纯数字（`600519`→`600519.SH`，`000001`→`000001.SZ`，`8xxxxx`→`8xxxxx.BJ`），港股加 `.HK`（`700.HK`），美股直接代码（`AAPL`）。CLI 自动标准化，你只需输入最简形式。

**数据源**：longport 为统一行情源，akshare 补充 A 股特色数据（THS 排名、行业对比、公司概况）。ta-lib 计算全部技术指标。

**JSON envelope**：所有输出 `{"ok": true/false, "data": ..., "error": null/string, "meta": {...}}`。`ok: false` 时 `error` 含错误详情。

---

## 深度触发指引

精确匹配具体问题到对应参考文件：

| 用户精确问题 | 读取路径 |
|-------------|---------|
| "scoop 的 --strict 是什么意思" / "scoop 和 hot 有什么区别" | → `references/watchlist.md` |
| "scan 结果中 overall_bias 怎么理解" / "各种颜色代表什么" | → `references/output-schema.md`（字段定义）→ `references/signal-strategy.md`（取值含义） |
| "趋势买入信号强不强" / "EXIT 信号要卖吗" / "共振信号怎么看" | → `references/signal-strategy.md` |
| "如何从候选股筛选到入库" / "完整的选股流程" | → 本文"工作流 1" → `references/market.md` → `references/watchlist.md` |
| "想同步长桥到同花顺" / "ths push 和 pull 区别" | → `references/sync.md` |
| "盘中实时监控怎么用" / "scan-live 是什么" | → `references/stock.md`（scan-live 命令）→ `references/signal-strategy.md`（实盘解读） |
