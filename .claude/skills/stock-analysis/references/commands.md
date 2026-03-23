# 命令速查

所有命令输出 JSON 信封 `{"ok": true, "data": ..., "meta": ...}`，从 `data` 字段解析结果。

通过 `uv run stk <子命令>` 执行（已安装则直接用 `stk`）。

---

## Market

### `stk market`

市场概览：9 大指数按 CN/HK/US 分组 + 三市场温度。

返回 `MarketOverview`:

- `indices`: `{"CN": [...], "HK": [...], "US": [...]}` — 每个 IndexQuote 含 symbol/name/last/change/change_pct
- `temperature`: `{"CN": ..., "HK": ..., "US": ...}` — 每个含 score(0-100)/level(冰点~沸点)

### `stk market news`

全局新闻。**默认合并 cls + ths 两个源，按时间倒序。**

| 参数 | 默认 | 说明 |
|------|------|------|
| `--source` | all | all/cls（财联社）/ths（同花顺） |
| `--count` | 20 | 条数 |
| `--filter` | 全部 | cls 专用：全部/重点 |

返回 `list[NewsItem]`，每条含 title/summary/published_at/source/url。

---

## Stock

### `stk stock rank`

技术选股排名（同花顺）。**默认返回行业多空分析 + 交叉验证候选股。**

| 参数 | 默认 | 说明 |
|------|------|------|
| `--screen` | all | all / 上涨: lxsz(连续上涨)/cxfl(持续放量)/xstp(向上突破)/ljqs(量价齐升) / 下跌: cxsl(连续下跌)/lxxd(持续缩量)/xxtp(向下突破)/ljqd(量价齐跌) |
| `--ma` | 20日均线 | xstp/xxtp 专用 |

- `--screen all` → 返回 `TechHotspot`:
  - `industries[]`: 行业多空统计（IndustryStats: industry/bull_count/bear_count/bull_screens/bear_screens），按 bull_count 降序。bull_screens/bear_screens 为中文（如 "连续上涨"/"持续缩量"）
  - `candidates[]`: 交叉验证候选股（TechCandidate: code/name/bull_screens/bear_screens），出现在 2+ 个多方 screen，bear_screens 标记空方冲突。screen 名称同为中文
  - `total_candidates`: 候选股总数
- `--screen <单个>` → 返回 `TechRank(type, label, items[])`
  - 每个 item: code/name/metrics(dict)

### `stk stock scan <symbols...>`

批量综合分析：quote + score + valuation + profile。接受多个 symbol。

返回 `ScanResult(group_name, total, items[])`，每个 ScanItem 含：

| 字段 | 说明 |
|------|------|
| symbol, name, last, change_pct | 基础行情 |
| score, signals[], score_detail{} | 评分 + 信号 + 各维度明细 |
| pe_ttm, pb, dividend_yield | 估值 |
| volume_ratio, turnover_rate, amplitude | 量能 |
| change_5d, change_10d, ytd_change_rate | 区间涨跌 |
| adx, atr, stop_loss, take_profit, risk_reward_ratio | 趋势 + ATR 风控 |
| capital_flow | 资金流（万元） |
| main_business | 主营业务 |

### `stk stock kline <symbols...>`

K 线 + 全部技术指标。接受多个 symbol。

| 参数 | 默认 | 说明 |
|------|------|------|
| `--type` | stock | stock/index |
| `--period` | day | day/week/month |
| `--count` | 10 | K 线天数 |

返回每日扁平数据：

- K 线：date, open, high, low, close, volume, turnover, change_pct
- EMA：EMA5, EMA10, EMA20, EMA60
- MACD：MACD, signal, hist
- RSI：RSI
- KDJ：K, D, J
- BOLL：upper, middle, lower
- ATR：ATR14

### `stk stock fundamental <symbol>`

同业对比。**默认返回全部 category。**

| 参数 | 默认 | 说明 |
|------|------|------|
| `--type` | all | all/growth(成长性)/valuation(估值)/dupont(杜邦，仅A股) |

- `--type all` → 返回 `FullComparison(symbol, comparisons[])`
  - 每个 IndustryComparison: symbol/category/companies[]
  - 每个 CompanyMetric: code/name/metrics{}
- `--type <单个>` → 返回 `IndustryComparison`

---

## Watchlist

### `stk watchlist list`

列出所有自选股分组。

### `stk watchlist show <name>`

查看分组内标的。

### `stk watchlist create <name>`

创建分组。`--symbol S1 --symbol S2 ...` 可指定初始成员。

### `stk watchlist add <name> <symbol>`

添加标的到分组。

### `stk watchlist remove <name> <symbol>`

从分组移除标的。

### `stk watchlist delete <name>`

删除分组。

### `stk watchlist scan <name>`

批量扫描全组（同 stock scan），`--sort score|change_pct`（默认 change_pct）。

### `stk watchlist kline <name>`

全组 K 线 + 全部技术指标（并行），`--period`/`--count` 同 stock kline。

---

## Tools

### `stk doctor check`

数据源健康检查。`--quick` 快速模式。

### `stk cache clear`

缓存清除。`--prefix PREFIX` 按前缀过滤。
