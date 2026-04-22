"""Asynchronous request and worker-result reducer actions."""

from dataclasses import dataclass

from zivo.models import (
    AppConfig,
    CreateZipArchiveRequest,
    CreateZipArchiveResult,
    ExternalLaunchRequest,
    ExtractArchiveRequest,
    ExtractArchiveResult,
    FileMutationResult,
    PasteAppliedChange,
    PasteConflict,
    PasteRequest,
    PasteSummary,
    ShellCommandResult,
    UndoEntry,
    UndoResult,
)

from .models import AttributeInspectionState, BrowserSnapshot, PaneState, TransferPaneId


@dataclass(frozen=True)
class RequestBrowserSnapshot:
    """Request asynchronous pane data for a directory path."""

    path: str
    cursor_path: str | None = None
    blocking: bool = False
    invalidate_paths: tuple[str, ...] = ()
    progressive: bool = True  # Enable progressive loading (current pane first)


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
class CurrentPaneSnapshotLoaded:
    """Apply a loaded current pane snapshot (Phase 1 of progressive loading)."""

    request_id: int
    current_path: str
    current_pane: PaneState
    parent_pane: PaneState


@dataclass(frozen=True)
class ParentChildSnapshotLoaded:
    """Apply loaded parent/child panes (Phase 2 of progressive loading)."""

    request_id: int
    parent_pane: PaneState
    child_pane: PaneState


@dataclass(frozen=True)
class ParentChildSnapshotFailed:
    """Apply an error raised while loading parent/child panes."""

    request_id: int
    message: str


@dataclass(frozen=True)
class TransferPaneSnapshotLoaded:
    """Apply a loaded directory snapshot to one transfer pane."""

    request_id: int
    pane_id: TransferPaneId
    current_path: str
    pane: PaneState


@dataclass(frozen=True)
class TransferPaneSnapshotFailed:
    """Apply an error raised while loading a transfer pane."""

    request_id: int
    pane_id: TransferPaneId
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
class AttributeInspectionLoaded:
    """Apply detailed metadata loaded for the attribute dialog."""

    request_id: int
    inspection: AttributeInspectionState


@dataclass(frozen=True)
class AttributeInspectionFailed:
    """Apply a terminal attribute-inspection failure."""

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
    applied_changes: tuple[PasteAppliedChange, ...] = ()


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
class UndoCompleted:
    """Apply a completed undo operation."""

    request_id: int
    entry: UndoEntry
    result: UndoResult


@dataclass(frozen=True)
class UndoFailed:
    """Apply a terminal undo operation failure."""

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
