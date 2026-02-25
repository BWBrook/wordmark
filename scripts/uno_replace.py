#!/usr/bin/env python3
"""UNO patch helper run with system Python that has `uno` bindings."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
import subprocess
import tempfile
import time
from typing import Any

import uno  # type: ignore
from com.sun.star.beans import PropertyValue  # type: ignore


def _prop(name: str, value: Any) -> PropertyValue:
    prop = PropertyValue()
    prop.Name = name
    prop.Value = value
    return prop


def _connect(port: int, timeout_s: float = 25.0):
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver",
        local,
    )
    target = f"uno:socket,host=127.0.0.1,port={port};urp;StarOffice.ComponentContext"
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            return resolver.resolve(target)
        except Exception:
            time.sleep(0.4)
    raise RuntimeError("Timed out connecting to headless LibreOffice UNO socket")


def _supports_track_changes(doc: Any) -> bool:
    return hasattr(doc, "RecordChanges")


def _configure_track_changes(doc: Any, *, track_changes: bool) -> dict[str, Any]:
    status = {
        "requested": bool(track_changes),
        "supported": _supports_track_changes(doc),
        "enabled": False,
        "show_tracked_changes": None,
    }

    if track_changes and status["supported"]:
        doc.RecordChanges = True
        status["enabled"] = bool(getattr(doc, "RecordChanges", False))

    if hasattr(doc, "CurrentController") and hasattr(doc.CurrentController, "ViewSettings"):
        view = doc.CurrentController.ViewSettings
        if hasattr(view, "ShowTrackedChanges"):
            view.ShowTrackedChanges = True
            status["show_tracked_changes"] = bool(getattr(view, "ShowTrackedChanges", True))

    return status


def _bind_author_metadata(doc: Any, *, author: str) -> dict[str, Any]:
    status = {
        "requested_author": author,
        "document_properties_supported": False,
        "author_before": None,
        "author_after": None,
        "set_author_ok": False,
        "error": None,
    }

    try:
        properties = doc.getDocumentProperties()
    except Exception as exc:
        status["error"] = str(exc)
        return status

    status["document_properties_supported"] = True
    status["author_before"] = getattr(properties, "Author", None)

    try:
        properties.Author = author
        properties.ModifiedBy = author
        status["author_after"] = getattr(properties, "Author", None)
        status["set_author_ok"] = status["author_after"] == author
    except Exception as exc:
        status["error"] = str(exc)

    return status


def _find_nth_occurrence(doc: Any, descriptor: Any, *, occurrence: int) -> tuple[Any | None, int]:
    found = doc.findFirst(descriptor)
    if not found:
        return None, 0

    matched = 1
    while matched < occurrence:
        found = doc.findNext(found.getEnd(), descriptor)
        if not found:
            return None, matched
        matched += 1

    return found, matched


def _replace_text_global(doc: Any, *, find_text: str, replacement: str) -> dict[str, Any]:
    descriptor = doc.createReplaceDescriptor()
    descriptor.SearchString = find_text
    descriptor.ReplaceString = replacement
    replaced = int(doc.replaceAll(descriptor))

    return {
        "status": "applied" if replaced > 0 else "not_found",
        "strategy_used": "replace_text_global",
        "replaced_count": replaced,
    }


def _replace_text_once(doc: Any, *, find_text: str, replacement: str, occurrence: int) -> dict[str, Any]:
    if occurrence < 1:
        raise ValueError(f"replace_text_once occurrence must be >= 1; got {occurrence}")

    descriptor = doc.createSearchDescriptor()
    descriptor.SearchString = find_text

    target, matched = _find_nth_occurrence(doc, descriptor, occurrence=occurrence)
    if target is None:
        return {
            "status": "not_found",
            "strategy_used": "replace_text_once",
            "replaced_count": 0,
            "matched_occurrences": matched,
            "requested_occurrence": occurrence,
        }

    target.setString(replacement)
    return {
        "status": "applied",
        "strategy_used": "replace_text_once",
        "replaced_count": 1,
        "matched_occurrences": matched,
        "requested_occurrence": occurrence,
    }


def _replace_span_once(
    doc: Any,
    *,
    find_text: str,
    occurrence: int,
    span_start: int,
    span_length: int,
    replacement: str,
) -> dict[str, Any]:
    if occurrence < 1:
        raise ValueError(f"replace_span_once occurrence must be >= 1; got {occurrence}")
    if span_start < 0 or span_length < 0:
        raise ValueError(f"replace_span_once span values must be >= 0; got start={span_start}, length={span_length}")

    descriptor = doc.createSearchDescriptor()
    descriptor.SearchString = find_text

    target, matched = _find_nth_occurrence(doc, descriptor, occurrence=occurrence)
    if target is None:
        return {
            "status": "not_found",
            "strategy_used": "replace_span_once",
            "replaced_count": 0,
            "matched_occurrences": matched,
            "requested_occurrence": occurrence,
        }

    matched_text = target.getString()
    if span_start > len(matched_text) or span_start + span_length > len(matched_text):
        return {
            "status": "invalid_span",
            "strategy_used": "replace_span_once",
            "replaced_count": 0,
            "matched_occurrences": matched,
            "requested_occurrence": occurrence,
            "matched_text_length": len(matched_text),
        }

    text_obj = target.getText()
    cursor = text_obj.createTextCursorByRange(target.getStart())
    if span_start > 0:
        cursor.goRight(span_start, False)
    if span_length > 0:
        cursor.goRight(span_length, True)
    cursor.setString(replacement)

    return {
        "status": "applied",
        "strategy_used": "replace_span_once",
        "replaced_count": 1,
        "matched_occurrences": matched,
        "requested_occurrence": occurrence,
    }


def _apply_operation(doc: Any, op: dict[str, Any]) -> dict[str, Any]:
    op_type = str(op.get("type"))

    if op_type == "replace_text_global":
        find_text = str(op["find"])
        replacement = str(op["replace"])
        details = _replace_text_global(doc, find_text=find_text, replacement=replacement)
        details.update(
            {
                "type": op_type,
                "find": find_text,
                "replace": replacement,
            }
        )
        return details

    if op_type == "replace_text_once":
        find_text = str(op["find"])
        replacement = str(op["replace"])
        occurrence = int(op.get("occurrence", 1))
        details = _replace_text_once(
            doc,
            find_text=find_text,
            replacement=replacement,
            occurrence=occurrence,
        )
        details.update(
            {
                "type": op_type,
                "find": find_text,
                "replace": replacement,
                "occurrence": occurrence,
            }
        )
        return details

    if op_type == "replace_paragraph_text":
        expected_text = op.get("expected_text")
        if expected_text is None:
            raise ValueError("UNO replace_paragraph_text requires expected_text for fallback matching")
        replacement = str(op.get("new_text", ""))
        occurrence = int(op.get("occurrence", 1))
        details = _replace_text_once(
            doc,
            find_text=str(expected_text),
            replacement=replacement,
            occurrence=occurrence,
        )
        details.update(
            {
                "type": op_type,
                "find": str(expected_text),
                "replace": replacement,
                "occurrence": occurrence,
                "strategy_used": "replace_paragraph_text_once",
            }
        )
        return details

    if op_type == "replace_span_once":
        find_text = str(op["find"])
        occurrence = int(op.get("occurrence", 1))
        span_start = int(op["span_start"])
        span_length = int(op["span_length"])
        replacement = str(op.get("replacement", ""))
        details = _replace_span_once(
            doc,
            find_text=find_text,
            occurrence=occurrence,
            span_start=span_start,
            span_length=span_length,
            replacement=replacement,
        )
        details.update(
            {
                "type": op_type,
                "find": find_text,
                "occurrence": occurrence,
                "span_start": span_start,
                "span_length": span_length,
                "replacement": replacement,
            }
        )
        return details

    raise ValueError(f"Unsupported UNO operation type: {op_type!r}")


def _apply_replace_ops(doc: Any, operations: list[dict[str, Any]]) -> tuple[int, list[dict[str, Any]]]:
    total = 0
    operation_results: list[dict[str, Any]] = []

    for index, op in enumerate(operations):
        result = _apply_operation(doc, op)
        replaced = int(result.get("replaced_count", 0))
        total += replaced
        operation_results.append(
            {
                "index": index,
                "type": str(op.get("type")),
                "requested": op,
                **result,
            }
        )

    return total, operation_results


def run(docx_path: Path, patch_data: dict[str, Any], author: str, track_changes: bool) -> dict[str, Any]:
    operations = patch_data.get("operations")
    if not isinstance(operations, list) or not operations:
        raise ValueError("Patch must include non-empty operations list")

    port = random.randint(21000, 29999)

    with tempfile.TemporaryDirectory(prefix="wordmark_uno_profile_") as profile_dir:
        profile_uri = Path(profile_dir).as_uri()
        soffice_cmd = [
            "soffice",
            f"-env:UserInstallation={profile_uri}",
            "--headless",
            "--nologo",
            "--nodefault",
            "--nolockcheck",
            "--norestore",
            f"--accept=socket,host=127.0.0.1,port={port};urp;StarOffice.ServiceManager",
        ]
        proc = subprocess.Popen(soffice_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            ctx = _connect(port)
            smgr = ctx.ServiceManager
            desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
            file_url = uno.systemPathToFileUrl(str(docx_path.resolve()))
            doc = desktop.loadComponentFromURL(file_url, "_blank", 0, tuple())

            track_status = _configure_track_changes(doc, track_changes=track_changes)
            author_binding = _bind_author_metadata(doc, author=author)

            replaced_count, operation_results = _apply_replace_ops(doc, operations)
            props = (_prop("FilterName", "MS Word 2007 XML"),)
            doc.storeToURL(file_url, props)
            if hasattr(doc, "close"):
                doc.close(True)

            if hasattr(desktop, "terminate"):
                desktop.terminate()

            operations_with_hits = sum(1 for item in operation_results if int(item.get("replaced_count", 0)) > 0)
            operations_without_hits = len(operation_results) - operations_with_hits

            return {
                "changed": replaced_count > 0,
                "replaced_count": replaced_count,
                "author": author,
                "track_changes": bool(track_changes),
                "track_changes_status": track_status,
                "author_binding_status": author_binding,
                "operations": operations,
                "operation_results": operation_results,
                "summary": {
                    "requested_operations": len(operations),
                    "operations_with_hits": operations_with_hits,
                    "operations_without_hits": operations_without_hits,
                },
            }
        finally:
            try:
                proc.terminate()
                proc.wait(timeout=8)
            except Exception:
                proc.kill()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--docx", required=True)
    parser.add_argument("--patch", required=True)
    parser.add_argument("--author", required=True)
    parser.add_argument("--track-changes", choices=["on", "off"], default="on")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    patch_data = json.loads(Path(args.patch).read_text(encoding="utf-8"))
    result = run(
        Path(args.docx),
        patch_data,
        author=args.author,
        track_changes=(args.track_changes == "on"),
    )
    Path(args.output).write_text(json.dumps(result, ensure_ascii=True), encoding="utf-8")


if __name__ == "__main__":
    main()
