"""Browsing and navigation reducer actions."""

from dataclasses import dataclass
from typing import Literal

from .models import SortField, SplitTerminalFocusTarget


@dataclass(frozen=True)
class OpenNewTab:
    """Create and activate a new browser tab."""


@dataclass(frozen=True)
class ActivateNextTab:
    """Activate the next browser tab."""


@dataclass(frozen=True)
class ActivatePreviousTab:
    """Activate the previous browser tab."""


@dataclass(frozen=True)
class CloseCurrentTab:
    """Close the currently active browser tab."""


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
class MoveCursorByPage:
    """Move cursor by page (page up or page down)."""

    direction: Literal["up", "down"]
    page_size: int
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
    line_number: int | None = None


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
class ToggleHiddenFiles:
    """Toggle hidden file visibility across the shell."""


@dataclass(frozen=True)
class SetSort:
    """Update sort settings."""

    field: SortField
    descending: bool
    directories_first: bool | None = None
