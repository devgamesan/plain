"""Shared selector helpers and compatibility entry points."""

from dataclasses import replace
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from stat import S_IMODE, filemode
from typing import TYPE_CHECKING

from zivo.models import (
    CommandPaletteInputFieldViewState,
    CommandPaletteItemViewState,
    CommandPaletteViewState,
    PaneEntry,
)
from zivo.theme_support import preview_syntax_theme_for_app_theme

from .entry_state_helpers import (
    current_entry_for_path as shared_current_entry_for_path,
)
from .entry_state_helpers import (
    single_target_entry as shared_single_target_entry,
)
from .entry_state_helpers import (
    target_paths as shared_target_paths,
)
from .entry_state_helpers import (
    visible_current_entry_states as shared_visible_current_entry_states,
)
from .models import (
    AppState,
    CommandPaletteState,
    DirectoryEntryState,
    DirectorySizeCacheEntry,
    FileSearchResultState,
    GrepSearchResultState,
    ReplacePreviewResultState,
    SortState,
)

if TYPE_CHECKING:
    from .command_palette import CommandPaletteItem


def get_command_palette_items(state: AppState) -> tuple["CommandPaletteItem", ...]:
    from .command_palette import get_command_palette_items

    return get_command_palette_items(state)


def normalize_command_palette_cursor(state: AppState, cursor_index: int) -> int:
    from .command_palette import normalize_command_palette_cursor

    return normalize_command_palette_cursor(state, cursor_index)


SIDE_PANE_SORT = SortState(field="name", descending=False, directories_first=True)
COMMAND_PALETTE_VISIBLE_WINDOW = 8
MIN_SEARCH_VISIBLE_WINDOW = 3
_SEARCH_OVERHEAD_ROWS = 10
_GREP_SEARCH_EXTRA_INPUT_ROWS = 2
_FILE_SEARCH_EXTRA_INPUT_ROWS = 1
MIN_CURRENT_PANE_VISIBLE_WINDOW = 5
_CURRENT_PANE_OVERHEAD_ROWS = 9


def _select_active_app_theme(state: AppState) -> str:
    if state.ui_mode == "CONFIG" and state.config_editor is not None:
        return state.config_editor.draft.display.theme
    return state.config.display.theme


def _select_active_preview_syntax_theme(state: AppState) -> str:
    if state.ui_mode == "CONFIG" and state.config_editor is not None:
        return state.config_editor.draft.display.preview_syntax_theme
    return state.config.display.preview_syntax_theme


def _format_tab_label(path: str) -> str:
    resolved = Path(path).expanduser()
    home = Path("~").expanduser()
    if resolved == home:
        return "~"
    if resolved == resolved.parent:
        return "/"
    return resolved.name or str(resolved)


def _has_execute_permission(entry: DirectoryEntryState) -> bool:
    """エントリが実行権限を持っているか判定."""
    if entry.permissions_mode is None:
        return False
    return bool(entry.permissions_mode & 0o111)


def select_target_paths(state: AppState) -> tuple[str, ...]:
    """Return selected paths, or the cursor path when nothing is selected."""

    return shared_target_paths(state)


def select_current_entry_for_path(
    state: AppState,
    path: str | None,
) -> DirectoryEntryState | None:
    """Return the visible current-pane entry for the given path."""

    return shared_current_entry_for_path(state, path)


def select_single_target_entry(state: AppState) -> DirectoryEntryState | None:
    """Return the visible entry when exactly one target is active."""

    return shared_single_target_entry(state)


def select_target_file_paths(state: AppState) -> tuple[str, ...]:
    """Return visible file targets, preserving selection-before-cursor behavior."""

    visible_entries = select_visible_current_entry_states(state)
    selected_files = tuple(
        entry.path
        for entry in visible_entries
        if entry.path in state.current_pane.selected_paths and entry.kind == "file"
    )
    if state.current_pane.selected_paths:
        return selected_files

    cursor_entry = select_current_entry_for_path(state, state.current_pane.cursor_path)
    if cursor_entry is None or cursor_entry.kind != "file":
        return ()
    return (cursor_entry.path,)


def select_has_visible_current_entries(state: AppState) -> bool:
    """Return whether the current pane has at least one visible entry."""

    return bool(select_visible_current_entry_states(state))


