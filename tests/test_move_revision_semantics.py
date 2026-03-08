from __future__ import annotations

from collections import Counter
from pathlib import Path

from docx import Document
from lxml import etree

from wordmark.constants import NSMAP, W_NS
from wordmark.docx_package import DocxPackage
from wordmark import ooxml_engine, uno_engine

DOC_PART = "word/document.xml"


def _w(local: str) -> str:
    return f"{{{W_NS}}}{local}"


def _build_run(text: str) -> etree._Element:
    run = etree.Element(_w("r"))
    text_node = etree.SubElement(run, _w("t"))
    text_node.text = text
    return run


def _make_move_fixture(path: Path, *, move_to_author: str = "Unknown Author", move_from_author: str = "Unknown Author") -> None:
    doc = Document()
    doc.add_paragraph("placeholder")
    doc.save(path)

    pkg = DocxPackage.open(path)
    root = pkg.read_xml(DOC_PART)
    paragraph = root.xpath(".//w:body//w:p", namespaces=NSMAP)[0]
    paragraph_props = paragraph.find(_w("pPr"))

    for child in list(paragraph):
        if paragraph_props is not None and child is paragraph_props:
            continue
        paragraph.remove(child)

    paragraph.append(_build_run("prefix "))

    move_to_range_start = etree.Element(_w("moveToRangeStart"))
    move_to_range_start.set(_w("id"), "96")
    paragraph.append(move_to_range_start)

    move_to = etree.Element(_w("moveTo"))
    move_to.set(_w("id"), "96")
    move_to.set(_w("author"), move_to_author)
    move_to.set(_w("date"), "2026-02-26T14:08:02Z")
    move_to.append(_build_run("destination text"))
    paragraph.append(move_to)

    move_to_range_end = etree.Element(_w("moveToRangeEnd"))
    move_to_range_end.set(_w("id"), "96")
    paragraph.append(move_to_range_end)

    paragraph.append(_build_run(" / "))

    move_from_range_start = etree.Element(_w("moveFromRangeStart"))
    move_from_range_start.set(_w("id"), "97")
    paragraph.append(move_from_range_start)

    move_from = etree.Element(_w("moveFrom"))
    move_from.set(_w("id"), "97")
    move_from.set(_w("author"), move_from_author)
    move_from.set(_w("date"), "2026-02-26T14:08:02Z")
    move_from.append(_build_run("source text"))
    paragraph.append(move_from)

    move_from_range_end = etree.Element(_w("moveFromRangeEnd"))
    move_from_range_end.set(_w("id"), "97")
    paragraph.append(move_from_range_end)

    paragraph.append(_build_run(" suffix"))

    pkg.write_xml(DOC_PART, root)
    pkg.save(path)


def test_inspect_review_visible_hides_move_from_text(tmp_path: Path) -> None:
    doc_path = tmp_path / "move-inspect.docx"
    _make_move_fixture(doc_path)

    visible = ooxml_engine.inspect(doc_path, text_mode="review-visible")
    raw = ooxml_engine.inspect(doc_path, text_mode="raw")

    assert visible.text_mode == "review-visible"
    assert "destination text" in visible.text_value
    assert "source text" not in visible.text_value

    assert raw.text_mode == "raw"
    assert "destination text" in raw.text_value
    assert "source text" in raw.text_value


def test_list_review_reports_move_revision_types_and_ids(tmp_path: Path) -> None:
    doc_path = tmp_path / "move-review-list.docx"
    _make_move_fixture(doc_path)

    review = ooxml_engine.list_review(doc_path)
    revision_types = [item["type"] for item in review["revisions"]]
    assert "move_to" in revision_types
    assert "move_from" in revision_types
    assert any(item["revision_id"] == "96" for item in review["revisions"])
    assert any(item["revision_id"] == "97" for item in review["revisions"])


def test_review_accept_handles_move_revisions_and_cleans_markers(tmp_path: Path) -> None:
    doc_path = tmp_path / "move-accept.docx"
    _make_move_fixture(doc_path, move_to_author="Barry Brook", move_from_author="Barry Brook")

    result = ooxml_engine.review_action(
        doc_path,
        mode="accept",
        author="Barry Brook",
        actor="Barry Brook",
        dry_run=False,
    )
    assert result.changed is True
    assert result.details["transformed"]["move_to"] == 1
    assert result.details["transformed"]["move_from"] == 1

    report = ooxml_engine.inspect(doc_path, text_mode="review-visible")
    assert "destination text" in report.text_value
    assert "source text" not in report.text_value

    pkg = DocxPackage.open(doc_path)
    root = pkg.read_xml(DOC_PART)
    assert not root.xpath(".//w:moveToRangeStart | .//w:moveToRangeEnd", namespaces=NSMAP)
    assert not root.xpath(".//w:moveFromRangeStart | .//w:moveFromRangeEnd", namespaces=NSMAP)


def test_review_reject_handles_move_revisions_and_cleans_markers(tmp_path: Path) -> None:
    doc_path = tmp_path / "move-reject.docx"
    _make_move_fixture(doc_path, move_to_author="Barry Brook", move_from_author="Barry Brook")

    result = ooxml_engine.review_action(
        doc_path,
        mode="reject",
        author="Barry Brook",
        actor="Barry Brook",
        dry_run=False,
    )
    assert result.changed is True
    assert result.details["transformed"]["move_to"] == 1
    assert result.details["transformed"]["move_from"] == 1

    report = ooxml_engine.inspect(doc_path, text_mode="review-visible")
    assert "destination text" not in report.text_value
    assert "source text" in report.text_value

    pkg = DocxPackage.open(doc_path)
    root = pkg.read_xml(DOC_PART)
    assert not root.xpath(".//w:moveToRangeStart | .//w:moveToRangeEnd", namespaces=NSMAP)
    assert not root.xpath(".//w:moveFromRangeStart | .//w:moveFromRangeEnd", namespaces=NSMAP)


def test_review_action_respects_author_filter_for_move_revisions(tmp_path: Path) -> None:
    doc_path = tmp_path / "move-author-filter.docx"
    _make_move_fixture(doc_path, move_to_author="Barry Brook", move_from_author="Barry Brook")

    result = ooxml_engine.review_action(
        doc_path,
        mode="accept",
        author="Someone Else",
        actor="Barry Brook",
        dry_run=False,
    )
    assert result.changed is False
    assert result.details["transformed"] == {"insert": 0, "delete": 0, "move_to": 0, "move_from": 0}

    review = ooxml_engine.list_review(doc_path)
    revision_types = [item["type"] for item in review["revisions"]]
    assert "move_to" in revision_types
    assert "move_from" in revision_types


def test_uno_normalization_covers_move_revisions(tmp_path: Path) -> None:
    doc_path = tmp_path / "uno-move-normalize.docx"
    _make_move_fixture(doc_path, move_to_author="Unknown Author", move_from_author="Unknown Author")

    details = uno_engine._normalize_unknown_revision_authors(  # noqa: SLF001 - tested intentionally
        doc_path,
        requested_author="Barry Brook",
        before_counter=Counter(),
    )
    assert details["normalized"] is True
    assert details["normalized_unknown_authors"] == 2
    assert details["normalized_unknown_by_type"]["move_to"] == 1
    assert details["normalized_unknown_by_type"]["move_from"] == 1
    assert details["remaining_unknown_authors"] == 0

    pkg = DocxPackage.open(doc_path)
    root = pkg.read_xml(DOC_PART)
    unknown = root.xpath(".//w:*[@w:author='Unknown Author']", namespaces=NSMAP)
    assert unknown == []
