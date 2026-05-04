"""State models for app-level updates and selector inputs."""

from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Literal

from zivo.models import (
    AppConfig,
    ConflictResolution,
    CreateKind,
    CreateSymlinkRequest,
    CreateZipArchiveRequest,
    CustomActionExecutionRequest,
    DeleteMode,
    ExtractArchiveRequest,
    PasteConflict,
    PasteConflictAction,
    PasteRequest,
    ShellCommandResult,
    UndoEntry,
)
from zivo.models.shell_data import EntryKind, NotificationLevel
from zivo.windows_paths import resolve_parent_directory_path as resolve_parent_directory_path_impl

UiMode = Literal[
    "ABOUT",
    "BROWSING",
    "FILTER",
    "RENAME",
    "CREATE",
    "EXTRACT",
    "ZIP",
    "SYMLINK",
    "PALETTE",
    "CONFIRM",
    "CONFIG",
    "SHELL",
    "BUSY",
]
SortField = Literal["name", "modified", "size"]
ClipboardMode = Literal["copy", "cut", "none"]
NameConflictKind = Literal["rename", "create_file", "create_dir"]
CommandPaletteSource = Literal[
    "commands",
    "file_search",
    "grep_search",
    "history",
    "bookmarks",
    "go_to_path",
    "replace_text",
    "replace_in_found_files",
    "replace_in_grep_files",
    "grep_replace_selected",
    "selected_files_grep",
]
GrepSearchFieldId = Literal["keyword", "include", "exclude"]
ReplaceFieldId = Literal["find", "replace"]
FindReplaceFieldId = Literal["filename", "find", "replace"]
GrepReplaceFieldId = Literal["keyword", "replace", "filename", "include", "exclude"]
GrepReplaceSelectedFieldId = Literal["keyword", "replace"]
SelectedFilesGrepFieldId = Literal["keyword"]
FileSearchTarget = Literal["files", "directories", "all"]
FileSearchFieldId = Literal["keyword", "target"]
DirectorySizeStatus = Literal["pending", "ready", "failed"]
CurrentPaneProjectionMode = Literal["full", "viewport"]
LayoutMode = Literal["browser", "transfer"]
TransferPaneId = Literal["left", "right"]
ConfigFieldId = Literal[
    "editor.command",
    "display.show_hidden_files",
    "display.show_directory_sizes",
    "display.enable_text_preview",
    "display.enable_image_preview",
    "display.image_preview_mode",
    "display.enable_pdf_preview",
    "display.enable_office_preview",
    "display.theme",
    "display.preview_syntax_theme",
    "display.preview_max_kib",
    "display.default_sort_field",
    "display.default_sort_descending",
    "display.directories_first",
    "display.grep_preview_context_lines",
    "display.show_help_bar",
    "behavior.confirm_delete",
    "behavior.confirm_exit",
    "behavior.paste_conflict_action",
    "logging.level",
]


@dataclass(frozen=True)
class DirectoryEntryState:
    """Raw directory entry data kept independent from UI formatting."""

    path: str
    name: str
    kind: EntryKind
    size_bytes: int | None = None
    modified_at: datetime | None = None
    hidden: bool = False
    permissions_mode: int | None = None
    owner: str | None = None
    group: str | None = None
    symlink: bool = False


@dataclass(frozen=True)
class PaneState:
    """Entries and cursor/selection state for a single pane."""

    directory_path: str
    entries: tuple[DirectoryEntryState, ...]
    cursor_path: str | None = None
    selected_paths: frozenset[str] = frozenset()
    selection_anchor_path: str | None = None
    mode: Literal["entries", "preview"] = "entries"
    preview_path: str | None = None
    preview_title: str | None = None
    preview_content: str | None = None
    preview_kind: Literal["text", "image", "kitty"] = "text"
    preview_message: str | None = None
    preview_truncated: bool = False
    preview_start_line: int | None = None
    preview_highlight_line: int | None = None


@dataclass(frozen=True)
class SortState:
    """Sort configuration used by selectors."""

    field: SortField = "name"
    descending: bool = False
    directories_first: bool = True


@dataclass(frozen=True)
class FilterState:
    """Name-based filter configuration."""

    query: str = ""
    active: bool = False


@dataclass(frozen=True)
class ClipboardState:
    """Clipboard metadata for future file operations."""

    mode: ClipboardMode = "none"
    paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class PasteConflictState:
    """Pending conflict dialog state for a clipboard paste."""

    request: PasteRequest
    conflicts: tuple[PasteConflict, ...]
    first_conflict: PasteConflict
    available_resolutions: tuple[ConflictResolution, ...] = ("overwrite", "skip", "rename")


