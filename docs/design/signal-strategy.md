# 信号规则

> Status: active

本文档是当前买卖信号阈值、优先级和时间语义的唯一事实来源。系统只维护一套
`StockAssessment`，不再计算事件型推荐、预警或兼容评分。

## 目标与状态

每日扫描从 Longport 分组中筛选当前具有操作意义的信号，而不是输出所有趋势标的。
所有判断只使用已确认日线；实时 quote 只用于展示。

每只成功分析的标的恰好属于一种状态：

- `buy`：满足买入基线并命中至少一种买入触发。
- `sell`：命中至少一种退出触发，优先于 buy。
- `watch`：趋势部分成立，但当前不具备有效买点。
- `ignored`：未形成需要关注的状态。

scan 只展开 buy 和 sell；watch 与 ignored 只进入汇总计数。route 直接使用这两个数组
刷新目标分组。

## 买入信号

必须满足全部基线：

```text
EMA9 > EMA26
AND Supertrend bullish
AND close >= EMA26
AND RSI14 < 75
AND close <= EMA9 + 1.5 * ATR10
```

并至少命中一种结构化触发：

| trigger | 判定 |
|---|---|
| `healthy_continuation` | `close >= EMA9` 且 `45 <= RSI14 < 70` |
| `pullback_hold` | `EMA26 <= close <= EMA9`、`RSI14 >= 40`，且收盘价高于前一日 |
| `momentum_recovery` | 最近 3 根已确认日线内 RSI14 上穿 50，当前仍不低于 50 |
| `trend_start` | 最近 3 根已确认日线内 Supertrend 翻多，当前仍为多头 |

成交额量比只解释量能，不作为买入硬门槛。

## 卖出信号

满足任意一项：

| trigger | 判定 |
|---|---|
| `supertrend_bearish` | 当前 Supertrend 为空头 |
| `ema26_breakdown` | 连续 2 根收盘价低于各自 EMA26 |
| `overheat_reversal` | 前一日 RSI14 不低于 75、今日 RSI14 下降且 `close < EMA9` |

卖出表示退出或风险预警，不表示做空。卖出优先于买入，同一标的不会同时进入两个数组。
单独 RSI 过热不会触发卖出，也不要求回落当日已经跌出过热区。

## 质量解释

质量上下文不改变买卖硬条件，只影响排序和说明：

| factor | 指标 |
|---|---|
| `momentum` | RSI14、KDJ9 |
| `macd` | MACD(12,26,9) |
| `boll` | BOLL(20,2) |
| `volume_price` | 5 日成交额量比、涨跌幅 |
| `ema_trend` | EMA5/10/20 |
| `money_flow` | MFI14 |
| `divergence` | 价格与 MACD histogram |

`quality.bias` 为 `supportive`、`mixed`、`risky` 或 `conflicting`。买卖数组按该顺序
排列，同一 bias 内按 5 日成交额量比降序排列。默认只输出 bias 和 warnings；
`--include-factors` 才展开全部 factors。

## 风控

只有 buy 项输出风险边界：

- `stop_loss` 优先使用位于价格下方的多头 Supertrend，否则使用 `close - 2*ATR10`。
- `trailing_stop` 在存在有效多头 Supertrend 时输出。
- 不输出固定止盈目标、风险收益比或风险等级。
- sell 是退出信号，不生成做空目标或空头风控。

## 数据与失败语义

- `calc_score()` 默认请求 60 根 K 线；剔除未收盘日线后至少需要 30 根。
- scan 中单标的失败进入 `failures`，其他标的继续处理。
- `summary.buy + sell + watch + ignored = analyzed`。
- `summary.total = analyzed + failed`。
- route 跳过扫描失败的标的，继续写入其余结果，并在成功响应中返回 `failures`。
- `--recent-bars N` 使用评分时已获取的数据附加最近 1–30 根紧凑日线，不二次请求。
