# Runbook: Goal 004 Reviewer Output Assessment Gate

## Starting Checks

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

Expected before assessment:

```text
HEAD = 03f85e6
origin/main = 03f85e6
only untracked file = .DS_Store plus this Goal 004 packet
```

If the state differs, stop and wake the orchestrator.

## Read Inputs

Read:

```text
AGENTS.md
docs/goals/004-reviewer-output-assessment/Goal.md
docs/goals/004-reviewer-output-assessment/Plan.md
docs/goals/004-reviewer-output-assessment/Runbook.md
docs/goals/004-reviewer-output-assessment/Log.md
docs/goals/003-critical-reviewer-dry-run/Log.md
docs/log/2026-06-13_critical_reviewer_dry_run.md
docs/critical-reviewer-agent-brief.md
docs/critical-reviewer-playbook.md
examples/reviewer_calibration/critical_line_edits.yaml
examples/reviewer_calibration/synthetic_manuscript_goal003.md
```

Optional audit reads if present:

```text
artifacts/goal003_review_patch.json
artifacts/transcripts/operations.jsonl
```

Do not stage or clean ignored artifacts.

## Evidence Commands

Capture review state:

```sh
uv run wordmark review list examples/edited/reviewer_dry_run_synthetic_goal003_edited_sat13jun2026.docx --text-mode review-visible --json > /tmp/goal004-review-list.json
jq '{revision_count: (.review.revisions|length), comment_count: (.review.comments|length), revision_types: ([.review.revisions[].type] | group_by(.) | map({type: .[0], count: length}))}' /tmp/goal004-review-list.json
```

Verify fidelity:

```sh
uv run wordmark verify examples/canonical/reviewer_dry_run_synthetic_goal003.docx examples/edited/reviewer_dry_run_synthetic_goal003_edited_sat13jun2026.docx --profile review-edit --json > /tmp/goal004-verify.json
jq '.verify.passed, .verify.checks.comment_integrity.ok, .verify.checks.compatibility_namespace_integrity.ok, .verify.checks.render_diff.ok' /tmp/goal004-verify.json
```

Use the JSON plus the documents/logs to make the assessment.

## Assessment Guidance

Tracked-edit assessment:

- Good: direct local edit, meaning preserved, better than a comment.
- Questionable: edit is correct but phrasing could be more elegant.
- Missed opportunity: local issue was left untouched or became a comment.
- Meaning-risk: edit may alter scientific meaning or emphasis.

Comment assessment:

- Appropriate: author judgment, evidence, methods, interpretation, or structure.
- Too timid: issue identified but action request not strong enough.
- Too broad: comment lacks a clear next action.
- Should-have-been-edit: comment describes a safe local edit.
- Missing: important scientific issue not flagged.

Engine/tooling assessment:

- Decide whether the second-pass-in-tracked-text UNO routing note is:
  - no action now;
  - operator guidance;
  - small future engine ticket.

## Write Assessment Packet

Create:

```text
docs/reviewer-output-assessment-goal003.md
docs/log/2026-06-14_reviewer_output_assessment.md
```

The benchmark packet should be concise and include:

- primary recommendation;
- baseline/edited DOCX paths;
- revision/comment counts;
- selected tracked edits;
- selected comments;
- any missed opportunities or caveats;
- specific questions for Barry.

## Validation

Run:

```sh
uv run wordmark review list examples/edited/reviewer_dry_run_synthetic_goal003_edited_sat13jun2026.docx --text-mode review-visible --json
uv run wordmark verify examples/canonical/reviewer_dry_run_synthetic_goal003.docx examples/edited/reviewer_dry_run_synthetic_goal003_edited_sat13jun2026.docx --profile review-edit --json
git diff --check
uv lock --check
uv run pytest
make check
```

Run `make test-external` only if the final diff changes external-tool, render,
Quarto, DOCX engine, OOXML/UNO, dependency, or CI behaviour.

## Commit And Push

Before staging:

```sh
git status --short
git diff --stat
```

Stage exact paths, likely:

```sh
git add docs/reviewer-output-assessment-goal003.md
git add docs/log/2026-06-14_reviewer_output_assessment.md
git add docs/goals/004-reviewer-output-assessment/Goal.md
git add docs/goals/004-reviewer-output-assessment/Plan.md
git add docs/goals/004-reviewer-output-assessment/Runbook.md
git add docs/goals/004-reviewer-output-assessment/Log.md
```

Confirm staged scope:

```sh
git diff --cached --stat
git status --short
```

Commit and push:

```sh
git commit -m "docs: assess critical reviewer dry run"
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

Wake the orchestrator with the result.
