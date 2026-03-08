from __future__ import annotations

import json
from pathlib import Path
import subprocess

from docx import Document
import pytest

from wordmark.external_tools import system_uno_available
from wordmark import ooxml_engine, uno_engine


pytestmark = [
    pytest.mark.external_tools,
    pytest.mark.uno,
    pytest.mark.skipif(not system_uno_available(), reason="System python UNO bindings unavailable"),
]

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
    assert "Fallback" in report.text_value


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
    lines = report.text_value.splitlines()
    assert "Draft sentence in first paragraph." in lines
    assert "Final sentence in second paragraph." in lines
    assert any(rev.author == "Barry Brook" for rev in report.revisions)


def test_parallel_uno_writes_are_serialized_by_lock(tmp_path: Path) -> None:
    doc_path = tmp_path / "uno-lock.docx"
    doc = Document()
    doc.add_paragraph("alpha beta gamma")
    doc.add_paragraph("delta epsilon zeta")
    doc.save(doc_path)

    patch1 = tmp_path / "patch1.json"
    patch1.write_text(
        json.dumps({"operations": [{"type": "replace_text_global", "find": "alpha", "replace": "ALPHA"}]}),
        encoding="utf-8",
    )
    patch2 = tmp_path / "patch2.json"
    patch2.write_text(
        json.dumps({"operations": [{"type": "replace_text_global", "find": "delta", "replace": "DELTA"}]}),
        encoding="utf-8",
    )

    cmd1 = ["uv", "run", "wordmark", "edit", "apply", str(doc_path), "--patch", str(patch1), "--json"]
    cmd2 = ["uv", "run", "wordmark", "edit", "apply", str(doc_path), "--patch", str(patch2), "--json"]
    p1 = subprocess.Popen(cmd1, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    p2 = subprocess.Popen(cmd2, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out1, err1 = p1.communicate(timeout=120)
    out2, err2 = p2.communicate(timeout=120)

    assert p1.returncode == 0, err1
    assert p2.returncode == 0, err2

    payload1 = json.loads(out1)
    payload2 = json.loads(out2)
    assert payload1["operation"]["engine"] == "uno"
    assert payload2["operation"]["engine"] == "uno"

    report = ooxml_engine.inspect(doc_path)
    merged = report.text_value
    assert "ALPHA beta gamma" in merged
    assert "DELTA epsilon zeta" in merged


def test_uno_replace_span_once_inserts_without_deleting_suffix(tmp_path: Path) -> None:
    doc_path = tmp_path / "uno-span-insert.docx"
    doc = Document()
    doc.add_paragraph("growth continued without saturation.")
    doc.save(doc_path)

    patch = {
        "operations": [
            {
                "type": "replace_span_once",
                "find": "growth continued without saturation",
                "occurrence": 1,
                "span_start": len("growth continued without "),
                "span_length": 0,
                "replacement": "clear ",
            }
        ]
    }

    outcome = uno_engine.apply_patch(
        doc_path,
        patch_data=patch,
        author="Barry Brook",
        track_changes=True,
        dry_run=False,
        fallback_reason="integration test replace_span_once insert",
    )
    assert outcome.engine == "uno"
    assert outcome.changed

    review = ooxml_engine.list_review(doc_path)
    inserted = [item["text"] for item in review["revisions"] if item["type"] == "insert"]
    deleted = [item["text"] for item in review["revisions"] if item["type"] == "delete"]
    assert "clear " in inserted
    assert "saturation" not in deleted


def test_uno_replace_span_once_deletes_hyphen_only(tmp_path: Path) -> None:
    doc_path = tmp_path / "uno-span-delete.docx"
    doc = Document()
    doc.add_paragraph("under-representation remains common.")
    doc.save(doc_path)

    patch = {
        "operations": [
            {
                "type": "replace_span_once",
                "find": "under-representation",
                "occurrence": 1,
                "span_start": len("under"),
                "span_length": 1,
                "replacement": "",
            }
        ]
    }

    outcome = uno_engine.apply_patch(
        doc_path,
        patch_data=patch,
        author="Barry Brook",
        track_changes=True,
        dry_run=False,
        fallback_reason="integration test replace_span_once delete",
    )
    assert outcome.engine == "uno"
    assert outcome.changed

    review = ooxml_engine.list_review(doc_path)
    inserted = [item["text"] for item in review["revisions"] if item["type"] == "insert"]
    deleted = [item["text"] for item in review["revisions"] if item["type"] == "delete"]
    assert inserted == []
    assert deleted == ["-"]
