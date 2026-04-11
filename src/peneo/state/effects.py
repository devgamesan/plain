"""Pure effect descriptions emitted by the reducer."""

from dataclasses import dataclass

from peneo.models import (
    AppConfig,
    CreatePathRequest,
    CreateZipArchiveRequest,
    DeleteRequest,
    ExternalLaunchRequest,
    ExtractArchiveRequest,
    PasteRequest,
    RenameRequest,
)

from .models import AppState, GrepSearchResultState


@dataclass(frozen=True)
class LoadBrowserSnapshotEffect:
    """Request a browser snapshot load outside the reducer."""

    request_id: int
    path: str
    cursor_path: str | None = None
    blocking: bool = False
    invalidate_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class LoadChildPaneSnapshotEffect:
    """Request a child-pane load outside the reducer."""

    request_id: int
    current_path: str
    cursor_path: str
    grep_result: GrepSearchResultState | None = None
    grep_context_lines: int = 3


@dataclass(frozen=True)
class RunDirectorySizeEffect:
    """Execute recursive size calculation outside the reducer."""

    request_id: int
    paths: tuple[str, ...]


@dataclass(frozen=True)
class RunClipboardPasteEffect:
    """Execute a clipboard paste outside the reducer."""

    request_id: int
    request: PasteRequest


@dataclass(frozen=True)
class RunFileMutationEffect:
    """Execute a rename/create mutation outside the reducer."""

    request_id: int
    request: RenameRequest | CreatePathRequest | DeleteRequest


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


@dataclass(frozen=True)
class StartSplitTerminalEffect:
    """Start a new embedded split-terminal session."""

    session_id: int
    cwd: str


@dataclass(frozen=True)
class WriteSplitTerminalInputEffect:
    """Write input into the active embedded split-terminal session."""

    session_id: int
    data: str


@dataclass(frozen=True)
class PasteFromClipboardEffect:
    """Paste clipboard contents into the active split-terminal session."""

    session_id: int


@dataclass(frozen=True)
class CloseSplitTerminalEffect:
    """Close the active embedded split-terminal session."""

    session_id: int


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


Effect = (
    LoadBrowserSnapshotEffect
    | LoadChildPaneSnapshotEffect
    | RunDirectorySizeEffect
    | RunClipboardPasteEffect
    | RunFileMutationEffect
    | RunArchivePreparationEffect
    | RunArchiveExtractEffect
    | RunZipCompressPreparationEffect
    | RunZipCompressEffect
    | RunExternalLaunchEffect
    | RunFileSearchEffect
    | RunGrepSearchEffect
    | StartSplitTerminalEffect
    | WriteSplitTerminalInputEffect
    | PasteFromClipboardEffect
    | CloseSplitTerminalEffect
    | RunConfigSaveEffect
    | RunShellCommandEffect
)


@dataclass(frozen=True)
class ReduceResult:
    """State transition result plus side effects to run externally."""

    state: AppState
    effects: tuple[Effect, ...] = ()
