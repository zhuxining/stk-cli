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

Three-layer architecture. Full design doc: `docs/design/architecture.md`.

```
src/stk/
├── cli.py              # Root Typer app, registers all subcommand groups
├── config.py           # pydantic-settings Settings (reads .env)
├── output.py           # Unified JSON envelope output
├── errors.py           # Custom exceptions + global error handler
├── deps.py             # Lazy singletons (longport ctx, etc.)
├── commands/           # Thin layer: parse args → call service → render output
│   ├── market.py       # stk market — grouped indices + temperature; stk market news
│   ├── stock.py        # stk stock — scan, kline, fundamental, rank
│   ├── watchlist.py    # stk watchlist — CRUD + scan + kline
│   ├── doctor.py       # stk doctor — data source health check
│   └── cache.py        # stk cache — cache management
├── services/           # Business logic: call APIs → return Pydantic models
│   ├── rank.py         # Stock technical rankings (THS)
│   ├── market.py       # Market overview: indices (CN/HK/US), temperature
│   ├── fundamental.py  # Valuation (via calc_indexes), industry comparison, profile
│   ├── quote.py # Longport raw API wrapper
│   ├── history.py      # K-line history fetch + caching
│   ├── indicator.py    # ta-lib calculations + get_daily (OHLCV + all indicators merged)
│   ├── score.py        # Multi-indicator resonance score + ATR risk control
│   ├── scan.py         # Batch analysis: watchlist scan + stock scan + kline_watchlist
│   ├── health.py       # Data source connectivity check
│   ├── news.py         # Global news (CLS / THS)
│   └── watchlist.py    # Watchlist via longport API, local group ID cache
├── models/             # Pydantic models (data contracts, JSON schema for agents)
│   ├── common.py       # Envelope, ErrorDetail
│   └── ...             # One file per domain
├── store/              # Local JSON file storage (~/.stk/)
│   ├── file_store.py   # Atomic JSON read/write
│   └── cache.py        # API response cache
└── utils/              # Utility functions
    ├── price.py        # Price formatting
    └── symbol.py       # Symbol normalization
```

### Key conventions

- **commands/** — Thin. No business logic. Parse params → call service → `output.render()`.
- **services/** — All logic here. Call data source → transform → return Pydantic model. No stdout.
- **models/** — Data contracts between layers. Also the JSON schema agents consume.
- **Data flow**: CLI command → commands/ → services/ → longport API → pandas DataFrame → models/ → output.py (JSON envelope to stdout).
- **Symbol normalization** (in `utils/symbol.py`): `600519`→`600519.SH`, `000001`→`000001.SZ`, `8xxxxx`→`8xxxxx.BJ`; `.HK`/`.US`/`.` prefix → pass through.
- **Target types**: `--type stock|index` (default `stock`).
- **JSON envelope**: `{"ok": true, "data": [...], "error": null, "meta": {...}}`. All output to stdout, logs to stderr.
- **Errors**: `StkError` → `ConfigError` / `SourceError` / `SymbolNotFoundError` / `IndicatorError` / `DataNotFoundError`. Services wrap SDK exceptions; global handler formats JSON error output.
- **Storage**: `~/.stk/` directory for local caches (e.g. `watchlist_groups.json` for group name→id mapping). Atomic writes (tmp file + rename). Watchlist data is stored on longport server.

Use `loguru` for all logging. Use `pandas` + `ta-lib` for indicator calculations in services.
Longport is the primary data source. akshare supplements A-share features: tech screening rankings (THS), industry comparison, company profile, global news (CLS/THS).
