from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from wordmark import ooxml_engine


FIXTURES_DIR = Path("examples/canonical/hard_patterns")
FIXTURE_TOKENS = {
    "risk_hyperlink.docx": "linkword",
    "risk_field_code.docx": "fieldword",
    "risk_content_control.docx": "sdtword",
    "risk_mixed_runs.docx": "mixword",
}


def _read_expected_hash(sha_path: Path) -> tuple[str, str]:
    line = sha_path.read_text(encoding="utf-8").strip()
    digest, filename = line.split("  ", 1)
    return digest, filename


def test_hard_pattern_fixture_checksums_match() -> None:
    assert FIXTURES_DIR.exists()
    for name in sorted(FIXTURE_TOKENS):
        docx_path = FIXTURES_DIR / name
        sha_path = FIXTURES_DIR / f"{name}.sha256"
        assert docx_path.exists()
        assert sha_path.exists()

        expected_hash, expected_name = _read_expected_hash(sha_path)
        actual_hash = hashlib.sha256(docx_path.read_bytes()).hexdigest()
        assert expected_name == name
        assert actual_hash == expected_hash


@pytest.mark.parametrize("fixture_name,token", sorted(FIXTURE_TOKENS.items()))
def test_preflight_flags_hard_patterns_as_unsupported_high_risk(fixture_name: str, token: str) -> None:
    path = FIXTURES_DIR / fixture_name
    report = ooxml_engine.preflight_patch(
        path,
        patch_data={
            "operations": [
                {
                    "type": "replace_text_once",
                    "find": token,
                    "replace": "replacement",
                }
            ]
        },
        track_changes=True,
        allow_paragraph_rewrite_tracked=False,
    )
    op = report["operations"][0]
    assert op["classification"] == "unsupported_high_risk"
    assert op["reason_code"] == "risky_markup_detected"
    assert op["recommended_engine"] == "uno"
    assert op["detected_patterns"]