@dataclass(frozen=True)
class DeleteConfirmationState:
    """Pending confirmation dialog state for trash or permanent deletion."""

    paths: tuple[str, ...]
    mode: DeleteMode = "trash"


@dataclass(frozen=True)
class EmptyTrashConfirmationState:
    """Pending confirmation dialog state for empty trash operation."""

    platform: Literal["linux", "darwin"]


@dataclass(frozen=True)
class ExitConfirmationState:
    """Pending confirmation dialog state for application exit."""


@dataclass(frozen=True)
class NameConflictState:
    """Pending dialog state for rename/create name collisions."""

    kind: NameConflictKind
    name: str


@dataclass(frozen=True)
class ArchiveExtractConfirmationState:
    """Pending confirmation dialog state for archive extraction conflicts."""

    request: ExtractArchiveRequest
    conflict_count: int
    first_conflict_path: str
    total_entries: int


@dataclass(frozen=True)
class ArchiveExtractProgressState:
    """Transient progress state for an archive extraction."""

    completed_entries: int
    total_entries: int
    current_path: str | None = None


@dataclass(frozen=True)
class ZipCompressConfirmationState:
    """Pending confirmation dialog state for zip compression conflicts."""

    request: CreateZipArchiveRequest
    total_entries: int


@dataclass(frozen=True)
class SymlinkOverwriteConfirmationState:
    """Pending confirmation dialog state for symlink destination overwrite."""

    request: CreateSymlinkRequest


@dataclass(frozen=True)
class ZipCompressProgressState:
    """Transient progress state for zip compression."""

    completed_entries: int
    total_entries: int
    current_path: str | None = None


@dataclass(frozen=True)
class AttributeInspectionState:
    """Pending read-only attribute dialog state."""

    name: str
    kind: EntryKind
    path: str
    symlink: bool = False
    size_bytes: int | None = None
    modified_at: datetime | None = None
    hidden: bool = False
    permissions_mode: int | None = None
    owner: str | None = None
    group: str | None = None


@dataclass(frozen=True)
class ReplaceConfirmationState:
    """Pending confirmation dialog state for text replacement operations."""

    mode: Literal[
        "replace_text",
        "replace_in_found_files",
        "replace_in_grep_files",
        "grep_replace_selected",
    ]
    find_text: str
    replacement_text: str
    target_paths: tuple[str, ...]
    total_match_count: int


@dataclass(frozen=True)
class CustomActionConfirmationState:
    """Pending confirmation for a resolved custom action command."""

    request: CustomActionExecutionRequest


@dataclass(frozen=True)
class ConfigEditorState:
    """Transient config editor state used by the config dialog."""

    path: str
    draft: AppConfig
    cursor_index: int = 0
    dirty: bool = False


@dataclass(frozen=True)
class ShellCommandState:
    """Transient shell command dialog state."""

    cwd: str
    command: str = ""
    cursor_pos: int = 0
    result: ShellCommandResult | None = None


@dataclass(frozen=True)
class HistoryState:
    """Back/forward navigation history."""

    back: tuple[str, ...] = ()
    forward: tuple[str, ...] = ()
    visited_all: tuple[str, ...] = ()


@dataclass(frozen=True)
class NotificationState:
    """Transient notification rendered by the UI shell."""

    level: NotificationLevel
    message: str


@dataclass(frozen=True)
class PendingInputState:
    """Transient text input state used by rename/create/archive flows."""

    prompt: str
    value: str = ""
    cursor_pos: int = 0
    target_path: str | None = None
    create_kind: CreateKind | None = None
    extract_source_path: str | None = None
    zip_source_paths: tuple[str, ...] | None = None
    symlink_source_path: str | None = None
    symlink_overwrite: bool = False


@dataclass(frozen=True)
class PendingKeySequenceState:
    """Transient multi-key prefix state used while browsing."""

    keys: tuple[str, ...]
    possible_next_keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class DirectorySizeCacheEntry:
    """Cached recursive directory size for a visible path."""

    path: str
    status: DirectorySizeStatus
    size_bytes: int | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class DirectorySizeDeltaState:
    """Transient changed-path metadata for the latest directory-size update."""

    changed_paths: tuple[str, ...] = ()
    revision: int = 0


