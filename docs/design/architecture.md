# stk-cli 架构设计（补充）

> 基础架构信息（目录结构、层级职责、开发命令）见 `CLAUDE.md`。本文档仅记录深度设计决策。

## 1. 数据源策略

**Longport 为唯一数据源**，覆盖 A 股、港股、美股。不再使用 akshare 路由。

### Symbol 规范化

`services/symbol.py` 的 `to_longport_symbol()` 统一处理所有市场的 symbol 格式：

| 输入 | 输出 | 说明 |
|------|------|------|
| `700.HK` | `700.HK` | 港股，原样 |
| `AAPL.US` | `AAPL.US` | 美股，原样 |
| `HSI.HK` | `HSI.HK` | 港股指数，原样 |
| `000001.SH` | `000001.SH` | 已有后缀，原样 |
| `.DJI` / `.IXIC` / `.SPX` | 原样 | 美股指数，点前缀 |
| `600519` | `600519.SH` | A 股，6xx → 上交所 |
| `000001` | `000001.SZ` | A 股，0xx → 深交所 |
| `300750` | `300750.SZ` | A 股，3xx → 深交所 |

## 2. 标的类型

通过 `--type` 参数区分，默认为 `stock`：

```python
class TargetType(str, Enum):
    STOCK = "stock"       # 个股（默认）
    SECTOR = "sector"     # 行业板块
    CONCEPT = "concept"   # 概念板块
    INDEX = "index"       # 指数
```

### 各类型支持矩阵（当前实现状态）

| 命令 | stock | index | sector | concept |
|------|-------|-------|--------|---------|
| quote | ✅ longport | ✅ longport | ✅ akshare | ✅ akshare |
| history | ✅ longport | ✅ longport | ❌ 待 akshare | ❌ 待 akshare |
| indicator | ✅ ta-lib | ✅ ta-lib | ❌ 待 akshare | ❌ |
| fundamental valuation | ✅ longport | ❌ | ❌ | ❌ |
| fundamental compare | ✅ akshare | ❌ | ❌ | ❌ |
| market index | ✅ longport（7 大指数） | — | — | — |
| market temperature | ✅ longport | — | — | — |
| market breadth | ✅ akshare | — | — | — |
| flow | ✅ longport | ❌ | ✅ akshare | ✅ akshare |
| chip cost | ✅ akshare | ❌ | ❌ | ❌ |
| news | ✅ akshare | ❌ | ❌ | ❌ |

## 3. Longport SDK API 使用映射

| stk 命令 | Longport API | 返回类型 |
|----------|-------------|----------|
| `quote get` | `ctx.quote([symbols])` | 实时行情 |
| `history get` | `ctx.candlesticks(symbol, period, count, adjust)` | K 线数据 |
| `fundamental valuation` | `ctx.static_info()` + `ctx.quote()` | 静态信息 + 实时价格 |
| `market index` | `ctx.quote(MAJOR_INDICES)` | 批量指数行情 |
| `market temperature` | `ctx.market_temperature(Market.CN)` | 市场温度 |
| `flow get` | `ctx.capital_distribution()` + `ctx.capital_flow()` | 资金分布 + 日内流向 |

## 4. 命令数据流

### 4.1 实时行情 (`stk quote`)

```
stk quote get 600519
  → commands/quote.py
  → services/quote.py: get_quote(symbol, target_type)
    → services/longport_quote.py: get_realtime_quote(symbol)
      → symbol.py: to_longport_symbol("600519") → "600519.SH"
      → ctx.quote(["600519.SH"])
      → 计算 change / change_pct
  → models/quote.py: Quote(symbol, name, last, open, high, low, prev_close, change, change_pct, volume, turnover, timestamp)
  → JSON envelope 输出
```

### 4.2 K 线数据 (`stk history`)

```
stk history get 700.HK --period day --count 30
  → services/history.py: get_history(symbol, period, count)
    → ctx.candlesticks("700.HK", Period.Day, 30, AdjustType.ForwardAdjust)
  → models/history.py: list[Candlestick]
```

