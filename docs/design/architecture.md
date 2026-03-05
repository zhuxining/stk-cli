# stk-cli 架构设计（补充）

> 基础架构信息（目录结构、层级职责、开发命令）见 `CLAUDE.md`。本文档仅记录深度设计决策。

## 1. 命令结构（2026-03 重组后）

按 **市场 → 板块 → 个股** 三层逻辑组织：

```
stk
├── market      # 市场整体：指数、温度、涨跌面、新闻
├── board       # 行业/概念板块：列表、成分股、资金流
├── stock       # 个股：报价、基本面、技术指标、资金流等
└── watchlist   # 自选股管理
```

### 命令与服务映射

| 命令 | 服务层文件 | 说明 |
|------|-----------|------|
| `stk market index` | `services/market.get_indices()` | 大盘指数 |
| `stk market temp` | `services/market.get_temperature()` | 市场温度 |
| `stk market breadth` | `services/market.get_breadth()` | 涨跌面 |
| `stk market news` | `services/news.get_global_news()` | 全局新闻 |
| `stk board list` | `services/board.get_board_list()` | 板块列表 |
| `stk board cons` | `services/board.get_board_cons()` | 板块成分股 |
| `stk board flow` | `services/board.get_sector_flow_hist()` | 板块资金流历史 |
| `stk board detail` | `services/board.get_sector_flow_detail()` | 板块内个股资金流 |
| `stk stock rank` | `services/rank.get_hot/tech/flow_rank()` | 统一排名入口 |
| `stk stock quote` | `services/quote.get_quote()` | 实时报价 |
| `stk stock profile` | `services/fundamental.get_profile()` | 公司概况 |
| `stk stock fundamental` | `services/fundamental.get_comparison()` | 同业对比 |
| `stk stock valuation` | `services/fundamental.get_valuation()` | 估值指标 |
| `stk stock indicator` | `services/indicator.calc_indicator()` | 技术指标 |
| `stk stock history` | `services/history.get_history()` | K 线历史 |
| `stk stock news` | `services/news.get_news()` | 个股新闻 |
| `stk stock flow` | `services/flow.get_stock_flow()` | 个股资金流 |
| `stk stock chip` | `services/chip.get_chip_distribution()` | 筹码分布 |
| `stk watchlist *` | `services/watchlist.*` | 自选股 CRUD |

---

## 2. 数据源策略

**Longport + akshare 双数据源**：

- **Longport**：主数据源，覆盖 A 股/港股/美股的实时行情、K 线、估值
- **akshare**：补充 A 股特色数据（新闻、筹码、市场广度、板块资金流、基本面对比）

### Symbol 规范化

`utils/symbol.py` 的 `to_longport_symbol()` 统一处理所有市场的 symbol 格式：

| 输入 | 输出 | 说明 |
|------|------|------|
| `700.HK` | `700.HK` | 港股，原样 |
| `AAPL.US` | `AAPL.US` | 美股，原样 |
| `HSI.HK` | `HSI.HK` | 港股指数，原样 |
| `.DJI` / `.IXIC` / `.SPX` | 原样 | 美股指数，点前缀 |
| `000001.SH` | `000001.SH` | 已有后缀，原样 |
| `600519` | `600519.SH` | A 股主板，6xx → 上交所 |
| `688001` | `688001.SH` | A 股科创板，688xxx → 上交所 |
| `000001` | `000001.SZ` | A 股主板，0xx → 深交所 |
| `002001` | `002001.SZ` | A 股中小板，002xxx → 深交所 |
| `300750` | `300750.SZ` | A 股创业板，300xxx → 深交所 |
| `800001` | `800001.BJ` | 北交所，8xxxxx → 北交所 |

### 数据转换工具

`utils/symbol.py` 提供统一的转换函数：

