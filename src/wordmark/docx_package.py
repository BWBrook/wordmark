"""Low-level DOCX package utilities with byte-preserving behavior for untouched parts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import zipfile

from lxml import etree


@dataclass(slots=True)
class DocxPackage:
    """In-memory DOCX ZIP parts.

    Untouched parts remain byte-identical; only explicitly written parts are
    re-serialized.
    """

    parts: dict[str, bytes]

    @classmethod
    def open(cls, path: Path) -> "DocxPackage":
        with zipfile.ZipFile(path, "r") as zf:
            parts = {name: zf.read(name) for name in zf.namelist()}
        return cls(parts=parts)

    def has_part(self, name: str) -> bool:
        return name in self.parts

    def read_part(self, name: str) -> bytes:
        if name not in self.parts:
            raise FileNotFoundError(f"DOCX part not found: {name}")
        return self.parts[name]

    def write_part(self, name: str, payload: bytes) -> None:
        self.parts[name] = payload

    def read_xml(self, name: str) -> etree._Element:
        payload = self.read_part(name)
        parser = etree.XMLParser(remove_blank_text=False, recover=False)
        return etree.fromstring(payload, parser=parser)

    def write_xml(self, name: str, root: etree._Element) -> None:
        payload = etree.tostring(
            root,
            xml_declaration=True,
            encoding="UTF-8",
            pretty_print=False,
        )
        self.write_part(name, payload)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for part_name in sorted(self.parts.keys()):
                zf.writestr(part_name, self.parts[part_name])