@dataclass(frozen=True)
class CurrentPaneDeltaState:
    """Transient changed-path metadata for the latest current-pane row update."""

    changed_paths: tuple[str, ...] = ()
    revision: int = 0


@dataclass(frozen=True)
class FileSearchResultState:
    """A single file-search result shown in the command palette."""

    path: str
    display_path: str
    entry_type: Literal["file", "directory"] = "file"


@dataclass(frozen=True)
class GrepSearchResultState:
    """A single grep result shown in the command palette."""

    path: str
    display_path: str
    line_number: int
    line_text: str
    column_number: int = 1

    @property
    def display_label(self) -> str:
        """Return the single-line palette label for the grep match."""

        return f"{self.display_path}:{self.line_number}: {self.line_text}"


@dataclass(frozen=True)
class ReplacePreviewResultState:
    """A single text-replace preview result shown in the command palette."""

    path: str
    display_path: str
    diff_text: str
    match_count: int
    first_match_line_number: int
    first_match_before: str
    first_match_after: str

    @property
    def display_label(self) -> str:
        """Return the single-line palette label for the replacement preview."""

        return (
            f"{self.display_path} ({self.match_count}): "
            f"{self.first_match_line_number}: "
            f"{self.first_match_before}"
        )


@dataclass(frozen=True)
class HistoryAndNavigationPaletteState:
    history_results: tuple[str, ...] = ()
    go_to_path_candidates: tuple[str, ...] = ()
    go_to_path_selection_active: bool = True


@dataclass(frozen=True)
class SfgPaletteState:
    target_paths: tuple[str, ...] = ()
    keyword: str = ""
    active_field: SelectedFilesGrepFieldId = "keyword"
    results: tuple[GrepSearchResultState, ...] = ()
    error_message: str | None = None


@dataclass(frozen=True)
class FileSearchPaletteState:
    results: tuple[FileSearchResultState, ...] = ()
    error_message: str | None = None
    cache_query: str = ""
    cache_results: tuple[FileSearchResultState, ...] = ()
    cache_root_path: str | None = None
    cache_show_hidden: bool = False
    cache_target: FileSearchTarget | None = None
    target: FileSearchTarget = "all"
    active_field: FileSearchFieldId = "keyword"


@dataclass(frozen=True)
class GrepSearchPaletteState:
    keyword: str = ""
    filename_filter: str = ""
    include_extensions: str = ""
    exclude_extensions: str = ""
    active_field: GrepSearchFieldId = "keyword"
    results: tuple[GrepSearchResultState, ...] = ()
    error_message: str | None = None


@dataclass(frozen=True)
class ReplacePreviewPaletteState:
    find_text: str = ""
    replacement_text: str = ""
    active_field: ReplaceFieldId = "find"
    preview_results: tuple[ReplacePreviewResultState, ...] = ()
    error_message: str | None = None
    status_message: str | None = None
    target_paths: tuple[str, ...] = ()
    total_match_count: int = 0


@dataclass(frozen=True)
class RffPaletteState:
    filename_query: str = ""
    active_field: FindReplaceFieldId = "filename"
    find_text: str = ""
    replacement_text: str = ""
    file_results: tuple[FileSearchResultState, ...] = ()
    file_error_message: str | None = None
    preview_results: tuple[ReplacePreviewResultState, ...] = ()
    error_message: str | None = None
    status_message: str | None = None
    total_match_count: int = 0


@dataclass(frozen=True)
class GrsPaletteState:
    keyword: str = ""
    active_field: GrepReplaceSelectedFieldId = "keyword"
    grep_results: tuple[GrepSearchResultState, ...] = ()
    grep_error_message: str | None = None
    replacement_text: str = ""
    preview_results: tuple[ReplacePreviewResultState, ...] = ()
    error_message: str | None = None
    status_message: str | None = None
    total_match_count: int = 0
    target_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class GrfPaletteState:
    keyword: str = ""
    include_extensions: str = ""
    exclude_extensions: str = ""
    active_field: GrepReplaceFieldId = "keyword"
    grep_results: tuple[GrepSearchResultState, ...] = ()
    grep_error_message: str | None = None
    filename_filter: str = ""
    replacement_text: str = ""
    preview_results: tuple[ReplacePreviewResultState, ...] = ()
    error_message: str | None = None
    status_message: str | None = None
    total_match_count: int = 0


