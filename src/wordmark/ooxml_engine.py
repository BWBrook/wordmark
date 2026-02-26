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
TEXT_MODE_REVIEW_VISIBLE = "review-visible"
TEXT_MODE_RAW = "raw"
TEXT_MODES = {TEXT_MODE_REVIEW_VISIBLE, TEXT_MODE_RAW}


class OoxmlUnsupportedOperation(RuntimeError):
    """Operation must be handled by fallback engine."""


class AnchorResolutionError(ValueError):
    """Anchor resolution failed with a machine-readable code."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


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


def _body_paragraphs(document_root: etree._Element) -> list[etree._Element]:
    return document_root.xpath(".//w:body//w:p", namespaces=NSMAP)


def _paragraph_at(paragraphs: list[etree._Element], idx: int) -> str:
    if idx < 0 or idx >= len(paragraphs):
        return ""
    return _paragraph_text(paragraphs[idx], text_mode=TEXT_MODE_REVIEW_VISIBLE)


def _normalize_anchor(
    *,
    selector: str | None = None,
    anchor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if selector:
        if selector.startswith("p:"):
            out["paragraph_index"] = int(selector.split(":", 1)[1])
        elif selector.startswith("text:"):
            out["expected_text"] = selector.split(":", 1)[1]
        else:
            raise AnchorResolutionError(
                "anchor_not_found",
                "Unsupported selector. Use 'p:<index>' or 'text:<snippet>'",
                {"selector": selector},
            )

    if anchor:
        out.update({k: v for k, v in anchor.items() if v is not None})
    return out


def _resolve_anchor_spec(
    document_root: etree._Element,
    *,
    selector: str | None = None,
    anchor: dict[str, Any] | None = None,
    fallback_text: str | None = None,
) -> tuple[int, etree._Element, dict[str, Any]]:
    paragraphs = _body_paragraphs(document_root)
    if not paragraphs:
        raise AnchorResolutionError("anchor_not_found", "No paragraphs found in document")

    spec = _normalize_anchor(selector=selector, anchor=anchor)
    paragraph_index = spec.get("paragraph_index")
    expected_text = spec.get("expected_text")
    context_before = spec.get("context_before")
    context_after = spec.get("context_after")
    occurrence_raw = spec.get("occurrence")
    occurrence_provided = occurrence_raw is not None
    occurrence = 1 if occurrence_raw is None else int(occurrence_raw)
    if occurrence < 1:
        raise AnchorResolutionError(
            "anchor_context_mismatch",
            f"Anchor occurrence must be >= 1, got {occurrence}",
            {"occurrence": occurrence},
        )

    candidate_indices = list(range(len(paragraphs)))

    if paragraph_index is not None:
        idx = int(paragraph_index)
        if idx < 0 or idx >= len(paragraphs):
            raise AnchorResolutionError(
                "anchor_not_found",
                f"Paragraph index out of range: {idx}",
                {"paragraph_index": idx, "paragraph_count": len(paragraphs)},
            )
        candidate_indices = [idx]

    filter_text = None
    if isinstance(expected_text, str) and expected_text:
        filter_text = expected_text
    elif fallback_text:
        filter_text = fallback_text

    if filter_text:
        candidate_indices = [
            idx for idx in candidate_indices if filter_text in _paragraph_text(paragraphs[idx])
        ]

    if isinstance(context_before, str) and context_before:
        candidate_indices = [
            idx
            for idx in candidate_indices
            if idx > 0 and context_before in _paragraph_at(paragraphs, idx - 1)
        ]
    if isinstance(context_after, str) and context_after:
        candidate_indices = [
            idx
            for idx in candidate_indices
            if idx < (len(paragraphs) - 1) and context_after in _paragraph_at(paragraphs, idx + 1)
        ]

    if not candidate_indices:
        code = "anchor_context_mismatch" if any([context_before, context_after]) else "anchor_not_found"
        raise AnchorResolutionError(
            code,
            "Anchor did not resolve to any paragraph",
            {
                "anchor": spec,
                "fallback_text": fallback_text,
                "paragraph_count": len(paragraphs),
            },
        )

    candidate_indices = sorted(candidate_indices)
    if occurrence_provided:
        if occurrence > len(candidate_indices):
            raise AnchorResolutionError(
                "anchor_not_found",
                f"Anchor occurrence out of range: {occurrence} > {len(candidate_indices)}",
                {
                    "occurrence": occurrence,
                    "candidate_count": len(candidate_indices),
                    "candidates": candidate_indices,
                },
            )
        selected_idx = candidate_indices[occurrence - 1]
    elif len(candidate_indices) == 1:
        selected_idx = candidate_indices[0]
    else:
        raise AnchorResolutionError(
            "anchor_ambiguous",
            "Anchor resolved to multiple candidate paragraphs",
            {
                "candidate_count": len(candidate_indices),
                "candidates": candidate_indices,
                "hint": "Provide anchor.occurrence or stronger context_before/context_after",
            },
        )

    return selected_idx, paragraphs[selected_idx], {
        "anchor": spec,
        "resolved_index": selected_idx,
        "candidate_count": len(candidate_indices),
        "candidates": candidate_indices,
    }


def _resolve_anchor(document_root: etree._Element, selector: str) -> tuple[int, etree._Element]:
    idx, paragraph, _ = _resolve_anchor_spec(document_root, selector=selector)
    return idx, paragraph


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
    _set_text_node(text_el, text)
    return run


def _set_text_node(text_el: etree._Element, text: str) -> None:
    if text != text.strip():
        text_el.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    else:
        text_el.attrib.pop("{http://www.w3.org/XML/1998/namespace}space", None)
    text_el.text = text


def _build_run_like(template_run: etree._Element, text: str, *, tag: str = "t") -> etree._Element:
    """Create a run preserving run-level styling from the template run."""
    run = etree.Element(_w("r"), attrib=dict(template_run.attrib))
    rpr = template_run.find(_w("rPr"))
    if rpr is not None:
        run.append(deepcopy(rpr))
    text_el = etree.SubElement(run, _w(tag))
    _set_text_node(text_el, text)
    return run


def _run_text_node_and_extras(run: etree._Element) -> tuple[etree._Element, list[etree._Element]] | None:
    """Return one text node and non-(rPr/t) children that need preservation."""
    text_nodes = run.findall(_w("t"))
    if len(text_nodes) != 1:
        return None
    extras = [child for child in list(run) if child.tag not in {_w("rPr"), _w("t")}]
    return text_nodes[0], extras


def _run_signature(run: etree._Element) -> tuple[tuple[tuple[str, str], ...], bytes]:
    attrs = tuple(sorted((str(k), str(v)) for k, v in run.attrib.items()))
    rpr = run.find(_w("rPr"))
    rpr_bytes = etree.tostring(rpr, encoding="utf-8") if rpr is not None else b""
    return attrs, rpr_bytes


def _safe_window_run_info(run: etree._Element) -> tuple[str, tuple[tuple[tuple[str, str], ...], bytes]] | None:
    info = _run_text_node_and_extras(run)
    if info is None:
        return None
    text_node, extras = info
    if extras:
        return None
    return text_node.text or "", _run_signature(run)


def _text_run_spans_multiple_runs(paragraph: etree._Element, find_text: str) -> bool:
    run_texts = []
    for run in paragraph.findall(_w("r")):
        text_nodes = run.findall(_w("t"))
        if len(text_nodes) != 1:
            continue
        run_texts.append(text_nodes[0].text or "")

    if not run_texts:
        return False

    joined = "".join(run_texts)
    offset = joined.find(find_text)
    if offset < 0:
        return False

    start = offset
    end = offset + len(find_text)
    cursor = 0
    touched = 0
    for text in run_texts:
        nxt = cursor + len(text)
        if max(cursor, start) < min(nxt, end):
            touched += 1
        cursor = nxt
    return touched > 1


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


def _replacement_delta(old_text: str, new_text: str) -> tuple[str, str, str, str]:
    """Return common prefix/suffix and changed middle segments."""
    prefix_len = 0
    max_prefix = min(len(old_text), len(new_text))
    while prefix_len < max_prefix and old_text[prefix_len] == new_text[prefix_len]:
        prefix_len += 1

    old_tail = len(old_text)
    new_tail = len(new_text)
    while old_tail > prefix_len and new_tail > prefix_len and old_text[old_tail - 1] == new_text[new_tail - 1]:
        old_tail -= 1
        new_tail -= 1

    common_prefix = old_text[:prefix_len]
    old_middle = old_text[prefix_len:old_tail]
    common_suffix = old_text[old_tail:]
    new_middle = new_text[prefix_len:new_tail]
    return common_prefix, old_middle, common_suffix, new_middle


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
    """Try run-level localized replace. Returns None when unsupported."""
    for run in paragraph.findall(_w("r")):
        info = _run_text_node_and_extras(run)
        if info is None:
            continue
        text_node, extras = info
        current_text = text_node.text or ""
        offset = current_text.find(find_text)
        if offset < 0:
            continue

        prefix = current_text[:offset]
        matched = current_text[offset : offset + len(find_text)]
        suffix = current_text[offset + len(find_text) :]

        parent = run.getparent()
        if parent is None:
            continue
        if extras and not prefix:
            # Keep fallback behavior when non-text run children would be dropped.
            continue
        idx = parent.index(run)
        parent.remove(run)

        if track_changes:
            common_prefix, old_middle, common_suffix, new_middle = _replacement_delta(matched, replacement)
            left_text = prefix + common_prefix
            right_text = common_suffix + suffix

            if left_text:
                if extras:
                    prefix_run = deepcopy(run)
                    prefix_text = prefix_run.find(_w("t"))
                    if prefix_text is None:
                        return None
                    _set_text_node(prefix_text, left_text)
                    parent.insert(idx, prefix_run)
                else:
                    parent.insert(idx, _build_run_like(run, left_text, tag="t"))
                idx += 1

            if old_middle:
                deleted = etree.Element(_w("del"))
                deleted.set(_w_attr("id"), str(revision_id))
                deleted.set(_w_attr("author"), author)
                deleted.set(_w_attr("date"), timestamp)
                deleted.append(_build_run_like(run, old_middle, tag="delText"))
                parent.insert(idx, deleted)
                idx += 1

            if new_middle:
                inserted = etree.Element(_w("ins"))
                inserted.set(_w_attr("id"), str(revision_id + 1))
                inserted.set(_w_attr("author"), author)
                inserted.set(_w_attr("date"), timestamp)
                inserted.append(_build_run_like(run, new_middle, tag="t"))
                parent.insert(idx, inserted)
                idx += 1

            if right_text:
                parent.insert(idx, _build_run_like(run, right_text, tag="t"))
        else:
            merged_text = prefix + replacement + suffix
            if extras:
                merged_run = deepcopy(run)
                merged_text_node = merged_run.find(_w("t"))
                if merged_text_node is None:
                    return None
                _set_text_node(merged_text_node, merged_text)
                parent.insert(idx, merged_run)
            else:
                parent.insert(idx, _build_run_like(run, merged_text, tag="t"))

        return {
            "old_text": matched,
            "new_text": replacement,
            "strategy": "localized_run",
        }

    runs = paragraph.findall(_w("r"))
    for start in range(len(runs)):
        start_run = runs[start]
        start_info = _safe_window_run_info(start_run)
        if start_info is None:
            continue
        start_text, signature = start_info
        parent = start_run.getparent()
        if parent is None:
            continue

        window_runs: list[etree._Element] = [start_run]
        window_text = start_text
        prev_pos = parent.index(start_run)

        for end in range(start + 1, len(runs)):
            run = runs[end]
            if run.getparent() is not parent:
                break
            current_pos = parent.index(run)
            if current_pos != prev_pos + 1:
                break
            prev_pos = current_pos

            info = _safe_window_run_info(run)
            if info is None:
                break
            run_text, run_signature = info
            if run_signature != signature:
                break

            window_runs.append(run)
            window_text += run_text

            offset = window_text.find(find_text)
            if offset < 0:
                continue

            prefix = window_text[:offset]
            matched = find_text
            suffix = window_text[offset + len(find_text) :]
            template_run = window_runs[0]
            insert_idx = parent.index(template_run)

            for window_run in window_runs:
                parent.remove(window_run)

            if track_changes:
                common_prefix, old_middle, common_suffix, new_middle = _replacement_delta(matched, replacement)
                left_text = prefix + common_prefix
                right_text = common_suffix + suffix

                if left_text:
                    parent.insert(insert_idx, _build_run_like(template_run, left_text, tag="t"))
                    insert_idx += 1

                if old_middle:
                    deleted = etree.Element(_w("del"))
                    deleted.set(_w_attr("id"), str(revision_id))
                    deleted.set(_w_attr("author"), author)
                    deleted.set(_w_attr("date"), timestamp)
                    deleted.append(_build_run_like(template_run, old_middle, tag="delText"))
                    parent.insert(insert_idx, deleted)
                    insert_idx += 1

                if new_middle:
                    inserted = etree.Element(_w("ins"))
                    inserted.set(_w_attr("id"), str(revision_id + 1))
                    inserted.set(_w_attr("author"), author)
                    inserted.set(_w_attr("date"), timestamp)
                    inserted.append(_build_run_like(template_run, new_middle, tag="t"))
                    parent.insert(insert_idx, inserted)
                    insert_idx += 1

                if right_text:
                    parent.insert(insert_idx, _build_run_like(template_run, right_text, tag="t"))
            else:
                parent.insert(insert_idx, _build_run_like(template_run, prefix + replacement + suffix, tag="t"))

            return {
                "old_text": matched,
                "new_text": replacement,
                "strategy": "localized_multi_run",
                "spanned_runs": len(window_runs),
            }

    return None


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


def _anchor_from_operation(op: dict[str, Any]) -> dict[str, Any] | None:
    raw_anchor = op.get("anchor")
    if raw_anchor is not None and not isinstance(raw_anchor, dict):
        raise ValueError("Operation anchor must be an object")

    merged: dict[str, Any] = {}
    for key in ("paragraph_index", "expected_text", "context_before", "context_after", "occurrence"):
        if key in op and op.get(key) is not None:
            merged[key] = op.get(key)
    if isinstance(raw_anchor, dict):
        merged.update({k: v for k, v in raw_anchor.items() if v is not None})
    return merged or None


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
