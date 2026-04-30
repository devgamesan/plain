"""Navigation reducer entry point."""

from typing import Callable

from .actions import Action, EnterSearchWorkspaceResult
from .effects import ReduceResult
from .models import AppState
from .reducer_common import ReducerFn
from .reducer_navigation_browsing import BROWSING_NAVIGATION_HANDLERS
from .reducer_navigation_snapshots import SNAPSHOT_NAVIGATION_HANDLERS
from .reducer_navigation_tabs import TAB_NAVIGATION_HANDLERS
from .reducer_search_workspace import handle_enter_search_workspace_result

_NavigationHandler = Callable[[AppState, Action, ReducerFn], ReduceResult]

_NAVIGATION_HANDLERS: dict[type[Action], _NavigationHandler] = {
    **TAB_NAVIGATION_HANDLERS,
    **BROWSING_NAVIGATION_HANDLERS,
    **SNAPSHOT_NAVIGATION_HANDLERS,
    EnterSearchWorkspaceResult: handle_enter_search_workspace_result,
}


def handle_navigation_action(
    state: AppState,
    action: Action,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    handler = _NAVIGATION_HANDLERS.get(type(action))
    if handler is not None:
        return handler(state, action, reduce_state)  # type: ignore[arg-type]
    return None
