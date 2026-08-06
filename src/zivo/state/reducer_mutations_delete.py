"""Delete and trash mutation handlers."""

from dataclasses import replace

from zivo.models import DeleteRequest

from .actions import (
    BeginDeleteTargets,
    BeginExitCurrentPath,
    CancelDeleteConfirmation,
    CancelExitConfirmation,
    ConfirmDeleteTargets,
    ConfirmExitCurrentPath,
    ExitCurrentPath,
)
from .effects import ExitCurrentPathEffect
from .models import (
    DeleteConfirmationState,
    ExitConfirmationState,
    NotificationState,
)
from .reducer_common import finalize, run_file_mutation_request
from .reducer_mutations_common import MutationHandler


def _handle_begin_delete_targets(state, action, reduce_state):
    if not action.paths:
        return finalize(state)
    if action.mode == "permanent" or state.confirm_delete:
        return finalize(
            replace(
                state,
                ui_mode="CONFIRM",
                notification=None,
                pending_input=None,
                command_palette=None,
                pending_file_search_request_id=None,
                pending_grep_search_request_id=None,
                paste_conflict=None,
                delete_confirmation=DeleteConfirmationState(
                    paths=action.paths,
                    mode=action.mode,
                ),
                archive_extract_confirmation=None,
                archive_extract_progress=None,
                zip_compress_confirmation=None,
                zip_compress_progress=None,
                name_conflict=None,
                attribute_inspection=None,
            )
        )
    return run_file_mutation_request(
        replace(
            state,
            notification=None,
            paste_conflict=None,
            delete_confirmation=None,
            archive_extract_confirmation=None,
            archive_extract_progress=None,
            zip_compress_confirmation=None,
            zip_compress_progress=None,
            name_conflict=None,
            attribute_inspection=None,
        ),
        DeleteRequest(paths=action.paths, mode=action.mode),
    )


def _handle_confirm_delete_targets(state, action, reduce_state):
    if state.delete_confirmation is None:
        return finalize(state)
    return run_file_mutation_request(
        replace(
            state,
            delete_confirmation=None,
            paste_conflict=None,
            notification=None,
        ),
        DeleteRequest(
            paths=state.delete_confirmation.paths,
            mode=state.delete_confirmation.mode,
        ),
    )


def _handle_cancel_delete_confirmation(state, action, reduce_state):
    message = (
        "Permanent delete cancelled"
        if state.delete_confirmation is not None
        and state.delete_confirmation.mode == "permanent"
        else "Delete cancelled"
    )
    return finalize(
        replace(
            state,
            delete_confirmation=None,
            ui_mode="BROWSING",
            notification=NotificationState(level="warning", message=message),
        )
    )


def _handle_begin_exit_current_path(state, action, reduce_state):
    if state.confirm_exit:
        return finalize(
            replace(
                state,
                ui_mode="CONFIRM",
                notification=None,
                pending_input=None,
                command_palette=None,
                pending_file_search_request_id=None,
                pending_grep_search_request_id=None,
                paste_conflict=None,
                delete_confirmation=None,
                exit_confirmation=ExitConfirmationState(),
                archive_extract_confirmation=None,
                archive_extract_progress=None,
                zip_compress_confirmation=None,
                zip_compress_progress=None,
                name_conflict=None,
                attribute_inspection=None,
            )
        )
    return reduce_state(state, ExitCurrentPath())


def _handle_confirm_exit_current_path(state, action, reduce_state):
    if state.exit_confirmation is None:
        return finalize(state)
    return finalize(
        replace(state, exit_confirmation=None),
        ExitCurrentPathEffect()
    )


def _handle_cancel_exit_confirmation(state, action, reduce_state):
    if state.exit_confirmation is None:
        return finalize(state)
    return finalize(
        replace(
            state,
            ui_mode="BROWSING",
            notification=None,
            exit_confirmation=None,
        )
    )


DELETE_MUTATION_HANDLERS: dict[type, MutationHandler] = {
    BeginDeleteTargets: _handle_begin_delete_targets,
    BeginExitCurrentPath: _handle_begin_exit_current_path,
    ConfirmDeleteTargets: _handle_confirm_delete_targets,
    ConfirmExitCurrentPath: _handle_confirm_exit_current_path,
    CancelDeleteConfirmation: _handle_cancel_delete_confirmation,
    CancelExitConfirmation: _handle_cancel_exit_confirmation,
}
