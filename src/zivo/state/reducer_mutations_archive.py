"""Archive and zip mutation handlers."""

from dataclasses import replace
from pathlib import Path

from .actions import (
    ArchiveExtractCompleted,
    ArchiveExtractFailed,
    ArchiveExtractProgress,
    ArchivePreparationCompleted,
    ArchivePreparationFailed,
    CancelArchiveExtractConfirmation,
    CancelZipCompressConfirmation,
    ConfirmArchiveExtract,
    ConfirmZipCompress,
    RequestBrowserSnapshot,
    ZipCompressCompleted,
    ZipCompressFailed,
    ZipCompressPreparationCompleted,
    ZipCompressPreparationFailed,
    ZipCompressProgress,
)
from .models import (
    ArchiveExtractConfirmationState,
    ArchiveExtractProgressState,
    NotificationAction,
    NotificationDetails,
    NotificationState,
    ZipCompressConfirmationState,
    ZipCompressProgressState,
)
from .reducer_common import (
    browser_snapshot_invalidation_paths,
    finalize,
    restore_ui_mode_after_pending_input,
    run_archive_extract_request,
    run_zip_compress_request,
)
from .reducer_mutations_common import MutationHandler


def _handle_confirm_archive_extract(state, action, reduce_state):
    if state.archive_extract_confirmation is None:
        return finalize(state)
    return run_archive_extract_request(
        replace(
            state,
            archive_extract_confirmation=None,
            archive_extract_progress=None,
            zip_compress_confirmation=None,
            zip_compress_progress=None,
            notification=None,
        ),
        state.archive_extract_confirmation.request,
    )


def _handle_confirm_zip_compress(state, action, reduce_state):
    if state.zip_compress_confirmation is None:
        return finalize(state)
    return run_zip_compress_request(
        replace(
            state,
            zip_compress_confirmation=None,
            zip_compress_progress=None,
            notification=None,
        ),
        state.zip_compress_confirmation.request,
    )


def _handle_cancel_archive_extract_confirmation(state, action, reduce_state):
    if state.archive_extract_confirmation is None:
        return finalize(state)
    return finalize(
        replace(
            state,
            archive_extract_confirmation=None,
            archive_extract_progress=None,
            zip_compress_confirmation=None,
            zip_compress_progress=None,
            notification=NotificationState(level="warning", message="Extraction cancelled"),
            ui_mode=restore_ui_mode_after_pending_input(state),
        )
    )


def _handle_cancel_zip_compress_confirmation(state, action, reduce_state):
    if state.zip_compress_confirmation is None:
        return finalize(state)
    return finalize(
        replace(
            state,
            zip_compress_confirmation=None,
            zip_compress_progress=None,
            notification=NotificationState(
                level="warning",
                message="Zip compression cancelled",
            ),
            ui_mode=restore_ui_mode_after_pending_input(state),
        )
    )


def _handle_archive_preparation_completed(state, action, reduce_state):
    if action.request_id != state.pending_archive_prepare_request_id:
        return finalize(state)

    if action.conflict_count > 0 and action.first_conflict_path is not None:
        return finalize(
            replace(
                state,
                notification=None,
                pending_archive_prepare_request_id=None,
                pending_archive_prepare_request=None,
                archive_extract_progress=None,
                archive_extract_confirmation=ArchiveExtractConfirmationState(
                    request=action.request,
                    conflict_count=action.conflict_count,
                    first_conflict_path=action.first_conflict_path,
                    total_entries=action.total_entries,
                ),
                ui_mode="CONFIRM",
            )
        )

    return run_archive_extract_request(
        replace(
            state,
            notification=None,
            pending_archive_prepare_request_id=None,
            pending_archive_prepare_request=None,
            archive_extract_confirmation=None,
            archive_extract_progress=None,
            zip_compress_confirmation=None,
            zip_compress_progress=None,
        ),
        action.request,
    )


def _handle_archive_preparation_failed(state, action, reduce_state):
    if action.request_id != state.pending_archive_prepare_request_id:
        return finalize(state)
    request = state.pending_archive_prepare_request
    return finalize(
        replace(
            state,
            notification=NotificationState(
                level="error",
                message=action.message,
                action=(
                    NotificationAction(
                        action_id="notification.retry",
                        label="Retry",
                        payload=request,
                    )
                    if request is not None
                    else None
                ),
            ),
            pending_archive_prepare_request_id=None,
            pending_archive_prepare_request=None,
            archive_extract_confirmation=None,
            archive_extract_progress=None,
            zip_compress_confirmation=None,
            zip_compress_progress=None,
            ui_mode=restore_ui_mode_after_pending_input(state),
        )
    )


