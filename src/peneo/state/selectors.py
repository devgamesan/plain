"""Selectors that convert AppState into display models."""

from dataclasses import dataclass, replace
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from stat import S_IMODE, filemode

from peneo.archive_utils import is_supported_archive_path
from peneo.models import (
    AttributeDialogState,
    CommandPaletteItemViewState,
    CommandPaletteViewState,
    ConfigDialogState,
    ConflictDialogState,
    CurrentPaneRowUpdate,
    CurrentPaneSizeUpdate,
    CurrentPaneUpdateHint,
    CurrentSummaryState,
    HelpBarState,
    InputBarState,
    PaneEntry,
    ShellCommandDialogState,
    SplitTerminalViewState,
    StatusBarState,
    ThreePaneShellData,
)

from .command_palette import (
    CommandPaletteItem,
    get_command_palette_items,
    normalize_command_palette_cursor,
)
from .models import (
    AppState,
    DirectoryEntryState,
    DirectorySizeCacheEntry,
    FileSearchResultState,
    GrepSearchResultState,
    SortState,
)

SIDE_PANE_SORT = SortState(field="name", descending=False, directories_first=True)
COMMAND_PALETTE_VISIBLE_WINDOW = 8
MIN_SEARCH_VISIBLE_WINDOW = 3
_SEARCH_OVERHEAD_ROWS = 5
MIN_CURRENT_PANE_VISIBLE_WINDOW = 5
_CURRENT_PANE_OVERHEAD_ROWS = 8


def _has_execute_permission(entry: DirectoryEntryState) -> bool:
    """エントリが実行権限を持っているか判定."""
    if entry.permissions_mode is None:
        return False
    return bool(entry.permissions_mode & 0o111)


@dataclass(frozen=True)
class _CurrentPaneProjection:
    visible_entries: tuple[DirectoryEntryState, ...]
    projected_entries: tuple[DirectoryEntryState, ...]
    cursor_index: int | None
    cursor_entry: DirectoryEntryState | None
    summary: CurrentSummaryState


def select_shell_data(state: AppState) -> ThreePaneShellData:
    """Build the display shell data consumed by the UI layer."""

    current_pane = _select_current_pane_projection(state)
    display_directory_sizes = (
        state.config.display.show_directory_sizes or state.sort.field == "size"
    )
    current_pane_update = _select_current_pane_update_hint(
        current_pane.projected_entries,
        state.directory_size_cache,
        display_directory_sizes,
        state.sort,
        state.current_pane.selected_paths,
        _select_cut_paths(state),
        state.current_pane_delta.changed_paths,
        state.current_pane_delta.revision,
        state.directory_size_delta.changed_paths,
        state.directory_size_delta.revision,
    )
    return ThreePaneShellData(
        current_path=state.current_path,
        parent_entries=select_parent_entries(state),
        current_entries=(
            _select_current_pane_entries(
                current_pane.projected_entries,
                state.directory_size_cache,
                display_directory_sizes,
                state.current_pane.selected_paths,
                _select_cut_paths(state),
            )
            if current_pane_update.mode == "full"
            else None
        ),
        child_entries=_select_child_entries_for_cursor(state, current_pane.cursor_entry),
        current_cursor_index=current_pane.cursor_index,
        current_cursor_visible=state.ui_mode != "FILTER",
        current_pane_update=current_pane_update,
        current_summary=current_pane.summary,
        current_context_input=select_input_bar_state(state),
        split_terminal=select_split_terminal_state(state),
        help=select_help_bar_state(state),
        command_palette=select_command_palette_state(state),
        status=select_status_bar_state(state),
        conflict_dialog=select_conflict_dialog_state(state),
        attribute_dialog=select_attribute_dialog_state(state),
        config_dialog=select_config_dialog_state(state),
        shell_command_dialog=select_shell_command_dialog_state(state),
    )


def select_parent_entries(state: AppState) -> tuple[PaneEntry, ...]:
    """Return display entries for the parent pane."""

    visible_entries = _select_side_pane_entry_states(state.parent_pane.entries, state.show_hidden)
    return _select_side_pane_entries(
        visible_entries,
        state.directory_size_cache,
        display_directory_sizes=False,
        selected_path=state.parent_pane.cursor_path,
        cut_paths=_select_visible_cut_paths(visible_entries, _select_cut_paths(state)),
    )


def select_current_entries(state: AppState) -> tuple[PaneEntry, ...]:
    """Return display entries for the current pane after filter/sort."""

    return _select_current_pane_entries(
        select_visible_current_entry_states(state),
        state.directory_size_cache,
        state.config.display.show_directory_sizes or state.sort.field == "size",
        state.current_pane.selected_paths,
        _select_cut_paths(state),
    )


def select_child_entries(state: AppState) -> tuple[PaneEntry, ...]:
    """Return display entries for the child pane when the cursor is on a directory."""

    cursor_entry = _get_current_cursor_entry(state)
    return _select_child_entries_for_cursor(state, cursor_entry)


def _select_child_entries_for_cursor(
    state: AppState,
    cursor_entry: DirectoryEntryState | None,
) -> tuple[PaneEntry, ...]:
    if cursor_entry is None:
        return ()
    # Check if it's a directory or an archive file
    is_archive = cursor_entry.kind == "file" and is_supported_archive_path(cursor_entry.path)
    if cursor_entry.kind != "dir" and not is_archive:
        return ()
    if (
        cursor_entry.path != state.child_pane.directory_path
        and state.pending_child_pane_request_id is None
    ):
        return ()
    visible_entries = _select_side_pane_entry_states(state.child_pane.entries, state.show_hidden)
    return _select_side_pane_entries(
        visible_entries,
        state.directory_size_cache,
        display_directory_sizes=False,
        selected_path=None,
        cut_paths=_select_visible_cut_paths(visible_entries, _select_cut_paths(state)),
    )


