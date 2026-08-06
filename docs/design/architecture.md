# stk-cli 架构

> Status: active

`stk-cli` 是面向 Agent 的单进程 JSON CLI，聚焦 K 线与指标、跨平台分组同步、股票
信号扫描和 ETF 横截面轮动。

## 系统边界

```text
CLI
├── data kline ───────> history ──> indicator
├── scan ─────────────> watchlist ──> score/scan ──> quote
├── rotate ───────────> watchlist ──> history/rotation
└── group
    ├── longport ─────> watchlist
    ├── ths ──────────> ths_wrapper
    ├── xueqiu ───────> xueqiu
    ├── sync ─────────> sync ──> watchlist/ths_wrapper/xueqiu
    ├── route ────────> scan ──> watchlist
    └── rotate ───────> rotation ──> watchlist
```

- Longport 是行情、K 线和主要分组的数据源。
- 同花顺和雪球是分组同步对端，不参与行情或信号计算；雪球支持默认自选和股票自定义
  分组，系统动态分组只读。
- 本地存储只保存缓存和 Longport 分组名称到 ID 的映射。
- 项目不执行交易、不管理仓位、不提供回测，也不长期保存行情数据。

## 分层职责

- `commands/`：解析参数、调用服务、渲染结果，不包含业务判断。
- `services/`：访问外部系统、转换数据、计算指标和信号、编排工作流，不写 stdout。
- `models/`：定义服务边界和公开 JSON 数据契约。
- `store/`：提供缓存和本地映射的原子读写。
- `utils/`：提供无业务状态的通用转换，例如 Symbol 规范化。
- `output.py`：统一输出 `ok/data/error/meta` envelope。

依赖方向保持为命令层 → 服务层 → 数据源/存储，模型可被命令层和服务层共同依赖。

## 核心数据流

### K 线与指标

```text
symbols
  -> normalize
  -> Longport candlesticks
  -> pandas DataFrame
  -> ta-lib / stockstats
  -> KlineBatchResult
```

指标服务只负责计算和解释数据，不决定扫描或 route 的成员资格。

### 分组扫描

```text
Longport group
  -> confirmed daily candles
  -> score each symbol concurrently
  -> classify StockAssessment state
  -> attach quote display data
  -> ScanResult
```

`score.py` 判断单标的事件与当前路由状态；`scan.py` 负责并发、聚合、过滤和排序。单标的
失败记录到 `errors`，不会阻断普通 scan。

### 分组同步

```text
Longport group <-> sync service <-> THS group / Xueqiu default watchlist
```

同步服务负责方向、差异和写入模式；平台边界负责 Symbol 转换及不支持资产过滤。
雪球认证仅从环境变量读取浏览器 Cookie `u`、`xq_a_token`、`xq_id_token`，不负责账号
密码登录、token 刷新或持久化。雪球 replace 先新增后删除，新增失败时跳过全部删除。

### ETF 三阶段轮动

```text
Longport source groups
  -> reject duplicate symbols
  -> fetch 90 confirmed daily bars concurrently
  -> align each pool to its modal as_of
  -> TA-Lib / stockstats per-symbol indicators
  -> absolute state from price structure and recent history
  -> independent stage-local pool percentiles
  -> rank_score and action
  -> merge and sort three routed stages
  -> RotationResult
```

`rotation.py` 同时承担单标的指标、池级横截面、跨池聚合和路由编排，但公开副作用只在
路由最后发生。`rotate` 只读；`group rotate` 在所有来源池成功完成后，使用 replace
刷新三个目标快照。来源池整体不可用时不修改目标组，个别标的失败则记录到
`failures[]` 并继续。

ETF 阶段由绝对趋势结构和历史事件决定，池内排名只决定同阶段展示顺序；inactive 只
计入汇总。详细公式和字段契约见[ETF 三阶段轮动](etf-rotation.md)。

### 信号快照

`group route` 扫描一个 Longport 源分组，并生成反转快照：买入由最近两根确认日线内
Supertrend 翻多触发；空头反转由最近两根确认日线内的 Supertrend 翻空触发，或由
EMA 死叉配合收盘价跌破 EMA26 触发。默认使用 replace
语义，不依赖昨日成员。个别标的扫描失败时跳过该标的，其余结果继续写入目标组；
成功响应通过 `source.failed` 和 `failures[]` 暴露完整失败信息。

具体判定规则以[信号规则](signal-strategy.md)为唯一事实来源。

## 运行时不变量

- 信号只使用已确认的完整日线；实时行情字段只用于展示。
- ETF 来源池分别计算横截面，两个池不共享中位数、波动率下限或百分位。
- stdout 只包含 JSON，日志写入 stderr。成功响应的 `status` 为 `success` 或
  `partial`；后者通过 `data.failures[]` 暴露可跳过的单项失败。请求级错误使用
  `ok: false, status: failed`。
- 服务将外部异常转换为 `StkError`，CLI 统一渲染错误。
- Pydantic 模型是服务层与调用方之间的契约。
- 缓存不是业务数据的权威来源，失败时不得静默伪造完整结果。
