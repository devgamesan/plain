"""State models for app-level updates and selector inputs."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from plain.models.shell_data import EntryKind, NotificationLevel

UiMode = Literal["BROWSING", "FILTER", "RENAME", "CREATE", "CONFIRM", "BUSY"]
SortField = Literal["name", "modified", "size"]
ClipboardMode = Literal["copy", "cut", "none"]


@dataclass(frozen=True)
class DirectoryEntryState:
    """Raw directory entry data kept independent from UI formatting."""

    path: str
    name: str
    kind: EntryKind
    size_bytes: int | None = None
    modified_at: datetime | None = None
    hidden: bool = False


@dataclass(frozen=True)
class PaneState:
    """Entries and cursor/selection state for a single pane."""

    directory_path: str
    entries: tuple[DirectoryEntryState, ...]
    cursor_path: str | None = None
    selected_paths: frozenset[str] = frozenset()


@dataclass(frozen=True)
class SortState:
    """Sort configuration used by selectors."""

    field: SortField = "name"
    descending: bool = False
    directories_first: bool = True


@dataclass(frozen=True)
class FilterState:
    """Name-based filter configuration."""

    query: str = ""
    recursive: bool = False
    active: bool = False


@dataclass(frozen=True)
class ClipboardState:
    """Clipboard metadata for future file operations."""

    mode: ClipboardMode = "none"
    paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class HistoryState:
    """Back/forward navigation history."""

    back: tuple[str, ...] = ()
    forward: tuple[str, ...] = ()


@dataclass(frozen=True)
class NotificationState:
    """Transient notification rendered by the UI shell."""

    level: NotificationLevel
    message: str


@dataclass(frozen=True)
class BrowserSnapshot:
    """Pane snapshot payload returned from async loaders."""

    current_path: str
    parent_pane: PaneState
    current_pane: PaneState
    child_pane: PaneState


@dataclass(frozen=True)
class AppState:
    """Single source of truth for reducer-managed application state."""

    current_path: str
    parent_pane: PaneState
    current_pane: PaneState
    child_pane: PaneState
    sort: SortState = SortState()
    filter: FilterState = FilterState()
    clipboard: ClipboardState = ClipboardState()
    history: HistoryState = HistoryState()
    ui_mode: UiMode = "BROWSING"
    notification: NotificationState | None = None
    pending_browser_snapshot_request_id: int | None = None
    pending_child_pane_request_id: int | None = None
    next_request_id: int = 1


def build_initial_app_state() -> AppState:
    """Return a deterministic initial state used by selector and reducer tests."""

    current_path = "/home/tadashi/develop/plain"
    docs_path = f"{current_path}/docs"

    parent_entries = (
        DirectoryEntryState("/home/tadashi/develop", "develop", "dir"),
        DirectoryEntryState("/home/tadashi/downloads", "downloads", "dir"),
        DirectoryEntryState("/home/tadashi/notes.txt", "notes.txt", "file"),
    )
    current_entries = (
        DirectoryEntryState(
            f"{current_path}/docs",
            "docs",
            "dir",
            modified_at=datetime(2026, 3, 21, 9, 10),
        ),
        DirectoryEntryState(
            f"{current_path}/src",
            "src",
            "dir",
            modified_at=datetime(2026, 3, 20, 19, 42),
        ),
        DirectoryEntryState(
            f"{current_path}/tests",
            "tests",
            "dir",
            modified_at=datetime(2026, 3, 20, 19, 42),
        ),
        DirectoryEntryState(
            f"{current_path}/README.md",
            "README.md",
            "file",
            size_bytes=2_150,
            modified_at=datetime(2026, 3, 21, 8, 55),
        ),
        DirectoryEntryState(
            f"{current_path}/pyproject.toml",
            "pyproject.toml",
            "file",
            size_bytes=712,
            modified_at=datetime(2026, 3, 20, 18, 11),
        ),
    )
    child_entries = (
        DirectoryEntryState(f"{docs_path}/spec_mvp.md", "spec_mvp.md", "file"),
        DirectoryEntryState(f"{docs_path}/notes.md", "notes.md", "file"),
        DirectoryEntryState(f"{docs_path}/wireframes", "wireframes", "dir"),
    )

    return AppState(
        current_path=current_path,
        parent_pane=PaneState(directory_path="/home/tadashi", entries=parent_entries),
        current_pane=PaneState(
            directory_path=current_path,
            entries=current_entries,
            cursor_path=f"{current_path}/docs",
        ),
        child_pane=PaneState(directory_path=docs_path, entries=child_entries),
        sort=SortState(field="name", descending=False, directories_first=True),
        filter=FilterState(query="", recursive=False, active=False),
    )


def build_placeholder_app_state(current_path: str) -> AppState:
    """Return an empty browser state used before the first snapshot loads."""

    resolved_path = str(Path(current_path).resolve())
    parent_path = str(Path(resolved_path).parent)
    return AppState(
        current_path=resolved_path,
        parent_pane=PaneState(directory_path=parent_path, entries=()),
        current_pane=PaneState(directory_path=resolved_path, entries=()),
        child_pane=PaneState(directory_path=resolved_path, entries=()),
    )
