# AGENTS.md

## Scope
This file defines repository-specific operating rules for agents working in `wordmark`.

## Instruction Priority
When instructions conflict, follow this order:
1. System and developer instructions from the runtime.
2. Explicit user instructions in the current conversation.
3. This `AGENTS.md`.

## Git Workflow
1. Do not create a commit unless the user explicitly asks for it.
2. Use batch commits by default, not atomic micro-commits.
3. Before any commit, summarize changed files so the user can review in VS Code.
4. When a commit is requested, push to remote in the same flow unless the user explicitly says not to.
5. Do not amend, rebase, or force-push unless explicitly requested.

## File Safety Defaults
1. Never overwrite original user files unless explicitly requested.
2. For edited outputs, write a new file with a clear suffix.
3. Preferred suffix format for `.docx` edits: `_edited_<dow><dd><mon><yyyy>` in lowercase, for example `_edited_mon23feb2026`.
4. Store repo-local edited fixture outputs under `examples/edited/`; keep `examples/canonical/` unmodified.
5. Always report the exact output path and filename at completion.

## Execution Expectations
1. Execute tasks end-to-end autonomously unless blocked.
2. Ask the user questions only when truly blocked by missing intent or required external action.
3. If non-sudo dependency updates are needed, perform them autonomously.
4. If sudo or external credentials are required, stop, explain the blocker, and propose a default path.

## Planning, Decisions, and Logs
1. If implementing from a plan file, mark progress with checkboxes as stages complete.
2. Record non-trivial technical decisions in `docs/decisions.md`.
3. Add dated execution notes to `docs/log/` for substantive work.

## Quality and Verification
1. Run canonical project checks before handoff:
- `uv run pytest`
- any task-specific validation commands
2. For `.docx` work, verify review state and readability after edits:
- inspect comments/revisions
- render document pages when layout fidelity matters
3. Review generated artifacts before sign-off when artifacts are part of the deliverable.

## Current Project Defaults
1. Default tracked-change/comment author label: `Barry Brook` unless overridden by user input.
2. Engine order for edits: OOXML first, UNO fallback second.
3. Keep sidecar artifacts and transcripts available for audit unless the user requests cleanup.
