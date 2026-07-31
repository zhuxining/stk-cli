# AGENTS.md

本文档约束在本仓库中工作的编码 Agent。

## 项目定位

`stk-cli` 是基于 Typer 的 JSON CLI，核心能力是请求 K 线与指标、同步 Longport/同花顺
分组，以及扫描 Longport 分组并维护每日买入和卖出信号快照。

- Python 3.14，使用 uv 管理依赖。
- 源码采用 `src/` 布局，入口为 `src/stk/cli.py`。
- Longport 提供行情、K 线和主要分组；同花顺仅作为分组同步对端。
- pandas 用于数据处理；ta-lib 与 stockstats 用于指标计算。

## 开发命令

```bash
uv sync
uv run stk --help
uv run pytest tests/path/to/test_file.py
make check
```

## 架构约束

- `commands/` 只解析参数、调用服务并渲染输出，不承载业务规则。
- `services/` 负责外部 API、指标计算、信号判断和工作流编排，不写 stdout。
- `models/` 定义服务与 JSON 输出之间的 Pydantic 契约。
- `store/` 只保存缓存和本地映射，不作为行情或分组的权威来源。
- CLI 输出统一使用 `ok/data/error/meta` envelope；日志只写 stderr。
- 服务将外部异常转换为明确的 `StkError` 子类，由 CLI 统一处理。
- Symbol 转换集中在 `utils/symbol.py`，不得在命令或服务中重复实现。

## 修改原则

- 保持命令层轻薄，优先在服务层实现可测试的纯业务逻辑。
- 修改公开 JSON 字段时同步 Pydantic 模型、精确契约测试和 Agent Skill。
- 修改信号阈值、优先级或时间语义时同步信号规则文档。
- 使用 loguru 记录日志，不向 stdout 输出调试信息。
- 保留用户已有改动，避免无关格式化和破坏性 Git 操作。

## 验证要求

- 为新增或变化的业务行为补充单元测试。
- 外部数据源在单元测试中使用 mock，测试不得依赖网络。
- 完成前运行 `make check`，包括 Ruff、格式、ty 和非集成测试。

## 设计文档

- [架构与边界](docs/design/architecture.md)
- [信号规则](docs/design/signal-strategy.md)

项目不负责交易下单、仓位分配、实时交易、回测或长期数据仓储。
