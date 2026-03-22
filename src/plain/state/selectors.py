"""Selectors that convert AppState into display models."""

from pathlib import Path

from plain.models import (
    ConflictDialogState,
    HelpBarState,
    InputBarState,
    PaneEntry,
    StatusBarState,
    ThreePaneShellData,
)

from .models import AppState, DirectoryEntryState, SortState


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
        help=select_help_bar_state(state),
        input_bar=select_input_bar_state(state),
        status=select_status_bar_state(state),
        conflict_dialog=select_conflict_dialog_state(state),
    )


def select_parent_entries(state: AppState) -> tuple[PaneEntry, ...]:
    """Return display entries for the parent pane."""

    cut_paths = _select_cut_paths(state)
    return tuple(
        _to_pane_entry(entry, cut=entry.path in cut_paths)
        for entry in state.parent_pane.entries
    )


def select_current_entries(state: AppState) -> tuple[PaneEntry, ...]:
    """Return display entries for the current pane after filter/sort."""

    cut_paths = _select_cut_paths(state)
    return tuple(
        _to_pane_entry(
            entry,
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
        for entry in state.child_pane.entries
    )


def select_status_bar_state(state: AppState) -> StatusBarState:
    """Return a status bar model derived from app state."""

    visible_entries = select_visible_current_entry_states(state)
    return StatusBarState(
        item_count=len(visible_entries),
        selected_count=len(state.current_pane.selected_paths),
        sort_label=_format_sort_label(state.sort),
        filter_label=_format_filter_label(state),
        message=state.notification.message if state.notification else None,
        message_level=state.notification.level if state.notification else None,
    )


def select_help_bar_state(state: AppState) -> HelpBarState:
    """Return the single-line help content for the active mode."""

    if state.ui_mode == "CONFIRM":
        return HelpBarState("o overwrite | s skip | r rename | esc cancel")
    if state.ui_mode == "FILTER":
        return HelpBarState("type filter | space recursive | enter apply | esc cancel")
    if state.ui_mode == "RENAME":
        return HelpBarState("type name | enter apply | esc cancel")
    if state.ui_mode == "CREATE":
        return HelpBarState("type name | enter apply | esc cancel")
    if state.ui_mode == "BUSY":
        return HelpBarState("processing...")
    return HelpBarState(
        "Space select | y copy | x cut | p paste | F2 rename | ctrl+n file | ctrl+shift+n dir"
    )


def select_input_bar_state(state: AppState) -> InputBarState | None:
    """Return the rename/create input bar state for the active mode."""

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
    )


def select_conflict_dialog_state(state: AppState) -> ConflictDialogState | None:
    """Return dialog content when the app is waiting on conflict input."""

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

    selected_paths = tuple(
        entry.path
        for entry in state.current_pane.entries
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

    entries = tuple(
        _filter_entries(
            state.current_pane.entries,
            state.filter.query,
            state.filter.active,
        )
    )
    return _sort_entries(entries, state.sort)


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
    return f"{sort.field} {direction}"


def _format_filter_label(state: AppState) -> str:
    if not state.filter.active or not state.filter.query:
        return "none"
    if state.filter.recursive:
        return f"{state.filter.query} (recursive)"
    return state.filter.query


def _get_current_cursor_entry(state: AppState) -> DirectoryEntryState | None:
    cursor_path = state.current_pane.cursor_path
    for entry in state.current_pane.entries:
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
    selected: bool = False,
    cut: bool = False,
) -> PaneEntry:
    return PaneEntry(
        name=entry.name,
        kind=entry.kind,
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
