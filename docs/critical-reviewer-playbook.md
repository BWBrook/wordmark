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

Typical supervisor-level comment themes:
- scope creep or unclear narrative focus
- unsupported claims or weak inference
- missing methods detail and reproducibility gaps
- figure/table readability and cross-reference consistency
- framing, contribution clarity, and audience fit

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
uv run wordmark inspect <docx> --json
uv run wordmark review list <docx> --json
```
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

Fidelity heuristics for reviewer-style edits:
1. For tiny clause fixes, target only the minimum phrase to preserve concise tracked deltas.
2. For append-at-end edits (for example adding a short instruction after an existing phrase), prefer a localized replacement that keeps the original prefix unchanged so Word displays an insertion, not full-span replacement.
3. For punctuation/hyphenation fixes (`bird specific` -> `bird-specific`), use focused replacement operations to keep revision scope minimal.
4. Use comments rather than inserted text when the action belongs to the student (for example placeholder checks like keyword/order verification).
5. If a candidate edit would produce broad delete+insert redlines, split it into smaller operations or convert it to comment guidance.

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
