"""UNO fallback engine bridge.

This module delegates to a system-Python UNO script so the main CLI can run in
an isolated uv environment even when `uno` is unavailable there.
"""

from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from importlib.resources import as_file, files
import json
import os
import platform
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any

from wordmark.constants import NSMAP, W_NS
from wordmark.docx_package import DocxPackage
from wordmark.external_tools import binary_path
from wordmark.models import OperationResult

DOC_PART = "word/document.xml"
_REVISION_SELECTOR = ".//w:ins | .//w:del | .//w:moveTo | .//w:moveFrom"
_REVISION_TYPE_BY_TAG = {
    f"{{{W_NS}}}ins": "insert",
    f"{{{W_NS}}}del": "delete",
    f"{{{W_NS}}}moveTo": "move_to",
    f"{{{W_NS}}}moveFrom": "move_from",
}


class UnoEngineError(RuntimeError):
    """Raised when UNO fallback execution fails."""


@contextmanager
def _helper_script_path():
    """Yield a filesystem path to the packaged UNO helper script."""
    try:
        resource = files("wordmark._resources").joinpath("uno_replace.py")
        with as_file(resource) as helper_path:
            if helper_path.exists():
                yield helper_path
                return
    except (FileNotFoundError, ModuleNotFoundError) as exc:
        raise UnoEngineError("Packaged UNO helper resource is unavailable") from exc
    raise UnoEngineError("Packaged UNO helper resource is unavailable")


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
    revisions = root.xpath(_REVISION_SELECTOR, namespaces=NSMAP)
    return Counter(_revision_signature(item) for item in revisions)


def _normalize_unknown_revision_authors(
    path: Path,
    *,
    requested_author: str,
    before_counter: Counter[tuple[str, str | None, str | None, str]],
) -> dict[str, Any]:
    pkg = DocxPackage.open(path)
    root = pkg.read_xml(DOC_PART)
    revisions = root.xpath(_REVISION_SELECTOR, namespaces=NSMAP)

    working_counter = Counter(before_counter)
    normalized = 0
    untouched_unknown = 0
    new_revision_count = 0
    new_revision_type_counts: Counter[str] = Counter()
    normalized_by_type: Counter[str] = Counter()
    remaining_unknown_by_type: Counter[str] = Counter()

    for revision in revisions:
        revision_type = _REVISION_TYPE_BY_TAG.get(str(revision.tag), "unknown")
        signature = _revision_signature(revision)
        if working_counter[signature] > 0:
            working_counter[signature] -= 1
            continue

        new_revision_count += 1
        new_revision_type_counts[revision_type] += 1
        author = revision.get(_w("author"))
        if author in {None, "", "Unknown Author"}:
            revision.set(_w("author"), requested_author)
            normalized += 1
            normalized_by_type[revision_type] += 1

    for revision in revisions:
        revision_type = _REVISION_TYPE_BY_TAG.get(str(revision.tag), "unknown")
        author = revision.get(_w("author"))
        if author in {None, "", "Unknown Author"}:
            untouched_unknown += 1
            remaining_unknown_by_type[revision_type] += 1

    if normalized > 0:
        pkg.write_xml(DOC_PART, root)
        pkg.save(path)

    return {
        "requested_author": requested_author,
        "new_revision_count": new_revision_count,
        "new_revision_type_counts": {
            "insert": int(new_revision_type_counts.get("insert", 0)),
            "delete": int(new_revision_type_counts.get("delete", 0)),
            "move_to": int(new_revision_type_counts.get("move_to", 0)),
            "move_from": int(new_revision_type_counts.get("move_from", 0)),
        },
        "normalized_unknown_authors": normalized,
        "normalized_unknown_by_type": {
            "insert": int(normalized_by_type.get("insert", 0)),
            "delete": int(normalized_by_type.get("delete", 0)),
            "move_to": int(normalized_by_type.get("move_to", 0)),
            "move_from": int(normalized_by_type.get("move_from", 0)),
        },
        "remaining_unknown_authors": untouched_unknown,
        "remaining_unknown_by_type": {
            "insert": int(remaining_unknown_by_type.get("insert", 0)),
            "delete": int(remaining_unknown_by_type.get("delete", 0)),
            "move_to": int(remaining_unknown_by_type.get("move_to", 0)),
            "move_from": int(remaining_unknown_by_type.get("move_from", 0)),
        },
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
    if platform.system() == "Darwin" and os.getenv("WORDMARK_ENABLE_MACOS_UNO") != "1":
        raise UnoEngineError(
            "UNO fallback is disabled by default on macOS. "
            "Set WORDMARK_ENABLE_MACOS_UNO=1 only if you are intentionally experimenting with LibreOffice's embedded Python."
        )

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

        resolved_uno_python = binary_path("libreoffice_python")
        if resolved_uno_python is not None:
            python_bin = Path(resolved_uno_python)
        else:
            python_bin = Path("/usr/bin/python3")
            if not python_bin.exists():
                resolved = shutil.which("python3")
                if resolved is None:
                    raise UnoEngineError("No python3 interpreter available for UNO fallback script")
                python_bin = Path(resolved)

        with _helper_script_path() as script_path:
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
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            except subprocess.TimeoutExpired as exc:
                raise UnoEngineError(
                    "UNO fallback timed out\n"
                    f"Command: {' '.join(cmd)}\n"
                    f"STDOUT:\n{exc.stdout or ''}\n"
                    f"STDERR:\n{exc.stderr or ''}"
                ) from exc
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
