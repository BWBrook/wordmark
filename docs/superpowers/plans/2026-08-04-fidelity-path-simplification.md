# Plan: Fidelity-Path Simplification Audit

**Date:** 2026-08-04
**Scope:** `/Users/bwbrook/work/wordmark`
**Status:** Proposed audit result; no source change recommended

## Objective

Audit the current Wordmark complexity around sidecars, operation
transcripts, edit-policy modes, interop drift and risk diagnostics, UNO
precision handling, optional manuscript rounds, and the DOCX fidelity path
(`preflight_patch`, `apply_patch`, and `cli.edit_apply`). Select at most one
evidence-backed, low-risk simplification. The audit must make the decision
measurable without changing review semantics or deleting infrastructure merely
because it is large.

## Acceptance

- Every candidate subsystem below has a recorded production entrypoint or an
  explicit absence-of-consumer finding.
- The fidelity-critical call path and its current complexity are recorded,
  including the direct CLI callers and the characterization tests that protect
  it.
- The audit either identifies one narrow cut with exact files and a safety
  argument or records a no-op decision with explicit deferrals. No speculative
  refactor is allowed.
- No DOCX source, tests, configuration, historical ADR/log, manuscript-round
  artifact, or review output is changed by this audit. The plan may be
  accompanied at publication by only one concise current decision entry in
  `docs/decisions.md` and one dated execution note in `docs/log/`; no broad
  ledger or historical rewrite is permitted.
- The inherited untracked `.DS_Store` remains untouched and unstaged.
- Stop after one focused review pass; a second pass is warranted only by
  material new evidence or a concrete defect.

## Non-goals and invariants

- Preserve review-visible/raw extraction, tracked-change and comment semantics,
  anchor ambiguity handling, OOXML-first/UNO-fallback ordering, and untouched
  DOCX package fidelity.
- Preserve Markdown/Quarto source-hash guards and verified-span safe-apply
  behaviour.
- Keep the manuscript-rounds subsystem available as an optional surface unless
  real usage evidence supports a separately approved narrow change.
- Do not add compatibility layers, fallbacks, migrations, or aliases for
  obsolete private-repository paths.
- Do not rewrite historical decisions or logs to make the current code look
  smaller.
- Do not infer dead code from line count, a lack of recent examples, or the
  absence of a downstream package. Confirm callers and contracts first.

## Evidence inventory

| Candidate | Live callers / contracts observed | Downstream consumers / usage status | Assessment |
| --- | --- | --- | --- |
| Sidecars | `src/wordmark/cli.py:199-210` writes review sidecars; `cli.py:969-999` writes inspect/verify sidecars; `src/wordmark/manuscript_rounds.py:236-245`, `manuscript_ingest.py:464-489`, and `manuscript_synthesis.py:644-831` write manuscript artifacts. `tests/test_comment_and_inspect.py:79-107` asserts the DOCX sidecar contract. | Search of `src/`, `scripts/`, and CLI call paths found no downstream production reader for emitted DOCX sidecar files; manuscript stages read their own round manifests/bundles, not the DOCX sidecars. Human/agent review is the implied consumer. Retention is **provisional pending Barry usage evidence**. | Active producer/test contract, but value is not demonstrated by an in-repo consumer. No safe deletion found without Barry's usage decision. |
| Operation transcript | `src/wordmark/cli.py:325`, `579`, `639`, and `671` append transcripts for comment, edit, accept, and reject operations. `cli.py:719-808` exposes cleanup and transcript-retention controls; `tests/test_artifacts_clean.py:53-81` asserts retention. | Search found no downstream production reader/parser for `artifacts/transcripts/operations.jsonl`; cleanup scans and deletes it, while docs and human/agent workflows may inspect it. Retention is **provisional pending Barry usage evidence**. | Active audit output with an explicit cleanup contract, but no machine consumer. Do not remove it silently. |
| Edit-policy modes and fallback controls | `src/wordmark/cli.py:341-365` exposes `strict|balanced|aggressive`, unsupported/UNO-failure policies, and paragraph-rewrite control. `src/wordmark/edit_policy.py:16-49` resolves them; `wordmark.yaml:1-21` configures fidelity mode, fallback policy, and paragraph-rewrite defaults. | Policy settings are consumed internally by `cli.edit_apply`; search found no downstream production reader of the returned policy metadata. `--drift-check`, `--drift-warning-threshold`, and `--emit-risk-summary` at `cli.py:351-365` are **CLI-only controls**, not `wordmark.yaml` settings. Mode retention is **provisional pending Barry usage evidence**. | Live CLI/config/test contract. Consolidation would be a product decision, not low-risk residue cleanup. |
| Interop drift and risk summary | `src/wordmark/cli.py:548-577` calls drift analysis and risk-summary emission; `src/wordmark/edit_policy.py:97-179` adapts `interop_drift`; `tests/test_interop_drift.py` and `tests/test_edit_policy.py:485-603` cover output and opt-out flags. | Search found no downstream production reader of `operation.details.interop_drift` or `risk_summary`; README/playbook describe human/agent triage as the consumer. Retention is **provisional pending Barry usage evidence**. | Advisory diagnostics are live and machine-readable, but removing or making them mandatory would alter the current contract; defer. |
| UNO precision and low-hit retry | `src/wordmark/cli.py:461-520` prepares precision patches, invokes UNO, and may retry low-hit global replacements. `src/wordmark/uno_precision.py:270-333` implements preparation; `tests/test_edit_policy.py:134-207` covers retry reporting and `209-472` covers rewrite strategies. | `cli.edit_apply` is the only production caller and consumes UNO result details to decide retry and attach operation metadata; search found no downstream reader of the detailed precision/retry records. Retention is **provisional pending Barry usage evidence**, while the mutation logic remains fidelity-critical. | Fallback fidelity logic with focused characterization. Do not simplify without real fallback cases and render evidence. |
| Manuscript rounds | `src/wordmark/cli.py:808-952` exposes prepare/collect/synthesize/decide/apply/status; `manuscript_rounds.py`, `manuscript_ingest.py`, and `manuscript_synthesis.py` are direct implementations. `tests/test_manuscript_workflow.py` and `tests/test_subprocess_timeouts.py` exercise them; README and workflow docs publish the commands. | Later manuscript stages consume the round files produced by earlier stages, but search found no production consumer outside the manuscript subsystem and no evidence of Barry using it in a real pilot. Retention is **provisional pending Barry usage evidence**. | Optional but reachable product surface. Freeze rather than delete or restructure in this tranche. |
| Fidelity-critical patch path | `src/wordmark/cli.py:387` calls `ooxml_engine.preflight_patch`; `cli.py:420`, `467`, and `484` call OOXML/UNO apply paths. `preflight_patch` is `ooxml_engine.py:422-698` (277 lines); `apply_patch` is `ooxml_engine.py:701-895` (195 lines); `cli.edit_apply` is `cli.py:335-588` (254 lines). | `cli.edit_apply` is the sole production orchestrator; search found no external production caller. Characterization contracts are explicit: `tests/test_phase3_anchor_and_preflight.py:13-33` covers preflight classification, `36-195` anchor disambiguation/occurrence, and `254-282` risky-markup routing; `tests/test_hard_pattern_fixtures.py:26-61` covers fixture checksums and hard-pattern preflight; `tests/test_failure_modes.py:24-60` covers anchor mismatch and unsupported-operation failure, `63-83` UNO failure surfacing, and `86-105` atomic package-save preservation; `tests/test_edit_policy.py:39-64` covers preflight-only non-mutation, `66-132` fallback policy outcomes, `134-207` low-hit retry, and `485-603` drift/risk-summary integration and opt-outs. | Complexity is concentrated in fidelity and fallback decisions. Extraction based only on size would increase regression risk. Defer. |

