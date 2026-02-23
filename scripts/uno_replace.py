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


def _apply_replace_ops(doc: Any, operations: list[dict[str, Any]]) -> int:
    total = 0
    for op in operations:
        if op.get("type") != "replace_text_global":
            raise ValueError(f"UNO helper only supports replace_text_global; got {op.get('type')!r}")
        find_text = str(op["find"])
        replacement = str(op["replace"])
        descriptor = doc.createReplaceDescriptor()
        descriptor.SearchString = find_text
        descriptor.ReplaceString = replacement
        replaced = int(doc.replaceAll(descriptor))
        total += replaced
    return total


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

            if track_changes and _supports_track_changes(doc):
                doc.RecordChanges = True
            if hasattr(doc, "CurrentController") and hasattr(doc.CurrentController, "ViewSettings"):
                view = doc.CurrentController.ViewSettings
                if hasattr(view, "ShowTrackedChanges"):
                    view.ShowTrackedChanges = True

            replaced_count = _apply_replace_ops(doc, operations)
            props = (_prop("FilterName", "MS Word 2007 XML"),)
            doc.storeToURL(file_url, props)
            if hasattr(doc, "close"):
                doc.close(True)

            if hasattr(desktop, "terminate"):
                desktop.terminate()

            return {
                "changed": replaced_count > 0,
                "replaced_count": replaced_count,
                "author": author,
                "track_changes": bool(track_changes),
                "operations": operations,
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
