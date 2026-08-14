"""Generate and compare a small, redistributable PDF preview corpus.

The corpus is generated in a temporary directory from PDF syntax authored in
this repository.  It does not commit third-party documents or fonts.  Run it
with the candidate dependency without changing the project lockfile:

    uv run --with pypdf==6.16.0 python scripts/benchmark_pdf_preview.py

The output is intentionally a measurement record, not a CI pass/fail gate.
It is used to make the Issue #1184 backend decision reproducible.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path
from typing import Any

MAX_INPUT_BYTES = 256 * 1024 * 1024
MAX_OUTPUT_BYTES = 64 * 1024
MAX_PAGES = 64
MAX_CONTENT_STREAM_BYTES = 1 * 1024 * 1024
TIMEOUT_SECONDS = 5.0


def _escape_pdf_text(value: str) -> bytes:
    return (
        value.encode("cp1252")
        .replace(b"\\", b"\\\\")
        .replace(b"(", b"\\(")
        .replace(b")", b"\\)")
    )


def _utf16_hex(value: str) -> bytes:
    return b"<" + b"feff" + value.encode("utf-16-be").hex().encode("ascii") + b">"


class _PdfBuilder:
    def __init__(
        self,
        *,
        japanese: bool = False,
        image: bool = False,
        embedded_font: bool = False,
    ) -> None:
        self.japanese = japanese
        self.image = image
        self.embedded_font = embedded_font
        self.objects: list[bytes] = []

    def add(self, value: bytes) -> int:
        self.objects.append(value)
        return len(self.objects)

    def stream(self, data: bytes, extra: bytes = b"") -> int:
        return self.add(
            b"<< /Length "
            + str(len(data)).encode("ascii")
            + extra
            + b" >>\nstream\n"
            + data
            + b"\nendstream"
        )

    def build(self, pages: list[bytes], *, title: str | None = None) -> bytes:
        catalog_id = self.add(b"")
        pages_id = self.add(b"")
        resources_id = self.add(b"")
        helvetica_id = self.add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
        if self.embedded_font:
            embedded_widths = b" ".join(b"500" for _ in range(95))
            embedded_font_file_id = self.stream(
                b"%!PS-AdobeFont-1.0: ZivoEmbedded 1.0\n"
                b"/FontName /ZIVO+Embedded def\n"
                b"% Synthetic original fixture font program; text uses WinAnsi encoding.\n"
            )
            embedded_descriptor_id = self.add(
                b"<< /Type /FontDescriptor /FontName /ZIVO+Embedded /Flags 4 "
                b"/FontBBox [0 -200 1000 900] /ItalicAngle 0 /Ascent 800 "
                b"/Descent -200 /CapHeight 700 /StemV 80 /FontFile "
                + str(embedded_font_file_id).encode("ascii")
                + b" 0 R >>"
            )
            helvetica_id = self.add(
                b"<< /Type /Font /Subtype /Type1 /BaseFont /ZIVO+Embedded "
                b"/FirstChar 32 /LastChar 126 /Widths ["
                + embedded_widths
                + b"] /Encoding /WinAnsiEncoding "
                b"/FontDescriptor "
                + str(embedded_descriptor_id).encode("ascii")
                + b" 0 R >>"
            )
        japanese_id: int | None = None
        if self.japanese:
            descendant_id = self.add(
                b"<< /Type /Font /Subtype /CIDFontType0 /BaseFont /HeiseiMin-W3 "
                b"/CIDSystemInfo << /Registry (Adobe) /Ordering (Japan1) /Supplement 2 >> "
                b"/DW 1000 >>"
            )
            japanese_id = self.add(
                b"<< /Type /Font /Subtype /Type0 /BaseFont /HeiseiMin-W3 "
                b"/Encoding /UniJIS-UTF16-H /DescendantFonts ["
                + str(descendant_id).encode("ascii")
                + b" 0 R] >>"
            )

        image_id: int | None = None
        if self.image:
            image_id = self.add(
                b"<< /Type /XObject /Subtype /Image /Width 1 /Height 1 "
                b"/ColorSpace /DeviceGray /BitsPerComponent 8 /Length 1 >>\n"
                b"stream\n\x00\nendstream"
            )

        resource_items = b"/Font << /F1 " + str(helvetica_id).encode("ascii") + b" 0 R"
        if japanese_id is not None:
            resource_items += b" /FJ " + str(japanese_id).encode("ascii") + b" 0 R"
        resource_items += b" >>"
        if image_id is not None:
            resource_items += b" /XObject << /Im1 " + str(image_id).encode("ascii") + b" 0 R >>"
        self.objects[resources_id - 1] = b"<< " + resource_items + b" >>"

        page_ids: list[int] = []
        for page_content in pages:
            content_id = self.stream(page_content)
            page_id = self.add(
                b"<< /Type /Page /Parent "
                + str(pages_id).encode("ascii")
                + b" 0 R /MediaBox [0 0 612 792] /Resources "
                + str(resources_id).encode("ascii")
                + b" 0 R /Contents "
                + str(content_id).encode("ascii")
                + b" 0 R >>"
            )
            page_ids.append(page_id)

        kids = b" ".join(str(page_id).encode("ascii") + b" 0 R" for page_id in page_ids)
        self.objects[pages_id - 1] = (
            b"<< /Type /Pages /Kids ["
            + kids
            + b"] /Count "
            + str(len(page_ids)).encode("ascii")
            + b" >>"
        )
        self.objects[catalog_id - 1] = (
            b"<< /Type /Catalog /Pages "
            + str(pages_id).encode("ascii")
            + b" 0 R >>"
        )

        info_id: int | None = None
        if title:
            info_id = self.add(b"<< /Title (" + _escape_pdf_text(title) + b") >>")

        output = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]
        for object_id, value in enumerate(self.objects, start=1):
            offsets.append(len(output))
            output.extend(f"{object_id} 0 obj\n".encode("ascii"))
            output.extend(value)
            output.extend(b"\nendobj\n")
        xref_offset = len(output)
        output.extend(f"xref\n0 {len(self.objects) + 1}\n".encode("ascii"))
        output.extend(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
        trailer = b"<< /Size " + str(len(self.objects) + 1).encode("ascii") + b" /Root 1 0 R"
        if info_id is not None:
            trailer += b" /Info " + str(info_id).encode("ascii") + b" 0 R"
        output.extend(b"trailer\n" + trailer + b" >>\nstartxref\n")
        output.extend(str(xref_offset).encode("ascii") + b"\n%%EOF\n")
        return bytes(output)


def _text_page(text: str, *, japanese: bool = False, rotate: bool = False) -> bytes:
    prefix = b"BT\n"
    if rotate:
        prefix += b"0 1 -1 0 100 100 cm\n"
    if japanese:
        return prefix + b"/FJ 14 Tf 50 740 Td " + _utf16_hex(text) + b" Tj ET\n"
    return prefix + b"/F1 14 Tf 50 740 Td (" + _escape_pdf_text(text) + b") Tj ET\n"


def _make_corpus(directory: Path) -> dict[str, Path]:
    corpus: dict[str, Path] = {}

    def write(name: str, data: bytes) -> None:
        path = directory / f"{name}.pdf"
        path.write_bytes(data)
        corpus[name] = path

    write(
        "simple_english",
        _PdfBuilder().build([_text_page("Zivo PDF preview: hello world.")], title="English"),
    )
    write(
        "unicode_japanese",
        _PdfBuilder(japanese=True).build(
            [_text_page("日本語のPDFプレビューです。", japanese=True)],
            title="Japanese",
        ),
    )
    write(
        "embedded_subset_font",
        _PdfBuilder(embedded_font=True).build(
            [_text_page("Embedded subset-font fixture")],
            title="Embedded font",
        ),
    )
    write(
        "multi_page",
        _PdfBuilder().build([_text_page(f"Page {index}: content") for index in range(1, 5)]),
    )
    write(
        "columns_and_table",
        _PdfBuilder().build(
            [
                b"BT /F1 12 Tf 50 740 Td (Left column) Tj 250 0 Td (Right column) Tj 0 -30 Td "
                b"(Name | Value) Tj 0 -20 Td (alpha | 1) Tj 0 -20 Td (beta | 2) Tj ET\n"
            ]
        ),
    )
    write("rotated", _PdfBuilder().build([_text_page("Rotated text", rotate=True)]))
    write("empty_page", _PdfBuilder().build([b"q Q\n"], title="Empty"))
    write("metadata_only", _PdfBuilder().build([b"q Q\n"], title="Metadata only"))
    write(
        "scan_image_only",
        _PdfBuilder(image=True).build(
            [b"q\n1 0 0 1 50 700 cm\n1 1 1 1 cm\n/Im1 Do\nQ\n"]
        ),
    )
    write(
        "large_content_stream",
        _PdfBuilder().build(
            [b"BT /F1 8 Tf 30 760 Td " + b"(line) Tj 0 -8 Td\n" * 80_000 + b"ET\n"]
        ),
    )
    write(
        "many_pages",
        _PdfBuilder().build([_text_page(f"Page {index}") for index in range(1, 101)]),
    )
    corrupt = corpus["simple_english"].read_bytes()
    (directory / "corrupt.pdf").write_bytes(corrupt[: len(corrupt) // 2])
    corpus["corrupt"] = directory / "corrupt.pdf"

    try:
        from pypdf import PdfWriter

        encrypted = directory / "encrypted.pdf"
        writer = PdfWriter(clone_from=corpus["simple_english"])
        writer.encrypt("preview-secret")
        with encrypted.open("wb") as handle:
            writer.write(handle)
        corpus["encrypted"] = encrypted
    except Exception as error:  # pragma: no cover - evaluation environment only
        raise RuntimeError("pypdf is required to generate the encrypted fixture") from error
    return corpus


def _rss_bytes() -> int | None:
    try:
        import resource

        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(value if sys.platform == "darwin" else value * 1024)
    except (ImportError, AttributeError, OSError):
        return None


def _bounded_text(parts: list[str]) -> tuple[str, bool]:
    output = ""
    limited = False
    for index, part in enumerate(parts, start=1):
        candidate = output + f"--- Page {index} ---\n" + part
        if len(candidate.encode("utf-8")) > MAX_OUTPUT_BYTES:
            limited = True
            break
        output = candidate
    return output, limited


def _run_pypdf(path: Path) -> dict[str, Any]:
    started = time.perf_counter()
    tracemalloc.start()
    outcome = "success"
    text = ""
    error = None
    pages_seen = 0
    has_text = False
    try:
        from pypdf import PdfReader, filters

        for name in (
            "MAX_DECLARED_STREAM_LENGTH",
            "MAX_ARRAY_BASED_STREAM_OUTPUT_LENGTH",
            "ZLIB_MAX_OUTPUT_LENGTH",
            "ZLIB_MAX_BUFFER_SIZE",
            "LZW_MAX_OUTPUT_LENGTH",
            "RUN_LENGTH_MAX_OUTPUT_LENGTH",
        ):
            if hasattr(filters, name):
                setattr(filters, name, min(getattr(filters, name), MAX_CONTENT_STREAM_BYTES))
        from pypdf.generic import _data_structures

        _data_structures.CONTENT_STREAM_ARRAY_MAX_LENGTH = min(
            _data_structures.CONTENT_STREAM_ARRAY_MAX_LENGTH,
            4096,
        )

        if path.stat().st_size > MAX_INPUT_BYTES:
            tracemalloc.stop()
            return {"backend": "pypdf", "reason": "resource_limit", "wall_ms": 0.0}
        reader = PdfReader(path, strict=False)
        if reader.is_encrypted:
            outcome = "encrypted"
        else:
            parts: list[str] = []
            for page in reader.pages:
                if pages_seen >= MAX_PAGES:
                    outcome = "resource_limit"
                    break
                pages_seen += 1
                page_text = page.extract_text() or ""
                has_text = has_text or bool(page_text.strip())
                parts.append(page_text)
                text, limited = _bounded_text(parts)
                if limited:
                    outcome = "resource_limit"
                    break
            if not has_text and outcome == "success":
                outcome = "no_text_content"
                text = ""
    except Exception as caught:  # noqa: BLE001 - classify arbitrary PDF parser failures
        outcome = "resource_limit" if type(caught).__name__ == "LimitReachedError" else "corrupt"
        error = type(caught).__name__
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "backend": "pypdf",
        "reason": outcome,
        "text_preview": text[:240],
        "pages_seen": pages_seen,
        "wall_ms": round((time.perf_counter() - started) * 1000, 3),
        "peak_tracemalloc_bytes": peak,
        "peak_rss_bytes": _rss_bytes(),
        "error": error,
    }


def _run_pypdf_bounded(path: Path) -> dict[str, Any]:
    """Run pypdf in a disposable worker so a hostile stream cannot block this runner."""

    started = time.perf_counter()
    try:
        completed = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--worker", str(path)],
            check=False,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
        if completed.returncode != 0:
            return {
                "backend": "pypdf",
                "reason": "worker_error",
                "wall_ms": round((time.perf_counter() - started) * 1000, 3),
                "error": completed.stderr[-240:],
            }
        return json.loads(completed.stdout)
    except subprocess.TimeoutExpired:
        return {
            "backend": "pypdf",
            "reason": "timeout",
            "wall_ms": round((time.perf_counter() - started) * 1000, 3),
        }


def _run_pdftotext(path: Path, executable: str) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            [executable, "-q", str(path), "-"],
            check=False,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            timeout=TIMEOUT_SECONDS,
        )
        text = completed.stdout.decode("utf-8", errors="replace")
        return {
            "backend": "pdftotext",
            "reason": "success" if text.strip() else "no_text_content",
            "exit_code": completed.returncode,
            "text_preview": text[:240],
            "wall_ms": round((time.perf_counter() - started) * 1000, 3),
        }
    except subprocess.TimeoutExpired:
        reason = "timeout"
    except OSError as error:
        reason = type(error).__name__
    return {
        "backend": "pdftotext",
        "reason": reason,
        "wall_ms": round((time.perf_counter() - started) * 1000, 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, help="write JSON results to this path")
    parser.add_argument("--worker", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker is not None:
        print(json.dumps(_run_pypdf(args.worker), ensure_ascii=False))
        return 0
    executable = shutil.which("pdftotext")
    with tempfile.TemporaryDirectory(prefix="zivo-pdf-corpus-") as temporary:
        corpus = _make_corpus(Path(temporary))
        records: list[dict[str, Any]] = []
        for name, path in corpus.items():
            records.append(
                {
                    "fixture": name,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "bytes": path.stat().st_size,
                    "pypdf": _run_pypdf_bounded(path),
                    "pdftotext": _run_pdftotext(path, executable) if executable else None,
                }
            )
        result = {
            "limits": {
                "input_bytes": MAX_INPUT_BYTES,
                "output_bytes": MAX_OUTPUT_BYTES,
                "max_pages": MAX_PAGES,
                "content_stream_bytes": MAX_CONTENT_STREAM_BYTES,
                "timeout_seconds": TIMEOUT_SECONDS,
            },
            "fixtures": records,
        }
        serialized = json.dumps(result, ensure_ascii=False, indent=2)
        print(serialized)
        if args.output:
            args.output.write_text(serialized + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
