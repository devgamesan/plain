"""Selectors that convert AppState into display models."""

from pathlib import Path

from peneo.models import (
    CommandPaletteItemViewState,
    CommandPaletteViewState,
    ConflictDialogState,
    CurrentSummaryState,
    HelpBarState,
    InputBarState,
    PaneEntry,
    StatusBarState,
    ThreePaneShellData,
)

from .command_palette import get_command_palette_items, normalize_command_palette_cursor
from .models import AppState, DirectoryEntryState, FileSearchResultState, SortState

SIDE_PANE_SORT = SortState(field="name", descending=False, directories_first=True)
FILE_SEARCH_VISIBLE_WINDOW = 8


def select_shell_data(state: AppState) -> ThreePaneShellData:
    """Build the display shell data consumed by the UI layer."""

    current_entries = select_visible_current_entry_states(state)
    cut_paths = _select_cut_paths(state)
    return ThreePaneShellData(
        current_path=state.current_path,
        parent_entries=select_parent_entries(state),
        current_entries=tuple(
            _to_pane_entry(
                entry,
                name_detail=_format_current_entry_name_detail(state, entry),
                selected=entry.path in state.current_pane.selected_paths,
                cut=entry.path in cut_paths,
            )
            for entry in current_entries
        ),
        child_entries=select_child_entries(state),
        current_cursor_index=_find_current_cursor_index(
            current_entries,
            state.current_pane.cursor_path,
        ),
        current_summary=select_current_summary_state(state),
        current_context_input=select_input_bar_state(state),
        help=select_help_bar_state(state),
        command_palette=select_command_palette_state(state),
        status=select_status_bar_state(state),
        conflict_dialog=select_conflict_dialog_state(state),
    )


def select_parent_entries(state: AppState) -> tuple[PaneEntry, ...]:
    """Return display entries for the parent pane."""

    cut_paths = _select_cut_paths(state)
    return tuple(
        _to_pane_entry(entry, cut=entry.path in cut_paths)
        for entry in _sort_entries(
            _filter_hidden_entries(state.parent_pane.entries, state.show_hidden),
            SIDE_PANE_SORT,
        )
    )


def select_current_entries(state: AppState) -> tuple[PaneEntry, ...]:
    """Return display entries for the current pane after filter/sort."""

    cut_paths = _select_cut_paths(state)
    return tuple(
        _to_pane_entry(
            entry,
            name_detail=_format_current_entry_name_detail(state, entry),
            selected=entry.path in state.current_pane.selected_paths,
            cut=entry.path in cut_paths,
        )
        for entry in select_visible_current_entry_states(state)
    )


def select_child_entries(state: AppState) -> tuple[PaneEntry, ...]:
    """Return display entries for the child pane when the cursor is on a directory."""

    cursor_entry = _get_current_cursor_entry(state)
    if cursor_entry is None or cursor_entry.kind != "dir":
        return ()
    if cursor_entry.path != state.child_pane.directory_path:
        return ()
    cut_paths = _select_cut_paths(state)
    return tuple(
        _to_pane_entry(entry, cut=entry.path in cut_paths)
        for entry in _sort_entries(
            _filter_hidden_entries(state.child_pane.entries, state.show_hidden),
            SIDE_PANE_SORT,
        )
    )


def select_current_summary_state(state: AppState) -> CurrentSummaryState:
    """Return the summary model shown near the current pane."""

    visible_entries = select_visible_current_entry_states(state)
    return CurrentSummaryState(
        item_count=len(visible_entries),
        selected_count=len(state.current_pane.selected_paths),
        sort_label=_format_sort_label(state.sort),
    )


def select_status_bar_state(state: AppState) -> StatusBarState:
    """Return a status bar model derived from app state."""

    return StatusBarState(
        message=state.notification.message if state.notification else None,
        message_level=state.notification.level if state.notification else None,
    )