### 4.3 技术指标 (`stk indicator`)

```
stk indicator get 600519 MACD --count 60
  → services/indicator.py: calc_indicator(symbol, "MACD", count=60)
    → get_history() → pandas DataFrame
    → talib.MACD(close, 12, 26, 9)
  → models/indicator.py: IndicatorResult(symbol, indicator, params, values)
```

支持的指标：MA, EMA, MACD, RSI, KDJ, BOLL

### 4.4 基本面 (`stk fundamental`)

```
stk fundamental compare 600519 --type growth
  → services/fundamental.py: get_comparison(symbol, category="growth")
    → ak.stock_zh_growth_comparison_em(em_symbol)
    → DataFrame rows → list[CompanyMetric] (行业中值/平均 + 同行 + 目标股)
  → models/fundamental.py: IndustryComparison(symbol, category, companies)

stk fundamental valuation 700.HK
  → services/fundamental.py: get_valuation(symbol)
    → ctx.static_info() → total_shares, eps_ttm, bps
    → ctx.quote() → last_done (实时价格)
    → PE = price / eps_ttm, PB = price / bps, market_cap = price * total_shares
  → models/fundamental.py: Valuation(pe, pb, market_cap, total_shares, float_shares)
```

支持的对比类型：growth（成长性）、valuation（估值）、dupont（杜邦分析）

### 4.5 指数行情 + 市场温度 (`stk market`)

```
stk market index
  → services/market.py: get_indices()
    → ctx.quote(MAJOR_INDICES)  # 7 大指数批量查询
    → MAJOR_INDICES = [000001.SH, 399001.SZ, 399006.SZ, HSI.HK, .IXIC, .DJI, .SPX]
  → models/market.py: list[IndexQuote]

stk market temperature
  → services/market.py: get_temperature()
    → ctx.market_temperature(Market.CN)
  → models/market.py: MarketTemperature(score, level, valuation, sentiment)
```

### 4.6 资金流向 (`stk flow`)

```
stk flow get 600519
  → services/flow.py: get_flow(symbol, target_type="stock")
    → ctx.capital_distribution("600519.SH") → 大/中/小单进出
    → ctx.capital_flow("600519.SH") → 日内分钟级 inflow
  → models/flow.py: MoneyFlow(symbol, large_in/out, medium_in/out, small_in/out, intraday)
```

## 5. 配置项

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `LONGPORT_APP_KEY` | longport 应用 Key | — |
| `LONGPORT_APP_SECRET` | longport 应用 Secret | — |
| `LONGPORT_ACCESS_TOKEN` | longport 访问令牌 | — |
| `DATA_DIR` | 本地文件存储目录 | `~/.stk/` |
| `DEFAULT_FORMAT` | 默认输出格式 | `json` |
| `LOG_LEVEL` | 日志级别 | `WARNING` |

## 6. 本地存储格式

```
~/.stk/
├── watchlist.json          # 自选股列表
└── config.json             # 可选：用户偏好配置持久化
```

## 7. akshare 补充功能（已实现）

| 功能 | akshare API | 说明 |
|------|------------|------|
| `news` — 新闻资讯 | `stock_news_em` | A 股新闻 |
| `chip cost` — 筹码分布 | `stock_cyq_em` | A 股筹码成本 |
| `market breadth` — 市场广度 | `stock_zh_a_spot_em` + `stock_zt_pool_em` | 涨跌家数 + 涨停跌停 |
| `fundamental compare` — 行业对比 | `stock_zh_growth/valuation/dupont_comparison_em` | 成长性/估值/杜邦分析 vs 行业同行 |
| `quote sector/concept` — 板块概念 | `stock_board_industry_name_em` / `stock_board_concept_name_em` | 板块行情 |
| `flow sector` — 板块资金流向 | `stock_sector_fund_flow_rank` | 行业/概念资金流 |
