"""Test Services Browser Snapshot Preview tests."""

from tests.support.browser_snapshot import (
    FilePreviewState,
    LiveBrowserSnapshotLoader,
    PdftotextPdfPreviewLoader,
    StubImagePreviewLoader,
    StubPdfPreviewLoader,
    subprocess,
)


def test_live_browser_snapshot_loader_uses_chafa_preview_for_supported_images(
    tmp_path, monkeypatch,
) -> None:
    monkeypatch.setattr(
        "zivo.services.terminal_detection.supports_kitty_graphics", lambda: False
    )
    monkeypatch.setattr(
        "zivo.services.previews.core.supports_kitty_graphics", lambda: False
    )
    project = tmp_path / "project"
    project.mkdir()
    image = project / "preview.png"
    image.write_bytes(b"png")
    preview_loader = StubImagePreviewLoader(
        previews_by_path={
            str(image): FilePreviewState.with_content(
                "\x1b[31m@@\x1b[0m\n",
                False,
                content_kind="image",
            ),
        }
    )
    loader = LiveBrowserSnapshotLoader(image_preview_loader=preview_loader)

    snapshot = loader.load_browser_snapshot(str(project), cursor_path=str(image))

    assert snapshot.child_pane.mode == "preview"
    assert snapshot.child_pane.preview_path == str(image)
    assert snapshot.child_pane.preview_content == "\x1b[31m@@\x1b[0m\n"
    assert snapshot.child_pane.preview_kind == "image"
    assert preview_loader.calls == [f"{image}:80:symbols"]

