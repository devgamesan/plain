"""Input dialog and configuration reducer actions."""

from dataclasses import dataclass

from zivo.models import CreateKind


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
class BeginCreateInput:
    """Enter create input mode for a new file or directory."""

    kind: CreateKind


@dataclass(frozen=True)
class BeginSymlinkInput:
    """Enter symlink input mode for a single source path."""

    source_path: str


@dataclass(frozen=True)
class BeginExtractArchiveInput:
    """Enter extract input mode for a supported archive."""

    source_path: str


@dataclass(frozen=True)
class BeginZipCompressInput:
    """Enter zip-compression input mode for one or more paths."""

    source_paths: tuple[str, ...]


@dataclass(frozen=True)
class BeginShellCommandInput:
    """Open the shell command input dialog."""


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
class ResetHelpBarConfig:
    """Reset help bar configuration to defaults."""


@dataclass(frozen=True)
class SetPendingInputValue:
    """Update the rename/create text input value and cursor position."""

    value: str
    cursor_pos: int


@dataclass(frozen=True)
class MovePendingInputCursor:
    """Move the pending input cursor by a relative delta."""

    delta: int


@dataclass(frozen=True)
class SetPendingInputCursor:
    """Set the pending input cursor to an absolute position."""

    cursor_pos: int


@dataclass(frozen=True)
class DeletePendingInputForward:
    """Delete the character at the cursor position (forward delete)."""


@dataclass(frozen=True)
class SetShellCommandValue:
    """Update the pending shell command input."""

    command: str
    cursor_pos: int = 0


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
class DismissNameConflict:
    """Dismiss the pending rename/create conflict dialog."""


@dataclass(frozen=True)
class DismissAboutDialog:
    """Dismiss the about dialog."""


@dataclass(frozen=True)
class DismissAttributeDialog:
    """Dismiss the pending read-only attribute dialog."""


@dataclass(frozen=True)
class SetFilterQuery:
    """Update the active filter query."""

    query: str
    active: bool | None = None


@dataclass(frozen=True)
class PasteIntoPendingInput:
    """Paste clipboard text into the pending input value."""

    text: str


@dataclass(frozen=True)
class MoveShellCommandCursor:
    """Move the shell command cursor by a relative delta."""

    delta: int


@dataclass(frozen=True)
class SetShellCommandCursor:
    """Set the shell command cursor to an absolute position."""

    cursor_pos: int


@dataclass(frozen=True)
class PasteIntoShellCommand:
    """Paste clipboard text into the shell command input at the cursor position."""

    text: str
