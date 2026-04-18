"""Pure reducer for AppState transitions."""

import logging
from dataclasses import replace

from .actions import (
    Action,
    ClearPendingKeySequence,
    DirectorySizesFailed,
    DirectorySizesLoaded,
    InitializeState,
    SetNotification,
    SetPendingKeySequence,
    SetUiMode,
)
from .effects import ReduceResult
from .models import AppState, PendingKeySequenceState, sync_active_browser_tab
from .reducer_common import finalize
from .reducer_mutations import handle_mutation_action
from .reducer_navigation import handle_navigation_action
from .reducer_palette import handle_palette_action
from .reducer_terminal_config import handle_terminal_config_action
from .selectors import compute_current_pane_visible_window, select_visible_current_entry_states

logger = logging.getLogger(__name__)


def reduce_app_state(state: AppState, action: Action) -> ReduceResult:
    """Return a new state after applying a reducer action."""

    if isinstance(action, InitializeState):
        return finalize(action.state)

    if isinstance(action, SetUiMode):
        return _finalize_reduce_result(state, action, finalize(replace(state, ui_mode=action.mode)))

    if isinstance(action, SetNotification):
        return _finalize_reduce_result(
            state,
            action,
            finalize(replace(state, notification=action.notification)),
        )

    if isinstance(action, SetPendingKeySequence):
        return _finalize_reduce_result(
            state,
            action,
            finalize(
                replace(
                    state,
                    pending_key_sequence=PendingKeySequenceState(
                        keys=action.keys,
                        possible_next_keys=action.possible_next_keys,
                    ),
                )
            ),
        )

    if isinstance(action, ClearPendingKeySequence):
        return _finalize_reduce_result(
            state,
            action,
            finalize(replace(state, pending_key_sequence=None)),
        )

    for handler in (
        handle_navigation_action,
        handle_mutation_action,
        handle_palette_action,
        handle_terminal_config_action,
    ):
        result = handler(state, action, reduce_app_state)
        if result is not None:
            return _finalize_reduce_result(state, action, result)

    return _finalize_reduce_result(state, action, finalize(state))


def _finalize_reduce_result(
    previous_state: AppState,
    action: Action,
    result: ReduceResult,
) -> ReduceResult:
    result = _finalize_pending_key_sequence(result)
    result = _finalize_current_pane_window(previous_state, result)
    result = _finalize_current_pane_delta(previous_state, result)
    result = ReduceResult(
        state=sync_active_browser_tab(result.state),
        effects=result.effects,
    )
    if isinstance(action, (DirectorySizesLoaded, DirectorySizesFailed)):
        return result
    if result.state == previous_state:
        return result
    return ReduceResult(
        state=_clear_transient_deltas(result.state),
        effects=result.effects,
    )


def _finalize_pending_key_sequence(result: ReduceResult) -> ReduceResult:
    if result.state.pending_key_sequence is None or result.state.ui_mode == "BROWSING":
        return result
    return ReduceResult(
        state=replace(result.state, pending_key_sequence=None),
        effects=result.effects,
    )


def _finalize_current_pane_window(
    previous_state: AppState,
    result: ReduceResult,
) -> ReduceResult:
    next_state = result.state
    if next_state == previous_state:
        return result

    if next_state.current_pane_projection_mode != "viewport":
        if next_state.current_pane_window_start == 0:
            return result
        return ReduceResult(
            state=replace(next_state, current_pane_window_start=0),
            effects=result.effects,
        )

    visible_entries = select_visible_current_entry_states(next_state)
    window_start = _select_current_pane_window_start(next_state, visible_entries)
    if window_start == next_state.current_pane_window_start:
        return result
    return ReduceResult(
        state=replace(next_state, current_pane_window_start=window_start),
        effects=result.effects,
    )


def _finalize_current_pane_delta(
    previous_state: AppState,
    result: ReduceResult,
) -> ReduceResult:
    next_state = result.state
    if next_state == previous_state:
        return result

    changed_paths = _select_current_pane_changed_paths(previous_state, next_state)
    if changed_paths:
        next_state = replace(
            next_state,
            current_pane_delta=replace(
                next_state.current_pane_delta,
                changed_paths=changed_paths,
                revision=next_state.current_pane_delta.revision + 1,
            ),
        )
    elif next_state.current_pane_delta.changed_paths:
        next_state = replace(
            next_state,
            current_pane_delta=replace(next_state.current_pane_delta, changed_paths=()),
        )

    return ReduceResult(state=next_state, effects=result.effects)


def _select_current_pane_changed_paths(
    previous_state: AppState,
    next_state: AppState,
) -> tuple[str, ...]:
    if previous_state.sort.field == "size" or next_state.sort.field == "size":
        return ()

    previous_visible_entries = select_visible_current_entry_states(previous_state)
    next_visible_entries = select_visible_current_entry_states(next_state)
    previous_visible_paths = tuple(entry.path for entry in previous_visible_entries)
    next_visible_paths = tuple(entry.path for entry in next_visible_entries)
    if previous_visible_paths != next_visible_paths:
        return ()

    previous_selected_paths = previous_state.current_pane.selected_paths
    next_selected_paths = next_state.current_pane.selected_paths
    previous_cut_paths = _select_cut_paths(previous_state)
    next_cut_paths = _select_cut_paths(next_state)
    return tuple(
        path
        for path in next_visible_paths
        if (path in previous_selected_paths) != (path in next_selected_paths)
        or (path in previous_cut_paths) != (path in next_cut_paths)
    )


def _select_current_pane_window_start(
    state: AppState,
    visible_entries,
) -> int:
    if not visible_entries:
        return 0

    visible_window = compute_current_pane_visible_window(state.terminal_height)
    max_window_start = max(0, len(visible_entries) - visible_window)
    window_start = min(state.current_pane_window_start, max_window_start)
    cursor_index = _find_current_cursor_index(visible_entries, state.current_pane.cursor_path)
    if cursor_index is None:
        return 0
    if cursor_index < window_start:
        return cursor_index
    if cursor_index >= window_start + visible_window:
        return cursor_index - visible_window + 1
    return window_start


def _find_current_cursor_index(visible_entries, cursor_path: str | None) -> int | None:
    if cursor_path is None:
        return None
    for index, entry in enumerate(visible_entries):
        if entry.path == cursor_path:
            return index
    return None


def _select_cut_paths(state: AppState) -> frozenset[str]:
    if state.clipboard.mode != "cut":
        return frozenset()
    return frozenset(state.clipboard.paths)


def _clear_transient_deltas(state: AppState) -> AppState:
    if not state.directory_size_delta.changed_paths:
        return state
    return replace(
        state,
        directory_size_delta=replace(state.directory_size_delta, changed_paths=()),
    )
