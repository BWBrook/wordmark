# Log: Goal 001 Python 3.14 Readiness Publication

## 2026-06-12 - Created By Wordmark Orchestrator

Barry authorized Goal 001, including commit and push if validation passes.

Initial expected action-repo state before this goal packet was added:

```text
branch/status = main...origin/main
HEAD = db52e96
modified = .github/workflows/ci.yml, .github/workflows/external-tools.yml,
  Makefile, README.md, docs/architecture.md, docs/decisions.md,
  docs/fidelity-policy.md, pyproject.toml, src/wordmark/models.py, uv.lock
untracked = .DS_Store, .python-version,
  docs/log/2026-05-29_macos_python314_readiness_sweep.md
```

This goal packet adds:

```text
docs/goals/001-python314-readiness-publish/Goal.md
docs/goals/001-python314-readiness-publish/Plan.md
docs/goals/001-python314-readiness-publish/Runbook.md
docs/goals/001-python314-readiness-publish/Log.md
```

`redpen` should update this log during execution, preserve `.DS_Store` as
unstaged local state, and wake the Wordmark orchestrator when complete or
blocked.

## 2026-06-12 19:54 AEST - Phase 1 Starting State Confirmed

Read the goal packet first (`Goal.md`, `Plan.md`, `Runbook.md`, `Log.md`),
then read repo-local `AGENTS.md` and the readiness-surface files named in the
goal.

Starting snapshot:

```text
pwd = /Users/bwbrook/work/wordmark
branch/status = main...origin/main
HEAD = db52e96
remote = origin git@github.com:BWBrook/wordmark.git
local default branch ref = origin/main
recent commits =
  db52e96 Harden markdown manuscript proposals
  0f31744 Refresh GitHub Actions setup actions
  2d97c5c Harden validation and subprocess handling
  28b5ebf Harden wordmark review workflows
  3195b3a Add macOS compatibility support
AGENTS.md = present and clean
```

Ran `git fetch --prune origin`. Remote safety gate passed:

```text
local HEAD = db52e96
origin/main = db52e96
```

Dirty state after fetch remains the expected readiness bundle plus untracked
`.DS_Store`, `.python-version`, the goal packet, and the prior readiness log.

## 2026-06-12 19:54 AEST - Phase 2 Diff Audit Complete

Audited the readiness diff and untracked scope.

Diff summary:

```text
.github/workflows/ci.yml             | Python 3.14 hosted pure lane
.github/workflows/external-tools.yml | Python 3.14 hosted external lane
Makefile                             | sync pins Python 3.14
README.md                            | macOS/Python 3.14 environment contract
docs/architecture.md                 | cross-platform wording
docs/decisions.md                    | ADR-038 Python 3.14 baseline
docs/fidelity-policy.md              | CLI-native wording
pyproject.toml                       | requires-python >=3.14, ruff py314
src/wordmark/models.py               | timezone-aware UTC timestamp
uv.lock                              | lockfile regenerated for >=3.14
```

Untracked scope:

```text
.DS_Store
.python-version
docs/goals/001-python314-readiness-publish/{Goal.md,Plan.md,Runbook.md,Log.md}
docs/log/2026-05-29_macos_python314_readiness_sweep.md
```

`.python-version` contains `3.14`. `git diff --check` passed during audit.
Dirty state is limited to the readiness bundle, this goal packet/log update,
and the preserved pre-existing `.DS_Store`.

Decision: add a short `docs/log/2026-06-12_python314_readiness_publication.md`
publication note after current validation so repo-level execution history
captures the publish evidence, not only this goal packet.

## 2026-06-12 19:54 AEST - Phase 3 Validation Passed

Ran the required validation gates in runbook order. No readiness-scope fixes
were required.

```text
uv sync --locked --extra dev
  PASS - resolved 21 packages, checked 20 packages
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
make test-external
  PASS - 12 passed, 5 skipped, 114 deselected
make check
  PASS - 126 passed, 5 skipped; ruff passed
actionlint
  PASS
uv run python -m compileall -q src tests
  PASS
uv build --out-dir /tmp/wordmark-dist-goal001
  PASS - built wordmark-0.1.0.tar.gz and wordmark-0.1.0-py3-none-any.whl
```

CLI fixture smoke checks:

```text
uv run wordmark inspect examples/canonical/test_doc.docx --json
  PASS - schema_version 2, 25 paragraphs, no comments/revisions
uv run wordmark review list examples/canonical/test_doc.docx --json
  PASS - schema_version 2, 25 paragraphs, no comments/revisions
uv run wordmark render examples/canonical/test_doc.docx --out /tmp/wordmark-render-goal001 --json
  PASS - PDF plus 3 PNG pages written under /tmp/wordmark-render-goal001
uv run wordmark verify examples/canonical/test_doc.docx examples/canonical/test_doc.docx --profile business-docs --json
  PASS - verify.passed true; render_diff.ok true; 3 pages; max ratio 0.0
```

Wheel smoke:

```text
rm -rf /tmp/wordmark-wheel-test-goal001
  PASS
uv venv --python 3.14 /tmp/wordmark-wheel-test-goal001
  PASS - CPython 3.14.4
uv pip install --python /tmp/wordmark-wheel-test-goal001/bin/python /tmp/wordmark-dist-goal001/*.whl
  PASS - installed wordmark 0.1.0 and 12 dependencies
/tmp/wordmark-wheel-test-goal001/bin/wordmark --help
  PASS - CLI help rendered
```

Generated/ignored outputs worth reporting:

```text
/tmp/wordmark-dist-goal001/
/tmp/wordmark-render-goal001/
/tmp/wordmark-wheel-test-goal001/
artifacts/test_doc.*
artifacts/test_doc.render/
artifacts/transcripts/operations.jsonl
```