def select_current_summary_state(state: AppState) -> CurrentSummaryState:
    """Return the summary model shown near the current pane."""

    return _select_current_pane_projection(state).summary


def select_status_bar_state(state: AppState) -> StatusBarState:
    """Return a status bar model derived from app state."""

    if state.notification is None and state.split_terminal.visible:
        return StatusBarState(
            message="Split terminal active",
            message_level="info",
        )
    return StatusBarState(
        message=state.notification.message if state.notification else None,
        message_level=state.notification.level if state.notification else None,
    )


def select_help_bar_state(state: AppState) -> HelpBarState:
    """Return the help content for the active mode."""

    if state.split_terminal.visible:
        if state.config.help_bar.split_terminal:
            return HelpBarState(state.config.help_bar.split_terminal)
        return HelpBarState(("type in terminal | esc close | ctrl+v paste",))
    if state.ui_mode == "CONFIRM":
        if state.delete_confirmation is not None:
            if (
                state.delete_confirmation.mode == "trash"
                and state.config.help_bar.confirm_delete
            ):
                return HelpBarState(state.config.help_bar.confirm_delete)
            if state.delete_confirmation.mode == "permanent":
                return HelpBarState(("enter confirm permanent delete | esc cancel",))
            return HelpBarState(("enter confirm delete | esc cancel",))
        if state.archive_extract_confirmation is not None:
            return HelpBarState(("enter continue extraction | esc return to input",))
        if state.zip_compress_confirmation is not None:
            return HelpBarState(("enter overwrite zip | esc return to input",))
        if state.name_conflict is not None:
            return HelpBarState(("enter return to input | esc return to input",))
        return HelpBarState(("resolve conflict in dialog",))
    if state.ui_mode == "DETAIL":
        if state.config.help_bar.detail:
            return HelpBarState(state.config.help_bar.detail)
        return HelpBarState(("enter close | esc close",))
    if state.ui_mode == "CONFIG":
        if state.config.help_bar.config:
            return HelpBarState(state.config.help_bar.config)
        return HelpBarState(
            (
                "up/down choose | left/right/enter change | s save | e edit file | r reset help",
                "esc close",
            )
        )
    if state.ui_mode == "SHELL":
        if state.config.help_bar.shell:
            return HelpBarState(state.config.help_bar.shell)
        return HelpBarState(("type command | enter run | esc cancel",))
    if state.ui_mode == "FILTER":
        if state.config.help_bar.filter:
            return HelpBarState(state.config.help_bar.filter)
        return HelpBarState(("type filter | enter/down apply | esc clear",))
    if state.ui_mode == "RENAME":
        if state.config.help_bar.rename:
            return HelpBarState(state.config.help_bar.rename)
        return HelpBarState(("type name | enter apply | esc cancel",))
    if state.ui_mode == "CREATE":
        if state.config.help_bar.create:
            return HelpBarState(state.config.help_bar.create)
        return HelpBarState(("type name | enter apply | esc cancel",))
    if state.ui_mode == "EXTRACT":
        if state.config.help_bar.extract:
            return HelpBarState(state.config.help_bar.extract)
        return HelpBarState(("type destination path | enter extract | esc cancel",))
    if state.ui_mode == "ZIP":
        if state.config.help_bar.zip:
            return HelpBarState(state.config.help_bar.zip)
        return HelpBarState(("type zip path | enter compress | esc cancel",))
    if state.ui_mode == "PALETTE":
        if state.command_palette is not None and state.command_palette.source == "file_search":
            if state.config.help_bar.palette_file_search:
                return HelpBarState(state.config.help_bar.palette_file_search)
            return HelpBarState(
                ("type filename | ↑↓ select | enter jump | Ctrl+E edit | esc cancel",)
            )
        if state.command_palette is not None and state.command_palette.source == "grep_search":
            if state.config.help_bar.palette_grep_search:
                return HelpBarState(state.config.help_bar.palette_grep_search)
            return HelpBarState(
                (
                    "type text / re:pattern | ↑↓ select | "
                    "enter jump | Ctrl+E edit | esc cancel",
                )
            )
        if state.command_palette is not None and state.command_palette.source == "history":
            if state.config.help_bar.palette_history:
                return HelpBarState(state.config.help_bar.palette_history)
            return HelpBarState(("type path | enter jump | esc cancel",))
        if state.command_palette is not None and state.command_palette.source == "bookmarks":
            if state.config.help_bar.palette_bookmarks:
                return HelpBarState(state.config.help_bar.palette_bookmarks)
            return HelpBarState(("type path | enter jump | esc cancel",))
        if state.command_palette is not None and state.command_palette.source == "go_to_path":
            if state.config.help_bar.palette_go_to_path:
                return HelpBarState(state.config.help_bar.palette_go_to_path)
            return HelpBarState(
                ("type path | ↑↓ select | tab complete | enter jump | esc cancel",)
            )
        if state.config.help_bar.palette:
            return HelpBarState(state.config.help_bar.palette)
        return HelpBarState(("type command | ↑↓ select | enter run | esc cancel",))
    if state.ui_mode == "BUSY":
        if state.config.help_bar.busy:
            return HelpBarState(state.config.help_bar.busy)
        return HelpBarState(("processing...",))
    if state.config.help_bar.browsing:
        return HelpBarState(state.config.help_bar.browsing)
    return HelpBarState(
        (
            "enter open | e edit | i info | space select | c copy | x cut | p paste | C path",
            "/ filter | s sort | d dir-first | . hidden | a select-all | ~ home",
            "f find | g grep | G go-to | H history | b bookmarks | B toggle-bookmark",
            "n new-file | N new-dir | r rename | R reload | t term | : palette | q quit",
        )
    )


