# 2026-03-08 — Phase 10 Manuscript Hardening and Anchor Slice

## Summary
Implemented the next recommended polishing phase across three areas:
1. manuscript workflow hardening
2. second safe `ooxml_engine` split (anchor resolution)
3. lightweight developer lint gate

## Delivered
1. Manuscript hardening
   - expanded characterization around GitHub payload variants, partial/malformed round directories, DOCX delta import semantics, exact-match ambiguity, excerpt ambiguity, and stronger non-mutation guarantees
   - added one real Quarto-backed `.qmd` smoke build test
   - made feedback event ordering deterministic before event IDs are assigned
2. OOXML decomposition slice 2
   - extracted anchor normalization/resolution into `src/wordmark/ooxml_anchor.py`
   - kept `ooxml_engine` as the public integration point
3. Developer quality gates
   - added `ruff`
   - added `make lint`
   - added hosted CI lint job
4. Docs and governance
   - updated README/workflow/architecture docs
   - added ADRs for Quarto smoke CI, anchor extraction, and lint lane

## Validation
- `uv run ruff check .` -> pass
- focused manuscript + OOXML characterization tests -> pass
- `uv run pytest -q` -> pass
- `make test-pure` -> pass
- `make test-external` -> pass

## Deferred
- any broader `ooxml_engine` breakup beyond the anchor slice
- manuscript redesign beyond conservative exact-match / event-translation semantics
- adding a coverage threshold to CI
