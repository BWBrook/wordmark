.PHONY: sync test test-pure test-pure-cov test-external lint check

sync:
	uv sync --extra dev --python 3.14

test:
	uv run pytest

test-pure:
	uv run pytest -m "not external_tools"

test-pure-cov:
	uv run pytest -m "not external_tools" --cov=wordmark --cov-report=term-missing --cov-fail-under=80

test-external:
	uv run pytest -m "external_tools"

lint:
	uv run ruff check .

check: test lint
