import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from zivo.adapters import LocalFilesystemAdapter
from zivo.services import (
    PREVIEW_PERMISSION_DENIED_MESSAGE,
    FakeBrowserSnapshotLoader,
    LiveBrowserSnapshotLoader,
)
from zivo.services.browser_snapshot import FilePreviewState, _resolve_cursor_path
from zivo.state import BrowserSnapshot, GrepSearchResultState
from zivo.state.models import DirectoryEntryState, PaneState


@dataclass
class StubFilesystemAdapter:
    entries_by_path: dict[str, tuple[DirectoryEntryState, ...]] = field(default_factory=dict)
    errors_by_path: dict[str, Exception] = field(default_factory=dict)
    list_directory_calls: list[str] = field(default_factory=list)

    def list_directory(self, path: str) -> tuple[DirectoryEntryState, ...]:
        self.list_directory_calls.append(path)
        if path in self.errors_by_path:
            raise self.errors_by_path[path]
        return self.entries_by_path[path]


@dataclass
class StubDocumentPreviewLoader:
    previews_by_path: dict[str, FilePreviewState] = field(default_factory=dict)
    calls: list[str] = field(default_factory=list)

    def load_preview(self, path: Path, *, preview_max_bytes: int) -> FilePreviewState | None:
        self.calls.append(f"{path}:{preview_max_bytes}")
        return self.previews_by_path.get(str(path))


@dataclass
class StubImagePreviewLoader:
    previews_by_path: dict[str, FilePreviewState] = field(default_factory=dict)
    calls: list[str] = field(default_factory=list)

    def load_preview(
        self, path: Path, *, preview_columns: int, image_preview_format: str = "symbols"
    ) -> FilePreviewState | None:
        self.calls.append(f"{path}:{preview_columns}:{image_preview_format}")
        return self.previews_by_path.get(str(path))


def _build_stub_filesystem(*paths: str) -> StubFilesystemAdapter:
    live_filesystem = LocalFilesystemAdapter()
    filesystem = StubFilesystemAdapter()
    for path in paths:
        filesystem.entries_by_path[path] = live_filesystem.list_directory(path)
    return filesystem