def select_input_bar_state(state: AppState) -> InputBarState | None:
    """Return contextual input state for the active mode."""

    if state.ui_mode == "FILTER" or (state.filter.active and state.filter.query):
        hint = "esc clear"
        if state.ui_mode == "FILTER":
            hint = "enter/down apply | esc clear"
        return InputBarState(
            mode_label="FILTER",
            prompt="Filter: ",
            value=state.filter.query,
            hint=hint,
        )

    if state.ui_mode not in {"RENAME", "CREATE", "EXTRACT", "ZIP"}:
        return None
    if state.pending_input is None:
        return None
    mode_label = "RENAME"
    if state.ui_mode == "CREATE":
        mode_label = "NEW FILE" if state.pending_input.create_kind == "file" else "NEW DIR"
    if state.ui_mode == "EXTRACT":
        mode_label = "EXTRACT"
    if state.ui_mode == "ZIP":
        mode_label = "ZIP"
    return InputBarState(
        mode_label=mode_label,
        prompt=state.pending_input.prompt,
        value=state.pending_input.value,
        hint=(
            "enter extract | esc cancel"
            if state.ui_mode == "EXTRACT"
            else "enter compress | esc cancel"
            if state.ui_mode == "ZIP"
            else "enter apply | esc cancel"
        ),
    )


def select_command_palette_state(state: AppState) -> CommandPaletteViewState | None:
    """Return the visible command palette entries for the active mode."""

    if state.ui_mode != "PALETTE" or state.command_palette is None:
        return None

    cursor_index = normalize_command_palette_cursor(state, state.command_palette.cursor_index)
    if state.command_palette.source == "file_search":
        visible_results, title = _select_file_search_window(
            state,
            state.command_palette.file_search_results,
            cursor_index,
        )
        return CommandPaletteViewState(
            title=title,
            query=state.command_palette.query,
            items=tuple(
                CommandPaletteItemViewState(
                    label=result.display_path,
                    shortcut=None,
                    enabled=True,
                    selected=index == cursor_index,
                )
                for index, result in visible_results
            ),
            empty_message=_file_search_empty_message(state),
        )
    if state.command_palette.source == "grep_search":
        visible_results, title = _select_grep_search_window(
            state,
            state.command_palette.grep_search_results,
            cursor_index,
        )
        return CommandPaletteViewState(
            title=title,
            query=state.command_palette.query,
            items=tuple(
                CommandPaletteItemViewState(
                    label=result.display_label,
                    shortcut=None,
                    enabled=True,
                    selected=index == cursor_index,
                )
                for index, result in visible_results
            ),
            empty_message=_grep_search_empty_message(state),
        )
    if state.command_palette.source == "history":
        return _build_command_palette_items_view(
            state,
            cursor_index,
            title="Directory History",
            empty_message="No directory history",
        )

    if state.command_palette.source == "bookmarks":
        return _build_command_palette_items_view(
            state,
            cursor_index,
            title="Bookmarks",
            empty_message="No bookmarks",
        )

    if state.command_palette.source == "go_to_path":
        selection_active = state.command_palette.go_to_path_selection_active
        empty_message = (
            "Type a path to jump to"
            if not state.command_palette.query.strip()
            else "No matching directories"
        )
        return _build_command_palette_items_view(
            state,
            cursor_index,
            title="Go to path",
            empty_message=empty_message,
            selected_override=selection_active or False,
        )

    items = get_command_palette_items(state)
    visible_items, title = _select_command_palette_window(items, cursor_index)
    return CommandPaletteViewState(
        title=title,
        query=state.command_palette.query,
        items=tuple(
            CommandPaletteItemViewState(
                label=item.label,
                shortcut=item.shortcut,
                enabled=item.enabled,
                selected=index == cursor_index,
            )
            for index, item in visible_items
        ),
        empty_message="No matching commands",
    )


def select_split_terminal_state(state: AppState) -> SplitTerminalViewState:
    """Return display data for the embedded split terminal pane."""

    split_terminal = state.split_terminal
    if not split_terminal.visible:
        return SplitTerminalViewState(
            visible=False,
            status="closed",
            body="",
            focused=False,
        )

    if split_terminal.status == "starting":
        body = "Starting shell..."
    else:
        body = "Shell ready."
    return SplitTerminalViewState(
        visible=True,
        status=split_terminal.status,
        body=body,
        focused=split_terminal.focus_target == "terminal",
    )