| 函数 | 说明 | 用途 |
|------|------|------|
| `to_longport_symbol(symbol)` | 用户输入 → Longport 格式 | 所有服务 |
| `to_em_symbol(symbol)` | 用户输入 → 东方财富格式 | `fundamental.py` |
| `to_ak_market(symbol)` | 用户输入 → akshare (code, market) | `flow.py`, `fundamental.py` |
| `is_hk(symbol)` | 是否为港股 | `fundamental.py` |
| `to_hk_code(symbol)` | 港股代码补零 | `fundamental.py` |
| `to_decimal(val)` | 安全 Decimal 转换 | 所有 akshare 服务 |
| `to_metrics(row, cols, skip)` | DataFrame 行 → metrics dict | 所有 akshare 服务 |

---

## 3. 标的类型

通过 `--type` 参数区分，默认为 `stock`：

```python
class TargetType(StrEnum):
    STOCK = "stock"       # 个股（默认）
    SECTOR = "sector"     # 行业板块
    CONCEPT = "concept"   # 概念板块
    INDEX = "index"       # 指数
```

### 各类型支持矩阵

| 命令 | stock | index | sector | concept |
|------|-------|-------|--------|---------|
| `stock quote` | ✅ | ✅ | ✅ | ✅ |
| `stock history` | ✅ | ✅ | ❌ | ❌ |
| `stock indicator` | ✅ | ✅ | ❌ | ❌ |
| `stock valuation` | ✅ | ❌ | ❌ | ❌ |
| `stock fundamental` | ✅ | ❌ | ❌ | ❌ |
| `stock flow` | ✅ | ❌ | ❌ | ❌ |
| `stock chip` | ✅ | ❌ | ❌ | ❌ |
| `stock news` | ✅ | ❌ | ❌ | ❌ |
| `board list` | ❌ | ❌ | ✅ | ✅ |
| `board cons` | ❌ | ❌ | ✅ | ✅ |
| `board flow/detail` | ❌ | ❌ | ✅ | ✅ |
| `market index` | ✅ (成分) | — | — | — |
| `market temperature` | ✅ (整体) | — | — | — |
| `market breadth` | ✅ (全市场) | — | — | — |

---

## 4. Longport SDK API 使用映射

| stk 命令 | Longport API | 返回类型 |
|----------|-------------|----------|
| `stock quote` | `ctx.quote([symbols])` | 实时行情 |
| `stock history` | `ctx.candlesticks(symbol, period, count, adjust)` | K 线数据 |
| `stock valuation` | `ctx.static_info()` + `ctx.quote()` | 静态信息 + 实时价格 |
| `market index` | `ctx.quote(MAJOR_INDICES)` | 批量指数行情 |
| `market temperature` | `ctx.market_temperature(Market.CN)` | 市场温度 |
| `stock flow` | `ctx.capital_distribution()` + `ctx.capital_flow()` | 资金分布 + 日内流向 |

---

## 5. 命令数据流

### 5.1 实时行情 (`stk stock quote`)

```
stk stock quote 600519
  → commands/stock.py: quote()
  → services/quote.py: get_quote(symbol, target_type)
    → utils/symbol.py: to_longport_symbol("600519") → "600519.SH"
    → services/longport_quote.py: get_realtime_quote("600519.SH")
      → ctx.quote(["600519.SH"])
      → 计算 change / change_pct
  → models/quote.py: Quote(symbol, name, last, open, high, low, prev_close, ...)
  → output.py: JSON envelope 输出
```

### 5.2 K 线数据 (`stk stock history`)

```
stk stock history 700.HK --period day --count 30
  → services/history.py: get_history(symbol, target_type, period, count)
    → to_longport_symbol("700.HK") → "700.HK"
    → ctx.candlesticks("700.HK", Period.Day, 30, AdjustType.ForwardAdjust)
  → models/history.py: list[Candlestick]
```

### 5.3 技术指标 (`stk stock indicator`)

```
stk stock indicator 600519 MACD --count 60
  → services/indicator.py: calc_indicator(symbol, "MACD", count=60)
    → get_history() → pandas DataFrame (close, open, high, low, volume)
    → talib.MACD(close, 12, 26, 9) → macd, signal, hist
  → models/indicator.py: IndicatorResult(symbol, indicator, params, values)
```

