"""Selection and file-mutation reducer actions."""

from dataclasses import dataclass

from zivo.models import ConflictResolution, CustomActionExecutionRequest, DeleteMode


@dataclass(frozen=True)
class BeginDeleteTargets:
    """Begin deleting the supplied target paths."""

    paths: tuple[str, ...]
    mode: DeleteMode = "trash"


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
class UndoLastOperation:
    """Undo the most recent reversible file operation."""


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
class BeginEmptyTrash:
    """Begin the empty trash operation with confirmation."""


@dataclass(frozen=True)
class ConfirmEmptyTrash:
    """Confirm the empty trash request."""


@dataclass(frozen=True)
class CancelEmptyTrashConfirmation:
    """Dismiss the pending empty trash confirmation dialog."""


@dataclass(frozen=True)
class BeginExitCurrentPath:
    """Begin the exit confirmation flow."""


@dataclass(frozen=True)
class ConfirmExitCurrentPath:
    """Confirm the application exit."""


@dataclass(frozen=True)
class CancelExitConfirmation:
    """Cancel the exit confirmation."""


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
class ConfirmSymlinkOverwrite:
    """Confirm overwriting the pending symlink destination."""


@dataclass(frozen=True)
class CancelSymlinkOverwriteConfirmation:
    """Return from symlink overwrite confirmation to input editing."""


@dataclass(frozen=True)
class ConfirmReplaceTargets:
    """Confirmed - proceed with the replace operation."""


@dataclass(frozen=True)
class CancelReplaceConfirmation:
    """Cancelled - abort the replace operation."""


@dataclass(frozen=True)
class BeginCustomActionConfirmation:
    """Show the resolved custom action before running it."""

    request: CustomActionExecutionRequest


@dataclass(frozen=True)
class ConfirmCustomAction:
    """Run the pending custom action."""


@dataclass(frozen=True)
class CancelCustomActionConfirmation:
    """Cancel the pending custom action."""
