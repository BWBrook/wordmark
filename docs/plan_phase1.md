# Wordmark Feasibility + Implementation Plan (Linux, CLI-first, Word-compatible)

## Execution Progress
- [x] 1. Repository foundation
- [x] 2. OOXML engine (primary deterministic layer)
- [x] 3. UNO engine (fallback for complex transforms)
- [x] 4. Review object model
- [x] 5. Verification and quality gates
- [x] 6. Agent workflow support
- [x] 7. Documentation and operator UX
- [x] Test suite + reproducible command validation

## Summary
This is feasible on Ubuntu/WSL with your current environment.  
You already have the core runtime stack installed (`LibreOffice 24.2.7`, `soffice`, `Pandoc 3.1.3`, `pdftoppm`, `git`, `python3`), so we can build a repo that opens/edits/saves `.docx` with comments and tracked changes while keeping Microsoft Word round-trip risk controlled through automated guardrails.

The recommended v1 architecture is a **dual-engine pipeline**:
1. **OOXML-structured edits** for deterministic operations (comments, metadata, targeted text ops).
2. **Headless LibreOffice UNO fallback** for complex edits where OOXML-only transforms are brittle.

Selected defaults:
- Primary surface: CLI-first pipeline
- Dependency policy: open-source only
- Fidelity bar: high on representative business docs
- Interop: strong Word round-trip
- Git strategy: `.docx` + sidecar diffs
- Engine strategy: dual engine
- Agent authorship: tracked revisions + comments, with configurable author label, defaulting to `"Barry Brook"`

## Public Interfaces and Types

### CLI surface (`wordmark` / `docxctl`)
1. `wordmark inspect <file.docx> [--json]`
2. `wordmark comment add <file.docx> --anchor "<selector>" --text "<comment>" [--author "<name>"] [--initials "<XX>"]`
3. `wordmark edit apply <file.docx> --patch <patch.json> [--track-changes on|off] [--author "<name>"]`
4. `wordmark review list <file.docx> [--format text|json]`
5. `wordmark review accept <file.docx> [--author "<name>"|--all]`
6. `wordmark review reject <file.docx> [--author "<name>"|--all]`
7. `wordmark verify <before.docx> <after.docx> --profile business-docs`
8. `wordmark render <file.docx> --out tmp/docs/<name>/` (DOCX -> PDF -> PNGs)

### Config file (`wordmark.yaml`)
1. `default_author: "Barry Brook"`
2. `default_initials: "BB"`
3. `track_changes_default: true`
4. `engine_order: ["ooxml", "uno"]`
5. `fidelity_profiles: ["business-docs"]`
6. `sidecar.enabled: true`
7. `sidecar.paths: { text: "...", xml_manifest: "...", render_diff: "..." }`

### Sidecar artifacts for PR review
1. `artifacts/<doc>.text.md` (normalized extracted text)
2. `artifacts/<doc>.comments.json` (comments, author, status, anchor info)
3. `artifacts/<doc>.revisions.json` (insert/delete/move summary, author/date if available)
4. `artifacts/<doc>.xml-manifest.json` (hashes of critical OOXML parts)
5. `artifacts/<doc>.render/` (page PNGs + visual diff metrics)
6. `artifacts/<doc>.report.json` (pass/fail thresholds)

## Implementation Design

### 1. Repository foundation
1. Initialize repo with `src/`, `tests/`, `fixtures/`, `artifacts/`, `tmp/docs/`, `docs/`.
2. Add deterministic environment management for Python deps and CLI entrypoint.
3. Add pre-commit/non-mutating validation commands that never rewrite tracked files unless explicitly invoked.

### 2. OOXML engine (primary deterministic layer)
1. Treat `.docx` as zip package and edit only targeted parts.
2. Implement robust part loader/writer for:
   - `word/document.xml`
   - `word/comments.xml` (+ relationships as needed)
   - revision-related elements in WordprocessingML where operations are safe
3. Preserve untouched XML parts byte-for-byte whenever possible to reduce formatting drift.
4. Add author/timestamp injection hooks using config defaults (`Barry Brook` unless overridden).

### 3. UNO engine (fallback for complex transforms)
1. Add headless LibreOffice orchestration wrapper using isolated user profile dirs.
2. Use UNO only for operations flagged as high-risk in OOXML layer.
3. Re-open and normalize output, then run verification gate before accepting result.
4. Log engine decision and fallback reason in operation report.