支持的指标：MA, EMA, MACD, RSI, KDJ, BOLL

### 5.4 基本面 (`stk stock fundamental`)

```
stk stock fundamental compare 600519 --type growth
  → services/fundamental.py: get_comparison(symbol, category="growth")
    → utils/symbol.py: to_em_symbol("600519") → "SH600519"
    → ak.stock_zh_growth_comparison_em("SH600519")
    → DataFrame rows → list[CompanyMetric] (行业中值/平均 + 同行 + 目标股)
  → models/fundamental.py: IndustryComparison(symbol, category, companies)

stk stock fundamental valuation 700.HK
  → services/fundamental.py: get_valuation(symbol)
    → ctx.static_info() → total_shares, eps_ttm, bps
    → ctx.quote() → last_done (实时价格)
    → PE = price / eps_ttm, PB = price / bps, market_cap = price * total_shares
  → models/fundamental.py: Valuation(pe, pb, market_cap, total_shares, float_shares)
```

支持的对比类型：`growth`（成长性）、`valuation`（估值）、`dupont`（杜邦分析，仅 A 股）

### 5.5 市场概览 (`stk market`)

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

stk market breadth
  → services/market.py: get_breadth()
    → ak.stock_zh_a_spot_em() → 涨跌家数统计
    → ak.stock_zt_pool_em(date) → 涨停数
    → ak.stock_zt_pool_dtgc_em(date) → 跌停数
  → models/market.py: MarketBreadth(up_count, down_count, flat_count, limit_up, limit_down)

stk market news --source cls
  → services/news.py: get_global_news(source="cls", count=20)
    → ak.stock_info_global_cls(symbol="全部")
  → models/news.py: list[NewsItem]
```

### 5.6 板块数据 (`stk board`)

```
stk board list --type sector
  → services/board.py: get_board_list(type="sector")
    → ak.stock_board_industry_name_em()
    → DataFrame → list[BoardItem](code, name, metrics)
  → models/quote.py: BoardList(type, items)

stk board cons 酿酒行业 --type sector
  → services/board.py: get_board_cons(name="酿酒行业", type="sector")
    → ak.stock_board_industry_cons_em(symbol="酿酒行业")
  → models/quote.py: BoardCons(board, type, items)

stk board flow 酿酒行业 --type sector
  → services/board.py: get_sector_flow_hist(name="酿酒行业", type="sector")
    → ak.stock_sector_fund_flow_hist(symbol="酿酒行业")
  → models/flow.py: SectorFlowHist(name, type, days[])

stk board detail 酿酒行业 --period 今日
  → services/board.py: get_sector_flow_detail(name="酿酒行业", period="今日")
    → ak.stock_sector_fund_flow_summary(symbol="酿酒行业", indicator="今日")
  → models/flow.py: SectorFlowDetail(sector, period, items[])
```

### 5.7 排名数据 (`stk stock rank`)

```
stk stock rank --type hot
  → services/rank.py: get_hot_rank()
    → ak.stock_hot_rank_em()
  → models/market.py: TechRank(type="hot", label="人气榜", items[])

stk stock rank --type tech --screen lxsz
  → services/rank.py: get_tech_rank(type="lxsz", ma="20 日均线")
    → ak.stock_rank_lxsz_ths()
  → models/market.py: TechRank(type="lxsz", label="连续上涨", items[])

stk stock rank --type flow --scope stock --period 今日
  → services/flow.py: get_flow_rank(scope="stock", period="今日")
    → ak.stock_individual_fund_flow_rank(indicator="今日")
  → models/flow.py: FlowRank(scope, period, items[])
