# Data 命令

```bash
stk data kline <symbols...> [--period day|week|month] [--count N]
```

返回 `DailyResult[]`。每个标的包含倒序排列的 `days`，每根 K 线合并：

- OHLCV 与 `change_pct`
- EMA5/9/10/20/26/60
- MACD、RSI、BOLL
- KDJ9、WR（WR14）、ATR10/14、Supertrend（stockstats）

symbols 支持空格或逗号分隔。A 股纯数字会自动转换为 Longport symbol。
