# Phase 3 Plan: Safety-First Expansion

## Execution Progress
- [x] 1. Hard-pattern fixture corpus and checksums
- [x] 2. Preflight diagnostics expansion and strict routing evidence
- [x] 3. Richer paragraph+context anchor model (backward compatible)
- [x] 4. Word desktop merge-back workflow support (SOP + helper output)
- [x] 5. Tests, docs, decision records, and execution logs

## Summary
Phase 3 extends Wordmark in three implementation waves:
1. Improve safety and explainability for complex OOXML patterns.
2. Add richer anchor semantics for disambiguation-safe edits/comments.
3. Formalize human-gated Word desktop merge-back workflow.

## Phase goals
1. Preserve strict fidelity defaults and avoid silent degradation.
2. Make preflight strategy selection decision-complete for operators and agents.
3. Support anchor resolution using paragraph index + local text context.
4. Keep shared/online documents untouched until manual GUI approval.

## Acceptance criteria
1. Expanded hard-pattern fixture corpus lives in `examples/canonical/` with `.sha256` sidecars.
2. Preflight output includes per-operation reason codes and detected pattern evidence.
3. Anchor resolution errors are explicit and machine-parseable.
4. Backward compatibility preserved for `p:<index>` and `text:<snippet>` selectors.
5. Merge-back SOP docs and desktop checklist are present and linked.
6. `uv run pytest` passes with added phase-3 tests.

## Constraints and defaults
1. Keep strict mode as default.
2. Do not add direct cloud write-back behavior.
3. Keep canonical fixtures immutable and edited outputs separated.
