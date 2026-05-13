# 信号策略设计

> **Status**: `active`

本文档记录 `stk-cli` 当前生效的每日监控信号机制。核心使用场景是自动化监控 100 个以上股票，并从中筛出今天需要重点关注的标的。

## 目录

- 目标与边界
- 单标的输出结构
- 批量监控输出结构
- 主信号策略
- 辅助因子策略
- 风控策略
- 入选、优先级与排序
- 指标解释输出

## 目标与边界

每日监控的目标不是给每只股票做完整体检，而是回答“今天哪些标的需要重点关注”。系统默认只展开有效信号、风险预警或左侧机会标的；无信号标的只进入统计字段。

设计边界：

- `services/score.py` 负责单标的信号判断，输出 `ScoreResult`。
- `services/scan.py` 负责批量扫描与重点关注筛选，输出 `MonitorResult`。
- 主信号只使用日线收盘 K 线确认，不处理盘中未确认信号。
- 主信号由 `EMA9/EMA26 + Supertrend(ATR10 x2.5)` 决定。
- `decision.confidence` 只表示主信号置信度，取值范围为 `0-100`。
- 辅助因子只解释主信号质量、冲突、风险或左侧机会，不生成单一综合分数。
- 风控字段独立输出，不参与主信号置信度计算。
- `sell` 与 `strong_sell` 表示减仓、退出或风险预警，不表达做空建议。

## 单标的输出结构

`ScoreResult` 是单标的监控契约：

```json
{
  "symbol": "600519.SH",
  "decision": {
    "action": "focus_buy",
    "level": "strong_buy",
    "direction": "bullish",
    "confidence": 92,
    "signal_status": "new",
    "signal_date": "2026-05-12",
    "bars_since_signal": 1,
    "summary": "EMA9/26 金叉与 Supertrend 多头强共振"
  },
  "primary_signal": {
    "strategy": "ema_supertrend",
    "ema_cross": "golden",
    "ema9": 123.45,
    "ema26": 120.12,
    "supertrend": 118.8,
    "supertrend_direction": "bullish",
    "adx": 28.4,
    "reasons": [
      "EMA9 位于 EMA26 上方",
      "Supertrend 当前为多头",
      "EMA 金叉发生在1根K线前"
    ]
  },
  "context": {
    "overall_bias": "supportive",
    "factors": [
      {
        "name": "momentum",
        "state": "neutral",
        "score": 42,
        "signals": ["RSI=55", "J=48"]
      }
    ],
    "warnings": ["布林收窄 (带宽4.8%)"]
  },
  "risk": {
    "atr": 2.34,
    "stop_loss": 118.8,
    "take_profit": 130.2,
    "risk_reward_ratio": 2.1,
    "risk_level": "low"
  }
}
```

字段语义：

| 字段 | 语义 |
|------|------|
| `symbol` | Longport symbol。 |
| `decision` | 面向每日监控的可执行判断。 |
| `decision.action` | `focus_buy`、`focus_sell` 或 `watch`。 |
| `decision.level` | `strong_buy`、`buy`、`hold`、`sell` 或 `strong_sell`。 |
| `decision.direction` | `bullish`、`bearish` 或 `neutral`。 |
| `decision.confidence` | 主信号置信度，只由 EMA9/26 与 Supertrend 决定。 |
| `decision.signal_status` | `new`、`active` 或 `stale`。 |
| `decision.signal_date` | 最近一次主信号触发日期。 |
| `decision.bars_since_signal` | 最近一次主信号距当前 K 线的根数。 |
| `primary_signal` | 主趋势策略的指标值和触发原因。 |
| `context` | 辅助因子、整体态度和风险提示。 |
| `risk` | ATR、止损、止盈、风险收益比和风险等级。 |

## 批量监控输出结构

`MonitorResult` 是每日批量扫描契约：

```json
{
  "run_date": "2026-05-13",
  "universe": {
    "name": "core-watchlist",
    "total": 128,
    "scanned": 126,
    "failed": 2
  },
  "summary": {
    "focus_count": 6,
    "high_priority_count": 2,
    "entry_signal_count": 4,
    "exit_signal_count": 1,
    "watch_signal_count": 1
  },
  "focus": [
    {
      "symbol": "600519.SH",
      "name": "贵州茅台",
      "priority": "high",
      "decision": {},
      "primary_signal": {},
      "context": {},
      "risk": {},
      "last": 123.45,
      "change_pct": 1.23,
      "source": "longport"
    }
  ],
  "ignored": {
    "no_signal_count": 120
  },
  "errors": [
    {
      "symbol": "000001.SZ",
      "reason": "Insufficient history for 000001.SZ"
    }
  ]
}
```

