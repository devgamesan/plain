"""Directory-size and child-pane synchronization helpers."""

from dataclasses import replace

from zivo.archive_utils import is_supported_archive_path

from .actions import RequestDirectorySizes
from .effects import Effect, LoadChildPaneSnapshotEffect, ReduceResult
from .entry_state_helpers import current_entry_for_path, visible_current_entry_states
from .models import DirectoryEntryState, DirectorySizeCacheEntry, PaneState
from .reducer_requests import ReducerFn


def maybe_request_directory_sizes(
    state,
    reduce_state: ReducerFn,
    *effects: Effect,
) -> ReduceResult:
    active_target_paths = directory_size_target_paths(state)
    if not active_target_paths:
        return ReduceResult(state=state, effects=effects)

    cache_by_path = directory_size_cache_by_path(state.directory_size_cache)
    pending_paths = tuple(
        path
        for path in active_target_paths
        if cache_by_path.get(path) is not None and cache_by_path[path].status == "pending"
    )
    missing_paths = tuple(path for path in active_target_paths if cache_by_path.get(path) is None)

    if not missing_paths:
        if pending_paths and state.pending_directory_size_request_id is None:
            return reduce_state(state, RequestDirectorySizes(pending_paths))
        return ReduceResult(state=state, effects=effects)

    request_paths = tuple(dict.fromkeys((*pending_paths, *missing_paths)))
    result = reduce_state(state, RequestDirectorySizes(request_paths))
    return ReduceResult(state=result.state, effects=(*effects, *result.effects))


def directory_size_target_paths(state) -> tuple[str, ...]:
    if not state.config.display.show_directory_sizes and state.sort.field != "size":
        return ()

    return tuple(
        dict.fromkeys(
            visible_directory_paths(
                visible_current_entry_states(state),
                show_hidden=True,
            )
        )
    )


def visible_directory_paths(
    entries: tuple[DirectoryEntryState, ...],
    show_hidden: bool,
) -> tuple[str, ...]:
    return tuple(
        entry.path
        for entry in entries
        if entry.kind == "dir" and (show_hidden or not entry.hidden)
    )


def directory_size_cache_by_path(
    entries: tuple[DirectorySizeCacheEntry, ...],
) -> dict[str, DirectorySizeCacheEntry]:
    return {entry.path: entry for entry in entries}


def upsert_directory_size_entries(
    current_entries: tuple[DirectorySizeCacheEntry, ...],
    new_entries: tuple[DirectorySizeCacheEntry, ...],
) -> tuple[DirectorySizeCacheEntry, ...]:
    cache_by_path = directory_size_cache_by_path(current_entries)
    for entry in new_entries:
        cache_by_path[entry.path] = entry
    return tuple(sorted(cache_by_path.values(), key=lambda entry: entry.path))


def sync_child_pane(
    state,
    cursor_path: str | None,
    reduce_state: ReducerFn,
) -> ReduceResult:
    entry = current_entry_for_path(state, cursor_path)
    if entry is None:
        next_state = replace(
            state,
            child_pane=PaneState(directory_path=state.current_path, entries=()),
            pending_child_pane_request_id=None,
        )
        return maybe_request_directory_sizes(next_state, reduce_state)

    if entry.kind != "dir" and not is_supported_archive_path(entry.path):
        if not state.config.display.show_preview:
            next_child_pane = PaneState(directory_path=state.current_path, entries=())
            if (
                state.pending_child_pane_request_id is None
                and state.child_pane == next_child_pane
            ):
                return maybe_request_directory_sizes(state, reduce_state)
            next_state = replace(
                state,
                child_pane=next_child_pane,
                pending_child_pane_request_id=None,
            )
            return maybe_request_directory_sizes(next_state, reduce_state)

    if state.pending_child_pane_request_id is None and _child_pane_matches_entry(
        state.child_pane,
        entry,
    ):
        return maybe_request_directory_sizes(state, reduce_state)

    request_id = state.next_request_id
    next_state = replace(
        state,
        pending_child_pane_request_id=request_id,
        next_request_id=request_id + 1,
    )
    return maybe_request_directory_sizes(
        next_state,
        reduce_state,
        LoadChildPaneSnapshotEffect(
            request_id=request_id,
            current_path=state.current_path,
            cursor_path=entry.path,
            preview_max_bytes=state.config.display.preview_max_kib * 1024,
        ),
    )


def normalize_child_pane_for_display(
    current_path: str,
    child_pane: PaneState,
    *,
    show_preview: bool,
) -> PaneState:
    if show_preview or child_pane.mode != "preview":
        return child_pane
    return PaneState(directory_path=current_path, entries=())


def _child_pane_matches_entry(
    child_pane: PaneState,
    entry: DirectoryEntryState,
) -> bool:
    if entry.kind == "dir" or is_supported_archive_path(entry.path):
        return child_pane.mode == "entries" and child_pane.directory_path == entry.path
    return (
        child_pane.mode == "preview"
        and child_pane.preview_path == entry.path
        and child_pane.preview_title is None
        and child_pane.preview_start_line is None
        and child_pane.preview_highlight_line is None
    )
