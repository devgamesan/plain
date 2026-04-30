"""Reducer handlers for configured custom actions."""

from __future__ import annotations

from dataclasses import replace
from textwrap import shorten

from .actions import (
    BeginCustomActionConfirmation,
    CancelCustomActionConfirmation,
    ConfirmCustomAction,
    CustomActionCompleted,
    CustomActionFailed,
)
from .effects import ReduceResult, RunCustomActionEffect
from .models import (
    AppState,
    CustomActionConfirmationState,
    NotificationState,
)
from .reducer_common import ReducerFn, finalize
from .reducer_mutations_common import MutationHandler


def _handle_begin_custom_action_confirmation(
    state: AppState,
    action: BeginCustomActionConfirmation,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return finalize(
        replace(
            state,
            ui_mode="CONFIRM",
            notification=None,
            command_palette=None,
            custom_action_confirmation=CustomActionConfirmationState(action.request),
        )
    )


def _handle_cancel_custom_action_confirmation(
    state: AppState,
    action: CancelCustomActionConfirmation,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return finalize(
        replace(
            state,
            ui_mode="BROWSING",
            custom_action_confirmation=None,
            notification=NotificationState(level="warning", message="Custom action cancelled"),
        )
    )


def _handle_confirm_custom_action(
    state: AppState,
    action: ConfirmCustomAction,
    reduce_state: ReducerFn,
) -> ReduceResult:
    if state.custom_action_confirmation is None:
        return finalize(state)
    request = state.custom_action_confirmation.request
    request_id = state.next_request_id
    ui_mode = "BROWSING" if request.mode in ("terminal", "terminal_window") else "BUSY"
    return finalize(
        replace(
            state,
            ui_mode=ui_mode,
            notification=NotificationState(
                level="info",
                message=f"Running custom action: {request.name}",
            ),
            custom_action_confirmation=None,
            pending_custom_action_request_id=request_id,
            next_request_id=request_id + 1,
        ),
        RunCustomActionEffect(request_id=request_id, request=request),
    )


def _handle_custom_action_completed(
    state: AppState,
    action: CustomActionCompleted,
    reduce_state: ReducerFn,
) -> ReduceResult:
    if state.pending_custom_action_request_id != action.request_id:
        return finalize(state)
    level, message = _notification_for_custom_action(
        action.request.name,
        action.result.result,
        mode=action.request.mode,
    )
    return finalize(
        replace(
            state,
            ui_mode="BROWSING",
            pending_custom_action_request_id=None,
            notification=NotificationState(level=level, message=message),
        )
    )


def _handle_custom_action_failed(
    state: AppState,
    action: CustomActionFailed,
    reduce_state: ReducerFn,
) -> ReduceResult:
    if state.pending_custom_action_request_id != action.request_id:
        return finalize(state)
    return finalize(
        replace(
            state,
            ui_mode="BROWSING",
            pending_custom_action_request_id=None,
            notification=NotificationState(
                level="error",
                message=f"{action.request.name} failed: {action.message}",
            ),
        )
    )


def _notification_for_custom_action(name: str, result, *, mode: str) -> tuple[str, str]:
    if mode == "terminal":
        return ("info", f"{name} finished")
    if mode == "terminal_window":
        return ("info", f"{name} started in new terminal")
    if result is None:
        return ("info", f"{name} finished")
    if result.exit_code == 0:
        detail = _first_output_line(result.stdout)
        if detail is None:
            return ("info", f"{name} finished successfully")
        return ("info", shorten(detail, width=120, placeholder="..."))
    detail = _first_output_line(result.stderr) or _first_output_line(result.stdout)
    if detail is None:
        return ("error", f"{name} failed with exit code {result.exit_code}")
    return (
        "error",
        shorten(f"{name} failed ({result.exit_code}): {detail}", width=120, placeholder="..."),
    )


def _first_output_line(output: str) -> str | None:
    for line in output.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


CUSTOM_ACTION_HANDLERS: dict[type, MutationHandler] = {
    BeginCustomActionConfirmation: _handle_begin_custom_action_confirmation,
    CancelCustomActionConfirmation: _handle_cancel_custom_action_confirmation,
    ConfirmCustomAction: _handle_confirm_custom_action,
    CustomActionCompleted: _handle_custom_action_completed,
    CustomActionFailed: _handle_custom_action_failed,
}
