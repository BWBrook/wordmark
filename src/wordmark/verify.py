"""Verification gates for DOCX integrity and render fidelity."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import tempfile
from typing import Any

from PIL import Image, ImageChops

from wordmark.config import AppConfig
from wordmark.constants import NSMAP, W_NS
from wordmark.docx_package import DocxPackage
from wordmark.render import render_docx
from wordmark.sidecar import hash_bytes

DOC_PART = "word/document.xml"
COMMENTS_PART = "word/comments.xml"


@dataclass(slots=True)
class VerifyResult:
    passed: bool
    profile: str
    checks: dict[str, Any]


def _w(local: str) -> str:
    return f"{{{W_NS}}}{local}"


def _comment_integrity(pkg: DocxPackage) -> dict[str, Any]:
    doc_root = pkg.read_xml(DOC_PART)
    doc_ids = set()
    for node in doc_root.xpath(".//w:commentReference | .//w:commentRangeStart | .//w:commentRangeEnd", namespaces=NSMAP):
        raw = node.get(_w("id"))
        if raw is not None:
            doc_ids.add(raw)

    comment_ids = set()
    if pkg.has_part(COMMENTS_PART):
        comments_root = pkg.read_xml(COMMENTS_PART)
        for c in comments_root.findall(_w("comment")):
            cid = c.get(_w("id"))
            if cid is not None:
                comment_ids.add(cid)

    orphan_doc_refs = sorted(doc_ids - comment_ids)
    unreferenced_comments = sorted(comment_ids - doc_ids)
    ok = len(orphan_doc_refs) == 0

    return {
        "ok": ok,
        "doc_ref_count": len(doc_ids),
        "comment_count": len(comment_ids),
        "orphan_doc_refs": orphan_doc_refs,
        "unreferenced_comments": unreferenced_comments,
    }


def _revision_stats(pkg: DocxPackage) -> dict[str, int]:
    doc_root = pkg.read_xml(DOC_PART)
    inserted = len(doc_root.xpath(".//w:ins", namespaces=NSMAP))
    deleted = len(doc_root.xpath(".//w:del", namespaces=NSMAP))
    return {"ins": inserted, "del": deleted}


def _page_diff_ratio(before_png: Path, after_png: Path, *, diff_output: Path | None = None) -> float:
    with Image.open(before_png) as a, Image.open(after_png) as b:
        if a.size != b.size:
            b = b.resize(a.size)
        diff = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
        if diff_output is not None:
            diff_output.parent.mkdir(parents=True, exist_ok=True)
            diff.save(diff_output)
        hist = diff.histogram()
        # RGB histogram has 256 bins per channel
        sq = 0
        for channel in range(3):
            base = channel * 256
            for idx in range(256):
                sq += hist[base + idx] * idx
        max_possible = a.size[0] * a.size[1] * 255 * 3
        if max_possible == 0:
            return 0.0
        return float(sq) / float(max_possible)


def _render_diff(
    before_docx: Path,
    after_docx: Path,
    threshold: float,
    *,
    persist_dir: Path | None = None,
) -> dict[str, Any]:
    if persist_dir is not None:
        persist_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="wordmark_verify_render_") as tmpdir:
        tmp = Path(tmpdir)
        before_out = render_docx(before_docx, tmp / "before")
        after_out = render_docx(after_docx, tmp / "after")

        before_pages = before_out.png_paths
        after_pages = after_out.png_paths
        page_count_match = len(before_pages) == len(after_pages)

        diffs: list[dict[str, Any]] = []
        pair_count = min(len(before_pages), len(after_pages))
        for idx in range(pair_count):
            before_page = before_pages[idx]
            after_page = after_pages[idx]
            diff_page = None
            before_copy = None
            after_copy = None
            if persist_dir is not None:
                before_copy = persist_dir / f"before-page-{idx + 1}.png"
                after_copy = persist_dir / f"after-page-{idx + 1}.png"
                shutil.copy2(before_page, before_copy)
                shutil.copy2(after_page, after_copy)
                diff_page = persist_dir / f"diff-page-{idx + 1}.png"

            ratio = _page_diff_ratio(before_page, after_page, diff_output=diff_page)
            diffs.append(
                {
                    "page": idx + 1,
                    "ratio": ratio,
                    "pass": ratio <= threshold,
                    "before_page": str(before_copy) if before_copy else None,
                    "after_page": str(after_copy) if after_copy else None,
                    "diff_page": str(diff_page) if diff_page else None,
                }
            )

        pass_all = page_count_match and all(item["pass"] for item in diffs)
        return {
            "ok": pass_all,
            "threshold": threshold,
            "page_count_match": page_count_match,
            "before_pages": len(before_pages),
            "after_pages": len(after_pages),
            "per_page": diffs,
        }


def verify_docx(
    before: Path,
    after: Path,
    *,
    profile: str,
    config: AppConfig,
    persist_render_dir: Path | None = None,
) -> VerifyResult:
    if profile not in config.fidelity_profiles:
        raise ValueError(f"Unknown fidelity profile {profile!r}; configured={config.fidelity_profiles}")

    before_pkg = DocxPackage.open(before)
    after_pkg = DocxPackage.open(after)

    key_parts = [DOC_PART, COMMENTS_PART, "word/styles.xml", "word/numbering.xml"]
    manifest = []
    for part in key_parts:
        manifest.append(
            {
                "part": part,
                "before_present": before_pkg.has_part(part),
                "after_present": after_pkg.has_part(part),
                "before_sha256": hash_bytes(before_pkg.read_part(part)) if before_pkg.has_part(part) else None,
                "after_sha256": hash_bytes(after_pkg.read_part(part)) if after_pkg.has_part(part) else None,
            }
        )

    comment_integrity = _comment_integrity(after_pkg)
    before_revs = _revision_stats(before_pkg)
    after_revs = _revision_stats(after_pkg)

    threshold = 0.02 if profile == "business-docs" else 0.05
    render_diff = _render_diff(before, after, threshold, persist_dir=persist_render_dir)

    checks = {
        "profile": profile,
        "manifest": manifest,
        "comment_integrity": comment_integrity,
        "revisions": {
            "before": before_revs,
            "after": after_revs,
            "delta": {
                "ins": after_revs["ins"] - before_revs["ins"],
                "del": after_revs["del"] - before_revs["del"],
            },
        },
        "render_diff": render_diff,
    }

    passed = bool(comment_integrity["ok"] and render_diff["ok"])
    return VerifyResult(passed=passed, profile=profile, checks=checks)


def dumps(result: VerifyResult) -> str:
    return json.dumps(
        {
            "passed": result.passed,
            "profile": result.profile,
            "checks": result.checks,
        },
        indent=2,
        ensure_ascii=True,
        sort_keys=True,
    )
