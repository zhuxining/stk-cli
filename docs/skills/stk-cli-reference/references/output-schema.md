# 输出结构详解

## MonitorResult（`stk stock scan` / `stk watchlist scan`）

顶层结构：

| 字段       | 说明                                                                                                  |
| ---------- | ----------------------------------------------------------------------------------------------------- |
| `run_date` | 运行日期                                                                                              |
| `universe` | `name`、`total`、`scanned`、`failed`                                                                  |
| `summary`  | `focus_count`、`strong_signal_count`、`entry_signal_count`、`exit_signal_count`、`watch_signal_count` |
| `focus[]`  | 重点关注标的                                                                                          |
| `ignored`  | `no_signal_count`                                                                                     |
| `errors[]` | 单标的非致命错误                                                                                      |

### FocusItem

| 分组             | 字段                                                                                                                                                         |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 展示             | `symbol`、`name`、`last`、`change_pct`、`source`                                                                                                             |
| `decision`       | `signal`（`趋势买入` / `趋势退出` / `超卖修复` / `观察`）、`strength`（`强信号` / `普通信号` / `观察`）、`signal_status`、`signal_date`、`bars_since_signal` |
| `primary_signal` | `ema_cross`、`ema9`、`ema26`、`supertrend`、`supertrend_direction`、`adx`、`reasons`                                                                         |
| `context`        | `overall_bias`、`factors[]`、`warnings[]`                                                                                                                    |
| `risk`           | `atr`、`stop_loss`、`take_profit`、`risk_reward_ratio`、`risk_level`                                                                                         |
| `daily10`        | 仅 `--daily10` 且强信号、辅助不冲突时出现                                                                                                                    |

### context.factors[]

| factor         | 主要 metrics                                                | 用途               |
| -------------- | ----------------------------------------------------------- | ------------------ |
| `momentum`     | `rsi14`、`rsi_zone`、`k`、`d`、`j`、`kdj_bias`              | 动量支持与过热判断 |
| `macd`         | `dif`、`dea`、`hist`、`bias`                                | MACD 多空状态      |
| `boll`         | `upper`、`middle`、`lower`、`position_pct`、`bandwidth_pct` | 价格位置与波动收敛 |
| `volume_price` | `volume_ratio_5d`、`price_change_pct`                       | 量能确认           |
| `ema_trend`    | `ema5`、`ema10`、`ema20`、`arrangement`                     | 短周期均线排列     |
| `money_flow`   | `mfi14`、`mfi_zone`                                         | 资金流强弱         |
| `divergence`   | `type`、`lookback`、`price_distance_pct`、`hist_delta`      | MACD 顶/底背离提示 |

### daily10 字段（需 `--daily10`）

| 分类     | 字段                                                                           |
| -------- | ------------------------------------------------------------------------------ |
| 价格量能 | `date`、`open`、`high`、`low`、`close`、`volume`、`turnover`、`change_pct`     |
| 主信号   | `ema9`、`ema26`、`supertrend`、`supertrend_direction`                          |
| 辅助指标 | `macd`、`macd_signal`、`macd_hist`、`rsi14`、`j`、`boll_position_pct`、`atr10` |

---

## LiveScanResult（`stk stock scan-live` / `stk watchlist scan-live`）

顶层结构：

| 字段        | 说明                                                                               |
| ----------- | ---------------------------------------------------------------------------------- |
| `mode`      | 固定 `live`                                                                        |
| `as_of`     | 扫描时间                                                                           |
| `timeframe` | K 线周期（`5m` / `15m`）                                                           |
| `summary`   | `focus_count`、`follow_count`、`weaken_count`、`overheated_count`、`observe_count` |
| `focus[]`   | 盘中触发提醒标的                                                                   |
| `ignored`   | `no_live_signal_count`                                                             |
| `errors[]`  | 单标的非致命错误                                                                   |

### LiveFocusItem

| 字段             | 说明                                 |
| ---------------- | ------------------------------------ |
| `daily_signal`   | 日线信号                             |
| `daily_strength` | 日线强度                             |
| `live_signal`    | `实时跟随` / `实时转弱` / `实时过热` |
| `strength`       | `强提醒` / `普通提醒`                |
| `trigger`        | 触发原因                             |
| `risk_line`      | 分钟触发失效线或观察线               |
| `volume_ratio`   | 最新分钟 K 成交额相对均值            |
| `vwap`           | 成交量加权均价                       |
| `ema20`          | 分钟 EMA20                           |
| `rsi14`          | 分钟 RSI14                           |