def select_conflict_dialog_state(state: AppState) -> ConflictDialogState | None:
    """Return dialog content when the app is waiting on conflict input."""

    if state.delete_confirmation is not None:
        confirmation = state.delete_confirmation
        target_count = len(confirmation.paths)
        first_name = Path(confirmation.paths[0]).name
        noun = "item" if target_count == 1 else "items"
        if confirmation.mode == "permanent":
            message = f"Permanently delete {target_count} {noun}? This cannot be undone."
            if target_count > 1:
                message = (
                    f"Permanently delete {target_count} items? "
                    f"The first target is {first_name}. This cannot be undone."
                )
            title = "Permanent Delete Confirmation"
        else:
            message = f"Move {target_count} {noun} to trash?"
            if target_count > 1:
                message = f"Move {target_count} items to trash? The first target is {first_name}."
            title = "Delete Confirmation"
        return ConflictDialogState(
            title=title,
            message=message,
            options=("enter confirm", "esc cancel"),
        )

    if state.archive_extract_confirmation is not None:
        confirmation = state.archive_extract_confirmation
        destination_name = Path(confirmation.first_conflict_path).name
        message = (
            f"{confirmation.conflict_count} archive path(s) already exist in the destination. "
            f"The first conflict is {destination_name}. Continue extraction?"
        )
        return ConflictDialogState(
            title="Extract Archive Confirmation",
            message=message,
            options=("enter continue", "esc return to input"),
        )

    if state.zip_compress_confirmation is not None:
        confirmation = state.zip_compress_confirmation
        destination_name = Path(confirmation.request.destination_path).name
        return ConflictDialogState(
            title="Zip Compression Confirmation",
            message=(
                f"{destination_name} already exists. "
                f"Overwrite it and continue compressing {confirmation.total_entries} item(s)?"
            ),
            options=("enter overwrite", "esc return to input"),
        )

    if state.name_conflict is not None:
        name = state.name_conflict.name
        if state.name_conflict.kind == "rename":
            title = "Rename Conflict"
            message = f"'{name}' already exists. Enter a different name before renaming."
        elif state.name_conflict.kind == "create_file":
            title = "Create File Conflict"
            message = f"'{name}' already exists. Enter a different name before creating the file."
        else:
            title = "Create Directory Conflict"
            message = (
                f"'{name}' already exists. Enter a different name before creating the directory."
            )
        return ConflictDialogState(
            title=title,
            message=message,
            options=("enter return to input", "esc return to input"),
        )

    if state.paste_conflict is None:
        return None

    first_conflict = state.paste_conflict.first_conflict
    conflict_count = len(state.paste_conflict.conflicts)
    destination_name = Path(first_conflict.destination_path).name
    source_name = Path(first_conflict.source_path).name
    return ConflictDialogState(
        title="Paste Conflict",
        message=(
            f"{destination_name} already exists for {source_name}. "
            f"{conflict_count} conflict(s) pending."
        ),
        options=tuple(
            {
                "overwrite": "o overwrite",
                "skip": "s skip",
                "rename": "r rename",
            }[resolution]
            for resolution in state.paste_conflict.available_resolutions
        )
        + ("esc cancel",),
    )


def select_attribute_dialog_state(state: AppState) -> AttributeDialogState | None:
    """Return dialog content when the app is showing read-only attributes."""

    if state.attribute_inspection is None:
        return None

    entry = state.attribute_inspection
    kind_label = "Directory" if entry.kind == "dir" else "File"
    hidden_label = "Yes" if entry.hidden else "No"
    return AttributeDialogState(
        title=f"Attributes: {entry.name}",
        lines=(
            f"Name: {entry.name}",
            f"Type: {kind_label}",
            f"Path: {entry.path}",
            f"Size: {_format_size_label(entry.size_bytes)}",
            f"Modified: {_format_modified_label_from_timestamp(entry.modified_at)}",
            f"Hidden: {hidden_label}",
            f"Permissions: {_format_permissions_label(entry.permissions_mode)}",
        ),
        options=("enter close", "esc close"),
    )


def select_config_dialog_state(state: AppState) -> ConfigDialogState | None:
    """Return dialog content when the app is showing editable config values."""

    if state.ui_mode != "CONFIG" or state.config_editor is None:
        return None

    config = state.config_editor.draft
    selected_index = state.config_editor.cursor_index
    lines = (
        f"Path: {state.config_editor.path}",
        "",
        _format_config_line(
            0, selected_index, "Editor command", _format_editor_command_value(config.editor.command)
        ),
        _format_config_line(
            1,
            selected_index,
            "Show hidden files",
            _format_bool(config.display.show_hidden_files),
        ),
        _format_config_line(
            2,
            selected_index,
            "Theme",
            config.display.theme,
        ),
        _format_config_line(
            3,
            selected_index,
            "Show directory sizes",
            _format_bool(config.display.show_directory_sizes),
        ),
        _format_config_line(
            4,
            selected_index,
            "Default sort field",
            config.display.default_sort_field,
        ),
        _format_config_line(
            5,
            selected_index,
            "Default sort descending",
            _format_bool(config.display.default_sort_descending),
        ),
        _format_config_line(
            6, selected_index, "Directories first", _format_bool(config.display.directories_first)
        ),
        _format_config_line(
            7, selected_index, "Confirm delete", _format_bool(config.behavior.confirm_delete)
        ),
        _format_config_line(
            8, selected_index, "Paste conflict action", config.behavior.paste_conflict_action
        ),
        _format_config_line(
            9, selected_index, "Log level", config.logging.level
        ),
        "",
        _format_custom_editor_hint(config.editor.command),
        "Terminal launch templates: edit config.toml with e",
        f"  Linux templates: {len(config.terminal.linux)}",
        f"  macOS templates: {len(config.terminal.macos)}",
        f"  Windows templates: {len(config.terminal.windows)}",
    )
    title = "Config Editor"
    if state.config_editor.dirty:
        title = "Config Editor*"
    return ConfigDialogState(
        title=title,
        lines=lines,
        options=("left/right/enter change", "s save", "e edit file", "esc close"),
    )


