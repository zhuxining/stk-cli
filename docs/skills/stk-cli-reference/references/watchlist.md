# Watchlist 命令参考

**何时读取**：用户要管理自选股分组、从候选/热门股批量入库、扫描自选信号、或做信号分流时读取此文件。watchlist 是命令最多的域，涵盖 CRUD + 5 种扫描工作流。

## 适用场景

- 建分组、增删标的：管理命令（`list`/`show`/`create`/`add`/`remove`/`delete`）
- 从技术候选入库：`stk watchlist scoop`
- 从热门股入库：`stk watchlist hot`
- 按信号方向分流（entry/exit）：`stk watchlist route`
- 识别 zigzag 转折信号：`stk watchlist zigzag`
- 扫描分组标的技术信号：`stk watchlist scan` / `scan-live` / `kline`

---

## 管理命令

| 命令 | 说明 |
|------|------|
| `stk watchlist list` | 列出所有分组 |
| `stk watchlist show <group>` | 查看分组标的 |
| `stk watchlist create <group> --symbol S ...` | 创建分组并添加初始标的 |
| `stk watchlist add <group> <symbols...>` | 批量添加（长桥 API 天然去重） |
| `stk watchlist remove <group> <symbols...>` | 批量移除 |
| `stk watchlist delete <group>` | 删除整个分组 |

---

## `stk watchlist scoop <name>`

捕获今日 THS 技术候选股到指定分组。是 "发现 → 入库" 的核心桥接命令。

```bash
stk watchlist scoop 热点股              # 全量入库
stk watchlist scoop 热点股 --scan       # 扫描过滤：只入推荐信号
stk watchlist scoop 热点股 --scan --strict  # 严格过滤
stk watchlist scoop 热点股 --replace    # 替换模式
```

| 参数 | 默认 | 说明 |
|------|------|------|
| `<name>` | 必填 | 目标分组名（不存在则自动创建） |
| `--scan` | `false` | 不加 = 全量入库（宽进宽出，适合建立初始候选池）。加此标志 = 仅入库 `strength == "推荐"` 的标的（精进，适合建仓级别筛选） |
| `--strict` | `false` | 需 `--scan`。在推荐基础上追加三道门槛：`bars_since_signal <= 2`（信号时效）+ `overall_bias == "supportive"`（辅助因子全员确认）+ `risk_reward_ratio >= 1.5`（风报比达标） |
| `--replace` `-r` | `false` | 清空目标分组再写入。不加 = 追加模式，保留分组已有标的 |

**工作流**：`stk market candidates` → `stk watchlist scoop <group> --scan` → `stk watchlist scan <group>`

**示例**：

```bash
# 全量入库（初次建立候选池）
stk watchlist scoop 今日候选

# 仅入库推荐信号标的
stk watchlist scoop 精选池 --scan

# 严格筛选 + 替换（每日轮换精选池）
stk watchlist scoop 精选池 --scan --strict --replace
```

返回 `WorkflowResult`：
```json
{
  "ok": true,
  "data": {
    "action": "scoop",
    "candidates_found": 8,
    "source_summary": {"total_scanned": 8, "focus_count": 5, "recommend_count": 3, "added": 3},
    "destinations": [{"group": "精选池", "added": 3}]
  }
}
```

---

## `stk watchlist hot <name>`

从东方财富热门股中选取标的入库。与 scoop 结构对称。

```bash
stk watchlist hot 热门股                 # 全量入库（Top 100）
stk watchlist hot 热门股 --source up     # 热度上升榜
stk watchlist hot 热门股 --scan          # 扫描过滤
stk watchlist hot 热门股 --scan --strict --replace  # 严格全量替换
```

| 参数 | 默认 | 说明 |
|------|------|------|
| `<name>` | 必填 | 目标分组名 |
| `--source` `-s` | `rank` | `rank`：当前热门 Top 100（稳定龙头）；`up`：热度上升最快 Top 100（动量爆发） |
| `--scan` | `false` | 同 scoop：不加 = 全量入库，加 = 仅入库推荐信号标的 |
| `--strict` | `false` | 同 scoop：需 `--scan`，追加信号时效+辅助因子+风报比三道门槛 |
| `--replace` `-r` | `false` | 同 scoop：替换模式清空再写入 |

