from dataclasses import replace

from tests.test_state_reducer import _reduce_state
from zivo.models import DeleteRequest
from zivo.state import (
    DeleteConfirmationState,
    EmptyTrashConfirmationState,
    NotificationState,
    RunFileMutationEffect,
    build_initial_app_state,
    reduce_app_state,
)
from zivo.state.actions import (
    BeginDeleteTargets,
    BeginEmptyTrash,
    CancelDeleteConfirmation,
    CancelEmptyTrashConfirmation,
    ConfirmDeleteTargets,
    ConfirmEmptyTrash,
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
    assert next_state.notification == NotificationState(level="warning", message="Delete cancelled")


def test_begin_permanent_delete_targets_enters_confirm_mode_when_delete_confirmation_disabled(
) -> None:
    state = build_initial_app_state(confirm_delete=False)

    next_state = _reduce_state(
        state,
        BeginDeleteTargets(("/home/tadashi/develop/zivo/docs",), mode="permanent"),
    )

    assert next_state.ui_mode == "CONFIRM"
    assert next_state.delete_confirmation == DeleteConfirmationState(
        paths=("/home/tadashi/develop/zivo/docs",),
        mode="permanent",
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
        message="Permanent delete cancelled",
    )


def test_begin_empty_trash_enters_confirm_mode(monkeypatch) -> None:
    monkeypatch.setattr("platform.system", lambda: "Darwin")

    state = build_initial_app_state()

    next_state = _reduce_state(state, BeginEmptyTrash())

    assert next_state.ui_mode == "CONFIRM"
    assert next_state.empty_trash_confirmation is not None
    assert next_state.empty_trash_confirmation.platform == "darwin"
    assert next_state.command_palette is None
    assert next_state.pending_input is None


def test_cancel_empty_trash_confirmation_returns_to_browsing() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        empty_trash_confirmation=EmptyTrashConfirmationState(platform="darwin"),
    )

    next_state = _reduce_state(state, CancelEmptyTrashConfirmation())

    assert next_state.ui_mode == "BROWSING"
    assert next_state.empty_trash_confirmation is None
    assert next_state.notification is None


def test_confirm_empty_trash_shows_notification_on_success(monkeypatch) -> None:
    from unittest.mock import MagicMock

    from zivo.services.trash_operations import MacOsTrashService

    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        empty_trash_confirmation=EmptyTrashConfirmationState(platform="darwin"),
    )

    fake_service = MacOsTrashService()
    monkeypatch.setattr("zivo.services.resolve_trash_service", lambda: fake_service)
    monkeypatch.setattr(
        "zivo.services.trash_operations.subprocess.run",
        lambda *a, **kw: MagicMock(returncode=0, stderr=""),
    )

    class FakeHome:
        def __truediv__(self, other):
            return FakePath()

    class FakePath:
        def exists(self):
            return False

    monkeypatch.setattr("pathlib.Path.home", lambda: FakeHome())

    next_state = _reduce_state(state, ConfirmEmptyTrash())

    assert next_state.ui_mode == "BROWSING"
    assert next_state.empty_trash_confirmation is None
    assert next_state.notification is not None
    assert next_state.notification.level == "info"
