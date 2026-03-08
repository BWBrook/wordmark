"""Internal OOXML anchor-resolution helpers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from lxml import etree

from wordmark.constants import NSMAP


class AnchorResolutionError(ValueError):
    """Anchor resolution failed with a machine-readable code."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


def _body_paragraphs(document_root: etree._Element) -> list[etree._Element]:
    return document_root.xpath(".//w:body//w:p", namespaces=NSMAP)


def _paragraph_at(
    paragraphs: list[etree._Element],
    idx: int,
    *,
    paragraph_text_fn: Callable[[etree._Element], str],
) -> str:
    if idx < 0 or idx >= len(paragraphs):
        return ""
    return paragraph_text_fn(paragraphs[idx])


def normalize_anchor(
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
        out.update({key: value for key, value in anchor.items() if value is not None})
    return out


def resolve_anchor_spec(
    document_root: etree._Element,
    *,
    paragraph_text_fn: Callable[[etree._Element], str],
    selector: str | None = None,
    anchor: dict[str, Any] | None = None,
    fallback_text: str | None = None,
) -> tuple[int, etree._Element, dict[str, Any]]:
    paragraphs = _body_paragraphs(document_root)
    if not paragraphs:
        raise AnchorResolutionError("anchor_not_found", "No paragraphs found in document")

    spec = normalize_anchor(selector=selector, anchor=anchor)
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
            idx for idx in candidate_indices if filter_text in paragraph_text_fn(paragraphs[idx])
        ]

    if isinstance(context_before, str) and context_before:
        candidate_indices = [
            idx
            for idx in candidate_indices
            if idx > 0 and context_before in _paragraph_at(paragraphs, idx - 1, paragraph_text_fn=paragraph_text_fn)
        ]
    if isinstance(context_after, str) and context_after:
        candidate_indices = [
            idx
            for idx in candidate_indices
            if idx < (len(paragraphs) - 1)
            and context_after in _paragraph_at(paragraphs, idx + 1, paragraph_text_fn=paragraph_text_fn)
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


def resolve_anchor(
    document_root: etree._Element,
    selector: str,
    *,
    paragraph_text_fn: Callable[[etree._Element], str],
) -> tuple[int, etree._Element]:
    idx, paragraph, _ = resolve_anchor_spec(
        document_root,
        paragraph_text_fn=paragraph_text_fn,
        selector=selector,
    )
    return idx, paragraph


def anchor_from_operation(op: dict[str, Any]) -> dict[str, Any] | None:
    raw_anchor = op.get("anchor")
    if raw_anchor is not None and not isinstance(raw_anchor, dict):
        raise ValueError("Operation anchor must be an object")

    merged: dict[str, Any] = {}
    for key in ("paragraph_index", "expected_text", "context_before", "context_after", "occurrence"):
        if key in op and op.get(key) is not None:
            merged[key] = op.get(key)
    if isinstance(raw_anchor, dict):
        merged.update({key: value for key, value in raw_anchor.items() if value is not None})
    return merged or None
