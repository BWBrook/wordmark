"""Environment probes for optional external command-line integrations."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess


def binary_path(name: str) -> str | None:
    return shutil.which(name)


def binary_available(name: str) -> bool:
    return binary_path(name) is not None


def missing_binaries(*names: str) -> list[str]:
    return [name for name in names if not binary_available(name)]


def render_tools_available() -> bool:
    return not missing_binaries("soffice", "pdftoppm")


def quarto_available() -> bool:
    return binary_available("quarto")


def gh_available() -> bool:
    return binary_available("gh")


def gh_auth_available(*, cwd: Path | None = None) -> bool:
    if not gh_available():
        return False
    proc = subprocess.run(
        ["gh", "auth", "status", "-h", "github.com"],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


def system_uno_available() -> bool:
    python_bin = Path("/usr/bin/python3")
    if not python_bin.exists():
        return False
    proc = subprocess.run(
        [str(python_bin), "-c", "import uno"],
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0