def test_live_browser_snapshot_loader_builds_three_pane_snapshot(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    docs = project / "docs"
    docs.mkdir()
    (docs / "spec.md").write_text("spec\n", encoding="utf-8")
    (project / "README.md").write_text("readme\n", encoding="utf-8")
    (tmp_path / "sibling").mkdir()

    loader = LiveBrowserSnapshotLoader()

    snapshot = loader.load_browser_snapshot(str(project))

    assert snapshot.current_path == str(project)
    assert [entry.name for entry in snapshot.parent_pane.entries] == ["project", "sibling"]
    assert [entry.name for entry in snapshot.current_pane.entries] == ["docs", "README.md"]
    assert snapshot.current_pane.cursor_path == str(docs)
    assert snapshot.child_pane.directory_path == str(docs)
    assert [entry.name for entry in snapshot.child_pane.entries] == ["spec.md"]


def test_live_browser_snapshot_loader_uses_cursor_path_for_child_pane(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    docs = project / "docs"
    docs.mkdir()
    src = project / "src"
    src.mkdir()
    (src / "main.py").write_text("print('zivo')\n", encoding="utf-8")

    loader = LiveBrowserSnapshotLoader()

    snapshot = loader.load_browser_snapshot(str(project), cursor_path=str(src))

    assert snapshot.current_pane.cursor_path == str(src)
    assert snapshot.child_pane.directory_path == str(src)
    assert [entry.name for entry in snapshot.child_pane.entries] == ["main.py"]


def test_live_browser_snapshot_loader_returns_empty_child_pane_for_file_cursor(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    readme = project / "README.md"
    readme.write_text("plain\n", encoding="utf-8")

    loader = LiveBrowserSnapshotLoader()

    snapshot = loader.load_browser_snapshot(str(project), cursor_path=str(readme))

    assert snapshot.current_pane.cursor_path == str(readme)
    assert snapshot.child_pane.mode == "preview"
    assert snapshot.child_pane.preview_path == str(readme)
    assert snapshot.child_pane.preview_content == "plain\n"
    assert snapshot.child_pane.preview_truncated is False


@pytest.mark.parametrize(
    ("filename", "content"),
    [
        ("app.log", "log line\n"),
        ("settings.conf", "key=value\n"),
        (".env", "DEBUG=true\n"),
        (".gitignore", "*.pyc\n"),
        ("component.vue", "<template></template>\n"),
        ("build.dockerfile", "FROM python:3.12\n"),
    ],
)
def test_live_browser_snapshot_loader_previews_added_text_targets(
    tmp_path,
    filename: str,
    content: str,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    target = project / filename
    target.write_text(content, encoding="utf-8")

    loader = LiveBrowserSnapshotLoader()

    snapshot = loader.load_browser_snapshot(str(project), cursor_path=str(target))

    assert snapshot.current_pane.cursor_path == str(target)
    assert snapshot.child_pane.mode == "preview"
    assert snapshot.child_pane.preview_path == str(target)
    assert snapshot.child_pane.preview_content == content
    assert snapshot.child_pane.preview_truncated is False


def test_live_browser_snapshot_loader_returns_empty_child_pane_for_binary_file_cursor(
    tmp_path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    binary = project / "archive.bin"
    binary.write_bytes(b"\x00\x01\x02\x03")

    loader = LiveBrowserSnapshotLoader()

    snapshot = loader.load_browser_snapshot(str(project), cursor_path=str(binary))

    assert snapshot.current_pane.cursor_path == str(binary)
    assert snapshot.child_pane.directory_path == str(project)
    assert snapshot.child_pane.entries == ()
    assert snapshot.child_pane.mode == "preview"
    assert snapshot.child_pane.preview_path == str(binary)
    assert snapshot.child_pane.preview_content is None
    assert snapshot.child_pane.preview_message == "Preview unavailable for this file type"


def test_live_browser_snapshot_loader_uses_document_preview_for_supported_documents(
    tmp_path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    report = project / "report.docx"
    report.write_bytes(b"placeholder")
    preview_loader = StubDocumentPreviewLoader(
        previews_by_path={
            str(report): FilePreviewState.with_content("# Report\n\nConverted\n", False),
        }
    )
    loader = LiveBrowserSnapshotLoader(document_preview_loader=preview_loader)

    snapshot = loader.load_browser_snapshot(str(project), cursor_path=str(report))

    assert snapshot.child_pane.mode == "preview"
    assert snapshot.child_pane.preview_path == str(report)
    assert snapshot.child_pane.preview_content == "# Report\n\nConverted\n"
    assert preview_loader.calls == [f"{report}:{64 * 1024}"]


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


def test_live_browser_snapshot_loader_skips_image_preview_when_disabled(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    image = project / "preview.png"
    image.write_bytes(b"png")
    preview_loader = StubImagePreviewLoader(
        previews_by_path={
            str(image): FilePreviewState.with_content("@@\n", False, content_kind="image"),
        }
    )
    loader = LiveBrowserSnapshotLoader(image_preview_loader=preview_loader)

    pane = loader.load_child_pane_snapshot(
        str(project),
        str(image),
        enable_image_preview=False,
    )

    assert pane.mode == "entries"
    assert pane.entries == ()
    assert preview_loader.calls == []


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


def test_live_browser_snapshot_loader_skips_office_preview_when_disabled(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    report = project / "report.docx"
    report.write_bytes(b"placeholder")
    preview_loader = StubDocumentPreviewLoader(
        previews_by_path={
            str(report): FilePreviewState.with_content("# Report\n\nConverted\n", False),
        }
    )
    loader = LiveBrowserSnapshotLoader(document_preview_loader=preview_loader)

    pane = loader.load_child_pane_snapshot(
        str(project),
        str(report),
        enable_office_preview=False,
    )

    assert pane.mode == "entries"
    assert pane.entries == ()
    assert preview_loader.calls == []
 

def test_live_browser_snapshot_loader_caches_document_previews(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    report = project / "slides.pptx"
    report.write_bytes(b"placeholder")
    preview_loader = StubDocumentPreviewLoader(
        previews_by_path={
            str(report): FilePreviewState.with_content("Slide 1\n", False),
        }
    )
    loader = LiveBrowserSnapshotLoader(document_preview_loader=preview_loader)

    first = loader.load_child_pane_snapshot(str(project), str(report))
    second = loader.load_child_pane_snapshot(str(project), str(report))

    assert first == second
    assert preview_loader.calls == [f"{report}:{64 * 1024}"]


def test_pandoc_document_preview_loader_returns_none_when_pandoc_is_missing(
    tmp_path,
    monkeypatch,
) -> None:
    from zivo.services.browser_snapshot import PandocDocumentPreviewLoader

    report = tmp_path / "report.docx"
    report.write_bytes(b"placeholder")
    loader = PandocDocumentPreviewLoader()

    monkeypatch.setattr(
        "zivo.services.previews.core.shutil.which",
        lambda name: None,
    )

    assert loader.load_preview(report, preview_max_bytes=64 * 1024) is None


def test_pandoc_document_preview_loader_uses_pandoc_command(tmp_path, monkeypatch) -> None:
    from zivo.services.browser_snapshot import PandocDocumentPreviewLoader

    slides = tmp_path / "slides.pptx"
    slides.write_bytes(b"placeholder")
    loader = PandocDocumentPreviewLoader()

    monkeypatch.setattr(
        "zivo.services.previews.core.shutil.which",
        lambda name: "/opt/homebrew/bin/pandoc",
    )

    class _CompletedProcess:
        stdout = b"# Slide 1\n"

    def _run(args, **kwargs):
        assert args == [
            "/opt/homebrew/bin/pandoc",
            "--from",
            "pptx",
            "--to",
            "markdown",
            str(slides),
        ]
        return _CompletedProcess()

    monkeypatch.setattr("zivo.services.previews.core.subprocess.run", _run)

    preview = loader.load_preview(slides, preview_max_bytes=64 * 1024)

    assert preview == FilePreviewState.with_content("# Slide 1\n", False)


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


def test_live_browser_snapshot_loader_detects_png_signature_without_extension(
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
    image = project / "preview.bin"
    image.write_bytes(b"\x89PNG\r\n\x1a\nrest")
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


def test_live_browser_snapshot_loader_uses_pdftotext_for_pdf_preview(
    tmp_path,
    monkeypatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    report = project / "report.pdf"
    report.write_bytes(b"%PDF-1.4")
    loader = LiveBrowserSnapshotLoader()

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


def test_live_browser_snapshot_loader_skips_pdf_preview_when_disabled(
    tmp_path,
    monkeypatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    report = project / "report.pdf"
    report.write_bytes(b"%PDF-1.4")
    loader = LiveBrowserSnapshotLoader()

    monkeypatch.setattr(
        "zivo.services.previews.core.shutil.which",
        lambda name: "/usr/bin/pdftotext",
    )

    pane = loader.load_child_pane_snapshot(
        str(project),
        str(report),
        enable_pdf_preview=False,
    )

    assert pane.mode == "entries"
    assert pane.entries == ()


def test_live_browser_snapshot_loader_builds_grep_context_preview(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    readme = project / "README.md"
    readme.write_text("one\ntwo\nTODO: update docs\nfour\nfive\n", encoding="utf-8")
    loader = LiveBrowserSnapshotLoader()

    pane = loader.load_grep_preview(
        str(project),
        GrepSearchResultState(
            path=str(readme),
            display_path="README.md",
            line_number=3,
            line_text="TODO: update docs",
        ),
    )

    assert pane.mode == "preview"
    assert pane.preview_title == "Preview: README.md:3"
    assert pane.preview_content == "one\ntwo\nTODO: update docs\nfour\nfive\n"
    assert pane.preview_start_line == 1
    assert pane.preview_highlight_line == 3


def test_live_browser_snapshot_loader_marks_unsupported_grep_preview(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    binary = project / "archive.bin"
    binary.write_bytes(b"\x00\x01\x02\x03")
    loader = LiveBrowserSnapshotLoader()

    pane = loader.load_grep_preview(
        str(project),
        GrepSearchResultState(
            path=str(binary),
            display_path="archive.bin",
            line_number=1,
            line_text="",
        ),
    )

    assert pane.mode == "preview"
    assert pane.preview_title == "Preview: archive.bin:1"
    assert pane.preview_content is None
    assert pane.preview_message == "Preview unavailable for this file type"


def test_live_browser_snapshot_loader_marks_permission_denied_preview_candidate(
    tmp_path,
    monkeypatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    readme = project / "README.md"
    readme.write_text("secret\n", encoding="utf-8")

    original_open = Path.open

    def _blocked_open(self: Path, *args, **kwargs):
        if self == readme:
            raise PermissionError("blocked")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", _blocked_open)
    loader = LiveBrowserSnapshotLoader()

    snapshot = loader.load_browser_snapshot(str(project), cursor_path=str(readme))

    assert snapshot.child_pane.mode == "preview"
    assert snapshot.child_pane.preview_path == str(readme)
    assert snapshot.child_pane.preview_content is None
    assert snapshot.child_pane.preview_message == "Preview unavailable: permission denied"


def test_live_browser_snapshot_loader_truncates_large_text_preview(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    readme = project / "README.md"
    readme.write_text("a" * (64 * 1024 + 10), encoding="utf-8")

    loader = LiveBrowserSnapshotLoader()

    snapshot = loader.load_browser_snapshot(str(project), cursor_path=str(readme))

    assert snapshot.child_pane.mode == "preview"
    assert snapshot.child_pane.preview_path == str(readme)
    assert snapshot.child_pane.preview_truncated is True
    assert snapshot.child_pane.preview_content == "a" * (64 * 1024)


def test_live_browser_snapshot_loader_uses_configured_preview_limit(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    readme = project / "README.md"
    readme.write_text("a" * (128 * 1024), encoding="utf-8")

    loader = LiveBrowserSnapshotLoader()

    snapshot = loader.load_browser_snapshot(str(project), cursor_path=str(readme))
    custom_pane = loader.load_child_pane_snapshot(
        str(project),
        str(readme),
        preview_max_bytes=128 * 1024,
    )

    assert snapshot.child_pane.preview_truncated is True
    assert len(snapshot.child_pane.preview_content or "") == 64 * 1024
    assert custom_pane.preview_truncated is False
    assert len(custom_pane.preview_content or "") == 128 * 1024


def test_live_browser_snapshot_loader_caches_text_preview_reads(tmp_path, monkeypatch) -> None:
    project = tmp_path / "project"
    project.mkdir()
    readme = project / "README.md"
    readme.write_text("cached preview\n", encoding="utf-8")

    original_open = Path.open
    open_calls: list[Path] = []

    def _tracking_open(self: Path, *args, **kwargs):
        if self == readme and args and args[0] == "rb":
            open_calls.append(self)
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", _tracking_open)
    loader = LiveBrowserSnapshotLoader()

    first = loader.load_child_pane_snapshot(str(project), str(readme))
    second = loader.load_child_pane_snapshot(str(project), str(readme))

    assert first == second
    assert open_calls == [readme]


def test_live_browser_snapshot_loader_invalidates_preview_cache_when_file_changes(
    tmp_path,
    monkeypatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    readme = project / "README.md"
    readme.write_text("version one\n", encoding="utf-8")

    original_open = Path.open
    open_calls: list[Path] = []

    def _tracking_open(self: Path, *args, **kwargs):
        if self == readme and args and args[0] == "rb":
            open_calls.append(self)
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", _tracking_open)
    loader = LiveBrowserSnapshotLoader()

    first = loader.load_child_pane_snapshot(str(project), str(readme))
    readme.write_text("version two updated\n", encoding="utf-8")
    second = loader.load_child_pane_snapshot(str(project), str(readme))

    assert first.preview_content == "version one\n"
    assert second.preview_content == "version two updated\n"
    assert open_calls == [readme, readme]


def test_live_browser_snapshot_loader_returns_empty_parent_pane_for_root_path() -> None:
    filesystem = StubFilesystemAdapter(
        entries_by_path={
            "/": (
                DirectoryEntryState("/README", "README", "file"),
                DirectoryEntryState("/tmp", "tmp", "dir"),
            )
        }
    )
    loader = LiveBrowserSnapshotLoader(filesystem=filesystem)

    snapshot = loader.load_browser_snapshot("/", cursor_path="/README")

    assert snapshot.current_path == "/"
    assert snapshot.parent_pane.directory_path == "/"
    assert snapshot.parent_pane.entries == ()
    assert snapshot.parent_pane.cursor_path is None
    assert snapshot.current_pane.entries == filesystem.entries_by_path["/"]
    assert filesystem.list_directory_calls == ["/"]


def test_live_browser_snapshot_loader_normalizes_not_found_error() -> None:
    loader = LiveBrowserSnapshotLoader(
        filesystem=StubFilesystemAdapter(errors_by_path={"/missing": FileNotFoundError("nope")})
    )

    with pytest.raises(OSError, match="Not found: /missing"):
        loader.load_browser_snapshot("/missing")


def test_live_browser_snapshot_loader_normalizes_permission_error() -> None:
    loader = LiveBrowserSnapshotLoader(
        filesystem=StubFilesystemAdapter(errors_by_path={"/secret": PermissionError("blocked")})
    )

    with pytest.raises(OSError, match="Permission denied: /secret"):
        loader.load_browser_snapshot("/secret")


def test_live_browser_snapshot_loader_reuses_directory_listings_across_snapshot_requests(
    tmp_path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    docs = project / "docs"
    docs.mkdir()
    (docs / "spec.md").write_text("spec\n", encoding="utf-8")

    filesystem = _build_stub_filesystem(str(project), str(tmp_path), str(docs))
    loader = LiveBrowserSnapshotLoader(filesystem=filesystem)

    first = loader.load_browser_snapshot(str(project), cursor_path=str(docs))
    second = loader.load_browser_snapshot(str(project), cursor_path=str(docs))

    assert first == second
    assert filesystem.list_directory_calls == [str(project), str(tmp_path), str(docs)]


def test_live_browser_snapshot_loader_reuses_cached_child_directory_snapshot(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    docs = project / "docs"
    docs.mkdir()
    (docs / "spec.md").write_text("spec\n", encoding="utf-8")

    filesystem = _build_stub_filesystem(str(project), str(tmp_path), str(docs))
    loader = LiveBrowserSnapshotLoader(filesystem=filesystem)

    loader.load_browser_snapshot(str(project), cursor_path=str(docs))
    loader.load_child_pane_snapshot(str(project), str(docs))

    assert filesystem.list_directory_calls == [str(project), str(tmp_path), str(docs)]


def test_live_browser_snapshot_loader_invalidates_selected_directory_cache_entry(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    docs = project / "docs"
    docs.mkdir()
    (docs / "spec.md").write_text("spec\n", encoding="utf-8")

    filesystem = _build_stub_filesystem(str(project), str(tmp_path), str(docs))
    loader = LiveBrowserSnapshotLoader(filesystem=filesystem)

    loader.load_browser_snapshot(str(project), cursor_path=str(docs))
    loader.invalidate_directory_listing_cache((str(project),))
    loader.load_browser_snapshot(str(project), cursor_path=str(docs))

    assert filesystem.list_directory_calls == [
        str(project),
        str(tmp_path),
        str(docs),
        str(project),
    ]


def test_resolve_cursor_path_returns_cursor_path_when_found() -> None:
    entries = (
        DirectoryEntryState("/a/.hidden", ".hidden", "file", hidden=True),
        DirectoryEntryState("/a/visible", "visible", "file"),
    )
    result = _resolve_cursor_path(entries, "/a/visible")
    assert result == "/a/visible"


def test_resolve_cursor_path_returns_none_when_entries_empty() -> None:
    result = _resolve_cursor_path((), None)
    assert result is None


def test_resolve_cursor_path_skips_hidden_when_show_hidden_false() -> None:
    entries = (
        DirectoryEntryState("/a/.hidden", ".hidden", "dir", hidden=True),
        DirectoryEntryState("/a/.config", ".config", "dir", hidden=True),
        DirectoryEntryState("/a/data", "data", "dir"),
        DirectoryEntryState("/a/src", "src", "dir"),
    )
    result = _resolve_cursor_path(entries, None, show_hidden=False)
    assert result == "/a/data"


def test_resolve_cursor_path_returns_first_entry_when_all_hidden() -> None:
    entries = (
        DirectoryEntryState("/a/.hidden", ".hidden", "dir", hidden=True),
        DirectoryEntryState("/a/.config", ".config", "dir", hidden=True),
    )
    result = _resolve_cursor_path(entries, None, show_hidden=False)
    assert result == "/a/.hidden"


def test_resolve_cursor_path_does_not_skip_hidden_when_show_hidden_true() -> None:
    entries = (
        DirectoryEntryState("/a/.hidden", ".hidden", "dir", hidden=True),
        DirectoryEntryState("/a/.config", ".config", "dir", hidden=True),
        DirectoryEntryState("/a/data", "data", "dir"),
    )
    result = _resolve_cursor_path(entries, None, show_hidden=True)
    assert result == "/a/.hidden"


def test_resolve_cursor_path_returns_first_entry_when_cursor_missing() -> None:
    entries = (
        DirectoryEntryState("/a/src", "src", "dir"),
        DirectoryEntryState("/a/docs", "docs", "dir"),
    )
    result = _resolve_cursor_path(entries, "/a/missing", show_hidden=False)
    assert result == "/a/src"


def test_resolve_cursor_path_skips_hidden_by_default() -> None:
    entries = (
        DirectoryEntryState("/a/.hidden", ".hidden", "dir", hidden=True),
        DirectoryEntryState("/a/visible", "visible", "dir"),
    )
    result = _resolve_cursor_path(entries, None)
    assert result == "/a/visible"


def test_fake_browser_snapshot_loader_prefers_requested_cursor_path() -> None:
    path = "/tmp/zivo"
    docs = f"{path}/docs"
    src = f"{path}/src"
    snapshot = BrowserSnapshot(
        current_path=path,
        parent_pane=PaneState(directory_path="/tmp", entries=()),
        current_pane=PaneState(
            directory_path=path,
            entries=(
                DirectoryEntryState(docs, "docs", "dir"),
                DirectoryEntryState(src, "src", "dir"),
            ),
            cursor_path=docs,
        ),
        child_pane=PaneState(directory_path=docs, entries=()),
    )
    loader = FakeBrowserSnapshotLoader(
        snapshots={path: snapshot},
        child_panes={(path, src): PaneState(directory_path=src, entries=())},
    )

    resolved = loader.load_browser_snapshot(path, cursor_path=src)

    assert resolved.current_pane.cursor_path == src
    assert resolved.child_pane.directory_path == src


def test_fake_browser_snapshot_loader_records_invalidated_directory_listing_paths() -> None:
    loader = FakeBrowserSnapshotLoader()

    loader.invalidate_directory_listing_cache(("/tmp/project", "/tmp/project/docs"))

    assert loader.invalidated_directory_listing_paths == [
        (
            str(Path("/tmp/project").resolve()),
            str(Path("/tmp/project/docs").resolve()),
        ),
    ]


def test_fake_browser_snapshot_loader_returns_empty_parent_pane_for_root_path() -> None:
    loader = FakeBrowserSnapshotLoader()

    snapshot = loader.load_browser_snapshot("/")

    assert snapshot.current_path == "/"
    assert snapshot.parent_pane.directory_path == "/"
    assert snapshot.parent_pane.entries == ()


# ヒューリスティックテキスト判定のテスト


def test_live_browser_snapshot_loader_previews_text_file_without_extension(tmp_path) -> None:
    """拡張子がないテキストファイルをプレビューできること."""
    project = tmp_path / "project"
    project.mkdir()
    readme = project / "README"
    readme.write_text("This is a README file.\n", encoding="utf-8")

    loader = LiveBrowserSnapshotLoader()

    snapshot = loader.load_browser_snapshot(str(project), cursor_path=str(readme))

    assert snapshot.current_pane.cursor_path == str(readme)
    assert snapshot.child_pane.mode == "preview"
    assert snapshot.child_pane.preview_path == str(readme)
    assert snapshot.child_pane.preview_content == "This is a README file.\n"
    assert snapshot.child_pane.preview_truncated is False


def test_live_browser_snapshot_loader_previews_text_file_with_unknown_extension(tmp_path) -> None:
    """拡張子リストにないテキストファイルをプレビューできること."""
    project = tmp_path / "project"
    project.mkdir()
    custom = project / "config.custom"
    custom.write_text("custom setting\n", encoding="utf-8")

    loader = LiveBrowserSnapshotLoader()

    snapshot = loader.load_browser_snapshot(str(project), cursor_path=str(custom))

    assert snapshot.current_pane.cursor_path == str(custom)
    assert snapshot.child_pane.mode == "preview"
    assert snapshot.child_pane.preview_path == str(custom)
    assert snapshot.child_pane.preview_content == "custom setting\n"
    assert snapshot.child_pane.preview_truncated is False


def test_live_browser_snapshot_loader_rejects_binary_file_with_unknown_extension(tmp_path) -> None:
    """拡張子リストにないバイナリファイルをプレビューしないこと."""
    project = tmp_path / "project"
    project.mkdir()
    binary = project / "data.unknown"
    binary.write_bytes(b"\x00\x01\x02\x03\x04\x05")

    loader = LiveBrowserSnapshotLoader()

    snapshot = loader.load_browser_snapshot(str(project), cursor_path=str(binary))

    assert snapshot.current_pane.cursor_path == str(binary)
    assert snapshot.child_pane.mode == "preview"
    assert snapshot.child_pane.preview_path == str(binary)
    assert snapshot.child_pane.preview_content is None
    assert snapshot.child_pane.preview_message == "Preview unavailable for this file type"


def test_live_browser_snapshot_loader_previews_empty_file_as_text(tmp_path) -> None:
    """空ファイルをテキストとしてプレビューできること."""
    project = tmp_path / "project"
    project.mkdir()
    empty = project / "empty.txt"
    empty.write_text("", encoding="utf-8")

    loader = LiveBrowserSnapshotLoader()

    snapshot = loader.load_browser_snapshot(str(project), cursor_path=str(empty))

    assert snapshot.current_pane.cursor_path == str(empty)
    assert snapshot.child_pane.mode == "preview"
    assert snapshot.child_pane.preview_path == str(empty)
    assert snapshot.child_pane.preview_content == ""
    assert snapshot.child_pane.preview_truncated is False


def test_live_browser_snapshot_loader_previews_high_printable_ratio_file(tmp_path) -> None:
    """printable率が70%以上のファイルをテキストとしてプレビューできること."""
    project = tmp_path / "project"
    project.mkdir()
    # printable率が高いテキスト（ASCII文字のみ）
    text = project / "high_printable.txt"
    text.write_text("Hello World! " * 50 + "\n", encoding="utf-8")

    loader = LiveBrowserSnapshotLoader()

    snapshot = loader.load_browser_snapshot(str(project), cursor_path=str(text))

    assert snapshot.current_pane.cursor_path == str(text)
    assert snapshot.child_pane.mode == "preview"
    assert snapshot.child_pane.preview_path == str(text)
    assert snapshot.child_pane.preview_content is not None
    assert "Hello World!" in snapshot.child_pane.preview_content


def test_live_browser_snapshot_loader_rejects_low_printable_ratio_file(tmp_path) -> None:
    """printable率が70%未満のファイルをバイナリとして扱うこと."""
    project = tmp_path / "project"
    project.mkdir()
    # printable率が低いデータ（バイナリっぽいデータ）
    binary = project / "low_printable.dat"
    # 70%未満のprintable率になるように作成
    content = bytes([i % 256 for i in range(512)])  # ランダムっぽいデータ
    binary.write_bytes(content)

    loader = LiveBrowserSnapshotLoader()

    snapshot = loader.load_browser_snapshot(str(project), cursor_path=str(binary))

    assert snapshot.current_pane.cursor_path == str(binary)
    assert snapshot.child_pane.mode == "preview"
    assert snapshot.child_pane.preview_path == str(binary)
    assert snapshot.child_pane.preview_content is None
    assert snapshot.child_pane.preview_message == "Preview unavailable for this file type"


def test_live_browser_snapshot_loader_grep_preview_with_unknown_extension(tmp_path) -> None:
    """grepプレビューで拡張子リストにないテキストファイルをプレビューできること."""
    project = tmp_path / "project"
    project.mkdir()
    custom = project / "source.custom"
    custom.write_text("line 1\nline 2\nline 3\n", encoding="utf-8")

    loader = LiveBrowserSnapshotLoader()

    result = GrepSearchResultState(
        path=str(custom),
        display_path="source.custom",
        line_number=2,
        line_text="line 2",
    )
    preview = loader.load_grep_preview(str(project), result, context_lines=1)

    assert preview.mode == "preview"
    assert preview.preview_path == str(custom)
    assert preview.preview_content is not None
    assert "line 1" in preview.preview_content
    assert "line 2" in preview.preview_content
    assert "line 3" in preview.preview_content
    assert preview.preview_start_line == 1
    assert preview.preview_highlight_line == 2


def test_live_browser_snapshot_loader_returns_permission_denied_for_denied_directory(
    tmp_path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    secret = project / "secret"
    secret.mkdir()

    loader = LiveBrowserSnapshotLoader(
        filesystem=StubFilesystemAdapter(
            entries_by_path={str(project): ()},
            errors_by_path={str(secret): PermissionError("blocked")},
        )
    )

    pane = loader.load_child_pane_snapshot(str(project), str(secret))

    assert pane.mode == "preview"
    assert pane.preview_message == PREVIEW_PERMISSION_DENIED_MESSAGE
    assert pane.entries == ()
    assert pane.directory_path == str(secret)


def test_live_browser_snapshot_loader_propagates_non_permission_os_error_for_directory(
    tmp_path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    inaccessible = project / "inaccessible"
    inaccessible.mkdir()

    loader = LiveBrowserSnapshotLoader(
        filesystem=StubFilesystemAdapter(
            entries_by_path={str(project): ()},
            errors_by_path={str(inaccessible): FileNotFoundError("gone")},
        )
    )

    with pytest.raises(OSError, match="Not found:"):
        loader.load_child_pane_snapshot(str(project), str(inaccessible))


def test_live_browser_snapshot_loader_caches_grep_context_preview_reads(
    tmp_path,
    monkeypatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    readme = project / "README.md"
    readme.write_text("line 1\nline 2\nline 3\nline 4\nline 5\n", encoding="utf-8")

    original_open = Path.open
    open_calls: list[Path] = []

    def _tracking_open(self: Path, *args, **kwargs):
        if self == readme and args and args[0] == "rb":
            open_calls.append(self)
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", _tracking_open)
    loader = LiveBrowserSnapshotLoader()

    first = loader.load_grep_preview(
        str(project),
        GrepSearchResultState(
            path=str(readme),
            display_path="README.md",
            line_number=3,
            line_text="line 3",
        ),
    )
    second = loader.load_grep_preview(
        str(project),
        GrepSearchResultState(
            path=str(readme),
            display_path="README.md",
            line_number=3,
            line_text="line 3",
        ),
    )

    assert first == second
    assert open_calls == [readme]


def test_live_browser_snapshot_loader_invalidates_grep_context_cache_when_file_changes(
    tmp_path,
    monkeypatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    readme = project / "README.md"
    readme.write_text("line 1\nline 2\nline 3\n", encoding="utf-8")

    original_open = Path.open
    open_calls: list[Path] = []

    def _tracking_open(self: Path, *args, **kwargs):
        if self == readme and args and args[0] == "rb":
            open_calls.append(self)
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", _tracking_open)
    loader = LiveBrowserSnapshotLoader()

    first = loader.load_grep_preview(
        str(project),
        GrepSearchResultState(
            path=str(readme),
            display_path="README.md",
            line_number=2,
            line_text="line 2",
        ),
    )
    readme.write_text("line 1 updated\nline 2 updated\nline 3 updated\n", encoding="utf-8")
    second = loader.load_grep_preview(
        str(project),
        GrepSearchResultState(
            path=str(readme),
            display_path="README.md",
            line_number=2,
            line_text="line 2 updated",
        ),
    )

    assert first.preview_content == "line 1\nline 2\nline 3\n"
    assert second.preview_content == "line 1 updated\nline 2 updated\nline 3 updated\n"
    assert len(open_calls) == 2


def test_live_browser_snapshot_loader_grep_cache_respects_different_context_lines(
    tmp_path,
    monkeypatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    readme = project / "README.md"
    readme.write_text("line 1\nline 2\nline 3\nline 4\nline 5\n", encoding="utf-8")

    original_open = Path.open
    open_calls: list[Path] = []

    def _tracking_open(self: Path, *args, **kwargs):
        if self == readme and args and args[0] == "rb":
            open_calls.append(self)
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", _tracking_open)
    loader = LiveBrowserSnapshotLoader()

    # Load with context_lines=1
    first = loader.load_grep_preview(
        str(project),
        GrepSearchResultState(
            path=str(readme),
            display_path="README.md",
            line_number=3,
            line_text="line 3",
        ),
        context_lines=1,
    )

    # Load with context_lines=3 (should be a different cache entry)
    second = loader.load_grep_preview(
        str(project),
        GrepSearchResultState(
            path=str(readme),
            display_path="README.md",
            line_number=3,
            line_text="line 3",
        ),
        context_lines=3,
    )

    assert first.preview_content == "line 2\nline 3\nline 4\n"
    assert second.preview_content == "line 1\nline 2\nline 3\nline 4\nline 5\n"
    assert len(open_calls) == 2  # Both should have opened the file


def test_load_grep_context_preview_reads_file_once(tmp_path, monkeypatch) -> None:
    project = tmp_path / "project"
    project.mkdir()
    readme = project / "README.md"
    readme.write_text("line 1\nline 2\nline 3\nline 4\nline 5\n", encoding="utf-8")

    original_open = Path.open
    open_calls: list[tuple[Path, str]] = []

    def _tracking_open(self: Path, *args, **kwargs):
        if self == readme:
            mode = args[0] if args else kwargs.get("mode", "r")
            open_calls.append((self, mode))
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", _tracking_open)

    from zivo.services.browser_snapshot import _load_grep_context_preview

    preview = _load_grep_context_preview(
        readme, 3, context_lines=1, preview_max_bytes=1024
    )

    assert preview.content == "line 2\nline 3\nline 4\n"
    assert preview.start_line == 2
    assert preview.highlight_line == 3
    # Should only open the file once
    assert len([call for call in open_calls if call[0] == readme]) == 1


def test_load_grep_context_preview_handles_binary_files(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    binary = project / "binary.bin"
    binary.write_bytes(b"\x00\x01\x02\x03\x04\x05")

    from zivo.services.browser_snapshot import (
        PREVIEW_UNSUPPORTED_MESSAGE,
        _load_grep_context_preview,
    )

    preview = _load_grep_context_preview(
        binary, 1, context_lines=1, preview_max_bytes=1024
    )

    assert preview.content is None
    assert preview.message == PREVIEW_UNSUPPORTED_MESSAGE


def test_load_grep_context_preview_handles_permission_denied(tmp_path, monkeypatch) -> None:
    project = tmp_path / "project"
    project.mkdir()
    readme = project / "README.md"
    readme.write_text("line 1\nline 2\nline 3\n", encoding="utf-8")

    original_open = Path.open

    def _permission_denied_open(self: Path, *args, **kwargs):
        if self == readme:
            raise PermissionError("Permission denied")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", _permission_denied_open)

    from zivo.services.browser_snapshot import (
        PREVIEW_PERMISSION_DENIED_MESSAGE,
        _load_grep_context_preview,
    )

    preview = _load_grep_context_preview(
        readme, 2, context_lines=1, preview_max_bytes=1024
    )

    assert preview.content is None
    assert preview.message == PREVIEW_PERMISSION_DENIED_MESSAGE
