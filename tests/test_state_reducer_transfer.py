from dataclasses import replace
from pathlib import Path

from tests.support.paths import TEST_DEVELOP_ROOT, TEST_HOME, TEST_PROJECT_ROOT
from tests.support.state import reduce_state as _reduce_state
from zivo.models import (
    PasteAppliedChange,
    PasteRequest,
    PasteSummary,
    UndoDeletePathStep,
    UndoEntry,
    UndoResult,
)
from zivo.state import (
    LoadTransferPaneEffect,
    RunClipboardPasteEffect,
    build_initial_app_state,
    reduce_app_state,
    select_shell_data,
)
from zivo.state.actions import (
    ActivatePreviousTab,
    ClipboardPasteCompleted,
    EnterTransferDirectory,
    FocusTransferPane,
    OpenNewTab,
    ToggleTransferMode,
    TransferCopyToOppositePane,
    TransferMoveToOppositePane,
    UndoCompleted,
)
from zivo.state.models import ClipboardState


def test_toggle_transfer_mode_initializes_left_and_right_from_current_pane() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())

    assert state.layout_mode == "transfer"
    assert state.active_transfer_pane == "left"
    assert state.transfer_left is not None
    assert state.transfer_right is not None
    assert state.transfer_left.current_path == state.current_path
    assert state.transfer_right.current_path == state.current_path
    assert state.transfer_left.pane == state.current_pane
    assert state.transfer_right.pane == state.current_pane


def test_transfer_copy_to_opposite_pane_uses_paste_effect() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())

    reduced = reduce_app_state(state, TransferCopyToOppositePane())

    assert reduced.state.ui_mode == "BROWSING"
    assert reduced.effects == (
        RunClipboardPasteEffect(
            request_id=1,
            request=PasteRequest(
                mode="copy",
                source_paths=(TEST_PROJECT_ROOT + '/docs',),
                destination_dir=TEST_PROJECT_ROOT,
                origin="transfer",
            ),
        ),
    )


def test_transfer_move_to_opposite_pane_uses_cut_paste_request() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())

    reduced = reduce_app_state(state, TransferMoveToOppositePane())

    assert reduced.effects == (
        RunClipboardPasteEffect(
            request_id=1,
            request=PasteRequest(
                mode="cut",
                source_paths=(TEST_PROJECT_ROOT + '/docs',),
                destination_dir=TEST_PROJECT_ROOT,
                origin="transfer",
            ),
        ),
    )


def test_transfer_paste_completed_refreshes_both_transfer_panes() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())
    state = _reduce_state(state, TransferMoveToOppositePane())

    reduced = reduce_app_state(
        state,
        ClipboardPasteCompleted(
            request_id=1,
            summary=PasteSummary(
                mode="cut",
                destination_dir=TEST_PROJECT_ROOT,
                total_count=1,
                success_count=1,
                skipped_count=0,
            ),
            applied_changes=(
                PasteAppliedChange(
                    source_path=TEST_PROJECT_ROOT + '/docs',
                    destination_path=TEST_PROJECT_ROOT + '/docs',
                ),
            ),
        ),
    )

    assert reduced.effects == (
        LoadTransferPaneEffect(
            request_id=2,
            pane_id="left",
            path=TEST_PROJECT_ROOT,
            cursor_path=TEST_PROJECT_ROOT + '/src',
            invalidate_paths=(
                str(Path(TEST_PROJECT_ROOT).resolve()),
                str(Path(TEST_DEVELOP_ROOT).resolve()),
            ),
        ),
        LoadTransferPaneEffect(
            request_id=3,
            pane_id="right",
            path=TEST_PROJECT_ROOT,
            cursor_path=TEST_PROJECT_ROOT + '/docs',
            invalidate_paths=(
                str(Path(TEST_PROJECT_ROOT).resolve()),
                str(Path(TEST_DEVELOP_ROOT).resolve()),
            ),
        ),
    )


def test_transfer_undo_completed_refreshes_both_transfer_panes() -> None:
    entry = UndoEntry(
        kind="paste_copy",
        steps=(UndoDeletePathStep(path=TEST_PROJECT_ROOT + '/copied'),),
    )
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())
    state = replace(
        state,
        undo_stack=(entry,),
        pending_undo_entry=entry,
        pending_undo_request_id=7,
        next_request_id=8,
        ui_mode="BUSY",
    )

    reduced = reduce_app_state(
        state,
        UndoCompleted(
            request_id=7,
            entry=entry,
            result=UndoResult(
                path=None,
                message="Undid copied item",
                removed_paths=(TEST_PROJECT_ROOT + '/copied',),
            ),
        ),
    )

    assert reduced.state.undo_stack == ()
    assert reduced.state.pending_undo_request_id is None
    assert reduced.effects == (
        LoadTransferPaneEffect(
            request_id=8,
            pane_id="left",
            path=TEST_PROJECT_ROOT,
            cursor_path=TEST_PROJECT_ROOT + '/docs',
            invalidate_paths=(
                str(Path(TEST_PROJECT_ROOT).resolve()),
                str(Path(TEST_DEVELOP_ROOT).resolve()),
            ),
        ),
        LoadTransferPaneEffect(
            request_id=9,
            pane_id="right",
            path=TEST_PROJECT_ROOT,
            cursor_path=TEST_PROJECT_ROOT + '/docs',
            invalidate_paths=(
                str(Path(TEST_PROJECT_ROOT).resolve()),
                str(Path(TEST_DEVELOP_ROOT).resolve()),
            ),
        ),
    )


