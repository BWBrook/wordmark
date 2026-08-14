from __future__ import annotations

from pathlib import Path
import shutil

from docx import Document
from lxml import etree
import pytest

from wordmark.constants import NSMAP, W_NS
from wordmark.docx_package import DocxPackage
from wordmark import ooxml_engine


DOC_PART = "word/document.xml"
SETTINGS_PART = "word/settings.xml"
M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"


def _w(local: str) -> str:
    return f"{{{W_NS}}}{local}"


def _w_attr(local: str) -> str:
    return f"{{{W_NS}}}{local}"


def _run(text: str | None = None) -> etree._Element:
    run = etree.Element(_w("r"))
    if text is not None:
        text_node = etree.SubElement(run, _w("t"))
        text_node.text = text
    return run


def _save_document_root(path: Path, root: etree._Element) -> None:
    pkg = DocxPackage.open(path)
    pkg.write_xml(DOC_PART, root)
    pkg.save(path)


def _canonical(element: etree._Element) -> bytes:
    return etree.tostring(element, method="c14n")


def _tracked_replace(path: Path, find: str, replace: str = "replacement") -> None:
    ooxml_engine.apply_patch(
        path,
        patch_data={"operations": [{"type": "replace_text_once", "find": find, "replace": replace}]},
        author="Barry Brook",
        track_changes=True,
        dry_run=False,
        allow_paragraph_rewrite_tracked=False,
    )


def test_field_bystander_allows_localized_target_and_preserves_field_subtrees(tmp_path: Path) -> None:
    source = Path("examples/canonical/hard_patterns/risk_field_code.docx")
    path = tmp_path / source.name
    shutil.copyfile(source, path)

    before_root = DocxPackage.open(path).read_xml(DOC_PART)
    before_field_nodes = [
        _canonical(node)
        for node in before_root.xpath(
            ".//w:r[w:fldChar or w:instrText]",
            namespaces=NSMAP,
        )
    ]

    preflight = ooxml_engine.preflight_patch(
        path,
        patch_data={
            "operations": [
                {"type": "replace_text_once", "find": "fieldword", "replace": "replacement"}
            ]
        },
        track_changes=True,
        allow_paragraph_rewrite_tracked=False,
    )
    operation = preflight["operations"][0]
    assert operation["classification"] == "safe_localized"
    assert operation["recommended_engine"] == "ooxml"
    assert {"fldChar", "instrText"} <= set(operation["detected_patterns"])

    _tracked_replace(path, "fieldword")

    after_root = DocxPackage.open(path).read_xml(DOC_PART)
    after_field_nodes = [
        _canonical(node)
        for node in after_root.xpath(
            ".//w:r[w:fldChar or w:instrText]",
            namespaces=NSMAP,
        )
    ]
    assert after_field_nodes == before_field_nodes
    assert "replacement token" in ooxml_engine.inspect(path).text_value


def test_target_inside_complex_field_stays_routed_to_uno(tmp_path: Path) -> None:
    path = tmp_path / "target-inside-field.docx"
    doc = Document()
    doc.add_paragraph("placeholder")
    doc.save(path)

    root = DocxPackage.open(path).read_xml(DOC_PART)
    paragraph = root.xpath(".//w:body/w:p", namespaces=NSMAP)[0]
    for child in list(paragraph):
        paragraph.remove(child)
    paragraph.append(_run("Before "))
    begin = _run()
    etree.SubElement(begin, _w("fldChar")).set(_w_attr("fldCharType"), "begin")
    paragraph.append(begin)
    instruction = _run()
    etree.SubElement(instruction, _w("instrText")).text = " DATE "
    paragraph.append(instruction)
    separate = _run()
    etree.SubElement(separate, _w("fldChar")).set(_w_attr("fldCharType"), "separate")
    paragraph.append(separate)
    paragraph.append(_run("fieldword"))
    end = _run()
    etree.SubElement(end, _w("fldChar")).set(_w_attr("fldCharType"), "end")
    paragraph.append(end)
    paragraph.append(_run(" after."))
    _save_document_root(path, root)

    preflight = ooxml_engine.preflight_patch(
        path,
        patch_data={
            "operations": [
                {"type": "replace_text_once", "find": "fieldword", "replace": "replacement"}
            ]
        },
        track_changes=True,
        allow_paragraph_rewrite_tracked=False,
    )
    operation = preflight["operations"][0]
    assert operation["classification"] == "unsupported_high_risk"
    assert operation["reason_code"] == "risky_markup_detected"
    assert operation["recommended_engine"] == "uno"
    assert "complex_field_range" in operation["detected_patterns"]

    with pytest.raises(ooxml_engine.OoxmlUnsupportedOperation, match="complex_field_range"):
        _tracked_replace(path, "fieldword")


