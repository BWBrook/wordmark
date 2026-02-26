# Phase 6 Plan: Move Revision Semantics and Review-Visible Inspection

## Execution Progress
- [x] 1. Normalize revision taxonomy to `insert|delete|move_to|move_from` in inspect/review/verify outputs
- [x] 2. Add explicit text extraction modes and set default to `review-visible`
- [x] 3. Expand UNO unknown-author normalization to include move revisions
- [x] 4. Implement move-aware accept/reject semantics and orphan range-marker cleanup
- [x] 5. Roll CLI JSON outputs to schema v2 (`inspect`, `review list`, `verify`)
- [x] 6. Update sidecar text snapshots to write extracted document text instead of revision-only concatenation
- [x] 7. Add regression tests for move semantics, schema v2, and text-mode behavior
- [x] 8. Run full verification (`uv run pytest`)
- [x] 9. Update docs, decisions, and execution logs

## Summary
Phase 6 hardens tracked-change fidelity around move revisions and aligns machine-readable outputs with reviewer-visible behavior. The implementation closes the `Unknown Author` move-tag gap, prevents duplicated extracted text from move-pair artifacts, and formalizes a v2 schema for inspection/review/verification payloads.
