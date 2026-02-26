# Fidelity Policy (Phase 5)

## Scope
This policy defines acceptance gates for Linux-native `.docx` review edits.

## Profile: `business-docs` (strict)
Target corpus includes:
- headings and normal paragraphs
- lists
- tables
- inline images
- comments and tracked revisions

Automated gates:
1. Package/OOXML integrity.
2. Comment-reference integrity.
3. Revision accounting.
4. Render diff gate with strict limits:
- threshold: `0.02`
- page growth allowance: `0`
- page count must remain unchanged

Use case:
- release-quality checks where layout drift risk must be tightly constrained.

## Profile: `review-edit` (iterative)
Automated gates:
1. Package/OOXML integrity.
2. Comment-reference integrity.
3. Revision accounting.
4. Render diff gate with review-focused tolerance:
- threshold: `0.12`
- page growth allowance: `2`
- bounded growth allowed for active tracked-edit rounds

Use case:
- supervisor/author iteration loops where many edits/comments are expected and strict release invariance is premature.

## Tracked-edit policy
- Default `fidelity_mode`: `strict`.
- In strict mode, tracked paragraph rewrite fallback is disabled.
- Localized replacements must compute common prefix/suffix and emit minimal middle-segment `w:del`/`w:ins` deltas where safe.
- `replace_paragraph_text` must attempt localized full-string replacement before any tracked paragraph rewrite fallback.
- Revision accounting and reviewer-facing extraction must treat move revisions (`w:moveTo`, `w:moveFrom`) as first-class tracked changes.
- Default inspection mode is `review-visible` (exclude deleted/moved-from text); raw mode is for diagnostics only.
- Strategy chain for unsupported OOXML localized edits:
  1. OOXML strict attempt
  2. UNO fallback attempt
  3. Comment-only fallback if UNO fails (default policy)
- Paragraph rewrite fallback in tracked mode is only allowed when explicitly enabled (for example `fidelity_mode=aggressive` or `--allow-paragraph-rewrite`).

## Hard-pattern policy
- Canonical risky-markup fixtures are maintained under `examples/canonical/hard_patterns/`.
- Preflight output must include per-operation:
  - `reason_code`
  - `reason_detail`
  - `detected_patterns`
  - `recommended_engine`
  - `recommended_strategy`
- In strict mode, risky-markup paragraphs (for example hyperlinks, field codes, content controls, run-break/tab constructs) are treated as unsupported/high-risk and routed to fallback policy.

## UNO fallback reliability policy
- UNO output must remain auditable through `operation_results` diagnostics.
- UNO payload must report `author_binding_status` for track-change attribution observability.
- If UNO introduces revisions with unresolved author fields, post-process normalization must bind newly introduced `Unknown Author` revisions to the requested author and record `author_binding_postprocess`.
- Unknown-author normalization must cover `w:ins`, `w:del`, `w:moveTo`, and `w:moveFrom`.
- Before UNO apply, eligible `replace_text_once` operations should be rewritten to `replace_span_once` with explicit in-match span metadata (`span_start`, `span_length`, `replacement`) so only the intended substring is mutated inside the matched phrase.
- Rewrite outcomes must be recorded as `uno_precision_rewrite`.
- If global replacements miss, CLI may perform one deterministic retry by converting missed `replace_text_global` operations to `replace_text_once`.
- Retry metadata must be recorded under operation details; no silent strategy changes.

## Interop drift diagnostics policy
- `edit apply` should run cross-reference drift diagnostics by default.
- Drift diagnostics track text-level changes in reference families:
  - `figure`
  - `table`
  - `equation`
  - `appendix`
- Warning threshold is explicit and operator-controlled (`low|moderate|high`).
- Drift output is advisory metadata only; it must not alter mutation behavior.
- Operation output should include `risk_summary` for fast triage of:
  - fallback path used (`used_uno_fallback`)
  - risky preflight operation count
  - drift severity and warning status

## Concurrency/write-safety policy
- Mutating commands targeting the same `.docx` must be serialized with an exclusive per-file lock (`<docx>.wordmark.lock`).
- Concurrent edits to one file without lock coordination are out of policy due to reproducible UNO store/write collisions.

## Anchor policy
- Preferred anchor model is paragraph+context:
  - `paragraph_index`
  - `expected_text`
  - `context_before`
  - `context_after`
  - `occurrence`
- Ambiguous or unresolved anchors must surface explicit machine-readable codes:
  - `anchor_not_found`
  - `anchor_ambiguous`
  - `anchor_context_mismatch`

## Interop policy
- Linux automated checks are mandatory.
- LibreOffice round-trip behavior is covered by render and integrity checks.
- Microsoft Word desktop round-trip spot-check remains a manual release gate for high-risk documents.

## Escalation rules
Escalate to manual review when:
- render diff gate fails,
- comment/reference integrity fails,
- UNO fallback yields unexpectedly low hit rates,
- UNO post-process reports unresolved unknown revision authors after normalization,
- interop drift warning is emitted for moderate/high-severity cross-reference changes,
- document complexity exceeds supported operation patterns.
