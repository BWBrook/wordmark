from __future__ import annotations

import json
from pathlib import Path
import subprocess

from docx import Document
import pytest

from wordmark import ooxml_engine, uno_engine


def _has_system_uno() -> bool:
    proc = subprocess.run(
        ["/usr/bin/python3", "-c", "import uno"],
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


@pytest.mark.skipif(not _has_system_uno(), reason="System python UNO bindings unavailable")
def test_uno_fallback_replace_text_global(tmp_path: Path) -> None:
    doc_path = tmp_path / "uno-test.docx"
    doc = Document()
    doc.add_paragraph("Hello UNO world")
    doc.save(doc_path)

    patch = {
        "operations": [
            {
                "type": "replace_text_global",
                "find": "UNO",
                "replace": "Fallback",
            }
        ]
    }

    with pytest.raises(ooxml_engine.OoxmlUnsupportedOperation):
        ooxml_engine.apply_patch(
            doc_path,
            patch_data=patch,
            author="Barry Brook",
            track_changes=True,
            dry_run=False,
        )

    outcome = uno_engine.apply_patch(
        doc_path,
        patch_data=patch,
        author="Barry Brook",
        track_changes=True,
        dry_run=False,
        fallback_reason="integration test",
    )
    assert outcome.engine == "uno"
    assert outcome.changed

    report = ooxml_engine.inspect(doc_path)
    assert "Fallback" in report.text


@pytest.mark.skipif(not _has_system_uno(), reason="System python UNO bindings unavailable")
def test_uno_fallback_replace_text_once_occurrence_and_author(tmp_path: Path) -> None:
    doc_path = tmp_path / "uno-once.docx"
    doc = Document()
    doc.add_paragraph("Draft sentence in first paragraph.")
    doc.add_paragraph("Draft sentence in second paragraph.")
    doc.save(doc_path)

    patch = {
        "operations": [
            {
                "type": "replace_text_once",
                "find": "Draft",
                "replace": "Final",
                "occurrence": 2,
            }
        ]
    }

    outcome = uno_engine.apply_patch(
        doc_path,
        patch_data=patch,
        author="Barry Brook",
        track_changes=True,
        dry_run=False,
        fallback_reason="integration test replace_text_once",
    )
    assert outcome.engine == "uno"
    assert outcome.changed
    assert outcome.details["uno"]["operation_results"][0]["strategy_used"] == "replace_text_once"

    report = ooxml_engine.inspect(doc_path)
    lines = report.text.splitlines()
    assert "Draft sentence in first paragraph." in lines
    assert "Final sentence in second paragraph." in lines
    assert any(rev.author == "Barry Brook" for rev in report.revisions)
