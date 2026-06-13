# 2026-06-13 Critical Reviewer Dry Run

## Scope
Goal 003 Phase B reviewed the accepted synthetic manuscript generated in Phase
A. The review used the Goal 002 critical-reviewer guidance and kept the split
between direct tracked line edits and comments for author judgment.

## Inputs And Outputs
- Source manuscript: `examples/reviewer_calibration/synthetic_manuscript_goal003.md`
- Baseline DOCX: `examples/canonical/reviewer_dry_run_synthetic_goal003.docx`
- Edited DOCX: `examples/edited/reviewer_dry_run_synthetic_goal003_edited_sat13jun2026.docx`
- Review patch artifact: `artifacts/goal003_review_patch.json`
- Operation transcript: `artifacts/transcripts/operations.jsonl`

## Review Mix
The tracked-edit batch used 15 high-confidence `replace_text_once` operations.
Wordmark represented those as 22 revision fragments in `review list`:
11 inserts and 11 deletes. Eight comments were added for author-judgment issues.

Examples of direct tracked edits:

- `farm houses` -> `farmhouses`
- `blackberry thickets was dense` -> `blackberry thickets were dense`
- `These results suggests` -> `These results suggest`
- `consistent with wider literature` -> `consistent with the wider literature`
- `other fauna that depends` -> `other fauna that depend`
- `landholders who was willing` -> `landholders who were willing`
- `the counts in a way that was hard` -> `the counts in ways that were hard`
- `an artefact of the cameras` -> `a camera artefact`

Examples of comments reserved for author judgment:

- evidence needed for the recolonisation-after-fire claim;
- road-accessible site-selection bias;
- observer allocation and detectability;
- pooling rule for fox detections;
- unsupported extrapolation to a more careful design;
- over-strong management recommendation;
- over-general `any strip is better than none` implication;
- unsupported temporal trend in corridor-edge change.

## Validation Evidence
Initial Wordmark validation passed:

- `uv run wordmark inspect examples/edited/reviewer_dry_run_synthetic_goal003_edited_sat13jun2026.docx --text-mode review-visible --json`
- `uv run wordmark review list examples/edited/reviewer_dry_run_synthetic_goal003_edited_sat13jun2026.docx --text-mode review-visible --json`
- `uv run wordmark verify examples/canonical/reviewer_dry_run_synthetic_goal003.docx examples/edited/reviewer_dry_run_synthetic_goal003_edited_sat13jun2026.docx --profile review-edit --json`

Verification result:

- `passed: true`
- comments: 8 comments, 8 DOCX references, no orphan or unreferenced comments
- revisions: 22 total revision fragments, 11 inserts and 11 deletes
- render diff: 3 pages before and after, no page growth, all pages below the
  `review-edit` threshold
- compatibility namespace integrity: OK

## Guidance Finding
No Goal 002 guidance tuning was needed. The line-edit-first stance was
sufficient for this dry run: routine grammar, punctuation, concision, and
clarity fixes became tracked edits, while methods, evidence, interpretation,
and management claims became comments.

One minor second-pass punctuation cleanup inside already tracked text preflighted
as requiring UNO rather than OOXML. It was not applied, because the main review
actions had already succeeded through safe localized OOXML operations and the
minor cleanup did not warrant fallback risk.
