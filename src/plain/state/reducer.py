"""Pure reducer for AppState transitions."""

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
    ClearSelection,
    ConfirmFilterInput,
    EnterCursorDirectory,
    GoToParentDirectory,
    InitializeState,
    MoveCursor,
    ReloadDirectory,
    RequestBrowserSnapshot,
    SetCursorPath,
    SetFilterQuery,
    SetFilterRecursive,
    SetNotification,
    SetSort,
    SetUiMode,
    ToggleSelection,
    ToggleSelectionAndAdvance,
)
from .effects import Effect, LoadBrowserSnapshotEffect, LoadChildPaneSnapshotEffect, ReduceResult
from .models import AppState, DirectoryEntryState, NotificationState, PaneState


def reduce_app_state(state: AppState, action: Action) -> ReduceResult:
    """Return a new state after applying a reducer action."""

    def done(next_state: AppState, *effects: Effect) -> ReduceResult:
        return ReduceResult(state=next_state, effects=effects)

    if isinstance(action, InitializeState):
        return done(action.state)

    if isinstance(action, SetUiMode):
        return done(replace(state, ui_mode=action.mode))

    if isinstance(action, BeginFilterInput):
        return done(replace(state, ui_mode="FILTER", notification=None))

    if isinstance(action, ConfirmFilterInput):
        return done(replace(state, ui_mode="BROWSING", notification=None))

    if isinstance(action, CancelFilterInput):
        return done(
            replace(
                state,
                ui_mode="BROWSING",
                filter=replace(state.filter, query="", recursive=False, active=False),
                notification=None,
            )
        )

    if isinstance(action, MoveCursor):
        cursor_path = _move_cursor(
            state.current_pane.cursor_path,
            action.visible_paths,
            action.delta,
        )
        next_state = replace(
            state,
            current_pane=replace(state.current_pane, cursor_path=cursor_path),
            notification=None,
        )
        return _sync_child_pane(next_state, cursor_path)

    if isinstance(action, SetCursorPath):
        if action.path is not None and action.path not in _current_entry_paths(state):
            return done(state)
        next_state = replace(
            state,
            current_pane=replace(state.current_pane, cursor_path=action.path),
            notification=None,
        )
        return _sync_child_pane(next_state, action.path)

    if isinstance(action, EnterCursorDirectory):
        entry = _current_entry_for_path(state, state.current_pane.cursor_path)
        if entry is None or entry.kind != "dir":
            return done(state)
        return reduce_app_state(
            state,
            RequestBrowserSnapshot(entry.path, blocking=True),
        )

    if isinstance(action, GoToParentDirectory):
        parent_path = str(Path(state.current_path).parent)
        return reduce_app_state(
            state,
            RequestBrowserSnapshot(
                parent_path,
                cursor_path=state.current_path,
                blocking=True,
            ),
        )

    if isinstance(action, ReloadDirectory):
        return reduce_app_state(
            state,
            RequestBrowserSnapshot(
                state.current_path,
                cursor_path=state.current_pane.cursor_path,
                blocking=True,
            ),
        )

    if isinstance(action, ToggleSelection):
        if action.path not in _current_entry_paths(state):
            return done(state)
        selected_paths = set(
            _normalize_selected_paths(
                state.current_pane.selected_paths,
                state.current_pane.entries,
            )
        )
        if action.path in selected_paths:
            selected_paths.remove(action.path)
        else:
            selected_paths.add(action.path)
        return done(
            replace(
                state,
                current_pane=replace(
                    state.current_pane,
                    selected_paths=frozenset(selected_paths),
                ),
            )
        )

    if isinstance(action, ToggleSelectionAndAdvance):
        if action.path not in _current_entry_paths(state):
            return done(state)
        selected_paths = set(
            _normalize_selected_paths(
                state.current_pane.selected_paths,
                state.current_pane.entries,
            )
        )
        if action.path in selected_paths:
            selected_paths.remove(action.path)
        else:
            selected_paths.add(action.path)
        cursor_path = _move_cursor(action.path, action.visible_paths, 1)
        next_state = replace(
            state,
            current_pane=replace(
                state.current_pane,
                cursor_path=cursor_path,
                selected_paths=frozenset(selected_paths),
            ),
            notification=None,
        )
        return _sync_child_pane(next_state, cursor_path)

    if isinstance(action, ClearSelection):
        return done(
            replace(
                state,
                current_pane=replace(state.current_pane, selected_paths=frozenset()),
            )
        )

    if isinstance(action, SetFilterQuery):
        active = bool(action.query) if action.active is None else action.active
        return done(
            replace(
                state,
                filter=replace(state.filter, query=action.query, active=active),
            )
        )

    if isinstance(action, SetFilterRecursive):
        return done(
            replace(
                state,
                filter=replace(state.filter, recursive=action.recursive),
            )
        )

    if isinstance(action, SetSort):
        directories_first = state.sort.directories_first
        if action.directories_first is not None:
            directories_first = action.directories_first
        return done(
            replace(
                state,
                sort=replace(
                    state.sort,
                    field=action.field,
                    descending=action.descending,
                    directories_first=directories_first,
                ),
            )
        )

    if isinstance(action, SetNotification):
        return done(replace(state, notification=action.notification))

    if isinstance(action, RequestBrowserSnapshot):
        request_id = state.next_request_id
        next_state = replace(
            state,
            notification=None,
            pending_browser_snapshot_request_id=request_id,
            pending_child_pane_request_id=None,
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

    if isinstance(action, BrowserSnapshotLoaded):
        if action.request_id != state.pending_browser_snapshot_request_id:
            return done(state)
        selected_paths = frozenset()
        if action.snapshot.current_path == state.current_path:
            selected_paths = _normalize_selected_paths(
                state.current_pane.selected_paths,
                action.snapshot.current_pane.entries,
            )
        return done(
            replace(
                state,
                current_path=action.snapshot.current_path,
                parent_pane=action.snapshot.parent_pane,
                current_pane=replace(
                    action.snapshot.current_pane,
                    selected_paths=selected_paths,
                ),
                child_pane=action.snapshot.child_pane,
                notification=None,
                pending_browser_snapshot_request_id=None,
                pending_child_pane_request_id=None,
                ui_mode="BROWSING" if action.blocking else state.ui_mode,
            )
        )

    if isinstance(action, BrowserSnapshotFailed):
        if action.request_id != state.pending_browser_snapshot_request_id:
            return done(state)
        return done(
            replace(
                state,
                notification=NotificationState(level="error", message=action.message),
                pending_browser_snapshot_request_id=None,
                pending_child_pane_request_id=None,
                ui_mode="BROWSING" if action.blocking else state.ui_mode,
            )
        )

    if isinstance(action, ChildPaneSnapshotLoaded):
        if action.request_id != state.pending_child_pane_request_id:
            return done(state)
        return done(
            replace(
                state,
                child_pane=action.pane,
                notification=None,
                pending_child_pane_request_id=None,
            )
        )

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

    return done(state)


def _current_entry_paths(state: AppState) -> set[str]:
    return {entry.path for entry in state.current_pane.entries}


def _normalize_selected_paths(
    selected_paths: frozenset[str],
    entries: tuple[DirectoryEntryState, ...],
) -> frozenset[str]:
    entry_paths = {entry.path for entry in entries}
    return frozenset(path for path in selected_paths if path in entry_paths)


def _move_cursor(
    current_path: str | None,
    visible_paths: tuple[str, ...],
    delta: int,
) -> str | None:
    if not visible_paths:
        return None

    if current_path in visible_paths:
        current_index = visible_paths.index(current_path)
    else:
        current_index = 0

    next_index = max(0, min(len(visible_paths) - 1, current_index + delta))
    return visible_paths[next_index]


def _sync_child_pane(state: AppState, cursor_path: str | None) -> ReduceResult:
    entry = _current_entry_for_path(state, cursor_path)
    if entry is None or entry.kind != "dir":
        return ReduceResult(
            state=replace(
                state,
                child_pane=PaneState(directory_path=state.current_path, entries=()),
                pending_child_pane_request_id=None,
            )
        )

    if (
        entry.path == state.child_pane.directory_path
        and state.pending_child_pane_request_id is None
    ):
        return ReduceResult(state=state)

    request_id = state.next_request_id
    next_state = replace(
        state,
        pending_child_pane_request_id=request_id,
        next_request_id=request_id + 1,
    )
    return ReduceResult(
        state=next_state,
        effects=(
            LoadChildPaneSnapshotEffect(
                request_id=request_id,
                current_path=state.current_path,
                cursor_path=entry.path,
            ),
        ),
    )


def _current_entry_for_path(
    state: AppState,
    path: str | None,
) -> DirectoryEntryState | None:
    if path is None:
        return None
    for entry in state.current_pane.entries:
        if entry.path == path:
            return entry
    return None
