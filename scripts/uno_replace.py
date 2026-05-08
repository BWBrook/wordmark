#!/usr/bin/env python3
"""Compatibility wrapper for the packaged UNO helper."""

from __future__ import annotations

from pathlib import Path
import runpy
import sys


def main() -> None:
    helper = Path(__file__).resolve().parents[1] / "src" / "wordmark" / "_resources" / "uno_replace.py"
    if not helper.exists():
        sys.stderr.write(f"Packaged UNO helper not found: {helper}\n")
        raise SystemExit(1)
    runpy.run_path(str(helper), run_name="__main__")


if __name__ == "__main__":
    main()
