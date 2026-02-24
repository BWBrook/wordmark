"""UNO fallback engine bridge.

This module delegates to a system-Python UNO script so the main CLI can run in
an isolated uv environment even when `uno` is unavailable there.
"""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any

from wordmark.constants import NSMAP, W_NS
from wordmark.docx_package import DocxPackage
from wordmark.models import OperationResult

DOC_PART = "word/document.xml"


class UnoEngineError(RuntimeError):
    """Raised when UNO fallback execution fails."""


def _w(local: str) -> str:
    return f"{{{W_NS}}}{local}"


def _revision_text(element: Any) -> str:
    parts = element.xpath(".//w:t/text() | .//w:delText/text()", namespaces=NSMAP)
    return "".join(parts)


def _revision_signature(element: Any) -> tuple[str, str | None, str | None, str]:
    return (
        str(element.tag),
        element.get(_w("id")),
        element.get(_w("date")),
        _revision_text(element),
    )


def _capture_revision_counter(path: Path) -> Counter[tuple[str, str | None, str | None, str]]:
    pkg = DocxPackage.open(path)
    root = pkg.read_xml(DOC_PART)
    revisions = root.xpath(".//w:ins | .//w:del", namespaces=NSMAP)
    return Counter(_revision_signature(item) for item in revisions)


def _normalize_unknown_revision_authors(
    path: Path,
    *,
    requested_author: str,
    before_counter: Counter[tuple[str, str | None, str | None, str]],
) -> dict[str, Any]:
    pkg = DocxPackage.open(path)
    root = pkg.read_xml(DOC_PART)
    revisions = root.xpath(".//w:ins | .//w:del", namespaces=NSMAP)

    working_counter = Counter(before_counter)
    normalized = 0
    untouched_unknown = 0
    new_revision_count = 0

    for revision in revisions:
        signature = _revision_signature(revision)
        if working_counter[signature] > 0:
            working_counter[signature] -= 1
            continue

        new_revision_count += 1
        author = revision.get(_w("author"))
        if author in {None, "", "Unknown Author"}:
            revision.set(_w("author"), requested_author)
            normalized += 1

    for revision in revisions:
        author = revision.get(_w("author"))
        if author in {None, "", "Unknown Author"}:
            untouched_unknown += 1

    if normalized > 0:
        pkg.write_xml(DOC_PART, root)
        pkg.save(path)

    return {
        "requested_author": requested_author,
        "new_revision_count": new_revision_count,
        "normalized_unknown_authors": normalized,
        "remaining_unknown_authors": untouched_unknown,
        "normalized": normalized > 0,
    }


def apply_patch(
    path: Path,
    *,
    patch_data: dict[str, Any],
    author: str,
    track_changes: bool,
    dry_run: bool,
    fallback_reason: str,
) -> OperationResult:
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "uno_replace.py"
    if not script_path.exists():
        raise UnoEngineError(f"UNO helper script missing: {script_path}")

    if dry_run:
        return OperationResult.now(
            command="edit apply",
            path=path,
            engine="uno",
            changed=False,
            author=author,
            details={
                "dry_run": True,
                "fallback_reason": fallback_reason,
                "operations": patch_data.get("operations", []),
            },
        )

    before_counter = Counter()
    if track_changes:
        before_counter = _capture_revision_counter(path)

    with tempfile.TemporaryDirectory(prefix="wordmark_uno_") as tmpdir:
        patch_path = Path(tmpdir) / "patch.json"
        out_path = Path(tmpdir) / "result.json"
        patch_path.write_text(json.dumps(patch_data, ensure_ascii=True), encoding="utf-8")

        python_bin = Path("/usr/bin/python3")
        if not python_bin.exists():
            resolved = shutil.which("python3")
            if resolved is None:
                raise UnoEngineError("No python3 interpreter available for UNO fallback script")
            python_bin = Path(resolved)

        cmd = [
            str(python_bin),
            str(script_path),
            "--docx",
            str(path),
            "--patch",
            str(patch_path),
            "--author",
            author,
            "--track-changes",
            "on" if track_changes else "off",
            "--output",
            str(out_path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise UnoEngineError(
                "UNO fallback failed\n"
                f"Command: {' '.join(cmd)}\n"
                f"STDOUT:\n{proc.stdout}\n"
                f"STDERR:\n{proc.stderr}"
            )

        payload = json.loads(out_path.read_text(encoding="utf-8"))

    postprocess: dict[str, Any] | None = None
    if track_changes and bool(payload.get("changed", False)):
        postprocess = _normalize_unknown_revision_authors(
            path,
            requested_author=author,
            before_counter=before_counter,
        )

    details: dict[str, Any] = {
        "dry_run": False,
        "fallback_reason": fallback_reason,
        "uno": payload,
    }
    if postprocess is not None:
        details["author_binding_postprocess"] = postprocess

    return OperationResult.now(
        command="edit apply",
        path=path,
        engine="uno",
        changed=bool(payload.get("changed", False)),
        author=author,
        details=details,
    )