@dataclass(frozen=True)
class CommandPaletteState:
    """Transient palette search and cursor state."""

    source: CommandPaletteSource = "commands"
    query: str = ""
    cursor_index: int = 0
    file_search: FileSearchPaletteState = field(default_factory=FileSearchPaletteState)
    grep_search: GrepSearchPaletteState = field(default_factory=GrepSearchPaletteState)
    replace_preview: ReplacePreviewPaletteState = field(
        default_factory=ReplacePreviewPaletteState,
    )
    history_and_navigation: HistoryAndNavigationPaletteState = field(
        default_factory=HistoryAndNavigationPaletteState
    )
    rff: RffPaletteState = field(default_factory=RffPaletteState)
    grs: GrsPaletteState = field(default_factory=GrsPaletteState)
    grf: GrfPaletteState = field(default_factory=GrfPaletteState)
    sfg: SfgPaletteState = field(default_factory=SfgPaletteState)


@dataclass(frozen=True)
class BrowserSnapshot:
    """Pane snapshot payload returned from async loaders."""

    current_path: str
    parent_pane: PaneState
    current_pane: PaneState
    child_pane: PaneState


@dataclass(frozen=True)
class TransferPaneState:
    """Directory pane state used by the two-pane transfer layout."""

    pane: PaneState
    current_path: str
    history: HistoryState = HistoryState()
    current_pane_window_start: int = 0
    current_pane_delta: CurrentPaneDeltaState = CurrentPaneDeltaState()
    pending_snapshot_request_id: int | None = None


@dataclass(frozen=True)
class BrowserTabState:
    """Per-tab browser state that can be swapped into the active app view."""

    current_path: str
    parent_pane: PaneState
    current_pane: PaneState
    child_pane: PaneState
    history: HistoryState = HistoryState()
    filter: FilterState = FilterState()
    current_pane_window_start: int = 0
    current_pane_delta: CurrentPaneDeltaState = CurrentPaneDeltaState()
    pending_browser_snapshot_request_id: int | None = None
    pending_child_pane_request_id: int | None = None
    layout_mode: LayoutMode = "browser"
    active_transfer_pane: TransferPaneId = "left"
    transfer_left: TransferPaneState | None = None
    transfer_right: TransferPaneState | None = None
    parent_pane_loading: bool = False  # Track parent pane loading in progressive mode
    child_pane_loading: bool = False  # Track child pane loading in progressive mode


@dataclass(frozen=True)
class AppState:
    """Single source of truth for reducer-managed application state."""

    current_path: str
    parent_pane: PaneState
    current_pane: PaneState
    child_pane: PaneState
    browser_tabs: tuple[BrowserTabState, ...] = ()
    active_tab_index: int = 0
    config: AppConfig = field(default_factory=AppConfig)
    config_path: str = ""
    show_hidden: bool = False
    show_help_bar: bool = True
    sort: SortState = SortState()
    confirm_delete: bool = True
    confirm_exit: bool = True
    paste_conflict_action: PasteConflictAction = "prompt"
    filter: FilterState = FilterState()
    clipboard: ClipboardState = ClipboardState()
    history: HistoryState = HistoryState()
    ui_mode: UiMode = "BROWSING"
    layout_mode: LayoutMode = "browser"
    active_transfer_pane: TransferPaneId = "left"
    transfer_left: TransferPaneState | None = None
    transfer_right: TransferPaneState | None = None
    notification: NotificationState | None = None
    pending_input: PendingInputState | None = None
    pending_key_sequence: PendingKeySequenceState | None = None
    command_palette: CommandPaletteState | None = None
    paste_conflict: PasteConflictState | None = None
    delete_confirmation: DeleteConfirmationState | None = None
    empty_trash_confirmation: EmptyTrashConfirmationState | None = None
    exit_confirmation: ExitConfirmationState | None = None
    name_conflict: NameConflictState | None = None
    archive_extract_confirmation: ArchiveExtractConfirmationState | None = None
    archive_extract_progress: ArchiveExtractProgressState | None = None
    zip_compress_confirmation: ZipCompressConfirmationState | None = None
    zip_compress_progress: ZipCompressProgressState | None = None
    symlink_overwrite_confirmation: SymlinkOverwriteConfirmationState | None = None
    replace_confirmation: ReplaceConfirmationState | None = None
    custom_action_confirmation: CustomActionConfirmationState | None = None
    attribute_inspection: AttributeInspectionState | None = None
    config_editor: ConfigEditorState | None = None
    shell_command: ShellCommandState | None = None
    post_reload_notification: NotificationState | None = None
    directory_size_cache: tuple[DirectorySizeCacheEntry, ...] = ()
    directory_size_delta: DirectorySizeDeltaState = DirectorySizeDeltaState()
    current_pane_delta: CurrentPaneDeltaState = CurrentPaneDeltaState()
    pending_browser_snapshot_request_id: int | None = None
    pending_child_pane_request_id: int | None = None
    pending_paste_request_id: int | None = None
    pending_file_mutation_request_id: int | None = None
    pending_archive_prepare_request_id: int | None = None
    pending_archive_extract_request_id: int | None = None
    pending_zip_compress_prepare_request_id: int | None = None
    pending_zip_compress_request_id: int | None = None
    pending_file_search_request_id: int | None = None
    pending_grep_search_request_id: int | None = None
    pending_replace_preview_request_id: int | None = None
    pending_replace_apply_request_id: int | None = None
    pending_directory_size_request_id: int | None = None
    pending_attribute_inspection_request_id: int | None = None
    pending_config_save_request_id: int | None = None
    pending_shell_command_request_id: int | None = None
    pending_custom_action_request_id: int | None = None
    undo_stack: tuple[UndoEntry, ...] = ()
    pending_undo_entry: UndoEntry | None = None
    pending_undo_request_id: int | None = None
    terminal_height: int = 24
    current_pane_projection_mode: CurrentPaneProjectionMode = "full"
    current_pane_window_start: int = 0
    next_request_id: int = 1


