"""Navigation and snapshot reducer handlers."""

from dataclasses import replace
from pathlib import Path
from typing import Callable

from .actions import (
    Action,
    ActivateNextTab,
    ActivatePreviousTab,
    BeginFilterInput,
    BrowserSnapshotFailed,
    BrowserSnapshotLoaded,
    CancelFilterInput,
    ChildPaneSnapshotFailed,
    ChildPaneSnapshotLoaded,
    CloseCurrentTab,
    ConfirmFilterInput,
    CurrentPaneSnapshotLoaded,
    DirectorySizesFailed,
    DirectorySizesLoaded,
    EnterCursorDirectory,
    GoBack,
    GoForward,
    GoToHomeDirectory,
    GoToParentDirectory,
    JumpCursor,
    MoveCursor,
    MoveCursorAndSelectRange,
    MoveCursorByPage,
    OpenNewTab,
    ParentChildSnapshotFailed,
    ParentChildSnapshotLoaded,
    ReloadDirectory,
    RequestBrowserSnapshot,
    RequestDirectorySizes,
    SetCursorPath,
    SetFilterQuery,
    SetSort,
    ToggleHiddenFiles,
)
from .effects import (
    LoadBrowserSnapshotEffect,
    LoadCurrentPaneEffect,
    LoadParentChildEffect,
    ReduceResult,
    RunDirectorySizeEffect,
)
from .models import (
    AppState,
    BrowserTabState,
    CurrentPaneDeltaState,
    DirectorySizeCacheEntry,
    DirectorySizeDeltaState,
    FilterState,
    HistoryState,
    NotificationState,
    PaneState,
    browser_tab_from_app_state,
    select_browser_tabs,
)
from .reducer_common import (
    ReducerFn,
    browser_snapshot_invalidation_paths,
    build_history_after_snapshot_load,
    current_entry_for_path,
    current_entry_paths,
    finalize,
    maybe_request_directory_sizes,
    move_cursor,
    normalize_child_pane_for_display,
    normalize_cursor_path,
    normalize_selected_paths,
    normalize_selection_anchor_path,
    select_range_paths,
    sync_child_pane,
    upsert_directory_size_entries,
)
from .selectors import select_visible_current_entry_states


def _replace_browser_tab(
    state: AppState,
    index: int,
    tab: BrowserTabState,
) -> AppState:
    tabs = list(select_browser_tabs(state))
    tabs[index] = tab
    next_state = replace(state, browser_tabs=tuple(tabs))
    if index == state.active_tab_index:
        return _load_browser_tab_from_tabs(next_state, tuple(tabs), index)
    return next_state


def _load_browser_tab_from_tabs(
    state: AppState,
    tabs: tuple[BrowserTabState, ...],
    index: int,
) -> AppState:
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


def _activate_tab(
    state: AppState,
    index: int,
    reduce_state: ReducerFn,
) -> ReduceResult:
    tabs = select_browser_tabs(state)
    return maybe_request_directory_sizes(
        _load_browser_tab_from_tabs(state, tabs, index),
        reduce_state,
    )


def _build_new_tab_state(state: AppState) -> BrowserTabState:
    active_tab = browser_tab_from_app_state(state)
    return replace(
        active_tab,
        current_pane=replace(
            active_tab.current_pane,
            selected_paths=frozenset(),
            selection_anchor_path=None,
        ),
        filter=FilterState(),
        history=HistoryState(visited_all=(active_tab.current_path,)),
        current_pane_delta=CurrentPaneDeltaState(),
        pending_browser_snapshot_request_id=None,
        pending_child_pane_request_id=None,
        layout_mode="browser",
        active_transfer_pane="left",
        transfer_left=None,
        transfer_right=None,
    )


def _find_browser_snapshot_tab_index(state: AppState, request_id: int) -> int | None:
    for index, tab in enumerate(select_browser_tabs(state)):
        if tab.pending_browser_snapshot_request_id == request_id:
            return index
    return None


def _find_child_pane_snapshot_tab_index(state: AppState, request_id: int) -> int | None:
    for index, tab in enumerate(select_browser_tabs(state)):
        if tab.pending_child_pane_request_id == request_id:
            return index
    return None