字段语义：

| 字段 | 语义 |
|------|------|
| `run_date` | 本次监控运行日期，使用 Asia/Shanghai 日期。 |
| `universe.name` | 股票池名称，watchlist 使用分组名，临时扫描使用 `ad-hoc`。 |
| `universe.total` | 请求扫描的标的总数。 |
| `universe.scanned` | 成功生成 `ScoreResult` 的标的数量。 |
| `universe.failed` | 单标的信号计算失败数量。 |
| `summary.focus_count` | 入选 `focus` 的标的数量。 |
| `summary.high_priority_count` | `priority=high` 的标的数量。 |
| `summary.entry_signal_count` | `decision.action=focus_buy` 的标的数量。 |
| `summary.exit_signal_count` | `decision.action=focus_sell` 的标的数量。 |
| `summary.watch_signal_count` | `decision.action=watch` 的标的数量。 |
| `focus` | 重点关注标的列表，默认不包含无信号标的。 |
| `ignored.no_signal_count` | 成功扫描但未进入 `focus` 的标的数量。 |
| `errors` | 非致命单标的错误列表。 |

`FocusItem` 在 `ScoreResult` 基础上补充展示字段：

- `name`：行情或 watchlist 提供的名称。
- `priority`：`high`、`medium` 或 `low`。
- `last`：实时最新价，行情失败时为空。
- `change_pct`：实时涨跌幅，行情失败时为空。
- `source`：行情来源，行情失败时为 `unknown`。

## 主信号策略

输入数据：

- `calc_score()` 默认读取最近 60 根日线 K 线。
- 少于 30 根 K 线时抛出 `IndicatorError`。
- 价格、EMA、Supertrend、ADX 和 ATR 均基于日线收盘数据计算。

主信号指标：

- `EMA9`：短周期趋势线。
- `EMA26`：慢周期趋势线。
- `Supertrend(ATR10, multiplier=2.5)`：趋势方向与动态趋势线。
- `ADX14`：趋势强度参考字段，只输出，不参与信号级别计算。

触发事件：

- `EMA9` 从下向上穿越 `EMA26` 记为 `ema_cross=golden`。
- `EMA9` 从上向下穿越 `EMA26` 记为 `ema_cross=death`。
- Supertrend 从空头翻为多头记为 `supertrend_flip=bullish`。
- Supertrend 从多头翻为空头记为 `supertrend_flip=bearish`。
- 共振窗口固定为最近 3 根 K 线。

信号级别：

| level | 判定规则 | action | direction | confidence |
|-------|----------|--------|-----------|------------|
| `strong_buy` | `EMA9 > EMA26`，Supertrend 多头，且最近 0-1 根 K 线内出现多头触发 | `focus_buy` | `bullish` | `92` |
| `buy` | `EMA9 > EMA26`，Supertrend 多头，且最近 2-3 根 K 线内出现多头触发 | `focus_buy` | `bullish` | `76` |
| `hold` | 指标未形成、EMA 与 Supertrend 不一致，或趋势排列存在但最近 3 根 K 线内无新触发 | `watch` | `neutral`、`bullish` 或 `bearish` | `25`、`35` 或 `48` |
| `sell` | `EMA9 < EMA26`，Supertrend 空头，且最近 2-3 根 K 线内出现空头触发 | `focus_sell` | `bearish` | `76` |
| `strong_sell` | `EMA9 < EMA26`，Supertrend 空头，且最近 0-1 根 K 线内出现空头触发 | `focus_sell` | `bearish` | `92` |

信号状态：

| status | 判定规则 |
|--------|----------|
| `new` | `bars_since_signal <= 1`。 |
| `active` | `2 <= bars_since_signal <= 3`。 |
| `stale` | 没有触发事件，或触发事件超过 3 根 K 线。 |

## 辅助因子策略

辅助因子用于解释主信号质量，不改变 `decision.level` 和 `decision.confidence`。

辅助因子列表：

