from __future__ import annotations

from pathlib import Path

from docx import Document

from wordmark import ooxml_engine


def test_replace_text_once_tracks_only_word_when_in_single_run(tmp_path: Path) -> None:
    doc_path = tmp_path / "single-run.docx"
    doc = Document()
    doc.add_paragraph("Week 1 practorial session.")
    doc.save(doc_path)

    result = ooxml_engine.apply_patch(
        doc_path,
        patch_data={"operations": [{"type": "replace_text_once", "find": "practorial", "replace": "practical"}]},
        author="Barry Brook",
        track_changes=True,
        dry_run=False,
    )

    op = result.details["operations"][0]
    assert op["strategy"] == "localized_run"
    assert op["old_text"] == "practorial"
    assert op["new_text"] == "practical"

    review = ooxml_engine.list_review(doc_path)
    assert [r["text"] for r in review["revisions"] if r["type"] == "ins"] == ["practical"]
    assert [r["text"] for r in review["revisions"] if r["type"] == "del"] == ["practorial"]


def test_replace_text_once_falls_back_when_match_spans_runs(tmp_path: Path) -> None:
    doc_path = tmp_path / "multi-run.docx"
    doc = Document()
    p = doc.add_paragraph()
    p.add_run("Week 1 ")
    p.add_run("prac")
    p.add_run("torial")
    p.add_run(" session.")
    doc.save(doc_path)

    result = ooxml_engine.apply_patch(
        doc_path,
        patch_data={"operations": [{"type": "replace_text_once", "find": "practorial", "replace": "practical"}]},
        author="Barry Brook",
        track_changes=True,
        dry_run=False,
    )

    op = result.details["operations"][0]
    assert op["strategy"] == "localized_multi_run"
    assert op["old_text"] == "practorial"
    assert op["new_text"] == "practical"

    review = ooxml_engine.list_review(doc_path)
    assert [r["text"] for r in review["revisions"] if r["type"] == "ins"] == ["practical"]
    assert [r["text"] for r in review["revisions"] if r["type"] == "del"] == ["practorial"]
