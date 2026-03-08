# Markdown/Quarto Collaboration Workflow

## Purpose
This workflow extends Wordmark from DOCX-native review to hybrid manuscript collaboration where canonical writing is in `.md` or `.qmd`.

Design intent:
1. Keep source-of-truth in plain-text authoring files.
2. Preserve review traceability in structured artifacts.
3. Support both technical and Word-oriented collaborators.

## Collaboration model
- Canonical source: `.md/.qmd`.
- Optional review artifact: generated `.docx` and/or `.pdf`.
- Feedback channels:
  - GitHub PR comments/suggestions (`gh` optional).
  - Markdown notes files.
  - Reviewed DOCX files (comments/revisions imported as events).
- Consolidated record: `feedback.bundle.json`.

Current conservative guarantees:
- `--apply-safe` applies deterministic source-aware edits when line/file anchors are available, otherwise deterministic exact-match edits.
- Repeated matches without reliable source anchors become `ambiguous`; they are reported, not auto-applied.
- Excerpt-based duplicate matches without reliable source anchors also remain `ambiguous`; they are not auto-applied.
- Reviewed DOCX comments/revisions are imported as feedback events and summaries, not as a lossless tracked-change backport to source.
- Missing or malformed round artifacts fail fast so the operator sees the problem immediately.

## Command sequence
### 1) Prepare a review round
```bash
uv run wordmark manuscript prepare chapter.qmd --formats docx,pdf --json
```

Output directory:
`artifacts/manuscript_rounds/<round_id>/`

Key files:
- `manifest.json`: source/build/git provenance, hashes, defaults.
- `prepare.report.json`: build command execution details.
- `rendered.docx` / `rendered.pdf` (if generated).

### 2) Collect feedback from channels
```bash
uv run wordmark manuscript collect artifacts/manuscript_rounds/<round_id> \
  --from-pr 123 \
  --notes /path/to/feedback.md \
  --docx-reviewed /path/to/reviewed.docx \
  --json
```

Key files:
- `feedback.bundle.json`: normalized event records.
- `feedback.timeline.md`: human-readable event timeline.
- `collect.report.json`: input and warning summary.

### 3) Synthesize edit proposals
```bash
uv run wordmark manuscript synthesize artifacts/manuscript_rounds/<round_id> \
  --source chapter.qmd \
  --export-critic \
  --json
```

Non-mutating outputs:
- `proposed.patch`
- `proposed.safe_edits.json`
- `open_issues.md`
- `review_summary.md`
- optional `source_review.critic.md`
- `synthesize.report.json`

### 4) Apply deterministic safe edits (explicit)
```bash
uv run wordmark manuscript synthesize artifacts/manuscript_rounds/<round_id> \
  --source chapter.qmd \
  --apply-safe \
  --json
```

Only deterministic, uniquely matched edits are applied.
Ambiguous or unresolved items remain in `open_issues.md`.

### 5) Check round completeness
```bash
uv run wordmark manuscript status artifacts/manuscript_rounds/<round_id> --json
```

`status` reports stage completion:
- prepare
- collect
- synthesize

## Guidance for reviewers and agents
1. Prefer concise, actionable feedback in notes files.
2. Use explicit replacement phrasing for automatable edits:
`replace 'old phrase' with 'new phrase'`.
3. If you know the source location, prefer anchored notes syntax:
`chapter.qmd:42: replace 'old phrase' with 'new phrase'`
4. Keep conceptual/structural guidance as comments, not forced line rewrites.
5. For Word-oriented collaborators, use reviewed DOCX files for comments/revisions, then ingest via `manuscript collect`.
6. Treat CriticMarkup export as optional reviewer UX, not canonical source.

## Safety boundaries
1. Do not overwrite source unintentionally:
   synthesis is non-mutating unless `--apply-safe` is used.
2. Do not treat generated DOCX as canonical source.
3. Do not rely on automatic DOCX tracked-change backporting in this phase.
4. Preserve round artifacts for auditability unless explicitly cleaned.
