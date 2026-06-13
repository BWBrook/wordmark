# Runbook: Goal 002 Critical Reviewer Throughput v1

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

Expected before implementation:

```text
HEAD = 355662d
origin/main = 355662d
pre-existing untracked file before this packet = .DS_Store
current untracked files = .DS_Store plus this Goal 002 packet
```

If the state differs, stop and wake the orchestrator.

## Context Reads

Read:

```text
AGENTS.md
README.md
docs/critical-reviewer-playbook.md
docs/authoring-workflow.md
docs/markdown-quarto-collab-workflow.md
docs/fidelity-policy.md
docs/decisions.md
tests/test_manuscript_workflow.py
```

Use bounded inspection for large files. The likely change surface is guidance
and calibration, not engine behavior.

## Implementation Notes

Recommended path:

1. Strengthen `docs/critical-reviewer-playbook.md`:
   - add a more assertive reviewer stance;
   - add tracked-edit versus comment rules;
   - add weak-versus-preferred examples;
   - keep safety and audit guidance intact.
2. Add a short reusable agent brief, likely:
   - `docs/critical-reviewer-agent-brief.md`.
3. Add a small calibration fixture, likely:
   - `examples/reviewer_calibration/critical_line_edits.yaml`.
4. Add a lightweight parser/structure test, likely:
   - `tests/test_reviewer_calibration.py`.
5. Add discoverability links and a dated log note.

The calibration fixture should include cases for:

- grammar/agreement;
- punctuation or hyphenation;
- British English spelling;
- wordiness or hedging;
- unclear antecedents;
- sentence-flow improvement;
- comment-only scientific or structural judgment.

Each case should make the preferred action obvious enough for a future agent to
calibrate against before reviewing a real document.

## Validation

If a calibration test is added:

```sh
uv run pytest tests/test_reviewer_calibration.py -q
```

Required:

```sh
uv lock --check
git diff --check
uv run ruff check .
uv run pytest
make check
```

Only run this if the final diff touches external-tool, render, Quarto, or DOCX
integration behavior:

```sh
make test-external
```

## Commit And Push

Before staging:

```sh
git status --short
git diff --stat
```

Stage exact paths. Expected paths may include:

```sh
git add docs/critical-reviewer-playbook.md
git add docs/critical-reviewer-agent-brief.md
git add docs/authoring-workflow.md README.md
git add examples/reviewer_calibration/critical_line_edits.yaml
git add tests/test_reviewer_calibration.py
git add docs/log/2026-06-13_critical_reviewer_throughput.md
git add docs/goals/002-critical-reviewer-throughput/Goal.md
git add docs/goals/002-critical-reviewer-throughput/Plan.md
git add docs/goals/002-critical-reviewer-throughput/Runbook.md
git add docs/goals/002-critical-reviewer-throughput/Log.md
```

Adjust the exact path list to match the final diff. Do not stage `.DS_Store`.

Confirm staged scope:

```sh
git diff --cached --stat
git status --short
```

Commit and push:

```sh
git commit -m "docs: strengthen critical reviewer guidance"
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
