# 信号规则

> Status: active

本文档是当前买卖信号阈值、优先级和时间语义的唯一事实来源。系统只维护一套
`StockAssessment`，不再计算事件型推荐、预警或兼容评分。

## 目标与状态

每日扫描从 Longport 分组中筛选当前具有操作意义的信号，而不是输出所有趋势标的。
所有判断只使用已确认日线；实时 quote 只用于展示。

每只成功分析的标的恰好属于一种状态：

- `buy`：最近三根确认日线内发生多头反转，当前结构同向且通过买入过滤。
- `sell`：最近三根确认日线内至少一个趋势指标转空，且该指标当前仍为空头。
- `watch`：EMA 与 Supertrend 尚未同向，或近期多头反转未通过买入过滤。
- `ignored`：趋势已经持续超过信号窗口，或未形成需要关注的反转。

scan 只展开 buy 和 sell；watch 与 ignored 只进入汇总计数。route 直接使用这两个数组
刷新目标分组。

## 反转事件与有效期

系统只识别四种事件：

| trigger code | 事件 |
|---|---|
| `supertrend_bullish_reversal` | Supertrend 由空翻多 |
| `ema_bullish_crossover` | EMA9 上穿 EMA26 |
| `supertrend_bearish_reversal` | Supertrend 由多翻空 |
| `ema_bearish_crossover` | EMA9 下穿 EMA26 |

buy 的两个同向事件必须相隔不超过 2 根确认日线。第二个事件发生时完成反转确认，并
输出 `signal.confirmation.confirmed_at`；确认当日的 `age_bars=0`，随后两根确认
日线为 1 和 2，从 3 开始失效。有效期内若当前方向反转，原信号立即失效。

`signal.triggers[]` 保留两个组成事件各自的 `code`、`occurred_at` 和相对当前的
`age_bars`。由于第一个事件最多早于确认事件两根日线，当确认信号处于最后一个有效日
时，第一个事件的 `age_bars` 最大可以是 4。

## 买入信号

必须同时满足：

```text
EMA9 > EMA26
AND Supertrend bullish
AND Supertrend 翻多与 EMA9 上穿 EMA26 相隔不超过 2 根确认日线
AND 双指标确认发生在最近三根确认日线内
AND close >= EMA26
AND RSI14 < 75
AND close <= EMA9 + 1.5 * ATR10
```

第一个多头事件只形成 setup，归入 watch；第二个事件完成确认后才进入 buy。若完成
确认时价格已经过热、跌破 EMA26 或高于追价上限，仍归入 watch。成交额量比只解释
量能，不作为买入硬门槛。

## 卖出信号

满足任意一项：

```text
最近三根确认日线内 Supertrend 由多翻空，且当前仍为 bearish
OR
最近三根确认日线内 EMA9 下穿 EMA26，且当前仍保持 EMA9 < EMA26
```

任一事件即可触发 sell；两项同时有效时返回两个 trigger。`signal.confirmation` 使用
最近一次有效空头事件作为三日窗口起点。卖出表示趋势转空的退出或风险预警，不表示
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
