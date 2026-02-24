# Phase 4 Plan: Reliability and Reviewer Throughput

## Execution Progress
- [x] 1. UNO fallback diagnostics and targeted replace support
- [x] 2. Deterministic UNO low-hit retry routing in CLI
- [x] 3. Verify profile split (`business-docs` + `review-edit`) with profile reasoning
- [x] 4. Tests for UNO diagnostics/retry and profile-aware verify
- [x] 5. Critical-reviewer playbook and supporting docs updates
- [x] 6. Decisions/log updates and full verification run

## Summary
Phase 4 sharpens behavior after advanced mixed-content testing by improving UNO observability, adding deterministic retry behavior for low-hit replacements, and introducing a review-oriented verify profile that tolerates bounded document growth while still surfacing fidelity risk.

## Goals
1. Make UNO fallback auditable at per-operation granularity.
2. Improve replacement reliability without introducing hidden heuristics.
3. Keep strict release-quality gate (`business-docs`) unchanged.
4. Provide a practical reviewer profile (`review-edit`) for iterative supervision workflows.
5. Equip fresh agents with a concrete playbook for high-quality, tool-aware critical review.

## Acceptance Criteria
1. UNO helper supports `replace_text_once` (with optional `occurrence`) and reports per-operation status.
2. CLI records and exposes retry metadata when low-hit global operations are retried.
3. `verify` includes profile-specific thresholds/tolerances and explicit `profile_reasoning` output.
4. `business-docs` behavior remains strict and backward-compatible.
5. Tests cover new behavior and `uv run pytest` passes.
6. Non-trivial decisions are recorded in `docs/decisions.md` and execution notes in `docs/log/`.

## Constraints
1. OOXML-first remains default; UNO is fallback.
2. No silent mutation strategy changes; retries must be explicit in output metadata.
3. Canonical fixtures remain immutable; edited outputs remain under `examples/edited/`.
