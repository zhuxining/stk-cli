# stk-cli 架构设计（补充）

> 基础架构信息（目录结构、层级职责、开发命令）见 `CLAUDE.md`。本文档仅记录深度设计决策。

## 1. 标的类型与路由策略

### 标的类型

通过 `--type` 参数区分，默认为 `stock`：

```python
class TargetType(str, Enum):
    STOCK = "stock"       # 个股（默认）
    SECTOR = "sector"     # 行业板块
    CONCEPT = "concept"   # 概念板块
    INDEX = "index"       # 指数
```

### CLI 使用示例

```bash
stk quote get 600519                    # 默认 stock
stk quote get 半导体 --type sector       # 板块行情
stk quote get 华为概念 --type concept     # 概念行情
stk quote get 上证指数 --type index       # 指数行情

stk flow get 600519                     # 个股资金流向
stk flow get 半导体 --type sector         # 板块资金流向

stk history get 600519 --period day     # 个股 K 线
stk history get 上证指数 --type index     # 指数 K 线
```

### 各类型支持的命令矩阵

| 命令 | stock | sector | concept | index |
|------|-------|--------|---------|-------|
| quote | ✅ | ✅ | ✅ | ✅ |
| history | ✅ | ✅ | ✅ | ✅ |
| flow | ✅ | ✅ | ✅ | ❌ |
| chip | ✅ | ❌ | ❌ | ❌ |
| indicator | ✅ | ✅ | ❌ | ✅ |
| fundamental | ✅ | ❌ | ❌ | ❌ |
| news | ✅ | ✅ | ✅ | ❌ |

不支持的组合返回明确错误（如 `stk chip cost 半导体 --type sector` → 错误提示"筹码分布仅支持个股"）。

## 2. 命令详细数据流

### 2.1 新闻资讯 (`stk news`)

```
stk news list 700.HK --count 10
  → services/news.py: get_news(symbol, count)
    → longport: 个股相关新闻（港美股）
    → akshare: 财经新闻、个股新闻（A股，如 stock_news_em）
  → models/news.py: NewsItem(title, source, url, published_at, summary)
  → JSON envelope 输出
```

### 2.2 基本面数据 (`stk fundamental`)

```
stk fundamental report 600519 --type income --period 2025Q3
  → services/fundamental.py: get_financial_report(symbol, report_type, period)
    → akshare: 利润表/资产负债表/现金流量表
  → models/fundamental.py: FinancialReport(...)

stk fundamental valuation 700.HK
  → services/fundamental.py: get_valuation(symbol)
    → longport: 静态信息（总股本、流通股等）
    → akshare: PE/PB/PS 等估值指标
  → models/fundamental.py: Valuation(pe, pb, ps, market_cap, ...)

stk fundamental dividend 700.HK
  → services/fundamental.py: get_dividends(symbol)
    → akshare: 历史分红记录
  → models/fundamental.py: Dividend(ex_date, amount, ...)
```

数据源选择：

- A股基本面数据主要来自 akshare（东方财富、同花顺等接口）
- 港美股基本面通过 longport 静态信息 + akshare 补充

### 2.3 指数与市场温度 (`stk market`)

```
stk market index
  → services/market.py: get_indices()
    → akshare: 国内指数（上证、深证、创业板、科创50 等）
    → longport: 港股恒生指数、美股三大指数
  → models/market.py: IndexQuote(symbol, name, last, change, change_pct, volume)

stk market temperature
  → services/market.py: get_temperature()
    → akshare 聚合计算:
      - 涨跌家数比
      - 涨停/跌停数量
      - 两市成交额
      - 融资融券余额
    → 综合评分算法 → 温度值（0-100，冰点-沸点）
  → models/market.py: MarketTemperature(score, level, details)
    - level: "冰点" / "偏冷" / "中性" / "偏热" / "沸点"
    - details: 各指标明细及其得分

stk market breadth
  → services/market.py: get_breadth()
    → akshare: 涨跌家数、涨跌停统计
  → models/market.py: MarketBreadth(up_count, down_count, limit_up, limit_down, ...)
```

市场温度评分逻辑集中在 `services/market.py`，各因子加权评分，权重可通过配置调整。

### 2.4 资金流向 (`stk flow`)

```
stk flow get 600519
  → services/flow.py: get_flow(symbol, target_type="stock")
    → akshare: 个股主力资金流向（stock_individual_fund_flow）
      - 主力/超大单/大单/中单/小单 净流入
  → models/flow.py: MoneyFlow(symbol, main_net, super_large_net, large_net, ...)

stk flow get 半导体 --type sector
  → services/flow.py: get_flow(name, target_type="sector")
    → akshare: 行业板块资金流向（stock_sector_fund_flow_rank）
  → models/flow.py: SectorFlow(sector, change_pct, main_net, ...)
```

### 2.5 筹码分布 (`stk chip`)

```
stk chip cost 600519
  → services/chip.py: get_chip_distribution(symbol)
    → akshare: 筹码分布数据（stock_cyq_em）
      - 各价位筹码占比、获利比例、平均成本、集中度
  → models/chip.py: ChipDistribution(symbol, avg_cost, profit_ratio, concentration, chips=[...])

stk chip holder 600519
  → services/chip.py: get_holder_change(symbol)
    → akshare: 股东人数变化（stock_hold_num_cninfo）
      - 股东人数、人均持股、户均持股变化
  → models/chip.py: HolderChange(date, holder_count, avg_shares, change_pct, ...)
```

资金流向与筹码分布数据主要来自 akshare（东方财富接口），仅支持 A股。

## 3. 配置项明细

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `LONGPORT_APP_KEY` | longport 应用 Key | — |
| `LONGPORT_APP_SECRET` | longport 应用 Secret | — |
| `LONGPORT_ACCESS_TOKEN` | longport 访问令牌 | — |
| `DATA_DIR` | 本地文件存储目录 | `~/.stk/` |
| `DEFAULT_FORMAT` | 默认输出格式 | `json` |
| `LOG_LEVEL` | 日志级别 | `WARNING` |

## 4. 本地存储格式

```
~/.stk/
├── watchlist.json          # 自选股列表
└── config.json             # 可选：用户偏好配置持久化
```

`watchlist.json` 格式：

```json
{
  "lists": {
    "my-hk": ["700.HK", "9988.HK"],
    "a-stock": ["600519", "000001"]
  }
}
```

## 5. 实现顺序

1. ~~**脚手架**：`cli.py`, `config.py`, `output.py`, `errors.py`, `deps.py` → `stk --help` 可用~~ ✅
2. ~~**模型优先**：`models/common.py` (Envelope), `models/quote.py`~~ ✅
3. **Quote 端到端**：`commands/quote.py` + `services/quote.py` + `services/longport_quote.py`
4. **Akshare 数据源**：`services/akshare_quote.py` + symbol 路由
5. **History**：K 线数据
6. **Indicator**：技术指标（依赖 history）
7. **News**：新闻资讯
8. **Fundamental**：基本面数据（财报、估值、股息）
9. **Market**：指数行情 + 市场温度 + 市场广度
10. **Flow**：资金流向（个股主力、板块）
11. **Chip**：筹码分布（成本分布、股东变动）
12. **Store + Watchlist**：本地 JSON 文件存储 + 自选股管理
