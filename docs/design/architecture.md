# stk-cli 架构设计（补充）

> 基础架构信息（目录结构、层级职责、开发命令）见 `CLAUDE.md`。本文档仅记录深度设计决策。

## 1. 命令结构

按 **市场 → 个股** 两层逻辑组织：

```
stk
├── market      # 市场整体：指数、温度、新闻
├── stock       # 个股：报价、基本面、技术指标、资金流、评分等
├── watchlist   # 自选股管理
├── doctor      # 数据源健康检查
└── cache       # 缓存管理
```

### 命令与服务映射

| 命令 | 服务层文件 | 说明 |
|------|-----------|------|
| `stk market index` | `services/market.get_indices()` | 大盘指数 |
| `stk market temp` | `services/market.get_temperature()` | 市场温度 |
| `stk market news` | `services/news.get_global_news()` | 全局新闻（cls/ths） |
| `stk stock rank` | `services/rank.get_tech_rank()` | 技术选股排名（同花顺） |
| `stk stock quote` | `services/quote.get_quote()` | 实时报价 |
| `stk stock profile` | `services/fundamental.get_profile()` | 公司概况 |
| `stk stock fundamental` | `services/fundamental.get_comparison()` | 同业对比 |
| `stk stock valuation` | `services/fundamental.get_valuation()` | 估值指标 (via calc_indexes) |
| `stk stock history` | `services/indicator.get_daily()` | K 线 + 全部技术指标（合并） |
| `stk stock indicator` | `services/indicator.calc_indicator()` | 单个技术指标查询 |
| `stk stock score` | `services/score.calc_score()` | 多指标共振评分 + ATR 风控 |
| `stk stock flow` | `services/flow.get_stock_flow()` | 个股资金流（longport） |
| `stk watchlist list` | `services/watchlist.list_watchlists()` | 列出所有分组 |
| `stk watchlist show` | `services/watchlist.get_watchlist()` | 查看分组内标的 |
| `stk watchlist create` | `services/watchlist.create_group()` | 创建分组 |
| `stk watchlist add` | `services/watchlist.add_symbol()` | 添加标的到分组 |
| `stk watchlist remove` | `services/watchlist.remove_symbol()` | 从分组移除标的 |
| `stk watchlist delete` | `services/watchlist.delete_group()` | 删除分组 |
| `stk doctor check` | `services/health.run_health_check()` | 数据源健康检查 |
| `stk cache clear` | `store/cache.clear_cache()` | 缓存清除 |

---

## 2. 数据源策略

**Longport 为主 + akshare（同花顺）为辅**：

- **Longport**：主数据源，覆盖 A 股/港股/美股的实时行情、K 线、估值 (calc_indexes)、资金流、自选股管理
- **akshare（同花顺）**：补充 A 股特色数据（技术选股排名、基本面对比、主营业务概况）
- **akshare（财联社）**：全局新闻

> 已移除所有东方财富（eastmoney）数据源，因其 IP 级别反爬限制导致接口不稳定。

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
| `to_ak_market(symbol)` | 用户输入 → akshare (code, market) | `fundamental.py` |
| `is_hk(symbol)` | 是否为港股 | `fundamental.py` |
| `to_hk_code(symbol)` | 港股代码补零 | `fundamental.py` |
| `extract_code(symbol)` | 提取纯数字代码 | `fundamental.py` |

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
| `stock quote` | ✅ | ✅ | ❌ | ❌ |
| `stock history` | ✅ | ✅ | ❌ | ❌ |
| `stock indicator` | ✅ | ✅ | ❌ | ❌ |
| `stock valuation` | ✅ | ❌ | ❌ | ❌ |
| `stock fundamental` | ✅ | ❌ | ❌ | ❌ |
| `stock flow` | ✅ | ❌ | ❌ | ❌ |
| `stock score` | ✅ | ❌ | ❌ | ❌ |

---

## 4. Longport SDK API 使用映射

| stk 命令 | Longport API | 返回类型 |
|----------|-------------|----------|
| `stock quote` | `ctx.quote([symbols])` | 实时行情 |
| `stock history` | `ctx.candlesticks(symbol, period, count, adjust)` | K 线 + 全部技术指标 |
| `stock valuation` | `ctx.calc_indexes([symbol], [CalcIndex.*])` | PE/PB/市值/涨跌/资金流等全量指标 |
| `market index` | `ctx.quote(MAJOR_INDICES)` | 批量指数行情 |
| `market temperature` | `ctx.market_temperature(Market.CN)` | 市场温度 |
| `stock flow` | `ctx.capital_distribution()` + `ctx.capital_flow()` | 资金分布 + 日内流向 |
| `watchlist *` | `ctx.watchlist()` / `ctx.create_watchlist_group()` / `ctx.update_watchlist_group()` / `ctx.delete_watchlist_group()` | 自选股分组管理 |

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

