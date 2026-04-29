"""Display-only data used by the initial three-pane shell."""

from dataclasses import dataclass
from typing import Literal

from zivo.models.shell_command import ShellCommandResult

EntryKind = Literal["dir", "file"]
NotificationLevel = Literal["info", "warning", "error"]
PreviewKind = Literal["text", "image"]


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
    executable: bool = False
    symlink: bool = False
    path: str = ""

    @property
    def kind_label(self) -> str:
        """Return the short label shown in the center table."""

        if self.symlink:
            return "LINK"
        return "DIR" if self.kind == "dir" else "FILE"

    @property
    def selection_marker(self) -> str:
        """Return the marker shown for selected rows in the center table."""

        return "*" if self.selected else " "


@dataclass(frozen=True)
class CurrentPaneSizeUpdate:
    """A targeted size-cell update for a single current-pane row."""

    path: str
    size_label: str
    row_index: int = -1


@dataclass(frozen=True)
class CurrentPaneRowUpdate:
    """A targeted full-row update for a single current-pane row."""

    path: str
    entry: PaneEntry
    row_index: int = -1


@dataclass(frozen=True)
class CurrentPaneUpdateHint:
    """Describe how the current pane should be refreshed."""

    mode: Literal["full", "size_delta", "row_delta"]
    revision: int = 0
    size_updates: tuple[CurrentPaneSizeUpdate, ...] = ()
    row_updates: tuple[CurrentPaneRowUpdate, ...] = ()


@dataclass(frozen=True)
class CurrentSummaryState:
    """Summary values displayed near the current directory pane."""

    item_count: int
    selected_count: int
    sort_label: str


@dataclass(frozen=True)
class TransferPaneViewState:
    """Display data for one side of the transfer layout."""

    title: str
    path: str
    entries: tuple[PaneEntry, ...]
    summary: CurrentSummaryState
    cursor_index: int | None
    cursor_visible: bool = True
    active: bool = False


@dataclass(frozen=True)
class ChildPaneViewState:
    """Display data rendered in the right-side child pane."""

    title: str
    entries: tuple[PaneEntry, ...] = ()
    preview_path: str | None = None
    preview_title: str | None = None
    preview_content: str | None = None
    preview_kind: PreviewKind = "text"
    preview_message: str | None = None
    preview_truncated: bool = False
    preview_start_line: int | None = None
    preview_highlight_line: int | None = None
    syntax_theme: str = "monokai"
    permissions_label: str = ""

    @property
    def is_preview(self) -> bool:
        """Return whether the pane should render a text preview."""

        return self.preview_content is not None or self.preview_message is not None


@dataclass(frozen=True)
class StatusBarState:
    """Notification content displayed in the bottom status bar."""

    message: str | None = None
    message_level: NotificationLevel | None = None


@dataclass(frozen=True)
class TabItemState:
    """Single tab item rendered in the tab bar."""

    label: str
    active: bool = False


@dataclass(frozen=True)
class TabBarState:
    """Top-level tab strip rendered above the current path bar."""

    tabs: tuple[TabItemState, ...]


@dataclass(frozen=True)
class HelpBarState:
    """Compact help summary rendered above the status bar."""

    lines: tuple[str, ...]

    @property
    def text(self) -> str:
        """Return the rendered help content."""

        return "\n".join(self.lines)


@dataclass(frozen=True)
class InputBarState:
    """Single-line prompt and value rendered for contextual text input."""

    mode_label: str
    prompt: str
    value: str
    cursor_pos: int
    hint: str


@dataclass(frozen=True)
class CommandPaletteItemViewState:
    """Single command row rendered in the command palette."""

    label: str
    shortcut: str | None
    enabled: bool
    selected: bool = False


@dataclass(frozen=True)
class CommandPaletteInputFieldViewState:
    """Single input row rendered above command palette results."""

    label: str
    value: str
    placeholder: str
    active: bool = False


@dataclass(frozen=True)
class CommandPaletteViewState:
    """Display data for the command palette."""

    title: str
    query: str
    items: tuple[CommandPaletteItemViewState, ...]
    empty_message: str
    input_fields: tuple[CommandPaletteInputFieldViewState, ...] = ()
    has_more_items: bool = False