def _apply_loaded_snapshot_to_tab(
    state: AppState,
    tab: BrowserTabState,
    action: BrowserSnapshotLoaded,
) -> BrowserTabState:
    selected_paths = frozenset()
    selection_anchor_path = None
    if action.snapshot.current_path == tab.current_path:
        selected_paths = normalize_selected_paths(
            tab.current_pane.selected_paths,
            action.snapshot.current_pane.entries,
        )
        selection_anchor_path = normalize_selection_anchor_path(
            tab.current_pane.selection_anchor_path,
            tuple(entry.path for entry in action.snapshot.current_pane.entries),
        )

    history_source = replace(
        state,
        current_path=tab.current_path,
        history=tab.history,
    )
    return replace(
        tab,
        current_path=action.snapshot.current_path,
        parent_pane=action.snapshot.parent_pane,
        current_pane=replace(
            action.snapshot.current_pane,
            selected_paths=selected_paths,
            selection_anchor_path=selection_anchor_path,
        ),
        child_pane=normalize_child_pane_for_display(
            action.snapshot.current_path,
            action.snapshot.child_pane,
            enable_text_preview=state.config.display.enable_text_preview,
            enable_pdf_preview=state.config.display.enable_pdf_preview,
            enable_office_preview=state.config.display.enable_office_preview,
        ),
        filter=FilterState() if action.snapshot.current_path != tab.current_path else tab.filter,
        history=build_history_after_snapshot_load(history_source, action.snapshot.current_path),
        current_pane_delta=CurrentPaneDeltaState(),
        pending_browser_snapshot_request_id=None,
        pending_child_pane_request_id=None,
    )


def _can_promote_child_pane(
    state: AppState,
    entry_path: str,
) -> bool:
    return (
        not state.filter.active
        and state.pending_child_pane_request_id is None
        and state.child_pane.mode == "entries"
        and state.child_pane.directory_path == entry_path
    )


def _promote_child_pane_to_current(
    state: AppState,
    path: str,
) -> AppState:
    promoted_entries = state.child_pane.entries
    promoted_cursor_path = normalize_cursor_path(promoted_entries, None)
    return replace(
        state,
        current_path=path,
        parent_pane=PaneState(
            directory_path=state.current_path,
            entries=state.current_pane.entries,
            cursor_path=path,
        ),
        current_pane=PaneState(
            directory_path=path,
            entries=promoted_entries,
            cursor_path=promoted_cursor_path,
        ),
        child_pane=PaneState(directory_path=path, entries=()),
        filter=FilterState(),
        notification=None,
        command_palette=None,
        directory_size_cache=(),
        pending_browser_snapshot_request_id=None,
        pending_child_pane_request_id=None,
        pending_directory_size_request_id=None,
        ui_mode="BROWSING",
        history=build_history_after_snapshot_load(state, path),
    )


# ---------------------------------------------------------------------------
# Individual handler functions
# ---------------------------------------------------------------------------


def _handle_open_new_tab(
    state: AppState,
    action: OpenNewTab,
    reduce_state: ReducerFn,
) -> ReduceResult:
    tabs = list(select_browser_tabs(state))
    insert_index = state.active_tab_index + 1
    tabs.insert(insert_index, _build_new_tab_state(state))
    next_state = _load_browser_tab_from_tabs(
        replace(state, notification=None),
        tuple(tabs),
        insert_index,
    )
    return maybe_request_directory_sizes(next_state, reduce_state)


def _handle_activate_next_tab(
    state: AppState,
    action: ActivateNextTab,
    reduce_state: ReducerFn,
) -> ReduceResult:
    tabs = select_browser_tabs(state)
    if len(tabs) <= 1:
        return finalize(state)
    return _activate_tab(state, (state.active_tab_index + 1) % len(tabs), reduce_state)


def _handle_activate_previous_tab(
    state: AppState,
    action: ActivatePreviousTab,
    reduce_state: ReducerFn,
) -> ReduceResult:
    tabs = select_browser_tabs(state)
    if len(tabs) <= 1:
        return finalize(state)
    return _activate_tab(state, (state.active_tab_index - 1) % len(tabs), reduce_state)


