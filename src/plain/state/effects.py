"""Pure effect descriptions emitted by the reducer."""

from dataclasses import dataclass

from plain.models import CreatePathRequest, PasteRequest, RenameRequest, TrashDeleteRequest

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
class LoadRecursiveFilterEffect:
    """Request a recursive filter search outside the reducer."""

    request_id: int
    path: str
    query: str

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


Effect = (
    LoadBrowserSnapshotEffect
    | LoadChildPaneSnapshotEffect
    | LoadRecursiveFilterEffect
    | RunClipboardPasteEffect
    | RunFileMutationEffect
)


@dataclass(frozen=True)
class ReduceResult:
    """State transition result plus side effects to run externally."""

    state: AppState
    effects: tuple[Effect, ...] = ()
