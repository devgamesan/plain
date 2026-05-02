"""Navigation-focused command palette reducers."""

from dataclasses import replace
from pathlib import Path
from typing import Callable

from zivo.windows_paths import is_windows_drives_root, is_windows_path

from .command_palette import get_command_palette_items, normalize_command_palette_cursor
from .effects import ReduceResult
from .models import AppState
from .reducer_common import (
    ReducerFn,
    expand_and_validate_path,
    finalize,
    list_matching_directory_paths,
)
from .reducer_palette_shared import (
    enter_palette,
    notify,
    request_palette_snapshot,
    restore_browsing_from_palette,
)
from .reducer_transfer import request_transfer_pane_snapshot


def handle_begin_history_search(state: AppState) -> ReduceResult:
    if state.layout_mode == "transfer":
        transfer = (
            state.transfer_left
            if state.active_transfer_pane == "left"
            else state.transfer_right
        )
        if transfer is None:
            return finalize(state)
        history_items = tuple(dict.fromkeys(transfer.history.visited_all))
    else:
        history_items = tuple(dict.fromkeys(state.history.visited_all))
    return finalize(enter_palette(state, source="history", history_results=history_items))


def handle_begin_bookmark_search(state: AppState) -> ReduceResult:
    return finalize(enter_palette(state, source="bookmarks"))


def handle_set_go_to_path_query(state: AppState, next_palette, query: str) -> ReduceResult:
    if state.layout_mode == "transfer":
        active_pane = (
            state.transfer_left
            if state.active_transfer_pane == "left"
            else state.transfer_right
        )
        base_path = active_pane.current_path
    else:
        base_path = state.current_path
    matches = list_matching_directory_paths(query, base_path)
    has_trailing_separator = query.endswith(("/", "\\"))
    return finalize(
        replace(
            state,
            command_palette=replace(
                next_palette,
                history_and_navigation=replace(
                    next_palette.history_and_navigation,
                    go_to_path_candidates=matches,
                    go_to_path_selection_active=not has_trailing_separator,
                ),
            ),
        )
    )


def handle_submit_history_palette(state: AppState, reduce_state: ReducerFn) -> ReduceResult:
    items = get_command_palette_items(state)
    if not items:
        return notify(state, level="warning", message="No directory history")
    selected_item = items[
        normalize_command_palette_cursor(state, state.command_palette.cursor_index)
    ]
    if state.layout_mode == "transfer":
        next_state = restore_browsing_from_palette(state)
        return request_transfer_pane_snapshot(
            next_state,
            next_state.active_transfer_pane,
            selected_item.path,
            invalidate_paths=(),
        )
    return request_palette_snapshot(state, reduce_state, path=selected_item.path)


def handle_submit_bookmarks_palette(state: AppState, reduce_state: ReducerFn) -> ReduceResult:
    items = get_command_palette_items(state)
    if not items:
        return notify(state, level="warning", message="No bookmarks")
    selected_item = items[
        normalize_command_palette_cursor(state, state.command_palette.cursor_index)
    ]
    if selected_item.path is None or not Path(selected_item.path).is_dir():
        return notify(
            state,
            level="error",
            message="Bookmarked path does not exist or is not a directory",
        )
    if state.layout_mode == "transfer":
        return request_transfer_pane_snapshot(
            state,
            state.active_transfer_pane,
            selected_item.path,
            invalidate_paths=(),
        )
    return request_palette_snapshot(state, reduce_state, path=selected_item.path)


def handle_submit_go_to_path_palette(state: AppState, reduce_state: ReducerFn) -> ReduceResult:
    items = get_command_palette_items(state)
    expanded_path = None
    if items and state.command_palette.history_and_navigation.go_to_path_selection_active:
        expanded_path = items[
            normalize_command_palette_cursor(state, state.command_palette.cursor_index)
        ].path
    if state.layout_mode == "transfer":
        active_pane = (
            state.transfer_left
            if state.active_transfer_pane == "left"
            else state.transfer_right
        )
        if expanded_path is None:
            expanded_path = expand_and_validate_path(
                state.command_palette.query, active_pane.current_path
            )
        if expanded_path is None:
            return notify(state, level="error", message="Path does not exist or is not a directory")
        next_state = restore_browsing_from_palette(state)
        return request_transfer_pane_snapshot(
            next_state,
            state.active_transfer_pane,
            expanded_path,
            invalidate_paths=(),
        )
    if expanded_path is None:
        expanded_path = expand_and_validate_path(state.command_palette.query, state.current_path)
    if expanded_path is None:
        return notify(state, level="error", message="Path does not exist or is not a directory")
    return request_palette_snapshot(state, reduce_state, path=expanded_path)


def handle_begin_go_to_path(
    state: AppState,
    list_windows_drive_paths_fn: Callable[[], tuple[str, ...]],
) -> ReduceResult:
    next_state = enter_palette(state, source="go_to_path")
    if is_windows_drives_root(state.current_path) or is_windows_path(state.current_path):
        next_state = replace(
            next_state,
            command_palette=replace(
                next_state.command_palette,
                history_and_navigation=replace(
                    next_state.command_palette.history_and_navigation,
                    go_to_path_candidates=list_windows_drive_paths_fn(),
                ),
            ),
        )
    return finalize(next_state)
