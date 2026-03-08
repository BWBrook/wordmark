"""Internal OOXML localized replacement helpers."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

from lxml import etree

from wordmark.constants import W_NS


def _w(local: str) -> str:
    return f"{{{W_NS}}}{local}"


def _w_attr(local: str) -> str:
    return f"{{{W_NS}}}{local}"


def _replacement_delta(old_text: str, new_text: str) -> tuple[str, str, str, str]:
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


def _set_text_node(text_el: etree._Element, text: str) -> None:
    if text != text.strip():
        text_el.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    else:
        text_el.attrib.pop("{http://www.w3.org/XML/1998/namespace}space", None)
    text_el.text = text


def _build_run_with_text(text: str, *, tag: str = "t") -> etree._Element:
    run = etree.Element(_w("r"))
    text_el = etree.SubElement(run, _w(tag))
    _set_text_node(text_el, text)
    return run


def _build_run_like(template_run: etree._Element, text: str, *, tag: str = "t") -> etree._Element:
    run = etree.Element(_w("r"), attrib=dict(template_run.attrib))
    rpr = template_run.find(_w("rPr"))
    if rpr is not None:
        run.append(deepcopy(rpr))
    text_el = etree.SubElement(run, _w(tag))
    _set_text_node(text_el, text)
    return run


def _run_text_node_and_extras(run: etree._Element) -> tuple[etree._Element, list[etree._Element]] | None:
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


def text_run_spans_multiple_runs(paragraph: etree._Element, find_text: str) -> bool:
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


def replace_text_once_localized(
    paragraph: etree._Element,
    *,
    paragraph_text_fn: Callable[[etree._Element], str],
    find_text: str,
    replacement: str,
    track_changes: bool,
    author: str,
    revision_id: int,
    timestamp: str,
) -> dict[str, Any] | None:
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


def replace_paragraph_content(
    paragraph: etree._Element,
    new_text: str,
    *,
    paragraph_text_fn: Callable[[etree._Element], str],
    track_changes: bool,
    author: str,
    revision_id: int,
    timestamp: str,
) -> dict[str, Any]:
    old_text = paragraph_text_fn(paragraph)
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
