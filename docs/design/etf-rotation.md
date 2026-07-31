# ETF 双池轮动

> Status: active
>
> Model: `rotation_v1`

ETF 轮动是独立于股票 `scan` 买卖信号的横截面系统。它从多个 Longport 来源组读取
ETF，每个来源池独立排名，再将阶段结果合并输出。当前约定使用：

- 来源池：`主题ETF`、`资产ETF`
- 结果组：`ETF启动`、`ETF领涨`、`ETF退潮`、`ETF落后`

系统只计算信号和维护观察分组，不执行交易、不分配仓位、不自动修改来源池。

## 命令与分组语义

只计算，不修改分组：

```bash
stk rotate 主题ETF 资产ETF
```

计算成功后完整替换四个阶段组：

```bash
stk group rotate \
  --source 主题ETF \
  --source 资产ETF \
  --emerging ETF启动 \
  --leading ETF领涨 \
  --weakening ETF退潮 \
  --lagging ETF落后
```

路由只有 replace 语义，不支持 append。所有来源组和目标组必须互不相同；来源池之间
不得包含重复 Symbol。重复代码、任一池整体不可用或成功标的少于 5 只都会使请求失败，
四个目标组均不刷新。

四个阶段是排名结果组，不是六种 action 的替代物。`rotate_in`、`hold`、`exit`、
`reduce`、`watch`、`avoid` 只作为每只 ETF 的输出字段，不创建额外分组。

## 数据窗口和日期

- 每只 ETF 请求 90 根日线。
- 当日尚未收盘时剔除当日日线。
- 至少需要 70 根有效确认日线。
- 每个池使用最新确认日期的众数作为 `as_of`；众数平值时取较新的日期。
- 最新日期不等于池内 `as_of` 的标的进入 `failures[]`。
- 所有计算只使用对应确认日及之前的数据。
- `previous_stage` 使用前一根确认日线重新计算完整池级横截面，不读取本地历史快照。

单标的历史不足、日期不一致或指标不可用时，其他标的继续分析。每个池最终仍需至少
5 只成功标的。覆盖关系始终满足：

```text
emerging + leading + weakening + lagging = analyzed
total = analyzed + failed
```

## 指标职责

TA-Lib 负责：

- `ROCP`：5、20、60 日收益
- `STDDEV`：20、60 日对数收益波动率
- `LINEARREG_SLOPE`、`CORREL`：20 日趋势质量
- `MFI`：MFI14
- `EMA`：EMA9、EMA20、EMA26、EMA60
- `RSI`：RSI14

stockstats 负责 Supertrend(10,3) 和同源 ATR10。ATR 百分比固定为：

```text
atr_pct = ATR10 / close * 100
```

pandas 和 NumPy 只负责日期对齐、池内中位数、百分位、成交额区间比较和因子组合。
成交额与 MFI 只表示交易活跃度和价格方向确认，不解释为 ETF 净申购或资金净流入。

## 强度轴

日对数收益与同期实现波动率：

```text
log_return[t] = log(close[t] / close[t-1])
vol20 = STDDEV(log_return, 20) * sqrt(20)
vol60 = STDDEV(log_return, 60) * sqrt(60)
```

使用池内波动率第 10 百分位作为分母下限：

```text
adjusted_volN = max(volN, pool_percentile_10(volN))
```

风险调整相对动量：

```text
excess20 = return20 - pool_median_return20
excess60 = return60 - pool_median_return60
relative_momentum20 = excess20 / adjusted_vol20
relative_momentum60 = excess60 / adjusted_vol60
```

趋势质量：

```text
slope20 = LINEARREG_SLOPE(log_close, 20)
r_squared20 = CORREL(log_close, time_index, 20) ^ 2
trend_quality = slope20 * r_squared20 / adjusted_vol20
```

原始因子先转换成池内 0–100 百分位，平值共享平均名次，全池平值为 50：

```text
strength =
    percentile(relative_momentum20) * 50%
    + percentile(relative_momentum60) * 35%
    + percentile(trend_quality) * 15%
```

## 动量轴

当前 5 日窗口与此前紧邻的 5 日窗口互不重叠：

