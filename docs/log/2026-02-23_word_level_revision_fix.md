# 2026-02-23 Word-level Revision Fidelity Fix

## Problem observed
Single-word tracked edits were displayed as whole-sentence changes in Word because `replace_text_once` used paragraph rewrite semantics.

## Root cause
- `replace_text_once` delegated to paragraph-wide rewrite, wrapping full old/new paragraph text in `w:del` and `w:ins`.
- Real-world paragraph runs included `w:lastRenderedPageBreak`, which the initial localized run matcher treated as unsupported.

## Implementation
- Added localized run-level replace path in `src/wordmark/ooxml_engine.py`:
  - attempts run split around first match,
  - preserves run styling (`w:rPr`) and run attributes,
  - emits precise `w:del`/`w:ins` for matched token,
  - records operation strategy (`localized_run` vs `paragraph_rewrite`).
- Extended matcher to tolerate/retain extra run children (for example `w:lastRenderedPageBreak`) when safe.

## Tests added
- `tests/test_word_level_revisions.py`
  - verifies word-level revision output for single-run case,
  - verifies fallback behavior when match spans multiple runs.

## Validation results
- `uv run pytest` -> PASS (`17 passed`)
- Real document validation:
  - input: `/mnt/c/temp/test_doc.docx`
  - output: `/mnt/c/temp/test_doc_single_word_v3_edited_mon23feb2026.docx`
  - review state shows one insertion (`practical`) and one deletion (`practorial`) with one comment.
