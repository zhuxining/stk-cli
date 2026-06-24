# Market 命令参考

**何时读取**：用户想看大盘温度、找热门板块、筛技术候选股、看热门个股排名时读取此文件。

## 适用场景

- 开仓前评估整体市场环境：`stk market index`
- 寻找特定技术形态的股票（放量突破/缩量筑底等）：`stk market rank`
- 识别资金正在流入的行业：`stk market hotspot`
- 跨 screen 多方确认的候选标的：`stk market candidates`
- 了解散户关注的热门股：`stk market hotstock`

建议顺序：先 `index` 判断市场方向，再 `hotspot` 缩小行业范围，最后用 `candidates` 或 `rank` 找到具体标的。

---

## `stk market index`

市场概览，指数按 `CN` / `HK` / `US` 分组，含三地温度。适合每日盘前快速了解全球市场状态。

| 参数 | 默认 | 说明 |
|------|------|------|
| （无位置参数） | - | 不需要指定标的 |

**示例**：

```bash
stk market index
```

输出摘要：
```json
{
  "ok": true,
  "data": {
    "indices": [
      {"symbol": "000001.SH", "name": "上证指数", "region": "CN", "last": 3350.12, "change_pct": 0.85}
    ],
    "temperature": {"score": 72, "level": "偏热", "valuation": "中等", "sentiment": "积极"},
    "regime": {"CN": "trending", "HK": "ranging", "US": "trending"}
  }
}
```

- `temperature.score` 综合估值+情绪，0-100 分。>80 过热需谨慎，<30 可能是左侧抄底机会
- `regime` 中 `trending` 适合趋势策略，`ranging` 适合波段，`mixed` 时降低仓位
- 返回类型 `MarketOverview`

---

## `stk market rank`

同花顺技术 screen 排名。每个 screen 代表一种技术形态筛选条件，帮你找到符合特定形态的股票。

| 参数 | 默认 | 说明 |
|------|------|------|
| `--screen` `-s` | `lxsz` | 见下方 screen 说明 |

**Screen 类型**：

| screen | 含义 | 适合场景 |
|--------|------|----------|
| `lxsz` | 连续上涨 | 强势追涨，市场趋势向上时用 |
| `cxfl` | 持续放量 | 资金持续流入，找机构建仓标的 |
| `xstp` | 向上突破 | 配合 `--ma` 做均线突破策略 |
| `ljqs` | 累积趋势 | 中长期趋势形成，适合稳健持仓 |
| `cxsl` | 持续缩量 | 缩量洗盘后可能变盘，适合潜伏 |
| `lxxd` | 连续下跌 | 超跌反弹候选，反转策略参考 |
| `xxtp` | 向下突破 | 配合 `--ma` 识别空头突破 |
| `ljqd` | 累积强度 | 长期强度累积，大资金关注 |

`--ma` 参数仅 `xstp` / `xxtp` 专用，指定参考均线周期。

**示例**：

```bash
# 找向上突破 20 日均线的标的
stk market rank --screen xstp --ma 20日均线

# 找持续放量的标的（资金流入信号）
stk market rank --screen cxfl
```

输出摘要：
```json
{
  "ok": true,
  "data": {
    "type": "xstp",
    "label": "向上突破(20日均线)",
    "items": [
      {"code": "600519", "name": "贵州茅台", "metrics": {...}}
    ]
  }
}
```

返回类型 `TechRank`。

---

## `stk market hotspot`

行业多空情绪统计。统计各行业中处于多方 screen 和空方 screen 的标的数量，反映行业级别的资金流向。

> **使用建议**：先运行 hotspot 找到多头集中的行业，再用 `stk market candidates` 从中挑具体标的。

| 参数 | 默认 | 说明 |
|------|------|------|
| `--ma` | `20日均线` | `xstp` / `xxtp` 专用 |

**示例**：

```bash
stk market hotspot --ma 60日均线
```

输出摘要：
```json
{
  "ok": true,
  "data": {
    "industries": [
      {"industry": "白酒", "bull_count": 12, "bear_count": 1, "bull_screens": ["lxsz", "cxfl"], "bear_screens": []}
    ]
  }
}
```

- `bull_count` - `bear_count` 差值为正的行业是当前资金倾向方向
- `bull_screens` 列出该行业标的出现的多方 screen，多个 screen 重叠 = 更强确认
- 返回类型 `TechIndustries`

---

## `stk market candidates`

跨 screen 候选股。返回出现在 ≥3 个多方 screen 且无空方冲突的股票，是技术初筛的最高共识度候选。

> **重要**：`candidates` 只是技术初筛，不代表趋势确认。必须继续跑 `stk stock scan <symbols...>` 做深度分析。

| 参数 | 默认 | 说明 |
|------|------|------|
| `--ma` | `20日均线` | `xstp` / `xxtp` 专用 |

**示例**：

```bash
stk market candidates --ma 20日均线
```

输出摘要：
```json
{
  "ok": true,
  "data": {
    "candidates": [
      {"code": "600519", "name": "贵州茅台", "bull_screens": ["lxsz", "cxfl", "ljqs"]}
    ],
    "total": 8
  }
}
```

- 直接衔接 `stk watchlist scoop <group>` 将候选股批量入库
- 返回类型 `TechCandidates`

---

## `stk market hotstock`

东方财富热门个股排行。展示散户关注度最高的标的。

| 参数 | 默认 | 说明 |
|------|------|------|
| `--source` `-s` | `rank` | `rank`：当前热门排名 Top 100（龙头稳定型）；`up`：热度上升最快 Top 100（动量爆发型，含 `rank_change` 排名变动） |

选择 `rank` 看市场焦点和持续热门标的；选择 `up` 找近期突然受关注的标的，可能有事件催化。

**示例**：

```bash
# 当前热门排名
stk market hotstock

# 热度上升最快
stk market hotstock --source up
```

输出摘要（`rank` 源）：
```json
{
  "ok": true,
  "data": {
    "source": "rank",
    "total": 100,
    "items": [
      {"rank": 1, "symbol": "600519.SH", "name": "贵州茅台", "last": 1680.00, "change_pct": 1.23, "rank_change": null}
    ]
  }
}
```

输出摘要（`up` 源）：
```json
{
  "ok": true,
  "data": {
    "source": "up",
    "total": 100,
    "items": [
      {"rank": 1, "symbol": "300750.SZ", "name": "宁德时代", "last": 210.50, "change_pct": 5.67, "rank_change": 48}
    ]
  }
}
```

- `rank_change` 仅 `up` 源有值，正数表示排名上升
- 可直接衔接到 `stk watchlist hot <group>` 将热门股批量入库
- 返回类型 `HotStockResult`
