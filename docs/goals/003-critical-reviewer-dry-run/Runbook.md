# Runbook: Goal 003 Critical Reviewer Dry Run

## Phase A Invocation

Phase A is intentionally run by the orchestrator with:

```text
model = gpt-5.4-mini
thinking = low
```

Do Phase A only. Do not proceed to review work.

## Phase A Starting Checks

```sh
pwd
git status --short --branch
git rev-parse --short HEAD
git rev-parse --short origin/main
git remote -v
git log -5 --oneline
git ls-files --others --exclude-standard
git fetch --prune origin
git rev-parse --short HEAD
git rev-parse --short origin/main
git status --short --branch
```

Expected before Phase A:

```text
HEAD = 3c985eb
origin/main = 3c985eb
pre-existing untracked file before this packet = .DS_Store
current untracked files = .DS_Store plus this Goal 003 packet
```

If the state differs, stop and wake the orchestrator.

## Phase A Manuscript Creation

Create a fictional manuscript source and baseline DOCX. Preferred paths:

```text
examples/reviewer_calibration/synthetic_manuscript_goal003.md
examples/canonical/reviewer_dry_run_synthetic_goal003.docx
```

Requirements:

- 800 to 1400 words;
- fictional ecology/conservation topic;
- plausible rough manuscript style;
- sections such as title, abstract, introduction, methods, results, discussion;
- natural mixture of local language problems and author-judgment issues;
- no answer key;
- no labelled flaw list;
- no real unpublished content.

Use `python-docx` through the project environment if needed. A small temporary
helper script is acceptable, but do not leave unnecessary scratch scripts in
the repository unless they are part of the deliverable.

## Phase A Smoke Check

Run:

```sh
uv run wordmark inspect examples/canonical/reviewer_dry_run_synthetic_goal003.docx --json
git status --short --branch
```

Update `docs/goals/003-critical-reviewer-dry-run/Log.md` with:

- source path;
- DOCX path;
- rough word count;
- smoke-check outcome;
- final status.

Then wake the orchestrator and stop. Do not commit or push.

## Phase B Invocation

Phase B is intentionally run later by the orchestrator with:

```text
model = gpt-5.5
thinking = xhigh
```

Do not start Phase B until the orchestrator sends the follow-up.

## Phase B Starting Checks

```sh
pwd
git status --short --branch
git rev-parse --short HEAD
git rev-parse --short origin/main
git ls-files --others --exclude-standard
```

Expected Phase B state:

- `HEAD` and `origin/main` still reflect the pre-Goal-003 branch tip unless
  the orchestrator reports otherwise;
- untracked/modified files are `.DS_Store`, the Goal 003 packet, and Phase A
  manuscript files.

Stop and wake the orchestrator if unexpected changes are present.

## Phase B Review Work

Read:

```text
docs/critical-reviewer-agent-brief.md
docs/critical-reviewer-playbook.md
examples/reviewer_calibration/critical_line_edits.yaml
docs/authoring-workflow.md
docs/fidelity-policy.md
```

Create a safe edited copy, likely:

```text
examples/edited/reviewer_dry_run_synthetic_goal003_edited_sat13jun2026.docx
```

Use Wordmark operations to:

- apply obvious high-confidence tracked line edits;
- add comments for author-judgment issues;
- avoid broad paragraph rewrites unless clearly safe;
- preserve auditability and sidecars.

## Phase B Validation

Run with actual paths:

```sh
uv run wordmark inspect <edited-docx> --text-mode review-visible --json
uv run wordmark review list <edited-docx> --text-mode review-visible --json
uv run wordmark verify <baseline-docx> <edited-docx> --profile review-edit --json
```

Render only if warranted:

```sh
uv run wordmark render <edited-docx> --out artifacts/goal003_render --json
```

Then:

```sh
git diff --check
uv lock --check
uv run pytest
make check
```

Run `make test-external` only if external-tool, render, Quarto, or DOCX
integration behaviour changes.

## Phase B Commit And Push

Before staging:

```sh
git status --short
git diff --stat
```

Stage exact paths. Do not stage `.DS_Store`.

Commit:

```sh
git commit -m "docs: run critical reviewer dry run"
git push origin main
```

## Hosted CI Verification

```sh
git rev-parse HEAD
gh run list --repo BWBrook/wordmark --branch main --limit 10 --json databaseId,workflowName,status,conclusion,headSha,url,createdAt
gh run watch <run-id> --repo BWBrook/wordmark --exit-status
gh run view <run-id> --repo BWBrook/wordmark --json databaseId,workflowName,status,conclusion,headSha,url,jobs
```

If CI fails:

```sh
gh run view <run-id> --repo BWBrook/wordmark --log-failed
```

Update the log, then decide whether the issue is in scope or wake the
orchestrator.

## Wake-Up Requirements

Phase A wake-up:

- manuscript paths;
- rough length;
- smoke-check result;
- final status;
- no review/guidance edit/commit/push confirmation.

Phase B wake-up:

- changed files;
- edited DOCX path;
- revision/comment counts;
- examples of direct tracked edits and author-judgment comments;
- validation outcomes;
- commit/push/CI status;
- final status and residual risks.
