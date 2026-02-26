# 2026-02-26 — Main Manuscript V3 Review Run

## Scope
- Input manuscript: `/mnt/c/Temp/main_manuscript_v3_BB.docx`
- Feedback notes: `/mnt/c/temp/barry_brook_feedback_to_tengyi.md`
- Output manuscript: `/mnt/c/temp/main_manuscript_v3_BB_edited_thu26feb2026.docx`

## Work performed
1. Completed a supervisor-style pass with tracked edits and anchored comments.
2. Translated markdown feedback into additional tracked edits/comments (conceptual issues left as comments, copy/grammar fixes as tracked changes).
3. Added five additional Barry Brook comments to cover unaddressed high-priority feedback areas:
   - keyword fit (`cellular automata`),
   - Box-Cox/normalisation clarity,
   - DFTD timing variable sign/definition,
   - exclusion-rule justification for implausible initial states,
   - reference hygiene checks.
4. Applied micro-cleanup operations for sentence-level fidelity cleanup in management implications.

## Verification
- Command:
  - `uv run wordmark verify /mnt/c/Temp/main_manuscript_v3_BB.docx /mnt/c/temp/main_manuscript_v3_BB_edited_thu26feb2026.docx --profile review-edit --json`
- Result:
  - `verify.passed = true`
  - `render_diff.ok = true`
  - `comment_integrity.ok = true`
  - page growth: `+1` page (within review-edit tolerance)

## Review state summary (post-run)
- Comments: 26 total
  - Barry Brook: 13
  - Nicholas Fountain-Jones: 13
- Revisions: 96 total
  - Barry Brook: 77
  - Nicholas Fountain-Jones: 19

## Edge case observed
- Residual `Unknown Author` values were present in `w:moveTo`/`w:moveFrom` nodes (not in `w:ins`/`w:del`) after UNO fallback operations.
- Current built-in postprocess normalisation targets `w:ins`/`w:del`; move revisions can escape that pass.
- For this document, two `Unknown Author` move revisions were normalised in-place to `Barry Brook` inside `word/document.xml`.

## Follow-up hardening opportunity
- Extend UNO postprocess author normalisation to include `w:moveTo` and `w:moveFrom` so this case is handled automatically.
