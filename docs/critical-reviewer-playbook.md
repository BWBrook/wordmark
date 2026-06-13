# Critical Reviewer Playbook (Agent)

## Purpose
This playbook helps a fresh agent combine domain judgment with Wordmark tooling to perform high-quality supervisory review on papers, chapters, and supplementary documents.

The core principle is:
- always start by reading the whole document, to understand the full context,
- make precise tracked edits where confidence is high,
- leave comments where author judgment is required,
- keep every change auditable.

## Reviewer stance
Use two channels of intervention intentionally:
1. Tracked changes for line-level or sentence-level fixes you are confident should be directly applied.
2. Comments for structural, conceptual, evidentiary, or interpretation issues the student/author should resolve.

The default stance is line-edit first. If the change is a normal editor's fix
and the intended wording is clear, apply it as a tracked edit instead of
leaving a vague comment. Reviewer confidence should be spent on the page:
grammar, punctuation, British English spelling, concise phrasing, local sentence
flow, and obvious antecedent fixes usually belong in tracked changes.

Typical supervisor-level comment themes:
- scope creep or unclear narrative focus
- unsupported claims or weak inference
- missing methods detail and reproducibility gaps
- figure/table readability and cross-reference consistency
- framing, contribution clarity, and audience fit

## Edit-versus-comment decision rules
Use tracked edits when all of these are true:
1. The fault is local to a word, phrase, clause, sentence, or short paragraph.
2. The replacement preserves the author's intended meaning.
3. A reasonable supervisor would not need the author to choose among competing scientific interpretations.
4. The edit can be expressed as a precise, auditable replacement.

Use comments when any of these are true:
1. The fix needs author judgment, new evidence, new analysis, or source checking.
2. The issue affects argument structure, study design, interpretation, or claims.
3. Several valid rewrites are possible and the choice changes emphasis.
4. The edit would require broad paragraph rewriting that Wordmark cannot represent cleanly.

When both channels are useful, do the local tracked edit first and add a comment
only for the remaining author decision. Avoid comments that merely describe an
edit you could safely make yourself.

## Calibration examples
Weak reviewer feedback says what might be wrong but leaves easy work for the
author. Preferred feedback applies the safe edit and reserves comments for
judgment calls.

| Situation | Weak feedback | Preferred action |
| --- | --- | --- |
| Subject-verb agreement | "Check grammar in this sentence." | Track `results suggests` -> `results suggest`. |
| Hyphenation | "Maybe hyphenate this phrase." | Track `bird specific` -> `bird-specific`. |
| British English | "Use consistent spelling." | Track `behavior` -> `behaviour` where journal style allows. |
| Wordiness | "This could be shorter." | Track `in order to` -> `to` when meaning is unchanged. |
| Antecedent clarity | "This is unclear." | Track `This suggests` -> `This pattern suggests` if the antecedent is explicit. |
| Sentence flow | "Sentence is awkward." | Track a focused clause-order fix if the logic is unchanged. |
| Missing evidence | "Needs evidence." | Comment with the exact claim, why support is needed, and what evidence/source to add. |
| Interpretation choice | "Maybe soften this claim." | Comment if softening changes the scientific interpretation or conclusion. |

## Safety defaults
1. Never overwrite original files; always write edited outputs to `examples/edited/` (or a user-specified safe output path) with a dated suffix.
2. Prefer OOXML-safe localized operations first.
3. Keep strict policy defaults unless task context explicitly justifies broader edits.
4. Preserve transcript and sidecars for auditability.
5. Run one mutating workflow per target file; Wordmark serializes writes with `<docx>.wordmark.lock`.

## Language convention
When acting in editor/reviewer role, prefer British English spelling by default unless the user or target journal style guide requests otherwise.

Examples:
- use `organise`, not `organize`
- use `behaviour`, not `behavior`
- use `modelling`, not `modeling`
- use `harmonised`, not `harmonized`

