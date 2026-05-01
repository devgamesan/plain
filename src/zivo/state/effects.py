"""Pure effect descriptions emitted by the reducer."""

from dataclasses import dataclass

from zivo.models import (
    AppConfig,
    CreatePathRequest,
    CreateSymlinkRequest,
    CreateZipArchiveRequest,
    CustomActionExecutionRequest,
    DeleteRequest,
    ExternalLaunchRequest,
    ExtractArchiveRequest,
    PasteRequest,
    RenameRequest,
    TextReplaceRequest,
    UndoEntry,
)

from .models import AppState, GrepSearchResultState, PaneState, TransferPaneId


@dataclass(frozen=True)
class LoadBrowserSnapshotEffect:
    """Request a browser snapshot load outside the reducer."""

    request_id: int
    path: str
    cursor_path: str | None = None
    blocking: bool = False
    invalidate_paths: tuple[str, ...] = ()
    enable_image_preview: bool = True
    enable_pdf_preview: bool = True
    enable_office_preview: bool = True


@dataclass(frozen=True)
class LoadChildPaneSnapshotEffect:
    """Request a child-pane load outside the reducer."""

    request_id: int
    current_path: str
    cursor_path: str
    preview_max_bytes: int = 64 * 1024
    enable_text_preview: bool = True
    enable_image_preview: bool = True
    enable_pdf_preview: bool = True
    enable_office_preview: bool = True
    preview_columns: int = 80
    grep_result: GrepSearchResultState | None = None
    grep_context_lines: int = 3


@dataclass(frozen=True)
class LoadCurrentPaneEffect:
    """Request current pane load (Phase 1 of progressive loading)."""

    request_id: int
    path: str
    cursor_path: str | None
    invalidate_paths: tuple[str, ...]


@dataclass(frozen=True)
class LoadParentChildEffect:
    """Request parent/child panes load (Phase 2 of progressive loading)."""

    request_id: int
    path: str
    cursor_path: str | None
    current_pane: PaneState
    enable_text_preview: bool = True
    enable_image_preview: bool = True
    enable_pdf_preview: bool = True
    enable_office_preview: bool = True


@dataclass(frozen=True)
class LoadTransferPaneEffect:
    """Request a directory snapshot for a transfer pane."""

    request_id: int
    pane_id: TransferPaneId
    path: str
    cursor_path: str | None = None
    invalidate_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class RunDirectorySizeEffect:
    """Execute recursive size calculation outside the reducer."""

    request_id: int
    paths: tuple[str, ...]


@dataclass(frozen=True)
class RunAttributeInspectionEffect:
    """Load detailed metadata for the attribute dialog outside the reducer."""

    request_id: int
    path: str


@dataclass(frozen=True)
class RunClipboardPasteEffect:
    """Execute a clipboard paste outside the reducer."""

    request_id: int
    request: PasteRequest


@dataclass(frozen=True)
class RunFileMutationEffect:
    """Execute a rename/create mutation outside the reducer."""

    request_id: int
    request: RenameRequest | CreatePathRequest | CreateSymlinkRequest | DeleteRequest


@dataclass(frozen=True)
class RunUndoEffect:
    """Execute an undo operation outside the reducer."""

    request_id: int
    entry: UndoEntry


@dataclass(frozen=True)
class RunArchivePreparationEffect:
    """Inspect an archive before extraction begins."""

    request_id: int
    request: ExtractArchiveRequest


@dataclass(frozen=True)
class RunArchiveExtractEffect:
    """Execute archive extraction outside the reducer."""

    request_id: int
    request: ExtractArchiveRequest


@dataclass(frozen=True)
class RunZipCompressPreparationEffect:
    """Inspect zip-compression inputs before execution begins."""

    request_id: int
    request: CreateZipArchiveRequest


@dataclass(frozen=True)
class RunZipCompressEffect:
    """Execute zip compression outside the reducer."""

    request_id: int
    request: CreateZipArchiveRequest


@dataclass(frozen=True)
class RunExternalLaunchEffect:
    """Execute an external file or terminal launch outside the reducer."""

    request_id: int
    request: ExternalLaunchRequest


@dataclass(frozen=True)
class RunFileSearchEffect:
    """Execute a recursive filename search outside the reducer."""

    request_id: int
    root_path: str
    query: str
    show_hidden: bool


@dataclass(frozen=True)
class RunGrepSearchEffect:
    """Execute a recursive content search outside the reducer."""

    request_id: int
    root_path: str
    query: str
    show_hidden: bool
    include_globs: tuple[str, ...] = ()
    exclude_globs: tuple[str, ...] = ()


@dataclass(frozen=True)
class RunTextReplacePreviewEffect:
    """Preview text replacement across selected files."""

    request_id: int
    request: TextReplaceRequest


@dataclass(frozen=True)
class RunTextReplaceApplyEffect:
    """Apply text replacement across selected files."""

    request_id: int
    request: TextReplaceRequest


@dataclass(frozen=True)
class RunConfigSaveEffect:
    """Persist the current config editor draft to disk."""

    request_id: int
    path: str
    config: AppConfig


@dataclass(frozen=True)
class RunShellCommandEffect:
    """Execute a shell command in the supplied directory."""

    request_id: int
    cwd: str
    command: str


@dataclass(frozen=True)
class RunCustomActionEffect:
    """Execute a resolved custom action."""

    request_id: int
    request: CustomActionExecutionRequest


@dataclass(frozen=True)
class ExitCurrentPathEffect:
    """Exit the application and return the current path."""

    return_code: int = 0


Effect = (
    LoadBrowserSnapshotEffect
    | LoadChildPaneSnapshotEffect
    | LoadCurrentPaneEffect
    | LoadParentChildEffect
    | LoadTransferPaneEffect
    | RunDirectorySizeEffect
    | RunAttributeInspectionEffect
    | RunClipboardPasteEffect
    | RunFileMutationEffect
    | RunUndoEffect
    | RunArchivePreparationEffect
    | RunArchiveExtractEffect
    | RunZipCompressPreparationEffect
    | RunZipCompressEffect
    | RunExternalLaunchEffect
    | RunFileSearchEffect
    | RunGrepSearchEffect
    | RunTextReplacePreviewEffect
    | RunTextReplaceApplyEffect
    | RunConfigSaveEffect
    | RunShellCommandEffect
    | RunCustomActionEffect
    | ExitCurrentPathEffect
)


@dataclass(frozen=True)
class ReduceResult:
    """State transition result plus side effects to run externally."""

    state: AppState
    effects: tuple[Effect, ...] = ()
