# Plan: Goal 002 Critical Reviewer Throughput v1

## Phase 1 - Confirm State And Read Context

- [x] Read the goal packet and repo-local `AGENTS.md`.
- [x] Capture local branch, SHA, remote, and dirty state.
- [x] Fetch/prune and confirm local `HEAD` and `origin/main` are both
  `355662d`.
- [x] Read the current reviewer guidance and manuscript workflow surfaces.
- [x] Record the implementation approach in `Log.md`.

## Phase 2 - Strengthen Reviewer Guidance

- [x] Revise `docs/critical-reviewer-playbook.md` to make high-confidence
  tracked line edits the default for grammar, clarity, concision, and sentence
  flow.
- [x] Add explicit tracked-edit versus comment decision rules.
- [x] Add weak-versus-preferred examples.
- [x] Preserve safety, auditability, British English, and fidelity guidance.

## Phase 3 - Add Agent Brief And Calibration

- [x] Add a concise reusable agent-facing critical-review brief.
- [x] Add calibration examples for line edits and comment-only cases.
- [x] Add lightweight validation for any structured calibration fixture.
- [x] Update README or authoring workflow links if needed.
- [x] Add a dated `docs/log/` note.

## Phase 4 - Local Validation

- [x] Run the focused calibration test, if one was added.
- [x] Run `uv lock --check`.
- [x] Run `git diff --check`.
- [x] Run `uv run ruff check .`.
- [x] Run `uv run pytest`.
- [x] Run `make check`.
- [x] Run `make test-external` only if the final diff touches external-tool,
  render, Quarto, or DOCX integration behavior.

## Phase 5 - Commit, Push, And Watch CI

- [x] Stage exact approved paths only.
- [x] Confirm `.DS_Store` is untracked and unstaged.
- [ ] Commit the guidance/calibration work.
- [ ] Push to `origin main`.
- [ ] Inspect the GitHub Actions `ci` run for the pushed SHA.
- [ ] If CI fails, fetch the failing log and update `Log.md` before deciding
  whether to fix in scope or wake the orchestrator.

## Phase 6 - Wake Orchestrator

- [ ] Record final status and GitHub Actions result in `Log.md`.
- [ ] Send the Wordmark orchestrator a concise wake-up with the guidance
  changes, calibration artifact, validation, CI URL/status, final git state,
  residual risks, and recommended next goal shape.
