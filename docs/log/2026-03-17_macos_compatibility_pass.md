# 2026-03-17 - macOS compatibility pass

## Summary
- cloned and validated `wordmark` on a fresh Apple Silicon macOS host
- confirmed `uv sync --extra dev`, `make lint`, and the pure test lane work on macOS
- installed repo-relevant host tools (`LibreOffice`, `quarto`, `poppler`) for realistic macOS integration checks
- added macOS-aware binary discovery for `soffice` and `quarto`
- kept UNO fallback disabled by default on macOS after proving LibreOffice's embedded Python launcher hangs on a non-interactive `import uno` probe on this machine

## Implementation notes
- `src/wordmark/external_tools.py`
  - added macOS candidate-path resolution for `soffice`, `quarto`, and LibreOffice's embedded Python launcher
  - made `system_uno_available()` return `False` by default on macOS unless `WORDMARK_ENABLE_MACOS_UNO=1` is explicitly set
- `src/wordmark/render.py`
  - switched DOCX-to-PDF conversion to use the resolved `soffice` path instead of assuming it is on `PATH`
- `src/wordmark/manuscript_rounds.py`
  - switched default Quarto build commands to use the resolved `quarto` path instead of assuming it is on `PATH`
- `src/wordmark/uno_engine.py`
  - added an explicit guard so UNO fallback does not silently hang on macOS by default
- `README.md`
  - documented the current macOS bootstrap path and clarified that UNO is still experimental there

## Verification
- `uv sync --extra dev`
- `make lint`
- `make test-pure`
- `make test-external`
- `make test`
