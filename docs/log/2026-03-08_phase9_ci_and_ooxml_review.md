# 2026-03-08 — Phase 9 CI and OOXML Review Slice

## Summary
Implemented the next hardening phase in two tracks:
1. hosted GitHub Actions CI
2. characterization-first extraction of the OOXML review-transform cluster

## Delivered
1. Hosted CI workflows:
   - `.github/workflows/ci.yml`
   - `.github/workflows/external-tools.yml`
2. DOCX-core characterization additions:
   - anchor not found / context mismatch / explicit occurrence
   - comment infrastructure creation invariants
   - strict vs allowed paragraph rewrite behavior
   - author-filtered review transform behavior
   - comment-integrity verify failure path
3. Small internal decomposition:
   - new `src/wordmark/ooxml_review.py`
   - `ooxml_engine.review_action(...)` now delegates to the internal review module
4. Docs and ADR updates for CI policy and the limited OOXML split

## Validation
- Focused characterization tests passed locally.
- Full suite passed with `uv run pytest -q`.

## Deferred
- further `ooxml_engine.py` decomposition
- manuscript redesign or source-aware backport logic
