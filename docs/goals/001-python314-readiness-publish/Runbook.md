# Runbook: Goal 001 Python 3.14 Readiness Publication

## Start

```sh
pwd
git status --short --branch
git rev-parse --short HEAD
git remote -v
git symbolic-ref --short refs/remotes/origin/HEAD
git log -5 --oneline
git status --short -- AGENTS.md
```

Read:

```text
AGENTS.md
docs/goals/001-python314-readiness-publish/Goal.md
docs/goals/001-python314-readiness-publish/Plan.md
docs/goals/001-python314-readiness-publish/Runbook.md
docs/goals/001-python314-readiness-publish/Log.md
README.md
docs/log/2026-05-29_macos_python314_readiness_sweep.md
docs/decisions.md
pyproject.toml
Makefile
.github/workflows/ci.yml
.github/workflows/external-tools.yml
src/wordmark/models.py
```

## Remote Safety Gate

```sh
git fetch --prune origin
git rev-parse --short HEAD
git rev-parse --short origin/main
git status --short --branch
```

Expected:

```text
HEAD = db52e96
origin/main = db52e96
```

Stop if that is not true.

## Diff Audit

```sh
git diff --stat
git diff -- .github/workflows/ci.yml .github/workflows/external-tools.yml Makefile README.md docs/architecture.md docs/decisions.md docs/fidelity-policy.md pyproject.toml src/wordmark/models.py
git diff -- uv.lock
git diff --check
```

Also inspect untracked files:

```sh
git status --short
```

Expected untracked files before publication include:

```text
.DS_Store
.python-version
docs/log/2026-05-29_macos_python314_readiness_sweep.md
docs/goals/001-python314-readiness-publish/
```

## Validation

Run in order:

```sh
uv sync --locked --extra dev
uv lock --check
git diff --check
uv run ruff check .
uv run pytest
make test-pure-cov
make test-external
make check
actionlint
uv run python -m compileall -q src tests
uv build --out-dir /tmp/wordmark-dist-goal001
```

CLI fixture smoke checks:

```sh
uv run wordmark inspect examples/canonical/test_doc.docx --json
uv run wordmark review list examples/canonical/test_doc.docx --json
uv run wordmark render examples/canonical/test_doc.docx --out /tmp/wordmark-render-goal001 --json
uv run wordmark verify examples/canonical/test_doc.docx examples/canonical/test_doc.docx --profile business-docs --json
```

Wheel smoke:

```sh
rm -rf /tmp/wordmark-wheel-test-goal001
uv venv --python 3.14 /tmp/wordmark-wheel-test-goal001
uv pip install --python /tmp/wordmark-wheel-test-goal001/bin/python /tmp/wordmark-dist-goal001/*.whl
/tmp/wordmark-wheel-test-goal001/bin/wordmark --help
```

Record pass/fail outcomes in `Log.md`.

## Commit

Before staging:

```sh
git status --short
```

Stage exact paths:

```sh
git add .github/workflows/ci.yml
git add .github/workflows/external-tools.yml
git add .python-version
git add Makefile
git add README.md
git add docs/architecture.md
git add docs/decisions.md
git add docs/fidelity-policy.md
git add docs/log/2026-05-29_macos_python314_readiness_sweep.md
git add docs/goals/001-python314-readiness-publish/Goal.md
git add docs/goals/001-python314-readiness-publish/Plan.md
git add docs/goals/001-python314-readiness-publish/Runbook.md
git add docs/goals/001-python314-readiness-publish/Log.md
git add pyproject.toml
git add src/wordmark/models.py
git add uv.lock
```

If you created a new dated publication log, stage that exact file too.

Verify staged scope:

```sh
git diff --cached --stat
git status --short
```

Confirm `.DS_Store` is not staged.

Commit:

```sh
git commit -m "chore: publish macOS Python 3.14 readiness"
```

## Push

```sh
git push origin main
git status --short --branch
git rev-parse --short HEAD
```

## Wake-Up

Send a short wake-up to the Wordmark orchestrator thread with:

- status: complete or blocked;
- final branch and SHA;
- validation summary;
- commit SHA and push result;
- final dirty/untracked state;
- exact residual risks;
- confirmation that `.DS_Store` was preserved and not staged.