def select_shell_command_dialog_state(state: AppState) -> ShellCommandDialogState | None:
    """Return dialog content when the app is collecting a shell command."""

    if state.ui_mode != "SHELL" or state.shell_command is None:
        return None

    return ShellCommandDialogState(
        title="Run Shell Command",
        cwd=state.shell_command.cwd,
        prompt="Command: ",
        command=state.shell_command.command,
        options=("enter run", "esc cancel"),
    )


def select_target_paths(state: AppState) -> tuple[str, ...]:
    """Return selected paths, or the cursor path when nothing is selected."""

    current_pane = _select_current_pane_projection(state)
    selected_paths = tuple(
        entry.path
        for entry in current_pane.visible_entries
        if entry.path in state.current_pane.selected_paths
    )
    if selected_paths:
        return selected_paths

    if current_pane.cursor_entry is None:
        return ()
    return (current_pane.cursor_entry.path,)


def select_visible_current_entry_states(state: AppState) -> tuple[DirectoryEntryState, ...]:
    """Return filtered and sorted raw current-pane entries."""

    return _select_visible_current_entry_states(
        state.current_pane.entries,
        state.directory_size_cache,
        state.show_hidden,
        state.filter.query,
        state.filter.active,
        state.sort,
    )


def _select_current_pane_projection(state: AppState) -> _CurrentPaneProjection:
    visible_entries = select_visible_current_entry_states(state)
    global_cursor_index = _find_current_cursor_index(
        visible_entries,
        state.current_pane.cursor_path,
    )
    projected_entries, cursor_index = _project_current_pane_entries(
        state,
        visible_entries,
        global_cursor_index,
    )
    cursor_entry = None if global_cursor_index is None else visible_entries[global_cursor_index]
    return _CurrentPaneProjection(
        visible_entries=visible_entries,
        projected_entries=projected_entries,
        cursor_index=cursor_index,
        cursor_entry=cursor_entry,
        summary=_build_current_summary(
            len(visible_entries),
            len(state.current_pane.selected_paths),
            state.sort,
        ),
    )


def _project_current_pane_entries(
    state: AppState,
    visible_entries: tuple[DirectoryEntryState, ...],
    global_cursor_index: int | None,
) -> tuple[tuple[DirectoryEntryState, ...], int | None]:
    if state.current_pane_projection_mode != "viewport":
        return visible_entries, global_cursor_index

    if not visible_entries:
        return (), None

    visible_window = compute_current_pane_visible_window(state.terminal_height)
    max_window_start = max(0, len(visible_entries) - visible_window)
    window_start = min(state.current_pane_window_start, max_window_start)
    window_end = min(len(visible_entries), window_start + visible_window)
    local_cursor_index = None
    if global_cursor_index is not None:
        local_cursor_index = global_cursor_index - window_start
    return visible_entries[window_start:window_end], local_cursor_index


@lru_cache(maxsize=256)
def _select_visible_current_entry_states(
    entries: tuple[DirectoryEntryState, ...],
    directory_size_cache: tuple[DirectorySizeCacheEntry, ...],
    show_hidden: bool,
    query: str,
    active: bool,
    sort: SortState,
) -> tuple[DirectoryEntryState, ...]:
    visible_entries = _filter_hidden_entries(entries, show_hidden)
    visible_entries = _filter_entries(visible_entries, query, active)
    if sort.field == "size":
        visible_entries = _overlay_directory_sizes(visible_entries, directory_size_cache)
    return _sort_entries(visible_entries, sort)


@lru_cache(maxsize=256)
def _select_current_pane_update_hint(
    projected_entries: tuple[DirectoryEntryState, ...],
    directory_size_cache: tuple[DirectorySizeCacheEntry, ...],
    display_directory_sizes: bool,
    sort: SortState,
    selected_paths: frozenset[str],
    cut_paths: frozenset[str],
    row_changed_paths: tuple[str, ...],
    row_revision: int,
    size_changed_paths: tuple[str, ...],
    size_revision: int,
) -> CurrentPaneUpdateHint:
    if sort.field == "size":
        return CurrentPaneUpdateHint(mode="full", revision=max(row_revision, size_revision))
    if row_changed_paths:
        row_updates = _select_current_pane_row_updates(
            projected_entries,
            directory_size_cache,
            display_directory_sizes,
            selected_paths,
            cut_paths,
            row_changed_paths,
        )
        projected_paths = frozenset(entry.path for entry in projected_entries)
        if len(row_updates) != len(frozenset(row_changed_paths) & projected_paths):
            return CurrentPaneUpdateHint(mode="full", revision=row_revision)
        return CurrentPaneUpdateHint(
            mode="row_delta",
            revision=row_revision,
            row_updates=row_updates,
        )
    if not size_changed_paths:
        return CurrentPaneUpdateHint(mode="full", revision=size_revision)
    return CurrentPaneUpdateHint(
        mode="size_delta",
        revision=size_revision,
        size_updates=_select_current_pane_size_updates(
            projected_entries,
            directory_size_cache,
            display_directory_sizes,
            size_changed_paths,
        ),
    )


@lru_cache(maxsize=256)
def _select_current_pane_row_updates(
    visible_entries: tuple[DirectoryEntryState, ...],
    directory_size_cache: tuple[DirectorySizeCacheEntry, ...],
    display_directory_sizes: bool,
    selected_paths: frozenset[str],
    cut_paths: frozenset[str],
    changed_paths: tuple[str, ...],
) -> tuple[CurrentPaneRowUpdate, ...]:
    changed_path_set = frozenset(changed_paths)
    return tuple(
        CurrentPaneRowUpdate(
            path=entry.path,
            entry=_to_pane_entry(
                entry,
                name_detail=_format_current_entry_name_detail(entry),
                size_label_override=_format_entry_size_label(
                    entry,
                    directory_size_cache,
                    display_directory_sizes=display_directory_sizes,
                ),
                selected=entry.path in selected_paths,
                cut=entry.path in cut_paths,
            ),
        )
        for entry in visible_entries
        if entry.path in changed_path_set
    )


