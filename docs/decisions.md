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