| factor name | 指标来源 | 输出语义 |
|-------------|----------|----------|
| `momentum` | `RSI14`、`KDJ(9,3,3)` | 动量是否支持当前方向，或是否出现超买、超卖。 |
| `macd` | `MACD(12,26,9)` | MACD 多空状态是否支持当前方向。 |
| `boll` | `BBANDS(20,2)` | 价格在布林区间中的位置，以及布林收窄预警。 |
| `volume_price` | 当前成交额、前 5 根平均成交额、当日涨跌幅 | 放量上涨、放量下跌或量价中性。 |
| `ema_trend` | `EMA5`、`EMA10`、`EMA20` | 短周期均线排列是否支持当前方向。 |
| `money_flow` | `MFI14` | 资金流强弱、超买或超卖。 |
| `divergence` | 最近 20 根 K 线与 MACD histogram | MACD 顶背离、底背离或无背离。 |

辅助因子状态：

| state | 语义 |
|-------|------|
| `confirming` | 支持主信号方向。 |
| `neutral` | 未提供明确支持或反对。 |
| `conflicting` | 与主信号方向冲突。 |
| `risk` | 提供风险提示，但不直接改变主方向。 |
| `opportunity` | 提示左侧关注机会，不直接升级为买入信号。 |
| `none` | 未检测到该类有效信号。 |

整体态度 `context.overall_bias`：

| bias | 判定规则 |
|------|----------|
| `conflicting` | `conflicting` 因子数量不少于 2，或多于 `confirming` 因子数量。 |
| `risky` | `risk` 因子数量不少于 2；或没有触发前一条规则但存在至少 1 个 `risk` 因子。 |
| `supportive` | `confirming` 因子数量不少于 2，且没有 `conflicting` 因子。 |
| `mixed` | 不满足以上条件。 |

`context.warnings` 只承载不直接改变主方向的提示。当前实现会在布林带宽占中轨比例低于 5% 时输出布林收窄预警。

## 风控策略

风控字段由 `RiskProfile` 输出：

| 字段 | 规则 |
|------|------|
| `atr` | 使用 Supertrend 同源的 `ATR10`。 |
| `stop_loss` | 多头且 Supertrend 线低于当前价格时，优先取 Supertrend 线；其他场景回退为 `current_price - ATR10 * 2`。 |
| `take_profit` | `current_price + ATR10 * 3`。 |
| `risk_reward_ratio` | `(take_profit - current_price) / (current_price - stop_loss)`，仅在风险距离大于 0 时输出。 |
| `risk_level` | `risk_reward_ratio >= 2` 为 `low`，`>= 1` 为 `medium`，其余为 `high`；无法计算时为 `medium`。 |

风控字段只用于执行参考和排序后的人工复核，不参与主信号级别计算。

## 入选、优先级与排序

入选 `focus` 的规则：

- `decision.level` 为 `strong_buy`、`buy`、`sell` 或 `strong_sell`，且 `signal_status` 为 `new` 或 `active`。
- `decision.level=hold` 时，只有 `context.factors` 中存在 `risk` 或 `opportunity`，或 `context.warnings` 非空，才进入 `focus`。
- `signal_status=stale` 的买卖方向标的默认不进入 `focus`。
- 扫描失败的标的不进入 `focus`，只进入 `errors`。

优先级规则：

| priority | 判定规则 |
|----------|----------|
| `high` | `strong_buy` 或 `strong_sell`，且 `context.overall_bias != conflicting`。 |
| `medium` | `buy`、`sell`、`strong_buy` 或 `strong_sell`，但未满足 `high`。 |
| `low` | `hold` 且因风险、机会或预警进入 `focus`。 |

排序规则：

1. `priority`：`high` 优先，其次 `medium`、`low`。
2. `context.overall_bias`：`supportive`、`mixed`、`risky`、`conflicting`。
3. `decision.confidence`：置信度高的优先。
4. `decision.bars_since_signal`：信号越新越靠前；空值按最老处理。

## 指标解释输出

`stk stock kline` 与 `stk watchlist kline` 输出 `DailyResult.days`，用于解释扫描信号来源。

日线指标包含：

- OHLCV：`open`、`high`、`low`、`close`、`volume`、`turnover`、`change_pct`。
- EMA：`EMA5`、`EMA9`、`EMA10`、`EMA20`、`EMA26`、`EMA60`。
- 趋势与波动：`Supertrend`、`SupertrendDirection`、`ATR14`。
- 其他技术指标：`MACD`、`signal`、`hist`、`RSI`、`K`、`D`、`J`、`upper`、`middle`、`lower`。

K 线指标服务只提供解释数据，不负责判断重点关注列表。
