from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfWriter

from scripts.benchmark_pdf_preview import _PdfBuilder, _text_page
from zivo.models import ShellCommandResult
from zivo.services.browser_snapshot import LiveBrowserSnapshotLoader
from zivo.services.previews.core import (
    PREVIEW_NO_TEXT_CONTENT_MESSAGE,
    PREVIEW_RESOURCE_LIMIT_MESSAGE,
    FilePreviewState,
    HybridPdfPreviewLoader,
    PreviewResourceBudget,
    PypdfPdfPreviewLoader,
)


def _write_pdf(path: Path, content: bytes) -> Path:
    path.write_bytes(_PdfBuilder().build([content]))
    return path


def test_pypdf_worker_extracts_text_and_keeps_page_boundaries(tmp_path: Path) -> None:
    report = tmp_path / "report.pdf"
    report.write_bytes(
        _PdfBuilder().build([_text_page("first"), _text_page("second")])
    )

    preview = PypdfPdfPreviewLoader().load_preview(
        report,
        preview_max_bytes=64 * 1024,
    )

    assert preview == FilePreviewState.with_content(
        "--- Page 1 ---\nfirst--- Page 2 ---\nsecond",
        False,
    )


def test_live_snapshot_uses_hybrid_pdf_loader_by_default(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    report = project / "report.pdf"
    report.write_bytes(_PdfBuilder().build([_text_page("default backend")]))

    pane = LiveBrowserSnapshotLoader().load_child_pane_snapshot(
        str(project),
        str(report),
    )

    assert pane.preview_content == "--- Page 1 ---\ndefault backend"
    assert pane.preview_reason is None


def test_pypdf_worker_classifies_empty_text_as_no_text(tmp_path: Path) -> None:
    report = _write_pdf(tmp_path / "empty.pdf", b"q Q\n")

    preview = PypdfPdfPreviewLoader().load_preview(
        report,
        preview_max_bytes=64 * 1024,
    )

    assert preview == FilePreviewState.with_message(
        PREVIEW_NO_TEXT_CONTENT_MESSAGE,
        reason="no_text_content",
    )


def test_pypdf_worker_does_not_treat_scan_pdf_as_text(tmp_path: Path) -> None:
    report = tmp_path / "scan.pdf"
    report.write_bytes(
        _PdfBuilder(image=True).build(
            [b"q\n1 0 0 1 50 700 cm\n/Im1 Do\nQ\n"]
        )
    )

    preview = PypdfPdfPreviewLoader().load_preview(
        report,
        preview_max_bytes=64 * 1024,
    )

    assert preview == FilePreviewState.with_message(
        PREVIEW_NO_TEXT_CONTENT_MESSAGE,
        reason="no_text_content",
    )


def test_pypdf_worker_classifies_encrypted_pdf_without_prompt(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    source.write_bytes(_PdfBuilder().build([_text_page("secret")]))
    report = tmp_path / "encrypted.pdf"
    writer = PdfWriter(clone_from=source)
    writer.encrypt("preview-secret")
    with report.open("wb") as handle:
        writer.write(handle)

    preview = PypdfPdfPreviewLoader().load_preview(
        report,
        preview_max_bytes=64 * 1024,
    )

    assert preview is not None
    assert preview.kind == "message"
    assert preview.reason == "encrypted"


def test_pypdf_worker_stops_at_page_limit(tmp_path: Path) -> None:
    report = tmp_path / "many-pages.pdf"
    report.write_bytes(_PdfBuilder().build([_text_page(f"page {index}") for index in range(4)]))
    budget = PreviewResourceBudget(pdf_max_pages=2)

    preview = PypdfPdfPreviewLoader(resource_budget=budget).load_preview(
        report,
        preview_max_bytes=64 * 1024,
    )

    assert preview is not None
    assert preview.kind == "content"
    assert preview.reason == "resource_limit"
    assert preview.truncated is True
    assert "page 3" not in (preview.content or "")


def test_pypdf_worker_stops_at_content_stream_limit(tmp_path: Path) -> None:
    report = tmp_path / "large-stream.pdf"
    report.write_bytes(
        _PdfBuilder().build(
            [b"BT /F1 8 Tf 30 760 Td " + b"(line) Tj 0 -8 Td\n" * 2000 + b"ET\n"]
        )
    )
    budget = PreviewResourceBudget(pdf_max_content_stream_bytes=1024)

    preview = PypdfPdfPreviewLoader(resource_budget=budget).load_preview(
        report,
        preview_max_bytes=64 * 1024,
    )

    assert preview == FilePreviewState.with_message(
        PREVIEW_RESOURCE_LIMIT_MESSAGE,
        reason="resource_limit",
    )


class _StubLoader:
    def __init__(self, preview: FilePreviewState | None) -> None:
        self.preview = preview
        self.calls = 0

    def load_preview(self, path: Path, **kwargs: object) -> FilePreviewState | None:
        self.calls += 1
        return self.preview


def test_hybrid_loader_falls_back_once_after_completed_parser_failure(tmp_path: Path) -> None:
    report = tmp_path / "report.pdf"
    report.write_bytes(b"pdf")
    primary = _StubLoader(FilePreviewState.with_message("broken", reason="corrupt"))
    fallback = _StubLoader(FilePreviewState.with_content("fallback\n", False))
    loader = HybridPdfPreviewLoader(
        pypdf_loader=primary,
        pdftotext_loader=fallback,
    )

    preview = loader.load_preview(report, preview_max_bytes=64 * 1024)

    assert preview == FilePreviewState.with_content("fallback\n", False)
    assert primary.calls == 1
    assert fallback.calls == 1


@pytest.mark.parametrize(
    "reason",
    ["cancelled", "timeout", "resource_limit", "permission_denied", "encrypted"],
)
def test_hybrid_loader_does_not_fallback_after_safety_stop(
    tmp_path: Path,
    reason: str,
) -> None:
    report = tmp_path / "report.pdf"
    report.write_bytes(b"pdf")
    primary = _StubLoader(FilePreviewState.with_message("stopped", reason=reason))
    fallback = _StubLoader(FilePreviewState.with_content("fallback\n", False))
    loader = HybridPdfPreviewLoader(
        pypdf_loader=primary,
        pdftotext_loader=fallback,
    )

    preview = loader.load_preview(report, preview_max_bytes=64 * 1024)

    assert preview == primary.preview
    assert fallback.calls == 0


def test_hybrid_loader_keeps_primary_no_text_when_fallback_missing(tmp_path: Path) -> None:
    report = tmp_path / "report.pdf"
    report.write_bytes(b"pdf")
    primary = _StubLoader(
        FilePreviewState.with_message("no text", reason="no_text_content")
    )
    fallback = _StubLoader(
        FilePreviewState.with_message("missing", reason="dependency_missing")
    )
    loader = HybridPdfPreviewLoader(
        pypdf_loader=primary,
        pdftotext_loader=fallback,
    )

    preview = loader.load_preview(report, preview_max_bytes=64 * 1024)

    assert preview == primary.preview
    assert fallback.calls == 1


def test_pypdf_process_result_output_limit_is_not_treated_as_success(
    tmp_path: Path,
    monkeypatch,
) -> None:
    report = tmp_path / "report.pdf"
    report.write_bytes(b"pdf")
    monkeypatch.setattr(
        "zivo.services.previews.core.run_bounded_process",
        lambda *args, **kwargs: ShellCommandResult(
            exit_code=-15,
            stdout='{"reason":"success","content":"partial',
            termination_reason="output_limited",
        ),
    )

    preview = PypdfPdfPreviewLoader().load_preview(report, preview_max_bytes=64 * 1024)

    assert preview is not None
    assert preview.reason == "resource_limit"


def test_pypdf_worker_preserves_permission_denied_reason(
    tmp_path: Path,
    monkeypatch,
) -> None:
    report = tmp_path / "report.pdf"
    report.write_bytes(b"pdf")
    monkeypatch.setattr(
        "zivo.services.previews.core.run_bounded_process",
        lambda *args, **kwargs: ShellCommandResult(
            exit_code=0,
            stdout='{"reason":"permission_denied"}',
        ),
    )

    preview = PypdfPdfPreviewLoader().load_preview(report, preview_max_bytes=64 * 1024)

    assert preview == FilePreviewState.permission_denied()
