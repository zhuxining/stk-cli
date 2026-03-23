# 命令速查

## Market

### `stk market`

市场概览：9 大指数按 CN/HK/US 分组 + 三市场温度。

返回 `MarketOverview`:

- `indices`: `{region: [IndexQuote]}` — 含 symbol/name/last/change/change_pct
- `temperature`: `{region: {score, level}}` — score(0-100), level(冰点~沸点)

### `stk market news`

全局新闻，默认合并 cls+ths 按时间倒序。

| 参数 | 默认 | 说明 |
|------|------|------|
| `--source` | all | all/cls/ths |
| `--count` | 20 | 条数 |
| `--filter` | 全部 | cls 专用：全部/重点 |

返回 `list[NewsItem]`: title/summary/published_at/source/url

---

## Stock

### `stk stock rank`

技术选股排名（同花顺）。

| 参数 | 默认 | 说明 |
|------|------|------|
| `--screen` | all | all / 上涨: lxsz/cxfl/xstp/ljqs / 下跌: cxsl/lxxd/xxtp/ljqd |
| `--ma` | 20日均线 | xstp/xxtp 专用 |

- `--screen all` → `TechHotspot`: industries[IndustryStats] + candidates[TechCandidate] + total_candidates
- `--screen <单个>` → `TechRank(type, label, items[])`

### `stk stock scan <symbols...>`

批量综合分析：quote + score + valuation + profile。

返回 `ScanResult(group_name, total, items[ScanItem])`。ScanItem 含：

- 行情: symbol/name/last/change_pct
- 评分: score/signals[]/score_detail{}
- 估值: pe_ttm/pb/dividend_yield
- 量能: volume_ratio/turnover_rate/amplitude
- 区间: change_5d/change_10d/ytd_change_rate
- 趋势风控: adx/atr/stop_loss/take_profit/risk_reward_ratio
- 资金: capital_flow（万元）
- 主营: main_business

### `stk stock kline <symbols...>`

K 线 + 全部技术指标。

| 参数 | 默认 | 说明 |
|------|------|------|
| `--type` | stock | stock/index |
| `--period` | day | day/week/month |
| `--count` | 20 | K 线天数 |

返回每日: OHLCV + EMA(5/10/20/60) + MACD(macd/signal/hist) + RSI + KDJ(K/D/J) + BOLL(upper/middle/lower) + ATR14

### `stk stock fundamental <symbol>`

同业对比。

| 参数 | 默认 | 说明 |
|------|------|------|
| `--type` | all | all/growth/valuation/dupont(仅A股) |

返回 `FullComparison(symbol, comparisons[IndustryComparison])`，每个含 companies[{code, name, metrics{}}]

---

## Watchlist

CRUD: `list` | `show <name>` | `create <name> [--symbol S ...]` | `add <name> <symbols...>` | `remove <name> <symbols...>` | `delete <name>`

### `stk watchlist scan <name>`

批量扫描全组（同 stock scan），`--sort score|change_pct`（默认 score）。

### `stk watchlist kline <name>`

全组 K 线 + 全部技术指标（并行），`--period`/`--count` 同 stock kline。

---

## Tools

- `stk doctor check [--quick]` — 数据源健康检查
- `stk cache clear [--prefix PREFIX]` — 缓存清除
