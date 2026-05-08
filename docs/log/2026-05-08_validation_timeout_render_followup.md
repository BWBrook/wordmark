# 2026-05-08 - Validation, Timeout, and Render Coverage Follow-Up

Completed the remaining action items from the initial repository review:

- added `wordmark.validation` for schema-style patch and anchor JSON validation at the CLI boundary
- rejected ambiguous comment anchor modes, malformed anchor selectors, empty `find` strings, unknown patch operation types, and invalid span/occurrence fields before mutation
- added bounded timeouts for `gh auth`, Git metadata probes, GitHub API ingestion, and manuscript build commands
- added pure-lane tests for render command timeout reporting, stale `pdftoppm` page cleanup, page-dimension mismatch verification failure, and persisted render artifact cleanup
- manually dispatched and confirmed the hosted `external-tools` workflow on commit `28b5ebf8c035181b4f6c9c9147fb8159f608f51d`

Targeted verification passed with `uv run pytest tests/test_cli_validation.py tests/test_subprocess_timeouts.py tests/test_render_verify_pure.py`.
