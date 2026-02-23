# Architecture Decisions

## 2026-02-23 - ADR-001: Python-first CLI stack
- Status: accepted
- Context: We need a Linux-native, agent-friendly `.docx` workflow with tight control over side effects.
- Decision: Implement v1 as a Python package with a CLI (`wordmark`) using `lxml` for OOXML mutation, optional LibreOffice UNO fallback, and JSON sidecars for review.
- Consequences: Fast iteration and testability in WSL; revision semantics remain constrained to safe operations in v1.

## 2026-02-23 - ADR-002: UNO bridge runs on system Python
- Status: accepted
- Context: `uv` virtual environments do not include LibreOffice `uno` bindings; direct import fails in venv.
- Decision: Execute UNO fallback through `/usr/bin/python3` helper script (`scripts/uno_replace.py`) and keep CLI runtime in uv-managed env.
- Consequences: Reliable UNO access without polluting project env; fallback behavior depends on system LibreOffice/pyuno availability.

## 2026-02-23 - ADR-003: Safe OOXML operation boundary
- Status: accepted
- Context: Full run-level OOXML revision surgery is error-prone and high-risk for unintended formatting drift.
- Decision: Restrict OOXML v1 mutations to deterministic, paragraph-level transforms and explicit comment insertion; route unsupported operations to UNO fallback.
- Consequences: Higher safety for common operations, but narrower direct OOXML feature surface in phase 1.

## 2026-02-23 - ADR-004: Word desktop validation is manual release gate
- Status: accepted
- Context: Native Microsoft Word cannot run in this Ubuntu workspace, but Word round-trip confidence is still required.
- Decision: Automate Linux integrity/render checks and treat Word desktop spot-check as explicit manual gate for release-critical documents.
- Consequences: CI remains Linux-native; final high-risk sign-off still requires human Word validation.

## 2026-02-23 - ADR-005: Localized run-level revisions for replace_text_once
- Status: accepted
- Context: Paragraph-rewrite tracked edits caused whole-sentence redlines for single-word changes, reducing review fidelity.
- Decision: For `replace_text_once`, attempt localized run-level split first and emit word-level `w:del`/`w:ins` when match is contained in a safe run shape. Fall back to paragraph rewrite only when localized split is unsafe/unsupported.
- Consequences: Common single-word corrections now produce precise revisions in Word; complex multi-run cases still degrade to paragraph-level rewrites until richer run-diff logic is implemented.

## 2026-02-23 - ADR-006: Strict fidelity policy with explicit fallback routing
- Status: accepted
- Context: Even with localized run-level edits, complex patterns can still trigger fidelity-degrading rewrites.
- Decision: Introduce explicit policy controls (`fidelity_mode`, `on_unsupported`, `on_uno_fail`, `allow_paragraph_rewrite_tracked`) with default chain:
  1. OOXML strict localized attempt
  2. UNO fallback
  3. Comment-only fallback
- Consequences: No silent tracked paragraph rewrites in strict mode; behavior is deterministic and auditable via preflight/strategy metadata.

## 2026-02-23 - ADR-007: Canonical vs edited fixture separation
- Status: accepted
- Context: Mounted-drive test files are ephemeral and unsafe as long-term baselines.
- Decision: Store immutable fixture baselines under `examples/canonical/` and generated edited outputs under `examples/edited/`.
- Consequences: Reproducible local test corpus and reduced risk of mutating canonical examples.

## 2026-02-23 - ADR-008: Artifact cleanup command defaults to preview mode
- Status: accepted
- Context: Sidecar and render outputs in `artifacts/` are intentionally disposable, but accidental deletion of useful audit logs is a risk.
- Decision: Add `wordmark artifacts clean` with safe preview default, explicit `--apply` for deletion, optional `--older-than-days` retention filter, and `--keep-transcripts` to preserve operation logs.
- Consequences: Routine cleanup is one command and scriptable; destructive actions require explicit intent and are auditable via structured command output.

## 2026-02-23 - ADR-009: Paragraph+context anchor model with backward selector compatibility
- Status: accepted
- Context: `p:<index>` and `text:<snippet>` selectors are simple but can be ambiguous in repeated-content documents.
- Decision: Standardize richer anchor semantics (`paragraph_index`, `expected_text`, `context_before`, `context_after`, `occurrence`) while preserving legacy selector compatibility.
- Consequences: Safer disambiguation for comments and edits; unresolved/ambiguous anchors now surface explicit error codes.

## 2026-02-23 - ADR-010: Risky-markup-first preflight routing
- Status: accepted
- Context: Some paragraphs can appear localizable but still include fragile OOXML structures (hyperlinks, field codes, content controls, break/tab constructs).
- Decision: Preflight and apply layers treat risky markup as high risk and route to fallback policy rather than attempting localized tracked mutation in strict workflows.
- Consequences: Reduced chance of formatting/review-fidelity drift on complex constructs; more operations route through UNO/comment fallback.

## 2026-02-23 - ADR-011: Word desktop compare/combine remains explicit human merge gate
- Status: accepted
- Context: Team requirement is no direct automated write-back to shared online files without human review.
- Decision: Add explicit desktop merge-back SOP and a non-mutating CLI handoff helper (`review prepare-merge`) that prepares checklist/report metadata.
- Consequences: Shared-doc updates remain human-approved; merge process is repeatable and documented.
