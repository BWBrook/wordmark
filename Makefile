.PHONY: sync test check

sync:
	uv sync --extra dev

test:
	uv run pytest

check: test
