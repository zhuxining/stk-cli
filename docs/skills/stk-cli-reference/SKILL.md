---
name: stk-cli-reference
description: >
  当你需要查询 A 股/港股/美股行情、扫描个股技术信号（日线/实盘）、
  管理自选股分组并批量导入候选标的、同步跨平台（长桥↔同花顺）自选数据、
  或诊断数据源健康状态时，使用此技能获取精确命令语法、参数选择建议、
  返回字段含义和信号解读规则。
---

# stk-cli 命令参考

所有 `stk` 命令通过统一 JSON envelope 输出：`{"ok": true, "data": ..., "error": null, "meta": {...}}`。输出到 stdout，日志到 stderr。

---

## 领域索引

按用户意图选择参考文件。**不要一次性读取所有文件**——只读匹配当前需求的：

| 当你想要... | 读取文件 | 涵盖命令 |
|-------------|---------|----------|
| 看大盘温度、找热门板块、筛技术候选、看热门个股 | `references/market.md` | `stk market *` 全部 |
| 扫描个股信号（日线/实盘）、看 K 线指标、同业对比 | `references/stock.md` | `stk stock *` 全部 |
| 管理自选分组、批量入库候选/热门股、信号分流、扫描自选 | `references/watchlist.md` | `stk watchlist *` 全部——命令最多 |
| 同步长桥↔同花顺自选数据 | `references/sync.md` | `stk sync *` 全部 |
| 诊断数据源、管理缓存 | `references/tools.md` | `stk doctor / cache` |
| 理解 scan 返回字段的结构和含义 | `references/output-schema.md` | `MonitorResult`、`LiveScanResult` 字段表 |
| 解读信号强弱、辅助因子、指标口径 | `references/signal-strategy.md` | 信号策略和交易含义 |

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

## 参考文件读取指引

| 用户提问示例 | 应读取 |
|-------------|--------|
| "scoop 的 --strict 是什么意思" | `references/watchlist.md` |
| "scan 结果中 overall_bias 怎么理解" | `references/output-schema.md`（查字段定义）→ `references/signal-strategy.md`（查取值含义） |
| "趋势买入信号强不强" | `references/signal-strategy.md` |
| "如何从候选股筛选到入库" | 本文"工作流 1" → `references/market.md` → `references/watchlist.md` |
| "想同步长桥到同花顺" | `references/sync.md` |
| "盘中实时监控怎么用" | `references/stock.md`（scan-live 命令）→ `references/signal-strategy.md`（实盘扫描部分） |