def _handle_archive_extract_progress(state, action, reduce_state):
    if action.request_id != state.pending_archive_extract_request_id:
        return finalize(state)

    message = f"Extracting archive {action.completed_entries}/{action.total_entries}"
    if action.current_path is not None:
        message = f"{message}: {Path(action.current_path).name}"
    return finalize(
        replace(
            state,
            archive_extract_progress=ArchiveExtractProgressState(
                completed_entries=action.completed_entries,
                total_entries=action.total_entries,
                current_path=action.current_path,
            ),
            notification=NotificationState(level="info", message=message),
        )
    )


def _handle_archive_extract_completed(state, action, reduce_state):
    if action.request_id != state.pending_archive_extract_request_id:
        return finalize(state)

    partial = action.result.cancelled or bool(action.result.unprocessed_paths)
    result_notification = NotificationState(
        level=action.result.level,
        message=action.result.message,
        action=(
            NotificationAction(
                action_id="notification.details",
                label="Details",
            )
            if partial
            else (
                NotificationAction(
                    action_id="notification.open_destination",
                    label="Open destination",
                    payload=action.result.destination_path,
                )
                if action.result.level == "info"
                else None
            )
        ),
        auto_dismiss=action.result.level == "info" and not partial,
        destination_path=action.result.destination_path,
        details=(
            NotificationDetails(
                failure_count=0,
                unprocessed_count=len(action.result.unprocessed_paths),
                unprocessed_paths=action.result.unprocessed_paths,
            )
            if partial
            else None
        ),
    )
    next_state = replace(
        state,
        notification=None,
        foreground_operation=None,
        pending_input=None,
        archive_extract_confirmation=None,
        archive_extract_progress=None,
        pending_archive_prepare_request_id=None,
        pending_archive_prepare_request=None,
        pending_archive_extract_request_id=None,
        zip_compress_confirmation=None,
        zip_compress_progress=None,
        post_reload_notification=result_notification,
        ui_mode="BROWSING",
    )
    return reduce_state(
        next_state,
        RequestBrowserSnapshot(
            path=str(Path(action.result.destination_path).parent),
            cursor_path=action.result.destination_path,
            blocking=True,
            invalidate_paths=browser_snapshot_invalidation_paths(
                str(Path(action.result.destination_path).parent),
                action.result.destination_path,
            ),
        ),
    )


def _handle_archive_extract_failed(state, action, reduce_state):
    if action.request_id != state.pending_archive_extract_request_id:
        return finalize(state)
    return finalize(
        replace(
            state,
            notification=NotificationState(level="error", message=action.message),
            foreground_operation=None,
            pending_archive_extract_request_id=None,
            archive_extract_progress=None,
            archive_extract_confirmation=None,
            zip_compress_confirmation=None,
            zip_compress_progress=None,
            ui_mode=restore_ui_mode_after_pending_input(state),
        )
    )


def _handle_zip_compress_preparation_completed(state, action, reduce_state):
    if action.request_id != state.pending_zip_compress_prepare_request_id:
        return finalize(state)

    if action.destination_exists:
        return finalize(
            replace(
                state,
                notification=None,
                pending_zip_compress_prepare_request_id=None,
                pending_zip_compress_prepare_request=None,
                zip_compress_progress=None,
                zip_compress_confirmation=ZipCompressConfirmationState(
                    request=action.request,
                    total_entries=action.total_entries,
                ),
                ui_mode="CONFIRM",
            )
        )

    return run_zip_compress_request(
        replace(
            state,
            notification=None,
            pending_zip_compress_prepare_request_id=None,
            pending_zip_compress_prepare_request=None,
            zip_compress_confirmation=None,
            zip_compress_progress=None,
        ),
        action.request,
    )


