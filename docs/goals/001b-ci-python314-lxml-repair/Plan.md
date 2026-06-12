# Plan: Goal 001b Hosted Python 3.14 CI Repair

## Phase 1 - Confirm Failure And Starting State

- [x] Read the goal packet and repo-local `AGENTS.md`.
- [x] Capture local branch, SHA, remote, and dirty state.
- [x] Fetch/prune and confirm local `HEAD` and `origin/main` are both
  `e9802fb`.
- [x] Inspect the failing GitHub Actions run for `e9802fb`.
- [x] Record the root cause in `Log.md`.

## Phase 2 - Apply Preferred Dependency Repair

- [x] Update `pyproject.toml` so `lxml` resolves to a CPython 3.14
  wheel-providing release.
- [x] Refresh `uv.lock`.
- [x] Confirm `uv sync --locked --extra dev` no longer builds failing
  `lxml==5.4.0`.
- [x] Add a short dated `docs/log/` note.
- [x] Add or update `docs/decisions.md` only if the dependency constraint
  change needs a durable ADR.

## Phase 3 - Local Validation

- [x] Run `uv lock --check`.
- [x] Run `git diff --check`.
- [x] Run `uv run ruff check .`.
- [x] Run `uv run pytest`.
- [x] Run `make test-pure-cov`.
- [x] Run `make check`.
- [x] Run `actionlint`.
- [x] Run `make test-external` if the final change could affect external-tools
  workflow behavior.

## Phase 4 - Commit, Push, And Watch CI

- [ ] Stage exact approved paths only.
- [ ] Confirm `.DS_Store` is untracked and unstaged.
- [ ] Commit the CI repair.
- [ ] Push to `origin main`.
- [ ] Inspect the new GitHub Actions `ci` run for the pushed SHA.
- [ ] If CI fails, fetch the failing log and update `Log.md` before deciding
  whether to fix in scope or wake the orchestrator.

## Phase 5 - Wake Orchestrator

- [ ] Record final status and GitHub Actions result in `Log.md`.
- [ ] Send the Wordmark orchestrator a concise wake-up with the repair,
  validation, CI URL/status, final git state, and residual risk.
