# Plan: Lean Boundary Cleanup

**Goal:** Remove high-confidence dependency, test, and compatibility residue
without changing Wordmark's active DOCX review semantics or deleting the
optional manuscript-rounds subsystem.

**Status:** Implemented locally; awaiting orchestrator review
**Created:** 2026-08-04
**Scope:** `/Users/bwbrook/work/wordmark`

## Objective

Make the current private scientific tool easier to understand and maintain by
keeping only the paths that the present package and test contract use. The
tranche is intentionally small: it should produce an immediately useful
reduction in maintenance burden, with one focused verification pass, rather
than begin a broad architecture rewrite.

## Non-goals

- Do not change OOXML review-visible/raw extraction, comments, tracked-change
  semantics, anchor safety, fallback ordering, or document fidelity behaviour.
- Do not redesign sidecars, append-only transcripts, policy modes, drift/risk
  diagnostics, or artifact cleanup.
- Do not delete or restructure the Markdown/Quarto manuscript-rounds
  subsystem; it remains an optional product surface pending a separate usage
  decision.
- Do not refactor `preflight_patch`, `apply_patch`, `cli.edit_apply`, or other
  fidelity-sensitive orchestration merely to reduce line count.
- Do not rewrite historical logs and ADRs solely to remove references that were
  accurate when written.
- Do not clean, stage, or alter the pre-existing untracked `.DS_Store`.

## Global constraints

- Treat the private repository's current package/runtime contract as the only
  compatibility target. Do not add fallbacks or migration layers for obsolete
  checkout paths.
- Preserve the active DOCX-first product boundary and all earned safety guards.
- Keep the packaged wheel and the editable `uv` development install working.
- Keep changes modular and local; avoid speculative abstractions or broad
  test-suite churn.
- Record the packaged-helper decision in the current decision log and add a
  dated execution note, as required by the repository contract.
- The implementer must inspect the diff before one batch commit and push. No
  amend, rebase, force-push, or unrelated-file staging.

## Planned changes

### Task 1: Implement the three bounded lean-boundary cuts

Evidence from the source import scan shows no production import of `docx`; the
package is used by test fixtures and manuscript workflow tests. Therefore:

- [x] remove `python-docx>=1.2,<2` from `[project].dependencies` in
  `pyproject.toml`;
- [x] add the same bounded requirement to the `dev` optional dependency group;
- [x] refresh `uv.lock` without unrelated upgrades;
- [x] leave test fixture code unchanged unless the dependency move exposes a real
  fixture issue.

Acceptance: production package metadata has no `python-docx` runtime edge,
dev installs still provide it, and the lock remains current.

#### Cut 2: Keep pure render characterization in the pure lane

`tests/test_verify_and_render.py` repeats two behavior-only tests already
covered by `tests/test_render_verify_pure.py`:

- stale prefix-page cleanup in `convert_pdf_to_png`;
- page-dimension mismatch failure in `_render_diff`.

- [x] Remove only the duplicated external copies. Keep the actual render/LibreOffice
integration tests and all external-only verification assertions in
`test_verify_and_render.py`. Do not weaken the pure tests or change their
assertions. Check the resulting imports and marker placement for dead code.

Acceptance: each pure behavior has one canonical pure-lane test, while the
external module still exercises real rendering and verification integration.

#### Cut 3: Remove the checkout-only UNO compatibility wrapper

The packaged helper at `src/wordmark/_resources/uno_replace.py` is already the
runtime resource and is covered by `tests/test_smoke.py`. The top-level
`scripts/uno_replace.py` wrapper and the fallback branch in
`src/wordmark/uno_engine.py` only preserve a direct-checkout path that is not
part of the current private package contract.

- [x] delete `scripts/uno_replace.py`;
- [x] simplify `_helper_script_path()` so it resolves the packaged resource only
  and raises a clear `UnoEngineError` if that resource is unavailable;
- [x] keep the existing packaged-resource smoke guard, adding only a narrowly
  useful assertion or message if needed;
- [x] update the current architecture description to point to
  `src/wordmark/_resources/uno_replace.py` rather than the removed wrapper;
- [x] add a concise current ADR (next available number) explaining the deliberate
  removal of the obsolete checkout fallback; leave historical ADR/log text
  intact;
- [x] add a dated execution note listing the exact files and validation evidence.

Acceptance: source and wheel installs resolve the packaged helper, the removed
wrapper is not referenced by active code, no direct-checkout fallback remains,
and UNO operation semantics are unchanged.

## Candidate explicitly rejected for this tranche

The shared preflight/apply planning refactor is deferred. Although duplicate
branching exists, it sits on the fidelity-critical path and needs stronger
characterization before extraction. Likewise defer deletion of manuscript
rounds, sidecar/transcript redesign, policy-axis consolidation, removal of
interop/precision diagnostics, and `wordmark.yaml` default simplification.
Those are product or architecture decisions, not low-risk residue cleanup.

## Validation

Run the canonical checks and the task-specific packaging/runtime checks:

```text
uv lock --check
git diff --check
uv run pytest
make check
make test-external
uv build --out-dir /tmp/wordmark-lean-boundary-cleanup
```

After building, inspect the wheel contents and run a minimal wheel/source
import smoke that confirms `wordmark._resources/uno_replace.py` is present and
`uno_engine._helper_script_path()` resolves it. Do not retain generated build
outputs in the repository. If an external-tool or UNO check is unavailable,
report the exact skip and retain the pure/package evidence rather than
inventing a workaround.

## Completion and publication boundary

The plan itself makes no Git changes beyond this file. During implementation,
batch the scoped source, test, dependency, documentation, decision, and log
changes into one reviewable commit only after the orchestrator has inspected
the diff and validation evidence. Push that commit to the current canonical
branch in the same flow, preserving all unrelated pre-existing state. Stop
after one focused self-review/repair pass; further cleanup belongs in a
separately approved tranche.
