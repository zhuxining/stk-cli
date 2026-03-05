# 策略模板

## 趋势跟踪型

- 核心指标: MA(5/10/20/60), MACD, BOLL
- 技术筛选: `stk stock rank --type tech --screen lxsz` (连续缩量上涨)
- 确认条件: 成交量趋势配合、均线多头排列
- 资金面: 主力持续净流入
- 板块筛选偏好: 偏好持续领涨行业板块，从板块内选趋势最稳的龙头（资金净流入持续 + 涨幅居前）

## 超跌反弹型

- 核心指标: RSI, KDJ, BOLL
- 技术筛选: `stk stock rank --type tech --screen cxfl` (持续放量)
- 触发条件: RSI < 30、KDJ 金叉、价格触及布林下轨
- 资金面: 主力由流出转为流入
- 板块筛选偏好: 偏好近期回调但资金开始回流的板块，从板块内选跌幅最深但资金转正的个股

## 价值投资型

- 估值指标: PE、PB、PS，通过 `stk stock valuation` 获取
- 成长性: `stk stock fundamental --type growth`
- 行业对比: `stk stock fundamental --type valuation`
- 杜邦分析: `stk stock fundamental --type dupont` (仅限A股)
- 板块筛选偏好: 偏好低估值行业板块（如银行、基建、公用事业），从板块内选 PE/PB 低于行业均值的龙头

## 短线动量型

- 热度排名: `stk stock rank --type hot`
- 资金排名: `stk stock rank --type flow --scope main`
- 筹码分布: `stk stock chip`
- 消息催化: `stk stock news`
- 板块筛选偏好: 偏好当日涨幅最大的概念板块，从板块内选资金净流入最多且换手率高的个股
