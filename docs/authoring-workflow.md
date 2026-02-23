# Authoring Workflow (Human + Agent)

## Setup
```bash
uv sync --extra dev
uv run wordmark --help
```

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
Supported anchors:
- `p:<index>` paragraph index
- `text:<snippet>` first paragraph containing snippet

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
      "replace": "Final"
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

## 5) Fidelity verification
```bash
uv run wordmark verify docs/before.docx docs/after.docx --profile business-docs --json
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
