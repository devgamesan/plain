from dataclasses import replace

from tests.support.state import reduce_state as _reduce_state
from zivo.models import DeleteRequest
from zivo.state import (
    DeleteConfirmationState,
    ExitConfirmationState,
    ForegroundOperationState,
    NotificationState,
    RunDeletePreparationEffect,
    RunFileMutationEffect,
    build_initial_app_state,
    reduce_app_state,
)
from zivo.state.actions import (
    AdvancePermanentDeleteConfirmation,
    BeginDeleteTargets,
    CancelDeleteConfirmation,
    ConfirmDeleteTargets,
    ConfirmExitCurrentPath,
    DeletePreparationCompleted,
)


def test_begin_delete_targets_single_runs_file_mutation() -> None:
    state = build_initial_app_state(confirm_delete=False)

    result = reduce_app_state(
        state,
        BeginDeleteTargets(("/home/tadashi/develop/zivo/docs",)),
    )

    assert result.state.ui_mode == "BUSY"
    assert result.effects == (
        RunFileMutationEffect(
            request_id=1,
            request=DeleteRequest(paths=("/home/tadashi/develop/zivo/docs",), mode="trash"),
        ),
    )


def test_begin_delete_targets_single_enters_confirm_mode_when_enabled() -> None:
    state = build_initial_app_state(confirm_delete=True)

    next_state = _reduce_state(
        state,
        BeginDeleteTargets(("/home/tadashi/develop/zivo/docs",)),
    )

    assert next_state.ui_mode == "CONFIRM"
    assert next_state.delete_confirmation == DeleteConfirmationState(
        paths=("/home/tadashi/develop/zivo/docs",)
    )


def test_begin_delete_targets_with_empty_paths_keeps_state() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(state, BeginDeleteTargets(()))

    assert next_state == state


def test_begin_delete_targets_multiple_enters_confirm_mode() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(
        state,
        BeginDeleteTargets(
            (
                "/home/tadashi/develop/zivo/docs",
                "/home/tadashi/develop/zivo/src",
            )
        ),
    )

    assert next_state.ui_mode == "CONFIRM"
    assert next_state.delete_confirmation == DeleteConfirmationState(
        paths=(
            "/home/tadashi/develop/zivo/docs",
            "/home/tadashi/develop/zivo/src",
        )
    )


def test_confirm_delete_targets_runs_file_mutation() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        delete_confirmation=DeleteConfirmationState(
            paths=(
                "/home/tadashi/develop/zivo/docs",
                "/home/tadashi/develop/zivo/src",
            )
        ),
        next_request_id=4,
    )

    result = reduce_app_state(state, ConfirmDeleteTargets())

    assert result.state.ui_mode == "BUSY"
    assert result.effects == (
        RunFileMutationEffect(
            request_id=4,
            request=DeleteRequest(
                paths=(
                    "/home/tadashi/develop/zivo/docs",
                    "/home/tadashi/develop/zivo/src",
                ),
                mode="trash",
            ),
        ),
    )


def test_cancel_delete_confirmation_returns_to_browsing_with_warning() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        delete_confirmation=DeleteConfirmationState(
            paths=("/home/tadashi/develop/zivo/docs",),
        ),
    )

    next_state = _reduce_state(state, CancelDeleteConfirmation())

    assert next_state.ui_mode == "BROWSING"
    assert next_state.notification == NotificationState(
        level="warning", message="Move to trash cancelled"
    )


def test_confirm_exit_requests_cancel_and_waits_for_active_operation() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        exit_confirmation=ExitConfirmationState(),
        foreground_operation=ForegroundOperationState(operation_id=8, kind="copy"),
    )

    result = reduce_app_state(state, ConfirmExitCurrentPath())

    assert result.state.pending_exit_after_operation is True
    assert result.state.ui_mode == "BROWSING"
    assert result.state.foreground_operation is not None
    assert result.state.foreground_operation.cancel_requested is True
    assert result.state.foreground_operation.cancelable is False


def test_begin_permanent_delete_targets_prepares_confirmation_when_delete_confirmation_disabled(
) -> None:
    state = build_initial_app_state(confirm_delete=False)

    result = reduce_app_state(
        state,
        BeginDeleteTargets(("/home/tadashi/develop/zivo/docs",), mode="permanent"),
    )

    assert result.state.ui_mode == "BUSY"
    assert result.state.pending_delete_prepare_request_id == 1
    assert result.effects == (
        RunDeletePreparationEffect(
            request_id=1,
            request=DeleteRequest(
                paths=("/home/tadashi/develop/zivo/docs",),
                mode="permanent",
            ),
        ),
    )


def test_delete_preparation_completion_shows_size_and_requires_additional_confirmation(
) -> None:
    request = DeleteRequest(
        paths=("/home/tadashi/develop/zivo/docs",),
        mode="permanent",
    )
    state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        pending_delete_prepare_request_id=4,
    )

    next_state = _reduce_state(
        state,
        DeletePreparationCompleted(
            request_id=4,
            request=request,
            total_size_bytes=4096,
            contains_directory=True,
        ),
    )

    assert next_state.ui_mode == "CONFIRM"
    assert next_state.delete_confirmation == DeleteConfirmationState(
        paths=request.paths,
        mode="permanent",
        total_size_bytes=4096,
        contains_directory=True,
    )


def test_risky_permanent_delete_requires_explicit_second_confirmation() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        delete_confirmation=DeleteConfirmationState(
            paths=("/tmp/docs",),
            mode="permanent",
            contains_directory=True,
        ),
    )

    unconfirmed = reduce_app_state(state, ConfirmDeleteTargets())
    armed = _reduce_state(state, AdvancePermanentDeleteConfirmation())
    confirmed = reduce_app_state(armed, ConfirmDeleteTargets())

    assert unconfirmed.state == state
    assert armed.delete_confirmation is not None
    assert armed.delete_confirmation.additional_confirmation_armed is True
    assert confirmed.effects == (
        RunFileMutationEffect(
            request_id=1,
            request=DeleteRequest(paths=("/tmp/docs",), mode="permanent"),
        ),
    )


def test_confirm_permanent_delete_targets_runs_file_mutation() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        delete_confirmation=DeleteConfirmationState(
            paths=("/home/tadashi/develop/zivo/docs",),
            mode="permanent",
        ),
        next_request_id=4,
    )

    result = reduce_app_state(state, ConfirmDeleteTargets())

    assert result.state.ui_mode == "BUSY"
    assert result.effects == (
        RunFileMutationEffect(
            request_id=4,
            request=DeleteRequest(
                paths=("/home/tadashi/develop/zivo/docs",),
                mode="permanent",
            ),
        ),
    )


def test_cancel_permanent_delete_confirmation_returns_to_browsing_with_warning() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        delete_confirmation=DeleteConfirmationState(
            paths=("/home/tadashi/develop/zivo/docs",),
            mode="permanent",
        ),
    )

    next_state = _reduce_state(state, CancelDeleteConfirmation())

    assert next_state.ui_mode == "BROWSING"
    assert next_state.notification == NotificationState(
        level="warning",
            message="Permanently delete cancelled",
    )
