"""Delete and trash mutation handlers."""

from dataclasses import replace

from zivo.models import DeleteRequest

from .actions import (
    BeginDeleteTargets,
    BeginEmptyTrash,
    BeginExitCurrentPath,
    CancelDeleteConfirmation,
    CancelEmptyTrashConfirmation,
    CancelExitConfirmation,
    ConfirmDeleteTargets,
    ConfirmEmptyTrash,
    ConfirmExitCurrentPath,
    ExitCurrentPath,
)
from .models import (
    DeleteConfirmationState,
    EmptyTrashConfirmationState,
    ExitConfirmationState,
    NotificationState,
)
from .reducer_common import finalize, run_file_mutation_request
from .reducer_mutations_common import MutationHandler, detect_platform


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


def _handle_begin_empty_trash(state, action, reduce_state):
    platform_kind = detect_platform()
    if platform_kind not in ("linux", "darwin", "windows"):
        return finalize(
            replace(
                state,
                notification=NotificationState(
                    level="error",
                    message="Empty trash is not supported on this platform",
                ),
            )
        )

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
            empty_trash_confirmation=EmptyTrashConfirmationState(
                platform=platform_kind,
            ),
            archive_extract_confirmation=None,
            archive_extract_progress=None,
            zip_compress_confirmation=None,
            zip_compress_progress=None,
            name_conflict=None,
            attribute_inspection=None,
        )
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


def _handle_confirm_empty_trash(state, action, reduce_state):
    if state.empty_trash_confirmation is None:
        return finalize(state)

    from zivo.services import resolve_trash_service

    trash_service = resolve_trash_service()
    removed_count, error_message = trash_service.empty_trash()

    if error_message and removed_count == 0:
        return finalize(
            replace(
                state,
                ui_mode="BROWSING",
                notification=NotificationState(level="error", message=error_message),
                empty_trash_confirmation=None,
            )
        )

    if error_message:
        message = error_message
        level = "warning"
    else:
        noun = "item" if removed_count == 1 else "items"
        message = f"Emptied {removed_count} {noun} from trash"
        level = "info"

    return finalize(
        replace(
            state,
            ui_mode="BROWSING",
            notification=NotificationState(level=level, message=message),
            empty_trash_confirmation=None,
        )
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


def _handle_cancel_empty_trash_confirmation(state, action, reduce_state):
    return finalize(
        replace(
            state,
            ui_mode="BROWSING",
            notification=None,
            empty_trash_confirmation=None,
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
                empty_trash_confirmation=None,
                exit_confirmation=ExitConfirmationState(),
                archive_extract_confirmation=None,
                archive_extract_progress=None,
                zip_compress_confirmation=None,
                zip_compress_progress=None,
                name_conflict=None,
                attribute_inspection=None,
            )
        )
    # confirm_exit が False の場合は reducer を経由して直接終了アクションを発行
    return reduce_state(state, ExitCurrentPath())


def _handle_confirm_exit_current_path(state, action, reduce_state):
    if state.exit_confirmation is None:
        return finalize(state)
    # ExitCurrentPath を reduce_state に渡して処理させる
    return reduce_state(
        replace(state, exit_confirmation=None),
        ExitCurrentPath()
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
    BeginEmptyTrash: _handle_begin_empty_trash,
    BeginExitCurrentPath: _handle_begin_exit_current_path,
    ConfirmDeleteTargets: _handle_confirm_delete_targets,
    ConfirmEmptyTrash: _handle_confirm_empty_trash,
    ConfirmExitCurrentPath: _handle_confirm_exit_current_path,
    CancelDeleteConfirmation: _handle_cancel_delete_confirmation,
    CancelEmptyTrashConfirmation: _handle_cancel_empty_trash_confirmation,
    CancelExitConfirmation: _handle_cancel_exit_confirmation,
}
