# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`stk-cli` is a Stock Query CLI tool built with Typer, designed for agent-driven interaction. It uses **longport** as the unified data source for all markets (A-share, HK, US), with **ta-lib** for technical analysis.

- Python 3.14, managed with **uv**
- Src layout: source in `src/stk/` (built as wheel package via `uv_build`)
- Entry point: `src/stk/cli.py` → `cli()` (registered as `stk` command via `project.scripts`)

## Commands

```bash
# Install dependencies
uv sync

# Run the CLI
uv run stk

# Lint & format (auto-fix enabled)
uv run ruff check .
uv run ruff format .

# Type check
uv run ty check

# Run all tests
uv run pytest

# Run tests excluding external service calls
uv run pytest -m "not integration"

# Run a single test file
uv run pytest tests/path/to/test_file.py
```

## Architecture

Three-layer architecture. Full design doc: `dosc/design/architecture.md`.

```
src/stk/
├── cli.py              # Root Typer app, registers all subcommand groups
├── config.py           # pydantic-settings Settings (reads .env)
├── output.py           # Unified JSON envelope output
├── errors.py           # Custom exceptions + global error handler
├── deps.py             # Lazy singletons (longport ctx, etc.)
├── commands/           # Thin layer: parse args → call service → render output
│   ├── quote.py        # stk quote — real-time quotes
│   ├── history.py      # stk history — historical candlesticks
│   ├── indicator.py    # stk indicator — technical indicators
│   ├── news.py         # stk news — news feed
│   ├── fundamental.py  # stk fundamental — financials, valuation
│   ├── market.py       # stk market — indices, temperature, breadth
│   ├── flow.py         # stk flow — money flow
│   ├── chip.py         # stk chip — chip distribution
│   └── watchlist.py    # stk watchlist — watchlist CRUD
├── services/           # Business logic: call APIs → return Pydantic models
│   ├── symbol.py       # Symbol normalization (user input → longport format)
│   ├── longport_quote.py
│   ├── quote.py        # Facade: all markets via longport
│   ├── history.py
│   ├── indicator.py    # ta-lib calculations (pure DataFrame ops)
│   ├── news.py
│   ├── fundamental.py
│   ├── market.py       # Index quotes + market temperature scoring
│   ├── flow.py
│   ├── chip.py
│   └── watchlist.py
├── models/             # Pydantic models (data contracts, JSON schema for agents)
│   ├── common.py       # Envelope, ErrorDetail
│   └── ...             # One file per domain
├── store/              # Local JSON file storage (~/.stk/)
│   └── file_store.py   # Atomic JSON read/write
└── utils/              # Utility functions
    └── price.py        # Price formatting
```

### Key conventions

- **commands/** — Thin. No business logic. Parse params → call service → `output.render()`.
- **services/** — All logic here. Call data source → transform → return Pydantic model. No stdout.
- **models/** — Data contracts between layers. Also the JSON schema agents consume.
- **Data flow**: CLI command → commands/ → services/ → longport API → pandas DataFrame → models/ → output.py (JSON envelope to stdout).
- **Symbol normalization** (in `services/symbol.py`): `600519`→`600519.SH`, `000001`→`000001.SZ`; `.HK`/`.US`/`.`prefix → pass through.
- **Target types**: `--type stock|sector|concept|index` (default `stock`).
- **JSON envelope**: `{"ok": true, "data": [...], "error": null, "meta": {...}}`. All output to stdout, logs to stderr.
- **Errors**: `StkError` → `ConfigError` / `SourceError` / `SymbolNotFoundError` / `IndicatorError` / `DataNotFoundError`. Services wrap SDK exceptions; global handler formats JSON error output.
- **Storage**: `~/.stk/` directory for watchlist.json etc. Atomic writes (tmp file + rename).

Use `loguru` for all logging. Use `pandas` + `ta-lib` for indicator calculations in services.
Longport is the primary data source. akshare supplements A-share features: news, chip distribution, market breadth, financial report, sector/concept quotes, sector money flow.
