# 2026-05-08 - GitHub Actions Node 24 Refresh

Updated hosted workflow setup actions in response to GitHub's Node.js 20 deprecation annotation:

- `.github/workflows/ci.yml`
  - `actions/checkout@v4` -> `actions/checkout@v6`
  - `actions/setup-python@v5` -> `actions/setup-python@v6`
  - `astral-sh/setup-uv@v5` -> `astral-sh/setup-uv@v8.1.0`
- `.github/workflows/external-tools.yml`
  - same checkout/setup-python/setup-uv updates
  - `quarto-dev/quarto-actions/setup@v2` -> `quarto-dev/quarto-actions/setup@v2.2.0`

Verified the updated action metadata for checkout/setup-python/setup-uv declares `using: node24`; Quarto setup remains a composite action. Local workflow validation passed with `actionlint`.
