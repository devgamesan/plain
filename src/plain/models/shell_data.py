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
    name_detail: str | None = None
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
class CurrentSummaryState:
    """Summary values displayed near the current directory pane."""

    item_count: int
    selected_count: int
    sort_label: str


@dataclass(frozen=True)
class StatusBarState:
    """Notification content displayed in the bottom status bar."""

    message: str | None = None
    message_level: NotificationLevel | None = None


@dataclass(frozen=True)
class HelpBarState:
    """A single-line help summary rendered above the status bar."""

    text: str


@dataclass(frozen=True)
class InputBarState:
    """Single-line prompt and value rendered for contextual text input."""

    mode_label: str
    prompt: str
    value: str
    hint: str


@dataclass(frozen=True)
class CommandPaletteItemViewState:
    """Single command row rendered in the command palette."""

    label: str
    shortcut: str | None
    enabled: bool
    selected: bool = False


@dataclass(frozen=True)
class CommandPaletteViewState:
    """Display data for the command palette."""

    query: str
    items: tuple[CommandPaletteItemViewState, ...]
    empty_message: str = "No matching commands"


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
    current_summary: CurrentSummaryState
    current_context_input: InputBarState | None
    help: HelpBarState
    command_palette: CommandPaletteViewState | None
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
        current_summary=CurrentSummaryState(
            item_count=len(current_entries),
            selected_count=0,
            sort_label="name asc dirs:on",
        ),
        current_context_input=None,
        help=HelpBarState(
            "Enter open | e edit | / filter | Space select | y copy | x cut | p paste | "
            "s sort | d dirs | F2 rename | : palette"
        ),
        command_palette=None,
        status=StatusBarState(message=None, message_level=None),
    )
