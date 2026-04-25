"""Reducer handlers for the two-pane transfer layout."""

from dataclasses import replace
from pathlib import Path
from typing import Callable

from zivo.models import PasteRequest

from .actions import (
    Action,
    ClearTransferSelection,
    EnterTransferDirectory,
    FocusTransferPane,
    GoToTransferHome,
    GoToTransferParent,
    JumpTransferCursor,
    MoveTransferCursor,
    MoveTransferCursorAndSelectRange,
    MoveTransferCursorByPage,
    PasteClipboardToTransferPane,
    SelectAllVisibleTransferEntries,
    ToggleTransferMode,
    ToggleTransferSelectionAndAdvance,
    TransferCopyToOppositePane,
    TransferMoveToOppositePane,
    TransferPaneSnapshotFailed,
    TransferPaneSnapshotLoaded,
)
from .effects import LoadTransferPaneEffect, ReduceResult
from .entry_state_helpers import select_visible_entry_states
from .models import AppState, NotificationState, PaneState, TransferPaneId, TransferPaneState
from .reducer_common import finalize, move_cursor, run_paste_request, select_range_paths
from .reducer_requests import browser_snapshot_invalidation_paths, build_history_after_snapshot_load

ReducerFn = Callable[[object, Action], ReduceResult]


def handle_transfer_action(
    state: AppState,
    action: Action,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    handler = _TRANSFER_HANDLERS.get(type(action))
    if handler is None:
        return None
    return handler(state, action, reduce_state)


def request_transfer_pane_snapshot(
    state: AppState,
    pane_id: TransferPaneId,
    path: str,
    *,
    cursor_path: str | None = None,
    invalidate_paths: tuple[str, ...] = (),
) -> ReduceResult:
    transfer = _transfer_pane(state, pane_id)
    if transfer is None:
        return finalize(state)
    request_id = state.next_request_id
    next_transfer = replace(transfer, pending_snapshot_request_id=request_id)
    next_state = _replace_transfer_pane(
        replace(state, next_request_id=request_id + 1, notification=None),
        pane_id,
        next_transfer,
    )
    return finalize(
        next_state,
        LoadTransferPaneEffect(
            request_id=request_id,
            pane_id=pane_id,
            path=path,
            cursor_path=cursor_path,
            invalidate_paths=invalidate_paths,
        ),
    )


def request_all_transfer_pane_snapshots(state: AppState) -> ReduceResult:
    if state.layout_mode != "transfer":
        return finalize(state)
    effects: list[LoadTransferPaneEffect] = []
    next_state = state
    for pane_id in ("left", "right"):
        transfer = _transfer_pane(next_state, pane_id)
        if transfer is None:
            continue
        request_id = next_state.next_request_id
        next_state = _replace_transfer_pane(
            replace(next_state, next_request_id=request_id + 1),
            pane_id,
            replace(transfer, pending_snapshot_request_id=request_id),
        )
        effects.append(
            LoadTransferPaneEffect(
                request_id=request_id,
                pane_id=pane_id,
                path=transfer.current_path,
                cursor_path=transfer.pane.cursor_path,
                invalidate_paths=browser_snapshot_invalidation_paths(transfer.current_path),
            )
        )
    return finalize(next_state, *effects)


def _handle_toggle_transfer_mode(
    state: AppState,
    action: ToggleTransferMode,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del action, reduce_state
    if state.layout_mode == "transfer":
        return finalize(
            replace(
                state,
                layout_mode="browser",
                transfer_left=None,
                transfer_right=None,
                notification=NotificationState(level="info", message="Transfer mode closed"),
            )
        )
    left = TransferPaneState(
        pane=state.current_pane, current_path=state.current_path, history=state.history
    )
    right = TransferPaneState(
        pane=state.current_pane, current_path=state.current_path, history=state.history
    )
    return finalize(
        replace(
            state,
            layout_mode="transfer",
            active_transfer_pane="left",
            transfer_left=left,
            transfer_right=right,
            notification=NotificationState(level="info", message="Transfer mode opened"),
        )
    )


def _handle_focus_transfer_pane(
    state: AppState,
    action: FocusTransferPane,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del reduce_state
    if state.layout_mode != "transfer":
        return finalize(state)
    return finalize(replace(state, active_transfer_pane=action.pane, notification=None))


def _handle_move_transfer_cursor(
    state: AppState,
    action: MoveTransferCursor,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del reduce_state
    pane_id = state.active_transfer_pane
    transfer = _require_transfer_pane(state, pane_id)
    cursor_path = move_cursor(transfer.pane.cursor_path, action.visible_paths, action.delta)
    return finalize(
        _replace_active_transfer_pane(
            state,
            replace(
                transfer,
                pane=replace(
                    transfer.pane,
                    cursor_path=cursor_path,
                    selection_anchor_path=None,
                ),
            ),
        )
    )


def _handle_jump_transfer_cursor(
    state: AppState,
    action: JumpTransferCursor,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del reduce_state
    if not action.visible_paths:
        return finalize(state)
    transfer = _require_transfer_pane(state, state.active_transfer_pane)
    cursor_path = (
        action.visible_paths[0]
        if action.position == "start"
        else action.visible_paths[-1]
    )
    return finalize(
        _replace_active_transfer_pane(
            state,
            replace(
                transfer,
                pane=replace(
                    transfer.pane,
                    cursor_path=cursor_path,
                    selection_anchor_path=None,
                ),
            ),
        )
    )


def _handle_move_transfer_cursor_by_page(
    state: AppState,
    action: MoveTransferCursorByPage,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del reduce_state
    if not action.visible_paths:
        return finalize(state)
    transfer = _require_transfer_pane(state, state.active_transfer_pane)
    current_index = (
        action.visible_paths.index(transfer.pane.cursor_path)
        if transfer.pane.cursor_path in action.visible_paths
        else 0
    )
    if action.direction == "up":
        next_index = max(0, current_index - action.page_size)
    else:
        next_index = min(len(action.visible_paths) - 1, current_index + action.page_size)
    return finalize(
        _replace_active_transfer_pane(
            state,
            replace(
                transfer,
                pane=replace(
                    transfer.pane,
                    cursor_path=action.visible_paths[next_index],
                    selection_anchor_path=None,
                ),
            ),
        )
    )


def _handle_move_transfer_cursor_and_select_range(
    state: AppState,
    action: MoveTransferCursorAndSelectRange,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del reduce_state
    if not action.visible_paths:
        return finalize(state)
    transfer = _require_transfer_pane(state, state.active_transfer_pane)
    base_cursor_path = (
        transfer.pane.cursor_path
        if transfer.pane.cursor_path in action.visible_paths
        else action.visible_paths[0]
    )
    anchor_path = (
        transfer.pane.selection_anchor_path
        if transfer.pane.selection_anchor_path in action.visible_paths
        else base_cursor_path
    )
    cursor_path = move_cursor(base_cursor_path, action.visible_paths, action.delta)
    if cursor_path is None:
        return finalize(state)
    return finalize(
        _replace_active_transfer_pane(
            state,
            replace(
                transfer,
                pane=replace(
                    transfer.pane,
                    cursor_path=cursor_path,
                    selected_paths=select_range_paths(
                        anchor_path,
                        cursor_path,
                        action.visible_paths,
                    ),
                    selection_anchor_path=anchor_path,
                ),
            ),
        )
    )


def _handle_toggle_transfer_selection_and_advance(
    state: AppState,
    action: ToggleTransferSelectionAndAdvance,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del reduce_state
    transfer = _require_transfer_pane(state, state.active_transfer_pane)
    visible = _visible_transfer_entries(state, transfer.pane)
    visible_path_set = {entry.path for entry in visible}
    if action.path not in visible_path_set:
        return finalize(state)
    selected = set(path for path in transfer.pane.selected_paths if path in visible_path_set)
    if action.path in selected:
        selected.remove(action.path)
    else:
        selected.add(action.path)
    cursor_path = move_cursor(action.path, action.visible_paths, 1)
    return finalize(
        _replace_active_transfer_pane(
            state,
            replace(
                transfer,
                pane=replace(
                    transfer.pane,
                    cursor_path=cursor_path,
                    selected_paths=frozenset(selected),
                    selection_anchor_path=None,
                ),
            ),
        )
    )


def _handle_clear_transfer_selection(
    state: AppState,
    action: ClearTransferSelection,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del action, reduce_state
    transfer = _require_transfer_pane(state, state.active_transfer_pane)
    return finalize(
        _replace_active_transfer_pane(
            state,
            replace(
                transfer,
                pane=replace(
                    transfer.pane,
                    selected_paths=frozenset(),
                    selection_anchor_path=None,
                ),
            ),
        )
    )


def _handle_select_all_visible_transfer_entries(
    state: AppState,
    action: SelectAllVisibleTransferEntries,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del reduce_state
    transfer = _require_transfer_pane(state, state.active_transfer_pane)
    return finalize(
        _replace_active_transfer_pane(
            state,
            replace(
                transfer,
                pane=replace(
                    transfer.pane,
                    selected_paths=frozenset(action.paths),
                    selection_anchor_path=None,
                ),
            ),
        )
    )


def _handle_enter_transfer_directory(
    state: AppState,
    action: EnterTransferDirectory,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del action, reduce_state
    transfer = _require_transfer_pane(state, state.active_transfer_pane)
    entry = _transfer_cursor_entry(state, transfer)
    if entry is None or entry.kind != "dir":
        return finalize(state)
    return request_transfer_pane_snapshot(
        state,
        state.active_transfer_pane,
        entry.path,
        invalidate_paths=browser_snapshot_invalidation_paths(entry.path),
    )


def _handle_go_to_transfer_parent(
    state: AppState,
    action: GoToTransferParent,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del action, reduce_state
    transfer = _require_transfer_pane(state, state.active_transfer_pane)
    parent_path = str(Path(transfer.current_path).parent)
    return request_transfer_pane_snapshot(
        state,
        state.active_transfer_pane,
        parent_path,
        cursor_path=transfer.current_path,
        invalidate_paths=browser_snapshot_invalidation_paths(parent_path),
    )


def _handle_go_to_transfer_home(
    state: AppState,
    action: GoToTransferHome,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del action, reduce_state
    _ = _require_transfer_pane(state, state.active_transfer_pane)
    home_dir = Path("~").expanduser()
    return request_transfer_pane_snapshot(
        state,
        state.active_transfer_pane,
        str(home_dir),
        invalidate_paths=browser_snapshot_invalidation_paths(str(home_dir)),
    )


def _handle_transfer_copy_to_opposite_pane(
    state: AppState,
    action: TransferCopyToOppositePane,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del action, reduce_state
    return _run_transfer_to_opposite(state, mode="copy")


def _handle_transfer_move_to_opposite_pane(
    state: AppState,
    action: TransferMoveToOppositePane,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del action, reduce_state
    return _run_transfer_to_opposite(state, mode="cut")


def _handle_paste_clipboard_to_transfer_pane(
    state: AppState,
    action: PasteClipboardToTransferPane,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del action, reduce_state
    if state.clipboard.mode == "none" or not state.clipboard.paths:
        return finalize(
            replace(
                state,
                notification=NotificationState(level="warning", message="Clipboard is empty"),
            )
        )
    transfer = _require_transfer_pane(state, state.active_transfer_pane)
    return run_paste_request(
        state,
        PasteRequest(
            mode=state.clipboard.mode,
            source_paths=state.clipboard.paths,
            destination_dir=transfer.current_path,
        ),
    )


def _handle_transfer_pane_snapshot_loaded(
    state: AppState,
    action: TransferPaneSnapshotLoaded,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del reduce_state
    transfer = _transfer_pane(state, action.pane_id)
    if transfer is None or transfer.pending_snapshot_request_id != action.request_id:
        return finalize(state)

    # 履歴を更新（build_history_after_snapshot_loadを再利用）
    temp_state = replace(
        state,
        current_path=transfer.current_path,
        history=transfer.history,
    )
    new_history = build_history_after_snapshot_load(temp_state, action.current_path)

    next_transfer = replace(
        transfer,
        pane=action.pane,
        current_path=action.current_path,
        current_pane_window_start=0,
        history=new_history,
        pending_snapshot_request_id=None,
    )
    return finalize(
        _replace_transfer_pane(
            replace(state, notification=None, ui_mode="BROWSING"),
            action.pane_id,
            next_transfer,
        )
    )


def _handle_transfer_pane_snapshot_failed(
    state: AppState,
    action: TransferPaneSnapshotFailed,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del reduce_state
    transfer = _transfer_pane(state, action.pane_id)
    if transfer is None or transfer.pending_snapshot_request_id != action.request_id:
        return finalize(state)
    return finalize(
        _replace_transfer_pane(
            replace(
                state,
                notification=NotificationState(level="error", message=action.message),
                ui_mode="BROWSING",
            ),
            action.pane_id,
            replace(transfer, pending_snapshot_request_id=None),
        )
    )


def _run_transfer_to_opposite(state: AppState, *, mode: str) -> ReduceResult:
    active = _require_transfer_pane(state, state.active_transfer_pane)
    opposite = _require_transfer_pane(state, _opposite_pane_id(state.active_transfer_pane))
    targets = _transfer_target_paths(state, active)
    if not targets:
        verb = "copy" if mode == "copy" else "move"
        return finalize(
            replace(
                state,
                notification=NotificationState(level="warning", message=f"Nothing to {verb}"),
            )
        )
    return run_paste_request(
        state,
        PasteRequest(
            mode=mode,  # type: ignore[arg-type]
            source_paths=targets,
            destination_dir=opposite.current_path,
        ),
    )


def _transfer_target_paths(state: AppState, transfer: TransferPaneState) -> tuple[str, ...]:
    visible_entries = _visible_transfer_entries(state, transfer.pane)
    selected_paths = tuple(
        entry.path for entry in visible_entries if entry.path in transfer.pane.selected_paths
    )
    if selected_paths:
        return selected_paths
    entry = _transfer_cursor_entry(state, transfer)
    return () if entry is None else (entry.path,)


def _transfer_cursor_entry(state: AppState, transfer: TransferPaneState):
    if transfer.pane.cursor_path is None:
        return None
    for entry in _visible_transfer_entries(state, transfer.pane):
        if entry.path == transfer.pane.cursor_path:
            return entry
    return None


def _visible_transfer_entries(state: AppState, pane: PaneState):
    return select_visible_entry_states(
        pane.entries,
        state.directory_size_cache,
        state.show_hidden,
        "",
        False,
        state.sort,
    )


def _transfer_pane(state: AppState, pane_id: TransferPaneId) -> TransferPaneState | None:
    return state.transfer_left if pane_id == "left" else state.transfer_right


def _require_transfer_pane(state: AppState, pane_id: TransferPaneId) -> TransferPaneState:
    transfer = _transfer_pane(state, pane_id)
    if transfer is None:
        raise RuntimeError("transfer pane is not initialized")
    return transfer


def _replace_transfer_pane(
    state: AppState,
    pane_id: TransferPaneId,
    transfer: TransferPaneState,
) -> AppState:
    if pane_id == "left":
        return replace(state, transfer_left=transfer)
    return replace(state, transfer_right=transfer)


def _replace_active_transfer_pane(
    state: AppState,
    transfer: TransferPaneState,
) -> AppState:
    return _replace_transfer_pane(state, state.active_transfer_pane, transfer)


def _opposite_pane_id(pane_id: TransferPaneId) -> TransferPaneId:
    return "right" if pane_id == "left" else "left"


_TRANSFER_HANDLERS: dict[type[Action], Callable[[AppState, Action, ReducerFn], ReduceResult]] = {
    ToggleTransferMode: _handle_toggle_transfer_mode,
    FocusTransferPane: _handle_focus_transfer_pane,
    MoveTransferCursor: _handle_move_transfer_cursor,
    JumpTransferCursor: _handle_jump_transfer_cursor,
    MoveTransferCursorByPage: _handle_move_transfer_cursor_by_page,
    MoveTransferCursorAndSelectRange: _handle_move_transfer_cursor_and_select_range,
    ToggleTransferSelectionAndAdvance: _handle_toggle_transfer_selection_and_advance,
    ClearTransferSelection: _handle_clear_transfer_selection,
    SelectAllVisibleTransferEntries: _handle_select_all_visible_transfer_entries,
    EnterTransferDirectory: _handle_enter_transfer_directory,
    GoToTransferParent: _handle_go_to_transfer_parent,
    GoToTransferHome: _handle_go_to_transfer_home,
    TransferCopyToOppositePane: _handle_transfer_copy_to_opposite_pane,
    TransferMoveToOppositePane: _handle_transfer_move_to_opposite_pane,
    PasteClipboardToTransferPane: _handle_paste_clipboard_to_transfer_pane,
    TransferPaneSnapshotLoaded: _handle_transfer_pane_snapshot_loaded,
    TransferPaneSnapshotFailed: _handle_transfer_pane_snapshot_failed,
}
