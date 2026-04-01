"""Pure reducer for AppState transitions."""

from dataclasses import replace

from .actions import Action, InitializeState, SetNotification, SetUiMode
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
        return done(replace(state, ui_mode=action.mode))

    if isinstance(action, SetNotification):
        return done(replace(state, notification=action.notification))

    for handler in (
        handle_navigation_action,
        handle_mutation_action,
        handle_palette_action,
        handle_terminal_config_action,
    ):
        result = handler(state, action, reduce_app_state)
        if result is not None:
            return result

    return done(state)
