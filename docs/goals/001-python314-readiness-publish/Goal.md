# Goal 001: Publish Python 3.14 Readiness Bundle

## Objective

Publish the existing macOS/Python 3.14 readiness work on `main` only after
re-validating that the current dirty bundle is coherent, tested, and safe to
commit.

## Why This Matters

Wordmark is about to move into product-quality reviewer workflow work. The
action repo is currently dirty with an apparently intentional Python 3.14/Mac
readiness bundle. Publishing that bundle first gives future goals a clean,
auditable baseline instead of layering new product changes onto unresolved
environment and CI updates.

## Operating Mode

Repo readiness and publication.

## Review Surface

The Wordmark orchestrator will review:

- final git status;
- exact files staged/committed;
- validation command outcomes;
- any code or docs fixes made during readiness validation;
- final commit SHA and push result;
- residual risks or untracked files.

## Scope

In scope:

- inspect the existing dirty readiness bundle;
- verify the bundle against current Mac mini and repo expectations;
- make narrow fixes only when required for the readiness bundle to validate;
- update or add a dated `docs/log/` note if current validation differs from
  the existing readiness log or if a publication note is needed;
- commit and push the accepted readiness bundle and this goal packet;
- preserve the pre-existing untracked `.DS_Store` without staging it.

Out of scope:

- critical-reviewer workflow improvements;
- DOCX reviewer behavior changes;
- Markdown/Quarto collaboration feature work;
- broad refactors unrelated to Python 3.14 readiness;
- changing scientific/reviewer defaults other than the already-dirty readiness
  bundle;
- deleting, cleaning, stashing, resetting, rebasing, force-pushing, or amending.

## Read First

- `AGENTS.md` - repo-local safety, git, verification, and file-output policy.
- `README.md` - public environment contract and validation command surface.
- `docs/log/2026-05-29_macos_python314_readiness_sweep.md` - prior readiness
  evidence to refresh.
- `docs/decisions.md` - ADR-038 and surrounding readiness decisions.
- `pyproject.toml` - Python requirement, tooling, and test configuration.
- `Makefile` - canonical local validation lanes.
- `.github/workflows/ci.yml` and `.github/workflows/external-tools.yml` -
  hosted validation changes.
- `src/wordmark/models.py` - currently dirty timestamp compatibility change.

## Starting State Checks

Start by reporting:

- `pwd`;
- `git status --short --branch`;
- `git rev-parse --short HEAD`;
- `git remote -v`;
- local default branch ref from local refs;
- `git log -5 --oneline`;
- whether `AGENTS.md` is present and clean.

Then run:

```sh
git fetch --prune origin
```

Stop and wake the orchestrator if either condition is not true after fetch:

- local `HEAD` is still `db52e96` on `main`;
- `origin/main` still resolves to `db52e96`.

Do not pull, merge, rebase, reset, stash, or checkout files to recover.

## Git And Publication Policy

Commit and push are authorized for this goal if, and only if, the validation
gates pass or any required fixes remain strictly inside this goal's readiness
scope and then pass validation.

Stage exact paths only. Expected publication paths are:

```text
.github/workflows/ci.yml
.github/workflows/external-tools.yml
.python-version
Makefile
README.md
docs/architecture.md
docs/decisions.md
docs/fidelity-policy.md
docs/log/2026-05-29_macos_python314_readiness_sweep.md
docs/goals/001-python314-readiness-publish/Goal.md
docs/goals/001-python314-readiness-publish/Plan.md
docs/goals/001-python314-readiness-publish/Runbook.md
docs/goals/001-python314-readiness-publish/Log.md
pyproject.toml
src/wordmark/models.py
uv.lock
```

If you add a new dated publication note under `docs/log/`, stage it exactly
and list it in the final report.

Do not stage `.DS_Store`. Preserve it as pre-existing local untracked state.

Use this commit message unless the final diff clearly warrants a better one:

```text
chore: publish macOS Python 3.14 readiness
```

Push with an ordinary:

```sh
git push origin main
```

## Data, Compute, And Staging Policy

- Run locally on the Mac mini checkout.
- Keep build, wheel-smoke, render, and verification scratch outputs under
  `/tmp` where practical.
- Ignored repo-local `artifacts/` outputs may be created by Wordmark commands
  and should be reported, not committed.
- Do not remove generated audit sidecars unless a command itself manages them.

## Required Work

- Audit the dirty bundle so you understand exactly what will be published.
- Refresh validation against the current checkout.
- Fix only readiness-scope defects if validation exposes them.
- Update the goal `Log.md` as you work.
- Commit and push the validated bundle if gates pass.
- Wake the Wordmark orchestrator when complete or blocked.

## Validation Gates

The goal is not complete until these pass, unless a gate is explicitly blocked
by an external system/tool issue that you report:

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

Also run these CLI smoke checks on the canonical fixture:

```sh
uv run wordmark inspect examples/canonical/test_doc.docx --json
uv run wordmark review list examples/canonical/test_doc.docx --json
uv run wordmark render examples/canonical/test_doc.docx --out /tmp/wordmark-render-goal001 --json
uv run wordmark verify examples/canonical/test_doc.docx examples/canonical/test_doc.docx --profile business-docs --json
```

Run a wheel smoke check from the built wheel:

```sh
rm -rf /tmp/wordmark-wheel-test-goal001
uv venv --python 3.14 /tmp/wordmark-wheel-test-goal001
uv pip install --python /tmp/wordmark-wheel-test-goal001/bin/python /tmp/wordmark-dist-goal001/*.whl
/tmp/wordmark-wheel-test-goal001/bin/wordmark --help
```

If a command fails, diagnose narrowly. Fix only if the cause is inside this
readiness bundle. Otherwise stop and wake the orchestrator with the failing
command and exact error summary.

## Deliverables

- Updated `docs/goals/001-python314-readiness-publish/Log.md`.
- A pushed commit on `main` if validation passes.
- Final report to the orchestrator with:
  - changed files committed;
  - validation commands and outcomes;
  - commit SHA and push result;
  - final `git status --short --branch`;
  - any ignored/generated scratch outputs worth noting;
  - any residual risk.

## Decision Authority

You may decide:

- how to organize concise validation notes in `Log.md`;
- whether a small readiness-scope fix is necessary to make validation pass;
- whether to add a dated `docs/log/` publication note if the existing readiness
  log does not clearly capture current validation/publishing evidence.

You must pause before:

- changing public CLI behavior outside the readiness bundle;
- changing review/editor workflow guidance;
- broadening Python/package/tooling scope beyond Python 3.14 readiness;
- deleting or cleaning pre-existing files;
- pulling, merging, rebasing, force-pushing, amending, resetting, stashing, or
  checking out files;
- committing if `origin/main` moved away from `db52e96`.

## Stop Conditions

Stop when one of these is true:

- validation passes, the exact intended paths are committed and pushed, and the
  final report is ready;
- a validation failure cannot be fixed within readiness scope;
- fetch shows `origin/main` or local `HEAD` is no longer at the expected
  starting commit;
- any required action would violate this goal's boundaries.

## Final Response Requirements

Wake the Wordmark orchestrator thread when done or blocked. Report:

- current branch, `HEAD`, and `origin/main`;
- committed SHA if any;
- push result if any;
- validation summary with exact command names;
- final dirty/untracked state;
- whether `.DS_Store` remains preserved and unstaged;
- whether all goal files and logs were updated as required;
- blocker details if stopped early.
