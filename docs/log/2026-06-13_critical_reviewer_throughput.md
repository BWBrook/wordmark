# 2026-06-13 Critical Reviewer Throughput

## Scope
Goal 002 strengthened Wordmark's agent-facing critical-review guidance without
changing DOCX mutation behavior, OOXML/UNO logic, dependencies, CI workflows, or
real manuscript content.

## Implementation Note
The work moves future agents toward a line-edit-first stance for routine local
language fixes, with comments reserved for author judgment. It adds a reusable
agent brief and a structured calibration fixture that distinguishes tracked-edit
cases from comment-only cases.

## Validation
Local validation passed:

- `uv run pytest tests/test_reviewer_calibration.py -q`
- `uv lock --check`
- `git diff --check`
- `uv run ruff check .`
- `uv run pytest`
- `make check`

`make test-external` was not run because the diff is guidance, calibration, and
pure fixture validation only; it does not touch external-tool, render, Quarto,
or DOCX integration behavior.

Hosted `ci` passed for implementation commit `483c687`:

- run: `27454942297`
- URL: `https://github.com/BWBrook/wordmark/actions/runs/27454942297`
- jobs: `lint` success; `pure-python (py3.14)` success

The final goal-packet bookkeeping commit is docs-only; the orchestrator
wake-up carries the final hosted CI status for that closing commit.
