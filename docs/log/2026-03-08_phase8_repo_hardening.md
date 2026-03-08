# 2026-03-08 — Phase 8 Repo Hardening

## Summary
Implemented the approved low-risk and medium-risk hardening work from the whole-repo audit, while deferring the high-risk DOCX-core and manuscript redesign items.

## Delivered
1. Local-first environment contract:
   - added pytest markers for external-tool-dependent tests
   - added `make test-pure` and `make test-external`
   - improved missing-tool diagnostics for render and default Quarto manuscript builds
2. Default/config drift reduction:
   - `__version__` now resolves from installed package metadata
   - `load_config()` now derives defaults from `AppConfig`
   - added tests that lock repo `wordmark.yaml` to code defaults
3. Manuscript characterization improvements:
   - GitHub ingestion success and auth-missing cases
   - default Quarto build behavior and missing-Quarto failure
   - build command failure path
   - repeated-text ambiguity in synthesis
   - partial status artifact behavior
4. `cli.py` responsibility reduction:
   - extracted cleanup helpers
   - extracted edit-policy/risk-summary helpers
   - extracted UNO precision rewrite helpers

## New modules
- `src/wordmark/external_tools.py`
- `src/wordmark/cleanup.py`
- `src/wordmark/edit_policy.py`
- `src/wordmark/uno_precision.py`

## Validation
- Focused changed-test run passed.
- Full suite passed with `uv run pytest -q`.

## Deferred
- Any decomposition of `src/wordmark/ooxml_engine.py`
- Any manuscript redesign beyond the current exact-match safe-apply model