### 4. Review object model
1. Define internal model for `Comment`, `Revision`, `Anchor`, `OperationResult`.
2. Guarantee stable IDs for sidecar comparison across runs where possible.
3. Support author filtering for review accept/reject operations.

### 5. Verification and quality gates
1. XML invariants: package integrity, relationship validity, no orphaned comment references.
2. Semantic invariants: comment count deltas match requested operations.
3. Render invariants: page-image diffs under thresholds for unchanged regions.
4. Interop invariants: open-save-open checks through LibreOffice and spot-check through Word in CI/manual matrix.

### 6. Agent workflow support
1. Add machine-friendly JSON I/O for all commands.
2. Add dry-run mode emitting exact intended mutations before write.
3. Add operation transcript for auditability (`who`, `what`, `where`, `engine`, `timestamp`).

### 7. Documentation and operator UX
1. `docs/architecture.md` for dual-engine rationale.
2. `docs/authoring-workflow.md` for human + agent collaboration.
3. `docs/fidelity-policy.md` defining acceptance thresholds and known edge cases.

## Test Cases and Scenarios

### Core functional tests
1. Add comment to paragraph span with explicit author metadata.
2. Add tracked insertion and deletion with default author `"Barry Brook"`.
3. Override author per command and verify metadata persistence.
4. Accept all revisions by author; reject all revisions by author.
5. Mixed comments + revisions + images + tables in one document.

### Fidelity tests (business-doc profile)
1. No unexpected style changes in headings, lists, tables, footnotes.
2. No page overflow/clipping regressions on reference fixtures.
3. No corruption/repair prompt when opening in LibreOffice and Word.
4. Round-trip open/edit/save in Linux workflow and reopen in Word with expected review artifacts intact.

### Failure-mode tests
1. Broken anchors for comment insertion.
2. Conflicting revision ranges.
3. Missing OOXML parts or malformed relationships.
4. UNO failure path and deterministic fallback/error reporting.

### Acceptance criteria (MVP gate)
1. 100% pass on functional review-operation tests for fixture corpus.
2. 0 document-corruption incidents across corpus.
3. Render diff thresholds met for all “no-layout-change-expected” scenarios.
4. Word round-trip spot tests pass on defined sample set.
5. CLI operations emit reproducible machine-readable reports.

## Assumptions and Defaults
1. Default tracked-change author label is `"Barry Brook"` and is user-configurable globally/per-command.
2. Open-source-only policy excludes paid SDK dependencies for v1.
3. CLI-first means human editing remains available via LibreOffice, but automation UX is centered on commands/JSON.
4. “High fidelity” is enforced on the agreed business-doc fixture corpus, not guaranteed for every possible `.docx` construct in v1.
5. Sidecar artifacts are first-class for Git PR review; `.docx` remains canonical source file.

## Risks and Mitigations
1. Risk: OOXML revision semantics are complex and easy to break.  
   Mitigation: restrict OOXML mutations to safe primitives; fallback to UNO for risky transforms; strict invariant tests.
2. Risk: Hidden formatting drift.  
   Mitigation: XML manifest + visual render diff + corpus-based acceptance gate.
3. Risk: Engine behavior differences across LibreOffice versions.  
   Mitigation: pin/test against a baseline version and capture version in reports.

## Source-backed feasibility notes
1. LibreOffice supports managing tracked changes (accept/reject) in review workflows.  
   https://help.libreoffice.org/latest/en-US/text/shared/01/02230400.html
2. LibreOffice help documents comment management/threading capabilities (with some features marked experimental in help pages).  
   https://help.libreoffice.org/latest/ug/text/swriter/01/sidebar_comments.html
3. Pandoc explicitly warns conversions can be lossy and documents `--track-changes` behavior, which is useful for extraction/scripting but not a full-fidelity editor.  
   https://pandoc.org/MANUAL.html
4. `python-docx` documents comment APIs including author/initial metadata; this makes it suitable for comment-centric structured edits.  
   https://python-docx.readthedocs.io/en/latest/user/comments.html
5. Microsoft Open XML docs illustrate the complexity of revision elements (`w:ins`, deletions, moves), reinforcing need for cautious revision handling.  
   https://learn.microsoft.com/en-us/office/open-xml/word/how-to-accept-all-revisions-in-a-word-processing-document
6. ONLYOFFICE docs show track-changes/comment review capabilities (useful comparator if we later evaluate alternative UI/editor paths).  
   https://helpcenter.onlyoffice.com/docs/userguides/document_editor/Review.aspx
