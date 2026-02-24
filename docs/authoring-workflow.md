# Authoring Workflow (Human + Agent)

## Setup
```bash
uv sync --extra dev
uv run wordmark --help
```

## Fixture layout
- Keep immutable baselines in `examples/canonical/`.
- Write generated edits to `examples/edited/`.

## 1) Inspect a document
```bash
uv run wordmark inspect docs/input.docx --json
```
This emits paragraph/comment/revision state and (by default) writes sidecar review artifacts.

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
- `replace_paragraph_text`
- `replace_text_once`

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
UNO fallback JSON includes per-operation diagnostics (`status`, `replaced_count`, `strategy_used`) and may include `uno_retry` metadata if low-hit global operations are retried as targeted single replacements.

Policy controls:
```bash
uv run wordmark edit apply docs/input.docx --patch patch.json --fidelity-mode strict --json
uv run wordmark edit apply docs/input.docx --patch patch.json --fidelity-mode aggressive --json
uv run wordmark edit apply docs/input.docx --patch patch.json --on-unsupported uno --on-uno-fail comment --json
```

Defaults in strict mode:
- no tracked paragraph rewrite fallback
- OOXML strict -> UNO -> comment-only fallback

Hard-pattern fixtures for regression testing are in `examples/canonical/hard_patterns/`.

## 4) Review operations
List:
```bash
uv run wordmark review list docs/input.docx --json
```

Accept/reject revisions:
```bash
uv run wordmark review accept docs/input.docx --author "Barry Brook" --json
uv run wordmark review reject docs/input.docx --all --json
```

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
- revision delta summary
- render diff checks with per-page artifacts

## 6) Visual rendering
```bash
uv run wordmark render docs/input.docx --out tmp/docs/input_render --json
```

## Dry-run and auditability
Mutating commands support `--dry-run` and always append operation metadata to:
- `artifacts/transcripts/operations.jsonl`

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
