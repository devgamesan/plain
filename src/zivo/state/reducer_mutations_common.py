"""Shared helpers for mutation reducer handlers."""

from typing import Callable

from zivo.models import (
    PasteAppliedChange,
    UndoDeletePathStep,
    UndoEntry,
    UndoMovePathStep,
    UndoRestoreTrashStep,
)

from .actions import Action, CancelForegroundOperation, ForegroundOperationProgress
from .effects import ReduceResult
from .models import AppState
from .reducer_common import ReducerFn

MutationHandler = Callable[[AppState, Action, ReducerFn], ReduceResult | None]

_UNDO_STACK_LIMIT = 20


def handle_cancel_foreground_operation(
    state: AppState,
    _action: CancelForegroundOperation,
    _reduce_state: ReducerFn,
) -> ReduceResult:
    """Mark the active operation for cooperative cancellation."""

    operation = state.foreground_operation
    if operation is None or operation.cancel_requested or not operation.cancelable:
        from .reducer_common import finalize

        return finalize(state)

    from dataclasses import replace

    from .reducer_common import finalize

    return finalize(
        replace(
            state,
            foreground_operation=replace(
                operation,
                cancel_requested=True,
                cancelable=False,
                phase="cancelling",
                message="Cancel requested; finishing current item",
            ),
        )
    )


def handle_foreground_operation_progress(
    state: AppState,
    action: ForegroundOperationProgress,
    _reduce_state: ReducerFn,
) -> ReduceResult:
    """Apply progress only while the matching operation is active."""

    operation = state.foreground_operation
    if operation is None or operation.operation_id != action.request_id:
        from .reducer_common import finalize

        return finalize(state)

    from dataclasses import replace

    from .reducer_common import finalize

    total = action.total
    completed = max(0, action.completed)
    if total is not None:
        total = max(0, total)
        completed = min(completed, total)
    return finalize(
        replace(
            state,
            foreground_operation=replace(
                operation,
                phase=("cancelling" if operation.cancel_requested else action.phase),
                completed=completed,
                total=total,
                current_path=action.current_path,
                message=(
                    f"{operation.kind.title()} {completed}/{total}"
                    if total is not None
                    else f"{operation.kind.title()} {completed}"
                ),
            ),
        )
    )


def push_undo_entry(state: AppState, entry: UndoEntry | None) -> tuple[UndoEntry, ...]:
    if entry is None:
        return state.undo_stack
    trimmed_stack = state.undo_stack[-(_UNDO_STACK_LIMIT - 1) :]
    return (*trimmed_stack, entry)


def undo_entry_for_file_mutation(action_result) -> UndoEntry | None:
    if action_result.operation == "rename" and action_result.path and action_result.source_path:
        return UndoEntry(
            kind="rename",
            steps=(
                UndoMovePathStep(
                    source_path=action_result.path,
                    destination_path=action_result.source_path,
                ),
            ),
        )
    if (
        action_result.operation == "delete"
        and action_result.delete_mode == "trash"
        and action_result.trash_records
    ):
        return UndoEntry(
            kind="trash_delete",
            steps=tuple(
                UndoRestoreTrashStep(record=record) for record in action_result.trash_records
            ),
        )
    return None


def undo_entry_for_paste(
    summary,
    applied_changes: tuple[PasteAppliedChange, ...],
) -> UndoEntry | None:
    if summary.success_count == 0 or not applied_changes or summary.overwrote_count:
        return None
    if summary.mode == "copy":
        return UndoEntry(
            kind="paste_copy",
            steps=tuple(
                UndoDeletePathStep(path=change.destination_path) for change in applied_changes
            ),
        )
    return UndoEntry(
        kind="paste_cut",
        steps=tuple(
            UndoMovePathStep(
                source_path=change.destination_path,
                destination_path=change.source_path,
            )
            for change in applied_changes
        ),
    )


def undo_entry_for_duplicate(applied_changes) -> UndoEntry | None:
    """Record all successful duplicate outputs as one copy-style undo."""

    if not applied_changes:
        return None
    return UndoEntry(
        kind="paste_copy",
        steps=tuple(
            UndoDeletePathStep(path=change.destination_path) for change in applied_changes
        ),
    )
