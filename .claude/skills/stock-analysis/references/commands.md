# 命令速查

通过 `uv run stk <子命令>` 执行（已安装则直接用 `stk`）。所有命令输出 JSON 信封 `{"ok": true, "data": ...}`，解析 `data` 字段。

## 市场

| 命令 | 用途 |
|------|------|
| `stk market news` | 全局新闻。`--source cls\|ths` `--count N` |

## 个股

| 命令 | 用途 |
|------|------|
| `stk stock rank` | 技术选股排名（同花顺）。`--screen lxsz\|cxfl\|xstp\|ljqs` |
| `stk stock quote <代码>` | 实时行情。`--type stock\|index` |
| `stk stock profile <代码>` | 公司主营简介 |
| `stk stock fundamental <代码>` | 行业对比。`--type growth\|valuation\|dupont` |
| `stk stock valuation <代码>` | PE/PB/市值等全量指标（via longport calc_indexes） |
| `stk stock history <代码>` | OHLCV + 全部技术指标（合并输出）。`--type stock\|index` `--period day\|week\|month` `--count N` |
| `stk stock indicator <代码> [指标名]` | 技术指标。省略指标名则计算全部 (EMA/MACD/RSI/KDJ/BOLL/ATR)。`--type stock\|index` `--period day\|week\|month` `--count N` `--timeperiod N` |
| `stk stock flow <代码>` | 个股资金流向（大/中/小单进出 + 日内分钟级流向） |
| `stk stock score <代码>` | 多指标共振评分 (0-100) + ATR 风控。`--count N` 历史数据量 |

## 自选

| 命令 | 用途 |
|------|------|
| `stk watchlist list` | 列出所有自选 |
| `stk watchlist show <名称>` | 查看自选股列表 |
| `stk watchlist create <名称>` | 创建自选组。`--symbol S1 --symbol S2` |
| `stk watchlist add <名称> <代码>` | 添加到自选 |
| `stk watchlist remove <名称> <代码>` | 从自选移除 |
| `stk watchlist delete <名称>` | 删除自选组 |

## 工具

| 命令 | 用途 |
|------|------|
| `stk doctor check` | 数据源健康检查。`--quick` 快速模式 |
| `stk cache clear` | 清除缓存。`--prefix PREFIX` 按前缀清除 |
