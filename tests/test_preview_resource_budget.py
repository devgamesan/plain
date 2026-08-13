import zipfile
from pathlib import Path

from zivo.models import ShellCommandResult
from zivo.services.previews.core import (
    ChafaImagePreviewLoader,
    FilePreviewState,
    PandocDocumentPreviewLoader,
    PdftotextPdfPreviewLoader,
    PreviewResourceBudget,
    _inspect_ooxml_archive,
)


def test_pdftotext_uses_path_as_one_argv_element_and_bounded_runner(
    tmp_path: Path,
    monkeypatch,
) -> None:
    report = tmp_path / "folder with spaces" / "report.pdf"
    report.parent.mkdir()
    report.write_bytes(b"%PDF-1.4")
    captured: dict[str, object] = {}

    def _run(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        return ShellCommandResult(exit_code=0, stdout="PDF text\n")

    monkeypatch.setattr("zivo.services.previews.core.run_bounded_process", _run)
    loader = PdftotextPdfPreviewLoader(
        resource_budget=PreviewResourceBudget(timeout_seconds=0.1),
    )
    loader.pdftotext_path = "/usr/bin/pdftotext"

    preview = loader.load_preview(report, preview_max_bytes=64 * 1024)

    assert preview == FilePreviewState.with_content("PDF text\n", False)
    assert captured["command"] == ["/usr/bin/pdftotext", "-q", str(report), "-"]
    assert captured["prefix_only"] is True
    assert captured["terminate_on_output_limit"] is True


def test_document_timeout_keeps_safe_partial_text_marked_limited(
    tmp_path: Path,
    monkeypatch,
) -> None:
    report = tmp_path / "report.docx"
    report.write_bytes(b"not a zip")

    monkeypatch.setattr("zivo.services.previews.core.shutil.which", lambda _: "/fake/pandoc")
    monkeypatch.setattr(
        "zivo.services.previews.core.run_bounded_process",
        lambda *args, **kwargs: ShellCommandResult(
            exit_code=-15,
            stdout="partial document\n",
            termination_reason="timed_out",
        ),
    )

    preview = PandocDocumentPreviewLoader().load_preview(
        report,
        preview_max_bytes=64 * 1024,
    )

    assert preview is not None
    assert preview.content == "partial document\n"
    assert preview.truncated is True
    assert preview.reason == "timeout"


def test_image_output_limit_does_not_render_partial_terminal_protocol(
    tmp_path: Path,
    monkeypatch,
) -> None:
    image = tmp_path / "image.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")
    monkeypatch.setattr("zivo.services.previews.core.shutil.which", lambda _: "/fake/chafa")
    monkeypatch.setattr(
        "zivo.services.previews.core.run_bounded_process",
        lambda *args, **kwargs: ShellCommandResult(
            exit_code=-15,
            stdout="partial image bytes",
            termination_reason="output_limited",
        ),
    )

    preview = ChafaImagePreviewLoader().load_preview(image, preview_columns=40)

    assert preview is not None
    assert preview.kind == "message"
    assert preview.reason == "resource_limit"
    assert preview.content is None


def test_image_preview_uses_a_relaxed_format_specific_budget(
    tmp_path: Path,
    monkeypatch,
) -> None:
    image = tmp_path / "image.png"
    image.write_bytes(b"PNG")
    budget = PreviewResourceBudget(
        image_timeout_seconds=7.0,
        image_stdout_max_bytes=2 * 1024 * 1024,
    )
    captured: dict[str, object] = {}

    monkeypatch.setattr("zivo.services.previews.core.shutil.which", lambda _: "/fake/chafa")

    def _run(command, **kwargs):
        captured.update(kwargs)
        return ShellCommandResult(exit_code=0, stdout="image\n")

    monkeypatch.setattr("zivo.services.previews.core.run_bounded_process", _run)

    preview = ChafaImagePreviewLoader(resource_budget=budget).load_preview(
        image,
        preview_columns=120,
    )

    assert preview == FilePreviewState.with_content("image\n", False, content_kind="image")
    assert captured["stdout_max_output_bytes"] == budget.image_stdout_max_bytes
    assert captured["timeout_seconds"] == budget.image_timeout_seconds


def test_cancelled_document_preview_is_not_a_success_cache_value(
    tmp_path: Path,
    monkeypatch,
) -> None:
    report = tmp_path / "report.pdf"
    report.write_bytes(b"%PDF-1.4")
    monkeypatch.setattr("zivo.services.previews.core.shutil.which", lambda _: "/fake/pdftotext")
    monkeypatch.setattr(
        "zivo.services.previews.core.run_bounded_process",
        lambda *args, **kwargs: ShellCommandResult(
            exit_code=-15,
            termination_reason="cancelled",
        ),
    )

    preview = PdftotextPdfPreviewLoader().load_preview(
        report,
        preview_max_bytes=64 * 1024,
        cancel_callback=lambda: True,
    )

    assert preview is not None
    assert preview.kind == "unavailable"
    assert preview.reason == "cancelled"


def test_ooxml_archive_metadata_limit_is_checked_without_extracting(tmp_path: Path) -> None:
    report = tmp_path / "report.docx"
    with zipfile.ZipFile(report, "w") as archive:
        archive.writestr("word/document.xml", "text")

    preview = _inspect_ooxml_archive(
        report,
        PreviewResourceBudget(max_archive_entries=0),
        None,
    )

    assert preview is not None
    assert preview.reason == "resource_limit"
