from __future__ import annotations

import zipfile
from pathlib import Path

from zivo.services.browser_snapshot import LiveBrowserSnapshotLoader
from zivo.services.previews import (
    FilePreviewState,
    OfficeDocumentPreviewLoader,
    PreviewResourceBudget,
)

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _write_package(path: Path, members: dict[str, str | bytes]) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)


def _docx_package(*, body: str) -> dict[str, str]:
    return {
        "word/document.xml": (
            f'<w:document xmlns:w="{W_NS}"><w:body>{body}</w:body></w:document>'
        )
    }


def test_office_loader_extracts_docx_paragraphs_tabs_and_tables(tmp_path: Path) -> None:
    report = tmp_path / "report.docx"
    _write_package(
        report,
        _docx_package(
            body=(
                "<w:p><w:r><w:t>Plan</w:t><w:tab/><w:t>2026</w:t></w:r></w:p>"
                "<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Item</w:t></w:r></w:p></w:tc>"
                "<w:tc><w:p><w:r><w:t>Amount</w:t></w:r></w:p></w:tc></w:tr></w:tbl>"
            )
        ),
    )

    preview = OfficeDocumentPreviewLoader().load_preview(report, preview_max_bytes=64 * 1024)

    assert preview == FilePreviewState.with_content("Plan\t2026\nItem | Amount\n", False)


def test_office_loader_extracts_xlsx_sheet_order_cells_and_formula_cache(tmp_path: Path) -> None:
    workbook = tmp_path / "sales.xlsx"
    _write_package(
        workbook,
        {
            "xl/workbook.xml": (
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<sheets><sheet name="Sales" r:id="rId2"/><sheet name="Notes" r:id="rId1"/>'
                "</sheets></workbook>"
            ),
            "xl/_rels/workbook.xml.rels": (
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Target="worksheets/notes.xml" Type="worksheet"/>'
                '<Relationship Id="rId2" Target="worksheets/sales.xml" Type="worksheet"/>'
                "</Relationships>"
            ),
            "xl/sharedStrings.xml": (
                '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                "<si><t>Product</t></si></sst>"
            ),
            "xl/worksheets/sales.xml": (
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                "<sheetData><row><c r=\"A1\" t=\"s\"><v>0</v></c>"
                '<c r="B1"><f>SUM(C1:C2)</f><v>3</v></c></row></sheetData></worksheet>'
            ),
            "xl/worksheets/notes.xml": (
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                '<sheetData><row><c r="A1" t="inlineStr"><is><t>Draft</t></is></c>'
                "</row></sheetData></worksheet>"
            ),
        },
    )

    preview = OfficeDocumentPreviewLoader().load_preview(workbook, preview_max_bytes=64 * 1024)

    assert preview is not None
    assert preview.content == (
        "[Sheet: Sales]\n"
        "A1 = Product\n"
        "B1 = =SUM(C1:C2) (cached: 3)\n"
        "[Sheet: Notes]\n"
        "A1 = Draft\n"
    )


def test_office_loader_uses_pptx_relationship_order_not_zip_order(tmp_path: Path) -> None:
    presentation = tmp_path / "plan.pptx"
    _write_package(
        presentation,
        {
            "ppt/presentation.xml": (
                '<p:presentation '
                'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<p:sldIdLst><p:sldId id="1" r:id="second"/><p:sldId id="2" r:id="first"/>'
                "</p:sldIdLst></p:presentation>"
            ),
            "ppt/_rels/presentation.xml.rels": (
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="first" Target="slides/slide1.xml" Type="slide"/>'
                '<Relationship Id="second" Target="slides/slide2.xml" Type="slide"/>'
                "</Relationships>"
            ),
            "ppt/slides/slide1.xml": (
                '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
                'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
                "<p:cSld><a:p><a:r><a:t>First</a:t></a:r></a:p></p:cSld></p:sld>"
            ),
            "ppt/slides/slide2.xml": (
                '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
                'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
                "<p:cSld><a:p><a:r><a:t>Second</a:t></a:r></a:p></p:cSld></p:sld>"
            ),
        },
    )

    preview = OfficeDocumentPreviewLoader().load_preview(presentation, preview_max_bytes=64 * 1024)

    assert preview == FilePreviewState.with_content(
        "[Slide 1]\nSecond\n[Slide 2]\nFirst\n", False
    )


