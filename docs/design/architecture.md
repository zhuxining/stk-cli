# stk-cli 架构设计（补充）

> 基础架构信息（目录结构、层级职责、开发命令）见 `CLAUDE.md`。本文档仅记录深度设计决策。

## 1. 命令结构

按 **市场 → 个股 → 自选股** 三层逻辑组织：

```
stk
├── market            # 市场整体：指数(CN/HK/US分组) + 温度 + 新闻
├── stock             # 个股：scan(综合分析), kline(K线+指标), fundamental, rank
├── watchlist         # 自选股：CRUD + scan + kline
├── doctor            # 数据源健康检查
└── cache             # 缓存管理
```

### 命令与服务映射

| 命令 | 服务层文件 | 说明 |
|------|-----------|------|
| `stk market` | `services/market.get_market_overview()` | CN/HK/US 指数分组 + 三市场温度 |
| `stk market news` | `services/news.get_all_news()` | 全局新闻（默认 cls+ths 合并；`--source` 可单查） |
| `stk stock scan` | `services/scan.batch_summary()` | 综合分析：quote+score+valuation（多 symbol） |
| `stk stock kline` | `services/indicator.get_daily()` | K 线 + 全部技术指标（多 symbol） |
| `stk stock fundamental` | `services/fundamental.get_full_comparison()` | 同业对比（默认全部 category；`--type` 可单查） |
| `stk stock rank` | `services/rank.get_tech_hotspot()` | 技术热点（默认行业分析+交叉验证选股；`--screen` 可单查） |
| `stk watchlist list` | `services/watchlist.list_watchlists()` | 列出所有分组 |
| `stk watchlist show` | `services/watchlist.get_watchlist()` | 查看分组内标的 |
| `stk watchlist create` | `services/watchlist.create_group()` | 创建分组 |
| `stk watchlist add` | `services/watchlist.add_symbols()` | 批量添加标的到分组 |
| `stk watchlist remove` | `services/watchlist.remove_symbols()` | 批量从分组移除标的 |
| `stk watchlist delete` | `services/watchlist.delete_group()` | 删除分组 |
| `stk watchlist scan` | `services/scan.scan_watchlist()` | 批量扫描全组：quote+score+valuation |
| `stk watchlist kline` | `services/scan.kline_watchlist()` | 全组 K 线 + 全部技术指标（并行） |
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
    STOCK = "stock"  # 个股（默认）
    SECTOR = "sector"  # 行业板块
    CONCEPT = "concept"  # 概念板块
    INDEX = "index"  # 指数
```

### 各类型支持矩阵

| 命令 | stock | index | sector | concept | 多 symbol |
|------|-------|-------|--------|---------|-----------|
| `stock scan` | ✅ | ❌ | ❌ | ❌ | ✅（全量批量） |
| `stock kline` | ✅ | ✅ | ❌ | ❌ | ✅ |
| `stock fundamental` | ✅ | ❌ | ❌ | ❌ | ❌ |
| `stock rank` | ✅ | ❌ | ❌ | ❌ | — |

---

## 4. Longport SDK API 使用映射

| stk 命令 | Longport API | 返回类型 |
|----------|-------------|----------|
| `market` | `ctx.quote(MAJOR_INDICES)` + `ctx.market_temperature(Market.CN/HK/US)` | 分组指数行情 + 三市场温度 |
| `stock scan` | `ctx.quote()` + `ctx.calc_indexes()` | 实时行情 + 估值指标（批量） |
| `stock kline` | `ctx.candlesticks(symbol, period, count, adjust)` | K 线 + 全部技术指标 |
| `watchlist *` | `ctx.watchlist()` / `ctx.create_watchlist_group()` / `ctx.update_watchlist_group()` / `ctx.delete_watchlist_group()` | 自选股分组管理 |

---

## 5. 命令数据流

### 5.1 市场概览 (`stk market`)

```
stk market
  → commands/market.py: market_overview() (callback, invoke_without_command)
  → services/market.py: get_market_overview()
    → get_indices(): ctx.quote(9 大指数) → 按 CN/HK/US 分组
      → CN: 000001.SH, 399001.SZ, 399006.SZ
      → HK: HSI.HK, HSCEI.HK, HSTECH.HK
      → US: .IXIC, .DJI, .SPX
    → _get_temperature_for_market("CN"/"HK"/"US") × 3
  → models/market.py: MarketOverview(indices, temperature)

