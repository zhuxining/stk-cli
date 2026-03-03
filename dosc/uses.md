# stk-cli 使用指南

## 安装

```bash
# 安装依赖
uv sync

# 验证安装
uv run stk --help
```

## 环境配置

在项目根目录创建 `.env` 文件：

```env
LONGPORT_APP_KEY=your_app_key
LONGPORT_APP_SECRET=your_app_secret
LONGPORT_ACCESS_TOKEN=your_access_token
```

从 [Longport OpenAPI 控制台](https://open.longportapp.com/account) 获取凭证。注意 access_token 有有效期，过期后需重新获取。

## Symbol 格式

| 市场 | 格式 | 示例 |
|------|------|------|
| A 股 | 6 位代码（自动识别交易所） | `600519`、`000001`、`300750` |
| A 股（完整） | 代码.交易所 | `600519.SH`、`000001.SZ` |
| 港股 | 代码.HK | `700.HK`、`9988.HK` |
| 美股 | 代码.US | `AAPL.US`、`TSLA.US` |
| A 股指数 | 代码.交易所 | `000001.SH`（上证）、`399001.SZ`（深证） |
| 港股指数 | 代码.HK | `HSI.HK`（恒生） |
| 美股指数 | .代码 | `.DJI`（道琼斯）、`.IXIC`（纳斯达克）、`.SPX`（标普） |

## 命令总览

```
stk
├── quote       实时行情
├── history     历史 K 线
├── indicator   技术指标
├── fundamental 基本面数据
├── market      市场概览
├── flow        资金流向
├── chip        筹码分布（待实现）
├── news        新闻资讯（待实现）
└── watchlist   自选股管理
```

---

## quote — 实时行情

获取个股或指数的实时行情数据。

```bash
# A 股
stk quote get 600519
stk quote get 000001

# 港股
stk quote get 700.HK

# 美股
stk quote get AAPL.US

# 指数
stk quote get 000001.SH --type index
stk quote get .DJI --type index
```

输出字段：symbol, name, last, open, high, low, prev_close, change, change_pct, volume, turnover, timestamp

---

## history — 历史 K 线

获取历史 K 线数据，支持日/周/月周期。

```bash
# 默认：最近 30 根日 K
stk history get 600519

# 指定周期和数量
stk history get 700.HK --period week --count 20
stk history get AAPL.US --period month --count 12

# 指数 K 线
stk history get 000001.SH --type index --period day --count 60
```

**参数：**

- `--period`, `-p`：K 线周期，可选 `day`（默认）/ `week` / `month`
- `--count`, `-c`：K 线数量，默认 30

输出字段：date, open, high, low, close, volume, turnover

---

## indicator — 技术指标

基于历史 K 线计算技术指标（ta-lib）。

```bash
# 均线
stk indicator get 600519 MA
stk indicator get 600519 EMA

# MACD
stk indicator get 600519 MACD

# RSI
stk indicator get 700.HK RSI

# KDJ
stk indicator get AAPL.US KDJ

# 布林带
stk indicator get 600519 BOLL

# 指定更多数据点
stk indicator get 600519 MACD --count 120 --period day
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

- `--period`, `-p`：K 线周期，默认 `day`
- `--count`, `-c`：数据点数量，默认 60

---

## fundamental — 基本面数据

### valuation — 估值指标

```bash
stk fundamental valuation 700.HK
stk fundamental valuation 600519
stk fundamental valuation AAPL.US
```

输出字段：symbol, pe, pb, market_cap, total_shares, float_shares

### report — 财务报表（待实现）

```bash
stk fundamental report 600519 --type income --period 2025Q3
```

### dividend — 分红记录（待实现）

```bash
stk fundamental dividend 700.HK
```

---

## market — 市场概览

### index — 主要指数行情

```bash
stk market index
```

一次性获取 7 大指数行情：上证指数、深证成指、创业板指、恒生指数、纳斯达克、道琼斯、标普 500。

### temperature — 市场温度

```bash
stk market temperature
```

输出字段：score (0-100), level (描述), valuation, sentiment

### breadth — 市场广度（待实现）

```bash
stk market breadth
```

---

## flow — 资金流向

获取个股的资金分布（大/中/小单）和日内分钟级资金流向。

```bash
# 个股资金流向
stk flow get 600519
stk flow get 700.HK
stk flow get AAPL.US
```

输出字段：

- 资金分布：large_in, large_out, medium_in, medium_out, small_in, small_out
- 日内流向：intraday (timestamp, inflow 列表)

---

## watchlist — 自选股管理

本地管理自选股列表，存储在 `~/.stk/watchlist.json`。

```bash
# 查看所有列表
stk watchlist list

# 查看指定列表
stk watchlist show my-hk

# 添加股票
stk watchlist add my-hk 700.HK
stk watchlist add a-stock 600519

# 删除股票
stk watchlist remove my-hk 700.HK
```

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

## 待实现功能

以下功能 Longport API 不支持，待后续接入 akshare：

| 功能 | 命令 |
|------|------|
| 新闻资讯 | `stk news list` |
| 筹码分布 | `stk chip cost` |
| 股东变动 | `stk chip holder` |
| 市场广度 | `stk market breadth` |
| 财务报表 | `stk fundamental report` |
| 分红记录 | `stk fundamental dividend` |
| 板块/概念行情 | `stk quote get --type sector/concept` |
| 板块资金流向 | `stk flow get --type sector` |
