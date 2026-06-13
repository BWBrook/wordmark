# Log: Goal 002 Critical Reviewer Throughput v1

## 2026-06-13 - Created By Wordmark Orchestrator

Goal 001 and Goal 001b are complete, and hosted `ci` is green at `355662d`.
Barry approved moving to the critical reviewer guidance work and asked that
future orchestrator closeouts include a concrete next-goal proposal for
approval or modification.

This goal targets the observed review-quality problem: agents are too reluctant
to make high-confidence grammatical and clarity-related line edits, tending
instead toward generic comments. The intended improvement is not a DOCX engine
change. It is a stronger reviewer stance, concrete edit/comment decision rules,
and calibration examples that future agents can read before reviewing a real
document.

Starting expectation for `redpen`:

```text
repo = /Users/bwbrook/work/wordmark
branch/status = main...origin/main
HEAD = 355662d
origin/main = 355662d
pre-existing untracked file before this packet = .DS_Store
current untracked files = .DS_Store plus this Goal 002 packet
```

Commit and push are authorized if local validation passes and hosted `ci`
passes for the pushed commit. `.DS_Store` must remain untracked and unstaged.

## 2026-06-13 - Redpen Start And Approach

Preflight confirmed the expected guard state after `git fetch --prune origin`:

```text
pwd = /Users/bwbrook/work/wordmark
branch/status = main...origin/main
HEAD = 355662d
origin/main = 355662d
dirty state = untracked .DS_Store plus untracked Goal 002 packet
```

Read repo-local `AGENTS.md`, the Goal 002 packet, `README.md`,
`docs/critical-reviewer-playbook.md`, `docs/authoring-workflow.md`,
`docs/markdown-quarto-collab-workflow.md`, `docs/fidelity-policy.md`, and the
current decision log tail. Implementation will stay in guidance and
calibration: sharpen the reviewer playbook, add a short reusable agent brief,
add structured calibration examples, validate that fixture with a focused
pytest test, and add a dated execution note. No DOCX mutation behavior,
OOXML/UNO logic, dependencies, CI workflow design, or manuscript content will be
changed.

## 2026-06-13 - Local Implementation And Validation

Implemented the guidance-only Goal 002 scope:

- strengthened `docs/critical-reviewer-playbook.md` with a line-edit-first
  reviewer stance, tracked-edit/comment decision rules, weak-versus-preferred
  examples, and sharper comment standards;
- added `docs/critical-reviewer-agent-brief.md` as the short reusable prompt
  for future agents;
- added `examples/reviewer_calibration/critical_line_edits.yaml` with 12
  calibration cases: 8 tracked-edit cases and 4 comment-only cases;
- added `tests/test_reviewer_calibration.py` to validate the calibration
  fixture shape, required categories, and tracked-edit/comment separation;
- linked the reviewer guidance from `README.md` and
  `docs/authoring-workflow.md`;
- added `docs/log/2026-06-13_critical_reviewer_throughput.md`.

Local validation passed:

```text
uv run pytest tests/test_reviewer_calibration.py -q
... [100%]

uv lock --check
Resolved 21 packages in 4ms

git diff --check
passed with no output

uv run ruff check .
All checks passed!

uv run pytest
129 passed, 5 skipped in 21.39s

make check
129 passed, 5 skipped in 18.88s
All checks passed!
```

`make test-external` was not run because the final diff does not touch
external-tool, render, Quarto, or DOCX integration behavior.
