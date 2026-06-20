.PHONY: check lint format type test test-quick

check: lint format type test-quick
	@echo "All checks passed."

lint:
	uv run ruff check src tests

format:
	uv run ruff format --check src tests

type:
	uv run ty check src tests

test:
	uv run pytest

test-quick:
	uv run pytest -m "not integration"
