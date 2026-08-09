from tests.test_state_reducer import _reduce_state
from zivo.state import build_initial_app_state, dispatch_key_input
from zivo.state.actions import (
    BeginCommandPalette,
    BeginDeleteTargets,
    BeginExitCurrentPath,
    BeginRenameInput,
    ClearTransferSelection,
    FocusTransferPane,
    SetNotification,
    ToggleHiddenFiles,
    ToggleTransferMode,
    TransferCopyToOppositePane,
    TransferMoveToOppositePane,
    UndoLastOperation,
)


def test_transfer_mode_tab_switches_pane_focus() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())

    # Left pane is active by default; Tab and shift+tab focus the opposite pane.
    assert dispatch_key_input(state, key="tab") == (
        SetNotification(None),
        FocusTransferPane("right"),
    )
    assert dispatch_key_input(state, key="shift+tab") == (
        SetNotification(None),
        FocusTransferPane("right"),
    )

    # With the right pane active, Tab focuses the left pane.
    state = _reduce_state(state, FocusTransferPane("right"))
    assert dispatch_key_input(state, key="tab") == (
        SetNotification(None),
        FocusTransferPane("left"),
    )


def test_transfer_mode_escape_exits_when_no_selection() -> None:
    """未選択時のEscでモード終了を確認"""
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())

    assert dispatch_key_input(state, key="escape") == (
        SetNotification(None),
        ToggleTransferMode(),
    )


def test_transfer_mode_escape_clears_selection() -> None:
    """選択時のEscで選択解除を確認"""
    from dataclasses import replace

    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())
    # 選択状態を作る
    updated_left_pane = replace(
        state.transfer_left.pane,
        selected_paths=(state.transfer_left.pane.cursor_path,),
    )
    transfer_left = replace(state.transfer_left, pane=updated_left_pane)
    state = replace(state, transfer_left=transfer_left)

    assert dispatch_key_input(state, key="escape") == (
        SetNotification(None),
        ClearTransferSelection(),
    )


def test_transfer_mode_double_escape_exits_with_selection() -> None:
    """選択時の2回のEscでモード終了を確認"""
    from dataclasses import replace

    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())
    # 選択状態を作る
    updated_left_pane = replace(
        state.transfer_left.pane,
        selected_paths=(state.transfer_left.pane.cursor_path,),
    )
    transfer_left = replace(state.transfer_left, pane=updated_left_pane)
    state = replace(state, transfer_left=transfer_left)

    # 1回目のEscで選択解除
    actions = dispatch_key_input(state, key="escape")
    assert len(actions) == 2
    assert actions[0] == SetNotification(None)
    assert isinstance(actions[1], ClearTransferSelection)

    # 選択解除後の状態を再現
    state = _reduce_state(state, actions[1])

    # 2回目のEscでモード終了
    assert dispatch_key_input(state, key="escape") == (
        SetNotification(None),
        ToggleTransferMode(),
    )


def test_transfer_mode_p_toggles_back_to_browser_mode() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())

    assert dispatch_key_input(state, key="p") == (
        SetNotification(None),
        ToggleTransferMode(),
    )


def test_transfer_mode_q_exits_app() -> None:
    """転送モードで q キーでアプリを終了することを確認"""
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())

    assert dispatch_key_input(state, key="q") == (
        SetNotification(None),
        BeginExitCurrentPath(),
    )


def test_transfer_mode_c_copies_to_opposite_pane() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())

    assert dispatch_key_input(state, key="c") == (
        SetNotification(None),
        TransferCopyToOppositePane(),
    )


def test_transfer_mode_m_moves_to_opposite_pane() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())

    assert dispatch_key_input(state, key="m") == (
        SetNotification(None),
        TransferMoveToOppositePane(),
    )


def test_transfer_removed_direct_keys_are_swallowed() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())

    for key in ("x", "v", "y", "[", "]"):
        assert dispatch_key_input(state, key=key) == ()


