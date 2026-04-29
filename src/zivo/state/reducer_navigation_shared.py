"""Shared helpers for navigation reducer modules."""

from dataclasses import replace

from zivo.windows_paths import comparable_path

from .actions import BrowserSnapshotLoaded
from .effects import ReduceResult
from .models import (
    AppState,
    BrowserTabState,
    CurrentPaneDeltaState,
    FilterState,
    HistoryState,
    PaneState,
    browser_tab_from_app_state,
    select_browser_tabs,
)
from .reducer_common import (
    ReducerFn,
    build_history_after_snapshot_load,
    maybe_request_directory_sizes,
    normalize_child_pane_for_display,
    normalize_cursor_path,
    normalize_selected_paths,
    normalize_selection_anchor_path,
)


def replace_browser_tab(
    state: AppState,
    index: int,
    tab: BrowserTabState,
) -> AppState:
    tabs = list(select_browser_tabs(state))
    tabs[index] = tab
    next_state = replace(state, browser_tabs=tuple(tabs))
    if index == state.active_tab_index:
        return load_browser_tab_from_tabs(next_state, tuple(tabs), index)
    return next_state


def load_browser_tab_from_tabs(
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


def activate_tab(
    state: AppState,
    index: int,
    reduce_state: ReducerFn,
) -> ReduceResult:
    tabs = select_browser_tabs(state)
    return maybe_request_directory_sizes(
        load_browser_tab_from_tabs(state, tabs, index),
        reduce_state,
    )


def build_new_tab_state(state: AppState) -> BrowserTabState:
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


def find_browser_snapshot_tab_index(state: AppState, request_id: int) -> int | None:
    for index, tab in enumerate(select_browser_tabs(state)):
        if tab.pending_browser_snapshot_request_id == request_id:
            return index
    return None


def find_child_pane_snapshot_tab_index(state: AppState, request_id: int) -> int | None:
    for index, tab in enumerate(select_browser_tabs(state)):
        if tab.pending_child_pane_request_id == request_id:
            return index
    return None


def apply_loaded_snapshot_to_tab(
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
            enable_image_preview=state.config.display.enable_image_preview,
            enable_pdf_preview=state.config.display.enable_pdf_preview,
            enable_office_preview=state.config.display.enable_office_preview,
        ),
        filter=FilterState() if action.snapshot.current_path != tab.current_path else tab.filter,
        history=build_history_after_snapshot_load(history_source, action.snapshot.current_path),
        current_pane_delta=CurrentPaneDeltaState(),
        pending_browser_snapshot_request_id=None,
        pending_child_pane_request_id=None,
    )


def can_promote_child_pane(
    state: AppState,
    entry_path: str,
) -> bool:
    return (
        not state.filter.active
        and state.pending_child_pane_request_id is None
        and state.child_pane.mode == "entries"
        and state.child_pane.directory_path == entry_path
    )


def promote_child_pane_to_current(
    state: AppState,
    path: str,
) -> AppState:
    promoted_entries = state.child_pane.entries
    promoted_cursor_path = normalize_cursor_path(promoted_entries, None)
    return replace(
        state,
        current_path=comparable_path(path),
        parent_pane=PaneState(
            directory_path=state.current_path,
            entries=state.current_pane.entries,
            cursor_path=comparable_path(path),
        ),
        current_pane=PaneState(
            directory_path=path,
            entries=promoted_entries,
            cursor_path=comparable_path(promoted_cursor_path),
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
