# 2026-02-26 — Phase 6 Implementation: Move Revision Semantics and Schema v2

## Scope
- Implemented Phase 6 hardening wave for:
  - move revision fidelity (`moveTo` / `moveFrom`)
  - reviewer-visible text extraction defaults
  - schema v2 output contract for `inspect`, `review list`, and `verify`

## Implementation highlights
1. **Core model and OOXML extraction updates**
   - `RevisionRecord` now carries:
     - `type` (`insert|delete|move_to|move_from`)
     - `revision_id`
   - `InspectReport` now carries:
     - `text_mode`
     - `text_value`
   - `ooxml_engine.inspect()` now supports `text_mode`:
     - default `review-visible`
     - optional `raw`
   - revision extraction now includes `w:ins`, `w:del`, `w:moveTo`, `w:moveFrom`.

2. **Move-aware review transforms**
   - `review accept`:
     - unwrap `move_to`
     - remove `move_from`
   - `review reject`:
     - remove `move_to`
     - unwrap `move_from`
   - orphan range markers (`moveToRange*`, `moveFromRange*`) are cleaned after transformation.

3. **UNO postprocess hardening**
   - Unknown-author normalization in `uno_engine` expanded from ins/del-only to:
     - `w:ins`
     - `w:del`
     - `w:moveTo`
     - `w:moveFrom`
   - Added per-type normalization counters in `author_binding_postprocess`.

4. **CLI schema and sidecar changes**
   - `inspect`, `review list`, and `verify` JSON payloads now include `schema_version: 2`.
   - `inspect` and `review list` now accept `--text-mode review-visible|raw`.
   - Sidecar text (`{stem}.text.md`) now writes extracted document text (`text_value`) instead of concatenated revision snippets.
   - Drift snapshots now explicitly use review-visible text extraction.

## Test coverage added/updated
- Added `tests/test_move_revision_semantics.py` covering:
  - review-visible vs raw extraction with move markup
  - move revision type/id reporting
  - accept/reject move semantics
  - range-marker cleanup
  - UNO move-author normalization
- Updated existing tests for:
  - revision type rename (`ins/del` -> `insert/delete`)
  - `InspectReport` text field change (`text` -> `text_value`)
  - schema v2 assertions for CLI payloads
  - verify revision counter key updates

## Verification
- Targeted suite:
  - `uv run pytest tests/test_move_revision_semantics.py tests/test_comment_and_inspect.py tests/test_verify_and_render.py tests/test_word_level_revisions.py tests/test_uno_fallback.py tests/test_edit_and_review.py tests/test_phase3_anchor_and_preflight.py tests/test_edit_policy.py -q`
  - Result: pass
- Full suite:
  - `uv run pytest -q`
  - Result: pass
