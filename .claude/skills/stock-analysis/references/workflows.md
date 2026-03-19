# 可复用工作流模块

各模式通过名称引用这些模块。模块内的独立查询应并行执行。

---

## 技术选股筛选

> 引用模式：选股、扫描、复盘

根据策略选择对应 screen 类型，可并行执行多个：

| screen | 含义 | 对应策略 |
|--------|------|---------|
| `lxsz` | 连续缩量上涨 | 趋势跟踪 |
| `cxfl` | 持续放量 | 超跌反弹 |
| `xstp` | 向上突破 | 突破回踩 |
| `ljqs` | 量价齐升 | 短线动量 |

- 选股模式：按策略选 1-2 个 screen 并行执行，取并集作为候选池
- 扫描/复盘模式：并行执行全部 4 个 screen，各取前 5 概览当日技术热点

---

## 个股深度扫描

> 引用模式：扫描、选股(验证步骤)

对每只股票并行查询：

- `stk stock quote <代码>` — 当前价格与涨跌
- `stk stock flow <代码>` — 资金流向
- `stk stock history <代码> --count 10` — 近期 K 线 + 全部技术指标
- `stk stock score <代码>` — 综合评分 + ATR 风控

**按需追加**（异动或需深入分析时）：

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

- `stk market news --source cls --count 10`

---

## 策略匹配

> 引用模式：选股

根据用户偏好或当前市场判断，参照 `references/strategies.md` 中的「市场环境与策略匹配」表确定策略方向。
