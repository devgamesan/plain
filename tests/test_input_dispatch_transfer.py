from tests.test_state_reducer import _reduce_state
from zivo.state import NotificationState, build_initial_app_state, dispatch_key_input
from zivo.state.actions import (
    ActivateNextTab,
    ActivatePreviousTab,
    FocusTransferPane,
    SetNotification,
    ToggleHiddenFiles,
    ToggleTransferMode,
    TransferCopyToOppositePane,
    TransferMoveToOppositePane,
    UndoLastOperation,
)


def test_transfer_mode_uses_brackets_for_pane_focus() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())

    assert dispatch_key_input(state, key="[") == (
        SetNotification(None),
        FocusTransferPane("left"),
    )
    assert dispatch_key_input(state, key="]") == (
        SetNotification(None),
        FocusTransferPane("right"),
    )


def test_transfer_mode_q_and_2_return_to_normal_mode() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())

    assert dispatch_key_input(state, key="q", character="q") == (
        SetNotification(None),
        ToggleTransferMode(),
    )
    assert dispatch_key_input(state, key="2", character="2") == (
        SetNotification(None),
        ToggleTransferMode(),
    )


def test_transfer_mode_keeps_tab_keys_for_browser_tabs() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())

    assert dispatch_key_input(state, key="tab") == (SetNotification(None), ActivateNextTab())
    assert dispatch_key_input(state, key="shift+tab") == (
        SetNotification(None),
        ActivatePreviousTab(),
    )


def test_transfer_mode_uses_non_function_keys_for_copy_and_move() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())

    assert dispatch_key_input(state, key="y") == (
        SetNotification(None),
        TransferCopyToOppositePane(),
    )
    assert dispatch_key_input(state, key="m") == (
        SetNotification(None),
        TransferMoveToOppositePane(),
    )


def test_transfer_mode_exposes_undo_and_hidden_toggle() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())

    assert dispatch_key_input(state, key="z") == (SetNotification(None), UndoLastOperation())
    assert dispatch_key_input(state, key=".") == (SetNotification(None), ToggleHiddenFiles())


def test_transfer_mode_does_not_use_clipboard_style_keys() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())
    expected = (
        SetNotification(
            NotificationState(
                level="warning",
                message="Use [], space, y copy, m move, z undo, . hidden, or q/2 to close",
            )
        ),
    )

    assert dispatch_key_input(state, key="c") == expected
    assert dispatch_key_input(state, key="x") == expected
    assert dispatch_key_input(state, key="v") == expected
