# 多股深入对比模板

## 适用场景

- 用户一次分析多只股票，并要求比较信号强弱、排序或深入拆解。
- 技术热点候选需要二次比较时，也使用本模板。
- DailyReport 默认不使用本模板；只有用户要求“深入对比/详细比较/多股比较”时追加。

## 输入数据

- `stk stock scan <symbols...>` 的 `MonitorResult`。
- 可选：`stk stock kline <symbols...> --count 20`。
- 可选：用户要求基本面时补 `stk stock fundamental <symbol>`。

## 分析方法

- 先按 `focus` 过滤，无明确信号标的只进入统计或一句提醒。
- 横向比较信号强弱：`decision.signal`、`decision.strength`、`signal_status`、`bars_since_signal`。
- 信号质量比较：主信号是否新鲜、ADX 是否支持、`context.overall_bias` 是否冲突。
- 风险收益比较：`risk_reward_ratio`、`risk_level`、`stop_loss`、`target_1`/`target_2`、`trailing_stop`。
- 辅助因子比较：只挑每只股票最重要的确认/冲突/风险因子，不堆指标。
- 推荐信号标的若有 `daily10`，用一句话比较延续性、过热和量能。

## 输出结构

```markdown
# 多股深入对比 - {YYYY-MM-DD}

## 结论

{1-2 句给出最值得跟踪、需要等待、风险退出和暂不处理的标的。}

## 横向对比

| 代码 | 名称 | 信号 | 新鲜度 | 辅助态度 | 风控 | 结论 |
|------|------|------|--------|----------|------|------|
| {symbol} | {name} | {signal}/{strength} | {signal_status}/{bars_since_signal}K | {overall_bias} | {按风控口径} | {跟踪突破/等待回踩/风险退出/仅观察/暂不处理} |

## 关键差异

| 代码 | 名称 | 主信号质量 | 辅助确认 | 风险冲突 | 近 10 日复核 |
|------|------|------------|----------|----------|--------------|
| {symbol} | {name} | {EMA/Supertrend/ADX 1句} | {最重要 confirming metrics；无则写”无”} | {最重要 warning/conflicting/risk；无则写”无”} | {仅推荐信号 + daily10 输出 1句；否则写”无”} |

## 排序建议

| 排序 | 标的 | 理由 | 明日动作 |
|------|------|------|----------|
| 1 | {symbol} | {最短理由} | {继续跟踪/等待回踩/风险退出/仅观察/暂不处理条件} |
| 2 | {symbol} | {最短理由} | {继续跟踪/等待回踩/风险退出/仅观察/暂不处理条件} |
| 3 | {symbol} | {最短理由} | {继续跟踪/等待回踩/风险退出/仅观察/暂不处理条件} |

## 统计

扫描 {scanned}/{total} | 重点关注 {focus_count} | 推荐 {recommend_count} | 买入信号 {entry_signal_count} | 退出/风险 {exit_signal_count} | 观察 {watch_signal_count} | 未入选 {no_signal_count} | 失败 {failed}
```