def select_visible_current_entry_states(state: AppState) -> tuple[DirectoryEntryState, ...]:
    """Return filtered and sorted raw current-pane entries."""

    return shared_visible_current_entry_states(state)


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
def _filter_hidden_entries(
    entries: tuple[DirectoryEntryState, ...],
    show_hidden: bool,
) -> tuple[DirectoryEntryState, ...]:
    if show_hidden:
        return entries
    return tuple(entry for entry in entries if not entry.hidden)


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


def compute_search_visible_window(terminal_height: int, *, extra_rows: int = 0) -> int:
    """Calculate visible command-palette items based on terminal height."""

    return max(
        MIN_SEARCH_VISIBLE_WINDOW,
        terminal_height - _SEARCH_OVERHEAD_ROWS - extra_rows,
    )


def compute_current_pane_visible_window(terminal_height: int) -> int:
    """Estimate how many current-pane rows are visible in the terminal."""

    return max(MIN_CURRENT_PANE_VISIBLE_WINDOW, terminal_height - _CURRENT_PANE_OVERHEAD_ROWS)


def _build_command_palette_items_view(
    state: AppState,
    cursor_index: int,
    title: str,
    empty_message: str | None = None,
    *,
    selected_override: bool | None = None,
) -> CommandPaletteViewState:
    """コマンドパレットのアイテムビューを構築する共通関数。"""
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
        has_more_items=len(items) > len(visible_items),
    )


def _select_file_search_window(
    state: AppState,
    results: tuple[FileSearchResultState, ...],
    cursor_index: int,
) -> tuple[tuple[tuple[int, FileSearchResultState], ...], str]:
    visible_window = compute_search_visible_window(
        state.terminal_height,
        extra_rows=_FILE_SEARCH_EXTRA_INPUT_ROWS,
    )
    target = state.command_palette.file_search.target if state.command_palette else "all"
    title = {
        "files": "Find File",
        "directories": "Find Directory",
        "all": "Find All",
    }.get(target, "Find All")
    return _select_search_window(
        results, cursor_index, title=title, visible_window=visible_window,
    )


def _select_grep_search_window(
    state: AppState,
    results: tuple[GrepSearchResultState, ...],
    cursor_index: int,
) -> tuple[tuple[tuple[int, GrepSearchResultState], ...], str]:
    visible_window = compute_search_visible_window(
        state.terminal_height,
        extra_rows=_GREP_SEARCH_EXTRA_INPUT_ROWS,
    )
    return _select_search_window(
        results, cursor_index, title="Grep", visible_window=visible_window,
    )


def _select_replace_preview_window(
    state: AppState,
    results: tuple[ReplacePreviewResultState, ...],
    cursor_index: int,
) -> tuple[tuple[tuple[int, ReplacePreviewResultState], ...], str]:
    visible_window = compute_search_visible_window(
        state.terminal_height,
        extra_rows=_GREP_SEARCH_EXTRA_INPUT_ROWS,
    )
    title = "Replace Text"
    if state.command_palette is not None and state.command_palette.replace_preview.preview_results:
        file_count = len(state.command_palette.replace_preview.preview_results)
        total_matches = state.command_palette.replace_preview.total_match_count
        title = f"Replace Text ({file_count} file(s), {total_matches} match(es))"
    return _select_search_window(results, cursor_index, title=title, visible_window=visible_window)


