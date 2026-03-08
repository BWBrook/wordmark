"""Internal OOXML review-transform helpers."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from lxml import etree

from wordmark.constants import NSMAP, W_NS
from wordmark.docx_package import DocxPackage
from wordmark.models import OperationResult

DOC_PART = "word/document.xml"


def _w(local: str) -> str:
    return f"{{{W_NS}}}{local}"


def _w_attr(local: str) -> str:
    return f"{{{W_NS}}}{local}"


def _normalize_whitespace_tag(runish: etree._Element) -> None:
    for deleted in runish.xpath(".//w:delText", namespaces=NSMAP):
        deleted.tag = _w("t")


def _author_matches(element: etree._Element, author: str | None) -> bool:
    if author is None:
        return True
    return element.get(_w_attr("author")) == author


def _unwrap(parent: etree._Element, element: etree._Element, *, normalize_deleted: bool) -> None:
    idx = parent.index(element)
    children = list(element)
    for child in children:
        element.remove(child)
        moved = deepcopy(child)
        if normalize_deleted:
            _normalize_whitespace_tag(moved)
        parent.insert(idx, moved)
        idx += 1
    parent.remove(element)


def _transform_revisions(doc_root: etree._Element, *, mode: str, author: str | None) -> dict[str, int]:
    transformed = {"insert": 0, "delete": 0, "move_to": 0, "move_from": 0}
    revision_type_by_tag = {
        _w("ins"): "insert",
        _w("del"): "delete",
        _w("moveTo"): "move_to",
        _w("moveFrom"): "move_from",
    }
    candidates = doc_root.xpath(".//w:ins | .//w:del | .//w:moveTo | .//w:moveFrom", namespaces=NSMAP)
    for rev in candidates:
        if not _author_matches(rev, author):
            continue
        parent = rev.getparent()
        if parent is None:
            continue

        if mode == "accept":
            if rev.tag in {_w("ins"), _w("moveTo")}:
                _unwrap(parent, rev, normalize_deleted=False)
                transformed[revision_type_by_tag[rev.tag]] += 1
            elif rev.tag in {_w("del"), _w("moveFrom")}:
                parent.remove(rev)
                transformed[revision_type_by_tag[rev.tag]] += 1
        else:
            if rev.tag in {_w("ins"), _w("moveTo")}:
                parent.remove(rev)
                transformed[revision_type_by_tag[rev.tag]] += 1
            elif rev.tag == _w("del"):
                _unwrap(parent, rev, normalize_deleted=True)
                transformed[revision_type_by_tag[rev.tag]] += 1
            elif rev.tag == _w("moveFrom"):
                _unwrap(parent, rev, normalize_deleted=False)
                transformed[revision_type_by_tag[rev.tag]] += 1
    return transformed


def _cleanup_orphan_move_ranges(doc_root: etree._Element) -> dict[str, int]:
    remaining_move_to_ids = {
        item.get(_w_attr("id"))
        for item in doc_root.xpath(".//w:moveTo", namespaces=NSMAP)
        if item.get(_w_attr("id")) is not None
    }
    remaining_move_from_ids = {
        item.get(_w_attr("id"))
        for item in doc_root.xpath(".//w:moveFrom", namespaces=NSMAP)
        if item.get(_w_attr("id")) is not None
    }

    removed = {"move_to_range": 0, "move_from_range": 0}
    for node in doc_root.xpath(".//w:moveToRangeStart | .//w:moveToRangeEnd", namespaces=NSMAP):
        range_id = node.get(_w_attr("id"))
        if range_id in remaining_move_to_ids:
            continue
        parent = node.getparent()
        if parent is None:
            continue
        parent.remove(node)
        removed["move_to_range"] += 1

    for node in doc_root.xpath(".//w:moveFromRangeStart | .//w:moveFromRangeEnd", namespaces=NSMAP):
        range_id = node.get(_w_attr("id"))
        if range_id in remaining_move_from_ids:
            continue
        parent = node.getparent()
        if parent is None:
            continue
        parent.remove(node)
        removed["move_from_range"] += 1

    return removed


def review_action(
    path: Path,
    *,
    mode: str,
    author: str | None,
    actor: str,
    dry_run: bool,
) -> OperationResult:
    if mode not in {"accept", "reject"}:
        raise ValueError("mode must be 'accept' or 'reject'")

    pkg = DocxPackage.open(path)
    doc_root = pkg.read_xml(DOC_PART)
    transformed = _transform_revisions(doc_root, mode=mode, author=author)
    cleaned_ranges = _cleanup_orphan_move_ranges(doc_root)
    changed = any(v > 0 for v in transformed.values()) or any(v > 0 for v in cleaned_ranges.values())

    result = OperationResult.now(
        command=f"review {mode}",
        path=path,
        engine="ooxml",
        changed=changed,
        author=actor,
        details={
            "filter_author": author,
            "transformed": transformed,
            "cleaned_move_ranges": cleaned_ranges,
            "dry_run": dry_run,
        },
    )

    if changed and not dry_run:
        pkg.write_xml(DOC_PART, doc_root)
        pkg.save(path)

    return result
