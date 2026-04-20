"""Mutation reducer dispatcher."""

from .actions import Action
from .effects import ReduceResult
from .models import AppState
from .reducer_common import ReducerFn
from .reducer_mutations_archive import ARCHIVE_MUTATION_HANDLERS
from .reducer_mutations_common import MutationHandler
from .reducer_mutations_delete import DELETE_MUTATION_HANDLERS
from .reducer_mutations_input import INPUT_MUTATION_HANDLERS
from .reducer_mutations_replace import REPLACE_MUTATION_HANDLERS
from .reducer_mutations_selection import SELECTION_MUTATION_HANDLERS
from .reducer_mutations_undo import UNDO_MUTATION_HANDLERS

_MUTATION_HANDLERS: dict[type[Action], MutationHandler] = {
    **INPUT_MUTATION_HANDLERS,
    **SELECTION_MUTATION_HANDLERS,
    **DELETE_MUTATION_HANDLERS,
    **ARCHIVE_MUTATION_HANDLERS,
    **REPLACE_MUTATION_HANDLERS,
    **UNDO_MUTATION_HANDLERS,
}


def handle_mutation_action(
    state: AppState,
    action: Action,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    handler = _MUTATION_HANDLERS.get(type(action))
    if handler is not None:
        return handler(state, action, reduce_state)  # type: ignore[arg-type]
    return None
