# Hard-Pattern Canonical Fixtures

These fixtures exercise complex OOXML structures where localized tracked edits can degrade fidelity.

## Files
- `risk_hyperlink.docx`: paragraph contains `w:hyperlink`.
- `risk_field_code.docx`: paragraph contains `w:fldChar` and `w:instrText`.
- `risk_content_control.docx`: paragraph contains `w:sdt`.
- `risk_mixed_runs.docx`: paragraph includes line-break/tab run constructs.

Each `.docx` has a sibling `.sha256` file for fixture integrity checks.

## Expected preflight behavior (strict mode defaults)
- `replace_text_once` targeting the risky paragraph should classify as `unsupported_high_risk`.
- `reason_code` should be `risky_markup_detected`.
- `recommended_engine` should be `uno`.
