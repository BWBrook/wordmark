# Log: Goal 001b Hosted Python 3.14 CI Repair

## 2026-06-12 - Created By Wordmark Orchestrator

Barry identified a GitHub CI failure after Goal 001. The Wordmark orchestrator
used the GitHub plugin and `gh` to inspect remote evidence before creating this
goal.

Observed failing runs:

```text
27408689878 - ci for a00d2bc chore: publish macOS Python 3.14 readiness
27408770801 - ci for e9802fb docs: record goal 001 publication result
```

Both push-triggered `ci` runs failed in `lint` and `pure-python (py3.14)` at
the `Sync dependencies` step:

```text
uv sync --extra dev
Building lxml==5.4.0
Failed to build `lxml==5.4.0`
Error: Please make sure the libxml2 and libxslt development packages are installed.
```

Root-cause hypothesis from orchestrator evidence: the Python 3.14 lock pins
`lxml==5.4.0`, which has no CPython 3.14 manylinux wheels; GitHub's Linux
runner therefore attempts a source build and lacks the required XML/XSLT
development headers. PyPI metadata checked by the orchestrator showed CPython
3.14 manylinux wheels for `lxml 6.0.1` and `6.0.2`.

Preferred repair: update the `lxml` dependency constraint and lockfile to a
CPython 3.14 wheel-providing `6.x` release if local tests pass. Use CI
system-header installation only as a fallback after reporting incompatibility
evidence.

## 2026-06-12 21:49 AEST - Phase 1 Starting State And Failure Confirmed

Read the goal packet first (`Goal.md`, `Plan.md`, `Runbook.md`, `Log.md`),
then read repo-local `AGENTS.md` and the named repair surface files.

Starting snapshot before repair:

```text
pwd = /Users/bwbrook/work/wordmark
branch/status = main...origin/main
local HEAD = e9802fb
origin/main = e9802fb
remote = origin git@github.com:BWBrook/wordmark.git
recent commits =
  e9802fb docs: record goal 001 publication result
  a00d2bc chore: publish macOS Python 3.14 readiness
  db52e96 Harden markdown manuscript proposals
  0f31744 Refresh GitHub Actions setup actions
  2d97c5c Harden validation and subprocess handling
untracked = .DS_Store plus this Goal 001b packet
```

Ran `git fetch --prune origin`. Remote guard passed:

```text
local HEAD = e9802fb
origin/main = e9802fb
```

Confirmed `gh auth status` is authenticated as `BWBrook`. Inspected GitHub
Actions run `27408770801` for `BWBrook/wordmark`:

```text
workflow = ci
event = push
headBranch = main
headSha = e9802fbc776c37ad702776e9ad1e36c6160aca75
status = completed
conclusion = failure
url = https://github.com/BWBrook/wordmark/actions/runs/27408770801
failed jobs = lint, pure-python (py3.14)
failed step = Sync dependencies
command = uv sync --extra dev
```

Concise failure evidence from `gh run view --log-failed`:

```text
Using CPython 3.14.5 interpreter at /opt/hostedtoolcache/Python/3.14.5/x64/bin/python3.14
Building lxml==5.4.0
Failed to build `lxml==5.4.0`
Error: Please make sure the libxml2 and libxslt development packages are installed.
hint: `lxml` (v5.4.0) was included because `wordmark` (v0.1.0) depends on `lxml`
```

Local repair surface confirms the root cause:

```text
pyproject.toml dependency = "lxml>=5.2,<6"
uv.lock requires-python = ">=3.14"
uv.lock lxml pin = 5.4.0
```

Chosen repair remains dependency-side: move the `lxml` constraint and lock to a
CPython 3.14 wheel-providing `6.x` release, avoiding workflow system packages
unless local compatibility fails.

## 2026-06-12 21:49 AEST - Phase 2 Preferred Repair Applied

Applied the dependency-side repair.

Changed `pyproject.toml`:

```text
lxml>=5.2,<6 -> lxml>=6.0.2,<7
```

Ran:

```text
uv lock --upgrade-package lxml
```

Result:

```text
Updated lxml v5.4.0 -> v6.1.1
```

Inspected `uv.lock`; it now pins `lxml==6.1.1` and includes CPython 3.14
manylinux wheels, including:

```text
lxml-6.1.1-cp314-cp314-manylinux2014_x86_64.manylinux_2_17_x86_64.whl
lxml-6.1.1-cp314-cp314-manylinux_2_26_x86_64.manylinux_2_28_x86_64.whl
```

Ran:

```text
uv sync --locked --extra dev
```

Result:

```text
PASS - installed lxml==6.1.1; no lxml==5.4.0 source build
```

No workflow system-package workaround was used. No external-tools workflow
change was made. No `docs/decisions.md` ADR update was needed because ADR-038
already records the Python 3.14 baseline; this goal is a narrow dependency
compatibility repair and is documented in `docs/log/`.

## 2026-06-12 21:49 AEST - Phase 3 Local Validation Passed

Required validation gates passed:

```text
uv lock --upgrade-package lxml
  PASS - lxml 5.4.0 -> 6.1.1
uv sync --locked --extra dev
  PASS - installed lxml==6.1.1 from wheel
uv lock --check
  PASS - resolved 21 packages
git diff --check
  PASS
uv run ruff check .
  PASS - All checks passed
uv run pytest
  PASS - 126 passed, 5 skipped
make test-pure-cov
  PASS - 114 passed, 17 deselected, coverage 83.69%
make check
  PASS - 126 passed, 5 skipped; ruff passed
actionlint
  PASS
make test-external
  PASS - 12 passed, 5 skipped, 114 deselected
```

`make test-external` was run even though workflow files were unchanged because
the repair updates a core dependency used by document/XML flows.
