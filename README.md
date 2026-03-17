# wordmark

Wordmark is a CLI-first toolkit for review workflows across `.docx` and Markdown/Quarto manuscripts, with Linux-first origins and growing macOS support.

## Goals
- Open and inspect `.docx` review state (comments and revisions)
- Add comments and apply tracked edits from a CLI or agent
- Accept/reject revisions by author or globally
- Verify fidelity with XML and render-based checks
- Emit machine-readable sidecar artifacts for Git review
- Bridge Markdown/Quarto collaboration rounds with optional DOCX review handoffs

## Quickstart

```bash
uv sync --extra dev
uv run wordmark --help
uv run pytest
make test-pure
make test-external
make lint
```

## macOS notes

Wordmark's pure-Python lane works on macOS with:

```bash
uv sync --extra dev
make test-pure
make lint
```

Optional host-tool workflows on macOS use:
- LibreOffice for `soffice` rendering and UNO fallback editing
- `pdftoppm` for render verification
- Quarto for default `.qmd` manuscript builds

Homebrew setup that matches the current macOS integration path:

```bash
brew install poppler
brew install --cask libreoffice quarto
```

Notes:
- Wordmark now probes common macOS install locations for `soffice`, LibreOffice's embedded Python launcher, and the Quarto cask binary when they are not on `PATH`.
- render/verify and Quarto-backed manuscript flows are supported on macOS when those tools are installed
- UNO fallback remains disabled by default on macOS because LibreOffice's embedded Python launcher is not yet a stable non-interactive probe target on this host; treat it as experimental only

## Environment contract
Core Python runtime:
- Python `>=3.11`
- `uv` for environment management

Host-installed tools used by optional workflows:
- `soffice` and `pdftoppm` for render/verify image-based checks
- LibreOffice-accessible UNO bindings for fallback editing
- `quarto` for default `.qmd` manuscript builds
- `gh` plus `gh auth status` for GitHub PR feedback ingestion

Conservative local validation paths:
```bash
# Full local suite
uv run pytest

# Pure-Python checks only
make test-pure

# Host-tool integration checks only
make test-external

# Lint
make lint
```

Hosted CI lanes:
- `ci`: required/default GitHub Actions lane running `make lint` and `make test-pure`
- `external-tools`: separate hosted integration lane running `make test-external` on Ubuntu with LibreOffice/UNO/rendering tools installed plus a real Quarto-backed `.qmd` smoke build

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
uv run wordmark manuscript prepare manuscript.qmd --formats docx,pdf --json
uv run wordmark manuscript collect artifacts/manuscript_rounds/<round_id> --notes feedback.md --json
uv run wordmark manuscript synthesize artifacts/manuscript_rounds/<round_id> --source manuscript.qmd --json
uv run wordmark manuscript status artifacts/manuscript_rounds/<round_id> --json
```

## Markdown/Quarto collaboration rounds
Wordmark uses a hybrid model for manuscript collaboration:
- canonical source stays in `.md`/`.qmd`
- reviewers can contribute via PR comments/suggestions, notes markdown, and optional DOCX review files
- feedback is normalized into structured sidecars and synthesized into safe patch proposals

Current guarantees:
- `manuscript synthesize --apply-safe` applies deterministic source-aware edits when line anchors are available, otherwise falls back to deterministic exact-match edits
- repeated matches without reliable source anchors are reported as ambiguous, not auto-applied
- excerpt-based duplicate matches without reliable source anchors are reported as ambiguous, not auto-applied
- imported DOCX comments/revisions are treated as review events, not as a lossless source backport
- malformed round inputs fail fast rather than being silently repaired

Core commands:
```bash
# 1) Prepare a review round bundle
uv run wordmark manuscript prepare chapter.qmd --formats docx,pdf --json

# 2) Collect feedback channels into one bundle
uv run wordmark manuscript collect artifacts/manuscript_rounds/<round_id> \
  --from-pr 123 \
  --notes /path/to/feedback.md \
  --docx-reviewed /path/to/chapter_reviewed.docx \
  --json

# 3) Synthesize safe edits + reports (non-mutating by default)
uv run wordmark manuscript synthesize artifacts/manuscript_rounds/<round_id> \
  --source chapter.qmd \
  --export-critic \
  --json

# 4) Apply only deterministic safe edits when ready
uv run wordmark manuscript synthesize artifacts/manuscript_rounds/<round_id> \
  --source chapter.qmd \
  --apply-safe \
  --json
```

See `docs/markdown-quarto-collab-workflow.md` for the full operator workflow.

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
