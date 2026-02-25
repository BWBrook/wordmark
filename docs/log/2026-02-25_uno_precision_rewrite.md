# 2026-02-25 - UNO Precision Rewrite Hardening

## Trigger
Road test feedback on `complex_test_3` showed clause-level tracked replacements under UNO fallback for edits that should have been narrow (single-word, punctuation, and short insertions).

## Changes
- Added UNO pre-apply precision rewrite pass in `src/wordmark/cli.py`:
  - computes replacement deltas (`common prefix/suffix + middle segments`)
  - rewrites eligible `replace_text_once` ops to `replace_span_once` with explicit in-match span metadata (`span_start`, `span_length`, `replacement`)
  - keeps UNO matching anchored to the original requested phrase/occurrence, then mutates only the target span inside that match
  - supports precise insertion-only, deletion-only, punctuation-only, and full-token substitutions in fallback mode
- Added UNO operation support in `scripts/uno_replace.py`:
  - `replace_span_once` (find nth match, then use text cursor to mutate only the requested span)
- Added rewrite diagnostics under `operation.details.uno_precision_rewrite`.
- Added tests in `tests/test_edit_policy.py`:
  - direct span-rewrite assertions for insertion, punctuation, append, token substitutions
  - CLI integration assertion that rewritten span patch is passed to UNO and diagnostics are emitted
- Added UNO integration tests in `tests/test_uno_fallback.py`:
  - insertion-only span edit preserves suffix token (`clear ` insertion before `saturation`)
  - hyphen-only deletion for compound term normalization

## Verification
- `uv run pytest tests/test_edit_policy.py -q`
- `uv run pytest tests/test_uno_fallback.py -q`
- `uv run pytest -q`

## Notes
- This improves precision when UNO fallback is unavoidable, but does not guarantee Word-perfect run-level deltas in every document shape.
- Field/code-driven numbering drift remains a separate interop hardening area.
