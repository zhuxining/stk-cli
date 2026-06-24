# stk-cli

Stock Query CLI for Agents — 基于 Typer 构建的 A 股/港股/美股行情查询命令行工具。

## 安装

```bash
# 使用 uv 安装（推荐）
uv sync
uv run stk --help

# 或者直接运行
uv run stk
```

## 环境配置

在项目根目录创建 `.env` 文件：

```env
LONGPORT_APP_KEY=your_app_key
LONGPORT_APP_SECRET=your_app_secret
LONGPORT_ACCESS_TOKEN=your_access_token
```

从 [Longport OpenAPI 控制台](https://open.longportapp.com/account) 获取凭证。注意 access_token 有有效期，过期后需重新获取。

### 同花顺同步（可选）

```env
THS_USERNAME=手机号
THS_PASSWORD=密码
```

## 符号格式

| 市场 | 格式 | 示例 |
|------|------|------|
| A 股主板 | 6 位代码（6 开头自动识别为沪市） | `600519` → `600519.SH` |
| 科创板 | 6 位代码（688 开头） | `688001` → `688001.SH` |
| 深市主板 | 6 位代码（000/001/002 开头） | `000001` → `000001.SZ` |
| 创业板 | 6 位代码（300 开头） | `300750` → `300750.SZ` |
| 北交所 | 6 位代码（8 开头） | `800001` → `800001.BJ` |
| 港股 | 代码.HK | `700.HK`、`9988.HK` |
| 美股 | 代码.US | `AAPL.US`、`TSLA.US` |
| A 股指数 | 代码。交易所 | `000001.SH`（上证）、`399001.SZ`（深证） |
| 港股指数 | 代码.HK | `HSI.HK`（恒生） |
| 美股指数 | .代码 | `.DJI`（道琼斯）、`.IXIC`（纳斯达克）、`.SPX`（标普） |

## 命令结构

按 **市场 → 个股** 两层逻辑组织：

```
stk
├── market      # 市场整体：指数、温度、技术排名、行业多空、候选股
├── stock       # 个股：扫描、K线、同业对比
├── watchlist   # 自选股管理
└── sync        # 跨平台自选股同步
```

---

## market — 市场整体

### index — 主要指数行情

```bash
stk market index
```

一次性获取 7 大指数行情：上证指数、深证成指、创业板指、恒生指数、纳斯达克、道琼斯、标普 500。

### temp — 市场温度

```bash
stk market temp
```

输出字段：`score` (0-100), `level` (描述), `valuation`, `sentiment`

### rank — 技术排名

```bash
stk market rank --screen lxsz
stk market rank --screen cxfl
stk market rank --screen xstp --ma 20日均线
stk market rank --screen ljqs
```

| 参数 | 默认 | 说明 |
|------|------|------|
| `--screen`, `-s` | `lxsz` | `lxsz` / `cxfl` / `xstp` / `ljqs` / `cxsl` / `lxxd` / `xxtp` / `ljqd` |
| `--ma` | `20日均线` | xstp/xxtp 专用均线 |

### hotspot — 行业多空情绪

```bash
stk market hotspot
```

统计各行业在多方/空方 screen 中的出现数量。

### candidates — 技术候选股

```bash
stk market candidates
```

出现在 3+ 个多方 screen 且无空方冲突的股票。

---

## stock — 个股查询

### quote — 实时报价

```bash
# A 股
stk stock quote 600519

# 港股
stk stock quote 700.HK

# 美股
stk stock quote AAPL.US

# 指数
stk stock quote 000001.SH --type index
```

输出字段：`symbol`, `name`, `last`, `open`, `high`, `low`, `prev_close`, `change`, `change_pct`, `volume`, `turnover`, `timestamp`

### profile — 公司概况

```bash
stk stock profile 600519
```

输出字段：`symbol`, `main_business`（主营业务）, `product_type`（产品类型）, `product_name`（产品名称）, `business_scope`（经营范围）

### comparison — 同业业绩对比

```bash
# 成长能力对比
stk stock comparison 600519 --type growth

# 估值对比
stk stock comparison 600519 --type valuation

# 杜邦分析（仅 A 股）
stk stock comparison 600519 --type dupont

# 港股成长能力
stk stock comparison 700.HK --type growth
```

**参数：**

- `--type`, `-t`：分析类型，可选 `growth`（成长能力）/ `valuation`（估值对比）/ `dupont`（杜邦分析，仅 A 股），默认 `growth`

输出字段：`symbol`, `category`, `companies[]`（同业公司指标对比）

### valuation — 估值指标

```bash
stk stock valuation 600519
stk stock valuation 700.HK
stk stock valuation AAPL.US
```

输出字段：`symbol`, `pe`, `pb`, `market_cap`, `total_shares`, `float_shares`

### indicator — 技术指标

```bash
# 均线
stk stock indicator 600519 MA
stk stock indicator 600519 EMA

# MACD
stk stock indicator 600519 MACD

# RSI
stk stock indicator 700.HK RSI

# KDJ
stk stock indicator AAPL.US KDJ

# 布林带
stk stock indicator 600519 BOLL

# 指定更多数据点
stk stock indicator 600519 MACD --count 120 --period day
```

**支持的指标：**

| 指标 | 说明 | 输出字段 |
|------|------|----------|
| MA | 简单移动平均 | MA{period} |
| EMA | 指数移动平均 | EMA{period} |
| MACD | 指数平滑异同移动平均 | MACD, signal, hist |
| RSI | 相对强弱指数 | RSI |
| KDJ | 随机指标 | K, D, J |
| BOLL | 布林带 | upper, middle, lower |

**参数：**

- `--period`, `-p`：K 线周期，可选 `day`（默认）/ `week` / `month`
- `--count`, `-c`：数据点数量，默认 60

### history — 历史 K 线

```bash
# 默认：最近 30 根日 K
stk stock history 600519

# 指定周期和数量
stk stock history 700.HK --period week --count 20
stk stock history AAPL.US --period month --count 12

# 指数 K 线
stk stock history 000001.SH --type index --period day --count 60
```

**参数：**

- `--period`, `-p`：K 线周期，可选 `day`（默认）/ `week` / `month`
- `--count`, `-c`：K 线数量，默认 30
- `--type`, `-t`：目标类型，默认 `stock`，指数用 `index`

输出字段：`date`, `open`, `high`, `low`, `close`, `volume`, `turnover`

---

## watchlist — 自选股管理

本地管理自选股列表，存储在 `~/.stk/watchlist.json`。

```bash
# 查看所有列表
stk watchlist list

# 创建列表
stk watchlist create mywatchlist

# 查看指定列表
stk watchlist show my-hk

# 添加股票
stk watchlist add my-hk 700.HK
stk watchlist add a-stock 600519

# 删除股票
stk watchlist remove my-hk 700.HK

# 删除列表
stk watchlist delete mywatchlist
```

---

## sync — 跨平台自选股同步

将长桥自选分组同步到其他平台。当前支持同花顺（雪球待后续支持）。

### sync ths list — 列出同花顺分组

```bash
stk sync ths list
```

### sync ths diff — 对比差异

```bash
# 对比长桥分组与同花顺同名分组
stk sync ths diff -f "重点关注"

# 指定不同目标分组名
stk sync ths diff -f "重点关注" -t "自选"
```

### sync ths push — 推送同步

```bash
# 仅追加（不删除目标端已有标的）
stk sync ths push -f "重点关注"

# 指定目标分组
stk sync ths push -f "重点关注" -t "同花顺自选"

# 全量覆盖（删除目标端多余标的再写入）
stk sync ths push -f "重点关注" --replace
```

**推送规则：**

- 默认仅追加：长桥全量标的追加到同花顺，不删除目标端已有标的
- `--replace` 模式：先删除目标端不在源端的标的，再写入源端全量
- 目标分组不存在时自动创建
- 自动跳过指数等不支持品种
- 科创板自动转换：`688xxx.SH`（长桥）→ `688xxx.KC`（同花顺）
- 创业板自动转换：`300xxx.SZ`（长桥）→ `300xxx.CYB`（同花顺）
- 只读分组（同花顺动态板块）不可写入

### sync ths pull — 拉取同步

```bash
# 仅追加（不删除目标端已有标的；LP Add 模式天然去重）
stk sync ths pull -f "重点关注"

# 指定目标长桥分组
stk sync ths pull -f "同花顺组" -t "长桥组"

# 全量覆盖（原子 Replace API）
stk sync ths pull -f "重点关注" --replace
```

**拉取规则：**

- 默认仅追加：同花顺全量标的追加到长桥（LP Add 模式天然去重），不删除目标端已有标的
- `--replace` 模式：原子 Replace API 全量替换长桥分组
- 目标长桥分组不存在时自动创建
- 科创板自动转换：`688xxx.KC`（同花顺）→ `688xxx.SH`（长桥）
- 创业板自动转换：`300xxx.CYB`（同花顺）→ `300xxx.SZ`（长桥）

---

## 输出格式

所有命令输出统一的 JSON envelope 格式：

```json
{
  "ok": true,
  "data": { ... },
  "error": null,
  "meta": { "source": "auto", "count": 30 }
}
```

错误时：

```json
{
  "ok": false,
  "data": null,
  "error": {
    "type": "SourceError",
    "message": "描述信息"
  }
}
```

---

## 数据来源

| 功能 | 数据来源 |
|------|----------|
| 个股/指数报价 | Longport（全市场） |
| K 线历史 | Longport（全市场） |
| 技术指标 | ta-lib（基于 K 线计算） |
| 估值指标 | Longport |
| 同业对比 | akshare（A 股/港股） |
| 公司概况 | akshare（A 股） |
| 市场温度 | Longport |

---

## 技术栈

- **Python 3.14** + **uv**
- **Typer** (CLI 框架)
- **Pydantic** (数据模型)
- **longport** (主数据源，全市场)
- **akshare** (A 股特色数据)
- **ta-lib** (技术指标计算)
- **pandas** (数据处理)

---

## 开发

```bash
# 同步依赖
uv sync

# 运行 CLI
uv run stk

# 代码检查
uv run ruff check .
uv run ruff format .

# 类型检查
uv run ty check

# 运行测试
uv run pytest
uv run pytest -m "not integration"  # 排除外部 API 调用
```

## 架构

```
src/stk/
├── cli.py              # Typer 入口
├── commands/           # 命令层（参数解析 → 服务调用 → 输出）
│   ├── market.py
│   ├── stock.py
│   ├── sync.py         # 跨平台自选同步
│   └── watchlist.py
├── services/           # 服务层（业务逻辑 + API 调用）
│   ├── comparison.py
│   ├── health.py
│   ├── history.py
│   ├── indicator.py
│   ├── live_scan.py
│   ├── market.py
│   ├── quote.py
│   ├── rank.py
│   ├── scan.py
│   ├── score.py
│   ├── sync.py         # 同步编排逻辑
│   ├── ths_wrapper.py  # 同花顺 API 薄封装
│   └── watchlist.py
├── models/             # 数据模型（Pydantic）
│   ├── sync.py         # 同步数据契约
│   └── ...
├── utils/              # 工具函数
│   ├── symbol.py       # 符号转换（含同花顺格式）
│   └── price.py        # 价格格式化
└── store/              # 本地存储 (~/.stk/)
```

## License

MIT
