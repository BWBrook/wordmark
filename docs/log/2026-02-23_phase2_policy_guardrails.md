# 2026-02-23 Phase 2 Policy Guardrails Log

## Implemented
- Added explicit edit policy controls:
  - `fidelity_mode` (`strict|balanced|aggressive`)
  - `on_unsupported` (`fail|comment|uno`)
  - `on_uno_fail` (`fail|comment`)
  - tracked paragraph rewrite allowance toggle
- Added non-mutating preflight classification for patch operations.
- Enforced strict-mode behavior in OOXML engine:
  - disallow tracked paragraph rewrite fallback unless explicitly allowed.
- Added comment-only fallback path after UNO failure.
- Extended localized tracked replacement to support compatible multi-run matches.

## Fixture layout updates
- Added canonical fixture baseline at `examples/canonical/test_doc.docx`.
- Added `examples/edited/` workspace for generated outputs.

## Verification
- `uv run pytest` -> PASS (`20 passed`).
- Existing word-level regression and new policy tests both pass.

## Notes
- Strict mode now prevents silent fidelity degradation.
- Complex unsupported patterns now route through policy-defined fallback chain and are surfaced in structured CLI output.
