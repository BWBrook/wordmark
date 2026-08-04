# Wordmark Architecture (Phase 11)

## Objective
Provide a cross-platform, CLI-first workflow for:
- editing `.docx` review state (comments + tracked changes) with controlled formatting risk, and
- running hybrid Markdown/Quarto collaboration rounds that keep `.md/.qmd` as canonical source while aggregating review feedback into auditable artifacts.

## High-level design
Wordmark uses a dual-engine mutation strategy:

1. OOXML engine (`src/wordmark/ooxml_engine.py`)
- First-choice deterministic engine.
- Operates directly on DOCX package parts (`word/document.xml`, `word/comments.xml`, rels, content types).
- Supports safe operations:
  - comment insertion
  - paragraph-level tracked text replacement
  - targeted single replace
  - revision accept/reject by author/all (including move revisions)
- Inspection supports explicit text extraction modes:
  - `review-visible` (default): excludes deleted and moved-from text
  - `raw`: includes all tracked text fragments
- Revision taxonomy in outputs is normalized to:
  - `insert`
  - `delete`
  - `move_to`
  - `move_from`
- Supports anchor resolution model:
  - selector compatibility (`p:<index>`, `text:<snippet>`)
  - paragraph+context anchor object (`paragraph_index`, `expected_text`, `context_before`, `context_after`, `occurrence`)
- Emits preflight diagnostics:
  - reason code/detail
  - detected risky patterns
  - recommended engine/strategy
- Keeps untouched ZIP parts byte-identical.

2. UNO fallback engine (`src/wordmark/uno_engine.py` + `src/wordmark/_resources/uno_replace.py`)
- Used for unsupported/high-risk patch operations.
- Delegates to system Python UNO bindings (`/usr/bin/python3`) and headless LibreOffice.
- Supports fallback operations:
  - `replace_text_global`
  - `replace_text_once` (with optional occurrence)
  - `replace_paragraph_text` (matched via `expected_text`)
- Emits per-operation diagnostics:
  - `status`
  - `replaced_count`
  - `strategy_used`
- Emits author-binding diagnostics and runs post-write normalization for newly introduced `Unknown Author` revisions across `w:ins`, `w:del`, `w:moveTo`, and `w:moveFrom`.
- Records fallback reason and optional low-hit retry metadata in operation details.

3. Interop drift diagnostics (`src/wordmark/interop_drift.py`)
- Text-snapshot analyzer for likely cross-reference drift after mutation.
- Scans Figure/Table/Equation/Appendix mention patterns and reports family-level deltas.
- Emits deterministic warning severity (`none|low|moderate|high`) and recommended action text.

## Core modules
- `src/wordmark/cli.py`: command surface and engine orchestration.
- `src/wordmark/docx_package.py`: byte-preserving OOXML ZIP access.
- `src/wordmark/interop_drift.py`: cross-reference drift detection and severity scoring.
- `src/wordmark/manuscript_models.py`: schema models for round manifests, feedback events, and safe edit proposals.
- `src/wordmark/manuscript_rounds.py`: round preparation/build orchestration and status reporting.
- `src/wordmark/manuscript_ingest.py`: feedback ingestion from notes, GitHub PR, and reviewed DOCX artifacts.
- `src/wordmark/manuscript_synthesis.py`: patch proposal synthesis, optional safe apply, and CriticMarkup export.
- `src/wordmark/ooxml_anchor.py`: internal anchor-resolution and anchor-normalization module.
- `src/wordmark/ooxml_engine.py`: inspect/comment/edit/review operations.
- `src/wordmark/ooxml_replace.py`: internal localized replacement and paragraph rewrite module.
- `src/wordmark/ooxml_review.py`: internal review-transform module for accept/reject and move-range cleanup.
- `src/wordmark/uno_engine.py`: UNO bridge, diagnostics, and author post-processing.
- `src/wordmark/render.py`: DOCX -> PDF -> PNG rendering.
- `src/wordmark/verify.py`: integrity and profile-aware render-diff quality gates.
- `src/wordmark/sidecar.py`: Git-friendly artifact writers.
- `src/wordmark/transcript.py`: append-only operation audit log.
- `examples/canonical/hard_patterns/`: canonical risky-markup fixture corpus.

Edit strategy controls:
- policy-driven strategy routing (`strict|balanced|aggressive`)
- preflight classification (`--preflight-only`) before mutation
- explicit fallback chain configuration (`on_unsupported`, `on_uno_fail`)
- deterministic UNO low-hit retry for missed global replacements
- interop drift checks with warning threshold controls
- concise operation risk summary emission for downstream consumers
- merge-back helper output (`review prepare-merge`) for Word desktop handoff
- v2 CLI JSON schema marker (`schema_version: 2`) for `inspect`, `review list`, and `verify`
- manuscript round command surface (`manuscript prepare|collect|synthesize|status`) with schema v1 sidecars

## Data and artifacts
- Canonical source for DOCX operations: `.docx` files.
- Canonical source for manuscript rounds: `.md`/`.qmd` files.
- Sidecars (default under `artifacts/`):
  - `{stem}.text.md` (document text snapshot for chosen `text_mode`, default `review-visible`)
  - `{stem}.comments.json`
  - `{stem}.revisions.json`
  - `{stem}.xml-manifest.json`
  - `{stem}.report.json`
  - `{stem}.render/` with before/after/diff PNG pages from `verify`.
- Transcript: `artifacts/transcripts/operations.jsonl`.

Manuscript round artifacts (default under `artifacts/manuscript_rounds/<round_id>/`):
- `manifest.json` (source/build provenance and hashes)
- `prepare.report.json`
- `feedback.bundle.json` (normalized multi-channel events)
- `feedback.timeline.md`
- `proposed.patch`
- `proposed.safe_edits.json`
- `open_issues.md`
- `review_summary.md`
- `synthesize.report.json`
- optional `source_review.critic.md`
- optional `proposal.decisions.jsonl`
- optional `proposal.decisions.summary.json`
- optional `proposal.apply.report.json`

## Configuration
`wordmark.yaml` controls:
- default author/initials
- track-changes default
- engine order
- fidelity mode and tracked rewrite allowance
- fallback policy and comment-fallback template
- fidelity profiles and profile settings (threshold/page-growth)
- sidecar path templates
- transcript path
- edited output workspace path

## Known boundaries
- Word desktop compare/combine remains a human-driven release action.
- CLI intentionally does not write directly to cloud-hosted shared documents.
- UNO matching still relies on LibreOffice literal search behavior; phrase-level, context-aware patches remain preferred over long full-paragraph literals.
- `review-edit` is for iterative supervision passes, not final release sign-off where strict layout invariance is required.
- `raw` text mode is intentionally lossy for reviewer readability in tracked documents; use it for diagnostics, not human handoff summaries.
- Automatic DOCX tracked-change backport to `.md/.qmd` is intentionally out-of-scope; only verified-span proposals that pass Markdown guards can be auto-applied.
- The first DOCX-core decomposition slice was limited to review transforms; the second slice now moves anchor resolution into `ooxml_anchor.py`.
- Localized replacement and rewrite logic now live in `ooxml_replace.py`, but remain the most fidelity-sensitive OOXML subsystem and should still be changed only behind characterization tests.

Verify gate notes:
- verification now includes OOXML compatibility namespace integrity checks (for example `mc:Ignorable` token declarations) to catch Word recovery-risk files before handoff.