**示例**：

```bash
# 热度上升标的 + 扫描过滤
stk watchlist hot 热度追踪 --source up --scan
```

返回 `WorkflowResult`，结构同 scoop（`action` 为 `hot`）。

---

## `stk watchlist route <src> <entry-dst> <exit-dst>`

扫描源分组全部标的，将 entry 信号（趋势买入/超卖修复）和 exit 信号（趋势退出）分流到不同分组。

> **使用场景**：日线扫描后，把不同方向的信号分开管理——观察组放 entry 标的等待买入时机，预警组放 exit 标的关注减仓时机。

```bash
stk watchlist route A股池 观察 预警 --replace
```

| 参数 | 默认 | 说明 |
|------|------|------|
| `<src>` | 必填 | 源分组名 |
| `<entry-dst>` | 必填 | entry 信号目标分组 |
| `<exit-dst>` | 必填 | exit 信号目标分组 |
| `--replace` `-r` | `false` | 替换模式。不加 = 追加到现有目标分组；加 = 先清空目标再写入 |

**示例**：

```bash
# 每日信号分流
stk watchlist route 全A股池 买入观察 卖出预警 --replace
```

返回 `WorkflowResult`：
```json
{
  "ok": true,
  "data": {
    "action": "route",
    "source_summary": {"total_scanned": 50, "focus_count": 15, "recommend_count": 8, "warning_count": 7},
    "destinations": [
      {"group": "买入观察", "added": 8},
      {"group": "卖出预警", "added": 7}
    ]
  }
}
```

---

## `stk watchlist zigzag <src> <dst>`

识别分组内过去 5 根 K 线出现 zigzag 转折信号（高点或低点）的标的。

> **使用场景**：捕捉潜在的波段反转机会。zigzag 低点可能预示反弹，zigzag 高点可能预示回调。

```bash
stk watchlist zigzag ETF股池 zigzag-picks
```

| 参数 | 默认 | 说明 |
|------|------|------|
| `<src>` | 必填 | 源分组名 |
| `<dst>` | 必填 | 目标分组名（zigzag 信号标的入库） |

算法参数：Depth=10（前后各 5 根确认 pivot），Deviation=5%（最小反转幅度）。这两个参数固定，过滤掉小幅波动噪声。

返回 `WorkflowResult`：`action` 为 `zigzag`。

---

## `stk watchlist scan <group>`

分组每日监控。对分组内全部标的做 `stk stock scan` 同等分析。

| 参数 | 默认 | 说明 |
|------|------|------|
| `<group>` | 必填 | 分组名 |
| `--daily10` | `false` | 推荐/预警标的补充最近 10 根日线 |
| `--full-context` | `false` | 输出完整辅助因子 |

返回 `MonitorResult`，结构同 `stk stock scan`（见 `references/output-schema.md`）。

---

## `stk watchlist scan-live <group>`

分组实盘提醒。对分组内全部标的做盘中的 live scan。

| 参数 | 默认 | 说明 |
|------|------|------|
| `<group>` | 必填 | 分组名 |
| `--timeframe` `-t` | `15m` | `5m` / `15m` |
| `--count` `-c` | `80` | 分钟 K 线根数 |

返回 `LiveScanResult`，结构同 `stk stock scan-live`（见 `references/output-schema.md`）。

---

## `stk watchlist kline <group>`

分组 K 线 + 指标。一次获取分组内所有标的的 K 线数据。

| 参数 | 默认 | 说明 |
|------|------|------|
| `<group>` | 必填 | 分组名 |
| `--period` `-p` | `day` | `day` / `week` / `month` |
| `--count` `-c` | `20` | 每只标的 K 线数量 |

返回 `DailyResult[]`，结构同 `stk stock kline`。
