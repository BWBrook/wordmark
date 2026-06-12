# 2026-06-12 - Python 3.14 Readiness Publication

## Summary
- Revalidated the existing macOS/Python 3.14 readiness bundle on the Mac mini.
- Confirmed the remote safety gate before publication: local `HEAD` and
  `origin/main` both resolved to `db52e96` after `git fetch --prune origin`.
- Published readiness evidence in Goal 001 after validation passed without
  readiness-scope fixes.

## Validation
- `uv sync --locked --extra dev` - passed.
- `uv lock --check` - passed.
- `git diff --check` - passed.
- `uv run ruff check .` - passed.
- `uv run pytest` - `126 passed, 5 skipped`.
- `make test-pure-cov` - `114 passed, 17 deselected`, coverage `83.69%`.
- `make test-external` - `12 passed, 5 skipped, 114 deselected`.
- `make check` - `126 passed, 5 skipped`, lint passed.
- `actionlint` - passed.
- `uv run python -m compileall -q src tests` - passed.
- `uv build --out-dir /tmp/wordmark-dist-goal001` - built source distribution
  and wheel.
- Canonical fixture smoke checks passed for `inspect`, `review list`, `render`,
  and `verify --profile business-docs`.
- Built-wheel smoke passed in `/tmp/wordmark-wheel-test-goal001`.

## Notes
- `verify` on `examples/canonical/test_doc.docx` passed the `business-docs`
  profile with `render_diff.ok = true`, 3 pages, and max render-diff ratio `0`.
- Generated scratch outputs were kept under `/tmp` where practical.
- Ignored repo-local sidecars/render outputs under `artifacts/` were retained
  for audit.
- The pre-existing `.DS_Store` remained unstaged local state.