@lru_cache(maxsize=256)
def _select_current_pane_size_updates(
    visible_entries: tuple[DirectoryEntryState, ...],
    directory_size_cache: tuple[DirectorySizeCacheEntry, ...],
    display_directory_sizes: bool,
    changed_paths: tuple[str, ...],
) -> tuple[CurrentPaneSizeUpdate, ...]:
    changed_path_set = frozenset(changed_paths)
    return tuple(
        CurrentPaneSizeUpdate(
            path=entry.path,
            size_label=_format_entry_size_label(
                entry,
                directory_size_cache,
                display_directory_sizes=display_directory_sizes,
            ),
        )
        for entry in visible_entries
        if entry.path in changed_path_set
    )


@lru_cache(maxsize=256)
def _select_side_pane_entry_states(
    entries: tuple[DirectoryEntryState, ...],
    show_hidden: bool,
) -> tuple[DirectoryEntryState, ...]:
    return _sort_entries(_filter_hidden_entries(entries, show_hidden), SIDE_PANE_SORT)


@lru_cache(maxsize=256)
def _select_current_pane_entries(
    visible_entries: tuple[DirectoryEntryState, ...],
    directory_size_cache: tuple[DirectorySizeCacheEntry, ...],
    display_directory_sizes: bool,
    selected_paths: frozenset[str],
    cut_paths: frozenset[str],
) -> tuple[PaneEntry, ...]:
    return tuple(
        _to_pane_entry(
            entry,
            name_detail=_format_current_entry_name_detail(entry),
            size_label_override=_format_entry_size_label(
                entry,
                directory_size_cache,
                display_directory_sizes=display_directory_sizes,
            ),
            selected=entry.path in selected_paths,
            cut=entry.path in cut_paths,
        )
        for entry in visible_entries
    )


@lru_cache(maxsize=256)
def _select_side_pane_entries(
    visible_entries: tuple[DirectoryEntryState, ...],
    directory_size_cache: tuple[DirectorySizeCacheEntry, ...],
    display_directory_sizes: bool,
    selected_path: str | None,
    cut_paths: frozenset[str],
) -> tuple[PaneEntry, ...]:
    return tuple(
        _to_pane_entry(
            entry,
            name_detail=_format_side_pane_name_detail(
                entry,
                directory_size_cache,
                display_directory_sizes=display_directory_sizes,
            ),
            selected=entry.path == selected_path,
            cut=entry.path in cut_paths,
        )
        for entry in visible_entries
    )


@lru_cache(maxsize=512)
def _select_visible_cut_paths(
    visible_entries: tuple[DirectoryEntryState, ...],
    cut_paths: frozenset[str],
) -> frozenset[str]:
    return frozenset(entry.path for entry in visible_entries if entry.path in cut_paths)


@lru_cache(maxsize=256)
def _build_current_summary(
    item_count: int,
    selected_count: int,
    sort: SortState,
) -> CurrentSummaryState:
    return CurrentSummaryState(
        item_count=item_count,
        selected_count=selected_count,
        sort_label=_format_sort_label(sort),
    )


@lru_cache(maxsize=256)
def _filter_hidden_entries(
    entries: tuple[DirectoryEntryState, ...],
    show_hidden: bool,
) -> tuple[DirectoryEntryState, ...]:
    if show_hidden:
        return entries
    return tuple(entry for entry in entries if not entry.hidden)


def _format_config_line(index: int, selected_index: int, label: str, value: str) -> str:
    prefix = ">" if index == selected_index else " "
    return f"{prefix} {label}: {value}"


def _format_bool(value: bool) -> str:
    return "true" if value else "false"


@lru_cache(maxsize=256)
def _filter_entries(
    entries: tuple[DirectoryEntryState, ...],
    query: str,
    active: bool,
) -> tuple[DirectoryEntryState, ...]:
    if not active or not query:
        return entries

    lowered_query = query.casefold()
    return tuple(entry for entry in entries if lowered_query in entry.name.casefold())


@lru_cache(maxsize=256)
def _sort_entries(
    entries: tuple[DirectoryEntryState, ...],
    sort: SortState,
) -> tuple[DirectoryEntryState, ...]:
    if sort.field == "size":
        return _sort_entries_by_size(entries, sort)

    directories = [entry for entry in entries if entry.kind == "dir"]
    files = [entry for entry in entries if entry.kind == "file"]

    sorted_directories = sorted(directories, key=_sort_key(sort.field), reverse=sort.descending)
    sorted_files = sorted(files, key=_sort_key(sort.field), reverse=sort.descending)

    if sort.directories_first:
        combined = [*sorted_directories, *sorted_files]
    else:
        combined = sorted(entries, key=_sort_key(sort.field), reverse=sort.descending)

    return tuple(combined)


def _sort_entries_by_size(
    entries: tuple[DirectoryEntryState, ...],
    sort: SortState,
) -> tuple[DirectoryEntryState, ...]:
    key = _sort_size_key(sort.descending)
    directories = [entry for entry in entries if entry.kind == "dir"]
    files = [entry for entry in entries if entry.kind == "file"]
    if sort.directories_first:
        combined = [*sorted(directories, key=key), *sorted(files, key=key)]
    else:
        combined = sorted(entries, key=key)
    return tuple(combined)


