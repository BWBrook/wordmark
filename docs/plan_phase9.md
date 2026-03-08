# Phase 9 Plan: Hosted CI and OOXML Review Slice

## Progress
- [x] 1. Add hosted GitHub Actions pure-Python workflow
- [x] 2. Add hosted external-tools workflow
- [x] 3. Strengthen DOCX-core characterization tests around anchors, review transforms, paragraph policy, comment infrastructure, and verify gates
- [x] 4. Extract the OOXML review-transform cluster into `src/wordmark/ooxml_review.py`
- [x] 5. Update architecture/decisions/log documentation
- [x] 6. Run the full local test suite

## Notes
This phase intentionally does not:
- split anchor resolution or localized replacement logic out of `ooxml_engine.py`
- redesign the manuscript source-mapping model
