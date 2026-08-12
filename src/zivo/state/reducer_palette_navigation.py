"""Navigation-focused command palette reducers."""

from dataclasses import replace

from .command_palette import (
    get_command_palette_items,
    normalize_command_palette_cursor,
    select_go_candidates,
)
from .effects import ReduceResult
from .models import AppState, GoSourceFilter
from .reducer_common import (
    ReducerFn,
    finalize,
)
from .reducer_palette_shared import (
    enter_palette,
    notify,
    restore_browsing_from_palette,
)
from .reducer_transfer import request_transfer_pane_snapshot


def handle_begin_bookmark_search(state: AppState) -> ReduceResult:
    next_state = enter_palette(state, source="go")
    return finalize(
        replace(
            next_state,
            command_palette=replace(
                next_state.command_palette,
                history_and_navigation=replace(
                    next_state.command_palette.history_and_navigation,
                    go_source_filter="bookmarks",
                ),
            ),
        )
    )


def handle_begin_go(
    state: AppState,
    source_filter: GoSourceFilter = "all",
) -> ReduceResult:
    next_state = enter_palette(state, source="go")
    return finalize(
        replace(
            next_state,
            command_palette=replace(
                next_state.command_palette,
                history_and_navigation=replace(
                    next_state.command_palette.history_and_navigation,
                    go_source_filter=source_filter,
                ),
            ),
        )
    )


def handle_submit_go_palette(state: AppState, reduce_state: ReducerFn) -> ReduceResult:
    """Submit a unified Go candidate or direct path."""

    items = get_command_palette_items(state)
    if not items:
        if state.command_palette.go_completion.loading:
            return notify(state, level="warning", message="Searching directories…")
        if state.command_palette.go_completion.error_message:
            return notify(
                state,
                level="error",
                message=state.command_palette.go_completion.error_message,
            )
        return notify(state, level="warning", message="No matching destinations")
    cursor = normalize_command_palette_cursor(state, state.command_palette.cursor_index)
    selected_item = items[cursor]
    candidates = select_go_candidates(
        state,
        source_filter=state.command_palette.history_and_navigation.go_source_filter,
        query=state.command_palette.query,
    )
    if cursor >= len(candidates):
        return notify(state, level="warning", message="Destination is no longer available")
    candidate = candidates[cursor]
    if (
        candidate.tab_index is not None
        and "open_tab" in candidate.sources
    ):
        next_state = restore_browsing_from_palette(state)
        from .actions import ActivateTabByIndex

        return reduce_state(next_state, ActivateTabByIndex(candidate.tab_index))
    if selected_item.path is None:
        return notify(state, level="error", message="Destination has no path")
    if state.layout_mode == "transfer":
        next_state = restore_browsing_from_palette(state)
        return request_transfer_pane_snapshot(
            next_state,
            next_state.active_transfer_pane,
            selected_item.path,
            invalidate_paths=(),
        )
    from .actions import RequestBrowserSnapshot

    return reduce_state(
        replace(state, pending_go_palette=state.command_palette),
        RequestBrowserSnapshot(selected_item.path, blocking=True),
    )