```text
current_excess5 = current_return5 - current_pool_median_return5
previous_excess5 = previous_return5 - previous_pool_median_return5
acceleration = (current_excess5 - previous_excess5) / adjusted_vol20
```

成交额和 MFI 确认：

```text
turnover_ratio = latest_5d_mean_turnover / previous_20d_mean_turnover
turnover_confirmation = sign(current_excess5) * log(turnover_ratio)
mfi_confirmation = (MFI14 - 50) / 50

volume_confirmation =
    percentile(turnover_confirmation) * 70%
    + percentile(mfi_confirmation) * 30%

momentum =
    percentile(acceleration) * 80%
    + volume_confirmation * 20%
```

## 阶段

每只成功分析的 ETF 唯一属于一个阶段：

```text
strength <= 50 AND momentum >= 55 -> emerging
strength > 50  AND momentum >= 45 -> leading
strength > 50  AND momentum < 45  -> weakening
strength <= 50 AND momentum < 55  -> lagging
```

45/55 缓冲用于降低阶段抖动。排序规则：

- `emerging`：momentum 降序，其次 strength 降序
- `leading`：strength 降序，其次 momentum 降序
- `weakening`：momentum 升序，其次 strength 降序
- `lagging`：strength 升序，其次 momentum 升序

阶段是池内相对位置，不等于可交易动作。即使整个池都处于绝对下跌趋势，也仍会存在
相对领先者，必须继续检查绝对趋势和 action。

## 绝对趋势与事件

绝对趋势：

```text
bullish = close > EMA20 > EMA60 AND Supertrend bullish
bearish = close < EMA20 < EMA60 AND Supertrend bearish
neutral = otherwise
```

系统识别最近三根确认日线内的四种事件：

- Supertrend 由空翻多
- Supertrend 由多翻空
- EMA9 上穿 EMA26
- EMA9 下穿 EMA26

介入过滤要求：

```text
close > EMA20
AND (Supertrend bullish OR EMA9 > EMA26)
AND RSI14 < 75
AND close <= EMA20 + 2 * ATR10
```

只有 `rotate_in` 和 `exit` 使用三根确认日线事件窗口；其余 action 表示当前状态。

## Action 优先级

action 按下列顺序唯一判定：

1. `exit`
   - 阶段为 `weakening` 或 `lagging`；
   - 最近三日出现 Supertrend 翻空或 EMA 死叉；
   - 对应指标当前仍为空头。
2. `rotate_in`
   - 阶段为 `emerging` 或 `leading`；
   - momentum 不低于 55；
   - 最近三日出现 Supertrend 翻多或 EMA 金叉；
   - 通过全部介入过滤。
3. `hold`
   - 阶段为 `leading`；
   - 绝对趋势为 `bullish`；
   - 没有当前有效的空头事件。
4. `reduce`
   - 阶段为 `weakening`，但尚未形成 `exit`。
5. `watch`
   - `emerging` 尚未获得技术确认；
   - 或 `emerging`/`leading` 因过热、趋势未确认或偏离 EMA20 过大而不能介入。
6. `avoid`
   - 阶段为 `lagging`，且没有新的 `exit` 事件。

## 流动性提示

系统不使用固定成交额阈值剔除 ETF。每个池分别计算 20 日平均成交额，处于池内后 20%
的标的保留在结果中，并输出：

```json
{"warnings": ["low_liquidity"]}
```

低流动性不会直接改变阶段或 action。调用方仍应人工检查成交额、买卖价差和跨境 ETF
溢折价。

## 输出契约

`RotationResult` 和路由结果都直接包含：

```text
model
sources[]
summary
emerging[]
leading[]
weakening[]
lagging[]
failures[]
```

路由结果另外包含 `operation`、`mode` 和 `targets[]`。每只 ETF 包含：

```text
pool
symbol
name
as_of
stage
previous_stage
stage_changed
action
trend
strength
momentum
factors
indicators
signal
warnings
```

`sources[]` 提供每个独立来源池的覆盖数和阶段数；`summary` 是所有池合并后的总计。
个别失败存在时成功 envelope 的 `status` 为 `partial`。

