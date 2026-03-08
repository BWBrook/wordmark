# 2026-03-08 — Phase 11 Replace Slice and Source-Aware Manuscript Hardening

## Summary
Addressed the previously deferred risks left after Phase 10:
1. localized OOXML replacement logic concentration
2. manuscript safe-apply not being source-aware enough
3. lack of a CI coverage floor

## Delivered
1. Source-aware manuscript hardening
   - anchored note syntax (`file:line:` / `file:start-end:`)
   - source-file-aware line-scoped synthesis for anchored edits
   - deterministic event ordering before event IDs
   - stronger failure handling for malformed round inputs
2. OOXML decomposition slice 3
   - extracted localized replacement and paragraph rewrite helpers into `src/wordmark/ooxml_replace.py`
   - kept `ooxml_engine` as the public integration point
3. Coverage gate
   - added `make test-pure-cov`
   - updated hosted CI to use the coverage-backed pure lane
4. Documentation and ADR updates
   - refreshed README/workflow/architecture wording to match the new source-aware manuscript behavior

## Validation
- `uv run ruff check .` -> pass
- focused changed-area tests -> pass
- `uv run pytest -q` -> pass
- `make test-pure` -> pass
- `make test-pure-cov` -> pass
- `make test-external` -> pass

## Remaining strategic deferrals
- any attempt at true AST/source-map manuscript backporting
- broader OOXML-engine breakup beyond the current small-slice approach
