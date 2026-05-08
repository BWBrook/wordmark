# 2026-05-08 - Markdown Tracked-Changes Hardening

## Summary
Hardened the manuscript Markdown/Quarto review workflow after a fresh audit of its tracked-change-equivalent behavior.

## Changes
1. Made safe proposals span-aware:
   - line/file anchors now preserve source byte spans
   - safe application verifies anchored text at the intended span
   - overlapping proposals are marked as conflicts
2. Added Markdown-aware guards:
   - YAML front matter
   - fenced code blocks
   - inline code
   - links/images
   - citations
3. Improved CriticMarkup export:
   - proposal-id annotations
   - span-based placement
   - delimiter escaping for nested CriticMarkup-like text
4. Added proposal decision and selected-apply commands:
   - `manuscript decide`
   - `manuscript apply-proposals`
   - append-only decision log and summary sidecars
5. Added regression coverage for repeated anchored lines, Markdown guards, CriticMarkup escaping, and accepted-proposal application.

## Validation
- `uv run pytest tests/test_manuscript_workflow.py -q` -> pass
- `make lint` -> pass
- `uv run pytest` -> pass
- `git diff --check` -> pass
- `make test-pure-cov` -> pass
