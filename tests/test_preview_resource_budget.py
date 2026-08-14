from pathlib import Path

import pytest

from zivo.app import create_app
from zivo.models import AppConfig, PreviewResourceConfig, ShellCommandResult
from zivo.services.previews.core import (
    PDF_PREVIEW_ENCRYPTED_MESSAGE,
    ChafaImagePreviewLoader,
    FilePreviewState,
    PdftotextPdfPreviewLoader,
    PreviewResourceBudget,
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


@pytest.mark.parametrize(
    ("stderr", "exit_code", "reason"),
    [
        ("Command Line Error: Incorrect password", 1, "encrypted"),
        ("Permission denied", 1, "permission_denied"),
        ("", 3, "permission_denied"),
    ],
)
def test_pdftotext_classifies_nonzero_failures_without_fallback_reason(
    tmp_path: Path,
    monkeypatch,
    stderr: str,
    exit_code: int,
    reason: str,
) -> None:
    report = tmp_path / "report.pdf"
    report.write_bytes(b"%PDF-1.4")
    monkeypatch.setattr(
        "zivo.services.previews.core.run_bounded_process",
        lambda *args, **kwargs: ShellCommandResult(
            exit_code=exit_code,
            stderr=stderr,
        ),
    )
    loader = PdftotextPdfPreviewLoader()
    loader.pdftotext_path = "/usr/bin/pdftotext"

    preview = loader.load_preview(report, preview_max_bytes=64 * 1024)

    assert preview is not None
    assert preview.reason == reason
    if reason == "encrypted":
        assert preview.message == PDF_PREVIEW_ENCRYPTED_MESSAGE


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


def test_kitty_image_preview_uses_the_bounded_preview_height(
    tmp_path: Path,
    monkeypatch,
) -> None:
    image = tmp_path / "image.png"
    image.write_bytes(b"PNG")
    captured: dict[str, object] = {}

    monkeypatch.setattr("zivo.services.previews.core.shutil.which", lambda _: "/fake/chafa")

    def _run(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        return ShellCommandResult(
            exit_code=0,
            stdout="\033_Gf=100;AAAA\033\\",
        )

    monkeypatch.setattr("zivo.services.previews.core.run_bounded_process", _run)

    preview = ChafaImagePreviewLoader().load_preview(
        image,
        preview_columns=40,
        preview_rows=12,
        image_preview_format="kitty",
    )

    assert preview == FilePreviewState.with_content(
        "\033_Gf=100;AAAA\033\\",
        False,
        content_kind="kitty",
    )
    assert captured["command"][-3:] == ["--size", "40x12", str(image)]


def test_preview_resource_config_converts_user_units_to_process_limits() -> None:
    budget = PreviewResourceBudget.from_config(
        PreviewResourceConfig(
            stdout_max_kib=512,
            image_stdout_max_mib=8,
            kitty_stdout_max_mib=64,
            input_max_mib=512,
            max_archive_entry_mib=128,
            max_archive_total_mib=512,
        )
    )

    assert budget.stdout_max_bytes == 512 * 1024
    assert budget.image_stdout_max_bytes == 8 * 1024 * 1024
    assert budget.kitty_stdout_max_bytes == 64 * 1024 * 1024
    assert budget.input_max_bytes == 512 * 1024 * 1024
    assert budget.max_archive_entry_bytes == 128 * 1024 * 1024
    assert budget.max_archive_total_bytes == 512 * 1024 * 1024


def test_create_app_passes_preview_resource_config_to_live_loader() -> None:
    app = create_app(
        app_config=AppConfig(
            preview=PreviewResourceConfig(image_stdout_max_mib=8),
        )
    )

    assert app._snapshot_loader.preview_resource_budget.image_stdout_max_bytes == (
        8 * 1024 * 1024
    )


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
