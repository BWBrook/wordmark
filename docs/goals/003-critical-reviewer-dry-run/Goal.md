# Goal 003: Critical Reviewer Dry Run

## Objective

Test whether the Goal 002 reviewer guidance actually changes agent behaviour
on a disposable synthetic manuscript by separating manuscript authorship from
critical review.

## Why This Matters

Goal 002 improved the guidance, but it did not measure behaviour. The next
useful step is a bounded dry run: generate a plausible flawed manuscript, then
use the new critical-reviewer brief and calibration fixture to produce tracked
edits and comments. The central question is whether the reviewer now makes
obvious line edits directly instead of leaving generic comments.

Barry requested a deliberate model contrast:

- Phase A uses a weaker model (`gpt-5.4-mini`, low thinking) to author the
  synthetic manuscript only.
- Phase B uses the stronger default (`gpt-5.5`, xhigh thinking) to review the
  weaker output.

## Operating Mode

Two-phase human-in-the-loop dry run.

## Phase Split

### Phase A - Synthetic Manuscript Authoring

Run this phase only when the orchestrator sends the goal with `gpt-5.4-mini`
and low thinking.

Purpose:

- create a disposable synthetic ecology/conservation manuscript;
- make it plausible, mixed-quality, and naturally flawed;
- avoid creating an answer key or labelled flaw list;
- stop and wake the orchestrator after generating and smoke-checking the
  manuscript.

Phase A must not:

- review, critique, or improve the manuscript;
- apply the Critical Reviewer brief;
- edit reviewer guidance;
- create tracked-review output;
- commit or push.

### Phase B - Critical Review Dry Run

Run this phase only after the orchestrator sends a follow-up with `gpt-5.5`
and xhigh thinking.

Purpose:

- review the Phase A manuscript using Goal 002's brief/playbook/calibration;
- produce tracked edits and comments in a safe output copy;
- measure the tracked-edit/comment mix;
- identify any remaining guidance failures;
- tune guidance only if the observed failure is reviewer judgment, not DOCX
  engine behaviour;
- validate, commit, push, and verify hosted CI if complete.

## Review Surface

The Wordmark orchestrator will review:

- whether Phase A manuscript quality is plausible and not contrived;
- whether Phase B makes high-confidence grammar/clarity edits directly;
- whether comments are reserved for author judgment;
- whether the dry-run report distinguishes guidance issues from engine issues;
- whether validation evidence supports the output;
- final git status, commits, hosted CI, and residual risks.

## Scope

In scope:

- create a synthetic manuscript source and DOCX fixture;
- use only disposable repo-local example paths;
- run a dry critical-review pass against the synthetic DOCX;
- inspect resulting revisions and comments;
- verify and optionally render the edited output;
- add a dated log/report for the dry run;
- optionally refine guidance if the dry run exposes a clear guidance defect;
- commit, push, and verify hosted CI after Phase B only.

Out of scope:

- real manuscript or unpublished user content;
- answer keys or labelled flaw lists for the synthetic manuscript;
- LLM evaluation harnesses;
- benchmark automation;
- DOCX mutation engine changes;
- OOXML or UNO logic changes;
- dependency changes;
- CI workflow redesign;
- cleanup of `.DS_Store`, ignored artifacts, or unrelated scratch outputs;
- force-push, amend, rebase, reset, stash, or destructive cleanup.

## Expected Deliverables

Expected files may include:

```text
examples/reviewer_calibration/synthetic_manuscript_goal003.md
examples/canonical/reviewer_dry_run_synthetic_goal003.docx
examples/edited/reviewer_dry_run_synthetic_goal003_edited_sat13jun2026.docx
docs/log/2026-06-13_critical_reviewer_dry_run.md
docs/critical-reviewer-playbook.md
docs/critical-reviewer-agent-brief.md
docs/goals/003-critical-reviewer-dry-run/Goal.md
docs/goals/003-critical-reviewer-dry-run/Plan.md
docs/goals/003-critical-reviewer-dry-run/Runbook.md
docs/goals/003-critical-reviewer-dry-run/Log.md
```

Use judgment about exact names if a different local pattern is clearly better,
but the final work must include:

- a synthetic source or provenance note;
- a baseline synthetic DOCX;
- an edited/reviewed DOCX output;
- a dry-run report/log with revision/comment counts and qualitative findings.

## Synthetic Manuscript Requirements

The Phase A manuscript should:

