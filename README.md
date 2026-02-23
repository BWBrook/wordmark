# wordmark

Wordmark is a Linux-first, CLI-first toolkit for working with `.docx` review workflows outside Microsoft Word.

## Goals
- Open and inspect `.docx` review state (comments and revisions)
- Add comments and apply tracked edits from a CLI or agent
- Accept/reject revisions by author or globally
- Verify fidelity with XML and render-based checks
- Emit machine-readable sidecar artifacts for Git review

## Quickstart

```bash
uv sync --extra dev
uv run wordmark --help
uv run pytest
```

## CLI commands
```bash
uv run wordmark inspect <file.docx> --json
uv run wordmark comment add <file.docx> --anchor "p:1" --text "Review note" --json
uv run wordmark edit apply <file.docx> --patch patch.json --json
uv run wordmark review list <file.docx> --json
uv run wordmark review accept <file.docx> --author "Barry Brook" --json
uv run wordmark review reject <file.docx> --all --json
uv run wordmark verify before.docx after.docx --profile business-docs --json
uv run wordmark render <file.docx> --out tmp/docs/render_out --json
```

## Default config
`wordmark.yaml` defines defaults such as:
- default author (`Barry Brook`)
- default initials (`BB`)
- track-changes default on
- engine preference (`ooxml`, then `uno` fallback)