def _handle_close_current_tab(
    state: AppState,
    action: CloseCurrentTab,
    reduce_state: ReducerFn,
) -> ReduceResult:
    tabs = list(select_browser_tabs(state))
    if len(tabs) <= 1:
        return finalize(
            replace(
                state,
                notification=NotificationState(
                    level="warning",
                    message="Cannot close the last tab",
                ),
            )
        )

    del tabs[state.active_tab_index]
    next_index = min(state.active_tab_index, len(tabs) - 1)
    next_state = _load_browser_tab_from_tabs(
        replace(state, notification=None),
        tuple(tabs),
        next_index,
    )
    return maybe_request_directory_sizes(next_state, reduce_state)


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
    return finalize(
        replace(
            state,
            ui_mode="BROWSING",
            current_pane=replace(
                state.current_pane,
                selection_anchor_path=None,
            ),
            notification=None,
        )
    )


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
        state.current_pane.cursor_path
        if state.current_pane.cursor_path in action.visible_paths
        else action.visible_paths[0]
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
        action.visible_paths[0]
        if action.position == "start"
        else action.visible_paths[-1]
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
    current_index = (
        action.visible_paths.index(state.current_pane.cursor_path)
        if state.current_pane.cursor_path in action.visible_paths
        else 0
    )
    if action.direction == "up":
        new_index = max(0, current_index - action.page_size)
    else:  # direction == "down"
        new_index = min(len(action.visible_paths) - 1, current_index + action.page_size)
    cursor_path = action.visible_paths[new_index]
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
            cursor_path=action.path,
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
    if _can_promote_child_pane(state, entry.path):
        next_state = _promote_child_pane_to_current(state, entry.path)
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


def _handle_request_browser_snapshot(
    state: AppState,
    action: RequestBrowserSnapshot,
    reduce_state: ReducerFn,
) -> ReduceResult:
    request_id = state.next_request_id
    next_state = replace(
        state,
        notification=None,
        command_palette=None,
        directory_size_cache=(),
        directory_size_delta=replace(state.directory_size_delta, changed_paths=()),
        pending_browser_snapshot_request_id=request_id,
        pending_child_pane_request_id=None,
        pending_directory_size_request_id=None,
        next_request_id=request_id + 1,
        ui_mode="BUSY" if action.blocking else state.ui_mode,
    )

    # Use progressive loading if enabled and not blocking
    if getattr(action, "progressive", True) and not action.blocking:
        return finalize(
            next_state,
            LoadCurrentPaneEffect(
                request_id=request_id,
                path=action.path,
                cursor_path=action.cursor_path,
                invalidate_paths=action.invalidate_paths,
            ),
        )

    # Use legacy synchronous loading for blocking mode
    return finalize(
        next_state,
        LoadBrowserSnapshotEffect(
            request_id=request_id,
            path=action.path,
            cursor_path=action.cursor_path,
            blocking=action.blocking,
            invalidate_paths=action.invalidate_paths,
            enable_pdf_preview=state.config.display.enable_pdf_preview,
            enable_office_preview=state.config.display.enable_office_preview,
        ),
    )


def _handle_request_directory_sizes(
    state: AppState,
    action: RequestDirectorySizes,
    reduce_state: ReducerFn,
) -> ReduceResult:
    unique_paths = tuple(dict.fromkeys(action.paths))
    if not unique_paths:
        return finalize(state)
    request_id = state.next_request_id
    next_state = replace(
        state,
        directory_size_cache=upsert_directory_size_entries(
            state.directory_size_cache,
            tuple(
                DirectorySizeCacheEntry(path=path, status="pending")
                for path in unique_paths
            ),
        ),
        pending_directory_size_request_id=request_id,
        next_request_id=request_id + 1,
    )
    return finalize(
        next_state,
        RunDirectorySizeEffect(request_id=request_id, paths=unique_paths),
    )


def _handle_browser_snapshot_loaded(
    state: AppState,
    action: BrowserSnapshotLoaded,
    reduce_state: ReducerFn,
) -> ReduceResult:
    tab_index = _find_browser_snapshot_tab_index(state, action.request_id)
    if tab_index is None:
        return finalize(state)
    tab = select_browser_tabs(state)[tab_index]
    next_state = _replace_browser_tab(
        state,
        tab_index,
        _apply_loaded_snapshot_to_tab(state, tab, action),
    )
    if tab_index != state.active_tab_index:
        return finalize(replace(next_state, post_reload_notification=None))
    next_state = replace(
        next_state,
        notification=state.post_reload_notification,
        post_reload_notification=None,
        ui_mode="BROWSING" if action.blocking else state.ui_mode,
    )
    return maybe_request_directory_sizes(next_state, reduce_state)