- be entirely fictional and disposable;
- be about ecology, conservation biology, wildlife monitoring, or restoration;
- be roughly 800 to 1400 words;
- include ordinary manuscript sections such as title, abstract, introduction,
  methods, results, and discussion;
- contain a natural mix of:
  - grammar and agreement problems;
  - punctuation/hyphenation issues;
  - American/British spelling inconsistency;
  - wordiness and hedging;
  - unclear antecedents;
  - awkward sentence flow;
  - unsupported claims;
  - methods or reproducibility gaps;
  - interpretive overreach;
  - paragraph-level structure issues;
- avoid absurd, cartoonish, or obviously labelled errors;
- avoid any real unpublished content or real student text.

Do not create an answer key. The dry-run review should not be handed a labelled
list of intended issues.

## Starting State Checks

Start each phase by reporting:

- `pwd`;
- `git status --short --branch`;
- `git rev-parse --short HEAD`;
- `git rev-parse --short origin/main`;
- `git remote -v`;
- `git log -5 --oneline`;
- whether `.DS_Store` is still untracked and unstaged.

At Phase A start, run:

```sh
git fetch --prune origin
```

Stop and wake the orchestrator if local `HEAD` and `origin/main` are not both
`3c985eb` before Phase A begins. Do not pull, merge, rebase, reset, or stash to
recover.

At Phase B start, report the current state and continue only if it contains the
expected uncommitted Phase A manuscript files plus `.DS_Store` and this goal
packet. If additional unexpected changes exist, stop and wake the orchestrator.

## Git And Publication Policy

Phase A:

- no commit;
- no push;
- no staging except if needed to inspect staged state, then unstage before
  wake-up;
- stop after the synthetic manuscript is created and smoke-checked.

Phase B:

- commit and push are authorized if local validation passes;
- stage exact files only;
- do not stage `.DS_Store`;
- use a concise commit message such as:

```text
docs: run critical reviewer dry run
```

After pushing, inspect the GitHub Actions `ci` run for the pushed commit. Use
`gh` for Actions checks/logs. GitHub interaction is limited to
`BWBrook/wordmark` run/check inspection for this goal.

## Validation Gates

Phase A minimum validation:

```sh
uv run wordmark inspect examples/canonical/reviewer_dry_run_synthetic_goal003.docx --json
git status --short --branch
```

Phase B minimum validation:

```sh
uv run wordmark inspect <edited-docx> --text-mode review-visible --json
uv run wordmark review list <edited-docx> --text-mode review-visible --json
uv run wordmark verify <baseline-docx> <edited-docx> --profile review-edit --json
git diff --check
uv lock --check
uv run pytest
make check
```

Render the edited DOCX if the verify output or review surface suggests layout
risk:

```sh
uv run wordmark render <edited-docx> --out artifacts/goal003_render --json
```

Run `make test-external` only if the final diff touches external-tool, render,
Quarto, or DOCX integration behaviour. This goal should normally not require
it unless render behaviour becomes part of the accepted deliverable.

## Deliverables

Phase A wake-up must include:

- manuscript path(s);
- word count or rough length;
- smoke-check command outcome;
- final `git status --short --branch`;
- confirmation of no review, no guidance edits, no commit, no push, and
  `.DS_Store` unstaged.

Phase B wake-up must include:

- changed files and summary;
- baseline DOCX path and edited DOCX path;
- revision count and comment count from `review list`;
- examples of tracked edits made directly;
- examples of comments reserved for author judgment;
- any guidance tuning performed;
- validation command outcomes;
- commit SHA and push result;
- GitHub Actions run URL and status;
- final `git status --short --branch`;
- residual risks and recommended next goal shape.

## Decision Authority

You may decide:

- exact synthetic manuscript topic;
- exact disposable file names within the expected path families;
- whether to use a small helper script, `python-docx`, or existing Wordmark
  tooling to create the baseline DOCX;
- whether guidance tuning is warranted after the dry run.

You must pause before:

- using real user/student/manuscript content;
- creating an answer key for the synthetic manuscript;
- modifying DOCX engine behaviour;
- adding dependencies;
- creating an LLM benchmark/evaluation harness;
- weakening validation;
- force-pushing, rebasing, amending, resetting, stashing, cleaning, or deleting
  local artifacts.

## Stop Conditions

Stop when one of these is true:

- Phase A synthetic manuscript is created, smoke-checked, and the orchestrator
  has been woken;
- Phase B local validation passes, the work is pushed, and hosted `ci` passes;
- the work requires product/scientific judgment beyond the scope above;
- starting state differs from the expected guard state;
- the work would leave this goal's scope.
