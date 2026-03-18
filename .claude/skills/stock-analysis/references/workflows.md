# 可复用工作流模块

各模式通过名称引用这些模块。模块内的独立查询应并行执行。

---

## 市场概览

> 引用模式：选股、扫描、盯盘、复盘

并行执行：
- `stk market index` — 指数表现
- `stk market temp` — 市场温度
- `stk market breadth` — 涨跌统计

---

## 板块扫描

> 引用模式：选股、扫描、复盘

**第一步**（并行）：
- `stk board list --type sector` — 行业板块排行
- `stk board list --type concept` — 概念板块排行

**第二步**（依赖第一步结果）：
- 对前 2-3 个板块执行 `stk board flow <名称>` — 验证资金持续流入

---

## 个股深度扫描

> 引用模式：扫描、选股(验证步骤)

对每只股票并行查询：
- `stk stock quote <代码>` — 当前价格与涨跌
- `stk stock flow <代码>` — 资金流向
- `stk stock history <代码> --count 10` — 近期 K 线 + 全部技术指标

**按需追加**（异动或需深入分析时）：
- `stk stock chip <代码>` — 筹码结构（仅A股）
- `stk stock fundamental <代码> --type growth` — 成长性（选股验证时追加）

> `history` 已包含 MACD/RSI/KDJ/BOLL/ATR 等全部指标，无需单独调用 `indicator`。

---

## 个股快速检查

> 引用模式：盯盘

对每只持仓股并行查询：
- `stk stock quote <代码>` — 当前价格与涨跌
- `stk stock flow <代码>` — 实时资金流向
- `stk stock indicator <代码>` — 全部技术指标（省略指标名 = 计算全部）

> 盯盘使用 `indicator` 而非 `history`，因为只需最新指标值，不需要历史 K 线序列。

---

## 资讯采集

> 引用模式：扫描

- `stk market news --source cls --filter 重点 --count 10`

---

## 策略匹配

> 引用模式：选股

根据 **市场概览** 的温度 + 涨跌统计，参照 `references/strategies.md` 中的「市场环境与策略匹配」表自动确定策略方向。
