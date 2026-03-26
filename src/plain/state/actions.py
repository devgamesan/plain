"""Reducer actions for app state transitions."""

from dataclasses import dataclass

from plain.models import (
    ConflictResolution,
    CreateKind,
    ExternalLaunchRequest,
    FileMutationResult,
    PasteConflict,
    PasteRequest,
    PasteSummary,
)

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
class BeginRenameInput:
    """Enter rename input mode for a single path."""

    path: str


@dataclass(frozen=True)
class BeginDeleteTargets:
    """Begin deleting the supplied target paths."""

    paths: tuple[str, ...]


@dataclass(frozen=True)
class BeginCreateInput:
    """Enter create input mode for a new file or directory."""

    kind: CreateKind


@dataclass(frozen=True)
class BeginCommandPalette:
    """Open the command palette."""


@dataclass(frozen=True)
class CancelCommandPalette:
    """Close the command palette without running a command."""


@dataclass(frozen=True)
class MoveCommandPaletteCursor:
    """Move the command palette cursor by the provided delta."""

    delta: int


@dataclass(frozen=True)
class SetCommandPaletteQuery:
    """Update the command palette query."""

    query: str


@dataclass(frozen=True)
class SubmitCommandPalette:
    """Run the currently selected command palette command."""


@dataclass(frozen=True)
class SetPendingInputValue:
    """Update the rename/create text input value."""

    value: str


@dataclass(frozen=True)
class SubmitPendingInput:
    """Submit the active rename/create text input."""


@dataclass(frozen=True)
class CancelPendingInput:
    """Cancel the active rename/create text input."""


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
class EnterCursorDirectory:
    """Navigate into the directory currently under the cursor."""


@dataclass(frozen=True)
class GoToParentDirectory:
    """Navigate to the parent directory of the current path."""


@dataclass(frozen=True)
class ReloadDirectory:
    """Reload the current directory snapshot."""


@dataclass(frozen=True)
class OpenPathWithDefaultApp:
    """Open a file path with the OS default application."""

    path: str


@dataclass(frozen=True)
class OpenTerminalAtPath:
    """Open a new terminal rooted at the supplied directory path."""

    path: str


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
class CopyTargets:
    """Copy the current selection or cursor target into the clipboard."""

    paths: tuple[str, ...]


@dataclass(frozen=True)
class CutTargets:
    """Mark the current selection or cursor target for move."""

    paths: tuple[str, ...]


@dataclass(frozen=True)
class PasteClipboard:
    """Paste the current clipboard into the current directory."""


@dataclass(frozen=True)
class ResolvePasteConflict:
    """Continue the pending paste with the chosen conflict resolution."""

    resolution: ConflictResolution


@dataclass(frozen=True)
class CancelPasteConflict:
    """Dismiss the pending paste conflict dialog."""


@dataclass(frozen=True)
class ConfirmDeleteTargets:
    """Confirm the pending delete request."""


@dataclass(frozen=True)
class CancelDeleteConfirmation:
    """Dismiss the pending delete confirmation dialog."""


@dataclass(frozen=True)
class DismissNameConflict:
    """Dismiss the pending rename/create conflict dialog."""


@dataclass(frozen=True)
class SetFilterQuery:
    """Update the active filter query."""

    query: str
    active: bool | None = None


@dataclass(frozen=True)
class ToggleHiddenFiles:
    """Toggle hidden file visibility across the shell."""


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


@dataclass(frozen=True)
class ClipboardPasteNeedsResolution:
    """Store the pending paste request and its conflicts."""

    request_id: int
    request: PasteRequest
    conflicts: tuple[PasteConflict, ...]


@dataclass(frozen=True)
class ClipboardPasteCompleted:
    """Apply the completed paste result."""

    request_id: int
    summary: PasteSummary


@dataclass(frozen=True)
class ClipboardPasteFailed:
    """Apply a terminal clipboard-operation failure."""

    request_id: int
    message: str


@dataclass(frozen=True)
class FileMutationCompleted:
    """Apply a completed rename/create operation."""

    request_id: int
    result: FileMutationResult


@dataclass(frozen=True)
class FileMutationFailed:
    """Apply a terminal rename/create operation failure."""

    request_id: int
    message: str


@dataclass(frozen=True)
class ExternalLaunchCompleted:
    """Apply a completed external launch operation."""

    request_id: int
    request: ExternalLaunchRequest


@dataclass(frozen=True)
class ExternalLaunchFailed:
    """Apply a terminal external launch failure."""

    request_id: int
    request: ExternalLaunchRequest
    message: str


Action = (
    InitializeState
    | SetUiMode
    | BeginFilterInput
    | ConfirmFilterInput
    | CancelFilterInput
    | BeginRenameInput
    | BeginCreateInput
    | BeginCommandPalette
    | CancelCommandPalette
    | MoveCommandPaletteCursor
    | SetCommandPaletteQuery
    | SubmitCommandPalette
    | SetPendingInputValue
    | SubmitPendingInput
    | CancelPendingInput
    | MoveCursor
    | SetCursorPath
    | EnterCursorDirectory
    | GoToParentDirectory
    | ReloadDirectory
    | OpenPathWithDefaultApp
    | OpenTerminalAtPath
    | ToggleSelection
    | ToggleSelectionAndAdvance
    | ClearSelection
    | CopyTargets
    | CutTargets
    | PasteClipboard
    | ResolvePasteConflict
    | CancelPasteConflict
    | DismissNameConflict
    | SetFilterQuery
    | ToggleHiddenFiles
    | SetSort
    | SetNotification
    | RequestBrowserSnapshot
    | BrowserSnapshotLoaded
    | BrowserSnapshotFailed
    | ChildPaneSnapshotLoaded
    | ChildPaneSnapshotFailed
    | ClipboardPasteNeedsResolution
    | ClipboardPasteCompleted
    | ClipboardPasteFailed
    | FileMutationCompleted
    | FileMutationFailed
    | ExternalLaunchCompleted
    | ExternalLaunchFailed
)
