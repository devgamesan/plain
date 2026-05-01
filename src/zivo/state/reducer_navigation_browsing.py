"""Browsing-focused navigation reducer handlers."""

from dataclasses import replace
from pathlib import Path

from zivo.windows_paths import comparable_path, is_windows_drives_root, is_windows_path

from .actions import (
    BeginFilterInput,
    CancelFilterInput,
    ConfirmFilterInput,
    EnterCursorDirectory,
    GoBack,
    GoForward,
    GoToHomeDirectory,
    GoToParentDirectory,
    JumpCursor,
    MoveCursor,
    MoveCursorAndSelectRange,
    MoveCursorByPage,
    ReloadDirectory,
    RequestBrowserSnapshot,
    SetCursorPath,
    SetFilterQuery,
    SetSort,
    ToggleHiddenFiles,
    ToggleSearchWorkspaceGrepDisplayMode,
)
from .effects import ReduceResult
from .models import AppState, NotificationState, resolve_parent_directory_path
from .reducer_common import (
    ReducerFn,
    browser_snapshot_invalidation_paths,
    current_entry_for_path,
    current_entry_paths,
    finalize,
    move_cursor,
    normalize_cursor_path,
    normalize_selected_paths,
    normalize_selection_anchor_path,
    select_range_paths,
    sync_child_pane,
)
from .reducer_navigation_shared import can_promote_child_pane, promote_child_pane_to_current
from .reducer_search_workspace import toggle_grep_search_workspace_display_mode
from .selectors import select_visible_current_entry_states


