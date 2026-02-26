# 2026-02-26 — Verify Guard for Word “Unreadable Content” Namespace Mismatch

## Trigger
Manual road testing surfaced a Word warning:
- “Word found unreadable content … Do you want to recover the contents?”

Root cause investigation showed:
- `word/document.xml` contained `mc:Ignorable` tokens (for example `w14 wp14 w15`) without corresponding namespace declarations (`xmlns:w14`, `xmlns:wp14`, `xmlns:w15`).

## Changes implemented
1. Added verify-time compatibility gate in `src/wordmark/verify.py`:
   - `checks.compatibility_namespace_integrity`
   - validates `mc:Ignorable` token prefixes against root namespace declarations
   - reports:
     - `ok`
     - `ignorable_tokens`
     - `missing_prefixes`
     - `declared_prefixes`
2. Updated verify pass rule to require:
   - `comment_integrity.ok`
   - `compatibility_namespace_integrity.ok`
   - `render_diff.ok`
3. Added regression test in `tests/test_verify_and_render.py`:
   - injects intentional ignorable-prefix mismatch into a DOCX
   - asserts verify fails with expected `missing_prefixes`.

## Validation
- Targeted:
  - `uv run pytest tests/test_verify_and_render.py -q` -> pass
- Full suite:
  - `uv run pytest -q` -> pass

## Notes
- This guard detects a class of Word-recovery-risk files that can still appear readable after recovery but are structurally unsafe for handoff.
