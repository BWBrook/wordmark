# 2026-08-04 Fidelity-Path Simplification Audit

## Scope

This read-only audit examined the current complexity around sidecars,
operation transcripts, edit-policy and fallback modes, interop/risk
diagnostics, UNO precision and low-hit retry, manuscript rounds, and the
fidelity-critical DOCX patch path (`preflight_patch`, `apply_patch`, and
`cli.edit_apply`). The reviewed plan records the callers, contracts, and
characterization coverage for each candidate.

## Evidence and result

| Candidate | Evidence observed | Result |
| --- | --- | --- |
| Sidecars and transcripts | Active writers, cleanup/retention controls, tests, and a documented/intended human or agent consumer; no observed downstream reader or usage evidence. | Retain provisionally pending Barry usage evidence. |
| Policy/fallback modes and interop/risk diagnostics | Live CLI/config controls and tests; diagnostics are consumed by the edit orchestrator, with documented/intended human or agent triage but no observed downstream reader or usage evidence. | Defer consolidation or removal until supported modes are deliberately chosen. |
| UNO precision/retry | Live fallback caller with focused characterization; mutation and retry details protect fidelity. | Defer until representative risky-markup/UNO cases exist. |
| Manuscript rounds | Reachable CLI surface with internal stage consumers, tests, and published workflow docs. | Freeze as optional; do not delete or restructure without a real pilot. |
| Preflight/apply path | Large, fidelity-sensitive functions with direct CLI callers and hard-pattern, failure-mode, and policy tests. | No extraction or shortening by line count alone. |

## Decision

No code cut is justified by the available evidence. No source, test,
configuration, manuscript artifact, or review output was changed, and no
existing historical entry was rewritten; the current ADR-040 and this dated
execution note were added. The audit therefore retains the current safeguards
and records the missing evidence needed for any later narrow simplification.

## Explicit deferrals

- Do not remove sidecar writers, transcript retention, cleanup controls, or
  policy/fallback modes.
- Do not remove `interop_drift.py`, `uno_precision.py`, or the UNO low-hit
  retry without representative fallback evidence and render checks.
- Do not delete or restructure manuscript rounds before a real manuscript
  pilot establishes their maintenance value.
- Do not extract shared preflight/apply planning or shorten `cli.edit_apply`
  merely to reduce line count; revisit only with characterization-backed
  design evidence.

## Guarded validation

Because this result changes no executable files, validation was limited to the
plan's untracked-file check, `git status --short --branch`, the name-only
tracked-diff check, and `git diff --check` as applicable. No tests, builds,
renders, `make`, dependency commands, or package smokes were run for this
audit-only result.

## Final state

The reviewed plan, current ADR-040, and this dated audit log are committed and
tracked. The inherited `.DS_Store` remains the only untracked and unstaged
path; no cleanup or unrelated generated output was touched.
