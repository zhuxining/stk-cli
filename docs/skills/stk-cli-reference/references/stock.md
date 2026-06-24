# Stock 命令参考

**何时读取**：用户要扫描个股技术信号（日线/实盘）、看 K 线和指标、或做同业对比分析时读取此文件。

## 适用场景

- 对指定标的做日线级别技术扫描：`stk stock scan`
- 盘中实时监控触发提醒：`stk stock scan-live`（仅盘中有效）
- 查看完整 K 线和技术指标数据：`stk stock kline`
- 同业对比（估值、成长性、杜邦分析）：`stk stock comparison`

---

## `stk stock scan <symbols...>`

个股每日监控扫描，是核心分析命令。扫描每只标的的技术信号（EMA 交叉、Supertrend、ADX）和辅助因子（动量、MACD、布林带、量价、资金流、背离），给出 `decision.signal` 和 `strength`。

```bash
stk stock scan 600519 000001 700.HK
stk stock scan 600519 --daily10
stk stock scan 600519 --full-context
```

| 参数 | 默认 | 说明 |
|------|------|------|
| `<symbols>` | 必填 | 标的代码列表（空格分隔）。A 股用纯数字（`600519`），港股加 `.HK`，美股直接代码 |
| `--daily10` | `false` | 推荐/预警信号标的补充最近 10 根日线数据。需要验证信号质量时开启 |
| `--full-context` | `false` | 输出完整辅助因子（含 `neutral`/`none`）。深度复盘时开启，日常扫描不必 |

选型指导：
- 日常快速扫描：不加任何 flag，只看 `focus[]` 中的推荐/预警
- 需要复核信号：加 `--daily10`，查看 `daily10` 中的 K 线序列和指标变化
- 全面复盘/调试：加 `--full-context`，看每一个辅助因子的完整态度

返回字段详见 `references/output-schema.md`（`MonitorResult`、`FocusItem`）。
信号解读详见 `references/signal-strategy.md`。

**示例**：

```bash
stk stock scan 600519
```

输出摘要：
```json
{
  "ok": true,
  "data": {
    "run_date": "2026-01-15",
    "universe": {"name": "custom", "total": 1, "scanned": 1, "failed": 0},
    "summary": {"focus_count": 1, "recommend_count": 1, "entry_signal_count": 1},
    "focus": [
      {
        "symbol": "600519.SH",
        "name": "贵州茅台",
        "last": 1680.00,
        "change_pct": 1.23,
        "decision": {"signal": "趋势买入", "strength": "推荐", "signal_status": "active", "signal_date": "2026-01-15", "bars_since_signal": 0},
        "primary_signal": {"ema_cross": "golden", "ema9": 1650.00, "ema26": 1630.00, "supertrend": 1620.00, "supertrend_direction": "up", "adx": 28, "reasons": []},
        "context": {"overall_bias": "supportive", "factors": [...], "warnings": []},
        "risk": {"atr": 25.00, "stop_loss": 1595.00, "take_profit": 1730.00, "target_1": 1730.00, "target_2": 1755.00, "trailing_stop": 1620.00, "risk_reward_ratio": 2.0, "risk_level": "medium"}
      }
    ],
    "ignored": {"no_signal_count": 0},
    "errors": []
  }
}
```

---

## `stk stock scan-live <symbols...>`

实盘提醒扫描。先做日线过滤，再用已完成 5m/15m K 线判断盘中触发。不改写日线 `decision`，仅提供独立提醒。

> **重要**：只在盘中有效。盘前/盘后日线数据不完整，信号会沿用上一交易日。

```bash
stk stock scan-live 600519 300750
stk stock scan-live 600519 --timeframe 5m
```

| 参数 | 默认 | 说明 |
|------|------|------|
| `<symbols>` | 必填 | 标的代码列表 |
| `--timeframe` `-t` | `15m` | `5m`：信号更多、噪声更大，适合活跃标的；`15m`：信号更少、质量更高，适合稳健监控 |
| `--count` `-c` | `80` | 分钟 K 线根数，越大消耗越多 |

`LiveScanResult` 返回字段详见 `references/output-schema.md`。

**示例**：

```bash
stk stock scan-live 300750 --timeframe 5m
```

输出摘要：
```json
{
  "ok": true,
  "data": {
    "mode": "live",
    "as_of": "2026-01-15T10:30:00",
    "timeframe": "5m",
    "focus": [
      {
        "symbol": "300750.SZ",
        "daily_signal": "趋势买入",
        "daily_strength": "推荐",
        "live_signal": "实时跟随",
        "strength": "强提醒",
        "trigger": "分钟收盘站上 VWAP 和 EMA20",
        "risk_line": 208.50,
        "vwap": 209.30,
        "ema20": 208.80,
        "rsi14": 62
      }
    ]
  }
}
```

---

## `stk stock kline <symbols...>`

K 线 + 全部技术指标。适合画图、手动复核或导出数据。

| 参数 | 默认 | 说明 |
|------|------|------|
| `<symbols>` | 必填 | 标的代码列表 |
| `--type` `-t` | `stock` | `stock`：个股；`index`：指数。指数不需要 Supertrend 等部分指标 |
| `--period` `-p` | `day` | `day`：短线分析；`week`：中期趋势确认；`month`：长周期趋势 |
| `--count` `-c` | `20` | K 线数量。趋势分析建议 60-120 根，短线信号看 20 根即可 |

返回 `DailyResult[]`，每根 K 线含 OHLCV + 全部指标：
`EMA5/9/10/20/26/60`、`MACD/signal/hist`、`RSI`、`K/D/J`（KDJ）、`upper/middle/lower`（BOLL）、`ATR10/ATR14`、`Supertrend/SupertrendDirection`。

**示例**：

```bash
# 日线
stk stock kline 600519

# 周线趋势确认
stk stock kline 600519 --period week --count 60
```

---

## `stk stock comparison <symbol>`

同业业绩对比。将标的与同行业公司做估值、成长性、杜邦 ROE 分解对比。

| 参数 | 默认 | 说明 |
|------|------|------|
| `<symbol>` | 必填 | 单个标的代码 |
| `--type` `-t` | `all` | `all`：全面对比；`growth`：营收/利润增长率；`valuation`：PE/PB/PS 估值水平；`dupont`：ROE 杜邦分解（仅 A 股） |

选型指导：
- 快速了解标的在同业中的位置 → `all`
- 评估成长股是否增速匹配估值 → `growth` + `valuation` 配合使用
- 深入理解 ROE 来源（杠杆/周转/利润率）→ `dupont`

**示例**：

```bash
stk stock comparison 600519
stk stock comparison 600519 --type valuation
```

返回 `FullComparison` 或 `IndustryComparison`。
