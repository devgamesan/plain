"""Pane-oriented selector implementations."""

from dataclasses import dataclass
from functools import lru_cache

from zivo.archive_utils import is_supported_archive_path
from zivo.models import (
    ChildPaneViewState,
    CurrentPaneRowUpdate,
    CurrentPaneSizeUpdate,
    CurrentPaneUpdateHint,
    CurrentSummaryState,
    PaneEntry,
    TabBarState,
    TabItemState,
)

from .models import (
    AppState,
    DirectoryEntryState,
    DirectorySizeCacheEntry,
    SortState,
    select_browser_tabs,
)
from .selectors_shared import (
    SIDE_PANE_SORT,
    _find_current_cursor_index,
    _format_child_preview_title,
    _format_current_entry_name_detail,
    _format_entry_size_label,
    _format_permissions_detail_label,
    _format_side_pane_name_detail,
    _format_sort_label,
    _format_tab_label,
    _select_active_app_theme,
    _select_active_preview_syntax_theme,
    _select_child_syntax_theme,
    _sort_entries,
    _to_pane_entry,
    compute_current_pane_visible_window,
    normalize_command_palette_cursor,
    select_visible_current_entry_states,
)


@dataclass(frozen=True)
class CurrentPaneProjection:
    visible_entries: tuple[DirectoryEntryState, ...]
    projected_entries: tuple[DirectoryEntryState, ...]
    cursor_index: int | None
    cursor_entry: DirectoryEntryState | None
    summary: CurrentSummaryState


def select_tab_bar_state(state: AppState) -> TabBarState:
    """Return display state for the top-level tab bar."""

    tabs = tuple(
        TabItemState(
            label=_format_tab_label(tab.current_path),
            active=index == state.active_tab_index,
        )
        for index, tab in enumerate(select_browser_tabs(state))
    )
    return TabBarState(tabs=tabs)


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
    if cursor_entry is None:
        return ()
    is_archive = cursor_entry.kind == "file" and is_supported_archive_path(cursor_entry.path)
    if cursor_entry.kind != "dir" and not is_archive:
        return ()
    return select_child_pane_for_cursor(state, cursor_entry).entries


def select_current_summary_state(state: AppState) -> CurrentSummaryState:
    """Return the summary model shown near the current pane."""

    return select_current_pane_projection(state).summary


