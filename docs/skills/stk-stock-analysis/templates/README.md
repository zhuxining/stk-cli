# 模板索引

`templates/` 按分析场景组织。每个模板都包含：适用场景、输入数据、分析方法、输出结构。`workflow/` 负责选择模板、取数和组装最终报告。

## 快速选择指南

| 用户意图 | 选择模板 |
|----------|----------|
| "今天市场怎么样"、"有什么热点"、"选股" | → `market-hotspot-analysis.md` |
| "我的持仓/自选"、"检查一下ETF分组"、"每日监控" | → `group-signal-tracking.md` |
| "对比几只股票"、"深入比较"、"多股分析" | → `multi-stock-deep-comparison.md` |

## 场景模板

| 模板 | 场景 | 默认命令 |
|------|------|----------|
| `market-hotspot-analysis.md` | 市场热点分析：市场温度、新闻影响、可选技术热点。 | `stk market`、`stk market news --count 20`，可选 `stk stock hotspot` / `stk stock candidates` / `stk stock scan` |
| `group-signal-tracking.md` | 分组信号追踪：watchlist 分组每日监控、focus 追踪、明日动作。 | `stk watchlist scan <group>` |
| `multi-stock-deep-comparison.md` | 多股深入对比：多只股票横向比较信号质量、风险收益、辅助因子和 high 日线复核。 | `stk stock scan <symbols...>`，可选 `kline` / `fundamental` |

## 通用口径

- 结论先行，第一屏回答“今天是否需要关注”，结论不超过 2 句。
- 多只股票必须用表格，不逐只写长段落。
- 只展开 `MonitorResult.focus`；观察标的只进入统计。
- 数字优先：`strength`、`signal_status`、`bars_since_signal`、`stop_loss`、`take_profit`、`risk_reward_ratio`。
- 强信号标的若有 `daily10`，只补 1 句复核。
- 辅助因子只引用 `state` 和 `metrics`。
- 退出类信号中 `stop_loss` 写”上方失效线”，`take_profit` 写”下行参考”。
- `观察` 只写观察、等待确认、风险提示、左侧机会，不写买卖动作。

## 固定动作口径

- `跟踪突破`：买入类 `signal` + `强信号`，未明显过热，量能或趋势延续较好。
- `等待回踩`：买入类 `signal` 但过热、缩量或 RR 一般。
- `风险退出`：退出类 `signal`。
- `仅观察`：`观察`。
- `暂不处理`：低质量或冲突明显的信号。

## 风控口径

- 买入类 `signal`：`止损 {stop_loss} / 止盈 {take_profit} / RR {risk_reward_ratio}`。
- 退出类 `signal`：`失效线 {stop_loss} / 下行参考 {take_profit}`。
- `观察`：`观察 / 风险 {risk_level}`。
