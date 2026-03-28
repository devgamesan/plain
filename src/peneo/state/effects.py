"""Pure effect descriptions emitted by the reducer."""

from dataclasses import dataclass

from peneo.models import (
    AppConfig,
    CreatePathRequest,
    ExternalLaunchRequest,
    PasteRequest,
    RenameRequest,
    TrashDeleteRequest,
)

from .models import AppState


@dataclass(frozen=True)
class LoadBrowserSnapshotEffect:
    """Request a browser snapshot load outside the reducer."""

    request_id: int
    path: str
    cursor_path: str | None = None
    blocking: bool = False


@dataclass(frozen=True)
class LoadChildPaneSnapshotEffect:
    """Request a child-pane load outside the reducer."""

    request_id: int
    current_path: str
    cursor_path: str


@dataclass(frozen=True)
class RunClipboardPasteEffect:
    """Execute a clipboard paste outside the reducer."""

    request_id: int
    request: PasteRequest


@dataclass(frozen=True)
class RunFileMutationEffect:
    """Execute a rename/create mutation outside the reducer."""

    request_id: int
    request: RenameRequest | CreatePathRequest | TrashDeleteRequest


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
class CloseSplitTerminalEffect:
    """Close the active embedded split-terminal session."""

    session_id: int


@dataclass(frozen=True)
class RunConfigSaveEffect:
    """Persist the current config editor draft to disk."""

    request_id: int
    path: str
    config: AppConfig


Effect = (
    LoadBrowserSnapshotEffect
    | LoadChildPaneSnapshotEffect
    | RunClipboardPasteEffect
    | RunFileMutationEffect
    | RunExternalLaunchEffect
    | RunFileSearchEffect
    | StartSplitTerminalEffect
    | WriteSplitTerminalInputEffect
    | CloseSplitTerminalEffect
    | RunConfigSaveEffect
)


@dataclass(frozen=True)
class ReduceResult:
    """State transition result plus side effects to run externally."""

    state: AppState
    effects: tuple[Effect, ...] = ()