@dataclass(frozen=True)
class ConflictDialogState:
    """Display data for the paste conflict dialog."""

    title: str
    message: str
    options: tuple[str, ...]


@dataclass(frozen=True)
class AttributeDialogState:
    """Display data for the read-only attribute dialog."""

    title: str
    lines: tuple[str, ...]
    options: tuple[str, ...]


@dataclass(frozen=True)
class ConfigDialogState:
    """Display data for the editable config dialog."""

    title: str
    lines: tuple[str, ...]
    options: tuple[str, ...]


@dataclass(frozen=True)
class ShellCommandDialogState:
    """Display data for the shell command input dialog."""

    title: str
    cwd: str
    prompt: str
    command: str
    options: tuple[str, ...]
    result: ShellCommandResult | None = None


@dataclass(frozen=True)
class InputDialogState:
    """Display data for the rename/create input dialog overlay."""

    title: str
    prompt: str
    value: str
    cursor_pos: int
    hint: str


@dataclass(frozen=True)
class ThreePaneShellData:
    """Complete display state for the shell UI."""

    tab_bar: TabBarState
    current_path: str
    parent_entries: tuple[PaneEntry, ...]
    current_entries: tuple[PaneEntry, ...] | None
    child_pane: ChildPaneViewState
    current_cursor_index: int | None
    current_cursor_visible: bool
    current_pane_update: CurrentPaneUpdateHint
    current_summary: CurrentSummaryState
    current_context_input: InputBarState | None
    help: HelpBarState
    command_palette: CommandPaletteViewState | None
    status: StatusBarState
    conflict_dialog: ConflictDialogState | None = None
    attribute_dialog: AttributeDialogState | None = None
    config_dialog: ConfigDialogState | None = None
    shell_command_dialog: ShellCommandDialogState | None = None
    input_dialog: InputDialogState | None = None
    layout_mode: Literal["browser", "transfer"] = "browser"
    transfer_left: TransferPaneViewState | None = None
    transfer_right: TransferPaneViewState | None = None


def build_dummy_shell_data() -> ThreePaneShellData:
    """Return static data for the initial three-pane shell."""

    current_entries = (
        PaneEntry(
            "docs",
            "dir",
            "-",
            "2026-03-21 09:10",
            path="/home/tadashi/develop/zivo/docs",
        ),
        PaneEntry(
            "src",
            "dir",
            "-",
            "2026-03-20 19:42",
            path="/home/tadashi/develop/zivo/src",
        ),
        PaneEntry(
            "tests",
            "dir",
            "-",
            "2026-03-20 19:42",
            path="/home/tadashi/develop/zivo/tests",
        ),
        PaneEntry(
            "README.md",
            "file",
            "2.1KiB",
            "2026-03-21 08:55",
            path="/home/tadashi/develop/zivo/README.md",
        ),
        PaneEntry(
            "pyproject.toml",
            "file",
            "712 B",
            "2026-03-20 18:11",
            path="/home/tadashi/develop/zivo/pyproject.toml",
        ),
    )

    return ThreePaneShellData(
        tab_bar=TabBarState((TabItemState("zivo", active=True),)),
        current_path="/home/tadashi/develop/zivo",
        parent_entries=(
            PaneEntry("develop", "dir"),
            PaneEntry("downloads", "dir"),
            PaneEntry("notes.txt", "file"),
        ),
        current_entries=current_entries,
        child_pane=ChildPaneViewState(
            title="Child Directory",
            entries=(
                PaneEntry("notes.md", "file"),
                PaneEntry("wireframes", "dir"),
            ),
        ),
        current_cursor_index=0,
        current_cursor_visible=True,
        current_pane_update=CurrentPaneUpdateHint(mode="full"),
        current_summary=CurrentSummaryState(
            item_count=len(current_entries),
            selected_count=0,
            sort_label="name asc dirs:on",
        ),
        current_context_input=None,
        help=HelpBarState(
            (
                "Enter open | e edit | / filter | : palette | ctrl+f find | ctrl+g grep | q quit",
                "Space select | y copy | x cut | v paste | s sort | d dirs | t term",
            )
        ),
        command_palette=None,
        status=StatusBarState(message=None, message_level=None),
        attribute_dialog=None,
        config_dialog=None,
        shell_command_dialog=None,
    )