def select_current_pane_projection(state: AppState) -> CurrentPaneProjection:
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
    return CurrentPaneProjection(
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


def select_child_pane_for_cursor(
    state: AppState,
    cursor_entry: DirectoryEntryState | None,
) -> ChildPaneViewState:
    syntax_theme = _select_child_syntax_theme(
        _select_active_app_theme(state),
        _select_active_preview_syntax_theme(state),
    )
    permissions_label = (
        _format_permissions_detail_label(cursor_entry)
        if cursor_entry
        else ""
    )
    palette_preview = _select_command_palette_preview_pane(state, syntax_theme)
    if palette_preview is not None:
        return palette_preview

    if cursor_entry is None:
        return _build_child_entries_view((), syntax_theme, permissions_label)

    is_archive = cursor_entry.kind == "file" and is_supported_archive_path(cursor_entry.path)
    if cursor_entry.kind == "dir" or is_archive:
        if (
            state.child_pane.mode == "preview"
            and state.child_pane.preview_message is not None
        ):
            pass
        elif (
            state.child_pane.mode != "entries"
            or cursor_entry.path != state.child_pane.directory_path
        ):
            return _build_child_entries_view((), syntax_theme, permissions_label)
    elif (
        state.child_pane.mode != "preview"
        or cursor_entry.path != state.child_pane.preview_path
    ):
        return _build_child_entries_view((), syntax_theme, permissions_label)

    if state.child_pane.mode == "preview" and state.child_pane.preview_content is not None:
        preview_path = state.child_pane.preview_path or cursor_entry.path
        return _build_child_preview_view(
            state.child_pane.preview_title,
            preview_path,
            state.child_pane.preview_content,
            state.child_pane.preview_message,
            state.child_pane.preview_truncated,
            state.child_pane.preview_start_line,
            state.child_pane.preview_highlight_line,
            syntax_theme,
            permissions_label,
        )
    if state.child_pane.mode == "preview" and state.child_pane.preview_message is not None:
        preview_path = state.child_pane.preview_path or cursor_entry.path
        return _build_child_preview_view(
            state.child_pane.preview_title,
            preview_path,
            state.child_pane.preview_content,
            state.child_pane.preview_message,
            state.child_pane.preview_truncated,
            state.child_pane.preview_start_line,
            state.child_pane.preview_highlight_line,
            syntax_theme,
            permissions_label,
        )

    visible_entries = _select_side_pane_entry_states(state.child_pane.entries, state.show_hidden)
    return _build_child_entries_view(
        _select_side_pane_entries(
            visible_entries,
            state.directory_size_cache,
            display_directory_sizes=False,
            selected_path=None,
            cut_paths=_select_visible_cut_paths(visible_entries, _select_cut_paths(state)),
        ),
        syntax_theme,
        permissions_label,
    )


def _select_command_palette_preview_pane(
    state: AppState,
    syntax_theme: str,
) -> ChildPaneViewState | None:
    if state.ui_mode != "PALETTE" or state.command_palette is None:
        return None
    if state.command_palette.source == "file_search":
        return _select_file_search_preview_pane(state, syntax_theme)
    if state.command_palette.source == "grep_search":
        return _select_grep_preview_pane(state, syntax_theme)
    if state.command_palette.source in {
        "replace_text",
        "replace_in_found_files",
        "replace_in_grep_files",
        "grep_replace_selected",
    }:
        return _select_replace_preview_pane(state, syntax_theme)
    return None


def _select_file_search_preview_pane(
    state: AppState,
    syntax_theme: str,
) -> ChildPaneViewState:
    if not state.config.display.show_preview:
        return _build_child_entries_view((), syntax_theme)

    results = state.command_palette.file_search_results
    if not results:
        return _build_child_entries_view((), syntax_theme)

    selected_result = results[
        normalize_command_palette_cursor(state, state.command_palette.cursor_index)
    ]
    if (
        state.child_pane.mode != "preview"
        or state.child_pane.preview_path != selected_result.path
        or state.child_pane.preview_title is not None
        or state.child_pane.preview_start_line is not None
        or state.child_pane.preview_highlight_line is not None
    ):
        return _build_child_entries_view((), syntax_theme)

    return _build_child_preview_view(
        state.child_pane.preview_title,
        state.child_pane.preview_path or selected_result.path,
        state.child_pane.preview_content,
        state.child_pane.preview_message,
        state.child_pane.preview_truncated,
        state.child_pane.preview_start_line,
        state.child_pane.preview_highlight_line,
        syntax_theme,
    )


def _select_grep_preview_pane(
    state: AppState,
    syntax_theme: str,
) -> ChildPaneViewState:
    if not state.config.display.show_preview:
        return _build_child_entries_view((), syntax_theme)

    results = state.command_palette.grep_search_results
    if not results:
        return _build_child_entries_view((), syntax_theme)

    selected_result = results[
        normalize_command_palette_cursor(state, state.command_palette.cursor_index)
    ]
    if (
        state.child_pane.mode != "preview"
        or state.child_pane.preview_path != selected_result.path
        or state.child_pane.preview_highlight_line != selected_result.line_number
    ):
        return _build_child_entries_view((), syntax_theme)

    return _build_child_preview_view(
        state.child_pane.preview_title,
        state.child_pane.preview_path or selected_result.path,
        state.child_pane.preview_content,
        state.child_pane.preview_message,
        state.child_pane.preview_truncated,
        state.child_pane.preview_start_line,
        state.child_pane.preview_highlight_line,
        syntax_theme,
    )


def _select_replace_preview_pane(
    state: AppState,
    syntax_theme: str,
) -> ChildPaneViewState:
    if not state.config.display.show_preview:
        return _build_child_entries_view((), syntax_theme)
    if state.command_palette.source == "replace_in_found_files":
        results = state.command_palette.rff_preview_results
    elif state.command_palette.source == "replace_in_grep_files":
        results = state.command_palette.grf_preview_results
    elif state.command_palette.source == "grep_replace_selected":
        results = state.command_palette.grs_preview_results
    else:
        results = state.command_palette.replace_preview_results
    if not results:
        return _build_child_entries_view((), syntax_theme)
    selected_result = results[
        normalize_command_palette_cursor(state, state.command_palette.cursor_index)
    ]
    if (
        state.child_pane.mode != "preview"
        or state.child_pane.preview_title != "Replace Preview"
        or state.child_pane.preview_path != selected_result.path
    ):
        return _build_child_entries_view((), syntax_theme)
    return _build_child_preview_view(
        state.child_pane.preview_title,
        state.child_pane.preview_path or selected_result.path,
        state.child_pane.preview_content,
        state.child_pane.preview_message,
        state.child_pane.preview_truncated,
        state.child_pane.preview_start_line,
        state.child_pane.preview_highlight_line,
        syntax_theme,
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
def select_current_pane_update_hint(
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
            row_index=row_index,
        )
        for row_index, entry in enumerate(visible_entries)
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
            row_index=row_index,
        )
        for row_index, entry in enumerate(visible_entries)
        if entry.path in changed_path_set
    )


@lru_cache(maxsize=256)
def _select_side_pane_entry_states(
    entries: tuple[DirectoryEntryState, ...],
    show_hidden: bool,
) -> tuple[DirectoryEntryState, ...]:
    visible_entries = entries if show_hidden else tuple(
        entry for entry in entries if not entry.hidden
    )
    return _sort_entries(visible_entries, SIDE_PANE_SORT)


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


@lru_cache(maxsize=256)
def _build_child_entries_view(
    entries: tuple[PaneEntry, ...],
    syntax_theme: str,
    permissions_label: str = "",
) -> ChildPaneViewState:
    return ChildPaneViewState(
        title="Child Directory",
        entries=entries,
        syntax_theme=syntax_theme,
        permissions_label=permissions_label,
    )


@lru_cache(maxsize=256)
def _build_child_preview_view(
    preview_title: str | None,
    preview_path: str,
    preview_content: str | None,
    preview_message: str | None,
    preview_truncated: bool,
    preview_start_line: int | None,
    preview_highlight_line: int | None,
    syntax_theme: str,
    permissions_label: str = "",
) -> ChildPaneViewState:
    return ChildPaneViewState(
        title=preview_title or _format_child_preview_title(preview_path, preview_truncated),
        preview_path=preview_path,
        preview_title=preview_title,
        preview_content=preview_content,
        preview_message=preview_message,
        preview_truncated=preview_truncated,
        preview_start_line=preview_start_line,
        preview_highlight_line=preview_highlight_line,
        syntax_theme=syntax_theme,
        permissions_label=permissions_label,
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


def _get_current_cursor_entry(state: AppState) -> DirectoryEntryState | None:
    return select_current_pane_projection(state).cursor_entry


def _select_cut_paths(state: AppState) -> frozenset[str]:
    if state.clipboard.mode != "cut":
        return frozenset()
    return frozenset(state.clipboard.paths)
