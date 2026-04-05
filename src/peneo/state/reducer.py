"""Pure reducer for AppState transitions."""

from dataclasses import replace

from .actions import (
    Action,
    DirectorySizesFailed,
    DirectorySizesLoaded,
    InitializeState,
    SetNotification,
    SetUiMode,
)
from .effects import ReduceResult
from .models import AppState
from .reducer_common import done
from .reducer_mutations import handle_mutation_action
from .reducer_navigation import handle_navigation_action
from .reducer_palette import handle_palette_action
from .reducer_terminal_config import handle_terminal_config_action


def reduce_app_state(state: AppState, action: Action) -> ReduceResult:
    """Return a new state after applying a reducer action."""

    if isinstance(action, InitializeState):
        return done(action.state)

    if isinstance(action, SetUiMode):
        return _finalize_reduce_result(state, action, done(replace(state, ui_mode=action.mode)))

    if isinstance(action, SetNotification):
        return _finalize_reduce_result(
            state,
            action,
            done(replace(state, notification=action.notification)),
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

    return _finalize_reduce_result(state, action, done(state))


def _finalize_reduce_result(
    previous_state: AppState,
    action: Action,
    result: ReduceResult,
) -> ReduceResult:
    if isinstance(action, (DirectorySizesLoaded, DirectorySizesFailed)):
        return result
    if result.state == previous_state:
        return result
    if not result.state.directory_size_delta.changed_paths:
        return result
    return ReduceResult(
        state=replace(
            result.state,
            directory_size_delta=replace(
                result.state.directory_size_delta,
                changed_paths=(),
            ),
        ),
        effects=result.effects,
    )
