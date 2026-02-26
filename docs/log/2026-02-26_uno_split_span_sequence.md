# 2026-02-26 - UNO Split-Span Sequence Hardening

## Trigger
Road-test review of a full thesis chapter showed residual fidelity quirks where two separated micro-edits in the same phrase were rendered as one broad clause replacement under UNO fallback.

## Changes
- Updated `src/wordmark/cli.py` UNO precision rewrite logic:
  - replaced character-level split detection with token-level island detection (`whitespace | word | punctuation`)
  - added conservative split routing for `replace_text_once` when there are exactly 2-3 separated change islands and `occurrence=1`
  - materializes split operations as ordered `replace_span_once` steps over evolving intermediate text
  - retains existing single-span rewrite path for all non-eligible shapes
- Added regression coverage in `tests/test_edit_policy.py`:
  - disjoint lexical edit split (`away from opportunistic understory` -> `beyond opportunistic understorey`)
  - article-drop plus later insertion split (`the canopy... communities` -> `canopy... bird communities`)
  - helper assertions that replay generated span ops and verify exact final phrase reconstruction

## Verification
- `uv run pytest -q tests/test_edit_policy.py`
- `uv run pytest -q`

## Notes
- Split rewrite is intentionally conservative to avoid over-fragmenting dense edits (for example high-frequency case/hyphen cascades).
- Existing fallback behavior remains intact when split preconditions are not met.
