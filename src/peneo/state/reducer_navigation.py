"""Navigation and snapshot reducer handlers."""

from dataclasses import replace
from pathlib import Path

from .actions import (
    Action,
    BeginFilterInput,
    BrowserSnapshotFailed,
    BrowserSnapshotLoaded,
    CancelFilterInput,
    ChildPaneSnapshotFailed,
    ChildPaneSnapshotLoaded,
    ConfirmFilterInput,
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
    ReloadDirectory,
    RequestBrowserSnapshot,
    RequestDirectorySizes,
    SetCursorPath,
    SetFilterQuery,
    SetSort,
    ToggleHiddenFiles,
)
from .effects import LoadBrowserSnapshotEffect, ReduceResult, RunDirectorySizeEffect
from .models import AppState, DirectorySizeCacheEntry, FilterState, NotificationState, PaneState
from .reducer_common import (
    ReducerFn,
    build_history_after_snapshot_load,
    current_entry_for_path,
    current_entry_paths,
    done,
    maybe_request_directory_sizes,
    move_cursor,
    normalize_cursor_path,
    normalize_selected_paths,
    normalize_selection_anchor_path,
    select_range_paths,
    sync_child_pane,
    upsert_directory_size_entries,
)
from .selectors import select_visible_current_entry_states


def handle_navigation_action(
    state: AppState,
    action: Action,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    if isinstance(action, BeginFilterInput):
        return done(
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

    if isinstance(action, ConfirmFilterInput):
        return done(
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

    if isinstance(action, CancelFilterInput):
        return done(
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

    if isinstance(action, MoveCursor):
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

    if isinstance(action, MoveCursorAndSelectRange):
        if not action.visible_paths:
            return done(state)
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
            return done(state)
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

    if isinstance(action, JumpCursor):
        if not action.visible_paths:
            return done(state)
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

    if isinstance(action, SetCursorPath):
        if action.path is not None and action.path not in current_entry_paths(state):
            return done(state)
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

    if isinstance(action, EnterCursorDirectory):
        entry = current_entry_for_path(state, state.current_pane.cursor_path)
        if entry is None or entry.kind != "dir":
            return done(state)
        return reduce_state(
            state,
            RequestBrowserSnapshot(entry.path, blocking=True),
        )

    if isinstance(action, GoToParentDirectory):
        parent_path = str(Path(state.current_path).parent)
        return reduce_state(
            state,
            RequestBrowserSnapshot(
                parent_path,
                cursor_path=state.current_path,
                blocking=True,
            ),
        )

    if isinstance(action, GoToHomeDirectory):
        home_path = str(Path("~").expanduser().resolve())
        return reduce_state(
            state,
            RequestBrowserSnapshot(home_path, blocking=True),
        )

    if isinstance(action, GoBack):
        if not state.history.back:
            return done(state)
        return reduce_state(
            state,
            RequestBrowserSnapshot(state.history.back[-1], blocking=True),
        )

    if isinstance(action, GoForward):
        if not state.history.forward:
            return done(state)
        return reduce_state(
            state,
            RequestBrowserSnapshot(state.history.forward[0], blocking=True),
        )

    if isinstance(action, ReloadDirectory):
        return reduce_state(
            state,
            RequestBrowserSnapshot(
                state.current_path,
                cursor_path=state.current_pane.cursor_path,
                blocking=True,
            ),
        )

    if isinstance(action, SetFilterQuery):
        active = bool(action.query) if action.active is None else action.active
        next_state = replace(
            state,
            filter=replace(state.filter, query=action.query, active=active),
        )
        visible_paths = tuple(
            entry.path for entry in select_visible_current_entry_states(next_state)
        )
        return done(
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

    if isinstance(action, ToggleHiddenFiles):
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

    if isinstance(action, SetSort):
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

    if isinstance(action, RequestBrowserSnapshot):
        request_id = state.next_request_id
        next_state = replace(
            state,
            notification=None,
            command_palette=None,
            directory_size_cache=(),
            pending_browser_snapshot_request_id=request_id,
            pending_child_pane_request_id=None,
            pending_directory_size_request_id=None,
            next_request_id=request_id + 1,
            ui_mode="BUSY" if action.blocking else state.ui_mode,
        )
        return done(
            next_state,
            LoadBrowserSnapshotEffect(
                request_id=request_id,
                path=action.path,
                cursor_path=action.cursor_path,
                blocking=action.blocking,
            ),
        )

    if isinstance(action, RequestDirectorySizes):
        unique_paths = tuple(dict.fromkeys(action.paths))
        if not unique_paths:
            return done(state)
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
        return done(
            next_state,
            RunDirectorySizeEffect(request_id=request_id, paths=unique_paths),
        )

    if isinstance(action, BrowserSnapshotLoaded):
        if action.request_id != state.pending_browser_snapshot_request_id:
            return done(state)
        selected_paths = frozenset()
        selection_anchor_path = None
        if action.snapshot.current_path == state.current_path:
            selected_paths = normalize_selected_paths(
                state.current_pane.selected_paths,
                action.snapshot.current_pane.entries,
            )
            selection_anchor_path = normalize_selection_anchor_path(
                state.current_pane.selection_anchor_path,
                tuple(entry.path for entry in action.snapshot.current_pane.entries),
            )
        filter_state = (
            FilterState()
            if action.snapshot.current_path != state.current_path
            else state.filter
        )
        next_state = replace(
            state,
            current_path=action.snapshot.current_path,
            parent_pane=action.snapshot.parent_pane,
            current_pane=replace(
                action.snapshot.current_pane,
                selected_paths=selected_paths,
                selection_anchor_path=selection_anchor_path,
            ),
            child_pane=action.snapshot.child_pane,
            filter=filter_state,
            notification=state.post_reload_notification,
            post_reload_notification=None,
            pending_browser_snapshot_request_id=None,
            pending_child_pane_request_id=None,
            ui_mode="BROWSING" if action.blocking else state.ui_mode,
            history=build_history_after_snapshot_load(state, action.snapshot.current_path),
        )
        return maybe_request_directory_sizes(next_state, reduce_state)

    if isinstance(action, BrowserSnapshotFailed):
        if action.request_id != state.pending_browser_snapshot_request_id:
            return done(state)
        return done(
            replace(
                state,
                notification=NotificationState(level="error", message=action.message),
                post_reload_notification=None,
                pending_browser_snapshot_request_id=None,
                pending_child_pane_request_id=None,
                ui_mode="BROWSING" if action.blocking else state.ui_mode,
            )
        )

    if isinstance(action, ChildPaneSnapshotLoaded):
        if action.request_id != state.pending_child_pane_request_id:
            return done(state)
        next_state = replace(
            state,
            child_pane=action.pane,
            notification=None,
            pending_child_pane_request_id=None,
        )
        return maybe_request_directory_sizes(next_state, reduce_state)

    if isinstance(action, ChildPaneSnapshotFailed):
        if action.request_id != state.pending_child_pane_request_id:
            return done(state)
        return done(
            replace(
                state,
                child_pane=PaneState(directory_path=state.current_path, entries=()),
                notification=NotificationState(level="error", message=action.message),
                pending_child_pane_request_id=None,
            )
        )

    if isinstance(action, DirectorySizesLoaded):
        if action.request_id != state.pending_directory_size_request_id:
            return done(state)
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
            pending_directory_size_request_id=None,
        )
        return done(next_state)

    if isinstance(action, DirectorySizesFailed):
        if action.request_id != state.pending_directory_size_request_id:
            return done(state)
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
            pending_directory_size_request_id=None,
        )
        return done(next_state)

    return None
