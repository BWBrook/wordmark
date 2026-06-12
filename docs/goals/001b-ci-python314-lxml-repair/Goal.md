# Goal 001b: Repair Hosted Python 3.14 CI

## Objective

Restore the GitHub Actions `ci` workflow on `main` after Goal 001 by fixing the
hosted Python 3.14 dependency-sync failure and publishing the repair only after
local validation passes.

## Why This Matters

Goal 001 published the Python 3.14 readiness baseline and local validation
passed, but GitHub push-triggered CI now fails before lint/tests run. Goal 002
should not start while the hosted baseline is red. This goal makes the hosted
Python 3.14 environment coherent with the local Mac mini baseline.

## Observed Failure

GitHub Actions evidence gathered by the Wordmark orchestrator:

```text
repo = BWBrook/wordmark
failed workflow = ci
failed runs =
  27408689878 for a00d2bc chore: publish macOS Python 3.14 readiness
  27408770801 for e9802fb docs: record goal 001 publication result
failed jobs = lint, pure-python (py3.14)
failed step = Sync dependencies
command = uv sync --extra dev
```

Failure snippet:

```text
Building lxml==5.4.0
Failed to build `lxml==5.4.0`
Error: Please make sure the libxml2 and libxslt development packages are installed.
hint: `lxml` (v5.4.0) was included because `wordmark` (v0.1.0) depends on `lxml`
```

The orchestrator also checked PyPI metadata: `lxml 5.4.x` exposes no CPython
3.14 manylinux wheels, while `lxml 6.0.1` and `6.0.2` do expose CPython 3.14
manylinux wheels.

## Operating Mode

CI repair and repo readiness.

## Review Surface

The Wordmark orchestrator will review:

- exact root-cause confirmation;
- dependency/workflow diff;
- validation evidence;
- pushed commit SHA;
- GitHub Actions run status for the pushed repair;
- final git status and residual risks.

## Scope

In scope:

- inspect the failing GitHub Actions run details for `BWBrook/wordmark`;
- repair the Python 3.14 hosted dependency-sync failure;
- preferred repair: update the `lxml` dependency constraint and lockfile to a
  CPython 3.14 wheel-providing release if local tests pass;
- fallback repair: add minimal hosted Linux build dependencies only if the
  dependency upgrade is incompatible or demonstrably inappropriate;
- update the relevant docs/log/decision notes for the chosen repair;
- commit, push, and verify the new GitHub Actions result.

Out of scope:

- Critical Reviewer Throughput work;
- unrelated dependency upgrades;
- broad workflow redesign;
- changing package behavior beyond compatibility with the selected dependency
  repair;
- cleanup of `.DS_Store`, ignored artifacts, or scratch outputs;
- force-push, amend, rebase, reset, stash, or destructive cleanup.

## Read First

- `AGENTS.md` - repo-local safety and git policy.
- `.github/workflows/ci.yml` - failing hosted workflow.
- `.github/workflows/external-tools.yml` - related hosted Python 3.14 workflow.
- `pyproject.toml` - dependency constraint.
- `uv.lock` - locked dependency version and wheel metadata.
- `docs/goals/001b-ci-python314-lxml-repair/Plan.md`
- `docs/goals/001b-ci-python314-lxml-repair/Runbook.md`
- `docs/goals/001b-ci-python314-lxml-repair/Log.md`
- `docs/decisions.md` - decide whether a small ADR entry is warranted.
- `docs/log/2026-06-12_python314_readiness_publication.md` - prior published
  readiness evidence.

## Starting State Checks

Start by reporting:

- `pwd`;
- `git status --short --branch`;
- `git rev-parse --short HEAD`;
- `git rev-parse --short origin/main`;
- `git remote -v`;
- `git log -5 --oneline`;
- whether `.DS_Store` is still the only untracked file before this packet.

Run:

```sh
git fetch --prune origin
```

