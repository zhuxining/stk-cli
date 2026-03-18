# 命令速查

通过 `uv run stk <子命令>` 执行（已安装则直接用 `stk`）。所有命令输出 JSON 信封 `{"ok": true, "data": ...}`，解析 `data` 字段。

## 市场

| 命令 | 用途 |
|------|------|
| `stk market index` | 主要指数行情 |
| `stk market temp` | 市场温度 (0-100) |
| `stk market breadth` | 涨跌统计（上涨/下跌/涨停/跌停） |
| `stk market news` | 全球市场新闻。`--source cls\|ths\|em` `--filter 全部\|重点` `--count N` |

## 板块

| 命令 | 用途 |
|------|------|
| `stk board list` | 板块排行。`--type sector\|concept` |
| `stk board cons <名称>` | 板块成分股。`--type sector\|concept` |
| `stk board flow <名称>` | 板块资金流向历史。`--type sector\|concept` |
| `stk board detail <名称>` | 板块内个股资金明细（仅行业板块）。`--period 今日\|5日\|10日` |

## 个股

| 命令 | 用途 |
|------|------|
| `stk stock rank` | 排行。`--type hot\|tech\|flow`；tech: `--screen lxsz\|cxfl\|xstp\|ljqs` `--ma`；flow: `--scope stock\|main\|sector\|concept` `--period 今日\|3日\|5日\|10日` `--market` |
| `stk stock quote <代码>` | 实时行情。`--type stock\|index\|sector\|concept` |
| `stk stock profile <代码>` | 公司主营简介 |
| `stk stock fundamental <代码>` | 行业对比。`--type growth\|valuation\|dupont` |
| `stk stock valuation <代码>` | PE/PB/PS/市值 |
| `stk stock history <代码>` | OHLCV + 全部技术指标（合并输出）。`--type stock\|index\|sector\|concept` `--period day\|week\|month` `--count N` |
| `stk stock indicator <代码> [指标名]` | 技术指标。省略指标名则计算全部 (EMA/MACD/RSI/KDJ/BOLL/ATR)。`--type stock\|index\|sector\|concept` `--period day\|week\|month` `--count N` `--timeperiod N` |
| `stk stock news <代码>` | 个股新闻。`--count N` |
| `stk stock flow <代码>` | 个股资金流向（实时 + 近期历史） |
| `stk stock chip <代码>` | 筹码分布（仅A股） |
| `stk stock score <代码>` | 多指标共振评分 (0-100)。`--count N` 历史数据量 |

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