def browser_tab_from_app_state(state: AppState) -> BrowserTabState:
    """Capture the active browser-facing state as a tab payload."""

    return BrowserTabState(
        current_path=state.current_path,
        parent_pane=state.parent_pane,
        current_pane=state.current_pane,
        child_pane=state.child_pane,
        history=state.history,
        filter=state.filter,
        current_pane_window_start=state.current_pane_window_start,
        current_pane_delta=state.current_pane_delta,
        pending_browser_snapshot_request_id=state.pending_browser_snapshot_request_id,
        pending_child_pane_request_id=state.pending_child_pane_request_id,
        layout_mode=state.layout_mode,
        active_transfer_pane=state.active_transfer_pane,
        transfer_left=state.transfer_left,
        transfer_right=state.transfer_right,
    )


def select_browser_tabs(state: AppState) -> tuple[BrowserTabState, ...]:
    """Return browser tabs with the active tab overlaid from top-level state."""

    if not state.browser_tabs:
        return (browser_tab_from_app_state(state),)

    tabs = list(state.browser_tabs)
    active_index = max(0, min(state.active_tab_index, len(tabs) - 1))
    tabs[active_index] = browser_tab_from_app_state(state)
    return tuple(tabs)


def sync_active_browser_tab(state: AppState) -> AppState:
    """Persist the active top-level browser state into the tab list."""

    tabs = select_browser_tabs(state)
    active_tab_index = max(0, min(state.active_tab_index, len(tabs) - 1))
    if tabs == state.browser_tabs and active_tab_index == state.active_tab_index:
        return state
    return replace(
        state,
        browser_tabs=tabs,
        active_tab_index=active_tab_index,
    )


def load_browser_tab(state: AppState, index: int) -> AppState:
    """Load the requested tab into the active top-level browser fields."""

    tabs = select_browser_tabs(state)
    clamped_index = max(0, min(index, len(tabs) - 1))
    tab = tabs[clamped_index]
    return replace(
        state,
        browser_tabs=tabs,
        active_tab_index=clamped_index,
        current_path=tab.current_path,
        parent_pane=tab.parent_pane,
        current_pane=tab.current_pane,
        child_pane=tab.child_pane,
        history=tab.history,
        filter=tab.filter,
        current_pane_window_start=tab.current_pane_window_start,
        current_pane_delta=tab.current_pane_delta,
        pending_browser_snapshot_request_id=tab.pending_browser_snapshot_request_id,
        pending_child_pane_request_id=tab.pending_child_pane_request_id,
        layout_mode=tab.layout_mode,
        active_transfer_pane=tab.active_transfer_pane,
        transfer_left=tab.transfer_left,
        transfer_right=tab.transfer_right,
    )


def resolve_parent_directory_path(path: str) -> tuple[str, str | None]:
    """Return the resolved path and its distinct parent, if one exists."""

    return resolve_parent_directory_path_impl(path)


