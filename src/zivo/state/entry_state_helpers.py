"""Shared helpers for visible entries and target resolution."""

from dataclasses import replace
from functools import lru_cache

from .models import AppState, DirectoryEntryState, DirectorySizeCacheEntry, SortState


@lru_cache(maxsize=256)
def _build_entry_index(entries: tuple[DirectoryEntryState, ...]) -> dict[str, int]:
    """Build a path-to-index mapping for entry lookup."""
    return {entry.path: index for index, entry in enumerate(entries)}


def visible_current_entry_states(state: AppState) -> tuple[DirectoryEntryState, ...]:
    """Return filtered and sorted raw current-pane entries."""

    return select_visible_entry_states(
        state.current_pane.entries,
        state.directory_size_cache,
        state.show_hidden,
        state.filter.query,
        state.filter.active,
        state.sort,
    )


def target_paths(state: AppState) -> tuple[str, ...]:
    """Return selected paths, or the cursor path when nothing is selected."""

    visible_entries = visible_current_entry_states(state)
    selected_paths = tuple(
        entry.path
        for entry in visible_entries
        if entry.path in state.current_pane.selected_paths
    )
    if selected_paths:
        return selected_paths

    cursor_entry = current_entry_for_path(state, state.current_pane.cursor_path)
    if cursor_entry is None:
        return ()
    return (cursor_entry.path,)


def current_entry_for_path(
    state: AppState,
    path: str | None,
) -> DirectoryEntryState | None:
    """Return the visible current-pane entry for the given path."""

    if path is None:
        return None
    visible_entries = visible_current_entry_states(state)
    index = _build_entry_index(visible_entries).get(path)
    if index is None:
        return None
    return visible_entries[index]


def single_target_entry(state: AppState) -> DirectoryEntryState | None:
    """Return the visible entry when exactly one target is active."""

    active_target_paths = target_paths(state)
    if len(active_target_paths) != 1:
        return None
    return current_entry_for_path(state, active_target_paths[0])


@lru_cache(maxsize=256)
def select_visible_entry_states(
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


def _directory_size_cache_by_path(
    entries: tuple[DirectorySizeCacheEntry, ...],
) -> dict[str, DirectorySizeCacheEntry]:
    return {entry.path: entry for entry in entries}