def test_live_browser_snapshot_loader_marks_missing_chafa_for_images(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    image = project / "preview.png"
    image.write_bytes(b"png")
    loader = LiveBrowserSnapshotLoader(image_preview_loader=StubImagePreviewLoader())

    snapshot = loader.load_browser_snapshot(str(project), cursor_path=str(image))

    assert snapshot.child_pane.mode == "preview"
    assert snapshot.child_pane.preview_path == str(image)
    assert snapshot.child_pane.preview_content is None
    assert snapshot.child_pane.preview_message == (
        "Preview unavailable: install `chafa` for image preview"
    )
    assert snapshot.child_pane.preview_reason == "dependency_missing"

def test_chafa_image_preview_loader_strips_non_sgr_control_sequences(
    tmp_path,
    monkeypatch,
) -> None:
    from zivo.services.browser_snapshot import ChafaImagePreviewLoader

    image = tmp_path / "preview.png"
    image.write_bytes(b"png")
    loader = ChafaImagePreviewLoader()

    monkeypatch.setattr(
        "zivo.services.previews.core.shutil.which",
        lambda name: "/usr/bin/chafa",
    )

    class _CompletedProcess:
        stdout = b"\x1b[?25l\x1b[31m@@\x1b[0m\n\x1b[?25h"

    monkeypatch.setattr(
        "zivo.services.previews.core.subprocess.run",
        lambda *args, **kwargs: _CompletedProcess(),
    )

    preview = loader.load_preview(image, preview_columns=40)

    assert preview == FilePreviewState.with_content(
        "\x1b[31m@@\x1b[0m\n",
        False,
        content_kind="image",
    )

def test_chafa_image_preview_loader_strips_osc_sequences(
    tmp_path,
    monkeypatch,
) -> None:
    from zivo.services.browser_snapshot import ChafaImagePreviewLoader

    image = tmp_path / "preview.png"
    image.write_bytes(b"png")
    loader = ChafaImagePreviewLoader()

    monkeypatch.setattr(
        "zivo.services.previews.core.shutil.which",
        lambda name: "/usr/bin/chafa",
    )

    class _CompletedProcess:
        stdout = (
            b"\x1b]7;file:///tmp/zivo\x1b\\"
            b"\x1b[31m@@\x1b[0m\n"
            b"\x1b]1337;RemoteHost=test\x07"
        )

    monkeypatch.setattr(
        "zivo.services.previews.core.subprocess.run",
        lambda *args, **kwargs: _CompletedProcess(),
    )

    preview = loader.load_preview(image, preview_columns=40)

    assert preview == FilePreviewState.with_content(
        "\x1b[31m@@\x1b[0m\n",
        False,
        content_kind="image",
    )

def test_chafa_image_preview_loader_uses_full_color_mode(
    tmp_path,
    monkeypatch,
) -> None:
    from zivo.services.browser_snapshot import ChafaImagePreviewLoader

    image = tmp_path / "preview.png"
    image.write_bytes(b"png")
    loader = ChafaImagePreviewLoader()

    monkeypatch.setattr(
        "zivo.services.previews.core.shutil.which",
        lambda name: "/usr/bin/chafa",
    )

    class _CompletedProcess:
        stdout = b"@@\n"

    captured_args: list[str] = []

    def _run(args, **kwargs):
        captured_args.extend(args)
        return _CompletedProcess()

    monkeypatch.setattr("zivo.services.previews.core.subprocess.run", _run)

    preview = loader.load_preview(image, preview_columns=40)

    assert preview == FilePreviewState.with_content("@@\n", False, content_kind="image")
    assert captured_args[:7] == [
        "/usr/bin/chafa",
        "--format",
        "symbols",
        "--colors",
        "full",
        "--animate",
        "off",
    ]

def test_chafa_image_preview_loader_falls_back_for_older_chafa(
    tmp_path,
    monkeypatch,
) -> None:
    from zivo.services.browser_snapshot import ChafaImagePreviewLoader

    image = tmp_path / "preview.png"
    image.write_bytes(b"png")
    loader = ChafaImagePreviewLoader()

    monkeypatch.setattr(
        "zivo.services.previews.core.shutil.which",
        lambda name: "/usr/bin/chafa",
    )

    class _CompletedProcess:
        stdout = b"@@\n"

    captured_calls: list[list[str]] = []

    def _run(args, **kwargs):
        captured_calls.append(list(args))
        if "--animate" in args:
            raise subprocess.CalledProcessError(
                1,
                args,
                stderr=b"chafa: Unknown option --animate\n",
            )
        return _CompletedProcess()

    monkeypatch.setattr("zivo.services.previews.core.subprocess.run", _run)

    preview = loader.load_preview(image, preview_columns=40)

    assert preview == FilePreviewState.with_content("@@\n", False, content_kind="image")
    assert captured_calls == [
        [
            "/usr/bin/chafa",
            "--format",
            "symbols",
            "--colors",
            "full",
            "--animate",
            "off",
            "--size",
            "40x",
            str(image),
        ],
        [
            "/usr/bin/chafa",
            "--format",
            "symbols",
            "--colors",
            "full",
            "--duration",
            "0",
            "--size",
            "40x",
            str(image),
        ],
    ]

def test_chafa_image_preview_loader_returns_error_when_command_fails(
    tmp_path,
    monkeypatch,
) -> None:
    from zivo.services.browser_snapshot import ChafaImagePreviewLoader

    image = tmp_path / "preview.png"
    image.write_bytes(b"png")
    loader = ChafaImagePreviewLoader()

    monkeypatch.setattr(
        "zivo.services.previews.core.shutil.which",
        lambda name: "/usr/bin/chafa",
    )

    def _run(args, **kwargs):
        raise subprocess.CalledProcessError(1, args, stderr=b"decoder failed\n")

    monkeypatch.setattr("zivo.services.previews.core.subprocess.run", _run)

    preview = loader.load_preview(image, preview_columns=40)

    assert preview == FilePreviewState.error()

def test_live_browser_snapshot_loader_uses_pdftotext_for_pdf_preview(
    tmp_path,
    monkeypatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    report = project / "report.pdf"
    report.write_bytes(b"%PDF-1.4")
    loader = LiveBrowserSnapshotLoader(pdf_preview_loader=PdftotextPdfPreviewLoader())

    monkeypatch.setattr(
        "zivo.services.previews.core.shutil.which",
        lambda name: "/usr/bin/pdftotext",
    )

    class _CompletedProcess:
        stdout = b"PDF text\n"

    monkeypatch.setattr(
        "zivo.services.previews.core.subprocess.run",
        lambda *args, **kwargs: _CompletedProcess(),
    )

    pane = loader.load_child_pane_snapshot(str(project), str(report))

    assert pane.mode == "preview"
    assert pane.preview_path == str(report)
    assert pane.preview_content == "PDF text\n"

def test_live_browser_snapshot_loader_uses_pdf_preview_loader_for_supported_pdfs(
    tmp_path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    report = project / "report.pdf"
    report.write_bytes(b"%PDF-1.4")
    preview_loader = StubPdfPreviewLoader(
        previews_by_path={
            str(report): FilePreviewState.with_content("PDF text\n", False),
        }
    )
    loader = LiveBrowserSnapshotLoader(pdf_preview_loader=preview_loader)

    pane = loader.load_child_pane_snapshot(str(project), str(report))

    assert pane.mode == "preview"
    assert pane.preview_path == str(report)
    assert pane.preview_content == "PDF text\n"
    assert preview_loader.calls == [f"{report}:{64 * 1024}"]

def test_pdftotext_pdf_preview_loader_caches_pdftotext_path(
    tmp_path,
    monkeypatch,
) -> None:
    from zivo.services.browser_snapshot import PdftotextPdfPreviewLoader

    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"
    first.write_bytes(b"%PDF-1.4")
    second.write_bytes(b"%PDF-1.4")
    loader = PdftotextPdfPreviewLoader()
    which_calls: list[str] = []

    def _which(name: str) -> str:
        which_calls.append(name)
        return "/usr/bin/pdftotext"

    class _CompletedProcess:
        stdout = b"PDF text\n"

    monkeypatch.setattr("zivo.services.previews.core.shutil.which", _which)
    monkeypatch.setattr(
        "zivo.services.previews.core.subprocess.run",
        lambda *args, **kwargs: _CompletedProcess(),
    )

    assert loader.load_preview(first, preview_max_bytes=64 * 1024) == (
        FilePreviewState.with_content("PDF text\n", False)
    )
    assert loader.load_preview(second, preview_max_bytes=64 * 1024) == (
        FilePreviewState.with_content("PDF text\n", False)
    )
    assert which_calls == ["pdftotext"]

def test_pdftotext_pdf_preview_loader_caches_missing_pdftotext(
    tmp_path,
    monkeypatch,
) -> None:
    from zivo.services.browser_snapshot import PdftotextPdfPreviewLoader

    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"
    first.write_bytes(b"%PDF-1.4")
    second.write_bytes(b"%PDF-1.4")
    loader = PdftotextPdfPreviewLoader()
    which_calls: list[str] = []

    def _which(name: str) -> None:
        which_calls.append(name)
        return None

    monkeypatch.setattr("zivo.services.previews.core.shutil.which", _which)

    first_preview = loader.load_preview(first, preview_max_bytes=64 * 1024)
    second_preview = loader.load_preview(second, preview_max_bytes=64 * 1024)
    assert first_preview is not None
    assert second_preview is not None
    assert first_preview.reason == "dependency_missing"
    assert second_preview.reason == "dependency_missing"
    assert which_calls == ["pdftotext"]

def test_live_browser_snapshot_loader_skips_pdf_preview_when_disabled(
    tmp_path,
    monkeypatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    report = project / "report.pdf"
    report.write_bytes(b"%PDF-1.4")
    loader = LiveBrowserSnapshotLoader()

    which_calls: list[str] = []

    def _which(name: str) -> str:
        which_calls.append(name)
        return "/usr/bin/pdftotext"

    monkeypatch.setattr("zivo.services.previews.core.shutil.which", _which)

    pane = loader.load_child_pane_snapshot(
        str(project),
        str(report),
        enable_pdf_preview=False,
    )

    assert pane.mode == "preview"
    assert pane.preview_reason == "disabled"
    assert pane.entries == ()
    assert which_calls == []