```

### 5.8 个股资金流 (`stk stock flow`)

```
stk stock flow 600519
  → services/flow.py: get_stock_flow(symbol="600519")
    → to_longport_symbol("600519") → "600519.SH"
    → ctx.capital_distribution("600519.SH") → 大/中/小单进出
    → ctx.capital_flow("600519.SH") → 日内分钟级 inflow
    → (A 股) ak.stock_individual_fund_flow(stock="600519", market="sh") → 历史数据
  → models/flow.py: StockFlow(symbol, large_in/out, medium_in/out, small_in/out, intraday[], history[])
```

---

## 6. 配置项

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `LONGPORT_APP_KEY` | Longport 应用 Key | — |
| `LONGPORT_APP_SECRET` | Longport 应用 Secret | — |
| `LONGPORT_ACCESS_TOKEN` | Longport 访问令牌 | — |
| `DATA_DIR` | 本地文件存储目录 | `~/.stk/` |
| `DEFAULT_FORMAT` | 默认输出格式 | `json` |
| `LOG_LEVEL` | 日志级别 | `WARNING` |

---

## 7. 本地存储格式

```
~/.stk/
├── watchlist.json          # 自选股列表
└── config.json             # 可选：用户偏好配置持久化
```

存储操作由 `services/watchlist.py` 封装，使用原子写入（tmp 文件 + rename）。

---

## 8. akshare 补充功能

| 功能 | 服务 | akshare API | 说明 |
|------|------|------------|------|
| 全局新闻 | `news.get_global_news()` | `stock_info_global_cls/ths/em` | 财联社/同花顺/东方财富 |
| 个股新闻 | `news.get_news()` | `stock_news_em` | A 股新闻 |
| 筹码分布 | `chip.get_chip_distribution()` | `stock_cyq_em` | A 股筹码成本 |
| 市场广度 | `market.get_breadth()` | `stock_zh_a_spot_em` + `stock_zt_pool_em` | 涨跌家数 + 涨停跌停 |
| 行业对比 | `fundamental.get_comparison()` | `stock_zh_growth/valuation/dupont_comparison_em` | 成长性/估值/杜邦 vs 同行 |
| 板块行情 | `board.get_board_list/cons()` | `stock_board_industry/concept_*_em` | 行业/概念板块 |
| 板块资金流 | `board.get_sector_flow_hist/detail()` | `stock_sector_fund_flow_hist/summary` | 板块历史/个股明细 |
| 人气/技术排名 | `rank.get_hot_rank()/get_tech_rank()` | `stock_hot_rank_em`, `stock_rank_*_ths` | 人气榜/技术选股 |
| 资金流排名 | `flow.get_flow_rank()` | `stock_individual/main/sector_fund_flow_rank` | 个股/主力/板块排名 |

---

## 9. 服务层文件结构（重组后）

```
services/
├── board.py          # 板块数据：list, cons, sector_flow_hist/detail
├── rank.py           # 排名数据：hot_rank, tech_rank
├── quote.py          # 实时报价：get_quote (stock/index/sector/concept)
├── market.py         # 市场概览：indices, temperature, breadth
├── flow.py           # 资金流：stock_flow, flow_rank
├── fundamental.py    # 基本面：valuation, comparison, profile
├── history.py        # K 线历史
├── indicator.py      # 技术指标 (ta-lib)
├── news.py           # 新闻资讯
├── chip.py           # 筹码分布
├── watchlist.py      # 自选股 CRUD
├── longport_quote.py # Longport 原始 API 封装
└── symbol.py         # （已移至 utils/symbol.py）
```

---

## 10. 错误处理

全局错误处理器在 `cli.py` 中捕获所有异常，转换为 JSON envelope：

```python
try:
    app()
except StkError as e:
    output.render_error(type(e).__name__, e.message)
except Exception as e:
    output.render_error("UnexpectedError", str(e))
```

自定义异常层次：

- `StkError` (基类)
  - `ConfigError` — 配置错误（环境变量缺失等）
  - `SourceError` — 数据源错误（API 失败、数据为空）
  - `SymbolNotFoundError` — 标的不存在
  - `IndicatorError` — 指标计算错误

日志使用 `loguru`，输出到 stderr（不干扰 stdout 的 JSON）。