def _select_search_window(
    results: tuple[FileSearchResultState | GrepSearchResultState | ReplacePreviewResultState, ...],
    cursor_index: int,
    *,
    title: str,
    visible_window: int,
) -> tuple[
    tuple[
        tuple[int, FileSearchResultState | GrepSearchResultState | ReplacePreviewResultState],
        ...,
    ],
    str,
]:
    total = len(results)
    if total == 0:
        return (), title
    if total <= visible_window:
        return tuple(enumerate(results)), f"{title} (1-{total} / {total})"

    ideal_start = cursor_index - (visible_window // 2)
    start = max(0, ideal_start)
    max_start = max(0, total - visible_window)
    start = min(start, max_start)
    end = min(total, start + visible_window)
    visible_results = tuple((index, results[index]) for index in range(start, end))
    return visible_results, f"{title} ({start + 1}-{end} / {total})"


def _select_command_palette_window(
    items: tuple["CommandPaletteItem", ...],
    cursor_index: int,
    visible_window: int = COMMAND_PALETTE_VISIBLE_WINDOW,
) -> tuple[tuple[tuple[int, "CommandPaletteItem"], ...], str]:
    total = len(items)
    if total <= visible_window:
        return tuple(enumerate(items)), "Command Palette"

    ideal_start = cursor_index - (visible_window // 2)
    start = max(0, ideal_start)
    max_start = max(0, total - visible_window)
    start = min(start, max_start)
    end = min(total, start + visible_window)
    visible_items = tuple((index, items[index]) for index in range(start, end))
    return visible_items, f"Command Palette ({start + 1}-{end} / {total})"


def _build_grep_search_input_fields(
    palette: CommandPaletteState,
) -> tuple[CommandPaletteInputFieldViewState, ...]:
    return (
        CommandPaletteInputFieldViewState(
            label="Keyword",
            value=palette.grep_search.keyword or palette.query,
            placeholder="text or re:pattern",
            active=palette.grep_search.active_field == "keyword",
        ),
        CommandPaletteInputFieldViewState(
            label="Filter: Filename",
            value=palette.grep_search.filename_filter,
            placeholder="pattern or re:pattern",
            active=palette.grep_search.active_field == "filename",
        ),
        CommandPaletteInputFieldViewState(
            label="Include extensions",
            value=palette.grep_search.include_extensions,
            placeholder="e.g. py, js",
            active=palette.grep_search.active_field == "include",
        ),
        CommandPaletteInputFieldViewState(
            label="Exclude extensions",
            value=palette.grep_search.exclude_extensions,
            placeholder="e.g. log, tmp",
            active=palette.grep_search.active_field == "exclude",
        ),
    )


def _build_file_search_input_fields(
    palette: CommandPaletteState,
) -> tuple[CommandPaletteInputFieldViewState, ...]:
    target_labels = {"files": "files", "directories": "dirs", "all": "all"}
    return (
        CommandPaletteInputFieldViewState(
            label="Keyword",
            value=palette.query,
            placeholder="type a filename or re:pattern",
            active=palette.file_search.active_field == "keyword",
        ),
        CommandPaletteInputFieldViewState(
            label="Target",
            value=target_labels.get(palette.file_search.target, "all"),
            placeholder="files/dirs/all",
            active=palette.file_search.active_field == "target",
        ),
    )


def _build_replace_input_fields(
    palette: CommandPaletteState,
) -> tuple[CommandPaletteInputFieldViewState, ...]:
    return (
        CommandPaletteInputFieldViewState(
            label="Find",
            value=palette.replace_preview.find_text,
            placeholder="text or re:pattern",
            active=palette.replace_preview.active_field == "find",
        ),
        CommandPaletteInputFieldViewState(
            label="Replace",
            value=palette.replace_preview.replacement_text,
            placeholder="replacement text",
            active=palette.replace_preview.active_field == "replace",
        ),
    )


def _build_find_replace_input_fields(
    palette: CommandPaletteState,
) -> tuple[CommandPaletteInputFieldViewState, ...]:
    return (
        CommandPaletteInputFieldViewState(
            label="Filename",
            value=palette.rff.filename_query,
            placeholder="pattern or re:pattern",
            active=palette.rff.active_field == "filename",
        ),
        CommandPaletteInputFieldViewState(
            label="Find",
            value=palette.rff.find_text,
            placeholder="text or re:pattern",
            active=palette.rff.active_field == "find",
        ),
        CommandPaletteInputFieldViewState(
            label="Replace",
            value=palette.rff.replacement_text,
            placeholder="replacement text",
            active=palette.rff.active_field == "replace",
        ),
    )


def _build_grep_replace_input_fields(
    palette: CommandPaletteState,
) -> tuple[CommandPaletteInputFieldViewState, ...]:
    return (
        CommandPaletteInputFieldViewState(
            label="Keyword",
            value=palette.grf_keyword or palette.query,
            placeholder="search text",
            active=palette.grf_active_field == "keyword",
        ),
        CommandPaletteInputFieldViewState(
            label="Replace",
            value=palette.grf_replacement_text,
            placeholder="replacement text",
            active=palette.grf_active_field == "replace",
        ),
        CommandPaletteInputFieldViewState(
            label="Filter: Filename",
            value=palette.grf_filename_filter,
            placeholder="pattern or re:pattern",
            active=palette.grf_active_field == "filename",
        ),
        CommandPaletteInputFieldViewState(
            label="Include extensions",
            value=palette.grf_include_extensions,
            placeholder="e.g. py, js",
            active=palette.grf_active_field == "include",
        ),
        CommandPaletteInputFieldViewState(
            label="Exclude extensions",
            value=palette.grf_exclude_extensions,
            placeholder="e.g. log, tmp",
            active=palette.grf_active_field == "exclude",
        ),
    )


def _build_grep_replace_selected_input_fields(
    palette: CommandPaletteState,
) -> tuple[CommandPaletteInputFieldViewState, ...]:
    return (
        CommandPaletteInputFieldViewState(
            label="Keyword",
            value=palette.grs_keyword or palette.query,
            placeholder="text or re:pattern",
            active=palette.grs_active_field == "keyword",
        ),
        CommandPaletteInputFieldViewState(
            label="Replace",
            value=palette.grs_replacement_text,
            placeholder="replacement text",
            active=palette.grs_active_field == "replace",
        ),
    )


def _build_selected_files_grep_input_fields(
    palette: CommandPaletteState,
) -> tuple[CommandPaletteInputFieldViewState, ...]:
    return (
        CommandPaletteInputFieldViewState(
            label="Keyword",
            value=palette.sfg.keyword or palette.query,
            placeholder="text or re:pattern",
            active=palette.sfg.active_field == "keyword",
        ),
    )


def _select_find_replace_preview_window(
    state: AppState,
    results: tuple[ReplacePreviewResultState, ...],
    cursor_index: int,
) -> tuple[tuple[tuple[int, ReplacePreviewResultState], ...], str]:
    visible_window = compute_search_visible_window(
        state.terminal_height,
        extra_rows=3,
    )
    title = "Replace in Found Files"
    if state.command_palette is not None and state.command_palette.rff.preview_results:
        file_count = len(state.command_palette.rff.preview_results)
        total_matches = state.command_palette.rff.total_match_count
        title = f"Replace in Found Files ({file_count} file(s), {total_matches} match(es))"
    return _select_search_window(results, cursor_index, title=title, visible_window=visible_window)


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
        symlink=entry.symlink,
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
    if size_bytes < 1024:
        return f"{size_bytes} B"
    units = ("KiB", "MiB", "GiB", "TiB")
    size = float(size_bytes)
    for unit in units:
        size /= 1024
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f}{unit}"
    return f"{size:.1f}TiB"


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


def _format_permissions_detail_label(entry: DirectoryEntryState) -> str:
    if entry.permissions_mode is None:
        return ""
    permission_str = _format_permissions_label(entry.permissions_mode)
    if entry.owner and entry.group:
        return f"{permission_str} {entry.owner} {entry.group}"
    if entry.owner:
        return f"{permission_str} {entry.owner}"
    return permission_str


def _format_editor_command_value(command: str | None) -> str:
    if command is None:
        return "system default"
    if command in {"nvim", "vim", "nano", "hx", "micro", "emacs -nw", "edit"}:
        return command
    return "custom (raw config only)"


def _format_custom_editor_hint(command: str | None) -> str:
    if command is None or command in {"nvim", "vim", "nano", "hx", "micro", "emacs -nw", "edit"}:
        return "Editor presets: system default, nvim, vim, nano, hx, micro, emacs -nw, edit"
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
        return "-"
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


def _format_config_line(*, is_selected: bool, label: str, value: str) -> str:
    prefix = ">" if is_selected else " "
    return f"{prefix} {label}: {value}"


def _format_bool(value: bool) -> str:
    return "true" if value else "false"


def _select_child_syntax_theme(app_theme: str, preview_syntax_theme: str) -> str:
    return preview_syntax_theme_for_app_theme(app_theme, preview_syntax_theme)


@lru_cache(maxsize=256)
def _format_child_preview_title(path: str, truncated: bool) -> str:
    suffix = " (truncated)" if truncated else ""
    return f"Preview: {Path(path).name}{suffix}"
