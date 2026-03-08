# Phase 10 Plan: Manuscript Hardening, Anchor Slice, and Lint Gate

## Progress
- [x] 1. Expand manuscript characterization for payload variants, malformed rounds, ambiguity, and non-mutation guarantees
- [x] 2. Add one real Quarto-backed manuscript smoke build path to the external-tools lane
- [x] 3. Extract anchor normalization/resolution into `src/wordmark/ooxml_anchor.py`
- [x] 4. Add `ruff`, `make lint`, and a hosted CI lint job
- [x] 5. Update README, workflow docs, architecture, decisions, and execution log
- [x] 6. Run lint, pure tests, external tests, and the full suite

## Notes
This phase intentionally does not:
- move localized replacement logic out of `ooxml_engine.py`
- change any public CLI or JSON contracts
- redesign manuscript backport/source-mapping semantics