def test_transfer_mode_exposes_undo_and_hidden_toggle() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())

    assert dispatch_key_input(state, key="z") == (SetNotification(None), UndoLastOperation())
    assert dispatch_key_input(state, key=".") == (SetNotification(None), ToggleHiddenFiles())


def test_transfer_mode_colon_begins_command_palette() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())

    assert dispatch_key_input(state, key=":", character=":") == (
        SetNotification(None),
        BeginCommandPalette(),
    )


def test_removed_direct_shortcuts_are_unbound_in_transfer_mode() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())

    for key in ("i", "C", "B", "G", "M", "O", "T", "H", "R"):
        assert dispatch_key_input(state, key=key) == ()


def test_transfer_mode_d_deletes_targets() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())

    result = dispatch_key_input(state, key="d")
    assert len(result) == 2
    assert result[0] == SetNotification(None)
    assert isinstance(result[1], BeginDeleteTargets)
    # カーソル位置のファイルがターゲットになる
    assert len(result[1].paths) == 1
    assert result[1].paths[0].endswith("/docs")


def test_transfer_mode_uppercase_d_permanently_deletes_targets() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())

    result = dispatch_key_input(state, key="D")

    assert result[1] == BeginDeleteTargets(
        ("/home/tadashi/develop/zivo/docs",),
        mode="permanent",
    )


def test_transfer_mode_d_warns_when_no_targets() -> None:
    from dataclasses import replace

    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())
    # カーソルをクリアしてターゲットがない状態を作る
    updated_left_pane = replace(
        state.transfer_left.pane,
        cursor_path=None,
        selected_paths=(),
    )
    updated_right_pane = replace(
        state.transfer_right.pane,
        cursor_path=None,
        selected_paths=(),
    )
    transfer_left = replace(state.transfer_left, pane=updated_left_pane)
    transfer_right = replace(state.transfer_right, pane=updated_right_pane)
    state = replace(state, transfer_left=transfer_left, transfer_right=transfer_right)

    result = dispatch_key_input(state, key="d")
    assert len(result) == 1
    assert isinstance(result[0], SetNotification)
    assert result[0].notification.message == "Nothing to delete"


def test_transfer_lowercase_r_begins_rename_for_single_target() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())

    result = dispatch_key_input(state, key="r")
    assert len(result) == 2
    assert result[0] == SetNotification(None)
    assert isinstance(result[1], BeginRenameInput)
    # カーソル位置のファイルがターゲットになる
    assert result[1].path.endswith("/docs")


def test_transfer_lowercase_r_warns_for_no_target() -> None:
    from dataclasses import replace

    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())
    # カーソルをクリアしてターゲットがない状態を作る
    updated_left_pane = replace(
        state.transfer_left.pane,
        cursor_path=None,
        selected_paths=(),
    )
    updated_right_pane = replace(
        state.transfer_right.pane,
        cursor_path=None,
        selected_paths=(),
    )
    transfer_left = replace(state.transfer_left, pane=updated_left_pane)
    transfer_right = replace(state.transfer_right, pane=updated_right_pane)
    state = replace(state, transfer_left=transfer_left, transfer_right=transfer_right)

    result = dispatch_key_input(state, key="r")
    assert len(result) == 1
    assert isinstance(result[0], SetNotification)
    assert result[0].notification.message == "Rename requires a single target"


def test_transfer_lowercase_r_warns_for_multiple_targets() -> None:
    from dataclasses import replace

    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())
    # 複数選択状態を作る
    updated_left_pane = replace(
        state.transfer_left.pane,
        selected_paths=(
            state.transfer_left.pane.cursor_path,
            "/tmp/zivo-test-src/docs2",
        ),
    )
    transfer_left = replace(state.transfer_left, pane=updated_left_pane)
    state = replace(state, transfer_left=transfer_left)

    result = dispatch_key_input(state, key="r")
    assert len(result) == 1
    assert isinstance(result[0], SetNotification)
    assert result[0].notification.message == "Rename requires a single target"
