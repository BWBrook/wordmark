# Phase 7 Plan: Markdown/Quarto Collaboration Bridge

## Progress
- [x] 1. Add manuscript command surface (`prepare|collect|synthesize|status`)
- [x] 2. Implement round manifest/build orchestration with provenance hashes
- [x] 3. Implement feedback ingestion from notes, optional GitHub PR, and reviewed DOCX
- [x] 4. Implement safe synthesis outputs (patch, safe edits, open issues, summary, optional CriticMarkup)
- [x] 5. Add end-to-end tests and validate full suite
- [x] 6. Update README/workflow/architecture docs
- [x] 7. Record ADR and execution log

## Scope summary
Phase 7 extends Wordmark beyond DOCX-native mutation into a hybrid manuscript workflow where `.md/.qmd` remains canonical, while collaborators can review through PR comments, notes markdown, and optional DOCX review artifacts.

## Definition of done
1. New manuscript commands are available and documented.
2. Round artifacts provide deterministic, auditable outputs.
3. Safe-apply remains explicit opt-in.
4. Full test suite passes.
