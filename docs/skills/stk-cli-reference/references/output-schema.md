# 扫描输出结构

`stk scan <longport-group>` 返回 `MonitorResult`：

| 字段 | 说明 |
|---|---|
| `run_date` | 扫描日期 |
| `universe` | 分组名、总数、成功数、失败数 |
| `summary` | focus、推荐、entry、exit 数量 |
| `focus[]` | 当前需要关注的标的 |
| `ignored` | 无有效信号数量 |
| `errors[]` | 单标的非致命错误 |

每个 `FocusItem` 包含：

- `symbol`、`name`、`last`、`change_pct`
- `decision`：信号、强度、状态、日期和信号年龄
- `primary_signal`：EMA、Supertrend、ADX 和原因
- `context`：辅助因子态度、指标与警告
- `risk`：ATR、止损、目标位、移动止损和风险收益比
- `daily10`：仅在请求 `--daily10` 且信号适合复核时出现

默认会从 `context.factors` 省略 neutral/none 因子；使用 `--full-context` 获取全部因子。
