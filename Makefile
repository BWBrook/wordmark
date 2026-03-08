.PHONY: sync test test-pure test-external check

sync:
	uv sync --extra dev

test:
	uv run pytest

test-pure:
	uv run pytest -m "not external_tools"

test-external:
	uv run pytest -m "external_tools"

check: test
