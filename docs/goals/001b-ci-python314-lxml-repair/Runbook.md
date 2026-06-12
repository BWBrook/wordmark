# Runbook: Goal 001b Hosted Python 3.14 CI Repair

## Starting Checks

```sh
pwd
git status --short --branch
git rev-parse --short HEAD
git rev-parse --short origin/main
git remote -v
git log -5 --oneline
git ls-files --others --exclude-standard
```

Then:

```sh
git fetch --prune origin
git rev-parse --short HEAD
git rev-parse --short origin/main
git status --short --branch
```

Expected before repair:

```text
HEAD = e9802fb
origin/main = e9802fb
only pre-existing untracked file before this packet = .DS_Store
```

## GitHub Failure Inspection

```sh
gh auth status
gh run view 27408770801 --repo BWBrook/wordmark --json databaseId,name,workflowName,conclusion,status,event,headBranch,headSha,url,jobs
gh run view 27408770801 --repo BWBrook/wordmark --log-failed
```

Record the failing job names, failing step, and concise error snippet in
`Log.md`.

## Preferred Repair

Use a version with CPython 3.14 Linux wheels. The orchestrator observed PyPI
metadata showing `lxml 6.0.2` has CPython 3.14 manylinux wheels.

Update `pyproject.toml` from:

```toml
"lxml>=5.2,<6",
```

to a compatible `6.x` constraint, for example:

```toml
"lxml>=6.0.2,<7",
```

Then refresh the lock:

```sh
uv lock --upgrade-package lxml
```

Inspect the resulting `uv.lock` entry for `lxml` and confirm it no longer pins
`5.4.0`.

## Validation

```sh
uv sync --locked --extra dev
uv lock --check
git diff --check
uv run ruff check .
uv run pytest
make test-pure-cov
make check
actionlint
```

Run this as well if workflow edits touch external hosted setup or if local
dependency behavior suggests external-tool risk:

```sh
make test-external
```

## Commit And Push

Before staging:

```sh
git status --short
git diff --stat
```

Stage exact paths, for example:

```sh
git add pyproject.toml uv.lock
git add docs/goals/001b-ci-python314-lxml-repair/Goal.md
git add docs/goals/001b-ci-python314-lxml-repair/Plan.md
git add docs/goals/001b-ci-python314-lxml-repair/Runbook.md
git add docs/goals/001b-ci-python314-lxml-repair/Log.md
git add docs/log/2026-06-12_ci_python314_lxml_repair.md
```

If `docs/decisions.md` or workflow files change, stage those exact files too.

Confirm `.DS_Store` is not staged:

```sh
git diff --cached --stat
git status --short
```

Commit and push:

```sh
git commit -m "ci: repair Python 3.14 lxml sync"
git push origin main
```

## Hosted CI Verification

Find and inspect the run for the pushed commit:

```sh
git rev-parse HEAD
gh run list --repo BWBrook/wordmark --branch main --limit 10 --json databaseId,workflowName,status,conclusion,headSha,url,createdAt
gh run watch <run-id> --repo BWBrook/wordmark --exit-status
gh run view <run-id> --repo BWBrook/wordmark --json databaseId,workflowName,status,conclusion,headSha,url,jobs
```

If it fails:

```sh
gh run view <run-id> --repo BWBrook/wordmark --log-failed
```

Then decide whether the new failure remains inside this goal. If not, wake the
orchestrator with the evidence.

## Final Status

```sh
git status --short --branch
git rev-parse --short HEAD
git rev-parse --short origin/main
git ls-files --others --exclude-standard
```

Wake the Wordmark orchestrator with the result.
