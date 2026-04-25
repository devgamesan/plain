from tests.test_state_reducer import _reduce_state
from zivo.state import build_initial_app_state, dispatch_key_input
from zivo.state.actions import (
    ActivateNextTab,
    ActivatePreviousTab,
    BeginCommandPalette,
    BeginDeleteTargets,
    BeginGoToPath,
    BeginHistorySearch,
    BeginRenameInput,
    ClearTransferSelection,
    CopyTargets,
    CutTargets,
    FocusTransferPane,
    PasteClipboardToTransferPane,
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


def test_transfer_mode_c_copies_selected_or_focused_entry_to_clipboard() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())

    result = dispatch_key_input(state, key="c")
    assert len(result) == 2
    assert result[0] == SetNotification(None)
    assert isinstance(result[1], CopyTargets)
    # カーソル位置のファイルがターゲットになる
    assert len(result[1].paths) == 1
    assert result[1].paths[0].endswith("/docs")


def test_transfer_mode_c_warns_when_no_targets() -> None:
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

    result = dispatch_key_input(state, key="c")
    assert len(result) == 1
    assert isinstance(result[0], SetNotification)
    assert result[0].notification.message == "Nothing to copy"


def test_transfer_mode_x_cuts_selected_or_focused_entry_to_clipboard() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())

    result = dispatch_key_input(state, key="x")
    assert len(result) == 2
    assert result[0] == SetNotification(None)
    assert isinstance(result[1], CutTargets)
    # カーソル位置のファイルがターゲットになる
    assert len(result[1].paths) == 1
    assert result[1].paths[0].endswith("/docs")


def test_transfer_mode_x_warns_when_no_targets() -> None:
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

    result = dispatch_key_input(state, key="x")
    assert len(result) == 1
    assert isinstance(result[0], SetNotification)
    assert result[0].notification.message == "Nothing to cut"


def test_transfer_mode_v_pastes_from_clipboard_to_focused_pane() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())

    result = dispatch_key_input(state, key="v")
    assert len(result) == 2
    assert result[0] == SetNotification(None)
    assert isinstance(result[1], PasteClipboardToTransferPane)


def test_transfer_mode_H_begins_history_search() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())

    assert dispatch_key_input(state, key="H") == (
        SetNotification(None),
        BeginHistorySearch(),
    )


def test_transfer_mode_colon_begins_command_palette() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())

    assert dispatch_key_input(state, key=":", character=":") == (
        SetNotification(None),
        BeginCommandPalette(),
    )

def test_transfer_mode_G_begins_go_to_path() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())

    assert dispatch_key_input(state, key="G") == (
        SetNotification(None),
        BeginGoToPath(),
    )


def test_transfer_mode_d_deletes_targets() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())

    result = dispatch_key_input(state, key="d")
    assert len(result) == 2
    assert result[0] == SetNotification(None)
    assert isinstance(result[1], BeginDeleteTargets)
    # カーソル位置のファイルがターゲットになる
    assert len(result[1].paths) == 1
    assert result[1].paths[0].endswith("/docs")


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