def _handle_zip_compress_preparation_failed(state, action, reduce_state):
    if action.request_id != state.pending_zip_compress_prepare_request_id:
        return finalize(state)
    request = state.pending_zip_compress_prepare_request
    return finalize(
        replace(
            state,
            notification=NotificationState(
                level="error",
                message=action.message,
                action=(
                    NotificationAction(
                        action_id="notification.retry",
                        label="Retry",
                        payload=request,
                    )
                    if request is not None
                    else None
                ),
            ),
            pending_zip_compress_prepare_request_id=None,
            pending_zip_compress_prepare_request=None,
            zip_compress_confirmation=None,
            zip_compress_progress=None,
            ui_mode=restore_ui_mode_after_pending_input(state),
        )
    )


def _handle_zip_compress_progress(state, action, reduce_state):
    if action.request_id != state.pending_zip_compress_request_id:
        return finalize(state)

    message = f"Compressing as zip {action.completed_entries}/{action.total_entries}"
    if action.current_path is not None:
        message = f"{message}: {Path(action.current_path).name}"
    return finalize(
        replace(
            state,
            zip_compress_progress=ZipCompressProgressState(
                completed_entries=action.completed_entries,
                total_entries=action.total_entries,
                current_path=action.current_path,
            ),
            notification=NotificationState(level="info", message=message),
        )
    )


def _handle_zip_compress_completed(state, action, reduce_state):
    if action.request_id != state.pending_zip_compress_request_id:
        return finalize(state)

    partial = action.result.cancelled or bool(action.result.unprocessed_paths)
    destination_parent = str(Path(action.result.destination_path).parent)
    result_notification = NotificationState(
        level=action.result.level,
        message=action.result.message,
        action=(
            NotificationAction(action_id="notification.details", label="Details")
            if partial
            else (
                NotificationAction(
                    action_id="notification.open_destination",
                    label="Open destination",
                    payload=destination_parent,
                )
                if action.result.level == "info"
                else None
            )
        ),
        auto_dismiss=action.result.level == "info" and not partial,
        destination_path=destination_parent,
        details=(
            NotificationDetails(
                failure_count=0,
                unprocessed_count=len(action.result.unprocessed_paths),
                unprocessed_paths=action.result.unprocessed_paths,
            )
            if partial
            else None
        ),
    )
    next_state = replace(
        state,
        notification=None,
        foreground_operation=None,
        pending_input=None,
        zip_compress_confirmation=None,
        zip_compress_progress=None,
        pending_zip_compress_prepare_request_id=None,
        pending_zip_compress_prepare_request=None,
        pending_zip_compress_request_id=None,
        post_reload_notification=result_notification,
        ui_mode="BROWSING",
    )
    return reduce_state(
        next_state,
        RequestBrowserSnapshot(
            path=str(Path(action.result.destination_path).parent),
            cursor_path=action.result.destination_path,
            blocking=True,
            invalidate_paths=browser_snapshot_invalidation_paths(
                str(Path(action.result.destination_path).parent),
                action.result.destination_path,
            ),
        ),
    )


def _handle_zip_compress_failed(state, action, reduce_state):
    if action.request_id != state.pending_zip_compress_request_id:
        return finalize(state)
    return finalize(
        replace(
            state,
            notification=NotificationState(level="error", message=action.message),
            foreground_operation=None,
            pending_zip_compress_request_id=None,
            zip_compress_progress=None,
            zip_compress_confirmation=None,
            ui_mode=restore_ui_mode_after_pending_input(state),
        )
    )


ARCHIVE_MUTATION_HANDLERS: dict[type, MutationHandler] = {
    ConfirmArchiveExtract: _handle_confirm_archive_extract,
    ConfirmZipCompress: _handle_confirm_zip_compress,
    CancelArchiveExtractConfirmation: _handle_cancel_archive_extract_confirmation,
    CancelZipCompressConfirmation: _handle_cancel_zip_compress_confirmation,
    ArchivePreparationCompleted: _handle_archive_preparation_completed,
    ArchivePreparationFailed: _handle_archive_preparation_failed,
    ArchiveExtractProgress: _handle_archive_extract_progress,
    ArchiveExtractCompleted: _handle_archive_extract_completed,
    ArchiveExtractFailed: _handle_archive_extract_failed,
    ZipCompressPreparationCompleted: _handle_zip_compress_preparation_completed,
    ZipCompressPreparationFailed: _handle_zip_compress_preparation_failed,
    ZipCompressProgress: _handle_zip_compress_progress,
    ZipCompressCompleted: _handle_zip_compress_completed,
    ZipCompressFailed: _handle_zip_compress_failed,
}
