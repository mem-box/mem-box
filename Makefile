.PHONY: help install dev-install lint format typecheck test test-cov clean pre-commit

help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install production dependencies
	uv sync

dev-install:  ## Install development dependencies
	uv sync --all-extras

lint:  ## Run ruff linting
	uv run ruff check .
	cd client/vscode && npm run lint

lint-fix:  ## Run ruff linting with auto-fix
	uv run ruff check --fix .

format:  ## Format code with ruff
	uv run ruff format .
	cd client/vscode && npm run format || true

format-check:  ## Check code formatting
	uv run ruff format --check .
	cd client/vscode && npm run format-check || true

typecheck:  ## Run mypy type checking
	uv run mypy lib server
	cd client/vscode && npm run compile

test:  ## Run tests
	uv run pytest
	cd client/vscode && npm test || echo "No TS tests yet"

test-cov:  ## Run tests with coverage report
	uv run pytest --cov-report=html
	@echo "Coverage report generated at htmlcov/index.html"

test-watch:  ## Run tests in watch mode
	uv run pytest-watch

check: lint format-check typecheck test  ## Run all quality checks

check-guidelines:  ## Check compliance with development guidelines
	@bash scripts/check-guidelines.sh

pre-commit-install:  ## Install pre-commit hooks
	uv run pre-commit install

pre-commit:  ## Run pre-commit hooks on all files
	uv run pre-commit run --all-files

clean:  ## Clean up generated files
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf dist
	rm -rf build
	rm -rf *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

cli:  ## Run the CLI
	uv run memory-box

server:  ## Run the MCP server
	uv run python -m memory_box.server

.DEFAULT_GOAL := help