def test_enter_transfer_directory_loads_active_pane_snapshot() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())

    reduced = reduce_app_state(state, EnterTransferDirectory())

    effect = reduced.effects[0]
    assert isinstance(effect, LoadTransferPaneEffect)
    assert effect.request_id == 1
    assert effect.pane_id == "left"
    assert effect.path == TEST_PROJECT_ROOT + '/docs'
    assert effect.invalidate_paths[0].endswith(TEST_PROJECT_ROOT + '/docs')
    assert effect.invalidate_paths[1].endswith(TEST_PROJECT_ROOT)


def test_focus_transfer_pane_changes_active_side() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())

    next_state = _reduce_state(state, FocusTransferPane("right"))

    assert next_state.active_transfer_pane == "right"


def test_select_shell_data_exposes_transfer_panes() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())

    shell = select_shell_data(state)

    assert shell.layout_mode == "transfer"
    assert shell.transfer_left is not None
    assert shell.transfer_right is not None
    assert shell.transfer_left.active is True
    assert shell.transfer_right.active is False
    assert shell.transfer_left.entries[0].name == "docs"
    assert shell.transfer_right.entries[0].name == "docs"


def test_transfer_mode_is_scoped_to_browser_tab() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())

    new_tab_state = _reduce_state(state, OpenNewTab())

    assert new_tab_state.active_tab_index == 1
    # New tab preserves transfer mode state
    assert new_tab_state.layout_mode == "transfer"
    assert new_tab_state.transfer_left is not None
    assert new_tab_state.transfer_right is not None

    previous_tab_state = _reduce_state(new_tab_state, ActivatePreviousTab())

    assert previous_tab_state.active_tab_index == 0
    assert previous_tab_state.layout_mode == "transfer"
    assert previous_tab_state.transfer_left is not None
    assert previous_tab_state.transfer_right is not None


def test_clipboard_cut_not_cleared_by_direct_transfer_move() -> None:
    """直接転送 Move が事前に仕掛けた clipboard cut を誤ってクリアしない（state-mixing 修正）。"""
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())
    state = replace(
        state,
        clipboard=ClipboardState(mode="cut", paths=(TEST_HOME + '/armed',)),
    )
    state = _reduce_state(state, TransferMoveToOppositePane())

    reduced = reduce_app_state(
        state,
        ClipboardPasteCompleted(
            request_id=state.pending_paste_request_id,
            summary=PasteSummary(
                mode="cut",
                destination_dir=TEST_PROJECT_ROOT,
                total_count=1,
                success_count=1,
                skipped_count=0,
            ),
            applied_changes=(
                PasteAppliedChange(
                    source_path=TEST_PROJECT_ROOT + '/docs',
                    destination_path=TEST_PROJECT_ROOT + '/docs',
                ),
            ),
        ),
    )

    assert reduced.state.clipboard.mode == "cut"
    assert reduced.state.clipboard.paths == (TEST_HOME + '/armed',)


def test_transfer_move_clears_successful_selection_keeps_others() -> None:
    """成功した source の選択を解除し、未適用の対象は選択を保持する。"""
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())
    armed_paths = (
        TEST_PROJECT_ROOT + '/docs',
        TEST_PROJECT_ROOT + '/src',
    )
    state = replace(
        state,
        transfer_left=replace(
            state.transfer_left,
            pane=replace(
                state.transfer_left.pane,
                selected_paths=frozenset(armed_paths),
                cursor_path=TEST_PROJECT_ROOT + '/docs',
            ),
        ),
    )
    state = _reduce_state(state, TransferMoveToOppositePane())

    reduced = reduce_app_state(
        state,
        ClipboardPasteCompleted(
            request_id=state.pending_paste_request_id,
            summary=PasteSummary(
                mode="cut",
                destination_dir=TEST_PROJECT_ROOT,
                total_count=2,
                success_count=1,
                skipped_count=0,
            ),
            applied_changes=(
                PasteAppliedChange(
                    source_path=TEST_PROJECT_ROOT + '/docs',
                    destination_path=TEST_PROJECT_ROOT + '/docs',
                ),
            ),
        ),
    )

    left = reduced.state.transfer_left
    assert left is not None
    assert TEST_PROJECT_ROOT + '/docs' not in left.pane.selected_paths
    assert TEST_PROJECT_ROOT + '/src' in left.pane.selected_paths
