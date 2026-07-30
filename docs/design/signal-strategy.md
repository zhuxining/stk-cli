# 信号规则

> Status: active

本文档是 `stk-cli` 信号阈值、优先级和时间语义的唯一事实来源。命令用法见 README 和
Agent Skill；公开字段的最终结构以 Pydantic 模型为准。

## 目标与边界

每日扫描从 Longport 分组中筛选当前具有操作意义的买入或卖出信号，而不是输出所有
多头或空头趋势。`routing` 是 scan 和 route 的主判定；`decision` 保留为事件解释，
两者互不替代。

- 所有判断只使用已确认的完整日线。
- `calc_score()` 默认请求 60 根 K 线；剔除未收盘日线后至少需要 30 根。
- `last`、`change_pct` 和 `source` 是实时展示字段，不参与信号计算。
- 卖出表示退出或风险预警，不表示做空建议。
- 系统不生成单一综合分数。

## 两种信号语义

`decision` 描述兼容保留的事件型信号：

- EMA9/EMA26 交叉与 Supertrend 翻转是否发生。
- `signal_date` 和 `bars_since_signal` 描述事件时间。
- `signal_status` 为 `new`、`active` 或 `stale`。

`routing` 描述当前可行动状态：

- `entry_eligible` 决定是否进入 scan 的 `focus` 和 route 的买入组。
- `exit_trigger` 决定是否进入 scan 的 `risk` 和 route 的卖出组。
- `entry_patterns` 解释买入资格命中了哪些路径。
- `reasons` 解释入选、拒绝或风险原因。

route 成员资格只由 `routing` 决定，不要求 `decision` 为推荐、预警或今天刚触发。

## 买入信号

### 基线

必须全部满足：

```text
EMA9 > EMA26
AND Supertrend bullish
AND close >= EMA26
AND RSI14 < 75
AND close <= EMA9 + 1.5 * ATR10
```

基线保证趋势一致、价格结构未破坏，同时排除过热和明显追高。

### 入选路径

满足基线后，至少命中一项：

| `entry_patterns` | 判定 |
|---|---|
| `healthy_continuation` | `close >= EMA9` 且 `45 <= RSI14 < 70` |
| `pullback_hold` | `EMA26 <= close <= EMA9`、`RSI14 >= 40`，且收盘价高于前一日收盘价 |
| `momentum_recovery` | 最近 3 根已确认日线内 RSI14 从下向上穿越 50，当前仍不低于 50 |
| `trend_start` | 最近 3 根已确认日线内 Supertrend 翻多，当前仍为多头 |

成交额量比只用于质量解释，不作为买入硬门槛。

## 卖出信号

满足任意一项：

```text
Supertrend bearish
OR 连续 2 根收盘价低于各自 EMA26
OR 前一日 RSI14 >= 75
   AND 今日 RSI14 < 前一日 RSI14
   AND 今日 close < EMA9
```

卖出信号优先于买入信号。同一标的即使命中宽松买入路径，只要卖出条件成立，就只进入
卖出组。

`overheated` 仅表示当前 `RSI14 >= 75`。单独过热不会触发卖出；过热回落路径要求
前一日 RSI14 不低于 75、今日 RSI14 下降且跌破 EMA9，但不要求今日 RSI14 已跌出
过热区。

## 修复观察

以下条件同时成立时标记 `recovery`，但不直接进入买入组：

```text
RSI14 从超卖区上穿 30
AND MACD histogram 从非正转为正
AND close > EMA5
```

趋势条件部分成立或出现修复迹象时，`routing.state` 为 `watch`；指标不足时为
`ignored`。

## 事件型主信号

事件型 `decision` 继续用于解释，不决定 route。事件窗口按
`bars_since_signal <= 2` 计算，即当前 K 线加此前 2 根，共最近 3 根已确认 K 线。

- 趋势买入：EMA9 高于 EMA26、Supertrend 多头、收盘价高于 EMA9，并且 EMA 金叉
  与 Supertrend 翻多都发生在事件窗口内。两项必须共振，事件年龄取两者中较大的值。
- 趋势退出：EMA9 低于 EMA26、Supertrend 空头、收盘价低于 EMA9，并且 EMA 死叉
  或 Supertrend 翻空至少一项发生在事件窗口内。事件年龄取已有事件中较小的值。
- 超卖修复：按多头辅助上下文计算，要求 `RSI14 <= 30`、MACD histogram 大于 0、
  `close > EMA5`，且 `context.overall_bias` 不是 `mixed` 或 `conflicting`。该事件固定
  发生在当前 K 线。
- 其他情况为观察。

事件型推荐还会经过质量过滤：

- `context.overall_bias=conflicting` 时降为观察。
- 多头事件的风险收益比缺失或低于 1.2 时降为观察。
- ADX 只追加趋势强弱原因，不改变信号强度。
- 金叉缩量或价格仍低于 EMA60 只追加提示，不改变信号强度。

事件年龄：

- `new`：`bars_since_signal <= 1`
- `active`：`bars_since_signal = 2`
- `stale`：`bars_since_signal` 为空

候选信号按 `推荐`、`预警`、观察的顺序选择；强度相同时选择事件年龄更小的信号。
质量过滤只会移除强度，不会清除已有的事件年龄，因此被降为观察的 decision 仍可能是
`new` 或 `active`。

## 辅助因子

| 因子 | 指标 | 作用 |
|---|---|---|
| `momentum` | RSI14、KDJ9 | 动量、超买和超卖解释 |
| `macd` | MACD(12,26,9) | 趋势动量确认 |
| `boll` | BOLL(20,2) | 价格位置和波动收窄 |
| `volume_price` | 5 日成交额量比、涨跌幅 | 量价质量 |
| `ema_trend` | EMA5/10/20 | 短周期排列 |
| `money_flow` | MFI14 | 资金流强弱 |
| `divergence` | 价格与 MACD histogram | 顶底背离 |

因子状态：

- `confirming`：支持当前方向。
- `conflicting`：与当前方向冲突。
- `risk`：风险提示。
- `opportunity`：左侧机会，不升级为买入信号。
- `neutral` / `none`：无明确判断，scan 默认省略。

`context.overall_bias` 按确认、冲突和风险因子数量归类为 `supportive`、`mixed`、
`conflicting` 或 `risky`。routing 只读取其中的 RSI14 和 5 日成交额量比，不使用
`overall_bias` 作为硬门槛；事件型 decision 则可能因冲突态度被降为观察。

## 风控

- ATR 使用与 Supertrend 同源的 ATR10。
- 选中信号方向不是 `neutral` 时计算价格边界，即使其强度已降为观察；方向为
  `neutral` 时只输出 ATR。
- 止损优先采用方向一致、位于价格正确一侧且不超过 2 倍 ATR10 的 Supertrend，
  否则回退为 2 倍 ATR10。
- `target_1` 和 `target_2` 分别使用 2 倍和 3 倍 ATR10。
- `trailing_stop` 输出当前 Supertrend。
- 风险收益比不参与每日 routing 成员资格。
- `take_profit` 作为 `target_2` 的兼容字段保留。

## Scan 与 Route

- scan 的 `focus` 展开 `entry_eligible=true` 的标的。
- scan 的 `risk` 展开 `exit_trigger=true` 的标的。
- 买入和卖出列表分别按 `supportive`、`mixed`、`risky`、`conflicting` 排序，
  同一辅助态度内 5 日成交额量比高的优先。
- 普通 scan 将单标的失败写入 `errors`，其余标的继续处理。
- route 默认 replace 两个目标组；任何扫描失败都会在首次写入前中止。
- route 的源组、买入组和卖出组必须互不相同。
