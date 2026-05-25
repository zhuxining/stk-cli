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
- 入选、强信号与排序
- 指标解释输出

## 目标与边界

每日监控的目标不是给每只股票做完整体检，而是回答“今天哪些标的需要重点关注”。系统默认只展开可行动的买入、退出或风险信号；无信号和中性观察标的只进入统计字段。

设计边界：

- `services/score.py` 负责单标的信号判断，输出 `ScoreResult`。
- `services/scan.py` 负责批量扫描与重点关注筛选，输出 `MonitorResult`。
- 主信号只使用日线收盘 K 线确认，不处理盘中未确认信号。
- 主信号默认由 `EMA9/EMA26 + Supertrend(ATR10 x2.5)` 决定，并补充保守确认后的反转、修复形态。
- `decision.intent` 表达处理意图，`decision.strength` 表达信号强弱，`decision.pattern` 表达形态来源；ADX 只作为趋势强度提示，不直接改变强弱。
- 辅助因子只解释主信号质量、冲突、风险或左侧机会，不生成单一综合分数。
- 风控字段独立输出，不参与主信号级别计算。
- `风险退出` 表示减仓、退出或风险预警，不表达做空建议。

## 单标的输出结构

`ScoreResult` 是单标的监控契约：

```json
{
  "symbol": "600519.SH",
  "decision": {
    "intent": "买入关注",
    "strength": "强信号",
    "pattern": "趋势共振",
    "signal_status": "new",
    "signal_date": "2026-05-12",
    "bars_since_signal": 1
  },
  "primary_signal": {
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
        "metrics": {
          "rsi14": 55,
          "rsi_zone": "neutral",
          "k": 52,
          "d": 54,
          "j": 48,
          "kdj_bias": "bearish"
        }
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
| `decision.intent` | `买入关注`、`风险退出` 或 `观察`。 |
| `decision.strength` | `强信号`、`普通信号` 或 `无信号`。 |
| `decision.pattern` | `趋势共振`、`反转确认` 或 `趋势修复`，表示信号来源。 |
| `decision.signal_status` | `new`、`active` 或 `stale`。 |
| `decision.signal_date` | 最近一次主信号触发日期。 |
| `decision.bars_since_signal` | 最近一次主信号距当前 K 线的根数。 |
| `primary_signal` | 主趋势策略的指标值和触发原因。 |
| `context` | 辅助因子、整体态度和风险提示。 |
| `context.factors[].metrics` | 辅助因子的结构化指标值，是 Agent 分析的主要依据；扫描命令默认省略 `neutral` / `none` 因子。 |
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
    "strong_signal_count": 2,
    "entry_signal_count": 4,
    "exit_signal_count": 1,
    "watch_signal_count": 0
  },
  "focus": [
    {
      "symbol": "600519.SH",
      "name": "贵州茅台",
      "decision": {},
      "primary_signal": {},
      "context": {},
      "risk": {},
      "last": 123.45,
      "change_pct": 1.23,
      "source": "longport",
      "daily10": [
        {
          "date": "2026-05-13",
          "open": 120.1,
          "high": 125.0,
          "low": 119.8,
          "close": 123.45,
          "volume": 1000000,
          "turnover": 123450000,
          "change_pct": 1.23,
          "ema9": 121.3,
          "ema26": 118.6,
          "supertrend": 116.2,
          "supertrend_direction": "bullish",
          "macd": 1.2,
          "macd_signal": 1.0,
          "macd_hist": 0.2,
          "rsi14": 56,
          "j": 70,
          "boll_position_pct": 82.4,
          "atr10": 2.34
        }
      ]
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
| `summary.strong_signal_count` | `decision.strength=强信号` 的标的数量。 |
| `summary.entry_signal_count` | `decision.intent=买入关注` 的标的数量。 |
| `summary.exit_signal_count` | `decision.intent=风险退出` 的标的数量。 |
| `summary.watch_signal_count` | `decision.intent=观察` 的标的数量；默认扫描口径下一般为 0，保留用于兼容。 |
| `focus` | 重点关注标的列表，默认只包含可行动的 `买入关注` / `风险退出`。 |
| `focus[].daily10` | 仅在扫描命令显式传入 `--daily10` 时，为强信号且辅助态度不冲突的标的补充最近 10 根压缩日线；其他标的默认不输出该字段。 |
| `ignored.no_signal_count` | 成功扫描但未进入可行动 `focus` 的标的数量。 |
| `errors` | 非致命单标的错误列表。 |

`FocusItem` 在 `ScoreResult` 基础上补充展示字段：

- `name`：行情或 watchlist 提供的名称。
- `last`：实时最新价，行情失败时为空。
- `change_pct`：实时涨跌幅，行情失败时为空。
- `source`：行情来源，行情失败时为 `unknown`。
- `daily10`：只在扫描命令显式传入 `--daily10`，且标的为强信号、辅助态度不冲突时补充，用于 Agent 复核信号发生位置、近期价格结构和指标变化。
- `context.factors`：扫描命令默认只输出 `confirming`、`conflicting`、`risk`、`opportunity` 因子，需完整辅助因子时传入 `--full-context`。

## 主信号策略

输入数据：

- `calc_score()` 默认读取最近 60 根日线 K 线。
- 少于 30 根 K 线时抛出 `IndicatorError`。
- 价格、EMA、Supertrend、ADX 和 ATR 均基于日线收盘数据计算。

主趋势信号指标：

- `EMA9`：短周期趋势线。
- `EMA26`：慢周期趋势线。
- `Supertrend(ATR10, multiplier=2.5)`：趋势方向与动态趋势线。
- `ADX14`：趋势强度参考字段，`<20` 视为趋势偏弱，`>=25` 视为趋势较强；只补充到 `primary_signal.reasons`，不参与信号级别计算。

触发事件：

- `EMA9` 从下向上穿越 `EMA26` 记为 `ema_cross=golden`。
- `EMA9` 从上向下穿越 `EMA26` 记为 `ema_cross=death`。
- Supertrend 从空头翻为多头记为 `supertrend_flip=bullish`。
- Supertrend 从多头翻为空头记为 `supertrend_flip=bearish`。
- 共振窗口固定为最近 3 根 K 线。

信号意图与强弱：

| intent | strength | 判定规则 |
|--------|----------|----------|
| `买入关注` | `强信号` | `EMA9 > EMA26`，Supertrend 多头，且最近 0-1 根 K 线内出现多头触发。 |
| `买入关注` | `普通信号` | `EMA9 > EMA26`，Supertrend 多头，且最近 2-3 根 K 线内出现多头触发。 |
| `观察` | `无信号` | 指标未形成、EMA 与 Supertrend 不一致，或趋势排列存在但最近 3 根 K 线内无新触发。 |
| `风险退出` | `普通信号` | `EMA9 < EMA26`，Supertrend 空头，且最近 2-3 根 K 线内出现空头触发。 |
| `风险退出` | `强信号` | `EMA9 < EMA26`，Supertrend 空头，且最近 0-1 根 K 线内出现空头触发。 |

信号形态：

| pattern | 判定规则 | 输出口径 |
|-------|----------|----------|
| `趋势共振` | 原 EMA9/26 + Supertrend 趋势共振。 | 顺势突破或退出信号。 |
| `反转确认` | 超买/超卖、MACD 背离或 BOLL 极端位置出现后，至少 2 个辅助因子确认同一方向。 | 底部反转关注或顶部风险退出。 |
| `趋势修复` | 趋势未破坏，价格回踩后重新收复 EMA9，或反抽后重新跌回 EMA9，并至少 2 个辅助因子确认。 | 趋势修复关注或反抽失败风险。 |

若多个形态同时命中，先按 `strength` 强弱选择，再按 `bars_since_signal` 新旧选择，最后按 `趋势共振 > 反转确认 > 趋势修复` 稳定排序。

信号状态：

| status | 判定规则 |
|--------|----------|
| `new` | `bars_since_signal <= 1`。 |
| `active` | `2 <= bars_since_signal <= 3`。 |
| `stale` | 没有触发事件，或触发事件超过 3 根 K 线。 |

## 辅助因子策略

辅助因子用于解释主信号质量，不改变 `decision.strength`。

辅助因子列表：

| factor name | 指标来源 | 输出语义 |
|-------------|----------|----------|
| `momentum` | `RSI14`、`KDJ(9,3,3)` | 动量是否支持当前方向，或是否出现超买、超卖。 |
| `macd` | `MACD(12,26,9)` | MACD 多空状态是否支持当前方向。 |
| `boll` | `BBANDS(20,2)` | 价格在布林区间中的位置，以及布林收窄预警。 |
| `volume_price` | 当前成交额、前 5 根平均成交额、当日涨跌幅 | 放量上涨、放量下跌或量价中性。 |
| `ema_trend` | `EMA5`、`EMA10`、`EMA20` | 短周期均线排列是否支持当前方向。 |
| `money_flow` | `MFI14` | 结合主方向解释资金流强弱、超买或超卖。 |
| `divergence` | 最近 20 根 K 线与 MACD histogram | MACD 顶背离、底背离或无背离。 |

辅助因子输出规则：

- `state` 是辅助因子的结论枚举，用于排序、过滤和冲突识别。
- `metrics` 是结构化指标明细，用于 Agent 分析和二次推理。

核心 `metrics` 字段：

| factor name | metrics |
|-------------|---------|
| `momentum` | `rsi14`、`rsi_zone`、`k`、`d`、`j`、`kdj_bias`。 |
| `macd` | `dif`、`dea`、`hist`、`bias`。 |
| `boll` | `upper`、`middle`、`lower`、`position_pct`、`bandwidth_pct`。 |
| `volume_price` | `volume_ratio_5d`、`price_change_pct`。 |
| `ema_trend` | `ema5`、`ema10`、`ema20`、`arrangement`。 |
| `money_flow` | `mfi14`、`mfi_zone`。 |
| `divergence` | `type`、`lookback`、`current_close`、`reference_price`、`current_hist`、`reference_hist`、`price_distance_pct`、`hist_delta`。 |

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

MFI 解释规则：

- `MFI14 < 20` 记为 `opportunity`，提示超卖或修复机会。
- `MFI14 > 80` 记为 `risk`，提示过热。
- 主方向为多头时，`MFI14 > 60` 记为 `confirming`，`MFI14 < 40` 记为 `conflicting`。
- 主方向为空头时，`MFI14 < 40` 记为 `confirming`，`MFI14 > 60` 记为 `conflicting`。
- 主方向为中性时，仅保留超买/超卖提示，其余多为 `neutral`。

## 风控策略

风控字段由 `RiskProfile` 输出：

| 字段 | 规则 |
|------|------|
| `atr` | 使用 Supertrend 同源的 `ATR10`。 |
| `stop_loss` | 多头时是下方止损线；空头或退出信号时是上方失效线。优先取方向一致的 Supertrend，否则回退为 `2 * ATR10`。 |
| `take_profit` | 多头时是上行参考目标；空头或退出信号时是下行风险参考，不表达做空建议。距离固定为 `3 * ATR10`。 |
| `risk_reward_ratio` | 多头按上行收益/下行风险计算；空头按下行空间/上方失效距离计算；仅在风险距离大于 0 时输出。 |
| `risk_level` | `risk_reward_ratio >= 2` 为 `low`，`>= 1` 为 `medium`，其余为 `high`；无法计算时为 `medium`。 |

风控字段只用于执行参考和排序后的人工复核，不参与主信号级别计算。

## 入选、强信号与排序

入选 `focus` 的规则：

- `decision.intent` 为 `买入关注` 或 `风险退出`。
- `decision.strength` 为 `强信号` 或 `普通信号`，且 `signal_status` 为 `new` 或 `active`。
- `decision.strength=无信号` 或 `decision.intent=观察` 默认不进入 `focus`。
- `signal_status=stale` 的买卖信号默认不进入 `focus`。
- 扫描失败的标的不进入 `focus`，只进入 `errors`。
- 默认扫描结果省略空值字段，并从 `context.factors` 中省略 `neutral` / `none` 因子；完整上下文用 `--full-context`。

强信号规则：

- `强信号` 计入 `summary.strong_signal_count`。
- 显式传入 `--daily10`，且强信号、`context.overall_bias != conflicting` 时补充 `daily10`，用于复核最近价格结构。

排序规则：

1. `decision.strength`：`强信号` 优先，其次 `普通信号`，最后 `无信号`。
2. `context.overall_bias`：`supportive`、`mixed`、`risky`、`conflicting`。
3. `decision.bars_since_signal`：信号越新越靠前；空值按最老处理。

## 指标解释输出

`stk stock kline` 与 `stk watchlist kline` 输出 `DailyResult.days`，用于解释扫描信号来源。

日线指标包含：

- OHLCV：`open`、`high`、`low`、`close`、`volume`、`turnover`、`change_pct`。
- EMA：`EMA5`、`EMA9`、`EMA10`、`EMA20`、`EMA26`、`EMA60`。
- 趋势与波动：`Supertrend`、`SupertrendDirection`、`ATR10`、`ATR14`。
- 其他技术指标：`MACD`、`signal`、`hist`、`RSI`、`K`、`D`、`J`、`upper`、`middle`、`lower`。

K 线指标服务只提供解释数据，不负责判断重点关注列表。

`MonitorResult.focus[].daily10` 需要扫描命令显式传入 `--daily10`。它使用 `DailyResult.days` 的压缩子集，仅包含 OHLCV、`change_pct`、`EMA9`、`EMA26`、Supertrend、MACD、RSI14、J 值、BOLL 区间位置和 `ATR10`。完整指标解释仍通过 `stk stock kline` 或 `stk watchlist kline` 获取。