Stop and wake the orchestrator if local `HEAD` and `origin/main` are not both
`e9802fb` before you begin repair work. Do not pull or merge to recover.

## Git And Publication Policy

Commit and push are authorized for this goal if local validation passes.

Stage exact files only. Expected files may include:

```text
.github/workflows/ci.yml
.github/workflows/external-tools.yml
pyproject.toml
uv.lock
docs/decisions.md
docs/log/2026-06-12_ci_python314_lxml_repair.md
docs/goals/001b-ci-python314-lxml-repair/Goal.md
docs/goals/001b-ci-python314-lxml-repair/Plan.md
docs/goals/001b-ci-python314-lxml-repair/Runbook.md
docs/goals/001b-ci-python314-lxml-repair/Log.md
```

Do not stage `.DS_Store`.

Use a concise commit message such as:

```text
ci: repair Python 3.14 lxml sync
```

Push with:

```sh
git push origin main
```

After pushing, inspect the new GitHub Actions `ci` run for the pushed commit.
Use `gh` for Actions checks/logs. GitHub interaction is limited to
`BWBrook/wordmark` run/check inspection for this goal.

## Required Work

- Confirm the remote CI failure and root cause.
- Attempt the preferred dependency-side repair first:
  - update `pyproject.toml` to require a CPython 3.14 wheel-providing `lxml`
    release;
  - refresh `uv.lock`;
  - validate locally.
- If the dependency-side repair fails due real code incompatibility, revert that
  attempted change and stop with evidence before trying a second strategy.
- If the dependency-side repair is compatible locally, commit and push it.
- Inspect the GitHub Actions run for the pushed repair.
- Update `Log.md` throughout and wake the orchestrator when complete or blocked.

## Validation Gates

Run at minimum:

```sh
uv lock --upgrade-package lxml
uv sync --locked --extra dev
uv lock --check
git diff --check
uv run ruff check .
uv run pytest
make test-pure-cov
make check
actionlint
```

If you modify `external-tools.yml` or if the dependency repair touches behavior
likely to affect external tools, also run:

```sh
make test-external
```

After push, verify the GitHub Actions `ci` run for the pushed commit. A passing
hosted `ci` run is the primary completion gate.

## Deliverables

- Updated `docs/goals/001b-ci-python314-lxml-repair/Log.md`.
- Any needed docs/decision/log note.
- Pushed commit on `main`, if validation passes.
- Wake-up report to the Wordmark orchestrator with:
  - root cause;
  - chosen repair;
  - validation results;
  - pushed commit SHA;
  - GitHub Actions run URL and status;
  - final `git status --short --branch`;
  - residual risks.

## Decision Authority

You may decide:

- exact `lxml` lower bound if the chosen version provides CPython 3.14 wheels
  and tests pass;
- whether a short ADR/log note is sufficient;
- whether `external-tools.yml` also needs a matching guard.

You must pause before:

- accepting a CI-only system-header workaround if dependency upgrade fails for
  unclear reasons;
- changing unrelated dependencies;
- weakening tests or lint;
- disabling or skipping CI jobs;
- force-pushing, rebasing, amending, resetting, stashing, cleaning, or deleting
  local artifacts.

## Stop Conditions

Stop when one of these is true:

- local validation passes, the repair is pushed, and the corresponding GitHub
  Actions `ci` run passes;
- the dependency-side repair fails due code incompatibility and a fallback
  strategy requires orchestrator judgement;
- remote/local starting state differs from the expected `e9802fb`;
- the fix would leave this goal's scope.

## Final Response Requirements

Wake the Wordmark orchestrator thread when done or blocked. Include:

- branch, local `HEAD`, and `origin/main`;
- commit SHA and push result, if any;
- GitHub Actions run URL and status;
- validation command outcomes;
- final dirty/untracked state;
- whether `.DS_Store` stayed untracked and unstaged;
- whether Goal 002 can proceed.
