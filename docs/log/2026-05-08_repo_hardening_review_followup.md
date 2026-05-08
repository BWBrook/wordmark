# 2026-05-08 - Repo Hardening Review Follow-Up

Implemented the high-priority hardening items from the fresh code review:

- packaged the UNO fallback helper under `src/wordmark/_resources/` and kept `scripts/uno_replace.py` as a checkout compatibility wrapper
- required explicit scope for `review accept` and `review reject`
- added artifact cleanup guardrails for non-`artifacts/` paths, with an explicit force override
- changed DOCX package saves to write a temporary sibling ZIP and atomically replace the target
- fixed comment relationship ID allocation to avoid duplicate `rId*` values
- made `manuscript synthesize --apply-safe` fail on prepare-time source hash drift unless `--allow-source-drift` is supplied
- cleaned stale render pages before `pdftoppm` output collection and made page-size mismatches fail render verification

Regression coverage was added for each changed behavior. Final verification for this pass should include `uv run pytest`, `make lint`, `make test-pure-cov`, and `uv build` plus a wheel-content check for `wordmark/_resources/uno_replace.py`.