stk market news
  → services/news.py: get_all_news(count=20)
    → 串行调用 get_global_news(source="cls") + get_global_news(source="ths")（间隔 1-3s）
    → 合并按时间倒序，截取 count 条
  → models/news.py: list[NewsItem]

stk market news --source cls
  → services/news.py: get_global_news(source="cls", count=20)
  → models/news.py: list[NewsItem]
```

### 5.2 综合分析 (`stk stock scan`)

```
stk stock scan 600519 700.HK
  → commands/stock.py: scan()
  → services/scan.py: batch_summary(symbols)
    → _batch_analyze(symbols, names):
      1. get_realtime_quotes(symbols)      → 1 次批量 API
      2. get_valuations(symbols)           → 1 次批量 API (calc_indexes)
      3. ThreadPoolExecutor(max_workers=8)
         ├─ calc_score(symbol) × N         → 并行
         └─ get_profile(symbol) × N        → 并行 + 7天磁盘缓存
      4. 合并 quote + valuation + score + profile → ScanItem[]
  → models/scan.py: ScanResult(group_name, total, items[])
```

### 5.3 K 线 + 全部指标 (`stk stock kline`)

```
stk stock kline 600519 --count 10
  → commands/stock.py: kline()
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

### 5.4 基本面 (`stk stock fundamental`)

```
stk stock fundamental 600519
  → services/fundamental.py: get_full_comparison(symbol)
    → 串行调用 get_comparison(symbol, category) × 3（间隔 1-3s 防风控）
      → categories: growth, valuation, dupont（港股无 dupont）
    → 每个 category: ak.stock_zh_{cat}_comparison_em() → IndustryComparison
  → models/fundamental.py: FullComparison(symbol, comparisons[])

stk stock fundamental 600519 --type growth
  → services/fundamental.py: get_comparison(symbol, category="growth")
  → models/fundamental.py: IndustryComparison(symbol, category, companies)
```

支持的对比类型：`growth`（成长性）、`valuation`（估值）、`dupont`（杜邦分析，仅 A 股）

### 5.5 技术选股排名 (`stk stock rank`)

```
stk stock rank
  → services/rank.py: get_tech_hotspot(ma="20日均线")
    → 串行调用 get_tech_rank(type=screen) × 8（间隔 1-3s 防风控）
    → 行业分析：6 个有"所属行业"的 screen 统计行业多空出现频次
    → 技术选股：4 个多方 screen 交叉验证，取 2+ screen 重叠的候选
  → models/market.py: TechHotspot(industries[], candidates[], total_candidates)

stk stock rank --screen lxsz
  → services/rank.py: get_tech_rank(type="lxsz", ma="20日均线")
    → ak.stock_rank_lxsz_ths()
  → models/market.py: TechRank(type="lxsz", label="连续上涨", items[])
```

支持的筛选类型（上涨）：`lxsz`（连续上涨）、`cxfl`（持续放量）、`xstp`（向上突破）、`ljqs`（量价齐升）
支持的筛选类型（下跌）：`cxsl`（连续下跌）、`lxxd`（持续缩量）、`xxtp`（向下突破）、`ljqd`（量价齐跌）

### 5.6 多指标共振评分 (内部，被 scan 调用)

```
calc_score(symbol, count=60)
  → services/score.py: calc_score(symbol, count=60)
    → services/history.get_history() → DataFrame
    → talib 计算: EMA/RSI/STOCH/MACD/BBANDS/ADX/ATR
    → services/flow.get_stock_flow() → 资金流维度（个股独有）
  → models/score.py: ScoreResult(total_score, rating, dimensions[], buy_signals[], sell_signals[], trend_strength, adx, atr, stop_loss, take_profit, risk_reward_ratio)
```

