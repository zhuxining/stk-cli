# Services 层重组计划

## Context

命令层已从 9 → 4 组完成重组。services 层 akshare 集成后出现关注点混合：

- `quote.py` 混合了个股报价（longport）和板块列表/成分股（akshare）
- `market.py` 混合了市场概览和个股排名
- `flow.py` 混合了个股资金流和板块资金流（服务不同命令）
- 符号转换 helpers 散落在 `services/symbol.py`、`fundamental.py`、`flow.py`、`quote.py` 中
- `to_longport_symbol()` 不支持科创板（688→SH）和北交所（8→BJ）

## 方案概述

1. **合并 `services/symbol.py` → `utils/symbol.py`**：统一所有符号转换 + Decimal/metrics 工具函数
2. **新建 `services/board.py`**：板块相关数据（从 quote.py + flow.py 抽出）
3. **新建 `services/rank.py`**：排名数据（从 market.py 抽出）
4. **精简 4 个现有 service 文件**

---

## 详细变更

### 1. 新建 `utils/symbol.py` — 统一符号转换 + 数据工具

从 `services/symbol.py` 移入：

- `to_longport_symbol(symbol) -> str` — **更新规则**：
  - `6xxxxx` → `.SH`（上交所主板）
  - `688xxx` → `.SH`（科创板，已被 6 开头覆盖）
  - `000/001/002/003xxx` → `.SZ`（深交所主板）
  - `300xxx` → `.SZ`（创业板）
  - `8xxxxx` → `.BJ`（北交所）**新增**
  - `.HK`/`.US`/`.`前缀/已有后缀 → 直通

从 `fundamental.py` 移入：

- `to_em_symbol(symbol) -> str` — 600519 → SH600519
- `is_hk(symbol) -> bool`
- `to_hk_code(symbol) -> str` — 700.HK → 00700

从 `flow.py` 移入：

- `to_ak_market(symbol) -> tuple[str, str]` — 返回 (code, market)

从 `quote.py` / `flow.py` 提取重复逻辑：

- `to_decimal(val) -> Decimal | None` — 安全 Decimal 转换
- `to_metrics(row, columns, skip_cols) -> dict[str, Decimal | None]` — DataFrame 行转 metrics

删除 `services/symbol.py`。

### 2. 新建 `services/board.py` — 板块数据

从 `quote.py` 移入：

- `get_board_list(type) -> BoardList`
- `get_board_cons(name, type) -> BoardCons`
- `_BOARD_API` 配置

从 `flow.py` 移入：

- `get_sector_flow_hist(name, type) -> SectorFlowHist`
- `get_sector_flow_detail(name, period) -> SectorFlowDetail`

使用 `utils.symbol.to_decimal` / `to_metrics` 替代内联实现。

### 3. 新建 `services/rank.py` — 排名数据

从 `market.py` 移入：

- `get_tech_rank(type, ma) -> TechRank`
- `get_hot_rank() -> TechRank`
- `_TECH_RANK_CONFIG`

### 4. 精简现有文件

**`services/quote.py`**：

- 保留：`get_quote()` + `_get_board_quote()`
- 移除：`get_board_list`、`get_board_cons`、`_BOARD_API`、`_SKIP_COLS`、`_to_decimal`
- 改用 `from stk.utils.symbol import to_decimal`

**`services/market.py`**：

- 保留：`get_indices()`、`get_temperature()`、`get_breadth()`
- 移除：`get_tech_rank`、`get_hot_rank`、`_TECH_RANK_CONFIG`、`_SKIP_COLS`

**`services/flow.py`**：

- 保留：`get_stock_flow()`、`get_flow_rank()`
- 移除：`get_sector_flow_hist`、`get_sector_flow_detail`、`_to_ak_stock_market`、`_to_metrics`
- 改用 `from stk.utils.symbol import to_ak_market, to_decimal, to_metrics`

**`services/fundamental.py`**：

- 3 个公开函数不变
- 移除 `_to_em_symbol`、`_is_hk`、`_to_hk_code`，改用 `from stk.utils.symbol import ...`

### 5. 命令层 import 更新

**`commands/board.py`**：

```python
# 之前
from stk.services.quote import get_board_list, get_board_cons
from stk.services.flow import get_sector_flow_hist, get_sector_flow_detail
# 之后
from stk.services.board import get_board_list, get_board_cons, get_sector_flow_hist, get_sector_flow_detail
```

**`commands/stock.py`**：

```python
# 之前
from stk.services.market import get_hot_rank, get_tech_rank
# 之后
from stk.services.rank import get_hot_rank, get_tech_rank
```

### 6. 所有 services 中的 import 更新

全部 `from stk.services.symbol import to_longport_symbol` → `from stk.utils.symbol import to_longport_symbol`

影响文件：`history.py`、`news.py`、`chip.py`、`longport_quote.py`、`flow.py`、`fundamental.py`

### 7. 测试更新

**`test_flow_sector.py`** 拆分为：

- `test_flow.py` — flow rank 测试（import 从 `stk.services.flow`）
- `test_board_service.py` — sector flow hist/detail 测试（import 从 `stk.services.board`，mock `stk.services.board.ak`）

**`test_symbol.py`**：

- import 从 `stk.services.symbol` → `stk.utils.symbol`
- 新增 `8xxxxx → .BJ` 测试用例

---

## 最终布局

```
utils/
├── price.py          # 不变
└── symbol.py         # 新建（合并 symbol + akshare helpers）

services/
├── longport_quote.py # import 更新
├── watchlist.py      # 不变
├── history.py        # import 更新
├── indicator.py      # 不变（通过 history 间接依赖）
├── chip.py           # import 更新
├── news.py           # import 更新
├── quote.py          # 精简：仅 get_quote
├── board.py          # 新建：板块列表/成分 + 板块资金流
├── market.py         # 精简：indices/temp/breadth
├── rank.py           # 新建：tech_rank + hot_rank
├── flow.py           # 精简：stock_flow + flow_rank
└── fundamental.py    # 微调：提取 helpers
```

## 执行步骤

1. 新建 `utils/symbol.py`（合并 + 更新规则）
2. 新建 `services/board.py` + `services/rank.py`
3. 精简 `services/quote.py`、`market.py`、`flow.py`、`fundamental.py`
4. 更新所有 services 的 `from stk.services.symbol` → `from stk.utils.symbol`
5. 删除 `services/symbol.py`
6. 更新 `commands/board.py` + `commands/stock.py` imports
7. 拆分测试文件 + 更新 test_symbol.py
8. 更新 `CLAUDE.md`
9. `uv run pytest` + `uv run ruff check . && ruff format .`

## 验证

```bash
uv run pytest -m "not integration"
uv run ruff check . && uv run ruff format .
uv run stk stock quote 600519
uv run stk board list
uv run stk market index
uv run stk stock rank --type tech
```