@pytest.mark.parametrize("protected_scope", ["complex_field", "comment_range"])
def test_protected_scope_started_in_prior_paragraph_blocks_target(
    tmp_path: Path,
    protected_scope: str,
) -> None:
    path = tmp_path / f"cross-paragraph-{protected_scope}.docx"
    doc = Document()
    doc.add_paragraph("before")
    doc.add_paragraph("target")
    doc.add_paragraph("after")
    doc.save(path)

    root = DocxPackage.open(path).read_xml(DOC_PART)
    paragraphs = root.xpath(".//w:body/w:p", namespaces=NSMAP)
    if protected_scope == "complex_field":
        begin = _run()
        etree.SubElement(begin, _w("fldChar")).set(_w_attr("fldCharType"), "begin")
        paragraphs[0].append(begin)
        end = _run()
        etree.SubElement(end, _w("fldChar")).set(_w_attr("fldCharType"), "end")
        paragraphs[2].insert(0, end)
        expected_pattern = "complex_field_range"
    else:
        start = etree.Element(_w("commentRangeStart"))
        start.set(_w_attr("id"), "7")
        paragraphs[0].append(start)
        end = etree.Element(_w("commentRangeEnd"))
        end.set(_w_attr("id"), "7")
        paragraphs[2].insert(0, end)
        expected_pattern = "comment_range"
    _save_document_root(path, root)

    preflight = ooxml_engine.preflight_patch(
        path,
        patch_data={
            "operations": [
                {"type": "replace_text_once", "find": "target", "replace": "replacement"}
            ]
        },
        track_changes=True,
        allow_paragraph_rewrite_tracked=False,
    )
    operation = preflight["operations"][0]
    assert operation["classification"] == "unsupported_high_risk"
    assert expected_pattern in operation["detected_patterns"]
    with pytest.raises(ooxml_engine.OoxmlUnsupportedOperation, match=expected_pattern):
        _tracked_replace(path, "target")


@pytest.mark.parametrize("special", ["tab", "break"])
def test_special_markup_elsewhere_in_paragraph_allows_safe_target(
    tmp_path: Path,
    special: str,
) -> None:
    path = tmp_path / f"bystander-{special}.docx"
    doc = Document()
    paragraph = doc.add_paragraph()
    special_run = paragraph.add_run("Context")
    if special == "tab":
        special_run.add_tab()
    else:
        special_run.add_break()
    paragraph.add_run(" target")
    doc.save(path)

    preflight = ooxml_engine.preflight_patch(
        path,
        patch_data={
            "operations": [
                {"type": "replace_text_once", "find": "target", "replace": "replacement"}
            ]
        },
        track_changes=True,
        allow_paragraph_rewrite_tracked=False,
    )
    operation = preflight["operations"][0]
    assert operation["classification"] == "safe_localized"
    expected_pattern = "tab" if special == "tab" else "br"
    assert expected_pattern in operation["detected_patterns"]

    _tracked_replace(path, "target")
    assert "replacement" in ooxml_engine.inspect(path).text_value


def test_target_in_run_with_special_markup_stays_blocked(tmp_path: Path) -> None:
    path = tmp_path / "same-run-tab.docx"
    doc = Document()
    run = doc.add_paragraph().add_run()
    run.add_tab()
    run.add_text("target")
    doc.save(path)

    preflight = ooxml_engine.preflight_patch(
        path,
        patch_data={
            "operations": [
                {"type": "replace_text_once", "find": "target", "replace": "replacement"}
            ]
        },
        track_changes=True,
        allow_paragraph_rewrite_tracked=False,
    )
    operation = preflight["operations"][0]
    assert operation["classification"] == "unsupported_high_risk"
    assert operation["recommended_engine"] == "uno"
    assert {"special_run_markup", "tab"} <= set(operation["detected_patterns"])