评分体系（满分 100）：

**个股维度**（7 维，直接加总 = 100）：

| 维度 | 权重 | 判断逻辑 |
|------|------|---------|
| 动量 | 15 | RSI(60%) + KDJ(40%) 加权合并。RSI 超卖满分，超买 0 分；KDJ 金叉满分，死叉 0 分 |
| MACD | 15 | 金叉满分，死叉 0 分，柱翻红/翻绿中间分 |
| BOLL | 15 | 下轨反弹满分，触及上轨 0 分 |
| 量价 | 10 | 放量上涨满分，放量下跌 0 分 |
| 趋势 | 20 | EMA(5/10/20/60) 多头排列满分，空头排列 0 分 |
| 背离 | 10 | MACD 柱状图底背离满分，顶背离 0 分 |
| 资金 | 15 | 主力大幅流入满分，大幅流出 0 分 |

**ETF 维度**（6 维，加总 85 → 归一化至 100）：

| 维度 | 权重 | 说明 |
|------|------|------|
| 动量 | 10 | 同上，权重略低 |
| MACD | 15 | 同上 |
| BOLL | 15 | 同上 |
| 量价 | 10 | 同上 |
| 趋势 | 25 | 权重更高，ETF 趋势性更强 |
| 背离 | 10 | 同上 |

**ADX 趋势强度标签**：ADX ≥ 25 → "trending"，< 25 → "ranging"（辅助判断，不参与评分）

ATR 风控（基于 ATR×2 止损 / ATR×3 止盈）：

```
止损价 = 当前价 - ATR(14) × 2.0
止盈价 = 当前价 + ATR(14) × 3.0
盈亏比 = (止盈价 - 当前价) / (当前价 - 止损价)  # 理论值 ≈ 1.5
```

### 5.7 自选股扫描与 K 线 (`stk watchlist scan` / `stk watchlist kline`)

```
stk watchlist scan ETF
  → services/scan.py: scan_watchlist(name, sort)
    → get_watchlist(name) → symbols
    → _batch_analyze(symbols, names)  # 同 stock scan 流程
  → models/scan.py: ScanResult(group_name, total, items[])

stk watchlist kline ETF
  → services/scan.py: kline_watchlist(name, period, count)
    → get_watchlist(name) → symbols
    → ThreadPoolExecutor(max_workers=8)
       └─ get_daily(symbol) × N  → 并行
  → list[DailyResult]
```

**性能优化**：

- `get_valuations()` 原生批量：N 个 symbol 仅 1 次 API 调用
- `calc_score()` 并行：30 只股票从 ~30s → ~4s
- `kline_watchlist()` 并行获取所有成员 K 线

### 5.8 数据源健康检查 (`stk doctor check`)

```
stk doctor check
  → commands/doctor.py: check()
  → services/health.run_health_check()
    → 检查 Longport API 连通性 + 延迟
  → output.render(results, meta={"healthy": N, "total": M})
```

### 5.9 缓存清除 (`stk cache clear`)

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
├── market.py         # 市场概览：indices (CN/HK/US) + temperature × 3
├── fundamental.py    # 基本面：valuation (批量 calc_indexes), comparison, profile
├── history.py        # K 线历史（供 indicator.py 内部调用）
├── indicator.py      # 技术指标 (ta-lib) + get_daily (OHLCV + 全部指标合并)
├── news.py           # 全局新闻（财联社/同花顺）
├── score.py          # 多指标共振评分 + ATR 风控
├── scan.py           # 批量分析核心：_batch_analyze() + scan + kline_watchlist
├── watchlist.py      # 自选股 CRUD (longport API + 本地 group ID 缓存)
├── quote.py # Longport 原始 API 封装
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
