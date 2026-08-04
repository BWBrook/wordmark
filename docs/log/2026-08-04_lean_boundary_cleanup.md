# 2026-08-04 Lean Boundary Cleanup

## Scope

This tranche removes three high-confidence maintenance residues without
changing active DOCX review semantics or the optional manuscript-rounds
surface:

- `python-docx` is now a development-only dependency used by test fixtures;
- duplicated pure render characterization was removed from the external test
  module;
- the obsolete checkout-only `scripts/uno_replace.py` wrapper and fallback
  branch were removed in favour of the packaged helper resource.

## Files Changed

- `pyproject.toml`
- `uv.lock`
- `tests/test_verify_and_render.py`
- `src/wordmark/uno_engine.py`
- `scripts/uno_replace.py` (removed)
- `docs/architecture.md`
- `docs/decisions.md`
- `docs/superpowers/plans/2026-08-04-lean-boundary-cleanup.md`
- this execution note

## Validation

- `uv lock --check` passed.
- `git diff --check` passed.
- `uv run pytest` passed: `127 passed, 5 skipped`.
- `make check` passed: `127 passed, 5 skipped`; Ruff clean.
- `make test-external` passed: `10 passed, 5 skipped, 117 deselected`.
- `uv build --out-dir /tmp/wordmark-lean-boundary-cleanup-0804` passed.
- Wheel inspection confirmed `wordmark/_resources/uno_replace.py` is present
  and `scripts/uno_replace.py` is absent.
- Source smoke resolved
  `src/wordmark/_resources/uno_replace.py` through
  `uno_engine._helper_script_path()`.
- Isolated wheel smoke resolved the packaged helper from the installed wheel
  at `/Users/bwbrook/.cache/uv/archive-v0/GlGPVCzdRpoK1d54/lib/python3.14/site-packages/wordmark/_resources/uno_replace.py`.

One focused repair was required: the initial full suite exposed that
`uno_engine.py` still uses `Path` for temporary patch files after the fallback
branch removal. The import was restored and the complete checks then passed.