def _handle_current_pane_loaded(
    state: AppState,
    action: CurrentPaneSnapshotLoaded,
    reduce_state: ReducerFn,
) -> ReduceResult:
    """Handle Phase 1 of progressive loading: current pane loaded."""
    tab_index = _find_browser_snapshot_tab_index(state, action.request_id)
    if tab_index is None:
        return finalize(state)

    tab = select_browser_tabs(state)[tab_index]
    next_tab = replace(
        tab,
        current_path=action.current_path,
        current_pane=action.current_pane,
        parent_pane=action.parent_pane,
        parent_pane_loading=True,
        child_pane_loading=True,
    )
    next_state = _replace_browser_tab(state, tab_index, next_tab)

    if tab_index == state.active_tab_index:
        next_state = replace(
            next_state,
            notification=state.post_reload_notification,
            post_reload_notification=None,
        )

    # Trigger Phase 2: load parent and child panes
    return finalize(
        next_state,
        LoadParentChildEffect(
            request_id=action.request_id,
            path=action.current_path,
            cursor_path=action.current_pane.cursor_path,
            current_pane=action.current_pane,
            enable_text_preview=state.config.display.enable_text_preview,
            enable_pdf_preview=state.config.display.enable_pdf_preview,
            enable_office_preview=state.config.display.enable_office_preview,
        ),
    )


def _handle_parent_child_loaded(
    state: AppState,
    action: ParentChildSnapshotLoaded,
    reduce_state: ReducerFn,
) -> ReduceResult:
    """Handle Phase 2 of progressive loading: parent and child panes loaded."""
    tab_index = _find_browser_snapshot_tab_index(state, action.request_id)
    if tab_index is None:
        return finalize(state)

    tab = select_browser_tabs(state)[tab_index]
    next_tab = replace(
        tab,
        parent_pane=action.parent_pane,
        child_pane=action.child_pane,
        parent_pane_loading=False,
        child_pane_loading=False,
    )
    next_state = _replace_browser_tab(state, tab_index, next_tab)

    if tab_index != state.active_tab_index:
        return finalize(replace(next_state, post_reload_notification=None))

    next_state = replace(
        next_state,
        notification=state.post_reload_notification,
        post_reload_notification=None,
        pending_browser_snapshot_request_id=None,
    )

    # Request directory sizes for the new entries
    return maybe_request_directory_sizes(next_state, reduce_state)


def _handle_parent_child_failed(
    state: AppState,
    action: ParentChildSnapshotFailed,
    reduce_state: ReducerFn,
) -> ReduceResult:
    """Handle Phase 2 failure: clear loading flags and show error."""
    tab_index = _find_browser_snapshot_tab_index(state, action.request_id)
    if tab_index is None:
        return finalize(state)

    tab = replace(
        select_browser_tabs(state)[tab_index],
        parent_pane_loading=False,
        child_pane_loading=False,
    )
    next_state = _replace_browser_tab(state, tab_index, tab)

    if tab_index != state.active_tab_index:
        return finalize(replace(next_state, post_reload_notification=None))

    return finalize(
        replace(
            next_state,
            notification=NotificationState(level="error", message=action.message),
            post_reload_notification=None,
            pending_browser_snapshot_request_id=None,
        )
    )


def _handle_browser_snapshot_failed(
    state: AppState,
    action: BrowserSnapshotFailed,
    reduce_state: ReducerFn,
) -> ReduceResult:
    tab_index = _find_browser_snapshot_tab_index(state, action.request_id)
    if tab_index is None:
        return finalize(state)
    tab = replace(
        select_browser_tabs(state)[tab_index],
        pending_browser_snapshot_request_id=None,
        pending_child_pane_request_id=None,
    )
    next_state = _replace_browser_tab(state, tab_index, tab)
    if tab_index != state.active_tab_index:
        return finalize(replace(next_state, post_reload_notification=None))
    return finalize(
        replace(
            next_state,
            notification=NotificationState(level="error", message=action.message),
            post_reload_notification=None,
            ui_mode="BROWSING" if action.blocking else state.ui_mode,
        )
    )


def _handle_child_pane_snapshot_loaded(
    state: AppState,
    action: ChildPaneSnapshotLoaded,
    reduce_state: ReducerFn,
) -> ReduceResult:
    tab_index = _find_child_pane_snapshot_tab_index(state, action.request_id)
    if tab_index is None:
        return finalize(state)
    tab = select_browser_tabs(state)[tab_index]
    next_state = _replace_browser_tab(
        state,
        tab_index,
        replace(
            tab,
            child_pane=normalize_child_pane_for_display(
                tab.current_path,
                action.pane,
                enable_text_preview=state.config.display.enable_text_preview,
                enable_pdf_preview=state.config.display.enable_pdf_preview,
                enable_office_preview=state.config.display.enable_office_preview,
            ),
            pending_child_pane_request_id=None,
        ),
    )
    if tab_index != state.active_tab_index:
        return finalize(next_state)
    next_state = replace(next_state, notification=None)
    return maybe_request_directory_sizes(next_state, reduce_state)


