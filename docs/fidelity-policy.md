# Fidelity Policy (Phase 1)

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
