# Watchlist Workflow Commands

> **Status**: draft
> **Date**: 2026-06-20

## Overview

在 `stk watchlist` 下新增两个工作流命令，将现有候选股扫描、信号筛选、自选股管理串成一步操作。面向每日监控场景：扩充股池 → 信号分流。

## Commands

### `stk watchlist scoop <name>`

捕获今日市场候选股到指定分组。

```bash
stk watchlist scoop 热点股
stk watchlist scoop A股池
```

**流程**：

1. 调用 `get_tech_candidates()`（同花顺 3+ 多方 screen 交叉验证）获取今日候选股
2. 调用 `batch_summary()` 扫描所有候选股，获取信号参考
3. 调用 `add_symbols(name, all_candidate_codes)` 将全部候选股加入目标分组
4. 返回 `WorkflowResult`：扫描统计 + 目标分组状态

**关键决策**：加入的是**全部候选股**，不限于 scan 的 focus 标的。scan 仅作为信号参考信息返回，不做过滤。理由是 candidates 本身已经是技术面初筛结果，再用 scan 过滤会过于严格。

---

### `stk watchlist route <src> <entry-dst> <exit-dst> [--replace]`

扫描源分组，按信号类型分流到两个目标分组。

```bash
# 追加模式（默认）：新信号追加到目标分组
stk watchlist route A股池 观察 预警

# 替换模式：先清空目标分组，再添加今日信号
stk watchlist route A股池 观察 预警 --replace
```

**流程**：

1. 调用 `scan_watchlist(src)` 获取 `MonitorResult`
2. 遍历 `focus` 标的：
   - `decision.signal` 为 entry 信号（趋势买入/超卖修复）→ 加入 `entry-dst`
   - `decision.signal` 为 exit 信号（趋势退出）→ 加入 `exit-dst`
3. 如果 `--replace`：添加前使用 `SecuritiesUpdateMode.Replace` 清空目标分组
4. 返回 `WorkflowResult`：分流统计 + 两个目标分组状态

**信号分类规则**：

| 信号 | 类型 | 目标 |
|------|------|------|
| 趋势买入 / 超卖修复 | entry | `entry-dst` |
| 趋势退出 | exit | `exit-dst` |
| 观察 / 无信号 | skip | 忽略 |

---

## Models

### `WorkflowResult`

新增到 `src/stk/models/watchlist.py`：

```python
class WorkflowResult(BaseModel):
    """Result of a watchlist workflow operation (scoop/route)."""

    action: str                                  # "scoop" or "route"
    candidates_found: int = 0                    # scoop: 初始候选股数量
    source_summary: MonitorSummary | None = None # 扫描结果统计
    destinations: list[Watchlist] = []           # 操作后的目标分组
```

---

## Service Functions

新增到 `src/stk/services/watchlist.py`：

### `scoop_candidates(name: str) -> WorkflowResult`

```python
def scoop_candidates(name: str) -> WorkflowResult:
    # 1. Get candidates
    candidates = get_tech_candidates()
    if not candidates.candidates:
        return WorkflowResult(action="scoop", candidates_found=0)

    symbols = expand_symbols([c.code for c in candidates.candidates])

    # 2. Scan for signal reference
    scan_result = batch_summary(symbols, include_daily10=False, include_full_context=False)

    # 3. Add all candidates to group
    add_symbols(name, symbols)

    # 4. Return result
    return WorkflowResult(
        action="scoop",
        candidates_found=len(candidates.candidates),
        source_summary=scan_result.summary,
        destinations=[get_watchlist(name)],
    )
```

### `route_signals(src, entry_dst, exit_dst, *, replace=False) -> WorkflowResult`

```python
def route_signals(src: str, entry_dst: str, exit_dst: str, *, replace: bool = False) -> WorkflowResult:
    # 1. Scan source group
    scan_result = scan_watchlist(src, include_daily10=False, include_full_context=False)

    # 2. Classify focus items
    entry_symbols = []
    exit_symbols = []
    for item in scan_result.focus:
        if item.decision.signal in {"趋势买入", "超卖修复"}:
            entry_symbols.append(item.symbol)
        elif item.decision.signal == "趋势退出":
            exit_symbols.append(item.symbol)

    # 3. Route to destinations
    mode = SecuritiesUpdateMode.Replace if replace else SecuritiesUpdateMode.Add

    if entry_symbols:
        add_symbols(entry_dst, entry_symbols, mode=mode)
    if exit_symbols:
        add_symbols(exit_dst, exit_symbols, mode=mode)

    # 4. Return result
    return WorkflowResult(
        action="route",
        source_summary=scan_result.summary,
        destinations=[get_watchlist(entry_dst), get_watchlist(exit_dst)],
    )
```

注意：`add_symbols` 增加可选 `mode` 参数，默认 `SecuritiesUpdateMode.Add`，传入 `Replace` 时先清空再添加。

---

## Files Changed

| File | Change |
|------|--------|
| `src/stk/models/watchlist.py` | +`WorkflowResult` 模型 |
| `src/stk/services/watchlist.py` | +`scoop_candidates()`、+`route_signals()`、`add_symbols` 增加 `mode` 参数 |
| `src/stk/commands/watchlist.py` | +`scoop` 命令、+`route` 命令 |

## Tests

### Unit tests

| Test | What it covers |
|------|---------------|
| `test_scoop_candidates` | candidates → scan → add all, verify WorkflowResult |
| `test_scoop_candidates_empty` | 无候选股时返回空结果 |
| `test_route_signals_default` | 默认追加模式验证 |
| `test_route_signals_replace` | `--replace` 模式验证 |
| `test_route_signals_empty` | 无信号时不做操作 |

### Verification

```bash
make check
uv run stk watchlist scoop 热点股
uv run stk watchlist route A股池 观察 预警 --replace
```

## Risk

- `scoop` 的 candidates 可能为 0（市场无候选股时），需优雅处理空结果
- `route` 的目标分组不存在时，自动创建（`add_symbols` 已有此能力）
- 单标失败不阻断整体流程（沿用 scan 的 `errors[]` 机制）
