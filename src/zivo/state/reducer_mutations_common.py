"""Shared helpers for mutation reducer handlers."""

from typing import Callable, Literal

from zivo.models import (
    PasteAppliedChange,
    UndoDeletePathStep,
    UndoEntry,
    UndoMovePathStep,
    UndoRestoreTrashStep,
)

from .actions import Action
from .effects import ReduceResult
from .models import AppState
from .reducer_common import ReducerFn

MutationHandler = Callable[[AppState, Action, ReducerFn], ReduceResult | None]

_UNDO_STACK_LIMIT = 20


def detect_platform() -> Literal["linux", "darwin", "windows"] | None:
    """Detect the current platform."""
    import platform as platform_module

    system = platform_module.system()
    if system == "Linux":
        return "linux"
    if system == "Darwin":
        return "darwin"
    if system == "Windows":
        return "windows"
    return None


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
