from dataclasses import dataclass, field

import pytest

from peneo.adapters import LocalFilesystemAdapter
from peneo.services import FakeBrowserSnapshotLoader, LiveBrowserSnapshotLoader
from peneo.state import BrowserSnapshot, DirectoryEntryState, PaneState


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
    (src / "main.py").write_text("print('peneo')\n", encoding="utf-8")

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
    assert snapshot.child_pane.mode == "entries"
    assert snapshot.child_pane.preview_content is None


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
    path = "/tmp/peneo"
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
    assert snapshot.parent_pane.cursor_path is None