def _handle_child_pane_snapshot_failed(
    state: AppState,
    action: ChildPaneSnapshotFailed,
    reduce_state: ReducerFn,
) -> ReduceResult:
    tab_index = _find_child_pane_snapshot_tab_index(state, action.request_id)
    if tab_index is None:
        return finalize(state)
    tab = select_browser_tabs(state)[tab_index]
    next_state = _replace_browser_tab(
        state,
        tab_index,
        replace(
            tab,
            child_pane=PaneState(directory_path=tab.current_path, entries=()),
            pending_child_pane_request_id=None,
        ),
    )
    if tab_index != state.active_tab_index:
        return finalize(next_state)
    return finalize(
        replace(
            next_state,
            notification=NotificationState(level="error", message=action.message),
        )
    )


def _handle_directory_sizes_loaded(
    state: AppState,
    action: DirectorySizesLoaded,
    reduce_state: ReducerFn,
) -> ReduceResult:
    if action.request_id != state.pending_directory_size_request_id:
        return finalize(state)
    loaded_entries = tuple(
        DirectorySizeCacheEntry(
            path=path,
            status="ready",
            size_bytes=size_bytes,
        )
        for path, size_bytes in action.sizes
    )
    failed_entries = tuple(
        DirectorySizeCacheEntry(
            path=path,
            status="failed",
            error_message=message,
        )
        for path, message in action.failures
    )
    next_state = replace(
        state,
        directory_size_cache=upsert_directory_size_entries(
            state.directory_size_cache,
            (*loaded_entries, *failed_entries),
        ),
        directory_size_delta=DirectorySizeDeltaState(
            changed_paths=tuple(
                dict.fromkeys(path for path, _ in (*action.sizes, *action.failures))
            ),
            revision=state.directory_size_delta.revision + 1,
        ),
        pending_directory_size_request_id=None,
    )
    return finalize(next_state)


def _handle_directory_sizes_failed(
    state: AppState,
    action: DirectorySizesFailed,
    reduce_state: ReducerFn,
) -> ReduceResult:
    if action.request_id != state.pending_directory_size_request_id:
        return finalize(state)
    next_state = replace(
        state,
        directory_size_cache=upsert_directory_size_entries(
            state.directory_size_cache,
            tuple(
                DirectorySizeCacheEntry(
                    path=path,
                    status="failed",
                    error_message=action.message,
                )
                for path in action.paths
            ),
        ),
        directory_size_delta=DirectorySizeDeltaState(
            changed_paths=tuple(dict.fromkeys(action.paths)),
            revision=state.directory_size_delta.revision + 1,
        ),
        pending_directory_size_request_id=None,
    )
    return finalize(next_state)


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_NavigationHandler = Callable[[AppState, Action, ReducerFn], ReduceResult]

_NAVIGATION_HANDLERS: dict[type[Action], _NavigationHandler] = {
    OpenNewTab: _handle_open_new_tab,
    ActivateNextTab: _handle_activate_next_tab,
    ActivatePreviousTab: _handle_activate_previous_tab,
    CloseCurrentTab: _handle_close_current_tab,
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
    RequestBrowserSnapshot: _handle_request_browser_snapshot,
    RequestDirectorySizes: _handle_request_directory_sizes,
    BrowserSnapshotLoaded: _handle_browser_snapshot_loaded,
    BrowserSnapshotFailed: _handle_browser_snapshot_failed,
    CurrentPaneSnapshotLoaded: _handle_current_pane_loaded,
    ParentChildSnapshotLoaded: _handle_parent_child_loaded,
    ParentChildSnapshotFailed: _handle_parent_child_failed,
    ChildPaneSnapshotLoaded: _handle_child_pane_snapshot_loaded,
    ChildPaneSnapshotFailed: _handle_child_pane_snapshot_failed,
    DirectorySizesLoaded: _handle_directory_sizes_loaded,
    DirectorySizesFailed: _handle_directory_sizes_failed,
}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def handle_navigation_action(
    state: AppState,
    action: Action,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    handler = _NAVIGATION_HANDLERS.get(type(action))
    if handler is not None:
        return handler(state, action, reduce_state)  # type: ignore[arg-type]
    return None
