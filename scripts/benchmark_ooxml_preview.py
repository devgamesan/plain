"""Manual comparison of the built-in OOXML preview and Pandoc.

This is intentionally not part of CI.  It creates deterministic, synthetic
packages and reports cold/warm latency, synchronous time-to-first-content, and
Python peak allocations for each backend.
"""

from __future__ import annotations

import argparse
import time
import tracemalloc
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from zivo.services.previews import OfficeDocumentPreviewLoader, PandocDocumentPreviewLoader


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--items", type=int, default=100, help="rows/paragraphs per fixture")
    args = parser.parse_args()
    if args.items < 1:
        parser.error("--items must be positive")

    with TemporaryDirectory(prefix="zivo-ooxml-benchmark-") as temporary_directory:
        root = Path(temporary_directory)
        fixtures = {
            "docx": _write_docx(root / "benchmark.docx", args.items),
            "xlsx": _write_xlsx(root / "benchmark.xlsx", args.items),
            "pptx": _write_pptx(root / "benchmark.pptx", args.items),
        }
        for suffix, path in fixtures.items():
            print(f"[{suffix.upper()}] {path.stat().st_size} bytes, {args.items} items")
            for label, loader in (
                ("builtin", OfficeDocumentPreviewLoader()),
                ("pandoc", PandocDocumentPreviewLoader()),
            ):
                _measure(label, loader, path)


def _measure(label: str, loader, path: Path) -> None:
    values: list[tuple[str, float, int, str]] = []
    for run in ("cold", "warm"):
        tracemalloc.start()
        started = time.perf_counter()
        preview = loader.load_preview(path, preview_max_bytes=64 * 1024)
        elapsed = time.perf_counter() - started
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        content = preview.content if preview is not None else None
        reason = preview.reason if preview is not None else "none"
        values.append((run, elapsed, peak, reason))
        if run == "cold":
            useful = bool(content and content.strip())
            print(f"  {label:7} first useful content={'yes' if useful else 'no'}")
    for run, elapsed, peak, reason in values:
        print(f"  {label:7} {run:5} wall={elapsed * 1000:8.2f} ms peak={peak:9} B reason={reason}")


def _write_docx(path: Path, items: int) -> Path:
    paragraphs = "".join(
        f"<w:p><w:r><w:t>Paragraph {index}: benchmark text</w:t></w:r></w:p>"
        for index in range(items)
    )
    members = {
        "[Content_Types].xml": (
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.'
            'relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-'
            'officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>"
        ),
        "_rels/.rels": (
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
            'relationships/officeDocument" Target="word/document.xml"/>'
            "</Relationships>"
        ),
        "word/document.xml": (
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body>{paragraphs}</w:body></w:document>"
        ),
    }
    return _write_zip(path, members)


def _write_xlsx(path: Path, items: int) -> Path:
    rows = "".join(
        f'<row><c r="A{index}" t="inlineStr"><is><t>Product {index}</t></is></c>'
        f'<c r="B{index}"><v>{index}</v></c></row>'
        for index in range(1, items + 1)
    )
    members = {
        "[Content_Types].xml": (
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.'
            'relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-'
            'officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.'
            'openxmlformats-'
            'officedocument.spreadsheetml.worksheet+xml"/>'
            "</Types>"
        ),
        "_rels/.rels": (
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
            'relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>"
        ),
        "xl/workbook.xml": (
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Benchmark" r:id="rId1"/></sheets></workbook>'
        ),
        "xl/_rels/workbook.xml.rels": (
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
            'relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            "</Relationships>"
        ),
        "xl/worksheets/sheet1.xml": (
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f"<sheetData>{rows}</sheetData></worksheet>"
        ),
    }
    return _write_zip(path, members)


def _write_pptx(path: Path, items: int) -> Path:
    slides = {
        f"ppt/slides/slide{index}.xml": (
            '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
            'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
            f"<p:cSld><a:p><a:r><a:t>Slide {index}</a:t></a:r></a:p></p:cSld></p:sld>"
        )
        for index in range(1, items + 1)
    }
    relationships = "".join(
        f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
        f'relationships/slide" Target="slides/slide{index}.xml"/>'
        for index in range(1, items + 1)
    )
    slide_ids = "".join(
        f'<p:sldId id="{index}" r:id="rId{index}"/>'
        for index in range(1, items + 1)
    )
    members = {
        "[Content_Types].xml": (
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.'
            'relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.'
            'openxmlformats-'
            'officedocument.presentationml.presentation.main+xml"/>'
            "</Types>"
        ),
        "_rels/.rels": (
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
            'relationships/officeDocument" Target="ppt/presentation.xml"/>'
            "</Relationships>"
        ),
        "ppt/presentation.xml": (
            '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f"<p:sldIdLst>{slide_ids}</p:sldIdLst></p:presentation>"
        ),
        "ppt/_rels/presentation.xml.rels": (
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f"{relationships}</Relationships>"
        ),
        **slides,
    }
    return _write_zip(path, members)


def _write_zip(path: Path, members: dict[str, str]) -> Path:
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return path


if __name__ == "__main__":
    main()
