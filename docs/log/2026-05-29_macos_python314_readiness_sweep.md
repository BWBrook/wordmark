# 2026-05-29 - macOS Python 3.14 Readiness Sweep

## Summary
- Reoriented the repo around Barry's Mac mini dev box as the active local R&D host.
- Promoted the project baseline from Python 3.11/3.12-era metadata to Python 3.14.
- Added `.python-version` so `uv` and local shells converge on Python 3.14 by default.
- Updated the Makefile, README, and GitHub Actions workflows to match the Python 3.14 baseline.
- Replaced the remaining `datetime.utcnow()` timestamp call with a timezone-aware UTC timestamp.

## Verification
- `uv lock --upgrade --python 3.14`
- `uv sync --extra dev --python 3.14`
- `uv sync --locked --extra dev`
- `uv run ruff check .`
- `make test-pure-cov` -> `114 passed, 17 deselected`, coverage `83.69%`
- `make test-external` -> `12 passed, 5 skipped, 114 deselected`
- `uv run pytest` -> `126 passed, 5 skipped`
- `actionlint`
- `uv lock --check`
- `uv run python -m compileall -q src tests`
- `uv build --out-dir /tmp/wordmark-dist-20260529`
- Wheel smoke test in `/tmp/wordmark-wheel-test-20260529`
- `uv run wordmark inspect examples/canonical/test_doc.docx --json`
- `uv run wordmark review list examples/canonical/test_doc.docx --json`
- `uv run wordmark render examples/canonical/test_doc.docx --out /tmp/wordmark-render-smoke-20260529 --json`
- `uv run wordmark verify examples/canonical/test_doc.docx examples/canonical/test_doc.docx --profile business-docs --json`
- `make check` -> `126 passed, 5 skipped`, lint passed
- `git diff --check`

## Notes
- Host tooling was already present on the Mac mini: `soffice`, `pdftoppm`, Quarto, GitHub CLI auth, Docker Desktop, and `actionlint`.
- `system_uno_available()` remains `False` by default on macOS, matching the explicit opt-in policy for LibreOffice UNO fallback.
- Generated sidecars/render outputs under `artifacts/` are ignored and retained for audit unless explicitly cleaned.
