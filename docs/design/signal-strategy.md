# 信号规则

> Status: active

本文档是股票买卖信号阈值、优先级和时间语义的唯一事实来源。系统只维护一套
`StockAssessment`，不再计算事件型推荐、预警或兼容评分。ETF 横截面轮动使用独立
模型与规则，详见 [ETF 双池轮动](etf-rotation.md)。

## 目标与状态

每日扫描从 Longport 分组中筛选当前具有操作意义的信号，而不是输出所有趋势标的。
所有判断只使用已确认日线；实时 quote 只用于展示。

每只成功分析的标的恰好属于一种状态：

- `buy`：最近两根确认日线内 Supertrend 由空翻多，当前仍为多头且通过买入过滤。
- `hold`：多头趋势结构（EMA9 > EMA26 且 Supertrend 多头）保持、收盘价位于 EMA26
  之上，且最近两根确认日线内无任何反转事件，视为持有观察。
- `sell`：最近两根确认日线内至少一个趋势指标转空，且该指标当前仍为空头。
- `watch`：趋势结构尚未同向、近期多头反转未通过买入过滤，或多头结构保持但收盘价
  已跌破 EMA26（趋势转弱观察）。
- `ignored`：趋势已经持续超过信号窗口，或未形成需要关注的反转（主要是空头趋势
  持续且无事件的标的）。

scan 只展开 buy、hold 和 sell；watch 与 ignored 只进入汇总计数。route 直接使用
这三个数组刷新目标分组。

## 反转事件与有效期

系统只识别四种事件：

| trigger code | 事件 |
|---|---|
| `supertrend_bullish_reversal` | Supertrend 由空翻多 |
| `ema_bullish_crossover` | EMA9 上穿 EMA26 |
| `supertrend_bearish_reversal` | Supertrend 由多翻空 |
| `ema_bearish_crossover` | EMA9 下穿 EMA26 |

buy 只使用 Supertrend 由空翻多作为触发事件，并输出
`signal.confirmation.confirmed_at`；确认当日的 `age_bars=0`，下一根确认日线为 1，
从 2 开始失效。有效期内若 Supertrend 再次翻空，原信号立即失效。

`signal.triggers[]` 保留事件的 `code`、`occurred_at` 和相对当前的 `age_bars`。
buy 固定只有 Supertrend 翻多事件；sell 可以包含一个或两个当前有效的空头事件。

## 买入信号

必须同时满足：

```text
最近两根确认日线内 Supertrend 由空翻多
AND 当前 Supertrend 仍为 bullish
AND close >= EMA26
AND RSI14 < 75
```

若 Supertrend 翻多后 RSI 已经过热或价格跌破 EMA26，归入 watch。涨幅以及相对
`EMA9 + 1.5 * ATR10` 的价格偏离不限制 buy 或 route 入组；`max_entry_price` 仅作为
参考信息输出。EMA9/EMA26 金叉不再是买入硬条件，仅作为质量上下文。成交额量比只解释
量能，不作为买入硬门槛。

## 卖出信号

满足任意一项：

```text
最近两根确认日线内 Supertrend 由多翻空，且当前仍为 bearish
OR
最近两根确认日线内 EMA9 下穿 EMA26，且当前仍保持 EMA9 < EMA26、close < EMA26
```

任一事件路径满足完整条件即可触发 sell；两项同时有效时返回两个 trigger。
EMA 死叉路径额外要求收盘价跌破 EMA26，避免均线上方的短暂缠绕过早触发退出。
`signal.confirmation` 使用
最近一次有效空头事件作为两日窗口起点。卖出表示趋势转空的退出或风险预警，不表示
做空。单独 RSI 过热、持续空头或普通价格跌破不会产生卖出信号。sell 优先于 buy，
同一标的不会同时进入两个数组。

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

只有 buy 与 hold 项输出风险边界：

- `stop_loss` 优先使用位于价格下方的多头 Supertrend，否则使用 `close - 2*ATR10`。
- `trailing_stop` 在存在有效多头 Supertrend 时输出；buy 表示入场止损，hold 表示
  持有跟踪线。
- 不输出固定止盈目标、风险收益比或风险等级。
- sell 是退出信号，不生成做空目标或空头风控。

## 数据与失败语义

- `calc_score()` 默认请求 60 根 K 线；剔除未收盘日线后至少需要 30 根。
- scan 中单标的失败进入 `failures`，其他标的继续处理。
- `summary.buy + sell + watch + hold + ignored = analyzed`。
- `summary.total = analyzed + failed`。
- route 跳过扫描失败的标的，保留失败标的在目标组中的原成员，继续写入其余结果，
  并在成功响应中返回 `failures`。
- `--recent-bars N` 使用评分时已获取的数据附加最近 1–30 根紧凑日线，不二次请求。