## Decision: no code cut in this tranche

The inventory does not establish a safe simplification. Each candidate is
either a live user-facing contract, a proven audit output, an optional but
reachable product surface, or fidelity-sensitive fallback logic. The only
defensible result of this audit is therefore a no-op for source, tests,
configuration, and historical records. The durable deliverable is this
evidence table and its explicit deferral boundary.

This is not a claim that the architecture is ideal. It identifies the missing
decision evidence needed before a cut becomes safe: a real usage sample for
sidecars/transcripts and manuscript rounds, a deliberate choice of supported
policy modes, and representative risky-markup/UNO cases for any shared
preflight/apply extraction.

## Validation and stopping rule

Because the recommended result changes no executable files, validation is
limited to checking the untracked plan explicitly, confirming its name, and
confirming that inherited state remains visible:

```sh
diff_status=0
git diff --no-index --check /dev/null docs/superpowers/plans/2026-08-04-fidelity-path-simplification.md || diff_status=$?
if [ "$diff_status" -ne 1 ]; then
  printf 'Unexpected plan diff-check status: %s (expected exactly 1)\n' "$diff_status" >&2
  exit 1
fi
git status --short --branch
git diff --name-only
```

The guarded diff check is expected to return exactly status `1` because the
untracked plan differs from `/dev/null`; its output must contain no whitespace
diagnostic. Any other status, including a whitespace-error status, fails the
audit. The name-only check must show no tracked source/test/config changes; the
untracked plan and inherited `.DS_Store` are the only expected additions before
publication. Do not run tests, builds, renders, `make`, dependency commands,
or package smokes for this audit-only no-op. If a later, separately approved
goal selects a code cut, that goal must add focused characterization plus the
relevant full pure/external checks before publication.

## Explicit deferrals

- Do not delete or redesign sidecar writers, sidecar path configuration, or
  the artifact-cleanup command.
- Do not remove the append-only transcript or its retention flag.
- Do not collapse fidelity modes, fallback policies, drift thresholds, or risk
  summary controls.
- Do not remove `interop_drift.py`, `uno_precision.py`, or the UNO low-hit
  retry without representative fallback evidence.
- Do not delete or restructure manuscript rounds; keep them frozen until a
  real manuscript pilot establishes whether they earn their maintenance cost.
- Do not extract shared preflight/apply planning or shorten `cli.edit_apply`
  merely to reduce line count. Revisit only behind characterization tests and
  a single, sharply scoped design proposal.
- Do not rewrite historical docs/ADRs or remove earned fidelity safeguards.

## Commit and publication boundary

This audit creates the plan file above. If the orchestrator accepts this
no-op result, the publication batch may also contain exactly one concise
current decision entry in `docs/decisions.md` and one dated execution note in
`docs/log/`, documenting the evidence, provisional-retention status, and
no-code decision. Preserve all historical ADR/log text and do not create a
broad ledger. Stage and commit only those explicitly permitted paths in one
batch after review, then push that commit to the current canonical branch under
the repository's normal commit/push policy. Never stage `.DS_Store` or
unrelated generated artifacts; do not amend, rebase, force-push, clean, or
otherwise reconcile inherited state. Stop after the single review pass and
hand the next product decision to Barry: either provide real usage evidence
for one deferred surface or approve a separate, narrowly scoped
simplification goal.
