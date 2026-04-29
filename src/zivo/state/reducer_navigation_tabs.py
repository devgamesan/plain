"""Tab-focused navigation reducer handlers."""

from dataclasses import replace

from .actions import (
    ActivateNextTab,
    ActivatePreviousTab,
    ActivateTabByIndex,
    CloseCurrentTab,
    OpenNewTab,
)
from .effects import ReduceResult
from .models import AppState, NotificationState, select_browser_tabs
from .reducer_common import ReducerFn, finalize, maybe_request_directory_sizes
from .reducer_navigation_shared import (
    activate_tab,
    build_new_tab_state,
    load_browser_tab_from_tabs,
)


def _handle_open_new_tab(
    state: AppState,
    action: OpenNewTab,
    reduce_state: ReducerFn,
) -> ReduceResult:
    tabs = list(select_browser_tabs(state))
    insert_index = state.active_tab_index + 1
    tabs.insert(insert_index, build_new_tab_state(state))
    next_state = load_browser_tab_from_tabs(
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
    return activate_tab(state, (state.active_tab_index + 1) % len(tabs), reduce_state)


def _handle_activate_tab_by_index(
    state: AppState,
    action: ActivateTabByIndex,
    reduce_state: ReducerFn,
) -> ReduceResult:
    tabs = select_browser_tabs(state)
    if action.index < 0 or action.index >= len(tabs):
        return finalize(state)
    return activate_tab(state, action.index, reduce_state)


def _handle_activate_previous_tab(
    state: AppState,
    action: ActivatePreviousTab,
    reduce_state: ReducerFn,
) -> ReduceResult:
    tabs = select_browser_tabs(state)
    if len(tabs) <= 1:
        return finalize(state)
    return activate_tab(state, (state.active_tab_index - 1) % len(tabs), reduce_state)


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
    next_state = load_browser_tab_from_tabs(
        replace(state, notification=None),
        tuple(tabs),
        next_index,
    )
    return maybe_request_directory_sizes(next_state, reduce_state)


TAB_NAVIGATION_HANDLERS = {
    OpenNewTab: _handle_open_new_tab,
    ActivateTabByIndex: _handle_activate_tab_by_index,
    ActivateNextTab: _handle_activate_next_tab,
    ActivatePreviousTab: _handle_activate_previous_tab,
    CloseCurrentTab: _handle_close_current_tab,
}
