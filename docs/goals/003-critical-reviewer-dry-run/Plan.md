# Plan: Goal 003 Critical Reviewer Dry Run

## Phase A - Weak-Model Synthetic Manuscript

- [x] Read the goal packet and repo-local `AGENTS.md`.
- [x] Capture branch, SHA, remote, dirty state, and fetch/prune guard.
- [x] Confirm local `HEAD` and `origin/main` are both `3c985eb`.
- [x] Create a fictional ecology/conservation manuscript source without an
  answer key.
- [x] Generate a baseline synthetic DOCX fixture in a safe repo-local path.
- [x] Smoke-check the baseline DOCX with `wordmark inspect`.
- [x] Update this log with manuscript paths and smoke-check outcome.
- [x] Wake the orchestrator and stop without committing or pushing.

## Phase B - Strong-Model Critical Review

- [x] Reconfirm branch, SHA, remote, dirty state, and Phase A file set.
- [x] Read the Goal 002 reviewer brief, playbook, and calibration fixture.
- [x] Build a review plan for the synthetic DOCX.
- [x] Apply high-confidence tracked line edits to a safe edited copy.
- [x] Add comments for author-judgment issues.
- [x] Inspect review state and count revisions/comments.
- [x] Verify the edited output with `review-edit` profile.
- [x] Render the edited output only if validation or layout risk warrants it.
- [x] Decide whether guidance tuning is warranted.
- [x] Add a dry-run report/log.
- [x] Run local validation.
- [x] Stage exact approved files only.
- [x] Confirm `.DS_Store` is untracked and unstaged.
- [ ] Commit and push.
- [ ] Inspect hosted `ci` for the pushed SHA.
- [ ] Wake the orchestrator with evidence and recommended next goal shape.
