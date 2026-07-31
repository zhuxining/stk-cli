# stk-cli

面向 Agent 和自动化程序的股票数据与分组信号扫描 CLI。

核心能力：

- 从 Longport 请求日、周、月 K 线并计算技术指标。
- 管理 Longport 分组，并与同花顺分组双向同步。
- 扫描 Longport 分组的已确认日线，生成当前买入与卖出信号快照。

所有命令向 stdout 输出统一 JSON envelope，日志写入 stderr。成功或部分成功输出
`ok/status/data/meta`，请求级失败输出 `ok/status/error/meta`，未使用字段不会以
`null` 占位。
本项目只提供数据和信号，不生成交易订单或仓位建议。

## 安装

项目要求 Python 3.14，并使用 uv 管理依赖：

```bash
uv sync
uv run stk --help
```

开发检查：

```bash
make check
```

## 配置

在项目根目录创建 `.env`：

```env
LONGPORT_APP_KEY=your_app_key
LONGPORT_APP_SECRET=your_app_secret
LONGPORT_ACCESS_TOKEN=your_access_token

# 使用同花顺同步时配置
THS_USERNAME=手机号
THS_PASSWORD=密码
```

## 常用工作流

请求 K 线与指标：

```bash
stk data kline 600519
stk data kline 600519,000001 700.HK --period week --count 60
```

管理和同步分组：

```bash
stk group longport list
stk group longport show 核心池
stk group ths list
stk group sync diff 长桥组 同花顺组
stk group sync push 长桥组 同花顺组
stk group sync pull 同花顺组 长桥组 --replace
```

扫描并更新每日信号分组：

```bash
stk scan 核心池
stk scan 核心池 --recent-bars 10 --include-factors
stk group route 核心池 买入信号 卖出信号
```

`scan` 只使用已确认日线。buy 要求 Supertrend 与 EMA 在三根日线内完成双重确认；
sell 在任一指标最近转空时即可预警。两者均只保留三根确认日线。`route` 默认完整刷新
两个 Longport 快照组；个别标的扫描失败不会阻断刷新，失败详情随成功结果返回。

所有输出都包含顶层 `status`：`success` 表示完整成功，`partial` 表示整体已执行但
`data.failures[]` 中存在单项失败，`failed` 表示请求无法执行。`partial` 仍保持
`ok: true`。

## Symbol

- `600519` → `600519.SH`
- `000001` → `000001.SZ`
- `800001` → `800001.BJ`
- 港股使用 `700.HK`
- 美股使用 `AAPL.US`

所有命令支持全局 `--no-cache`，用于单次跳过缓存。

## 进一步阅读

- [架构设计](docs/design/architecture.md)
- [信号规则](docs/design/signal-strategy.md)
- [Agent CLI Skill](docs/skills/stk-cli-reference/SKILL.md)
