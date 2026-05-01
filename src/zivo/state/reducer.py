"""Pure reducer for AppState transitions."""

import logging
from dataclasses import replace

from zivo.windows_paths import paths_equal

from .actions import (
    Action,
    ClearPendingKeySequence,
    DirectorySizesFailed,
    DirectorySizesLoaded,
    ExitCurrentPath,
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
from .reducer_transfer import handle_transfer_action
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

    if isinstance(action, ExitCurrentPath):
        # reducer では何もせず、app.py で処理させる
        return finalize(state)

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
        handle_transfer_action,
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

    # Fast path: only cursor moved, no visible entries change
    if (previous_state.current_pane.entries == next_state.current_pane.entries and
        previous_state.show_hidden == next_state.show_hidden and
        previous_state.filter == next_state.filter and
        previous_state.sort == next_state.sort):
        # Reuse previous visible entries calculation
        visible_entries = select_visible_current_entry_states(previous_state)
        window_start = _select_current_pane_window_start(next_state, visible_entries)
        if window_start == next_state.current_pane_window_start:
            return result
        return ReduceResult(
            state=replace(next_state, current_pane_window_start=window_start),
            effects=result.effects,
        )

    # Slow path: visible entries may have changed
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


def _select_selection_changed_paths(
    previous_selected_paths: frozenset[str],
    next_selected_paths: frozenset[str],
    previous_cut_paths: frozenset[str],
    next_cut_paths: frozenset[str],
    visible_path_set: frozenset[str] | None = None,
) -> tuple[str, ...]:
    """選択/カット状態が変更されたパスを返す（オプションで可視パスでフィルタ）。"""
    selected_diff = (previous_selected_paths ^ next_selected_paths)
    cut_diff = (previous_cut_paths ^ next_cut_paths)
    changed_paths = selected_diff | cut_diff

    if visible_path_set is not None:
        changed_paths = changed_paths & visible_path_set

    return tuple(sorted(changed_paths))


def _select_current_pane_changed_paths(
    previous_state: AppState,
    next_state: AppState,
) -> tuple[str, ...]:
    if previous_state.sort.field == "size" or next_state.sort.field == "size":
        return ()

    # Fast path: only selection/cut state changed
    if (previous_state.current_pane.entries == next_state.current_pane.entries and
        previous_state.show_hidden == next_state.show_hidden and
        previous_state.filter == next_state.filter and
        previous_state.sort == next_state.sort):
        return _select_selection_changed_paths(
            previous_state.current_pane.selected_paths,
            next_state.current_pane.selected_paths,
            _select_cut_paths(previous_state),
            _select_cut_paths(next_state),
        )

    # Slow path: visible entries may have changed
    previous_visible_entries = select_visible_current_entry_states(previous_state)
    next_visible_entries = select_visible_current_entry_states(next_state)
    previous_visible_paths = tuple(entry.path for entry in previous_visible_entries)
    next_visible_paths = tuple(entry.path for entry in next_visible_entries)
    if previous_visible_paths != next_visible_paths:
        return ()

    return _select_selection_changed_paths(
        previous_state.current_pane.selected_paths,
        next_state.current_pane.selected_paths,
        _select_cut_paths(previous_state),
        _select_cut_paths(next_state),
        visible_path_set=frozenset(next_visible_paths),
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
    viewport_step = max(2, visible_window // 4)
    cursor_index = _find_current_cursor_index(visible_entries, state.current_pane.cursor_path)
    if cursor_index is None:
        return 0
    if cursor_index < window_start:
        return max(0, min(cursor_index - (viewport_step - 1), window_start - viewport_step))
    if cursor_index >= window_start + visible_window:
        minimum_visible_start = cursor_index - visible_window + 1
        return min(
            max_window_start,
            max(minimum_visible_start, window_start + viewport_step),
        )
    return window_start


def _find_current_cursor_index(visible_entries, cursor_path: str | None) -> int | None:
    if cursor_path is None:
        return None
    for index, entry in enumerate(visible_entries):
        if paths_equal(entry.path, cursor_path):
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
