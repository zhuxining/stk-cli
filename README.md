# stk-cli

面向 Agent 和自动化程序的股票数据与分组信号扫描 CLI。

核心能力：

- 从 Longport 请求日、周、月 K 线并计算技术指标。
- 管理 Longport 分组，并与同花顺分组双向同步。
- 扫描 Longport 分组的已确认日线，生成当前买入与卖出信号快照。
- 对多个 ETF 来源池独立排名，生成启动、领涨、退潮和落后阶段快照。

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
XUEQIU_UID=浏览器 Cookie 中的 u
XUEQIU_A_TOKEN=浏览器 Cookie 中的 xq_a_token
XUEQIU_ID_TOKEN=浏览器 Cookie 中的 xq_id_token
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
stk group xueqiu list
stk group xueqiu show
stk group xueqiu show 策略池
stk group xueqiu create 策略池
stk group xueqiu add 策略池 600519 000001
stk group xueqiu remove 策略池 600519
stk group xueqiu delete 策略池
stk group sync diff 长桥组 同花顺组
stk group sync push 长桥组 同花顺组
stk group sync pull 同花顺组 长桥组 --replace
stk group sync diff 长桥组 --platform xueqiu
stk group sync push 长桥组 --platform xueqiu
stk group sync pull --platform xueqiu --replace
```

雪球支持默认“我的自选”和股票自定义分组；系统动态分组只读。三个 Cookie 值从已登录
浏览器复制到 `.env`，程序不会保存、刷新或输出这些凭据。省略同步远端组名时使用
“我的自选”。

扫描并更新每日信号分组：

```bash
stk scan 核心池
stk scan 核心池 --recent-bars 10 --include-factors
stk group route 核心池 买入信号 卖出信号
```

`scan` 只使用已确认日线。buy 由最近两根确认日线内的 Supertrend 翻多触发，并经过
趋势结构与 RSI 过滤，不限制涨幅；sell 在任一指标最近两根确认日线内转空时即可预警。`route` 默认完整刷新
两个 Longport 快照组；个别标的扫描失败不会阻断刷新，失败详情随成功结果返回。

所有输出都包含顶层 `status`：`success` 表示完整成功，`partial` 表示整体已执行但
`data.failures[]` 中存在单项失败，`failed` 表示请求无法执行。`partial` 仍保持
`ok: true`。

ETF 双池轮动：

```bash
# 只计算，不修改分组
stk rotate 主题ETF 资产ETF

# 计算成功后完整替换三个共享阶段组
stk group rotate \
  --source 主题ETF \
  --source 资产ETF \
  --emerging ETF启动 \
  --strong ETF强势 \
  --fading ETF退潮
```

`rotation_v2` 使用绝对价格结构判定启动、强势、退潮或内部 inactive；来源池内百分位
只负责各阶段排序。启动区分 rebound/confirmed，再结合 RSI 与 ATR 产生 action。
目标组只有 replace 语义；来源组之间不得有重复 Symbol，来源与目标组必须互不相同。
完整规则见 [ETF 三阶段轮动](docs/design/etf-rotation.md)。

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
- [ETF 双池轮动](docs/design/etf-rotation.md)
- [Agent CLI Skill](docs/skills/stk-cli-reference/SKILL.md)
