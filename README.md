# stk-cli

面向 Agent 和自动化程序的股票数据与分组信号扫描 CLI。

核心能力：

- 从 Longport 请求日/周/月 K 线，并用 ta-lib 与 stockstats 计算技术指标。
- 管理 Longport 自选分组。
- 在 Longport 与同花顺之间同步分组。
- 扫描 Longport 分组的已确认日线信号，并按 entry/exit 信号分流。

所有命令向 stdout 输出统一 JSON envelope，日志写入 stderr。

## 安装

```bash
uv sync
uv run stk --help
```

项目使用 Python 3.14。完整检查：

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

## 命令结构

```text
stk
├── data
│   └── kline
├── group
│   ├── longport
│   │   └── list / show / create / add / remove / delete
│   ├── ths
│   │   └── list
│   ├── sync
│   │   └── diff / push / pull
│   └── route
└── scan
```

### K 线与指标

```bash
stk data kline 600519
stk data kline 600519,000001 700.HK --period week --count 60
```

每根 K 线合并返回 OHLCV、EMA、MACD、RSI、WR、KDJ、BOLL、ATR 和 Supertrend。
其中 KDJ、WR、ATR 与 Supertrend 由 stockstats 计算，其余技术指标继续使用 ta-lib。

### Longport 分组

```bash
stk group longport list
stk group longport show 核心池
stk group longport create 核心池 --symbol 600519 --symbol 000001
stk group longport add 核心池 700.HK AAPL.US
stk group longport remove 核心池 000001
stk group longport delete 核心池
```

### 同花顺分组与同步

```bash
stk group ths list

stk group sync diff 长桥组 同花顺组
stk group sync push 长桥组 同花顺组
stk group sync push 长桥组 同花顺组 --replace
stk group sync pull 同花顺组 长桥组
stk group sync pull 同花顺组 长桥组 --replace
```

目标分组名可省略，默认与源分组同名。默认同步为追加；`--replace` 使目标与源一致。

### 分组信号扫描

```bash
stk scan 核心池
stk scan 核心池 --daily10
stk scan 核心池 --full-context
```

扫描仅使用已确认日线。输出包含信号决策、主趋势、辅助因子、ATR 风控和单标的错误。

### 信号分流

```bash
stk group route 核心池 买入观察 卖出预警
stk group route 核心池 买入观察 卖出预警 --replace
```

- `趋势买入`、`超卖修复` → entry 目标组。
- `趋势退出` → exit 目标组。
- 默认追加；`--replace` 会让两个目标组与本次扫描结果一致。

## Symbol

- `600519` → `600519.SH`
- `000001` → `000001.SZ`
- `800001` → `800001.BJ`
- 港股使用 `700.HK`
- 美股可使用 `AAPL.US`

所有命令支持全局 `--no-cache`，用于单次跳过缓存。
