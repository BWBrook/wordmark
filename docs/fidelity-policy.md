# Fidelity Policy (Phase 3)

## Scope
This policy defines acceptance gates for Linux-native `.docx` review edits under the `business-docs` profile.

## Profile: `business-docs`
Target corpus includes:
- headings and normal paragraphs
- lists
- tables
- inline images
- comments and tracked revisions

## Automated gates
1. Package/OOXML integrity
- DOCX ZIP remains readable.
- Key OOXML parts parse successfully.

2. Comment-reference integrity
- No orphan document comment references (`commentReference`/range IDs without matching comments).

3. Revision accounting
- Report before/after revision counts (`w:ins`, `w:del`) and deltas.

4. Render diff gate
- DOCX -> PDF -> PNG conversion for before/after.
- Per-page diff ratio threshold for `business-docs`: `0.02`.
- Page count must match.
- Diff artifacts persisted under sidecar render directory.

## Tracked-edit policy (Phase 2)
- Default `fidelity_mode`: `strict`.
- In strict mode, tracked paragraph rewrite fallback is disabled.
- Strategy chain for unsupported OOXML localized edits:
  1. OOXML strict attempt
  2. UNO fallback attempt
  3. Comment-only fallback if UNO fails (default policy)
- Paragraph rewrite fallback in tracked mode is only allowed when explicitly enabled (for example `fidelity_mode=aggressive` or `--allow-paragraph-rewrite`).

## Hard-pattern policy (Phase 3)
- Canonical risky-markup fixtures are maintained under `examples/canonical/hard_patterns/`.
- Preflight output must include per-operation:
  - `reason_code`
  - `reason_detail`
  - `detected_patterns`
  - `recommended_engine`
  - `recommended_strategy`
- In strict mode, risky-markup paragraphs (for example hyperlinks, field codes, content controls, run-break constructs) are treated as unsupported/high-risk and routed to fallback policy.

## Anchor policy (Phase 3)
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

## Known non-goals in Phase 1
- Full parity across every advanced OOXML revision pattern.
- Guaranteed layout identity for all arbitrary template families.

## Escalation rules
Escalate to manual review when:
- render diff gate fails,
- comment/reference integrity fails,
- UNO fallback mutates unexpected regions,
- document complexity exceeds Phase 1 supported operation patterns.
