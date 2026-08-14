"""Internal OOXML localized replacement helpers."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
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


def _run_signature(run: etree._Element) -> tuple[tuple[tuple[str, str], ...], bytes]:
    attrs = tuple(sorted((str(k), str(v)) for k, v in run.attrib.items()))
    rpr = run.find(_w("rPr"))
    rpr_bytes = etree.tostring(rpr, encoding="utf-8") if rpr is not None else b""
    return attrs, rpr_bytes


@dataclass(slots=True)
class _VisibleTextSpan:
    node: etree._Element
    run: etree._Element | None
    start: int
    end: int
    safe: bool
    unsafe_patterns: tuple[str, ...]


@dataclass(slots=True)
class LocalizedReplacePlan:
    """A first-occurrence replacement decision bound to exact OOXML nodes."""

    status: str
    match_start: int
    match_end: int
    runs: tuple[etree._Element, ...] = ()
    prefix: str = ""
    suffix: str = ""
    strategy: str = ""
    detected_patterns: tuple[str, ...] = ()


@dataclass(slots=True)
class ProtectedScopeState:
    complex_field_depth: int = 0
    active_comment_ids: dict[str, int] = field(default_factory=dict)


def _update_protected_scope_state(
    element: etree._Element,
    state: ProtectedScopeState,
) -> bool:
    if element.tag == _w("commentRangeStart"):
        comment_id = element.get(_w_attr("id"), "")
        state.active_comment_ids[comment_id] = state.active_comment_ids.get(comment_id, 0) + 1
        return True
    if element.tag == _w("commentRangeEnd"):
        comment_id = element.get(_w_attr("id"), "")
        remaining = state.active_comment_ids.get(comment_id, 0) - 1
        if remaining > 0:
            state.active_comment_ids[comment_id] = remaining
        else:
            state.active_comment_ids.pop(comment_id, None)
        return True
    if element.tag == _w("fldChar"):
        field_type = element.get(_w_attr("fldCharType"), "")
        if field_type == "begin":
            state.complex_field_depth += 1
        elif field_type == "end":
            state.complex_field_depth = max(0, state.complex_field_depth - 1)
        return True
    return False


def protected_scope_state_before(
    root: etree._Element,
    target: etree._Element,
) -> ProtectedScopeState:
    state = ProtectedScopeState()
    for _, element in etree.iterwalk(root, events=("start",)):
        if element is target:
            break
        _update_protected_scope_state(element, state)
    return state


_SPECIAL_ANCESTOR_PATTERNS = {
    _w("hyperlink"): "hyperlink",
    _w("sdt"): "sdt",
    _w("sdtContent"): "sdt",
    _w("smartTag"): "smartTag",
    _w("customXml"): "customXml",
    _w("fldSimple"): "fldSimple",
    _w("ins"): "existing_revision",
    _w("del"): "existing_revision",
    _w("moveTo"): "existing_revision",
    _w("moveFrom"): "existing_revision",
}


def _local_name(element: etree._Element) -> str:
    return etree.QName(element).localname


def _direct_safe_run(
    paragraph: etree._Element,
    text_node: etree._Element,
) -> tuple[etree._Element | None, set[str]]:
    patterns: set[str] = set()
    run = text_node.getparent()
    if run is None or run.tag != _w("r") or run.getparent() is not paragraph:
        patterns.add("non_direct_text")
        for ancestor in text_node.iterancestors():
            pattern = _SPECIAL_ANCESTOR_PATTERNS.get(ancestor.tag)
            if pattern:
                patterns.add(pattern)
            if ancestor is paragraph:
                break
        return None, patterns

    children = list(run)
    expected_children = [text_node]
    if children and children[0].tag == _w("rPr"):
        expected_children.insert(0, children[0])
    if children != expected_children or text_node.tag != _w("t"):
        extras = [child for child in children if child not in expected_children]
        patterns.update(_local_name(child) for child in extras)
        patterns.add("special_run_markup")
        return run, patterns

    return run, patterns


def _review_visible_text_spans(
    paragraph: etree._Element,
    *,
    initial_scope_state: ProtectedScopeState | None = None,
) -> tuple[str, list[_VisibleTextSpan]]:
    spans: list[_VisibleTextSpan] = []
    parts: list[str] = []
    cursor = 0
    state = ProtectedScopeState()
    if initial_scope_state is not None:
        state.complex_field_depth = initial_scope_state.complex_field_depth
        state.active_comment_ids = dict(initial_scope_state.active_comment_ids)

    for event, element in etree.iterwalk(paragraph, events=("start",)):
        if event != "start":
            continue

        if _update_protected_scope_state(element, state):
            continue
        if element.tag not in {_w("t"), _w("delText")}:
            continue

        hidden = any(
            ancestor.tag in {_w("del"), _w("moveFrom")}
            for ancestor in element.iterancestors()
        )
        if hidden:
            continue

        text = element.text or ""
        run, patterns = _direct_safe_run(paragraph, element)
        if state.complex_field_depth:
            patterns.add("complex_field_range")
        if state.active_comment_ids:
            patterns.add("comment_range")

        end = cursor + len(text)
        spans.append(
            _VisibleTextSpan(
                node=element,
                run=run,
                start=cursor,
                end=end,
                safe=not patterns,
                unsafe_patterns=tuple(sorted(patterns)),
            )
        )
        parts.append(text)
        cursor = end

    return "".join(parts), spans


def plan_replace_text_once_localized(
    paragraph: etree._Element,
    *,
    paragraph_text_fn: Callable[[etree._Element], str],
    find_text: str,
    initial_scope_state: ProtectedScopeState | None = None,
) -> LocalizedReplacePlan:
    """Bind the first review-visible match and decide whether it is safe to localize."""
    visible_text, spans = _review_visible_text_spans(
        paragraph,
        initial_scope_state=initial_scope_state,
    )
    expected_text = paragraph_text_fn(paragraph)
    if visible_text != expected_text:
        return LocalizedReplacePlan(
            status="unsafe_markup",
            match_start=-1,
            match_end=-1,
            detected_patterns=("review_text_projection_mismatch",),
        )

    match_start = visible_text.find(find_text)
    if match_start < 0:
        return LocalizedReplacePlan(status="not_found", match_start=-1, match_end=-1)
    match_end = match_start + len(find_text)
    touched = [
        span
        for span in spans
        if max(span.start, match_start) < min(span.end, match_end)
    ]
    if not touched or any(not span.safe for span in touched):
        detected = sorted(
            {
                pattern
                for span in touched
                for pattern in span.unsafe_patterns
            }
        )
        return LocalizedReplacePlan(
            status="unsafe_markup",
            match_start=match_start,
            match_end=match_end,
            detected_patterns=tuple(detected or ["unmapped_review_text"]),
        )

    runs: list[etree._Element] = []
    for span in touched:
        if span.run is not None and all(span.run is not existing for existing in runs):
            runs.append(span.run)

    if len(runs) > 1:
        positions = [paragraph.index(run) for run in runs]
        signatures = [_run_signature(run) for run in runs]
        if any(right != left + 1 for left, right in zip(positions, positions[1:])):
            return LocalizedReplacePlan(
                status="incompatible_multi_run",
                match_start=match_start,
                match_end=match_end,
                detected_patterns=("noncontiguous_runs",),
            )
        if any(signature != signatures[0] for signature in signatures[1:]):
            return LocalizedReplacePlan(
                status="incompatible_multi_run",
                match_start=match_start,
                match_end=match_end,
                detected_patterns=("incompatible_run_formatting",),
            )

    first_span = touched[0]
    last_span = touched[-1]
    first_text = first_span.node.text or ""
    last_text = last_span.node.text or ""
    prefix = first_text[: match_start - first_span.start]
    suffix = last_text[match_end - last_span.start :]
    return LocalizedReplacePlan(
        status="safe",
        match_start=match_start,
        match_end=match_end,
        runs=tuple(runs),
        prefix=prefix,
        suffix=suffix,
        strategy="localized_run" if len(runs) == 1 else "localized_multi_run",
    )


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
    plan: LocalizedReplacePlan | None = None,
) -> dict[str, Any] | None:
    selected_plan = plan or plan_replace_text_once_localized(
        paragraph,
        paragraph_text_fn=paragraph_text_fn,
        find_text=find_text,
    )
    if selected_plan.status != "safe" or not selected_plan.runs:
        return None

    runs = list(selected_plan.runs)
    template_run = runs[0]
    parent = template_run.getparent()
    if parent is not paragraph or any(run.getparent() is not parent for run in runs):
        return None

    insert_idx = parent.index(template_run)
    for run in runs:
        parent.remove(run)

    if track_changes:
        common_prefix, old_middle, common_suffix, new_middle = _replacement_delta(find_text, replacement)
        left_text = selected_plan.prefix + common_prefix
        right_text = common_suffix + selected_plan.suffix

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
        parent.insert(
            insert_idx,
            _build_run_like(
                template_run,
                selected_plan.prefix + replacement + selected_plan.suffix,
                tag="t",
            ),
        )

    report: dict[str, Any] = {
        "old_text": find_text,
        "new_text": replacement,
        "strategy": selected_plan.strategy,
    }
    if len(runs) > 1:
        report["spanned_runs"] = len(runs)
    return report


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
