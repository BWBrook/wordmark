# Phase 5 Plan: Interop Drift Visibility and Risk Summary

## Execution Progress
- [x] 1. Add interop drift analysis module for cross-reference families
- [x] 2. Integrate drift check into `edit apply` with explicit CLI controls
- [x] 3. Emit operation-level risk summary metadata for auditability
- [x] 4. Add regression tests for drift analysis and CLI metadata/flags
- [x] 5. Update docs, decision records, and execution logs
- [x] 6. Run full verification and capture results

## Summary
Phase 5 improves observability after fallback-heavy editing by adding cross-reference drift diagnostics and a concise risk summary to `edit apply` output, so operators can quickly decide when Word desktop merge/validation is needed.

## Goals
1. Surface likely Figure/Table/Equation/Appendix numbering drift after mutation.
2. Keep drift signaling deterministic, lightweight, and machine-readable.
3. Provide one concise risk block (`risk_summary`) that downstream agents and humans can consume.
4. Preserve existing OOXML-first behavior and fallback semantics.

## Acceptance Criteria
1. `edit apply` can run drift analysis by default and disable it explicitly with flags.
2. Drift warning sensitivity is operator-tunable (`low|moderate|high`).
3. Output includes `operation.details.interop_drift` and `operation.details.risk_summary` when enabled.
4. Tests cover pure drift analysis plus CLI integration/flag behavior.
5. `uv run pytest` passes and docs/decision/log records are updated.

## Constraints
1. Drift analysis is heuristic text-level diagnostics, not a full field-code evaluator.
2. No silent behavior changes to mutation engines; diagnostics are additive metadata.
3. Canonical fixtures remain immutable.
