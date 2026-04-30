"""Snapshot and async response handlers for navigation reducers."""

from dataclasses import replace

from .actions import (
    BrowserSnapshotFailed,
    BrowserSnapshotLoaded,
    ChildPaneSnapshotFailed,
    ChildPaneSnapshotLoaded,
    CurrentPaneSnapshotLoaded,
    DirectorySizesFailed,
    DirectorySizesLoaded,
    ParentChildSnapshotFailed,
    ParentChildSnapshotLoaded,
    RequestBrowserSnapshot,
    RequestDirectorySizes,
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
    DirectorySizeCacheEntry,
    DirectorySizeDeltaState,
    NotificationState,
    PaneState,
    select_browser_tabs,
)
from .reducer_common import (
    ReducerFn,
    finalize,
    maybe_request_directory_sizes,
    normalize_child_pane_for_display,
    upsert_directory_size_entries,
)
from .reducer_navigation_shared import (
    apply_loaded_snapshot_to_tab,
    find_browser_snapshot_tab_index,
    find_child_pane_snapshot_tab_index,
    replace_browser_tab,
)


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
        search_workspace=None,
        directory_size_cache=(),
        directory_size_delta=replace(state.directory_size_delta, changed_paths=()),
        pending_browser_snapshot_request_id=request_id,
        pending_child_pane_request_id=None,
        pending_directory_size_request_id=None,
        next_request_id=request_id + 1,
        ui_mode="BUSY" if action.blocking else state.ui_mode,
    )

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

    return finalize(
        next_state,
        LoadBrowserSnapshotEffect(
            request_id=request_id,
            path=action.path,
            cursor_path=action.cursor_path,
            blocking=action.blocking,
            invalidate_paths=action.invalidate_paths,
            enable_image_preview=state.config.display.enable_image_preview,
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
    tab_index = find_browser_snapshot_tab_index(state, action.request_id)
    if tab_index is None:
        return finalize(state)
    tab = select_browser_tabs(state)[tab_index]
    next_state = replace_browser_tab(
        state,
        tab_index,
        apply_loaded_snapshot_to_tab(state, tab, action),
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
    tab_index = find_browser_snapshot_tab_index(state, action.request_id)
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
        search_workspace=None,
    )
    next_state = replace_browser_tab(state, tab_index, next_tab)

    if tab_index == state.active_tab_index:
        next_state = replace(
            next_state,
            notification=state.post_reload_notification,
            post_reload_notification=None,
        )

    return finalize(
        next_state,
        LoadParentChildEffect(
            request_id=action.request_id,
            path=action.current_path,
            cursor_path=action.current_pane.cursor_path,
            current_pane=action.current_pane,
            enable_text_preview=state.config.display.enable_text_preview,
            enable_image_preview=state.config.display.enable_image_preview,
            enable_pdf_preview=state.config.display.enable_pdf_preview,
            enable_office_preview=state.config.display.enable_office_preview,
        ),
    )


def _handle_parent_child_loaded(
    state: AppState,
    action: ParentChildSnapshotLoaded,
    reduce_state: ReducerFn,
) -> ReduceResult:
    tab_index = find_browser_snapshot_tab_index(state, action.request_id)
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
    next_state = replace_browser_tab(state, tab_index, next_tab)

    if tab_index != state.active_tab_index:
        return finalize(replace(next_state, post_reload_notification=None))

    next_state = replace(
        next_state,
        notification=state.post_reload_notification,
        post_reload_notification=None,
        pending_browser_snapshot_request_id=None,
    )
    return maybe_request_directory_sizes(next_state, reduce_state)


def _handle_parent_child_failed(
    state: AppState,
    action: ParentChildSnapshotFailed,
    reduce_state: ReducerFn,
) -> ReduceResult:
    tab_index = find_browser_snapshot_tab_index(state, action.request_id)
    if tab_index is None:
        return finalize(state)

    tab = replace(
        select_browser_tabs(state)[tab_index],
        parent_pane_loading=False,
        child_pane_loading=False,
    )
    next_state = replace_browser_tab(state, tab_index, tab)

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
    tab_index = find_browser_snapshot_tab_index(state, action.request_id)
    if tab_index is None:
        return finalize(state)
    tab = replace(
        select_browser_tabs(state)[tab_index],
        pending_browser_snapshot_request_id=None,
        pending_child_pane_request_id=None,
    )
    next_state = replace_browser_tab(state, tab_index, tab)
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
    tab_index = find_child_pane_snapshot_tab_index(state, action.request_id)
    if tab_index is None:
        return finalize(state)
    tab = select_browser_tabs(state)[tab_index]
    next_state = replace_browser_tab(
        state,
        tab_index,
        replace(
            tab,
            child_pane=normalize_child_pane_for_display(
                tab.current_path,
                action.pane,
                enable_text_preview=state.config.display.enable_text_preview,
                enable_image_preview=state.config.display.enable_image_preview,
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
    tab_index = find_child_pane_snapshot_tab_index(state, action.request_id)
    if tab_index is None:
        return finalize(state)
    tab = select_browser_tabs(state)[tab_index]
    next_state = replace_browser_tab(
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


SNAPSHOT_NAVIGATION_HANDLERS = {
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