def select_help_bar_state(state: AppState) -> HelpBarState:
    """Return the single-line help content for the active mode."""

    if state.ui_mode == "CONFIRM":
        if state.delete_confirmation is not None:
            return HelpBarState("enter confirm delete | esc cancel")
        if state.name_conflict is not None:
            return HelpBarState("enter return to input | esc return to input")
        return HelpBarState("resolve conflict in dialog")
    if state.ui_mode == "FILTER":
        return HelpBarState("type filter | enter/down apply | esc clear")
    if state.ui_mode == "RENAME":
        return HelpBarState("type name | enter apply | esc cancel")
    if state.ui_mode == "CREATE":
        return HelpBarState("type name | enter apply | esc cancel")
    if state.ui_mode == "PALETTE":
        if state.command_palette is not None and state.command_palette.source == "file_search":
            return HelpBarState("type filename | enter jump | esc cancel")
        return HelpBarState("type command | enter run | esc cancel")
    if state.ui_mode == "BUSY":
        return HelpBarState("processing...")
    return HelpBarState(
        "Right dir | Enter open | e edit | / filter | Space select | y copy | x cut | "
        "p paste | q quit | "
        "s sort | d dirs | F2 rename | : palette"
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

    if state.ui_mode not in {"RENAME", "CREATE"}:
        return None
    if state.pending_input is None:
        return None
    mode_label = "RENAME"
    if state.ui_mode == "CREATE":
        mode_label = "NEW FILE" if state.pending_input.create_kind == "file" else "NEW DIR"
    return InputBarState(
        mode_label=mode_label,
        prompt=state.pending_input.prompt,
        value=state.pending_input.value,
        hint="enter apply | esc cancel",
    )


def select_command_palette_state(state: AppState) -> CommandPaletteViewState | None:
    """Return the visible command palette entries for the active mode."""

    if state.ui_mode != "PALETTE" or state.command_palette is None:
        return None

    cursor_index = normalize_command_palette_cursor(state, state.command_palette.cursor_index)
    if state.command_palette.source == "file_search":
        visible_results, title = _select_file_search_window(
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

    items = get_command_palette_items(state)
    return CommandPaletteViewState(
        title="Command Palette",
        query=state.command_palette.query,
        items=tuple(
            CommandPaletteItemViewState(
                label=item.label,
                shortcut=item.shortcut,
                enabled=item.enabled,
                selected=index == cursor_index,
            )
            for index, item in enumerate(items)
        ),
        empty_message="No matching commands",
    )


def select_conflict_dialog_state(state: AppState) -> ConflictDialogState | None:
    """Return dialog content when the app is waiting on conflict input."""

    if state.delete_confirmation is not None:
        target_count = len(state.delete_confirmation.paths)
        first_name = Path(state.delete_confirmation.paths[0]).name
        noun = "item" if target_count == 1 else "items"
        message = f"Move {target_count} {noun} to trash?"
        if target_count > 1:
            message = (
                f"Move {target_count} items to trash? "
                f"The first target is {first_name}."
            )
        return ConflictDialogState(
            title="Delete Confirmation",
            message=message,
            options=("enter confirm", "esc cancel"),
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


def select_target_paths(state: AppState) -> tuple[str, ...]:
    """Return selected paths, or the cursor path when nothing is selected."""

    visible_entries = select_visible_current_entry_states(state)
    selected_paths = tuple(
        entry.path
        for entry in visible_entries
        if entry.path in state.current_pane.selected_paths
    )
    if selected_paths:
        return selected_paths

    cursor_entry = _get_current_cursor_entry(state)
    if cursor_entry is None:
        return ()
    return (cursor_entry.path,)


def select_visible_current_entry_states(state: AppState) -> tuple[DirectoryEntryState, ...]:
    """Return filtered and sorted raw current-pane entries."""

    entries = _filter_hidden_entries(state.current_pane.entries, state.show_hidden)
    entries = tuple(
        _filter_entries(
            entries,
            state.filter.query,
            state.filter.active,
        )
    )
    return _sort_entries(entries, state.sort)


def _filter_hidden_entries(
    entries: tuple[DirectoryEntryState, ...],
    show_hidden: bool,
) -> tuple[DirectoryEntryState, ...]:
    if show_hidden:
        return entries
    return tuple(entry for entry in entries if not entry.hidden)


def _filter_entries(
    entries: tuple[DirectoryEntryState, ...],
    query: str,
    active: bool,
) -> tuple[DirectoryEntryState, ...]:
    if not active or not query:
        return entries

    lowered_query = query.casefold()
    return tuple(entry for entry in entries if lowered_query in entry.name.casefold())


def _sort_entries(
    entries: tuple[DirectoryEntryState, ...],
    sort: SortState,
) -> tuple[DirectoryEntryState, ...]:
    directories = [entry for entry in entries if entry.kind == "dir"]
    files = [entry for entry in entries if entry.kind == "file"]

    sorted_directories = sorted(directories, key=_sort_key(sort.field), reverse=sort.descending)
    sorted_files = sorted(files, key=_sort_key(sort.field), reverse=sort.descending)

    if sort.directories_first:
        combined = [*sorted_directories, *sorted_files]
    else:
        combined = sorted(entries, key=_sort_key(sort.field), reverse=sort.descending)

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


def _format_sort_label(sort: SortState) -> str:
    direction = "desc" if sort.descending else "asc"
    directories = "on" if sort.directories_first else "off"
    return f"{sort.field} {direction} dirs:{directories}"


def _select_file_search_window(
    results: tuple[FileSearchResultState, ...],
    cursor_index: int,
) -> tuple[tuple[tuple[int, FileSearchResultState], ...], str]:
    total = len(results)
    if total == 0:
        return (), "Find File"

    start = max(
        0,
        min(
            cursor_index - (FILE_SEARCH_VISIBLE_WINDOW // 2),
            max(0, total - FILE_SEARCH_VISIBLE_WINDOW),
        ),
    )
    end = min(total, start + FILE_SEARCH_VISIBLE_WINDOW)
    visible_results = tuple((index, results[index]) for index in range(start, end))
    return visible_results, f"Find File ({start + 1}-{end} / {total})"


def _file_search_empty_message(state: AppState) -> str:
    if state.pending_file_search_request_id is not None:
        return "Searching files..."
    return "No matching files"


def _get_current_cursor_entry(state: AppState) -> DirectoryEntryState | None:
    cursor_path = state.current_pane.cursor_path
    for entry in select_visible_current_entry_states(state):
        if entry.path == cursor_path:
            return entry
    return None


def _select_cut_paths(state: AppState) -> frozenset[str]:
    if state.clipboard.mode != "cut":
        return frozenset()
    return frozenset(state.clipboard.paths)


def _to_pane_entry(
    entry: DirectoryEntryState,
    *,
    name_detail: str | None = None,
    selected: bool = False,
    cut: bool = False,
) -> PaneEntry:
    return PaneEntry(
        name=entry.name,
        kind=entry.kind,
        name_detail=name_detail,
        size_label=_format_size_label(entry.size_bytes),
        modified_label=_format_modified_label(entry),
        selected=selected,
        cut=cut,
    )


def _find_current_cursor_index(
    entries: tuple[DirectoryEntryState, ...],
    cursor_path: str | None,
) -> int | None:
    if cursor_path is None:
        return None
    for index, entry in enumerate(entries):
        if entry.path == cursor_path:
            return index
    return None


def _format_size_label(size_bytes: int | None) -> str:
    if size_bytes is None:
        return "-"
    if size_bytes < 1_000:
        return f"{size_bytes} B"
    return f"{size_bytes / 1_000:.1f} KB"


def _format_modified_label(entry: DirectoryEntryState) -> str:
    if entry.modified_at is None:
        return "-"
    return entry.modified_at.strftime("%Y-%m-%d %H:%M")


def _format_current_entry_name_detail(
    state: AppState,
    entry: DirectoryEntryState,
) -> str | None:
    return None
