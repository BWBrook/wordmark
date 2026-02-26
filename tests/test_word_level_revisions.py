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
    assert [r["text"] for r in review["revisions"] if r["type"] == "insert"] == ["ic"]
    assert [r["text"] for r in review["revisions"] if r["type"] == "delete"] == ["ori"]


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
    assert [r["text"] for r in review["revisions"] if r["type"] == "insert"] == ["ic"]
    assert [r["text"] for r in review["revisions"] if r["type"] == "delete"] == ["ori"]


def test_replace_text_once_tracks_minimal_insertion(tmp_path: Path) -> None:
    doc_path = tmp_path / "minimal-insert.docx"
    doc = Document()
    doc.add_paragraph("Reported that 73% studies were carried out post-2005.")
    doc.save(doc_path)

    ooxml_engine.apply_patch(
        doc_path,
        patch_data={"operations": [{"type": "replace_text_once", "find": "73% studies", "replace": "73% of studies"}]},
        author="Barry Brook",
        track_changes=True,
        dry_run=False,
    )

    review = ooxml_engine.list_review(doc_path)
    inserted = [r["text"] for r in review["revisions"] if r["type"] == "insert"]
    deleted = [r["text"] for r in review["revisions"] if r["type"] == "delete"]
    assert inserted == ["of "]
    assert deleted == []


def test_replace_text_once_tracks_hyphen_delta(tmp_path: Path) -> None:
    doc_path = tmp_path / "hyphen-delta.docx"
    doc = Document()
    doc.add_paragraph("Birds were counted with no bird specific analysis.")
    doc.save(doc_path)

    ooxml_engine.apply_patch(
        doc_path,
        patch_data={"operations": [{"type": "replace_text_once", "find": "bird specific", "replace": "bird-specific"}]},
        author="Barry Brook",
        track_changes=True,
        dry_run=False,
    )

    review = ooxml_engine.list_review(doc_path)
    inserted = [r["text"] for r in review["revisions"] if r["type"] == "insert"]
    deleted = [r["text"] for r in review["revisions"] if r["type"] == "delete"]
    assert inserted == ["-"]
    assert deleted == [" "]


def test_replace_paragraph_text_append_tracks_insert_only(tmp_path: Path) -> None:
    doc_path = tmp_path / "append-text.docx"
    doc = Document()
    doc.add_paragraph("Running title (?)")
    doc.save(doc_path)

    ooxml_engine.apply_patch(
        doc_path,
        patch_data={
            "operations": [
                {
                    "type": "replace_paragraph_text",
                    "paragraph_index": 0,
                    "expected_text": "Running title (?)",
                    "new_text": "Running title (?) Please confirm before submission.",
                }
            ]
        },
        author="Barry Brook",
        track_changes=True,
        dry_run=False,
        allow_paragraph_rewrite_tracked=True,
    )

    review = ooxml_engine.list_review(doc_path)
    inserted = [r["text"] for r in review["revisions"] if r["type"] == "insert"]
    deleted = [r["text"] for r in review["revisions"] if r["type"] == "delete"]
    assert inserted == [" Please confirm before submission."]
    assert deleted == []