### 5.2 K 线 + 全部指标 (`stk stock history`)

```
stk stock history 600519 --count 10
  → commands/stock.py: history()
  → services/indicator.py: get_daily(symbol, count=10)
    → get_history(count=10+60) → 拉取 70 根 K 线（60 根用于指标预热）
    → 在同一 DataFrame 上计算全部指标（EMA/MACD/RSI/KDJ/BOLL/ATR）
    → 合并 OHLCV + 涨跌幅 + 全部指标为逐日扁平数据
    → 截取最近 count 天，按新到旧排列
  → models/indicator.py: DailyResult(symbol, days[])
```

每日数据结构（扁平 dict）：

- K 线：date, open, high, low, close, volume, turnover, change_pct
- EMA：EMA5, EMA10, EMA20, EMA60
- MACD：MACD, signal, hist
- RSI：RSI
- KDJ：K, D, J
- BOLL：upper, middle, lower
- ATR：ATR14

### 5.3 单指标查询 (`stk stock indicator`)

```
stk stock indicator 600519 MACD --count 60
  → services/indicator.py: calc_indicator(symbol, "MACD", count=60)
    → get_history() → pandas DataFrame
    → talib.MACD(close, 12, 26, 9) → macd, signal, hist
  → models/indicator.py: IndicatorResult(symbol, indicator, params, values)
```

支持的指标：EMA, MACD, RSI, KDJ, BOLL, ATR

省略 name 参数时计算全部指标（按指标名分组返回）：

```
stk stock indicator 600519
  → services/indicator.py: calc_all_indicators(symbol, count=10)
  → models/indicator.py: AllIndicatorsResult(symbol, indicators)
```

### 5.4 基本面 (`stk stock fundamental`)

```
stk stock fundamental 600519 --type growth
  → services/fundamental.py: get_comparison(symbol, category="growth")
    → utils/symbol.py: to_em_symbol("600519") → "SH600519"
    → ak.stock_zh_growth_comparison_em("SH600519")
    → DataFrame rows → list[CompanyMetric] (行业中值/平均 + 同行 + 目标股)
  → models/fundamental.py: IndustryComparison(symbol, category, companies)

stk stock valuation 700.HK
  → services/fundamental.py: get_valuation(symbol)
    → ctx.calc_indexes(["700.HK"], [CalcIndex.PeTtmRatio, PbRatio, TotalMarketValue, ...])
    → 返回全量指标：PE/PB/市值/涨跌幅/资金流/换手率/振幅/量比/股息率等
  → models/fundamental.py: Valuation(pe_ttm_ratio, pb_ratio, total_market_value, ...)
```

支持的对比类型：`growth`（成长性）、`valuation`（估值）、`dupont`（杜邦分析，仅 A 股）

### 5.5 市场概览 (`stk market`)

```
stk market index
  → services/market.py: get_indices()
    → ctx.quote(MAJOR_INDICES)  # 7 大指数批量查询
    → MAJOR_INDICES = [000001.SH, 399001.SZ, 399006.SZ, HSI.HK, .IXIC, .DJI, .SPX]
  → models/market.py: list[IndexQuote]

stk market temp
  → services/market.py: get_temperature()
    → ctx.market_temperature(Market.CN)
  → models/market.py: MarketTemperature(score, level, valuation, sentiment)

stk market news --source cls
  → services/news.py: get_global_news(source="cls", count=20)
    → ak.stock_info_global_cls(symbol="全部")
  → models/news.py: list[NewsItem]
```

全局新闻支持数据源：`cls`（财联社）、`ths`（同花顺）

### 5.6 技术选股排名 (`stk stock rank`)

```
stk stock rank --screen lxsz
  → services/rank.py: get_tech_rank(type="lxsz", ma="20日均线")
    → ak.stock_rank_lxsz_ths()
  → models/market.py: TechRank(type="lxsz", label="连续上涨", items[])
```

支持的筛选类型：`lxsz`（连续上涨）、`cxfl`（持续放量）、`xstp`（向上突破）、`ljqs`（量价齐升）

### 5.7 个股资金流 (`stk stock flow`)

