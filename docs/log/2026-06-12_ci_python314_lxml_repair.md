# 2026-06-12 - CI Python 3.14 lxml Repair

## Summary
- Repaired the hosted GitHub Actions `ci` failure introduced by the Python 3.14
  readiness publication.
- Root cause: the Python 3.14 lock still pinned `lxml==5.4.0`, which did not
  provide CPython 3.14 manylinux wheels for the hosted Linux runner, causing
  `uv sync --extra dev` to attempt a source build without `libxml2`/`libxslt`
  development headers.
- Chosen repair: move the project `lxml` constraint to `lxml>=6.0.2,<7` and
  refresh only the `lxml` lock resolution.

## Evidence
- Failed GitHub Actions run inspected: `27408770801`.
- Failed jobs: `lint` and `pure-python (py3.14)`.
- Failed step: `Sync dependencies`.
- Failure snippet: `Building lxml==5.4.0`, then missing XML/XSLT development
  package error.
- New lock pins `lxml==6.1.1` and includes CPython 3.14 manylinux x86_64
  wheels.

## Notes
- No workflow package-install workaround was used.
- No unrelated dependency upgrade was made.
- No external-tools workflow change was made.

## Local Validation
- `uv lock --upgrade-package lxml` - updated `lxml 5.4.0` to `6.1.1`.
- `uv sync --locked --extra dev` - passed and installed `lxml==6.1.1`.
- `uv lock --check` - passed.
- `git diff --check` - passed.
- `uv run ruff check .` - passed.
- `uv run pytest` - `126 passed, 5 skipped`.
- `make test-pure-cov` - `114 passed, 17 deselected`, coverage `83.69%`.
- `make check` - `126 passed, 5 skipped`, lint passed.
- `actionlint` - passed.
- `make test-external` - `12 passed, 5 skipped, 114 deselected`.
