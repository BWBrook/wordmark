# 2026-02-24 UNO Lock + Minimal Delta Log

## Scope
Follow-up hardening after complex document stress run:
1. isolate/reproduce UNO save failure,
2. reduce over-broad tracked-change spans for small edits.

## Reproduction result
- Isolated UNO write failure to concurrent writes against the same `.docx`.
- Minimal fixture: one document with two parallel `replace_text_global` operations launched simultaneously.
- Observed failure signature on one process:
  - `com.sun.star.io.IOException`
  - `SfxBaseModel::impl_store ... Write Code:12`

## Implementation
- Added per-file operation lock in CLI (`.wordmark.lock`) for mutating commands:
  - `comment add`
  - `edit apply`
  - `review accept`
  - `review reject`
- Improved OOXML localized tracked-delta behavior:
  - compute common prefix/suffix and emit middle-only `w:del`/`w:ins`
  - examples now represented minimally (`of ` insertion, hyphen swap, tail append)
- Enhanced `replace_paragraph_text` to attempt localized replacement before paragraph rewrite fallback.

## Tests
- Added/updated tests in:
  - `tests/test_uno_fallback.py`
  - `tests/test_word_level_revisions.py`
- New coverage includes:
  - concurrent UNO edit invocations serialized successfully,
  - minimal tracked-change deltas for insertion/hyphen scenarios,
  - appended text on paragraph replacement represented as insert-only delta.

## Verification
- `uv run pytest tests/test_word_level_revisions.py tests/test_uno_fallback.py` -> PASS.
