"""Display-only data used by the initial three-pane shell."""

from dataclasses import dataclass
from typing import Literal

EntryKind = Literal["dir", "file"]
NotificationLevel = Literal["info", "warning", "error"]


@dataclass(frozen=True)
class PaneEntry:
    """A single row rendered in one of the directory panes."""

    name: str
    kind: EntryKind
    size_label: str = "-"
    modified_label: str = "-"
    selected: bool = False
    cut: bool = False

    @property
    def kind_label(self) -> str:
        """Return the short label shown in the center table."""

        return "DIR" if self.kind == "dir" else "FILE"

    @property
    def selection_marker(self) -> str:
        """Return the marker shown for selected rows in the center table."""

        return "*" if self.selected else " "


@dataclass(frozen=True)
class StatusBarState:
    """Summary values displayed in the bottom status bar."""

    item_count: int
    selected_count: int
    sort_label: str
    filter_label: str
    message: str | None = None
    message_level: NotificationLevel | None = None


@dataclass(frozen=True)
class HelpBarState:
    """A single-line help summary rendered above the status bar."""

    text: str


@dataclass(frozen=True)
class InputBarState:
    """Single-line prompt and value rendered for rename/create."""

    mode_label: str
    prompt: str
    value: str


@dataclass(frozen=True)
class ConflictDialogState:
    """Display data for the paste conflict dialog."""

    title: str
    message: str
    options: tuple[str, ...]


@dataclass(frozen=True)
class ThreePaneShellData:
    """Complete display state for the shell UI."""

    current_path: str
    parent_entries: tuple[PaneEntry, ...]
    current_entries: tuple[PaneEntry, ...]
    child_entries: tuple[PaneEntry, ...]
    current_cursor_index: int | None
    help: HelpBarState
    input_bar: InputBarState | None
    status: StatusBarState
    conflict_dialog: ConflictDialogState | None = None


def build_dummy_shell_data() -> ThreePaneShellData:
    """Return static data for the initial three-pane shell."""

    current_entries = (
        PaneEntry("docs", "dir", "-", "2026-03-21 09:10"),
        PaneEntry("src", "dir", "-", "2026-03-20 19:42"),
        PaneEntry("tests", "dir", "-", "2026-03-20 19:42"),
        PaneEntry("README.md", "file", "2.1 KB", "2026-03-21 08:55"),
        PaneEntry("pyproject.toml", "file", "712 B", "2026-03-20 18:11"),
    )

    return ThreePaneShellData(
        current_path="/home/tadashi/develop/plain",
        parent_entries=(
            PaneEntry("develop", "dir"),
            PaneEntry("downloads", "dir"),
            PaneEntry("notes.txt", "file"),
        ),
        current_entries=current_entries,
        child_entries=(
            PaneEntry("spec_mvp.md", "file"),
            PaneEntry("notes.md", "file"),
            PaneEntry("wireframes", "dir"),
        ),
        current_cursor_index=0,
        help=HelpBarState("Space select | y copy | x cut | p paste"),
        input_bar=None,
        status=StatusBarState(
            item_count=len(current_entries),
            selected_count=0,
            sort_label="name asc",
            filter_label="none",
            message=None,
            message_level=None,
        ),
    )
