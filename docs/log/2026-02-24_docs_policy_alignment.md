# 2026-02-24 - Docs Policy Alignment After Complex Road Tests

## Context
Recent stress testing on `complex_test_2.docx` produced tooling hardening in three areas:
- per-file serialization lock for mutating commands
- minimal tracked-change deltas for localized replacements
- UNO author-attribution normalization for newly introduced `Unknown Author` revisions

The user asked for a documentation review to ensure workflow and playbook guidance matched the implemented behavior.

## Updates made
- `docs/authoring-workflow.md`
  - added mutation-safety section with lock semantics (`<docx>.wordmark.lock`)
  - clarified localized OOXML edit behavior and strict-mode minimal-delta expectations
  - expanded UNO diagnostics notes to include author binding and post-process metadata
  - documented stale lock-file handling after interrupted runs
- `docs/fidelity-policy.md`
  - codified minimal-delta requirement for localized tracked edits
  - codified localized-first behavior for `replace_paragraph_text`
  - added concurrency/write-safety policy for same-file mutation serialization
  - expanded UNO reliability policy with author binding and post-process normalization
  - added escalation trigger for unresolved unknown revision authors
- `docs/critical-reviewer-playbook.md`
  - added lock-aware safety default for reviewer workflows
  - added reviewer heuristics for preserving concise tracked deltas
  - reinforced comment-first handling for author-owned placeholder checks
  - documented `author_binding_postprocess` and `uno_retry` diagnostics in operation details

## Verification
- `uv run pytest` -> `41 passed`
