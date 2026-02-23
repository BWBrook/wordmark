"""OOXML-first engine for deterministic DOCX inspection and safe review edits."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lxml import etree

from wordmark.constants import NSMAP, P_NS, W_NS
from wordmark.docx_package import DocxPackage
from wordmark.models import CommentRecord, InspectReport, OperationResult, RevisionRecord

DOC_PART = "word/document.xml"
COMMENTS_PART = "word/comments.xml"
DOC_RELS_PART = "word/_rels/document.xml.rels"
CONTENT_TYPES_PART = "[Content_Types].xml"

COMMENTS_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
COMMENTS_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"


class OoxmlUnsupportedOperation(RuntimeError):
    """Operation must be handled by fallback engine."""


def _w(local: str) -> str:
    return f"{{{W_NS}}}{local}"


def _w_attr(local: str) -> str:
    return f"{{{W_NS}}}{local}"


def _p(local: str) -> str:
    return f"{{{P_NS}}}{local}"


def _ct(local: str) -> str:
    return f"{{{CONTENT_TYPES_NS}}}{local}"


def _now_w3c() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text_of(element: etree._Element) -> str:
    parts = element.xpath(".//w:t/text() | .//w:delText/text()", namespaces=NSMAP)
    return "".join(parts)


def _paragraph_text(paragraph: etree._Element) -> str:
    return "".join(paragraph.xpath(".//w:t/text()", namespaces=NSMAP))


def _normalize_whitespace_tag(runish: etree._Element) -> None:
    for deleted in runish.xpath(".//w:delText", namespaces=NSMAP):
        deleted.tag = _w("t")


def _next_numeric_id(elements: list[etree._Element], attr_qname: str) -> int:
    values: list[int] = []
    for el in elements:
        raw = el.get(attr_qname)
        if raw is None:
            continue
        if str(raw).isdigit():
            values.append(int(raw))
    return (max(values) + 1) if values else 0


def _resolve_anchor(document_root: etree._Element, selector: str) -> tuple[int, etree._Element]:
    paragraphs = document_root.xpath(".//w:body//w:p", namespaces=NSMAP)
    if not paragraphs:
        raise ValueError("No paragraphs found in document")

    if selector.startswith("p:"):
        idx = int(selector.split(":", 1)[1])
        if idx < 0 or idx >= len(paragraphs):
            raise ValueError(f"Paragraph index out of range: {idx}")
        return idx, paragraphs[idx]

    if selector.startswith("text:"):
        snippet = selector.split(":", 1)[1]
        for idx, p in enumerate(paragraphs):
            if snippet in _paragraph_text(p):
                return idx, p
        raise ValueError(f"Snippet not found in document: {snippet!r}")

    raise ValueError("Unsupported selector. Use 'p:<index>' or 'text:<snippet>'")


def _ensure_comments_infrastructure(pkg: DocxPackage) -> etree._Element:
    if pkg.has_part(COMMENTS_PART):
        comments_root = pkg.read_xml(COMMENTS_PART)
    else:
        comments_root = etree.Element(_w("comments"), nsmap={"w": W_NS})

    rels_root = pkg.read_xml(DOC_RELS_PART)
    rel_elems = rels_root.findall(_p("Relationship"))
    existing_rel = None
    for rel in rel_elems:
        if rel.get("Type") == COMMENTS_REL_TYPE:
            existing_rel = rel
            break
    if existing_rel is None:
        next_id = _next_numeric_id(rel_elems, "Id")
        rid = f"rId{next_id if next_id > 0 else len(rel_elems) + 1}"
        rel_el = etree.Element(_p("Relationship"))
        rel_el.set("Id", rid)
        rel_el.set("Type", COMMENTS_REL_TYPE)
        rel_el.set("Target", "comments.xml")
        rels_root.append(rel_el)
        pkg.write_xml(DOC_RELS_PART, rels_root)

    ct_root = pkg.read_xml(CONTENT_TYPES_PART)
    override_exists = False
    for override in ct_root.findall(_ct("Override")):
        if override.get("PartName") == "/word/comments.xml":
            override_exists = True
            break
    if not override_exists:
        override = etree.Element(_ct("Override"))
        override.set("PartName", "/word/comments.xml")
        override.set("ContentType", COMMENTS_CT)
        ct_root.append(override)
        pkg.write_xml(CONTENT_TYPES_PART, ct_root)

    pkg.write_xml(COMMENTS_PART, comments_root)
    return comments_root


def _build_run_with_text(text: str, tag: str = "t") -> etree._Element:
    run = etree.Element(_w("r"))
    text_el = etree.SubElement(run, _w(tag))
    if text != text.strip():
        text_el.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    text_el.text = text
    return run


def _replace_paragraph_content(
    paragraph: etree._Element,
    new_text: str,
    *,
    track_changes: bool,
    author: str,
    revision_id: int,
    timestamp: str,
) -> dict[str, Any]:
    old_text = _paragraph_text(paragraph)
    ppr = paragraph.find(_w("pPr"))
    for child in list(paragraph):
        if ppr is not None and child is ppr:
            continue
        paragraph.remove(child)

    if track_changes:
        if old_text:
            deleted = etree.Element(_w("del"))
            deleted.set(_w_attr("id"), str(revision_id))
            deleted.set(_w_attr("author"), author)
            deleted.set(_w_attr("date"), timestamp)
            deleted.append(_build_run_with_text(old_text, tag="delText"))
            paragraph.append(deleted)
        if new_text:
            inserted = etree.Element(_w("ins"))
            inserted.set(_w_attr("id"), str(revision_id + 1))
            inserted.set(_w_attr("author"), author)
            inserted.set(_w_attr("date"), timestamp)
            inserted.append(_build_run_with_text(new_text, tag="t"))
            paragraph.append(inserted)
    else:
        paragraph.append(_build_run_with_text(new_text, tag="t"))

    return {
        "old_text": old_text,
        "new_text": new_text,
    }


def inspect(path: Path) -> InspectReport:
    pkg = DocxPackage.open(path)
    doc_root = pkg.read_xml(DOC_PART)

    paragraphs = doc_root.xpath(".//w:body//w:p", namespaces=NSMAP)
    paragraph_texts = [_paragraph_text(p) for p in paragraphs]

    comments: list[CommentRecord] = []
    if pkg.has_part(COMMENTS_PART):
        comments_root = pkg.read_xml(COMMENTS_PART)
        for item in comments_root.findall(_w("comment")):
            cid = int(item.get(_w_attr("id"), "0"))
            comments.append(
                CommentRecord(
                    comment_id=cid,
                    author=item.get(_w_attr("author"), ""),
                    initials=item.get(_w_attr("initials"), ""),
                    created_at=item.get(_w_attr("date")),
                    text=_text_of(item),
                    anchor=None,
                )
            )

    revisions: list[RevisionRecord] = []
    for ins in doc_root.findall(".//" + _w("ins")):
        revisions.append(
            RevisionRecord(
                rev_type="ins",
                author=ins.get(_w_attr("author")),
                created_at=ins.get(_w_attr("date")),
                text=_text_of(ins),
            )
        )
    for deleted in doc_root.findall(".//" + _w("del")):
        revisions.append(
            RevisionRecord(
                rev_type="del",
                author=deleted.get(_w_attr("author")),
                created_at=deleted.get(_w_attr("date")),
                text=_text_of(deleted),
            )
        )

    return InspectReport(
        path=path,
        paragraph_count=len(paragraphs),
        text="\n".join(paragraph_texts),
        comments=comments,
        revisions=revisions,
    )


def list_review(path: Path) -> dict[str, Any]:
    report = inspect(path)
    return {
        "path": str(path),
        "paragraph_count": report.paragraph_count,
        "comments": [
            {
                "id": c.comment_id,
                "author": c.author,
                "initials": c.initials,
                "created_at": c.created_at,
                "text": c.text,
            }
            for c in report.comments
        ],
        "revisions": [
            {
                "type": r.rev_type,
                "author": r.author,
                "created_at": r.created_at,
                "text": r.text,
            }
            for r in report.revisions
        ],
    }


def add_comment(
    path: Path,
    *,
    selector: str,
    text: str,
    author: str,
    initials: str,
    dry_run: bool,
) -> OperationResult:
    pkg = DocxPackage.open(path)
    doc_root = pkg.read_xml(DOC_PART)
    comments_root = _ensure_comments_infrastructure(pkg)

    paragraph_index, paragraph = _resolve_anchor(doc_root, selector)

    next_comment_id = _next_numeric_id(comments_root.findall(_w("comment")), _w_attr("id"))
    timestamp = _now_w3c()

    comment_el = etree.Element(_w("comment"))
    comment_el.set(_w_attr("id"), str(next_comment_id))
    comment_el.set(_w_attr("author"), author)
    comment_el.set(_w_attr("initials"), initials)
    comment_el.set(_w_attr("date"), timestamp)

    p_el = etree.SubElement(comment_el, _w("p"))
    p_el.append(_build_run_with_text(text, tag="t"))
    comments_root.append(comment_el)

    marker_start = etree.Element(_w("commentRangeStart"))
    marker_start.set(_w_attr("id"), str(next_comment_id))
    marker_end = etree.Element(_w("commentRangeEnd"))
    marker_end.set(_w_attr("id"), str(next_comment_id))

    ref_run = etree.Element(_w("r"))
    rpr = etree.SubElement(ref_run, _w("rPr"))
    rstyle = etree.SubElement(rpr, _w("rStyle"))
    rstyle.set(_w_attr("val"), "CommentReference")
    cref = etree.SubElement(ref_run, _w("commentReference"))
    cref.set(_w_attr("id"), str(next_comment_id))

    insert_pos = 0
    first = paragraph[0] if len(paragraph) > 0 else None
    if first is not None and first.tag == _w("pPr"):
        insert_pos = 1
    paragraph.insert(insert_pos, marker_start)
    paragraph.append(marker_end)
    paragraph.append(ref_run)

    result = OperationResult.now(
        command="comment add",
        path=path,
        engine="ooxml",
        changed=True,
        author=author,
        details={
            "comment_id": next_comment_id,
            "selector": selector,
            "paragraph_index": paragraph_index,
            "timestamp": timestamp,
            "dry_run": dry_run,
        },
    )

    if not dry_run:
        pkg.write_xml(DOC_PART, doc_root)
        pkg.write_xml(COMMENTS_PART, comments_root)
        pkg.save(path)

    return result


def apply_patch(
    path: Path,
    *,
    patch_data: dict[str, Any],
    author: str,
    track_changes: bool,
    dry_run: bool,
) -> OperationResult:
    operations = patch_data.get("operations")
    if not isinstance(operations, list) or not operations:
        raise ValueError("Patch must include non-empty 'operations' list")

    unsupported = [op for op in operations if op.get("type") not in {"replace_paragraph_text", "replace_text_once"}]
    if unsupported:
        types = sorted({str(op.get("type")) for op in unsupported})
        raise OoxmlUnsupportedOperation(
            f"Unsupported OOXML operations require fallback engine: {', '.join(types)}"
        )

    pkg = DocxPackage.open(path)
    doc_root = pkg.read_xml(DOC_PART)
    paragraphs = doc_root.xpath(".//w:body//w:p", namespaces=NSMAP)
    if not paragraphs:
        raise ValueError("No paragraphs found in document body")

    timestamp = _now_w3c()
    revision_base = _next_numeric_id(
        doc_root.xpath(".//w:ins | .//w:del", namespaces=NSMAP), _w_attr("id")
    )

    op_reports: list[dict[str, Any]] = []
    next_revision_id = revision_base

    for op in operations:
        op_type = str(op.get("type"))

        if op_type == "replace_paragraph_text":
            idx = int(op["paragraph_index"])
            if idx < 0 or idx >= len(paragraphs):
                raise ValueError(f"paragraph_index out of range: {idx}")
            p = paragraphs[idx]
            expected = op.get("expected_text")
            old_text = _paragraph_text(p)
            if expected is not None and old_text != expected:
                raise ValueError(
                    f"Expected paragraph text mismatch at index {idx}: expected={expected!r}, actual={old_text!r}"
                )
            new_text = str(op.get("new_text", ""))
            report = _replace_paragraph_content(
                p,
                new_text,
                track_changes=track_changes,
                author=author,
                revision_id=next_revision_id,
                timestamp=timestamp,
            )
            report.update({"type": op_type, "paragraph_index": idx})
            op_reports.append(report)
            next_revision_id += 2
            continue

        if op_type == "replace_text_once":
            find_text = str(op["find"])
            replacement = str(op["replace"])
            target_idx = None
            for idx, paragraph in enumerate(paragraphs):
                current = _paragraph_text(paragraph)
                if find_text in current:
                    target_idx = idx
                    new_text = current.replace(find_text, replacement, 1)
                    report = _replace_paragraph_content(
                        paragraph,
                        new_text,
                        track_changes=track_changes,
                        author=author,
                        revision_id=next_revision_id,
                        timestamp=timestamp,
                    )
                    report.update(
                        {
                            "type": op_type,
                            "paragraph_index": idx,
                            "find": find_text,
                            "replace": replacement,
                        }
                    )
                    op_reports.append(report)
                    next_revision_id += 2
                    break
            if target_idx is None:
                raise ValueError(f"Text not found for replace_text_once: {find_text!r}")
            continue

    result = OperationResult.now(
        command="edit apply",
        path=path,
        engine="ooxml",
        changed=bool(op_reports),
        author=author,
        details={
            "operations": op_reports,
            "track_changes": track_changes,
            "dry_run": dry_run,
        },
    )

    if not dry_run:
        pkg.write_xml(DOC_PART, doc_root)
        pkg.save(path)

    return result


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
    transformed = {"ins": 0, "del": 0}
    candidates = doc_root.xpath(".//w:ins | .//w:del", namespaces=NSMAP)
    for rev in candidates:
        if not _author_matches(rev, author):
            continue
        parent = rev.getparent()
        if parent is None:
            continue

        if mode == "accept":
            if rev.tag == _w("ins"):
                _unwrap(parent, rev, normalize_deleted=False)
                transformed["ins"] += 1
            elif rev.tag == _w("del"):
                parent.remove(rev)
                transformed["del"] += 1
        else:
            if rev.tag == _w("ins"):
                parent.remove(rev)
                transformed["ins"] += 1
            elif rev.tag == _w("del"):
                _unwrap(parent, rev, normalize_deleted=True)
                transformed["del"] += 1
    return transformed


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
    changed = any(v > 0 for v in transformed.values())

    result = OperationResult.now(
        command=f"review {mode}",
        path=path,
        engine="ooxml",
        changed=changed,
        author=actor,
        details={
            "filter_author": author,
            "transformed": transformed,
            "dry_run": dry_run,
        },
    )

    if changed and not dry_run:
        pkg.write_xml(DOC_PART, doc_root)
        pkg.save(path)

    return result
