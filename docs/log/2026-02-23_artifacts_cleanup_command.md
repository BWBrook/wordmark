# 2026-02-23 Artifact Cleanup Command Log

## Implemented
- Added new CLI group `artifacts` with command:
  - `wordmark artifacts clean`
- Cleanup supports:
  - preview by default (no deletion without `--apply`)
  - `--older-than-days <N>` time-based filtering
  - `--keep-transcripts` to retain `artifacts/transcripts/*`
  - automatic pruning of empty directories after deletion
- Preserves sentinel files by default:
  - `.gitkeep`
  - `README.md`

## Verification
- Added tests in `tests/test_artifacts_clean.py` covering:
  - preview with age filtering
  - apply mode with transcript retention
  - apply mode pruning empty nested render directories

## Usage
- Preview:
  - `uv run wordmark artifacts clean --json`
- Delete stale files older than 7 days:
  - `uv run wordmark artifacts clean --older-than-days 7 --apply --json`
