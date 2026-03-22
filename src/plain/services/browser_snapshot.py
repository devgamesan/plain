"""Snapshot loading services for three-pane browser state."""

from dataclasses import dataclass, field, replace
from pathlib import Path
from time import sleep
from typing import Mapping, Protocol

from plain.adapters import DirectoryReader, LocalFilesystemAdapter
from plain.state.models import AppState, BrowserSnapshot, PaneState, build_initial_app_state


class BrowserSnapshotLoader(Protocol):
    """Boundary for loading pane snapshots outside the reducer."""

    def load_browser_snapshot(
        self,
        path: str,
        cursor_path: str | None = None,
    ) -> BrowserSnapshot: ...

    def load_child_pane_snapshot(
        self,
        current_path: str,
        cursor_path: str | None,
    ) -> PaneState: ...


@dataclass(frozen=True)
class LiveBrowserSnapshotLoader:
    """Load three-pane snapshots from the local filesystem."""

    filesystem: DirectoryReader = field(default_factory=LocalFilesystemAdapter)

    def load_browser_snapshot(
        self,
        path: str,
        cursor_path: str | None = None,
    ) -> BrowserSnapshot:
        resolved_path = str(Path(path).expanduser().resolve())
        current_entries = self._list_directory(resolved_path)
        resolved_cursor_path = _resolve_cursor_path(current_entries, cursor_path)

        parent_path = str(Path(resolved_path).parent)
        parent_entries = self._list_directory(parent_path)
        parent_cursor_path = (
            resolved_path if _contains_path(parent_entries, resolved_path) else None
        )

        return BrowserSnapshot(
            current_path=resolved_path,
            parent_pane=PaneState(
                directory_path=parent_path,
                entries=parent_entries,
                cursor_path=parent_cursor_path,
            ),
            current_pane=PaneState(
                directory_path=resolved_path,
                entries=current_entries,
                cursor_path=resolved_cursor_path,
            ),
            child_pane=self.load_child_pane_snapshot(resolved_path, resolved_cursor_path),
        )

    def load_child_pane_snapshot(
        self,
        current_path: str,
        cursor_path: str | None,
    ) -> PaneState:
        if cursor_path is None:
            return PaneState(directory_path=current_path, entries=())

        child_path = Path(cursor_path).expanduser().resolve()
        if not child_path.is_dir():
            return PaneState(directory_path=current_path, entries=())

        child_entries = self._list_directory(str(child_path))
        return PaneState(directory_path=str(child_path), entries=child_entries)

    def _list_directory(self, path: str):
        try:
            return self.filesystem.list_directory(path)
        except PermissionError as error:
            raise OSError(f"アクセスできません: {path}") from error
        except FileNotFoundError as error:
            raise OSError(f"見つかりません: {path}") from error
        except NotADirectoryError as error:
            raise OSError(f"ディレクトリではありません: {path}") from error
        except OSError as error:
            raise OSError(str(error) or f"ディレクトリ読み込みに失敗しました: {path}") from error


@dataclass(frozen=True)
class FakeBrowserSnapshotLoader:
    """Deterministic loader used by tests."""

    snapshots: Mapping[str, BrowserSnapshot] = field(default_factory=dict)
    child_panes: Mapping[tuple[str, str | None], PaneState] = field(default_factory=dict)
    failure_messages: Mapping[str, str] = field(default_factory=dict)
    child_failure_messages: Mapping[tuple[str, str | None], str] = field(default_factory=dict)
    default_delay_seconds: float = 0.0
    per_path_delay_seconds: Mapping[str, float] = field(default_factory=dict)
    child_delay_seconds: Mapping[tuple[str, str | None], float] = field(default_factory=dict)

    def load_browser_snapshot(
        self,
        path: str,
        cursor_path: str | None = None,
    ) -> BrowserSnapshot:
        delay = self.per_path_delay_seconds.get(path, self.default_delay_seconds)
        if delay > 0:
            sleep(delay)

        if path in self.failure_messages:
            raise OSError(self.failure_messages[path])

        snapshot = self.snapshots.get(path)
        if snapshot is not None:
            return snapshot

        return _build_fallback_snapshot(path, cursor_path)

    def load_child_pane_snapshot(
        self,
        current_path: str,
        cursor_path: str | None,
    ) -> PaneState:
        key = (current_path, cursor_path)
        delay = self.child_delay_seconds.get(key, self.default_delay_seconds)
        if delay > 0:
            sleep(delay)

        if key in self.child_failure_messages:
            raise OSError(self.child_failure_messages[key])

        pane = self.child_panes.get(key)
        if pane is not None:
            return pane

        return PaneState(directory_path=current_path, entries=())


def snapshot_from_app_state(state: AppState) -> BrowserSnapshot:
    """Convert reducer state into a loader response payload."""

    return BrowserSnapshot(
        current_path=state.current_path,
        parent_pane=state.parent_pane,
        current_pane=state.current_pane,
        child_pane=state.child_pane,
    )


def _build_fallback_snapshot(path: str, cursor_path: str | None) -> BrowserSnapshot:
    initial_state = build_initial_app_state()
    if path == initial_state.current_path:
        state = initial_state
        if cursor_path and _contains_path(state.current_pane.entries, cursor_path):
            state = replace(
                state,
                current_pane=replace(state.current_pane, cursor_path=cursor_path),
            )
        return snapshot_from_app_state(state)

    resolved_path = str(Path(path).expanduser().resolve())
    parent_path = str(Path(resolved_path).parent)
    return BrowserSnapshot(
        current_path=resolved_path,
        parent_pane=PaneState(directory_path=parent_path, entries=()),
        current_pane=PaneState(directory_path=resolved_path, entries=(), cursor_path=cursor_path),
        child_pane=PaneState(directory_path=resolved_path, entries=()),
    )


def _resolve_cursor_path(entries, cursor_path: str | None) -> str | None:
    if cursor_path and _contains_path(entries, cursor_path):
        return cursor_path
    if not entries:
        return None
    return entries[0].path


def _contains_path(entries, path: str) -> bool:
    return any(entry.path == path for entry in entries)
