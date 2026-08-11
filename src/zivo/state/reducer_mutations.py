"""Mutation reducer dispatcher."""

from .actions import (
    Action,
    CancelForegroundOperation,
    ForegroundOperationAborted,
    ForegroundOperationProgress,
)
from .effects import ReduceResult
from .models import AppState
from .reducer_common import ReducerFn
from .reducer_custom_actions import CUSTOM_ACTION_HANDLERS
from .reducer_mutations_archive import ARCHIVE_MUTATION_HANDLERS
from .reducer_mutations_bulk_rename import BULK_RENAME_MUTATION_HANDLERS
from .reducer_mutations_common import (
    MutationHandler,
    handle_cancel_foreground_operation,
    handle_foreground_operation_aborted,
    handle_foreground_operation_progress,
)
from .reducer_mutations_delete import DELETE_MUTATION_HANDLERS
from .reducer_mutations_duplicate import DUPLICATE_MUTATION_HANDLERS
from .reducer_mutations_input import INPUT_MUTATION_HANDLERS
from .reducer_mutations_replace import REPLACE_MUTATION_HANDLERS
from .reducer_mutations_selection import SELECTION_MUTATION_HANDLERS
from .reducer_mutations_undo import UNDO_MUTATION_HANDLERS

_MUTATION_HANDLERS: dict[type[Action], MutationHandler] = {
    **INPUT_MUTATION_HANDLERS,
    **SELECTION_MUTATION_HANDLERS,
    **DELETE_MUTATION_HANDLERS,
    **DUPLICATE_MUTATION_HANDLERS,
    **ARCHIVE_MUTATION_HANDLERS,
    **BULK_RENAME_MUTATION_HANDLERS,
    **REPLACE_MUTATION_HANDLERS,
    **UNDO_MUTATION_HANDLERS,
    **CUSTOM_ACTION_HANDLERS,
    CancelForegroundOperation: handle_cancel_foreground_operation,
    ForegroundOperationProgress: handle_foreground_operation_progress,
    ForegroundOperationAborted: handle_foreground_operation_aborted,
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