def _sort_key(field: str):
    if field == "modified":
        return lambda entry: (
            entry.modified_at is None,
            entry.modified_at or 0,
            entry.name.casefold(),
        )
    if field == "size":
        return lambda entry: (
            entry.size_bytes is None,
            entry.size_bytes or -1,
            entry.name.casefold(),
        )
    return lambda entry: entry.name.casefold()


def _sort_size_key(descending: bool):
    def key(entry: DirectoryEntryState) -> tuple[int, int, str]:
        if entry.size_bytes is None:
            return (1, 0, entry.name.casefold())
        value = -entry.size_bytes if descending else entry.size_bytes
        return (0, value, entry.name.casefold())

    return key


def _format_sort_label(sort: SortState) -> str:
    direction = "desc" if sort.descending else "asc"
    directories = "on" if sort.directories_first else "off"
    return f"{sort.field} {direction} dirs:{directories}"


def compute_search_visible_window(terminal_height: int) -> int:
    """Calculate visible search items based on terminal height."""
    palette_rows = max(1, terminal_height // 2)
    return max(MIN_SEARCH_VISIBLE_WINDOW, palette_rows - _SEARCH_OVERHEAD_ROWS)


def _build_command_palette_items_view(
    state: AppState,
    cursor_index: int,
    title: str,
    empty_message: str | None = None,
    *,
    selected_override: bool | None = None,
) -> CommandPaletteViewState:
    """コマンドパレットのアイテムビューを構築する共通関数。

    Args:
        state: アプリケーション状態
        cursor_index: カーソル位置
        title: パレットタイトル
        empty_message: 空メッセージ（Noneの場合はデフォルト値を使用）
        selected_override: 選択状態の上書き（go_to_path用）

    Returns:
        CommandPaletteViewState: コマンドパレットの表示状態
    """
    items = get_command_palette_items(state)
    visible_window = compute_search_visible_window(state.terminal_height)
    visible_items, _palette_title = _select_command_palette_window(
        items, cursor_index, visible_window=visible_window
    )

    return CommandPaletteViewState(
        title=title,
        query=state.command_palette.query,
        items=tuple(
            CommandPaletteItemViewState(
                label=item.label,
                shortcut=item.shortcut,
                enabled=item.enabled,
                selected=(
                    (
                        selected_override if selected_override is not None else True
                    ) and index == cursor_index
                ),
            )
            for index, item in visible_items
        ),
        empty_message=empty_message or "No items",
    )


def compute_current_pane_visible_window(terminal_height: int) -> int:
    """Estimate how many current-pane rows are visible in the terminal."""

    return max(MIN_CURRENT_PANE_VISIBLE_WINDOW, terminal_height - _CURRENT_PANE_OVERHEAD_ROWS)


def _select_file_search_window(
    state: AppState,
    results: tuple[FileSearchResultState, ...],
    cursor_index: int,
) -> tuple[tuple[tuple[int, FileSearchResultState], ...], str]:
    visible_window = compute_search_visible_window(state.terminal_height)
    return _select_search_window(
        results, cursor_index, title="Find File", visible_window=visible_window,
    )


def _select_grep_search_window(
    state: AppState,
    results: tuple[GrepSearchResultState, ...],
    cursor_index: int,
) -> tuple[tuple[tuple[int, GrepSearchResultState], ...], str]:
    visible_window = compute_search_visible_window(state.terminal_height)
    return _select_search_window(
        results, cursor_index, title="Grep", visible_window=visible_window,
    )


def _select_search_window(
    results: tuple[FileSearchResultState | GrepSearchResultState, ...],
    cursor_index: int,
    *,
    title: str,
    visible_window: int,
) -> tuple[tuple[tuple[int, FileSearchResultState | GrepSearchResultState], ...], str]:
    total = len(results)
    if total == 0:
        return (), title
    if total <= visible_window:
        return tuple(enumerate(results)), f"{title} (1-{total} / {total})"

    # 3段階アルゴリズムでスクロール位置を決定
    # 1. 中央揃えの理想的な位置を計算
    ideal_start = cursor_index - (visible_window // 2)
    # 2. 先頭境界を適用
    start = max(0, ideal_start)
    # 3. 末尾境界を適用（末尾が必ず見えるように）
    max_start = max(0, total - visible_window)
    start = min(start, max_start)
    end = min(total, start + visible_window)
    visible_results = tuple((index, results[index]) for index in range(start, end))
    return visible_results, f"{title} ({start + 1}-{end} / {total})"


def _select_command_palette_window(
    items: tuple[CommandPaletteItem, ...],
    cursor_index: int,
    visible_window: int = COMMAND_PALETTE_VISIBLE_WINDOW,
) -> tuple[tuple[tuple[int, CommandPaletteItem], ...], str]:
    total = len(items)
    if total <= visible_window:
        return tuple(enumerate(items)), "Command Palette"

    # 3段階アルゴリズムでスクロール位置を決定
    # 1. 中央揃えの理想的な位置を計算
    ideal_start = cursor_index - (visible_window // 2)
    # 2. 先頭境界を適用
    start = max(0, ideal_start)
    # 3. 末尾境界を適用（末尾が必ず見えるように）
    max_start = max(0, total - visible_window)
    start = min(start, max_start)
    end = min(total, start + visible_window)
    visible_items = tuple((index, items[index]) for index in range(start, end))
    return visible_items, f"Command Palette ({start + 1}-{end} / {total})"


def _file_search_empty_message(state: AppState) -> str:
    if state.pending_file_search_request_id is not None:
        return "Searching files..."
    if (
        state.command_palette is not None
        and state.command_palette.source == "file_search"
        and state.command_palette.file_search_error_message is not None
    ):
        return state.command_palette.file_search_error_message
    return "No matching files"


def _grep_search_empty_message(state: AppState) -> str:
    if state.pending_grep_search_request_id is not None:
        return "Searching matches..."
    if (
        state.command_palette is not None
        and state.command_palette.source == "grep_search"
        and state.command_palette.grep_search_error_message is not None
    ):
        return state.command_palette.grep_search_error_message
    return "No matching lines"


def _get_current_cursor_entry(state: AppState) -> DirectoryEntryState | None:
    return _select_current_pane_projection(state).cursor_entry


def _select_cut_paths(state: AppState) -> frozenset[str]:
    if state.clipboard.mode != "cut":
        return frozenset()
    return frozenset(state.clipboard.paths)


@lru_cache(maxsize=4096)
def _to_pane_entry(
    entry: DirectoryEntryState,
    *,
    name_detail: str | None = None,
    size_label_override: str | None = None,
    selected: bool = False,
    cut: bool = False,
) -> PaneEntry:
    return PaneEntry(
        name=entry.name,
        kind=entry.kind,
        name_detail=name_detail,
        size_label=size_label_override or _format_size_label(entry.size_bytes),
        modified_label=_format_modified_label(entry),
        selected=selected,
        cut=cut,
        executable=_has_execute_permission(entry),
        path=entry.path,
    )


def _find_current_cursor_index(
    entries: tuple[DirectoryEntryState, ...],
    cursor_path: str | None,
) -> int | None:
    if cursor_path is None:
        return None
    return _build_entry_index(entries).get(cursor_path)


@lru_cache(maxsize=256)
def _build_entry_index(entries: tuple[DirectoryEntryState, ...]) -> dict[str, int]:
    return {entry.path: index for index, entry in enumerate(entries)}


def _format_size_label(size_bytes: int | None) -> str:
    if size_bytes is None:
        return "-"
    if size_bytes < 1_000:
        return f"{size_bytes} B"
    units = ("KB", "MB", "GB", "TB")
    size = float(size_bytes)
    for unit in units:
        size /= 1_000
        if size < 1_000 or unit == units[-1]:
            return f"{size:.1f} {unit}"
    return f"{size:.1f} TB"


def _format_modified_label(entry: DirectoryEntryState) -> str:
    if entry.modified_at is None:
        return "-"
    return entry.modified_at.strftime("%Y-%m-%d %H:%M")


def _format_modified_label_from_timestamp(value: datetime | None) -> str:
    if value is None:
        return "-"
    return value.strftime("%Y-%m-%d %H:%M")


def _format_permissions_label(mode: int | None) -> str:
    if mode is None:
        return "-"
    normalized_mode = S_IMODE(mode)
    return f"{filemode(mode)} ({normalized_mode:03o})"


def _format_editor_command_value(command: str | None) -> str:
    if command is None:
        return "system default"
    if command in {"nvim", "vim", "nano", "hx", "micro", "emacs -nw"}:
        return command
    return "custom (raw config only)"


def _format_custom_editor_hint(command: str | None) -> str:
    if command is None or command in {"nvim", "vim", "nano", "hx", "micro", "emacs -nw"}:
        return "Editor presets: system default, nvim, vim, nano, hx, micro, emacs -nw"
    return f"Custom editor command: {command}"


def _format_current_entry_name_detail(entry: DirectoryEntryState) -> str | None:
    return None


@lru_cache(maxsize=256)
def _directory_size_cache_by_path(
    directory_size_cache: tuple[DirectorySizeCacheEntry, ...],
) -> dict[str, DirectorySizeCacheEntry]:
    return {entry.path: entry for entry in directory_size_cache}


@lru_cache(maxsize=256)
def _overlay_directory_sizes(
    entries: tuple[DirectoryEntryState, ...],
    directory_size_cache: tuple[DirectorySizeCacheEntry, ...],
) -> tuple[DirectoryEntryState, ...]:
    cache_by_path = _directory_size_cache_by_path(directory_size_cache)
    return tuple(
        replace(entry, size_bytes=cache_by_path[entry.path].size_bytes)
        if entry.kind == "dir"
        and entry.path in cache_by_path
        and cache_by_path[entry.path].status == "ready"
        else entry
        for entry in entries
    )


def _format_entry_size_label(
    entry: DirectoryEntryState,
    directory_size_cache: tuple[DirectorySizeCacheEntry, ...],
    *,
    display_directory_sizes: bool,
) -> str:
    if entry.kind != "dir":
        return _format_size_label(entry.size_bytes)
    if not display_directory_sizes:
        return "-"
    cached_entry = _directory_size_cache_by_path(directory_size_cache).get(entry.path)
    if cached_entry is None or cached_entry.status == "failed":
        return "-"
    if cached_entry.status == "pending":
        return "calculating..."
    return _format_size_label(cached_entry.size_bytes)


def _format_side_pane_name_detail(
    entry: DirectoryEntryState,
    directory_size_cache: tuple[DirectorySizeCacheEntry, ...],
    *,
    display_directory_sizes: bool,
) -> str | None:
    if entry.kind != "dir":
        return None
    size_label = _format_entry_size_label(
        entry,
        directory_size_cache,
        display_directory_sizes=display_directory_sizes,
    )
    if size_label == "-":
        return None
    return size_label
