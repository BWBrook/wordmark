# Phase 11 Plan: Replace Slice, Source-Aware Manuscript Apply, and Coverage Gate

## Progress
- [x] 1. Make manuscript safe-apply source-aware when line/file anchors are available
- [x] 2. Extend manuscript tests for anchored notes, wrong-file suggestions, malformed rounds, and real Quarto smoke build
- [x] 3. Extract localized replacement and paragraph rewrite logic into `src/wordmark/ooxml_replace.py`
- [x] 4. Add a conservative pure-lane coverage floor with `make test-pure-cov`
- [x] 5. Update CI, docs, ADRs, and execution log
- [x] 6. Run lint, pure tests, coverage-backed pure tests, external tests, and the full suite

## Notes
This phase intentionally does not:
- implement AST/source-map manuscript backporting
- perform a broad OOXML-engine redesign
