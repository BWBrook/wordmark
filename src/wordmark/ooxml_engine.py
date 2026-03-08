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
from wordmark import ooxml_anchor
from wordmark import ooxml_replace
from wordmark import ooxml_review

DOC_PART = "word/document.xml"
COMMENTS_PART = "word/comments.xml"
DOC_RELS_PART = "word/_rels/document.xml.rels"
CONTENT_TYPES_PART = "[Content_Types].xml"

COMMENTS_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
COMMENTS_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"
TEXT_MODE_REVIEW_VISIBLE = "review-visible"
TEXT_MODE_RAW = "raw"
TEXT_MODES = {TEXT_MODE_REVIEW_VISIBLE, TEXT_MODE_RAW}


class OoxmlUnsupportedOperation(RuntimeError):
    """Operation must be handled by fallback engine."""


AnchorResolutionError = ooxml_anchor.AnchorResolutionError


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


def _paragraph_text(paragraph: etree._Element, *, text_mode: str = TEXT_MODE_REVIEW_VISIBLE) -> str:
    if text_mode not in TEXT_MODES:
        raise ValueError(f"Unsupported text_mode={text_mode!r}; expected one of {sorted(TEXT_MODES)}")

    nodes = paragraph.xpath(".//w:t | .//w:delText", namespaces=NSMAP)
    parts: list[str] = []
    for node in nodes:
        if text_mode == TEXT_MODE_REVIEW_VISIBLE:
            hidden = any(ancestor.tag in {_w("del"), _w("moveFrom")} for ancestor in node.iterancestors())
            if hidden:
                continue
        parts.append(node.text or "")

    return "".join(parts)


def _document_text(document_root: etree._Element, *, text_mode: str) -> str:
    paragraphs = document_root.xpath(".//w:body//w:p", namespaces=NSMAP)
    return "\n".join(_paragraph_text(paragraph, text_mode=text_mode) for paragraph in paragraphs)


def _next_numeric_id(elements: list[etree._Element], attr_qname: str) -> int:
    values: list[int] = []
    for el in elements:
        raw = el.get(attr_qname)
        if raw is None:
            continue
        if str(raw).isdigit():
            values.append(int(raw))
    return (max(values) + 1) if values else 0


def _body_paragraphs(document_root: etree._Element) -> list[etree._Element]:
    return document_root.xpath(".//w:body//w:p", namespaces=NSMAP)


def _resolve_anchor_spec(
    document_root: etree._Element,
    *,
    selector: str | None = None,
    anchor: dict[str, Any] | None = None,
    fallback_text: str | None = None,
) -> tuple[int, etree._Element, dict[str, Any]]:
    return ooxml_anchor.resolve_anchor_spec(
        document_root,
        paragraph_text_fn=lambda paragraph: _paragraph_text(paragraph, text_mode=TEXT_MODE_REVIEW_VISIBLE),
        selector=selector,
        anchor=anchor,
        fallback_text=fallback_text,
    )


def _anchor_from_operation(op: dict[str, Any]) -> dict[str, Any] | None:
    return ooxml_anchor.anchor_from_operation(op)


def _replace_text_once_localized(
    paragraph: etree._Element,
    *,
    find_text: str,
    replacement: str,
    track_changes: bool,
    author: str,
    revision_id: int,
    timestamp: str,
) -> dict[str, Any] | None:
    return ooxml_replace.replace_text_once_localized(
        paragraph,
        paragraph_text_fn=lambda current_paragraph: _paragraph_text(current_paragraph, text_mode=TEXT_MODE_REVIEW_VISIBLE),
        find_text=find_text,
        replacement=replacement,
        track_changes=track_changes,
        author=author,
        revision_id=revision_id,
        timestamp=timestamp,
    )


def _text_run_spans_multiple_runs(paragraph: etree._Element, find_text: str) -> bool:
    return ooxml_replace.text_run_spans_multiple_runs(paragraph, find_text)


def _replace_paragraph_content(
    paragraph: etree._Element,
    new_text: str,
    *,
    track_changes: bool,
    author: str,
    revision_id: int,
    timestamp: str,
) -> dict[str, Any]:
    return ooxml_replace.replace_paragraph_content(
        paragraph,
        new_text,
        paragraph_text_fn=lambda current_paragraph: _paragraph_text(current_paragraph, text_mode=TEXT_MODE_REVIEW_VISIBLE),
        track_changes=track_changes,
        author=author,
        revision_id=revision_id,
        timestamp=timestamp,
    )