## Recommended workflow
1. Inspect baseline:
```bash
uv run wordmark inspect <docx> --text-mode review-visible --json
uv run wordmark review list <docx> --text-mode review-visible --json
```
Use `--text-mode raw` only for low-level diagnostics when you need to inspect full tracked XML text footprints.
2. Build a review plan from document structure:
- quick language edits (grammar/clarity)
- medium rewrites (sentence tightening)
- high-level comments (logic/structure)
3. Run patch preflight before mutation:
```bash
uv run wordmark edit apply <docx> --patch patch.json --preflight-only --json
```
4. Apply edits with policy controls:
```bash
uv run wordmark edit apply <docx> --patch patch.json --json
```
5. Add comments for unresolved/high-level issues:
```bash
uv run wordmark comment add <docx> --anchor-json '{...}' --text "..." --json
```
6. Verify and render:
```bash
uv run wordmark verify <before.docx> <after.docx> --profile review-edit --json
uv run wordmark render <after.docx> --out tmp/docs/review_render --json
```
7. Re-inspect revisions/comments and summarize outcomes for the human.

## Edit strategy guidance
Use these operation patterns deliberately:
- `replace_text_once`: preferred for precise word/phrase edits.
- `replace_paragraph_text`: now tries localized full-string replacement first; keep for genuine sentence/paragraph rewrites, not trivial token fixes.
- `replace_text_global`: useful for repeated terminology normalization, but verify hit counts and review context.

When authoring patches:
1. Start narrow: phrase-level replacements outperform long literal paragraph strings for reliability.
2. Add anchor context when ambiguity is plausible (`expected_text`, `context_before`, `context_after`, `occurrence`).
3. For repeated tokens, specify `occurrence` where available.
4. Prefer several small, high-confidence replacements over one sweeping paragraph rewrite.

Fidelity heuristics for reviewer-style edits:
1. For tiny clause fixes, target only the minimum phrase to preserve concise tracked deltas.
2. For append-at-end edits (for example adding a short instruction after an existing phrase), prefer a localized replacement that keeps the original prefix unchanged so Word displays an insertion, not full-span replacement.
3. For punctuation/hyphenation fixes (`bird specific` -> `bird-specific`), use focused replacement operations to keep revision scope minimal.
4. Use comments rather than inserted text when the action belongs to the student (for example placeholder checks like keyword/order verification).
5. If a candidate edit would produce broad delete+insert redlines, split it into smaller operations or convert it to comment guidance.
6. If the edit is obvious but repeated, preflight the hit count and use `replace_text_global` only when every occurrence has the same intended correction.

## Interpreting UNO fallback output
UNO payload now includes per-operation diagnostics:
- `status` (`applied` or `not_found`)
- `replaced_count`
- `strategy_used`
- `author_binding_status`
- `operation_results[]`

Operation details may also include:
- `author_binding_postprocess` when `Unknown Author` revisions introduced by UNO are normalized to the requested author label
- `uno_retry` metadata when low-hit global replacements are retried as targeted single replacements
- `uno_precision_rewrite` metadata when fallback `replace_text_once` operations are narrowed to smaller spans before UNO apply
- `interop_drift` metadata when Figure/Table/Equation/Appendix references changed between before/after snapshots
- `risk_summary` metadata for quick triage of fallback risk (`used_uno_fallback`, risky op count, drift severity/warning)

When `interop_drift.warning` is true:
1. Treat the pass as provisionally complete, not release-ready.
2. Run `review prepare-merge` and complete a Word desktop compare/combine check.
3. Prioritise validation of all changed reference families reported in `interop_drift.changed_families`.

## Verification profile selection
Use `business-docs` for release-quality, layout-sensitive sign-off.
- strict render threshold
- no page growth allowed

Use `review-edit` for iterative supervision rounds.
- more tolerant render threshold
- bounded page growth allowed
- still requires comment/reference integrity and render pass criteria

## Comment-writing standards
Good supervisor comments are:
1. Specific about the issue.
2. Actionable with clear next step.
3. Proportionate in tone and scope.
4. Focused on decisions the author must make, not on routine grammar or style
   fixes that should have been tracked.

Template pattern:
- Observation: what is unclear or weak.
- Why it matters: impact on interpretation/readability.
- Action request: what to revise.

## Handoff checklist
Before declaring a document ready for user review:
1. Confirm output path and filename explicitly.
2. Summarize edit categories (grammar, phrasing, structural comments).
3. Report verify profile and pass/fail outcome.
4. Flag any unresolved limitations (for example fallback misses or manual Word desktop checks).
5. Keep artifacts/transcript available unless user requested cleanup.

## Revision semantics reminder
Wordmark revision outputs use normalized types:
- `insert`
- `delete`
- `move_to`
- `move_from`

For review accept/reject:
- accept keeps inserts and move destinations, removes deletions and move sources
- reject removes inserts and move destinations, restores deletions and move sources
