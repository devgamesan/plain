from dataclasses import dataclass, field
from pathlib import Path

import pytest

from zivo.adapters import LocalFilesystemAdapter
from zivo.services import (
    PREVIEW_PERMISSION_DENIED_MESSAGE,
    FakeBrowserSnapshotLoader,
    LiveBrowserSnapshotLoader,
)
from zivo.state import BrowserSnapshot, DirectoryEntryState, GrepSearchResultState, PaneState


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
        ("/tmp/project", "/tmp/project/docs"),
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
