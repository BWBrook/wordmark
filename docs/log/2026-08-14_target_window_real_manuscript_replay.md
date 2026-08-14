# 2026-08-14 Target-Window Real-Manuscript Replay

## Scope

Goal 005 replaced paragraph-wide risk vetoes for `replace_text_once` with an
exact first-match OOXML target window. It also made preflight simulate ordered
OOXML mutations, enabled Word's document-level track-revisions setting after a
tracked apply, and retained paragraph-wide guards for paragraph rewrites.

The change was tested against fresh copies of the three Ink NEE manuscripts
from the prior real pilot. Source documents and the prior edited outputs were
not modified. The new ignored evidence bundle is under
`artifacts/real_pilots/ink_nee_goal005/`.

## Result

- Applied 65 of 120 proposed line-edit operations, up from 48 in the prior
  pilot. All 48 prior edits were retained and 17 additional operations were
  recovered.
- Every applied operation produced its exact character-minimal common-middle
  delete/insert delta.
- Applied all 30 new comments and preserved all seven inherited comments.
  Final comment counts were 31, 3, and 3; all 26 targeted comment ranges were
  localized exactly.
- Wordmark itself produced one enabled direct `w:trackRevisions` child in each
  edited document. The former post-processing settings script was not used.
- Field, instruction-text, and hyperlink node sequences were unchanged from
  source: main 270/90/1, supplement 9/3/0, and extended data 0/0/0.
- Inspect, review-list, `review-edit` verification, and render checks passed in
  raw and review-visible modes. Page counts stayed at 36, 11, and 6.
- All 53 source/edited page pairs were inspected at readable scale. No
  clipping, overlap, blanking, missing content, table or figure damage, or
  material layout drift was found.

Of the 55 withheld operations, 53 still intersect unsafe markup or incompatible
run topology. Two compatible multi-run targets were classified safe by the
product but remained outside this pilot's deliberately single-run execution
envelope. Replaying the full 53-page acceptance pass for those two operations
would not change the Goal 005 decision.

## Implementation Notes

- Protected complex-field and comment-range state now carries across body
  paragraphs.
- Preflight and apply use the same target planner and sequential mutation
  semantics, including guarded paragraph-rewrite paths.
- New revision IDs are allocated above every numeric `w:id` already present in
  `word/document.xml`.
- `w:trackRevisions` is inserted according to the settings schema predecessor
  prefix and existing disabled or misplaced settings are normalized.

The first replay exposed an obsolete paragraph-wide diagnostic veto in the
ignored pilot harness. Removing that veto was necessary to exercise the new
contract. A second narrow harness adjustment used a unique surviving substring
for one comment whose anchor capitalization changed through a recovered tracked
edit. Neither adjustment changed product code or manuscript content.

## Validation

- `uv lock --check` passed.
- `git diff --check` passed.
- `make check` passed: 147 tests passed, 5 skipped; Ruff clean.
- `make test-pure-cov` passed: 137 tests passed, 15 deselected; total coverage
  85.51% against the 80% floor.
- `make test-external` passed: 10 tests passed, 5 skipped, 137 deselected.
- Real-pilot acceptance passed; see
  `artifacts/real_pilots/ink_nee_goal005/analysis/execution/acceptance_report.md`.
