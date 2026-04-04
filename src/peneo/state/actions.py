"""Reducer actions for app state transitions."""

from dataclasses import dataclass
from typing import Literal

from peneo.models import (
    AppConfig,
    ConflictResolution,
    CreateKind,
    CreateZipArchiveRequest,
    CreateZipArchiveResult,
    ExternalLaunchRequest,
    ExtractArchiveRequest,
    ExtractArchiveResult,
    FileMutationResult,
    PasteConflict,
    PasteRequest,
    PasteSummary,
    ShellCommandResult,
)

from .models import (
    AppState,
    BrowserSnapshot,
    FileSearchResultState,
    GrepSearchResultState,
    NotificationState,
    PaneState,
    SortField,
    SplitTerminalFocusTarget,
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
class BeginExtractArchiveInput:
    """Enter extract input mode for a supported archive."""

    source_path: str


@dataclass(frozen=True)
class BeginZipCompressInput:
    """Enter zip-compression input mode for one or more paths."""

    source_paths: tuple[str, ...]


@dataclass(frozen=True)
class BeginFileSearch:
    """Open the command palette in file search mode."""


@dataclass(frozen=True)
class BeginGrepSearch:
    """Open the command palette in grep search mode."""


@dataclass(frozen=True)
class BeginHistorySearch:
    """Open the command palette in directory history mode."""


@dataclass(frozen=True)
class BeginBookmarkSearch:
    """Open the command palette in bookmark-list mode."""


@dataclass(frozen=True)
class BeginGoToPath:
    """Open the command palette in go-to-path mode."""


@dataclass(frozen=True)
class BeginCommandPalette:
    """Open the command palette."""


@dataclass(frozen=True)
class BeginShellCommandInput:
    """Open the shell command input dialog."""


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
class DismissConfigEditor:
    """Close the config editor without saving pending changes."""


@dataclass(frozen=True)
class MoveConfigEditorCursor:
    """Move the config editor cursor by the provided delta."""

    delta: int


@dataclass(frozen=True)
class CycleConfigEditorValue:
    """Advance or reverse the selected config editor value."""

    delta: int


@dataclass(frozen=True)
class SaveConfigEditor:
    """Persist the current config editor draft to config.toml."""


@dataclass(frozen=True)
class FileSearchCompleted:
    """Apply completed file-search results to the command palette."""

    request_id: int
    query: str
    results: tuple[FileSearchResultState, ...]


@dataclass(frozen=True)
class FileSearchFailed:
    """Apply a terminal file-search failure."""

    request_id: int
    query: str
    message: str
    invalid_query: bool = False


@dataclass(frozen=True)
class GrepSearchCompleted:
    """Apply completed grep-search results to the command palette."""

    request_id: int
    query: str
    results: tuple[GrepSearchResultState, ...]


@dataclass(frozen=True)
class GrepSearchFailed:
    """Apply a terminal grep-search failure."""

    request_id: int
    query: str
    message: str
    invalid_query: bool = False


@dataclass(frozen=True)
class SetPendingInputValue:
    """Update the rename/create text input value."""

    value: str


@dataclass(frozen=True)
class SetShellCommandValue:
    """Update the pending shell command input."""

    command: str


@dataclass(frozen=True)
class SubmitPendingInput:
    """Submit the active rename/create text input."""


@dataclass(frozen=True)
class CancelPendingInput:
    """Cancel the active rename/create text input."""


@dataclass(frozen=True)
class SubmitShellCommand:
    """Submit the active shell command input."""


@dataclass(frozen=True)
class CancelShellCommandInput:
    """Cancel the active shell command input."""


@dataclass(frozen=True)
class MoveCursor:
    """Move the cursor within a caller-provided visible path list."""

    delta: int
    visible_paths: tuple[str, ...]


@dataclass(frozen=True)
class JumpCursor:
    """Jump cursor to the start or end of the visible path list."""

    position: Literal["start", "end"]
    visible_paths: tuple[str, ...]


@dataclass(frozen=True)
class MoveCursorAndSelectRange:
    """Move the cursor and replace the current selection with an anchored range."""

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
class GoToHomeDirectory:
    """Navigate to the user's home directory."""


@dataclass(frozen=True)
class ReloadDirectory:
    """Reload the current directory snapshot."""


@dataclass(frozen=True)
class GoBack:
    """Navigate to the previous directory in the history stack."""


@dataclass(frozen=True)
class GoForward:
    """Navigate to the next directory in the history forward stack."""


@dataclass(frozen=True)
class ExitCurrentPath:
    """Exit the application and return the current path."""

    return_code: int = 0


@dataclass(frozen=True)
class OpenPathWithDefaultApp:
    """Open a filesystem path with the OS default application."""

    path: str


@dataclass(frozen=True)
class OpenPathInEditor:
    """Open a file path with the configured editor."""

    path: str


@dataclass(frozen=True)
class OpenTerminalAtPath:
    """Open a new terminal rooted at the supplied directory path."""

    path: str


@dataclass(frozen=True)
class ShowAttributes:
    """Open the attribute dialog for the current single target."""


@dataclass(frozen=True)
class CopyPathsToClipboard:
    """Copy the current target path list to the system clipboard."""


@dataclass(frozen=True)
class AddBookmark:
    """Persist the supplied directory path as a bookmark."""

    path: str


@dataclass(frozen=True)
class RemoveBookmark:
    """Remove the supplied directory path from bookmarks."""

    path: str


@dataclass(frozen=True)
class ToggleSplitTerminal:
    """Open or close the embedded split terminal."""


@dataclass(frozen=True)
class FocusSplitTerminal:
    """Move input focus between the browser and split terminal."""

    target: SplitTerminalFocusTarget


@dataclass(frozen=True)
class SendSplitTerminalInput:
    """Write input bytes into the active split terminal session."""

    data: str


@dataclass(frozen=True)
class PasteFromClipboardToTerminal:
    """Paste clipboard contents into the active split terminal session."""


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
class SelectAllVisibleEntries:
    """Select every currently visible entry in the current pane."""

    paths: tuple[str, ...]


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
class ConfirmArchiveExtract:
    """Confirm the pending archive extraction request."""


@dataclass(frozen=True)
class CancelArchiveExtractConfirmation:
    """Return from archive extraction confirmation to input editing."""


@dataclass(frozen=True)
class ConfirmZipCompress:
    """Confirm the pending zip compression request."""


@dataclass(frozen=True)
class CancelZipCompressConfirmation:
    """Return from zip-compression confirmation to input editing."""


@dataclass(frozen=True)
class DismissNameConflict:
    """Dismiss the pending rename/create conflict dialog."""


@dataclass(frozen=True)
class DismissAttributeDialog:
    """Dismiss the pending read-only attribute dialog."""


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
class RequestDirectorySizes:
    """Request asynchronous recursive sizes for visible directories."""

    paths: tuple[str, ...]


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
class DirectorySizesLoaded:
    """Apply completed recursive directory sizes."""

    request_id: int
    sizes: tuple[tuple[str, int], ...]
    failures: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class DirectorySizesFailed:
    """Apply a terminal recursive size failure."""

    request_id: int
    paths: tuple[str, ...]
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
class ArchivePreparationCompleted:
    """Apply preflight archive scan details before extraction begins."""

    request_id: int
    request: ExtractArchiveRequest
    total_entries: int
    conflict_count: int = 0
    first_conflict_path: str | None = None


@dataclass(frozen=True)
class ArchivePreparationFailed:
    """Apply a terminal archive preparation failure."""

    request_id: int
    message: str


@dataclass(frozen=True)
class ArchiveExtractProgress:
    """Apply archive extraction progress updates."""

    request_id: int
    completed_entries: int
    total_entries: int
    current_path: str | None = None


@dataclass(frozen=True)
class ArchiveExtractCompleted:
    """Apply the completed archive extraction result."""

    request_id: int
    result: ExtractArchiveResult


@dataclass(frozen=True)
class ArchiveExtractFailed:
    """Apply a terminal archive extraction failure."""

    request_id: int
    message: str


@dataclass(frozen=True)
class ZipCompressPreparationCompleted:
    """Apply preflight zip-compression details before execution begins."""

    request_id: int
    request: CreateZipArchiveRequest
    total_entries: int
    destination_exists: bool = False


@dataclass(frozen=True)
class ZipCompressPreparationFailed:
    """Apply a terminal zip-compression preparation failure."""

    request_id: int
    message: str


@dataclass(frozen=True)
class ZipCompressProgress:
    """Apply zip-compression progress updates."""

    request_id: int
    completed_entries: int
    total_entries: int
    current_path: str | None = None


@dataclass(frozen=True)
class ZipCompressCompleted:
    """Apply the completed zip-compression result."""

    request_id: int
    result: CreateZipArchiveResult


@dataclass(frozen=True)
class ZipCompressFailed:
    """Apply a terminal zip-compression failure."""

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


@dataclass(frozen=True)
class ShellCommandCompleted:
    """Apply a completed shell command execution."""

    request_id: int
    result: ShellCommandResult


@dataclass(frozen=True)
class ShellCommandFailed:
    """Apply a shell command worker failure."""

    request_id: int
    message: str


@dataclass(frozen=True)
class SplitTerminalStarted:
    """Mark the split terminal session as ready."""

    session_id: int
    cwd: str


@dataclass(frozen=True)
class SplitTerminalStartFailed:
    """Apply an embedded split-terminal startup error."""

    session_id: int
    message: str


@dataclass(frozen=True)
class SplitTerminalOutputReceived:
    """Append output from the active split terminal session."""

    session_id: int
    data: str


@dataclass(frozen=True)
class SplitTerminalExited:
    """Apply embedded split-terminal process exit."""

    session_id: int
    exit_code: int | None


@dataclass(frozen=True)
class ConfigSaveCompleted:
    """Apply a successful config save."""

    request_id: int
    path: str
    config: AppConfig


@dataclass(frozen=True)
class ConfigSaveFailed:
    """Apply a failed config save."""

    request_id: int
    message: str


@dataclass(frozen=True)
class SetTerminalHeight:
    """Update the stored terminal height."""

    height: int


Action = (
    InitializeState
    | SetUiMode
    | BeginFilterInput
    | ConfirmFilterInput
    | CancelFilterInput
    | BeginRenameInput
    | BeginCreateInput
    | BeginExtractArchiveInput
    | BeginZipCompressInput
    | BeginFileSearch
    | BeginGrepSearch
    | BeginHistorySearch
    | BeginBookmarkSearch
    | BeginCommandPalette
    | BeginShellCommandInput
    | CancelCommandPalette
    | MoveCommandPaletteCursor
    | SetCommandPaletteQuery
    | SubmitCommandPalette
    | DismissConfigEditor
    | MoveConfigEditorCursor
    | CycleConfigEditorValue
    | SaveConfigEditor
    | FileSearchCompleted
    | FileSearchFailed
    | GrepSearchCompleted
    | GrepSearchFailed
    | SetPendingInputValue
    | SetShellCommandValue
    | SubmitPendingInput
    | SubmitShellCommand
    | CancelPendingInput
    | CancelShellCommandInput
    | MoveCursor
    | MoveCursorAndSelectRange
    | JumpCursor
    | SetCursorPath
    | EnterCursorDirectory
    | GoToParentDirectory
    | GoToHomeDirectory
    | GoBack
    | GoForward
    | ReloadDirectory
    | ExitCurrentPath
    | OpenPathWithDefaultApp
    | OpenPathInEditor
    | OpenTerminalAtPath
    | ShowAttributes
    | CopyPathsToClipboard
    | AddBookmark
    | RemoveBookmark
    | ToggleSplitTerminal
    | FocusSplitTerminal
    | SendSplitTerminalInput
    | PasteFromClipboardToTerminal
    | ToggleSelection
    | ToggleSelectionAndAdvance
    | ClearSelection
    | SelectAllVisibleEntries
    | CopyTargets
    | CutTargets
    | PasteClipboard
    | ResolvePasteConflict
    | CancelPasteConflict
    | ConfirmDeleteTargets
    | CancelDeleteConfirmation
    | ConfirmArchiveExtract
    | CancelArchiveExtractConfirmation
    | ConfirmZipCompress
    | CancelZipCompressConfirmation
    | DismissNameConflict
    | DismissAttributeDialog
    | SetFilterQuery
    | ToggleHiddenFiles
    | SetSort
    | SetNotification
    | RequestBrowserSnapshot
    | RequestDirectorySizes
    | BrowserSnapshotLoaded
    | BrowserSnapshotFailed
    | ChildPaneSnapshotLoaded
    | ChildPaneSnapshotFailed
    | DirectorySizesLoaded
    | DirectorySizesFailed
    | ClipboardPasteNeedsResolution
    | ClipboardPasteCompleted
    | ClipboardPasteFailed
    | ArchivePreparationCompleted
    | ArchivePreparationFailed
    | ArchiveExtractProgress
    | ArchiveExtractCompleted
    | ArchiveExtractFailed
    | ZipCompressPreparationCompleted
    | ZipCompressPreparationFailed
    | ZipCompressProgress
    | ZipCompressCompleted
    | ZipCompressFailed
    | FileMutationCompleted
    | FileMutationFailed
    | ExternalLaunchCompleted
    | ExternalLaunchFailed
    | ShellCommandCompleted
    | ShellCommandFailed
    | SplitTerminalStarted
    | SplitTerminalStartFailed
    | SplitTerminalOutputReceived
    | SplitTerminalExited
    | ConfigSaveCompleted
    | ConfigSaveFailed
    | SetTerminalHeight
)