def test_office_loader_marks_output_limit_with_safe_partial_text(tmp_path: Path) -> None:
    report = tmp_path / "report.docx"
    _write_package(report, _docx_package(body="<w:p><w:r><w:t>0123456789</w:t></w:r></w:p>"))

    preview = OfficeDocumentPreviewLoader().load_preview(report, preview_max_bytes=5)

    assert preview is not None
    assert preview.kind == "content"
    assert preview.content == "01234"
    assert preview.truncated is True
    assert preview.reason == "resource_limit"


def test_office_loader_uses_metadata_fallback_when_limit_has_no_text(tmp_path: Path) -> None:
    report = tmp_path / "report.docx"
    _write_package(report, _docx_package(body="<w:p><w:r><w:t>内容</w:t></w:r></w:p>"))

    preview = OfficeDocumentPreviewLoader().load_preview(report, preview_max_bytes=1)

    assert preview is not None
    assert preview.kind == "message"
    assert preview.message == "Preview stopped at a safety limit"
    assert preview.reason == "resource_limit"


def test_office_loader_handles_corrupt_and_unsafe_packages_without_traceback(
    tmp_path: Path,
) -> None:
    corrupt = tmp_path / "corrupt.docx"
    corrupt.write_bytes(b"not a zip")
    unsafe = tmp_path / "unsafe.docx"
    _write_package(
        unsafe,
        {
            "../outside.xml": "bad",
            **_docx_package(body="<w:p><w:r><w:t>safe</w:t></w:r></w:p>"),
        },
    )

    corrupt_preview = OfficeDocumentPreviewLoader().load_preview(
        corrupt, preview_max_bytes=64 * 1024
    )
    unsafe_preview = OfficeDocumentPreviewLoader().load_preview(
        unsafe, preview_max_bytes=64 * 1024
    )

    assert corrupt_preview is not None
    assert corrupt_preview.reason == "corrupt"
    assert corrupt_preview.message == "Document could not be read"
    assert unsafe_preview is not None
    assert unsafe_preview.reason == "corrupt"


def test_office_loader_reports_password_protected_packages(tmp_path: Path, monkeypatch) -> None:
    report = tmp_path / "protected.docx"
    _write_package(report, _docx_package(body="<w:p><w:t>secret</w:t></w:p>"))
    original_infolist = zipfile.ZipFile.infolist

    def protected_infolist(archive: zipfile.ZipFile):
        infos = original_infolist(archive)
        infos[0].flag_bits |= 0x1
        return infos

    monkeypatch.setattr(zipfile.ZipFile, "infolist", protected_infolist)

    preview = OfficeDocumentPreviewLoader().load_preview(report, preview_max_bytes=64 * 1024)

    assert preview is not None
    assert preview.reason == "encrypted"
    assert preview.message == "Password-protected document"


def test_office_loader_rejects_dtd_and_entity_declarations(tmp_path: Path) -> None:
    report = tmp_path / "entity.docx"
    _write_package(
        report,
        _docx_package(
            body='<!DOCTYPE w:document [<!ENTITY x "unsafe">]><w:p><w:t>&x;</w:t></w:p>'
        ),
    )

    preview = OfficeDocumentPreviewLoader().load_preview(report, preview_max_bytes=64 * 1024)

    assert preview is not None
    assert preview.reason == "corrupt"


def test_office_loader_honors_resource_budget_and_cancel(tmp_path: Path) -> None:
    report = tmp_path / "report.docx"
    _write_package(report, _docx_package(body="<w:p><w:t>text</w:t></w:p>"))

    limited = OfficeDocumentPreviewLoader(
        resource_budget=PreviewResourceBudget(max_archive_entries=0)
    ).load_preview(report, preview_max_bytes=64 * 1024)
    cancelled = OfficeDocumentPreviewLoader().load_preview(
        report,
        preview_max_bytes=64 * 1024,
        cancel_callback=lambda: True,
    )

    assert limited is not None
    assert limited.reason == "resource_limit"
    assert cancelled == FilePreviewState.unavailable("cancelled")


def test_live_loader_uses_builtin_office_preview_by_default(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    report = project / "report.docx"
    _write_package(report, _docx_package(body="<w:p><w:t>Built in</w:t></w:p>"))

    pane = LiveBrowserSnapshotLoader().load_child_pane_snapshot(str(project), str(report))

    assert pane.preview_content == "Built in\n"
    assert pane.preview_reason is None
