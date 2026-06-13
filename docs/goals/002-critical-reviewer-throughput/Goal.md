# Goal 002: Critical Reviewer Throughput v1

## Objective

Improve Wordmark's agent-facing critical-review guidance so a fresh reviewer
agent produces more high-confidence tracked line edits for grammar, clarity,
concision, and sentence flow, while still reserving comments for issues that
need author judgment.

## Why This Matters

Wordmark's document mutation and manuscript-round machinery is now a credible
baseline, but the reviewer guidance is still too cautious and checklist-like.
Barry's observed pain point is not that agents cannot leave comments; it is
that they under-produce useful grammatical and clarity-related line edits.

This goal should make reviewer agents more practically useful: less generic
feedback, more precise edits where confidence is high, and better judgment
about when not to edit.

## Operating Mode

Product guidance and calibration.

## Review Surface

The Wordmark orchestrator will review:

- whether the guidance materially pushes agents toward high-confidence line
  edits rather than generic comments;
- whether edit-versus-comment rules are explicit and usable;
- whether examples are concrete enough to calibrate future agents;
- whether validation evidence supports the changed docs/examples;
- final git status, commits, hosted CI, and residual risks.

## Scope

In scope:

- strengthen `docs/critical-reviewer-playbook.md`;
- add a concise agent-facing critical-review brief that can be pasted into
  future review tasks;
- add a small calibration fixture or equivalent examples showing source text,
  weak feedback, preferred tracked edits, preferred comments, and rationale;
- add lightweight validation for any structured calibration fixture;
- update README or workflow docs only where needed to make the new guidance
  discoverable;
- add a dated log note for the goal;
- commit, push, and verify hosted CI if local validation passes.

Out of scope:

- DOCX mutation engine changes;
- OOXML or UNO fidelity behavior changes;
- real manuscript review work;
- LLM evaluation harnesses or benchmark runners;
- broad CLI redesign;
- unrelated documentation cleanup;
- dependency changes;
- cleanup of `.DS_Store`, ignored artifacts, or scratch outputs;
- force-push, amend, rebase, reset, stash, or destructive cleanup.

## Product Direction

The guidance should make these principles unmistakable:

1. Make the edit when the fix is obvious.
2. Prefer tracked edits for grammar, punctuation, spelling, British English
   normalization, concision, unclear antecedents, and sentence-flow fixes.
3. Prefer comments for factual uncertainty, scientific interpretation,
   unsupported claims, missing methods detail, structural decisions, and
   author-choice trade-offs.
4. Avoid timid "consider revising" comments when the agent can safely provide
   the actual improved wording.
5. Preserve Wordmark's safety posture: narrow anchors, auditable sidecars,
   strict/default fidelity controls, and no overwrite of originals.
6. Keep supervisor tone: direct, specific, proportionate, and useful.

## Expected Deliverables

Expected files may include:

```text
docs/critical-reviewer-playbook.md
docs/critical-reviewer-agent-brief.md
docs/authoring-workflow.md
README.md
docs/log/2026-06-13_critical_reviewer_throughput.md
examples/reviewer_calibration/critical_line_edits.yaml
tests/test_reviewer_calibration.py
docs/goals/002-critical-reviewer-throughput/Goal.md
docs/goals/002-critical-reviewer-throughput/Plan.md
docs/goals/002-critical-reviewer-throughput/Runbook.md
docs/goals/002-critical-reviewer-throughput/Log.md
```

Use judgment about exact names if a different local pattern is clearly better,
but the final work must include:

- a durable playbook update;
- a short reusable agent brief;
- concrete calibration examples;
- validation that any structured calibration examples parse and contain the
  expected fields.

## Required Content

The revised guidance must cover:

- tracked edit versus comment decision rules;
- a "line-edit first where confident" stance;
- examples of weak generic feedback and preferred stronger alternatives;
- examples of high-confidence micro-edits:
  - grammar and agreement;
  - punctuation and hyphenation;
  - British English spelling;
  - wordiness and hedging;
  - unclear antecedents;
  - sentence-flow fixes;
- examples where comments are preferable:
  - scientific uncertainty;
  - missing evidence or methods;
  - interpretation choices;
  - structural or narrative decisions;
- calibration cases suitable for future agents to read before doing review
  work.

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
`355662d` before you begin implementation. Do not pull, merge, rebase, reset,
or stash to recover.

## Git And Publication Policy

Commit and push are authorized for this goal if local validation passes.

Stage exact files only. Do not stage `.DS_Store`.

Use a concise commit message such as:

```text
docs: strengthen critical reviewer guidance
```

Push with:

```sh
git push origin main
```

After pushing, inspect the GitHub Actions `ci` run for the pushed commit. Use
`gh` for Actions checks/logs. GitHub interaction is limited to
`BWBrook/wordmark` run/check inspection for this goal.

## Validation Gates

Run at minimum:

```sh
uv lock --check
git diff --check
uv run ruff check .
uv run pytest
make check
```

If you add a focused calibration test, run it explicitly before the full suite,
for example:

```sh
uv run pytest tests/test_reviewer_calibration.py -q
```

Run `make test-external` only if you change external-tool behavior, render
fixtures, Quarto paths, or DOCX integration behavior. This goal should normally
not require it.

After push, verify the GitHub Actions `ci` run for the pushed commit. A passing
hosted `ci` run is the primary publication gate.

## Deliverables

- Updated guidance/docs/examples.
- Updated `docs/goals/002-critical-reviewer-throughput/Log.md`.
- A dated `docs/log/` note.
- Pushed commit on `main`, if validation passes.
- Wake-up report to the Wordmark orchestrator with:
  - summary of guidance changes;
  - calibration examples added;
  - validation command outcomes;
  - commit SHA and push result;
  - GitHub Actions run URL and status;
  - final `git status --short --branch`;
  - residual risks and recommended next goal shape.

## Decision Authority

You may decide:

- exact calibration fixture format;
- exact examples, as long as they are concrete and supervisor-relevant;
- whether README, authoring workflow, or both need short discoverability links;
- whether a `docs/decisions.md` entry is warranted.

You must pause before:

- changing DOCX mutation behavior;
- adding an LLM evaluation framework;
- adding dependencies;
- doing real manuscript review work;
- weakening validation;
- force-pushing, rebasing, amending, resetting, stashing, cleaning, or deleting
  local artifacts.

## Stop Conditions

Stop when one of these is true:

- local validation passes, the work is pushed, and hosted `ci` passes;
- the work requires product/scientific judgment beyond the scope above;
- the starting state differs from the expected `355662d`;
- the fix would leave this goal's scope.

## Final Response Requirements

Wake the Wordmark orchestrator thread when done or blocked. Include:

- branch, local `HEAD`, and `origin/main`;
- changed files and summary;
- calibration artifact path and example count;
- validation command outcomes;
- commit SHA and push result;
- GitHub Actions run URL and status;
- final dirty/untracked state;
- whether `.DS_Store` stayed untracked and unstaged;
- recommended next goal shape.
