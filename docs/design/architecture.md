# stk-cli 架构

> Status: active

`stk-cli` 是面向 Agent 的单进程 CLI，聚焦数据指标、分组同步和分组信号扫描。

## 边界

```text
CLI runtime
  ├── data command  ──> history ──> indicator
  ├── scan command  ──> watchlist ──> score/scan ──> quote
  └── group command
        ├── longport ──> watchlist
        ├── ths ───────> ths_wrapper
        ├── sync ──────> sync ──> watchlist/ths_wrapper
        └── route ─────> scan ──> watchlist
```

- `commands/` 仅解析参数、调用服务和渲染结果。
- `services/` 负责外部 API、指标、评分、扫描和同步编排，不写 stdout。
- `models/` 是服务与 JSON 输出之间的数据契约。
- `store/` 只保存缓存和 Longport 分组名称到 ID 的映射。
- `output.py` 统一输出 `ok/data/error/meta` envelope。

## 核心数据流

### K 线指标

```text
stk data kline
  -> normalize symbols
  -> Longport candlesticks
  -> pandas DataFrame
  -> ta-lib + stockstats indicators
  -> DailyResult[]
```

支持日、周、月 K 线。输出合并 OHLCV、EMA、MACD、RSI、WR、KDJ、BOLL、ATR 和
Supertrend。KDJ、WR、ATR 与 Supertrend 使用 stockstats，其他技术指标使用 ta-lib。

### 分组扫描

```text
stk scan <longport-group>
  -> fetch Longport group
  -> fetch closed daily candles
  -> score each symbol concurrently
  -> attach quote display data
  -> filter and sort active focus signals
  -> MonitorResult
```

评分由 `score.py` 完成；`scan.py` 只负责批量执行、聚合、过滤和排序。单标的失败记录在
`errors`，不阻断其他标的。

### 分组同步

```text
Longport group <-> sync service <-> THS group
```

- push 固定为 Longport → THS。
- pull 固定为 THS → Longport。
- 默认追加，不删除目标端已有成员。
- replace 使目标分组与源分组一致。
- 同步边界负责 Longport/THS symbol 转换和不支持资产过滤。

### 信号分流

`group route` 先扫描 Longport 源分组，再将趋势买入/超卖修复写入 entry 组，将趋势退出
写入 exit 组。默认追加；replace 会同时替换两个目标组，空结果对应空目标组。

## 运行时约束

- Longport 是行情、K 线和主要分组的数据源。
- 同花顺只作为分组同步对端。
- 每日扫描只使用已确认日线；未收盘的当日 K 线不会进入信号判断。
- 服务边界将外部异常转换成 `StkError`；CLI 统一渲染错误 envelope。
- stdout 只包含 JSON，日志写入 stderr。
- 缓存是数据源副本，不是业务数据权威来源。
