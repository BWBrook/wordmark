# Authoring Workflow (Human + Agent)

## Setup
```bash
uv sync --extra dev
uv run wordmark --help
```

Validation lanes:
```bash
uv run pytest
make test-pure
make test-pure-cov
make test-external
make lint
```

## Fixture layout
- Keep immutable baselines in `examples/canonical/`.
- Write generated edits to `examples/edited/`.

## Mutation safety
- Never run mutating commands directly on your only copy of a document. Create an output copy with a dated suffix first.
- Mutating commands (`comment add`, `edit apply`, `review accept`, `review reject`) acquire an exclusive per-document lock at `<docx>.wordmark.lock`.
- Concurrent operations against the same `.docx` are queued by the lock, avoiding UNO write collisions.

## 1) Inspect a document
```bash
uv run wordmark inspect docs/input.docx --json
```
Default inspection text mode is reviewer-visible (`review-visible`), which hides deleted and moved-from text:
```bash
uv run wordmark inspect docs/input.docx --text-mode review-visible --json
```
Use raw extraction for diagnostics:
```bash
uv run wordmark inspect docs/input.docx --text-mode raw --json
```
JSON outputs for `inspect`, `review list`, and `verify` include `schema_version: 2`.
`inspect` report payload includes:
- `text_mode`
- `text_value`
- revision entries with `type` in `{insert, delete, move_to, move_from}`.

## 2) Add comments
```bash
uv run wordmark comment add docs/input.docx \
  --anchor "p:3" \
  --text "Please tighten this paragraph." \
  --author "Barry Brook" \
  --initials "BB" \
  --json
```
Or use paragraph+context anchor JSON:
```bash
uv run wordmark comment add docs/input.docx \
  --anchor-json '{"expected_text":"reviewword","context_before":"Section B","occurrence":1}' \
  --text "Please tighten this paragraph." \
  --json
```
Supported anchors:
- `p:<index>` paragraph index
- `text:<snippet>` first paragraph containing snippet
- anchor JSON object fields:
  - `paragraph_index` (optional)
  - `expected_text` (optional)
  - `context_before` (optional)
  - `context_after` (optional)
  - `occurrence` (optional, 1-based)

## 3) Apply tracked edits via patch JSON
Example patch (`patch.json`):
```json
{
  "operations": [
    {
      "type": "replace_paragraph_text",
      "paragraph_index": 2,
      "new_text": "Updated paragraph text."
    },
    {
      "type": "replace_text_once",
      "find": "Draft",
      "replace": "Final",
      "anchor": {
        "expected_text": "Draft appears",
        "context_before": "Divider Context"
      }
    }
  ]
}
```

Run:
```bash
uv run wordmark edit apply docs/input.docx --patch patch.json --json
```

Patch operations currently supported by OOXML engine:
- `replace_paragraph_text` (attempts localized full-string replacement first; only falls back to tracked paragraph rewrite when policy allows).
- `replace_text_once` (preferred for precise edits; emits minimal tracked `w:del`/`w:ins` deltas when safe).

Fallback operation currently supported by UNO engine:
- `replace_text_global`
- `replace_text_once`
- `replace_paragraph_text` (matched by `expected_text`)

## Edit policy and preflight
Preflight strategy selection without mutation:
```bash
uv run wordmark edit apply docs/input.docx --patch patch.json --preflight-only --json
```
Preflight JSON includes `reason_code`, `reason_detail`, `detected_patterns`, `recommended_engine`, and `recommended_strategy`.
UNO fallback JSON includes per-operation diagnostics (`status`, `replaced_count`, `strategy_used`, `author_binding_status`) and may include:
- `uno_retry` metadata if low-hit global operations are retried as targeted single replacements
- `author_binding_postprocess` metadata when newly introduced `Unknown Author` revisions are normalized to the requested author
- `uno_precision_rewrite` metadata when fallback `replace_text_once` operations are narrowed to minimal spans before UNO apply
- `interop_drift` metadata when cross-reference families (Figure/Table/Eq/Appendix) shift between before/after text snapshots
- `risk_summary` metadata with concise fallback and drift risk signals for downstream triage

Drift/risk controls:
```bash
# default: drift check + risk summary on
uv run wordmark edit apply docs/input.docx --patch patch.json --json

# disable drift diagnostics
uv run wordmark edit apply docs/input.docx --patch patch.json --no-drift-check --json

# set warning sensitivity
uv run wordmark edit apply docs/input.docx --patch patch.json --drift-warning-threshold high --json

# disable risk summary block
uv run wordmark edit apply docs/input.docx --patch patch.json --no-emit-risk-summary --json
```