def _build_run_with_text(text: str, tag: str = "t") -> etree._Element:
    return ooxml_replace._build_run_with_text(text, tag=tag)


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


def _paragraph_risky_patterns(paragraph: etree._Element) -> list[str]:
    risky_map = {
        _w("hyperlink"): "hyperlink",
        _w("instrText"): "instrText",
        _w("fldChar"): "fldChar",
        _w("drawing"): "drawing",
        _w("object"): "object",
        _w("pict"): "pict",
        _w("sdt"): "sdt",
        _w("smartTag"): "smartTag",
        _w("tab"): "tab",
        _w("br"): "br",
        _w("cr"): "cr",
        _w("sym"): "sym",
        _w("footnoteReference"): "footnoteReference",
        _w("endnoteReference"): "endnoteReference",
    }
    found: set[str] = set()
    for el in paragraph.iter():
        pattern = risky_map.get(el.tag)
        if pattern:
            found.add(pattern)
    return sorted(found)


def _paragraph_has_risky_markup(paragraph: etree._Element) -> bool:
    return bool(_paragraph_risky_patterns(paragraph))


def inspect(path: Path, *, text_mode: str = TEXT_MODE_REVIEW_VISIBLE) -> InspectReport:
    pkg = DocxPackage.open(path)
    doc_root = pkg.read_xml(DOC_PART)

    paragraphs = doc_root.xpath(".//w:body//w:p", namespaces=NSMAP)

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
    revision_type_by_tag = {
        _w("ins"): "insert",
        _w("del"): "delete",
        _w("moveTo"): "move_to",
        _w("moveFrom"): "move_from",
    }
    revision_nodes = doc_root.xpath(".//w:ins | .//w:del | .//w:moveTo | .//w:moveFrom", namespaces=NSMAP)
    for item in revision_nodes:
        revision_type = revision_type_by_tag.get(item.tag)
        if revision_type is None:
            continue
        revisions.append(
            RevisionRecord(
                type=revision_type,
                revision_id=item.get(_w_attr("id")),
                author=item.get(_w_attr("author")),
                created_at=item.get(_w_attr("date")),
                text=_text_of(item),
            )
        )

    return InspectReport(
        path=path,
        paragraph_count=len(paragraphs),
        text_mode=text_mode,
        text_value=_document_text(doc_root, text_mode=text_mode),
        comments=comments,
        revisions=revisions,
    )


def list_review(path: Path, *, text_mode: str = TEXT_MODE_REVIEW_VISIBLE) -> dict[str, Any]:
    report = inspect(path, text_mode=text_mode)
    return {
        "path": str(path),
        "paragraph_count": report.paragraph_count,
        "text_mode": report.text_mode,
        "text_value": report.text_value,
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
                "type": r.type,
                "revision_id": r.revision_id,
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
    selector: str | None = None,
    anchor: dict[str, Any] | None = None,
    text: str,
    author: str,
    initials: str,
    dry_run: bool,
) -> OperationResult:
    pkg = DocxPackage.open(path)
    doc_root = pkg.read_xml(DOC_PART)
    comments_root = _ensure_comments_infrastructure(pkg)

    paragraph_index, paragraph, anchor_resolution = _resolve_anchor_spec(
        doc_root,
        selector=selector,
        anchor=anchor,
    )

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
            "anchor": anchor or {},
            "anchor_resolution": anchor_resolution,
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


def _find_replace_once_target(
    paragraphs: list[etree._Element],
    find_text: str,
) -> tuple[int, etree._Element] | None:
    for idx, paragraph in enumerate(paragraphs):
        if find_text in _paragraph_text(paragraph):
            return idx, paragraph
    return None


