"""Reducer actions for app state transitions."""

from dataclasses import dataclass

from .models import (
    AppState,
    BrowserSnapshot,
    NotificationState,
    PaneState,
    SortField,
    UiMode,
)


@dataclass(frozen=True)
class InitializeState:
    """Replace the entire app state."""

    state: AppState


@dataclass(frozen=True)
class SetUiMode:
    """Change the current UI mode."""

    mode: UiMode


@dataclass(frozen=True)
class BeginFilterInput:
    """Enter filter input mode."""


@dataclass(frozen=True)
class ConfirmFilterInput:
    """Commit the current filter query and return to browsing mode."""


@dataclass(frozen=True)
class CancelFilterInput:
    """Discard the current filter input and return to browsing mode."""


@dataclass(frozen=True)
class MoveCursor:
    """Move the cursor within a caller-provided visible path list."""

    delta: int
    visible_paths: tuple[str, ...]


@dataclass(frozen=True)
class SetCursorPath:
    """Set the current pane cursor to a specific absolute path."""

    path: str | None


@dataclass(frozen=True)
class ToggleSelection:
    """Toggle selection for an entry in the current pane."""

    path: str


@dataclass(frozen=True)
class ToggleSelectionAndAdvance:
    """Toggle selection and advance the cursor within the visible path list."""

    path: str
    visible_paths: tuple[str, ...]


@dataclass(frozen=True)
class ClearSelection:
    """Clear all selections in the current pane."""


@dataclass(frozen=True)
class SetFilterQuery:
    """Update the active filter query."""

    query: str
    active: bool | None = None


@dataclass(frozen=True)
class SetFilterRecursive:
    """Toggle recursive filtering mode."""

    recursive: bool


@dataclass(frozen=True)
class SetSort:
    """Update sort settings."""

    field: SortField
    descending: bool
    directories_first: bool | None = None


@dataclass(frozen=True)
class SetNotification:
    """Update the transient notification rendered in the shell."""

    notification: NotificationState | None


@dataclass(frozen=True)
class RequestBrowserSnapshot:
    """Request asynchronous pane data for a directory path."""

    path: str
    cursor_path: str | None = None
    blocking: bool = False


@dataclass(frozen=True)
class BrowserSnapshotLoaded:
    """Apply a loaded browser snapshot to reducer state."""

    request_id: int
    snapshot: BrowserSnapshot
    blocking: bool = False


@dataclass(frozen=True)
class BrowserSnapshotFailed:
    """Apply an error raised while loading a browser snapshot."""

    request_id: int
    message: str
    blocking: bool = False


@dataclass(frozen=True)
class ChildPaneSnapshotLoaded:
    """Apply a loaded child-pane snapshot to reducer state."""

    request_id: int
    pane: PaneState


@dataclass(frozen=True)
class ChildPaneSnapshotFailed:
    """Apply an error raised while loading the child pane."""

    request_id: int
    message: str


Action = (
    InitializeState
    | SetUiMode
    | BeginFilterInput
    | ConfirmFilterInput
    | CancelFilterInput
    | MoveCursor
    | SetCursorPath
    | ToggleSelection
    | ToggleSelectionAndAdvance
    | ClearSelection
    | SetFilterQuery
    | SetFilterRecursive
    | SetSort
    | SetNotification
    | RequestBrowserSnapshot
    | BrowserSnapshotLoaded
    | BrowserSnapshotFailed
    | ChildPaneSnapshotLoaded
    | ChildPaneSnapshotFailed
)
