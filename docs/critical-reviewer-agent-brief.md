# Critical Reviewer Agent Brief

Use this brief before reviewing a manuscript, chapter, proposal, or supplement
with Wordmark.

## Operating Stance
Read the whole document first, then work in two channels:
1. Make high-confidence tracked line edits for grammar, punctuation, British
   English spelling, concision, clarity, and local sentence flow.
2. Leave comments for scientific, structural, evidentiary, interpretive, or
   author-choice issues.

Do not turn obvious edits into comments. If the intended fix is clear and does
not change meaning, apply it as a tracked edit.

## Line Edits To Make Directly
- Subject-verb agreement and tense consistency.
- Punctuation, hyphenation, and spacing fixes.
- British English normalisation when no journal style overrides it.
- Removal of filler such as `in order to`, `it is important to note that`, or
  needless hedging, when meaning is preserved.
- Local antecedent clarification where the referent is clear.
- Sentence-flow fixes that keep the author's claim intact.

## Comments To Reserve
- Missing evidence, citations, methods detail, or reproducibility information.
- Claims that require scientific judgment, reanalysis, or source checking.
- Structural problems in the argument, section order, or narrative focus.
- Figure/table interpretation, cross-reference problems, or reader-facing
  explanation gaps.
- Rewrites where several valid versions would change emphasis.

## Patch Discipline
- Prefer `replace_text_once` for phrase-level edits.
- Add anchor context when the same phrase appears more than once.
- Use `replace_text_global` only after confirming every occurrence should
  change.
- Split broad rewrites into small tracked edits plus comments where author
  judgment remains.
- Verify revisions and comments before handoff.

Use `examples/reviewer_calibration/critical_line_edits.yaml` as the compact
calibration fixture for this stance.
