# Goal 004: Reviewer Output Assessment Gate

## Objective

Assess the Goal 003 critical-review output as a product artefact and decide
whether Wordmark is ready for Barry's human-scientist benchmark review, needs
guidance tuning first, needs an engine/tooling follow-up first, or should rerun
the dry run.

## Why This Matters

Goal 003 proved that the line-edit-first guidance can produce a plausible mix
of tracked edits and comments on a synthetic manuscript. That is not the same
as judging whether the output is scientifically useful, sufficiently incisive,
or ready for a human benchmark. This goal is a narrow assessment gate before
moving to a real or human-rated review task.

Barry has offered human-scientist eyes as a comparative benchmark. The best use
of that time is a compact review packet, not a request to rummage through raw
artifacts.

## Operating Mode

Assessment and decision gate.

## Decision Shape

End with exactly one primary recommendation:

```text
READY FOR BARRY BENCHMARK
TUNE GUIDANCE FIRST
CREATE ENGINE FOLLOW-UP FIRST
REWORK DRY RUN
```

Use secondary notes for caveats, but do not leave the outcome as an open-ended
narrative.

## Review Surface

Assess the Goal 003 output against the product intent:

- high-confidence language fixes should become tracked edits;
- comments should be reserved for author judgment;
- tracked edits should preserve scientific meaning;
- comments should be specific, actionable, and appropriately incisive;
- any engine/tooling limitation should be separated from reviewer judgment;
- the human benchmark packet should be quick for Barry to inspect.

## Scope

In scope:

- inspect Goal 003 baseline and edited DOCX artifacts;
- inspect Goal 003 review-state JSON using Wordmark commands;
- inspect the Goal 003 review patch and operation transcript if present;
- classify sampled or full edit/comment outputs into clear assessment buckets;
- identify missed line-edit opportunities or over-commenting if present;
- identify comments that should have been edits, or edits that should have
  been comments;
- decide whether the second-pass-in-tracked-text UNO routing deserves an
  engine ticket, operator guidance, or no immediate action;
- write a human-scientist benchmark packet for Barry;
- add a dated log note;
- commit, push, and verify hosted CI if validation passes.

Out of scope:

- editing the Goal 003 reviewed DOCX;
- creating a new manuscript;
- rerunning the review unless the output is unusable;
- changing reviewer guidance;
- changing DOCX mutation behaviour, OOXML/UNO logic, dependencies, or CI;
- creating an LLM evaluation harness;
- cleaning artifacts or `.DS_Store`;
- force-push, amend, rebase, reset, stash, or destructive cleanup.

## Inputs

Primary inputs:

```text
examples/reviewer_calibration/synthetic_manuscript_goal003.md
examples/canonical/reviewer_dry_run_synthetic_goal003.docx
examples/edited/reviewer_dry_run_synthetic_goal003_edited_sat13jun2026.docx
docs/log/2026-06-13_critical_reviewer_dry_run.md
docs/goals/003-critical-reviewer-dry-run/Log.md
docs/critical-reviewer-agent-brief.md
docs/critical-reviewer-playbook.md
examples/reviewer_calibration/critical_line_edits.yaml
```

Optional audit inputs if present:

```text
artifacts/goal003_review_patch.json
artifacts/transcripts/operations.jsonl
artifacts/reviewer_dry_run_synthetic_goal003_edited_sat13jun2026.render/
```

Do not clean, move, or stage ignored audit artifacts.

## Expected Deliverables

Expected files may include:

```text
docs/reviewer-output-assessment-goal003.md
docs/log/2026-06-14_reviewer_output_assessment.md
docs/goals/004-reviewer-output-assessment/Goal.md
docs/goals/004-reviewer-output-assessment/Plan.md
docs/goals/004-reviewer-output-assessment/Runbook.md
docs/goals/004-reviewer-output-assessment/Log.md
```

The assessment packet must include:

- one primary recommendation from the allowed decision shape;
- a short summary of the dry-run output;
- tracked-edit assessment, with examples;
- comment assessment, with examples;
- missed-opportunity or overreach notes, if any;
- engine/tooling note on the second-pass-in-tracked-text UNO routing;
- a concise section for Barry's benchmark review with explicit questions.

## Barry Benchmark Packet Requirements

The packet should let Barry judge depth and incisiveness quickly. Include:

- the baseline DOCX path;
- the edited DOCX path;
- revision/comment counts;
- 4 to 6 tracked-edit examples to inspect;
- 4 to 6 comment examples to inspect;
- 3 to 5 benchmark questions for Barry, such as:
  - Were the comments scientifically incisive enough?
  - Were any claims left insufficiently challenged?
  - Did any tracked edit alter meaning or miss the best phrasing?
  - Were any comments too timid, too broad, or too procedural?
  - Would this be useful as a first-pass supervisor review?

Do not ask Barry to inspect everything unless the assessment finds a serious
problem.

## Starting State Checks

Start by reporting:

- `pwd`;
- `git status --short --branch`;
- `git rev-parse --short HEAD`;
- `git rev-parse --short origin/main`;
- `git remote -v`;
- `git log -5 --oneline`;
- whether `.DS_Store` is still untracked and unstaged.

Run:

```sh
git fetch --prune origin
```

Stop and wake the orchestrator if local `HEAD` and `origin/main` are not both
`03f85e6` before you begin assessment. Do not pull, merge, rebase, reset, or
stash to recover.

## Validation Gates

Run:

```sh
uv run wordmark review list examples/edited/reviewer_dry_run_synthetic_goal003_edited_sat13jun2026.docx --text-mode review-visible --json
uv run wordmark verify examples/canonical/reviewer_dry_run_synthetic_goal003.docx examples/edited/reviewer_dry_run_synthetic_goal003_edited_sat13jun2026.docx --profile review-edit --json
git diff --check
uv lock --check
uv run pytest
make check
```

Run `make test-external` only if the final diff changes external-tool, render,
Quarto, DOCX engine, OOXML/UNO, dependency, or CI behaviour. This goal should
normally not require it.

After push, verify the GitHub Actions `ci` run for the pushed commit. Use `gh`
for Actions checks/logs. GitHub interaction is limited to `BWBrook/wordmark`
run/check inspection for this goal.

## Git And Publication Policy

Commit and push are authorized if validation passes.

Stage exact files only. Do not stage `.DS_Store` or ignored artifacts.

Use a concise commit message such as:

```text
docs: assess critical reviewer dry run
```

Push with:

```sh
git push origin main
```

## Deliverables In Wake-Up

Wake the Wordmark orchestrator with:

- primary recommendation;
- changed files;
- validation command outcomes;
- commit SHA and push result;
- GitHub Actions run URL and status;
- final `git status --short --branch`;
- `.DS_Store` unstaged confirmation;
- whether Barry benchmark review is recommended now;
- exact file path Barry should inspect if benchmark review proceeds.

## Stop Conditions

Stop when one of these is true:

- validation passes, the assessment is pushed, hosted `ci` passes, and the
  orchestrator is woken;
- the Goal 003 artifacts are missing or unreadable;
- assessment finds the dry run unusable and needs orchestrator judgment;
- the work would leave this goal's scope.
