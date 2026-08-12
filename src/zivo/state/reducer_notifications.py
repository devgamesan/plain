"""Reducer handlers for actionable notification activation and dismissal."""

from dataclasses import replace

from zivo.models import (
    CreateZipArchiveRequest,
    DuplicateRequest,
    ExtractArchiveRequest,
    PasteRequest,
    UndoEntry,
)

from .actions import (
    ActivateNotificationAction,
    DismissNotification,
    RequestBrowserSnapshot,
    UndoLastOperation,
)
from .effects import ReduceResult
from .models import AppState, NotificationDetails
from .reducer_common import (
    ReducerFn,
    browser_snapshot_invalidation_paths,
    finalize,
    run_archive_prepare_request,
    run_paste_request,
    run_zip_compress_prepare_request,
)
from .reducer_mutations_duplicate import run_duplicate_request


def _consume_notification(state: AppState) -> AppState:
    """Remove the action before dispatching its effect to prevent re-entry."""

    return replace(
        state,
        notification=None,
        notification_details=None,
        command_palette=None,
        ui_mode="BROWSING",
    )


def _show_notification_details(
    state: AppState,
    details: NotificationDetails,
) -> ReduceResult:
    return finalize(
        replace(
            _consume_notification(state),
            notification_details=details,
            ui_mode="DETAIL",
        )
    )


def _open_notification_destination(
    state: AppState,
    destination_path: str,
    reduce_state: ReducerFn,
) -> ReduceResult:
    next_state = _consume_notification(state)
    return reduce_state(
        next_state,
        RequestBrowserSnapshot(
            path=destination_path,
            blocking=True,
            invalidate_paths=browser_snapshot_invalidation_paths(destination_path),
        ),
    )


def _run_notification_retry(
    state: AppState,
    payload: object,
) -> ReduceResult | None:
    next_state = _consume_notification(state)
    if isinstance(payload, PasteRequest):
        if payload.conflict_resolution is not None:
            return None
        return run_paste_request(next_state, payload, force_conflict_prompt=True)
    if isinstance(payload, DuplicateRequest):
        return run_duplicate_request(next_state, payload)
    if isinstance(payload, ExtractArchiveRequest):
        return run_archive_prepare_request(next_state, payload)
    if isinstance(payload, CreateZipArchiveRequest):
        return run_zip_compress_prepare_request(next_state, payload)
    return None


def handle_notification_action(
    state: AppState,
    action: ActivateNotificationAction,
    reduce_state: ReducerFn,
) -> ReduceResult:
    """Execute a notification action through the existing reducer paths."""

    notification = state.notification
    if state.notification_revision != action.revision:
        return finalize(state)
    notification_action = (
        notification.action
        if notification is not None
        else (
            state.notification_details.recovery_action
            if state.notification_details is not None
            else None
        )
    )
    if notification_action is None or notification_action.action_id != action.action_id:
        return finalize(state)

    if action.action_id == "notification.details":
        if notification is None:
            return finalize(state)
        if notification.details is None:
            return finalize(_consume_notification(state))
        return _show_notification_details(state, notification.details)

    if action.action_id == "notification.open_destination":
        destination_path = notification.destination_path
        if destination_path is None and isinstance(notification_action.payload, str):
            destination_path = notification_action.payload
        if destination_path is None:
            return finalize(_consume_notification(state))
        return _open_notification_destination(state, destination_path, reduce_state)

    if action.action_id == "notification.undo":
        if not isinstance(notification_action.payload, UndoEntry):
            return finalize(_consume_notification(state))
        if not state.undo_stack or state.undo_stack[-1] != notification_action.payload:
            return finalize(_consume_notification(state))
        return reduce_state(_consume_notification(state), UndoLastOperation())

    if action.action_id == "notification.retry":
        result = _run_notification_retry(state, notification_action.payload)
        if result is not None:
            return result
        return finalize(_consume_notification(state))

    return finalize(_consume_notification(state))


def handle_notification_dismiss(
    state: AppState,
    action: DismissNotification,
) -> ReduceResult:
    """Reject stale or non-auto-dismiss notifications before clearing state."""

    notification = state.notification
    if (
        notification is None
        or state.notification_revision != action.revision
        or not notification.auto_dismiss
    ):
        return finalize(state)
    return finalize(replace(state, notification=None))
