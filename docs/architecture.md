# Wordmark Architecture (Phase 1)

## Objective
Provide a Linux-first, CLI-first workflow for editing `.docx` review state (comments + tracked changes) with controlled formatting risk and Git-friendly artifacts.

## High-level design
Wordmark uses a dual-engine mutation strategy:

1. OOXML engine (`src/wordmark/ooxml_engine.py`)
- First-choice deterministic engine.
- Operates directly on DOCX package parts (`word/document.xml`, `word/comments.xml`, rels, content types).
- Supports safe operations in v1:
  - comment insertion
  - paragraph-level tracked text replacement
  - targeted single replace
  - revision accept/reject by author/all
- Keeps untouched ZIP parts byte-identical.

2. UNO fallback engine (`src/wordmark/uno_engine.py` + `scripts/uno_replace.py`)
- Used for unsupported/high-risk patch operations.
- Delegates to system Python UNO bindings (`/usr/bin/python3`) and headless LibreOffice.
- Currently supports `replace_text_global` operations.
- Records fallback reason and engine choice in operation report metadata.

## Core modules
- `src/wordmark/cli.py`: command surface and engine orchestration.
- `src/wordmark/docx_package.py`: byte-preserving OOXML ZIP access.
- `src/wordmark/ooxml_engine.py`: inspect/comment/edit/review operations.
- `src/wordmark/uno_engine.py`: fallback bridge and error surfacing.
- `src/wordmark/render.py`: DOCX -> PDF -> PNG rendering.
- `src/wordmark/verify.py`: integrity and render-diff quality gates.
- `src/wordmark/sidecar.py`: Git-friendly artifact writers.
- `src/wordmark/transcript.py`: append-only operation audit log.

## Data and artifacts
- Canonical source: `.docx` files.
- Sidecars (default under `artifacts/`):
  - `{stem}.text.md`
  - `{stem}.comments.json`
  - `{stem}.revisions.json`
  - `{stem}.xml-manifest.json`
  - `{stem}.report.json`
  - `{stem}.render/` with before/after/diff PNG pages from `verify`.
- Transcript: `artifacts/transcripts/operations.jsonl`.

## Configuration
`wordmark.yaml` controls:
- default author/initials
- track-changes default
- engine order
- fidelity profiles
- sidecar path templates
- transcript path

## Known boundaries (Phase 1)
- OOXML tracked-change edits are intentionally constrained to safe paragraph-level transforms.
- Complex revision constructs (moves, nested field code scenarios, advanced style-preserving run surgery) are out of scope in v1.
- Microsoft Word desktop spot-check remains a manual verification gate outside this Ubuntu environment.
