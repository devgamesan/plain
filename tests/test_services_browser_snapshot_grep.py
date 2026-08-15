"""Test Services Browser Snapshot Grep tests."""

from tests.support.browser_snapshot import (
    GrepSearchResultState,
    LiveBrowserSnapshotLoader,
    Path,
)


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

def test_live_browser_snapshot_loader_reuses_grep_context_window_for_nearby_results(
    tmp_path,
    monkeypatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    readme = project / "README.md"
    readme.write_text(
        "".join(f"line {line}\n" for line in range(1, 20)),
        encoding="utf-8",
    )

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
        context_lines=1,
    )
    second = loader.load_grep_preview(
        str(project),
        GrepSearchResultState(
            path=str(readme),
            display_path="README.md",
            line_number=4,
            line_text="line 4",
        ),
        context_lines=1,
    )

    assert first.preview_content == "line 2\nline 3\nline 4\n"
    assert second.preview_content == "line 3\nline 4\nline 5\n"
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

def test_live_browser_snapshot_loader_invalidates_grep_context_window_when_file_changes(
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
        context_lines=1,
    )
    readme.write_text("LINE 1\nLINE 2\nLINE 3\nLINE 4\nLINE 5\n", encoding="utf-8")
    second = loader.load_grep_preview(
        str(project),
        GrepSearchResultState(
            path=str(readme),
            display_path="README.md",
            line_number=4,
            line_text="LINE 4",
        ),
        context_lines=1,
    )

    assert first.preview_content == "line 2\nline 3\nline 4\n"
    assert second.preview_content == "LINE 3\nLINE 4\nLINE 5\n"
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
