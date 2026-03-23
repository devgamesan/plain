from dataclasses import dataclass, field

import pytest

from plain.services import FakeBrowserSnapshotLoader, LiveBrowserSnapshotLoader
from plain.state import BrowserSnapshot, DirectoryEntryState, PaneState


@dataclass
class StubFilesystemAdapter:
    entries_by_path: dict[str, tuple[DirectoryEntryState, ...]] = field(default_factory=dict)
    errors_by_path: dict[str, Exception] = field(default_factory=dict)
    recursive_entries_by_key: dict[tuple[str, str], tuple[DirectoryEntryState, ...]] = field(
        default_factory=dict
    )

    def list_directory(self, path: str) -> tuple[DirectoryEntryState, ...]:
        if path in self.errors_by_path:
            raise self.errors_by_path[path]
        return self.entries_by_path[path]

    def list_directory_recursive(self, path: str, query: str) -> tuple[DirectoryEntryState, ...]:
        if path in self.errors_by_path:
            raise self.errors_by_path[path]
        return self.recursive_entries_by_key[(path, query)]


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
    (src / "main.py").write_text("print('plain')\n", encoding="utf-8")

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
    assert snapshot.child_pane.directory_path == str(project)
    assert snapshot.child_pane.entries == ()


def test_live_browser_snapshot_loader_searches_entries_recursively(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    docs = project / "docs"
    docs.mkdir()
    archive = docs / "archive"
    archive.mkdir()
    src = project / "src"
    src.mkdir()
    (docs / "spec.md").write_text("spec\n", encoding="utf-8")
    (archive / "spec-old.md").write_text("old\n", encoding="utf-8")
    (src / "spec_helper.py").write_text("print('plain')\n", encoding="utf-8")

    loader = LiveBrowserSnapshotLoader()

    entries = loader.load_recursive_entries(str(project), "spec")

    assert {entry.name for entry in entries} == {"spec.md", "spec-old.md", "spec_helper.py"}
    assert {entry.path for entry in entries} == {
        str(docs / "spec.md"),
        str(archive / "spec-old.md"),
        str(src / "spec_helper.py"),
    }


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


def test_fake_browser_snapshot_loader_prefers_requested_cursor_path() -> None:
    path = "/tmp/plain"
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