```
stk stock flow 600519
  → services/flow.py: get_stock_flow(symbol="600519")
    → to_longport_symbol("600519") → "600519.SH"
    → ctx.capital_distribution("600519.SH") → 大/中/小单进出
    → ctx.capital_flow("600519.SH") → 日内分钟级 inflow
  → models/flow.py: StockFlow(symbol, large_in/out, medium_in/out, small_in/out, intraday[])
```

### 5.8 多指标共振评分 (`stk stock score`)

```
stk stock score 600519
  → commands/stock.py: score()
  → services/score.py: calc_score(symbol, count=60)
    → services/history.get_history() → DataFrame
    → talib.RSI/STOCH/MACD/BBANDS/ATR 逐项计算
    → services/flow.get_stock_flow() → 资金流维度（可选）
  → models/score.py: ScoreResult(total_score, rating, dimensions[], buy_signals[], sell_signals[], atr, stop_loss, take_profit, risk_reward_ratio)
```

评分体系（满分 100）：

| 维度 | 权重 | 判断逻辑 |
|------|------|---------|
| RSI  | 20 | 超卖(<30)满分，超买(>70)0分 |
| KDJ  | 20 | 金叉满分，死叉0分 |
| MACD | 15 | 金叉满分，死叉0分 |
| BOLL | 15 | 下轨反弹满分，触及上轨0分 |
| 量价 | 15 | 放量上涨满分，放量下跌0分 |
| 资金 | 15 | 主力大幅流入满分，大幅流出0分 |

评级：A+(≥85) / A(≥70) / B+(≥60) / B(≥50) / C(<50)

ATR 风控（基于 ATR×2 止损 / ATR×3 止盈）：

```
止损价 = 当前价 - ATR(14) × 2.0
止盈价 = 当前价 + ATR(14) × 3.0
盈亏比 = (止盈价 - 当前价) / (当前价 - 止损价)  # 理论值 ≈ 1.5
```

### 5.9 数据源健康检查 (`stk doctor check`)

```
stk doctor check
  → commands/doctor.py: check()
  → services/health.run_health_check()
    → 检查 Longport API 连通性 + 延迟
  → output.render(results, meta={"healthy": N, "total": M})
```

### 5.10 缓存清除 (`stk cache clear`)

```
stk cache clear [--prefix PREFIX]
  → commands/cache.py: clear(prefix="")
  → store/cache.clear_cache(prefix)
    → 按 prefix 过滤缓存条目（prefix="" 清除全部）
  → output.render({"cleared": N, "prefix": "..."})
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
├── watchlist_groups.json   # 自选股分组 name→id 映射缓存（数据存 longport 服务端）
└── config.json             # 可选：用户偏好配置持久化
```

自选股数据存储在 longport 服务端，本地仅缓存分组名称与 ID 的映射关系，用于 add/remove/delete 操作时快速查找分组 ID。每次 `watchlist list` 时自动同步缓存。存储使用原子写入（tmp 文件 + rename）。

---

## 8. akshare 补充功能

| 功能 | 服务 | akshare API | 数据源 |
|------|------|------------|--------|
| 全局新闻 | `news.get_global_news()` | `stock_info_global_cls/ths` | 财联社/同花顺 |
| 技术选股 | `rank.get_tech_rank()` | `stock_rank_lxsz/cxfl/xstp/ljqs_ths` | 同花顺 |
| 行业对比 | `fundamental.get_comparison()` | `stock_zh_growth/valuation/dupont_comparison_em` | 东方财富（数据中心） |
| 主营业务 | `fundamental.get_profile()` | `stock_zyjs_ths` | 同花顺 |

---

## 9. 服务层文件结构

```
services/
├── rank.py           # 技术选股排名（同花顺）
├── quote.py          # 实时报价（longport）
├── market.py         # 市场概览：indices, temperature
├── flow.py           # 个股资金流（longport capital_distribution + capital_flow）
├── fundamental.py    # 基本面：valuation (calc_indexes), comparison, profile
├── history.py        # K 线历史（供 indicator.py 内部调用）
├── indicator.py      # 技术指标 (ta-lib) + get_daily (OHLCV + 全部指标合并)
├── news.py           # 全局新闻（财联社/同花顺）
├── score.py          # 多指标共振评分 + ATR 风控
├── watchlist.py      # 自选股 CRUD (longport API + 本地 group ID 缓存)
├── longport_quote.py # Longport 原始 API 封装
└── health.py         # 数据源健康检查
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
  - `DataNotFoundError` — 数据不存在

日志使用 `loguru`，输出到 stderr（不干扰 stdout 的 JSON）。
