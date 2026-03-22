from dataclasses import dataclass, field

import pytest

from plain.services import LiveBrowserSnapshotLoader
from plain.state import DirectoryEntryState


@dataclass
class StubFilesystemAdapter:
    entries_by_path: dict[str, tuple[DirectoryEntryState, ...]] = field(default_factory=dict)
    errors_by_path: dict[str, Exception] = field(default_factory=dict)

    def list_directory(self, path: str) -> tuple[DirectoryEntryState, ...]:
        if path in self.errors_by_path:
            raise self.errors_by_path[path]
        return self.entries_by_path[path]


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


def test_live_browser_snapshot_loader_normalizes_not_found_error() -> None:
    loader = LiveBrowserSnapshotLoader(
        filesystem=StubFilesystemAdapter(errors_by_path={"/missing": FileNotFoundError("nope")})
    )

    with pytest.raises(OSError, match="見つかりません: /missing"):
        loader.load_browser_snapshot("/missing")


def test_live_browser_snapshot_loader_normalizes_permission_error() -> None:
    loader = LiveBrowserSnapshotLoader(
        filesystem=StubFilesystemAdapter(errors_by_path={"/secret": PermissionError("blocked")})
    )

    with pytest.raises(OSError, match="アクセスできません: /secret"):
        loader.load_browser_snapshot("/secret")