def build_initial_app_state(
    *,
    config: AppConfig | None = None,
    config_path: str = "/home/tadashi/.config/zivo/config.toml",
    show_hidden: bool = False,
    show_help_bar: bool = True,
    sort: SortState | None = None,
    confirm_delete: bool = True,
    confirm_exit: bool = True,
    paste_conflict_action: PasteConflictAction = "prompt",
    post_reload_notification: NotificationState | None = None,
    current_pane_projection_mode: CurrentPaneProjectionMode = "full",
) -> AppState:
    """Return a deterministic initial state used by selector and reducer tests."""

    current_path = "/home/tadashi/develop/zivo"
    docs_path = f"{current_path}/docs"

    parent_entries = (
        DirectoryEntryState("/home/tadashi/develop", "develop", "dir"),
        DirectoryEntryState("/home/tadashi/downloads", "downloads", "dir"),
        DirectoryEntryState("/home/tadashi/notes.txt", "notes.txt", "file"),
    )
    current_entries = (
        DirectoryEntryState(
            f"{current_path}/docs",
            "docs",
            "dir",
            modified_at=datetime(2026, 3, 21, 9, 10),
        ),
        DirectoryEntryState(
            f"{current_path}/src",
            "src",
            "dir",
            modified_at=datetime(2026, 3, 20, 19, 42),
        ),
        DirectoryEntryState(
            f"{current_path}/tests",
            "tests",
            "dir",
            modified_at=datetime(2026, 3, 20, 19, 42),
        ),
        DirectoryEntryState(
            f"{current_path}/README.md",
            "README.md",
            "file",
            size_bytes=2_150,
            modified_at=datetime(2026, 3, 21, 8, 55),
        ),
        DirectoryEntryState(
            f"{current_path}/pyproject.toml",
            "pyproject.toml",
            "file",
            size_bytes=712,
            modified_at=datetime(2026, 3, 20, 18, 11),
        ),
    )
    child_entries = (
        DirectoryEntryState(f"{docs_path}/notes.md", "notes.md", "file"),
        DirectoryEntryState(f"{docs_path}/wireframes", "wireframes", "dir"),
    )

    state = AppState(
        current_path=current_path,
        config=config or AppConfig(),
        config_path=config_path,
        parent_pane=PaneState(directory_path="/home/tadashi", entries=parent_entries),
        current_pane=PaneState(
            directory_path=current_path,
            entries=current_entries,
            cursor_path=f"{current_path}/docs",
        ),
        child_pane=PaneState(directory_path=docs_path, entries=child_entries),
        show_hidden=show_hidden,
        show_help_bar=show_help_bar,
        sort=sort or SortState(field="name", descending=False, directories_first=True),
        confirm_delete=confirm_delete,
        confirm_exit=confirm_exit,
        paste_conflict_action=paste_conflict_action,
        filter=FilterState(query="", active=False),
        post_reload_notification=post_reload_notification,
        current_pane_projection_mode=current_pane_projection_mode,
    )
    return sync_active_browser_tab(state)


def build_placeholder_app_state(
    current_path: str,
    *,
    config: AppConfig | None = None,
    config_path: str = "",
    show_hidden: bool = False,
    show_help_bar: bool = True,
    sort: SortState | None = None,
    confirm_delete: bool = True,
    confirm_exit: bool = True,
    paste_conflict_action: PasteConflictAction = "prompt",
    post_reload_notification: NotificationState | None = None,
    current_pane_projection_mode: CurrentPaneProjectionMode = "viewport",
) -> AppState:
    """Return an empty browser state used before the first snapshot loads."""

    if current_path == "/":
        resolved_path = str(Path(current_path).expanduser().resolve())
        parent_path = resolved_path if Path(resolved_path).parent == Path(resolved_path) else str(
            Path(resolved_path).parent
        )
    else:
        resolved_path, parent_path = resolve_parent_directory_path(current_path)
    state = AppState(
        current_path=resolved_path,
        config=config or AppConfig(),
        config_path=config_path,
        parent_pane=PaneState(directory_path=parent_path or resolved_path, entries=()),
        current_pane=PaneState(directory_path=resolved_path, entries=()),
        child_pane=PaneState(directory_path=resolved_path, entries=()),
        show_hidden=show_hidden,
        show_help_bar=show_help_bar,
        sort=sort or SortState(),
        confirm_delete=confirm_delete,
        confirm_exit=confirm_exit,
        paste_conflict_action=paste_conflict_action,
        post_reload_notification=post_reload_notification,
        current_pane_projection_mode=current_pane_projection_mode,
    )
    return sync_active_browser_tab(state)
