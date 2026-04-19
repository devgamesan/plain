"""Undo and shared completion/failure mutation handlers."""

from dataclasses import replace

from .actions import (
    FileMutationCompleted,
    FileMutationFailed,
    UndoCompleted,
    UndoFailed,
    UndoLastOperation,
)
from .models import NotificationState
from .reducer_common import (
    cursor_path_after_file_mutation,
    finalize,
    request_snapshot_refresh,
    restore_ui_mode_after_pending_input,
    run_undo_request,
)
from .reducer_mutations_common import (
    MutationHandler,
    push_undo_entry,
    undo_entry_for_file_mutation,
)


def _handle_undo_last_operation(state, action, reduce_state):
    if state.pending_undo_request_id is not None:
        return finalize(
            replace(
                state,
                notification=NotificationState(level="warning", message="Undo already in progress"),
            )
        )
    if not state.undo_stack:
        return finalize(
            replace(
                state,
                notification=NotificationState(level="warning", message="Nothing to undo"),
            )
        )
    return run_undo_request(state, state.undo_stack[-1])


def _handle_file_mutation_completed(state, action, reduce_state):
    if action.request_id != state.pending_file_mutation_request_id:
        return finalize(state)
    selected_paths = state.current_pane.selected_paths
    if action.result.removed_paths:
        selected_paths = frozenset(
            path for path in selected_paths if path not in action.result.removed_paths
        )
    next_state = replace(
        state,
        notification=None,
        current_pane=replace(
            state.current_pane,
            selected_paths=selected_paths,
            selection_anchor_path=None,
        ),
        pending_input=None,
        delete_confirmation=None,
        archive_extract_confirmation=None,
        archive_extract_progress=None,
        zip_compress_confirmation=None,
        zip_compress_progress=None,
        name_conflict=None,
        pending_file_mutation_request_id=None,
        undo_stack=push_undo_entry(state, undo_entry_for_file_mutation(action.result)),
        post_reload_notification=NotificationState(
            level=action.result.level,
            message=action.result.message,
        ),
        ui_mode="BROWSING",
    )
    return request_snapshot_refresh(
        next_state,
        cursor_path=cursor_path_after_file_mutation(state, action.result),
        keep_current_cursor=not bool(action.result.removed_paths),
    )


def _handle_undo_completed(state, action, reduce_state):
    if action.request_id != state.pending_undo_request_id:
        return finalize(state)
    selected_paths = state.current_pane.selected_paths
    if action.result.removed_paths:
        selected_paths = frozenset(
            path for path in selected_paths if path not in action.result.removed_paths
        )
    next_stack = state.undo_stack
    if (
        state.pending_undo_entry is not None
        and state.undo_stack
        and state.undo_stack[-1] == state.pending_undo_entry
    ):
        next_stack = state.undo_stack[:-1]
    next_state = replace(
        state,
        notification=None,
        current_pane=replace(
            state.current_pane,
            selected_paths=selected_paths,
            selection_anchor_path=None,
        ),
        undo_stack=next_stack,
        pending_undo_entry=None,
        pending_undo_request_id=None,
        post_reload_notification=NotificationState(
            level=action.result.level,
            message=action.result.message,
        ),
        ui_mode="BROWSING",
    )
    keep_current_cursor = True
    if (
        action.result.removed_paths
        and state.current_pane.cursor_path in action.result.removed_paths
    ):
        keep_current_cursor = False
    return request_snapshot_refresh(
        next_state,
        cursor_path=action.result.path,
        keep_current_cursor=keep_current_cursor,
    )


def _handle_undo_failed(state, action, reduce_state):
    if action.request_id != state.pending_undo_request_id:
        return finalize(state)
    return finalize(
        replace(
            state,
            notification=NotificationState(level="error", message=action.message),
            pending_undo_entry=None,
            pending_undo_request_id=None,
            ui_mode="BROWSING",
        )
    )


def _handle_file_mutation_failed(state, action, reduce_state):
    if action.request_id != state.pending_file_mutation_request_id:
        return finalize(state)
    return finalize(
        replace(
            state,
            notification=NotificationState(level="error", message=action.message),
            pending_file_mutation_request_id=None,
            delete_confirmation=None,
            archive_extract_confirmation=None,
            archive_extract_progress=None,
            zip_compress_confirmation=None,
            zip_compress_progress=None,
            name_conflict=None,
            ui_mode=restore_ui_mode_after_pending_input(state),
        )
    )


UNDO_MUTATION_HANDLERS: dict[type, MutationHandler] = {
    UndoLastOperation: _handle_undo_last_operation,
    FileMutationCompleted: _handle_file_mutation_completed,
    UndoCompleted: _handle_undo_completed,
    UndoFailed: _handle_undo_failed,
    FileMutationFailed: _handle_file_mutation_failed,
}