def test_unsafe_first_duplicate_is_not_skipped_for_safe_later_duplicate(tmp_path: Path) -> None:
    path = tmp_path / "first-duplicate-unsafe.docx"
    doc = Document()
    paragraph = doc.add_paragraph()
    unsafe = paragraph.add_run()
    unsafe.add_break()
    unsafe.add_text("target")
    paragraph.add_run(" then target")
    doc.save(path)

    preflight = ooxml_engine.preflight_patch(
        path,
        patch_data={
            "operations": [
                {"type": "replace_text_once", "find": "target", "replace": "replacement"}
            ]
        },
        track_changes=True,
        allow_paragraph_rewrite_tracked=False,
    )
    assert preflight["operations"][0]["classification"] == "unsupported_high_risk"
    with pytest.raises(ooxml_engine.OoxmlUnsupportedOperation):
        _tracked_replace(path, "target")
    assert ooxml_engine.inspect(path).text_value.count("target") == 2


def test_preflight_simulates_ordered_duplicate_replacements_without_writing(tmp_path: Path) -> None:
    path = tmp_path / "ordered-duplicates.docx"
    doc = Document()
    doc.add_paragraph("target one")
    doc.add_paragraph("target two")
    doc.save(path)
    before = path.read_bytes()
    patch = {
        "operations": [
            {"type": "replace_text_once", "find": "target", "replace": "updated"},
            {"type": "replace_text_once", "find": "target", "replace": "updated"},
        ]
    }

    preflight = ooxml_engine.preflight_patch(
        path,
        patch_data=patch,
        track_changes=False,
        allow_paragraph_rewrite_tracked=False,
    )
    assert [operation["paragraph_index"] for operation in preflight["operations"]] == [0, 1]
    assert [operation["classification"] for operation in preflight["operations"]] == [
        "safe_localized",
        "safe_localized",
    ]
    assert path.read_bytes() == before

    result = ooxml_engine.apply_patch(
        path,
        patch_data=patch,
        author="Barry Brook",
        track_changes=False,
        dry_run=False,
        allow_paragraph_rewrite_tracked=False,
    )
    assert [operation["paragraph_index"] for operation in result.details["operations"]] == [0, 1]
    assert ooxml_engine.inspect(path).text_value.splitlines() == ["updated one", "updated two"]