def preflight_patch(
    path: Path,
    *,
    patch_data: dict[str, Any],
    track_changes: bool,
    allow_paragraph_rewrite_tracked: bool,
) -> dict[str, Any]:
    """Classify patch operations without mutating the document."""
    operations = patch_data.get("operations")
    if not isinstance(operations, list) or not operations:
        raise ValueError("Patch must include non-empty 'operations' list")

    pkg = DocxPackage.open(path)
    doc_root = pkg.read_xml(DOC_PART)
    paragraphs = _body_paragraphs(doc_root)
    if not paragraphs:
        raise ValueError("No paragraphs found in document body")

    op_reports: list[dict[str, Any]] = []
    summary = {
        "safe_localized": 0,
        "needs_multi_run_localized": 0,
        "requires_uno": 0,
        "unsupported_high_risk": 0,
    }

    for i, op in enumerate(operations):
        op_type = str(op.get("type"))
        report: dict[str, Any] = {
            "index": i,
            "type": op_type,
            "classification": "",
            "recommended_strategy": "",
            "recommended_engine": "",
            "paragraph_index": None,
            "reason": "",
            "reason_code": "",
            "reason_detail": "",
            "detected_patterns": [],
        }

        if op_type == "replace_paragraph_text":
            try:
                anchor = _anchor_from_operation(op)
                resolve_anchor = dict(anchor or {})
                if "paragraph_index" in resolve_anchor:
                    # Preserve legacy behavior: expected_text mismatch is checked after index selection.
                    resolve_anchor.pop("expected_text", None)
                idx, paragraph, anchor_resolution = _resolve_anchor_spec(doc_root, anchor=resolve_anchor)
                report["paragraph_index"] = idx
                report["anchor_resolution"] = anchor_resolution
            except AnchorResolutionError as exc:
                report.update(
                    {
                        "classification": "unsupported_high_risk",
                        "recommended_strategy": "none",
                        "recommended_engine": "comment_fallback",
                        "reason": exc.code,
                        "reason_code": exc.code,
                        "reason_detail": str(exc),
                        "anchor_details": exc.details,
                    }
                )
                summary[report["classification"]] += 1
                op_reports.append(report)
                continue
            except ValueError as exc:
                report.update(
                    {
                        "classification": "unsupported_high_risk",
                        "recommended_strategy": "none",
                        "recommended_engine": "comment_fallback",
                        "reason": "invalid_anchor_payload",
                        "reason_code": "invalid_anchor_payload",
                        "reason_detail": str(exc),
                    }
                )
                summary[report["classification"]] += 1
                op_reports.append(report)
                continue

            risky_patterns = _paragraph_risky_patterns(paragraph)
            if risky_patterns:
                report.update(
                    {
                        "classification": "unsupported_high_risk",
                        "recommended_strategy": "none",
                        "recommended_engine": "uno",
                        "reason": "risky_markup_detected",
                        "reason_code": "risky_markup_detected",
                        "reason_detail": "Paragraph contains risky OOXML markup for paragraph rewrite",
                        "detected_patterns": risky_patterns,
                    }
                )
            elif track_changes and not allow_paragraph_rewrite_tracked:
                report.update(
                    {
                        "classification": "requires_uno",
                        "recommended_strategy": "uno",
                        "recommended_engine": "uno",
                        "reason": "tracked_paragraph_rewrite_disallowed",
                        "reason_code": "tracked_paragraph_rewrite_disallowed",
                        "reason_detail": "Strict tracked mode disallows paragraph rewrite fallback",
                    }
                )
            else:
                report.update(
                    {
                        "classification": "safe_localized",
                        "recommended_strategy": "paragraph_rewrite",
                        "recommended_engine": "ooxml",
                        "reason": "explicit_paragraph_replace",
                        "reason_code": "explicit_paragraph_replace",
                        "reason_detail": "Paragraph rewrite is allowed under current policy",
                    }
                )

            summary[report["classification"]] += 1
            op_reports.append(report)
            continue

        if op_type == "replace_text_once":
            find_text = str(op["find"])
            replacement = str(op["replace"])
            try:
                anchor = _anchor_from_operation(op)
                idx, paragraph, anchor_resolution = _resolve_anchor_spec(
                    doc_root,
                    anchor=anchor,
                    fallback_text=find_text,
                )
                report["paragraph_index"] = idx
                report["anchor_resolution"] = anchor_resolution
            except AnchorResolutionError as exc:
                report.update(
                    {
                        "classification": "unsupported_high_risk",
                        "recommended_strategy": "none",
                        "recommended_engine": "comment_fallback",
                        "reason": exc.code,
                        "reason_code": exc.code,
                        "reason_detail": str(exc),
                        "anchor_details": exc.details,
                        "find": find_text,
                    }
                )
                summary[report["classification"]] += 1
                op_reports.append(report)
                continue
            except ValueError as exc:
                report.update(
                    {
                        "classification": "unsupported_high_risk",
                        "recommended_strategy": "none",
                        "recommended_engine": "comment_fallback",
                        "reason": "invalid_anchor_payload",
                        "reason_code": "invalid_anchor_payload",
                        "reason_detail": str(exc),
                        "find": find_text,
                    }
                )
                summary[report["classification"]] += 1
                op_reports.append(report)
                continue

            if find_text not in _paragraph_text(paragraph):
                report.update(
                    {
                        "classification": "unsupported_high_risk",
                        "recommended_strategy": "none",
                        "recommended_engine": "comment_fallback",
                        "reason": "find_text_not_in_resolved_anchor",
                        "reason_code": "find_text_not_in_resolved_anchor",
                        "reason_detail": f"find={find_text!r} not present at resolved paragraph {idx}",
                        "find": find_text,
                    }
                )
                summary[report["classification"]] += 1
                op_reports.append(report)
                continue

            risky_patterns = _paragraph_risky_patterns(paragraph)
            if risky_patterns:
                report.update(
                    {
                        "classification": "unsupported_high_risk",
                        "recommended_strategy": "none",
                        "recommended_engine": "uno",
                        "reason": "risky_markup_detected",
                        "reason_code": "risky_markup_detected",
                        "reason_detail": "Resolved paragraph contains risky OOXML markup",
                        "detected_patterns": risky_patterns,
                    }
                )
                summary[report["classification"]] += 1
                op_reports.append(report)
                continue

            probe = _replace_text_once_localized(
                deepcopy(paragraph),
                find_text=find_text,
                replacement=replacement,
                track_changes=track_changes,
                author="preflight",
                revision_id=1,
                timestamp="1970-01-01T00:00:00Z",
            )
            if probe is not None:
                report.update(
                    {
                        "classification": "safe_localized",
                        "recommended_strategy": str(probe.get("strategy", "localized_run")),
                        "recommended_engine": "ooxml",
                        "reason": "localized_strategy_available",
                        "reason_code": "localized_strategy_available",
                        "reason_detail": f"Localized strategy {probe.get('strategy', 'localized_run')} is available",
                    }
                )
            elif _text_run_spans_multiple_runs(paragraph, find_text):
                report.update(
                    {
                        "classification": "needs_multi_run_localized",
                        "recommended_strategy": "uno" if track_changes and not allow_paragraph_rewrite_tracked else "paragraph_rewrite",
                        "recommended_engine": "uno" if track_changes and not allow_paragraph_rewrite_tracked else "ooxml",
                        "reason": "match_spans_multiple_runs",
                        "reason_code": "match_spans_multiple_runs",
                        "reason_detail": "Match spans runs that are not safely localizable in this paragraph",
                        "detected_patterns": ["match_spans_multiple_runs"],
                    }
                )
            elif track_changes and not allow_paragraph_rewrite_tracked:
                report.update(
                    {
                        "classification": "requires_uno",
                        "recommended_strategy": "uno",
                        "recommended_engine": "uno",
                        "reason": "tracked_paragraph_rewrite_disallowed",
                        "reason_code": "tracked_paragraph_rewrite_disallowed",
                        "reason_detail": "Strict tracked mode disallows paragraph rewrite fallback",
                    }
                )
            else:
                report.update(
                    {
                        "classification": "requires_uno",
                        "recommended_strategy": "paragraph_rewrite",
                        "recommended_engine": "ooxml",
                        "reason": "localized_strategy_unavailable",
                        "reason_code": "localized_strategy_unavailable",
                        "reason_detail": "Fallback would require paragraph rewrite",
                    }
                )

            summary[report["classification"]] += 1
            op_reports.append(report)
            continue

        report.update(
            {
                "classification": "requires_uno",
                "recommended_strategy": "uno",
                "recommended_engine": "uno",
                "reason": f"unsupported_ooxml_op:{op_type}",
                "reason_code": "unsupported_ooxml_op",
                "reason_detail": f"Operation type {op_type!r} is not implemented in OOXML engine",
            }
        )
        summary[report["classification"]] += 1
        op_reports.append(report)

    return {
        "path": str(path),
        "track_changes": track_changes,
        "allow_paragraph_rewrite_tracked": allow_paragraph_rewrite_tracked,
        "operations": op_reports,
        "summary": summary,
    }


