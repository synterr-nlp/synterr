# Quality gate — one call, CI runs the same targets (AGENTS.md → Gate).
.PHONY: check check-full lint format test test-slow docs

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests
	uv run mypy

format:
	uv run ruff format src tests
	uv run ruff check --fix src tests

test:
	uv run pytest -m "not slow"

test-slow:
	uv run pytest --no-cov -m "slow"

docs:
	uv run mkdocs build --strict

check: lint test

check-full: check test-slow docs
