# ETF 三阶段轮动

> Status: active
>
> Model: `rotation_v2`

ETF 轮动从 Longport 来源组读取 ETF，以绝对价格结构判定启动、强势和退潮，并在每个
来源池、每个阶段内独立排序。百分位只决定同阶段优先级，不决定阶段。系统只计算信号
和维护观察分组，不执行交易、不分配仓位、不自动修改来源池。

## 命令与分组

```bash
stk rotate 主题ETF

stk group rotate \
  --source 主题ETF \
  --emerging ETF启动 \
  --strong ETF强势 \
  --fading ETF退潮
```

路由只有 replace 语义。来源组和三个目标组必须互不相同；多个来源池不得包含重复
Symbol。任一池整体不可用或成功标的少于 5 只时，三个目标组都不刷新。系统不会删除
旧版的 `ETF落后` 分组。

## 数据与状态

- 每只 ETF 请求 90 根日线，剔除未收盘日线后至少需要 70 根。
- 每个池使用最新确认日期的众数作为 `as_of`；日期不一致的标的进入 `failures[]`。
- 状态完全由 K 线回算，不读取或保存本地阶段历史。
- 每只成功分析的 ETF 属于 `emerging`、`strong`、`fading` 或内部 `inactive`。
- inactive 只返回汇总数量，不返回明细，也不写入目标组。

```text
emerging + strong + fading + inactive = analyzed
total = analyzed + failed
```

判定优先级：

```text
fading -> confirmed emerging -> strong -> rebound emerging -> inactive
```

## 指标

趋势结构使用 Supertrend(10,3)、EMA5/9/10/20/26/60、EMA20 五日斜率和 ADX14；
动量使用 5/20/60 日收益、前一个不重叠 5 日收益和 MACD(12,26,9)；波动使用 ATR10
与 20/60 日实现波动率；量价确认使用 5 日成交额相对前 20 日均值及 MFI14；趋势质量
使用 20 日对数价格回归斜率乘以 R²，并按波动率调整。

成交额和 MFI 只表示交易活跃度与价格方向确认，不解释为 ETF 净申购或资金净流入。
RSI、ADX、MACD 和均线排列除明确写入硬条件的部分外，只用于 action、warning 和排序。

## 启动 emerging

满足任一路径。

```text
confirmed:
    最近两根确认日线内 Supertrend 由空翻多
    AND 当前 Supertrend bullish
    AND close > EMA20
    AND return5 > 0

rebound:
    return5 > 0
    AND return5 > previous_return5
    AND close > EMA9
    AND close >= EMA20 - 0.25 * ATR10
    AND EMA20 五日斜率 > -1%（均线不再加速下跌）
```

只有 confirmed 且 `RSI14 < 75`、`close <= EMA20 + 2*ATR10` 时 action 为
`rotate_in`，其余为 `watch`。过热或偏离过大不改变阶段，只生成 warning 并阻止介入。
单纯连续上涨不构成启动确认：反弹必须伴随均线企稳（斜率接近转正）且贴近 EMA20。

排序先放 confirmed，再按 Supertrend 事件新鲜度和 `rank_score`：

```text
rank_score = 5日风险调整改善 40% + 趋势质量 20%
           + 成交额确认 20% + 接近 EMA20 程度 20%
```

## 强势 strong

```text
当前 Supertrend bullish
AND close > EMA20
AND EMA20 > 5根确认日线前的 EMA20
AND return20 > 0
AND 未连续 3 日及以上下跌（consecutive_down < 3）
AND 当前不存在有效退潮条件
```

强势 action 固定为 `hold`。RSI/KDJ/WR 过热、单日跌破短均线或 MACD histogram 单日
缩短都不会单独移出强势阶段；但连续 3 个及以上交易日收阴会直接移出强势
（价格结构仍多头但短期动量已转弱，不再视为强势持有）。

```text
rank_score = 20日风险调整收益 30% + 20日趋势质量 25% + ADX14 20%
           + MACD histogram / ATR10 15% + 成交额与 MFI 确认 10%
```

## 退潮 fading

退潮首先要求最近 10 根确认日线内曾满足 confirmed emerging 或 strong。单纯 rebound
失败直接回到 inactive，长期弱势 ETF 不会因为继续下跌而成为退潮。

```text
severe:
    当前 Supertrend bearish
    AND close < EMA20
    AND MACD histogram < 0
    AND ADX14 高于两根日线前

confirmed:
    最近三根确认日线内 Supertrend 由多翻空且当前仍 bearish
    OR 连续两日 close < EMA20 且 EMA20 五日斜率 <= 0
    OR 连续 3 日及以上收阴且 close < EMA20（3 连阴破位）

mild:
    return5 < 0
    AND EMA5 < EMA10
    AND MACD histogram < 0
    AND close <= EMA20 + 0.5 * ATR10
```

严重度优先级为 `severe > confirmed > mild`。mild 的 action 为 `reduce`，confirmed 和
severe 为 `exit`。

```text
rank_score = 5日风险调整跌幅 35% + 跌破 EMA20 的 ATR 距离 30%
           + MACD 空头强度 20% + 下跌成交额确认 15%
```

## 输出契约

```text
model = rotation_v2
sources[]
summary
emerging[]
strong[]
fading[]
failures[]
```

每项包含 `stage`、`previous_state`、`stage_changed`、`action`、`rank_score`、可选
`setup`、可选 `fade_severity`、`trend`、`factors`、`indicators`、`signal` 和
`warnings`。路由结果另包含三个 `targets[]`。

单标的失败不阻断同池其他标的；每池最终仍需至少 5 只成功标的。存在个别失败时成功
envelope 的 `status` 为 `partial`。
