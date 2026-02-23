"""UNO fallback engine bridge.

This module delegates to a system-Python UNO script so the main CLI can run in
an isolated uv environment even when `uno` is unavailable there.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any

from wordmark.models import OperationResult


class UnoEngineError(RuntimeError):
    """Raised when UNO fallback execution fails."""


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
        return OperationResult.now(
            command="edit apply",
            path=path,
            engine="uno",
            changed=bool(payload.get("changed", False)),
            author=author,
            details={
                "dry_run": False,
                "fallback_reason": fallback_reason,
                "uno": payload,
            },
        )