def test_preflight_simulates_rewrite_before_classifying_later_unsafe_duplicate(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ordered-rewrite-then-unsafe.docx"
    doc = Document()
    first = doc.add_paragraph()
    first.add_run("tar")
    formatted = first.add_run("get")
    formatted.bold = True
    unsafe = doc.add_paragraph().add_run()
    unsafe.add_break()
    unsafe.add_text("target")
    doc.save(path)
    before = path.read_bytes()
    patch = {
        "operations": [
            {"type": "replace_text_once", "find": "target", "replace": "updated"},
            {"type": "replace_text_once", "find": "target", "replace": "updated"},
        ]
    }

    preflight = ooxml_engine.preflight_patch(
        path,
        patch_data=patch,
        track_changes=True,
        allow_paragraph_rewrite_tracked=True,
    )
    first_report, second_report = preflight["operations"]
    assert first_report["paragraph_index"] == 0
    assert first_report["classification"] == "needs_multi_run_localized"
    assert first_report["recommended_engine"] == "ooxml"
    assert first_report["recommended_strategy"] == "paragraph_rewrite"
    assert second_report["paragraph_index"] == 1
    assert second_report["classification"] == "unsupported_high_risk"
    assert second_report["recommended_engine"] == "uno"
    assert path.read_bytes() == before

    with pytest.raises(ooxml_engine.OoxmlUnsupportedOperation):
        ooxml_engine.apply_patch(
            path,
            patch_data=patch,
            author="Barry Brook",
            track_changes=True,
            dry_run=False,
            allow_paragraph_rewrite_tracked=True,
        )
    assert path.read_bytes() == before


def test_compatible_multi_run_plan_is_shared_by_preflight_and_apply(tmp_path: Path) -> None:
    path = tmp_path / "compatible-multi-run.docx"
    doc = Document()
    paragraph = doc.add_paragraph()
    paragraph.add_run("pre tar")
    paragraph.add_run("get post")
    doc.save(path)

    preflight = ooxml_engine.preflight_patch(
        path,
        patch_data={
            "operations": [
                {"type": "replace_text_once", "find": "target", "replace": "replacement"}
            ]
        },
        track_changes=True,
        allow_paragraph_rewrite_tracked=False,
    )
    operation = preflight["operations"][0]
    assert operation["classification"] == "safe_localized"
    assert operation["recommended_strategy"] == "localized_multi_run"

    result = ooxml_engine.apply_patch(
        path,
        patch_data={
            "operations": [
                {"type": "replace_text_once", "find": "target", "replace": "replacement"}
            ]
        },
        author="Barry Brook",
        track_changes=True,
        dry_run=False,
        allow_paragraph_rewrite_tracked=False,
    )
    assert result.details["operations"][0]["strategy"] == "localized_multi_run"


def test_incompatible_multi_run_stays_routed(tmp_path: Path) -> None:
    path = tmp_path / "incompatible-multi-run.docx"
    doc = Document()
    paragraph = doc.add_paragraph()
    paragraph.add_run("tar")
    second = paragraph.add_run("get")
    second.bold = True
    doc.save(path)

    preflight = ooxml_engine.preflight_patch(
        path,
        patch_data={
            "operations": [
                {"type": "replace_text_once", "find": "target", "replace": "replacement"}
            ]
        },
        track_changes=True,
        allow_paragraph_rewrite_tracked=False,
    )
    operation = preflight["operations"][0]
    assert operation["classification"] == "needs_multi_run_localized"
    assert operation["recommended_engine"] == "uno"
    with pytest.raises(ooxml_engine.OoxmlUnsupportedOperation):
        _tracked_replace(path, "target")


def test_tracked_apply_enables_track_revisions_once_and_preserves_settings(tmp_path: Path) -> None:
    path = tmp_path / "track-settings.docx"
    doc = Document()
    doc.add_paragraph("target")
    doc.add_paragraph("second")
    doc.save(path)

    before_root = DocxPackage.open(path).read_xml(SETTINGS_PART)
    before_children = [_canonical(child) for child in before_root]
    _tracked_replace(path, "target")

    after_root = DocxPackage.open(path).read_xml(SETTINGS_PART)
    track_revisions = after_root.findall(_w("trackRevisions"))
    assert len(track_revisions) == 1
    assert track_revisions[0].get(_w_attr("val")) is None
    after_other_children = [
        _canonical(child)
        for child in after_root
        if child.tag != _w("trackRevisions")
    ]
    assert after_other_children == before_children

    _tracked_replace(path, "second", "updated")
    final_root = DocxPackage.open(path).read_xml(SETTINGS_PART)
    assert len(final_root.findall(_w("trackRevisions"))) == 1


def test_existing_disabled_track_revisions_is_normalized(tmp_path: Path) -> None:
    path = tmp_path / "disabled-track-settings.docx"
    doc = Document()
    doc.add_paragraph("target")
    doc.save(path)

    pkg = DocxPackage.open(path)
    settings_root = pkg.read_xml(SETTINGS_PART)
    track_revisions = etree.Element(_w("trackRevisions"))
    track_revisions.set(_w_attr("val"), "0")
    settings_root.insert(0, track_revisions)
    pkg.write_xml(SETTINGS_PART, settings_root)
    pkg.save(path)

    _tracked_replace(path, "target")
    final_root = DocxPackage.open(path).read_xml(SETTINGS_PART)
    elements = final_root.findall(_w("trackRevisions"))
    assert len(elements) == 1
    assert elements[0].get(_w_attr("val")) is None


def test_enabled_track_revisions_settings_part_stays_byte_identical(tmp_path: Path) -> None:
    path = tmp_path / "enabled-track-settings.docx"
    doc = Document()
    doc.add_paragraph("target")
    settings = doc.settings.element
    default_tab_stop = settings.find(_w("defaultTabStop"))
    assert default_tab_stop is not None
    settings.insert(settings.index(default_tab_stop), etree.Element(_w("trackRevisions")))
    doc.save(path)

    before = DocxPackage.open(path).read_part(SETTINGS_PART)
    _tracked_replace(path, "target")
    after = DocxPackage.open(path).read_part(SETTINGS_PART)
    assert after == before


@pytest.mark.parametrize("dry_run,track_changes", [(False, False), (True, True)])
def test_non_tracked_and_dry_run_do_not_enable_track_revisions(
    tmp_path: Path,
    dry_run: bool,
    track_changes: bool,
) -> None:
    path = tmp_path / f"settings-no-enable-{dry_run}-{track_changes}.docx"
    doc = Document()
    doc.add_paragraph("target")
    doc.save(path)

    before = DocxPackage.open(path).read_part(SETTINGS_PART)
    ooxml_engine.apply_patch(
        path,
        patch_data={
            "operations": [
                {"type": "replace_text_once", "find": "target", "replace": "replacement"}
            ]
        },
        author="Barry Brook",
        track_changes=track_changes,
        dry_run=dry_run,
        allow_paragraph_rewrite_tracked=False,
    )
    after_pkg = DocxPackage.open(path)
    assert after_pkg.read_part(SETTINGS_PART) == before
    assert not after_pkg.read_xml(SETTINGS_PART).findall(_w("trackRevisions"))


def test_revision_ids_follow_existing_move_revision_ids(tmp_path: Path) -> None:
    path = tmp_path / "move-revision-id.docx"
    doc = Document()
    doc.add_paragraph("target")
    doc.save(path)

    root = DocxPackage.open(path).read_xml(DOC_PART)
    paragraph = root.xpath(".//w:body/w:p", namespaces=NSMAP)[0]
    move_to = etree.Element(_w("moveTo"))
    move_to.set(_w_attr("id"), "40")
    move_to.append(_run("moved "))
    paragraph.insert(0, move_to)
    _save_document_root(path, root)

    _tracked_replace(path, "target")
    final_root = DocxPackage.open(path).read_xml(DOC_PART)
    inserted_ids = final_root.xpath(".//w:ins/@w:id", namespaces=NSMAP)
    deleted_ids = final_root.xpath(".//w:del/@w:id", namespaces=NSMAP)
    assert deleted_ids == ["41"]
    assert inserted_ids == ["42"]


def test_revision_ids_follow_property_change_ids(tmp_path: Path) -> None:
    path = tmp_path / "property-change-ids.docx"
    doc = Document()
    doc.add_paragraph("formatting metadata")
    doc.add_paragraph("target")
    doc.save(path)

    root = DocxPackage.open(path).read_xml(DOC_PART)
    paragraphs = root.xpath(".//w:body/w:p", namespaces=NSMAP)
    ppr = etree.Element(_w("pPr"))
    ppr_change = etree.SubElement(ppr, _w("pPrChange"))
    ppr_change.set(_w_attr("id"), "80")
    paragraphs[0].insert(0, ppr)
    first_run = paragraphs[0].find(_w("r"))
    assert first_run is not None
    rpr = etree.Element(_w("rPr"))
    rpr_change = etree.SubElement(rpr, _w("rPrChange"))
    rpr_change.set(_w_attr("id"), "90")
    first_run.insert(0, rpr)
    _save_document_root(path, root)

    _tracked_replace(path, "target")
    final_root = DocxPackage.open(path).read_xml(DOC_PART)
    assert final_root.xpath(".//w:del/@w:id", namespaces=NSMAP) == ["91"]
    assert final_root.xpath(".//w:ins/@w:id", namespaces=NSMAP) == ["92"]


@pytest.mark.parametrize(
    "child_names,expected_names",
    [
        (
            ["compat", "rsids", "mathPr", "themeFontLang"],
            ["trackRevisions", "compat", "rsids", "mathPr", "themeFontLang"],
        ),
        (
            ["zoom", "proofState", "compat", "rsids"],
            ["zoom", "proofState", "trackRevisions", "compat", "rsids"],
        ),
    ],
)
def test_track_revisions_uses_schema_predecessor_prefix(
    tmp_path: Path,
    child_names: list[str],
    expected_names: list[str],
) -> None:
    path = tmp_path / f"settings-order-{'-'.join(child_names)}.docx"
    doc = Document()
    doc.add_paragraph("target")
    doc.save(path)

    pkg = DocxPackage.open(path)
    settings_root = pkg.read_xml(SETTINGS_PART)
    for child in list(settings_root):
        settings_root.remove(child)
    for name in child_names:
        tag = f"{{{M_NS}}}mathPr" if name == "mathPr" else _w(name)
        settings_root.append(etree.Element(tag))
    pkg.write_xml(SETTINGS_PART, settings_root)
    pkg.save(path)

    _tracked_replace(path, "target")
    final_root = DocxPackage.open(path).read_xml(SETTINGS_PART)
    final_names = [etree.QName(child).localname for child in final_root]
    assert final_names == expected_names
