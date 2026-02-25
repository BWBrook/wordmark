# wordmark

Wordmark is a Linux-first, CLI-first toolkit for working with `.docx` review workflows outside Microsoft Word.

## Goals
- Open and inspect `.docx` review state (comments and revisions)
- Add comments and apply tracked edits from a CLI or agent
- Accept/reject revisions by author or globally
- Verify fidelity with XML and render-based checks
- Emit machine-readable sidecar artifacts for Git review

## Quickstart

```bash
uv sync --extra dev
uv run wordmark --help
uv run pytest
```

## CLI commands
```bash
uv run wordmark inspect <file.docx> --json
uv run wordmark comment add <file.docx> --anchor "p:1" --text "Review note" --json
uv run wordmark comment add <file.docx> --anchor-json '{"expected_text":"reviewword","context_before":"Section B"}' --text "Review note" --json
uv run wordmark edit apply <file.docx> --patch patch.json --json
uv run wordmark review list <file.docx> --json
uv run wordmark review accept <file.docx> --author "Barry Brook" --json
uv run wordmark review reject <file.docx> --all --json
uv run wordmark review prepare-merge before.docx after.docx --json
uv run wordmark verify before.docx after.docx --profile business-docs --json
uv run wordmark verify before.docx after.docx --profile review-edit --json
uv run wordmark render <file.docx> --out tmp/docs/render_out --json
uv run wordmark artifacts clean --json
uv run wordmark artifacts clean --older-than-days 7 --apply --json
```

## Canonical and edited fixtures
- Canonical immutable examples live under `examples/canonical/`.
- Hard-pattern preflight fixtures live under `examples/canonical/hard_patterns/`.
- Edited/generated working outputs belong under `examples/edited/`.
- Default safety policy is high-fidelity first: strict OOXML localized edits, then UNO fallback, then comment-only fallback (unless overridden by CLI/config flags).

## Edit policy controls
```bash
# Inspect strategy without mutating
uv run wordmark edit apply <file.docx> --patch patch.json --preflight-only --json

# Strict mode (default): no tracked paragraph rewrite fallback
uv run wordmark edit apply <file.docx> --patch patch.json --fidelity-mode strict --json

# Aggressive mode: allow tracked paragraph rewrite fallback when needed
uv run wordmark edit apply <file.docx> --patch patch.json --fidelity-mode aggressive --json
```

`--preflight-only` returns per-operation diagnostics including:
- `classification`
- `reason_code` and `reason_detail`
- `detected_patterns`
- `recommended_engine` and `recommended_strategy`

UNO fallback responses now include per-operation diagnostics (`status`, `replaced_count`, `strategy_used`), and `edit apply` records deterministic low-hit retry attempts under `operation.details.uno_retry` when missed global operations are retried as targeted single replacements.

`edit apply` also emits additive diagnostics by default:
- `operation.details.interop_drift`: likely cross-reference drift signals (`Figure/Table/Eq/Appendix`) from before/after text snapshots.
- `operation.details.risk_summary`: compact policy/risk snapshot (`used_uno_fallback`, risky preflight count, drift severity/warning, mode).

Control flags:
```bash
# Disable drift diagnostics for a run
uv run wordmark edit apply <file.docx> --patch patch.json --no-drift-check --json

# Tighten drift warning threshold
uv run wordmark edit apply <file.docx> --patch patch.json --drift-warning-threshold high --json

# Disable risk summary emission
uv run wordmark edit apply <file.docx> --patch patch.json --no-emit-risk-summary --json
```

## Merge-Back Workflow
For shared/online docs, keep agent edits in local copies and merge by human approval in Word desktop:
```bash
uv run wordmark review prepare-merge before.docx after.docx --json
```
Detailed checklist: `docs/release_gate_word_desktop.md`.

## Artifact housekeeping
```bash
# Preview cleanup scope (safe default)
uv run wordmark artifacts clean --json

# Remove all removable files under artifacts/
uv run wordmark artifacts clean --apply --json

# Remove only files older than 7 days
uv run wordmark artifacts clean --older-than-days 7 --apply --json

# Keep operations transcript while cleaning stale sidecars
uv run wordmark artifacts clean --older-than-days 7 --keep-transcripts --apply --json
```

## Default config
`wordmark.yaml` defines defaults such as:
- default author (`Barry Brook`)
- default initials (`BB`)
- track-changes default on
- engine preference (`ooxml`, then `uno` fallback)
- fidelity policy and fallback behavior (`strict|balanced|aggressive`, unsupported handling, UNO-fail handling)
- verify profiles and gates (`business-docs`, `review-edit`)