def apply_patch(
    path: Path,
    *,
    patch_data: dict[str, Any],
    author: str,
    track_changes: bool,
    dry_run: bool,
    allow_paragraph_rewrite_tracked: bool = True,
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
            anchor = _anchor_from_operation(op)
            resolve_anchor = dict(anchor or {})
            if "paragraph_index" in resolve_anchor:
                resolve_anchor.pop("expected_text", None)
            try:
                idx, p, anchor_resolution = _resolve_anchor_spec(doc_root, anchor=resolve_anchor)
            except AnchorResolutionError as exc:
                raise ValueError(f"{exc.code}: {exc}") from exc
            risky_patterns = _paragraph_risky_patterns(p)
            if risky_patterns:
                raise OoxmlUnsupportedOperation(
                    "Risky OOXML markup detected for paragraph rewrite "
                    f"at paragraph {idx}: {', '.join(risky_patterns)}"
                )
            expected = op.get("expected_text")
            old_text = _paragraph_text(p)
            if expected is not None and old_text != expected:
                raise ValueError(
                    f"Expected paragraph text mismatch at index {idx}: expected={expected!r}, actual={old_text!r}"
                )
            new_text = str(op.get("new_text", ""))
            report = None
            if old_text:
                report = _replace_text_once_localized(
                    p,
                    find_text=old_text,
                    replacement=new_text,
                    track_changes=track_changes,
                    author=author,
                    revision_id=next_revision_id,
                    timestamp=timestamp,
                )

            if report is None:
                if track_changes and not allow_paragraph_rewrite_tracked:
                    raise OoxmlUnsupportedOperation(
                        f"Tracked paragraph rewrite disallowed by fidelity policy at paragraph {idx}"
                    )
                report = _replace_paragraph_content(
                    p,
                    new_text,
                    track_changes=track_changes,
                    author=author,
                    revision_id=next_revision_id,
                    timestamp=timestamp,
                )
                report["strategy"] = "paragraph_rewrite"

            report.update(
                {
                    "type": op_type,
                    "paragraph_index": idx,
                    "strategy": str(report.get("strategy", "localized_run")),
                    "anchor": anchor or {},
                    "anchor_resolution": anchor_resolution,
                }
            )
            op_reports.append(report)
            next_revision_id += 2
            continue

        if op_type == "replace_text_once":
            find_text = str(op["find"])
            replacement = str(op["replace"])
            anchor = _anchor_from_operation(op)
            if anchor:
                try:
                    idx, paragraph, anchor_resolution = _resolve_anchor_spec(
                        doc_root,
                        anchor=anchor,
                        fallback_text=find_text,
                    )
                except AnchorResolutionError as exc:
                    raise ValueError(f"{exc.code}: {exc}") from exc
                current = _paragraph_text(paragraph)
                if find_text not in current:
                    raise ValueError(
                        f"find_text_not_in_resolved_anchor: find={find_text!r} at paragraph {idx}"
                    )
            else:
                target = _find_replace_once_target(paragraphs, find_text)
                if target is None:
                    raise ValueError(f"Text not found for replace_text_once: {find_text!r}")
                idx, paragraph = target
                current = _paragraph_text(paragraph)
                anchor_resolution = {
                    "anchor": {},
                    "resolved_index": idx,
                    "candidate_count": 1,
                    "candidates": [idx],
                }

            risky_patterns = _paragraph_risky_patterns(paragraph)
            if risky_patterns:
                raise OoxmlUnsupportedOperation(
                    "Risky OOXML markup detected for localized replace_text_once "
                    f"at paragraph {idx}: {', '.join(risky_patterns)}"
                )

            report = _replace_text_once_localized(
                paragraph,
                find_text=find_text,
                replacement=replacement,
                track_changes=track_changes,
                author=author,
                revision_id=next_revision_id,
                timestamp=timestamp,
            )
            if report is None:
                if track_changes and not allow_paragraph_rewrite_tracked:
                    raise OoxmlUnsupportedOperation(
                        "Localized replace unsupported and tracked paragraph rewrite disallowed "
                        f"for find={find_text!r} at paragraph {idx}"
                    )
                new_text = current.replace(find_text, replacement, 1)
                report = _replace_paragraph_content(
                    paragraph,
                    new_text,
                    track_changes=track_changes,
                    author=author,
                    revision_id=next_revision_id,
                    timestamp=timestamp,
                )
                report["strategy"] = "paragraph_rewrite"

            report.update(
                {
                    "type": op_type,
                    "paragraph_index": idx,
                    "find": find_text,
                    "replace": replacement,
                    "anchor": anchor or {},
                    "anchor_resolution": anchor_resolution,
                }
            )
            op_reports.append(report)
            next_revision_id += 2
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


def review_action(
    path: Path,
    *,
    mode: str,
    author: str | None,
    actor: str,
    dry_run: bool,
) -> OperationResult:
    return ooxml_review.review_action(
        path,
        mode=mode,
        author=author,
        actor=actor,
        dry_run=dry_run,
    )
