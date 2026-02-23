# Canonical DOCX Fixtures

This directory stores stable, repo-local DOCX examples used for manual and automated fidelity testing.

## Current fixtures
- `test_doc.docx`: copied from `/mnt/c/temp/test_doc.docx` on 2026-02-23.
- `test_doc.docx.sha256`: SHA-256 checksum of the canonical fixture.
- `hard_patterns/`: phase-3 fixture corpus for risky OOXML patterns used in preflight routing tests.

## Usage
Use these files as immutable baselines. Write edited outputs to `examples/edited/` using suffixed filenames rather than modifying canonical fixtures in place.