def _handle_begin_filter_input(
    state: AppState,
    action: BeginFilterInput,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return finalize(
        replace(
            state,
            ui_mode="FILTER",
            current_pane=replace(
                state.current_pane,
                selection_anchor_path=None,
            ),
            notification=None,
            pending_input=None,
            command_palette=None,
            pending_file_search_request_id=None,
            pending_grep_search_request_id=None,
            delete_confirmation=None,
            name_conflict=None,
            attribute_inspection=None,
        )
    )


def _handle_confirm_filter_input(
    state: AppState,
    action: ConfirmFilterInput,
    reduce_state: ReducerFn,
) -> ReduceResult:
    next_state = replace(
        state,
        ui_mode="BROWSING",
        current_pane=replace(
            state.current_pane,
            selection_anchor_path=None,
        ),
        notification=None,
    )
    visible_entries = select_visible_current_entry_states(next_state)
    cursor_path = normalize_cursor_path(visible_entries, next_state.current_pane.cursor_path)
    next_state = replace(
        next_state,
        current_pane=replace(
            next_state.current_pane,
            cursor_path=cursor_path,
        ),
    )
    return sync_child_pane(next_state, cursor_path, reduce_state)


def _handle_cancel_filter_input(
    state: AppState,
    action: CancelFilterInput,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return finalize(
        replace(
            state,
            ui_mode="BROWSING",
            filter=replace(state.filter, query="", active=False),
            current_pane=replace(
                state.current_pane,
                selection_anchor_path=None,
            ),
            notification=None,
            pending_input=None,
            command_palette=None,
            delete_confirmation=None,
            name_conflict=None,
            attribute_inspection=None,
        )
    )


def _handle_move_cursor(
    state: AppState,
    action: MoveCursor,
    reduce_state: ReducerFn,
) -> ReduceResult:
    cursor_path = move_cursor(
        state.current_pane.cursor_path,
        action.visible_paths,
        action.delta,
    )
    next_state = replace(
        state,
        current_pane=replace(
            state.current_pane,
            cursor_path=cursor_path,
            selection_anchor_path=None,
        ),
        notification=None,
    )
    return sync_child_pane(next_state, cursor_path, reduce_state)


def _handle_move_cursor_and_select_range(
    state: AppState,
    action: MoveCursorAndSelectRange,
    reduce_state: ReducerFn,
) -> ReduceResult:
    if not action.visible_paths:
        return finalize(state)
    base_cursor_path = (
        normalize_selection_anchor_path(state.current_pane.cursor_path, action.visible_paths)
        or comparable_path(action.visible_paths[0])
    )
    anchor_path = normalize_selection_anchor_path(
        state.current_pane.selection_anchor_path,
        action.visible_paths,
    )
    if anchor_path is None:
        anchor_path = base_cursor_path
    cursor_path = move_cursor(base_cursor_path, action.visible_paths, action.delta)
    if cursor_path is None:
        return finalize(state)
    next_state = replace(
        state,
        current_pane=replace(
            state.current_pane,
            cursor_path=cursor_path,
            selected_paths=select_range_paths(
                anchor_path,
                cursor_path,
                action.visible_paths,
            ),
            selection_anchor_path=anchor_path,
        ),
        notification=None,
    )
    return sync_child_pane(next_state, cursor_path, reduce_state)


def _handle_jump_cursor(
    state: AppState,
    action: JumpCursor,
    reduce_state: ReducerFn,
) -> ReduceResult:
    if not action.visible_paths:
        return finalize(state)
    cursor_path = (
        comparable_path(action.visible_paths[0])
        if action.position == "start"
        else comparable_path(action.visible_paths[-1])
    )
    next_state = replace(
        state,
        current_pane=replace(
            state.current_pane,
            cursor_path=cursor_path,
            selection_anchor_path=None,
        ),
        notification=None,
    )
    return sync_child_pane(next_state, cursor_path, reduce_state)


def _handle_move_cursor_by_page(
    state: AppState,
    action: MoveCursorByPage,
    reduce_state: ReducerFn,
) -> ReduceResult:
    if not action.visible_paths:
        return finalize(state)
    current_cursor_path = normalize_selection_anchor_path(
        state.current_pane.cursor_path,
        action.visible_paths,
    )
    current_index = (
        action.visible_paths.index(current_cursor_path) if current_cursor_path is not None else 0
    )
    if action.direction == "up":
        new_index = max(0, current_index - action.page_size)
    else:
        new_index = min(len(action.visible_paths) - 1, current_index + action.page_size)
    cursor_path = comparable_path(action.visible_paths[new_index])
    next_state = replace(
        state,
        current_pane=replace(
            state.current_pane,
            cursor_path=cursor_path,
            selection_anchor_path=None,
        ),
        notification=None,
    )
    return sync_child_pane(next_state, cursor_path, reduce_state)


def _handle_set_cursor_path(
    state: AppState,
    action: SetCursorPath,
    reduce_state: ReducerFn,
) -> ReduceResult:
    if action.path is not None and action.path not in current_entry_paths(state):
        return finalize(state)
    next_state = replace(
        state,
        current_pane=replace(
            state.current_pane,
            cursor_path=comparable_path(action.path),
            selection_anchor_path=None,
        ),
        notification=None,
    )
    return sync_child_pane(next_state, action.path, reduce_state)


def _handle_enter_cursor_directory(
    state: AppState,
    action: EnterCursorDirectory,
    reduce_state: ReducerFn,
) -> ReduceResult:
    entry = current_entry_for_path(state, state.current_pane.cursor_path)
    if entry is None or entry.kind != "dir":
        return finalize(state)
    if can_promote_child_pane(state, entry.path):
        next_state = promote_child_pane_to_current(state, entry.path)
        return sync_child_pane(next_state, next_state.current_pane.cursor_path, reduce_state)
    return reduce_state(
        state,
        RequestBrowserSnapshot(entry.path, blocking=True),
    )


def _handle_go_to_parent_directory(
    state: AppState,
    action: GoToParentDirectory,
    reduce_state: ReducerFn,
) -> ReduceResult:
    if is_windows_drives_root(state.current_path):
        return finalize(state)
    if is_windows_path(state.current_path):
        _, parent_path = resolve_parent_directory_path(state.current_path)
        if parent_path is None:
            return finalize(state)
    else:
        parent_path = str(Path(state.current_path).parent)
    return reduce_state(
        state,
        RequestBrowserSnapshot(
            parent_path,
            cursor_path=state.current_path,
            blocking=True,
        ),
    )


def _handle_go_to_home_directory(
    state: AppState,
    action: GoToHomeDirectory,
    reduce_state: ReducerFn,
) -> ReduceResult:
    home_path = str(Path("~").expanduser().resolve())
    return reduce_state(
        state,
        RequestBrowserSnapshot(home_path, blocking=True),
    )


def _handle_go_back(
    state: AppState,
    action: GoBack,
    reduce_state: ReducerFn,
) -> ReduceResult:
    if not state.history.back:
        return finalize(state)
    return reduce_state(
        state,
        RequestBrowserSnapshot(state.history.back[-1], blocking=True),
    )


def _handle_go_forward(
    state: AppState,
    action: GoForward,
    reduce_state: ReducerFn,
) -> ReduceResult:
    if not state.history.forward:
        return finalize(state)
    return reduce_state(
        state,
        RequestBrowserSnapshot(state.history.forward[0], blocking=True),
    )


def _handle_reload_directory(
    state: AppState,
    action: ReloadDirectory,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return reduce_state(
        state,
        RequestBrowserSnapshot(
            state.current_path,
            cursor_path=state.current_pane.cursor_path,
            blocking=True,
            invalidate_paths=browser_snapshot_invalidation_paths(
                state.current_path,
                state.current_pane.cursor_path,
            ),
        ),
    )


def _handle_set_filter_query(
    state: AppState,
    action: SetFilterQuery,
    reduce_state: ReducerFn,
) -> ReduceResult:
    active = bool(action.query) if action.active is None else action.active
    next_state = replace(
        state,
        filter=replace(state.filter, query=action.query, active=active),
    )
    visible_paths = tuple(
        entry.path for entry in select_visible_current_entry_states(next_state)
    )
    return finalize(
        replace(
            next_state,
            current_pane=replace(
                next_state.current_pane,
                selection_anchor_path=normalize_selection_anchor_path(
                    state.current_pane.selection_anchor_path,
                    visible_paths,
                ),
            ),
        )
    )


def _handle_toggle_hidden_files(
    state: AppState,
    action: ToggleHiddenFiles,
    reduce_state: ReducerFn,
) -> ReduceResult:
    next_state = replace(
        state,
        show_hidden=not state.show_hidden,
        notification=NotificationState(
            level="info",
            message="Hidden files shown" if not state.show_hidden else "Hidden files hidden",
        ),
    )
    visible_entries = select_visible_current_entry_states(next_state)
    visible_paths = tuple(entry.path for entry in visible_entries)
    selected_paths = normalize_selected_paths(
        state.current_pane.selected_paths,
        visible_entries,
    )
    cursor_path = normalize_cursor_path(visible_entries, state.current_pane.cursor_path)
    next_state = replace(
        next_state,
        current_pane=replace(
            next_state.current_pane,
            cursor_path=cursor_path,
            selected_paths=selected_paths,
            selection_anchor_path=normalize_selection_anchor_path(
                state.current_pane.selection_anchor_path,
                visible_paths,
            ),
        ),
    )
    return sync_child_pane(next_state, cursor_path, reduce_state)


def _handle_set_sort(
    state: AppState,
    action: SetSort,
    reduce_state: ReducerFn,
) -> ReduceResult:
    directories_first = state.sort.directories_first
    if action.directories_first is not None:
        directories_first = action.directories_first
    next_state = replace(
        state,
        sort=replace(
            state.sort,
            field=action.field,
            descending=action.descending,
            directories_first=directories_first,
        ),
    )
    visible_entries = select_visible_current_entry_states(next_state)
    visible_paths = tuple(entry.path for entry in visible_entries)
    cursor_path = normalize_cursor_path(
        visible_entries,
        state.current_pane.cursor_path,
    )
    next_state = replace(
        next_state,
        current_pane=replace(
            next_state.current_pane,
            cursor_path=cursor_path,
            selection_anchor_path=normalize_selection_anchor_path(
                state.current_pane.selection_anchor_path,
                visible_paths,
            ),
        ),
    )
    return sync_child_pane(next_state, cursor_path, reduce_state)


def _handle_toggle_search_workspace_grep_display_mode(
    state: AppState,
    action: ToggleSearchWorkspaceGrepDisplayMode,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return toggle_grep_search_workspace_display_mode(state, reduce_state)


BROWSING_NAVIGATION_HANDLERS = {
    BeginFilterInput: _handle_begin_filter_input,
    ConfirmFilterInput: _handle_confirm_filter_input,
    CancelFilterInput: _handle_cancel_filter_input,
    MoveCursor: _handle_move_cursor,
    MoveCursorAndSelectRange: _handle_move_cursor_and_select_range,
    JumpCursor: _handle_jump_cursor,
    MoveCursorByPage: _handle_move_cursor_by_page,
    SetCursorPath: _handle_set_cursor_path,
    EnterCursorDirectory: _handle_enter_cursor_directory,
    GoToParentDirectory: _handle_go_to_parent_directory,
    GoToHomeDirectory: _handle_go_to_home_directory,
    GoBack: _handle_go_back,
    GoForward: _handle_go_forward,
    ReloadDirectory: _handle_reload_directory,
    SetFilterQuery: _handle_set_filter_query,
    ToggleHiddenFiles: _handle_toggle_hidden_files,
    SetSort: _handle_set_sort,
    ToggleSearchWorkspaceGrepDisplayMode: _handle_toggle_search_workspace_grep_display_mode,
}
