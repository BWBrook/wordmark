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