Policy controls:
```bash
uv run wordmark edit apply docs/input.docx --patch patch.json --fidelity-mode strict --json
uv run wordmark edit apply docs/input.docx --patch patch.json --fidelity-mode aggressive --json
uv run wordmark edit apply docs/input.docx --patch patch.json --on-unsupported uno --on-uno-fail comment --json
```

Defaults in strict mode:
- no tracked paragraph rewrite fallback
- OOXML strict -> UNO -> comment-only fallback
- localized replacements emit minimal tracked deltas (for example insert-only and hyphen-only changes remain narrow)

Hard-pattern fixtures for regression testing are in `examples/canonical/hard_patterns/`.

## 4) Review operations
List:
```bash
uv run wordmark review list docs/input.docx --json
```
Or inspect raw revision-adjacent text extraction:
```bash
uv run wordmark review list docs/input.docx --text-mode raw --json
```

Accept/reject revisions:
```bash
uv run wordmark review accept docs/input.docx --author "Barry Brook" --json
uv run wordmark review reject docs/input.docx --all --json
```
Move revisions are handled explicitly:
- accept: keep `move_to`, remove `move_from`
- reject: remove `move_to`, keep `move_from`

Prepare Word desktop compare/combine handoff:
```bash
uv run wordmark review prepare-merge docs/before.docx docs/after.docx --json
```
See `docs/release_gate_word_desktop.md` for the manual release checklist.

## 5) Fidelity verification
```bash
uv run wordmark verify docs/before.docx docs/after.docx --profile business-docs --json
uv run wordmark verify docs/before.docx docs/after.docx --profile review-edit --json
```
`verify` runs:
- OOXML integrity checks
- comment-reference consistency checks
- compatibility namespace integrity checks (`compatibility_namespace_integrity`)
- revision delta summary (`insert`, `delete`, `move_to`, `move_from`, `total`)
- render diff checks with per-page artifacts

If `compatibility_namespace_integrity.ok` is false, treat the output as invalid for Word handoff even if comments/revisions appear present.

## 6) Visual rendering
```bash
uv run wordmark render docs/input.docx --out tmp/docs/input_render --json
```

## Dry-run and auditability
Mutating commands support `--dry-run` and always append operation metadata to:
- `artifacts/transcripts/operations.jsonl`

Lock files are removed automatically after command completion. If a stale lock filename remains after an interrupted run, it is safe to remove once no wordmark process is active for that document.

## Artifact cleanup
Preview cleanup candidates:
```bash
uv run wordmark artifacts clean --json
```

Delete stale sidecars older than 14 days:
```bash
uv run wordmark artifacts clean --older-than-days 14 --apply --json
```

Delete stale sidecars while retaining transcript history:
```bash
uv run wordmark artifacts clean --older-than-days 14 --keep-transcripts --apply --json
```

## 7) Manuscript (Markdown/Quarto) collaboration rounds
Use this flow when canonical writing is in `.md`/`.qmd`, but reviewers may work via PR comments, markdown notes, or DOCX review files.

Prepare a round:
```bash
uv run wordmark manuscript prepare chapter.qmd --formats docx,pdf --json
```

Collect feedback into one bundle:
```bash
uv run wordmark manuscript collect artifacts/manuscript_rounds/<round_id> \
  --from-pr 123 \
  --notes /path/to/feedback.md \
  --docx-reviewed /path/to/chapter_reviewed.docx \
  --json
```

Synthesize patch proposals (non-mutating):
```bash
uv run wordmark manuscript synthesize artifacts/manuscript_rounds/<round_id> \
  --source chapter.qmd \
  --export-critic \
  --json
```

Apply deterministic safe edits only when explicitly approved:
```bash
uv run wordmark manuscript synthesize artifacts/manuscript_rounds/<round_id> \
  --source chapter.qmd \
  --apply-safe \
  --json
```

Check round status:
```bash
uv run wordmark manuscript status artifacts/manuscript_rounds/<round_id> --json
```

Key defaults:
- `.md/.qmd` remains canonical source.
- feedback is preserved in sidecar artifacts (`feedback.bundle.json`, timeline/report files).
- DOCX is an optional review bridge artifact, not a source-of-truth replacement.
