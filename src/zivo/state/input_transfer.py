"""Keyboard handling for the two-pane transfer layout."""

from .actions import (
    ActivateNextTab,
    ActivatePreviousTab,
    BeginBookmarkSearch,
    BeginGoToPath,
    BeginHistorySearch,
    ClearTransferSelection,
    EnterTransferDirectory,
    FocusTransferPane,
    GoToTransferHome,
    GoToTransferParent,
    JumpTransferCursor,
    MoveTransferCursor,
    MoveTransferCursorAndSelectRange,
    MoveTransferCursorByPage,
    SelectAllVisibleTransferEntries,
    ToggleHiddenFiles,
    ToggleTransferMode,
    ToggleTransferSelectionAndAdvance,
    TransferCopyToOppositePane,
    TransferMoveToOppositePane,
    UndoLastOperation,
)
from .entry_state_helpers import select_visible_entry_states
from .input_common import DispatchedActions, supported, warn
from .models import AppState, PaneState, TransferPaneState
from .selectors import compute_current_pane_visible_window

TRANSFER_KEYMAP = {
    "2",
    "G",
    "q",
    "~",
    "[",
    "]",
    "up",
    "down",
    "j",
    "k",
    "shift+up",
    "shift+down",
    "pageup",
    "pagedown",
    "home",
    "end",
    "space",
    "a",
    "escape",
    "enter",
    "l",
    "right",
    "h",
    "H",
    "left",
    "y",
    "m",
    ".",
    "z",
    "b",
    "tab",
    "shift+tab",
}


def dispatch_transfer_input(
    state: AppState,
    *,
    key: str,
    character: str | None,
) -> DispatchedActions:
    del character
    transfer = _active_transfer_pane(state)
    if transfer is None:
        return supported(ToggleTransferMode())
    visible_paths = _visible_paths(state, transfer.pane)

    if key in {"2", "q"}:
        return supported(ToggleTransferMode())
    if key == "tab":
        return supported(ActivateNextTab())
    if key == "shift+tab":
        return supported(ActivatePreviousTab())
    if key == "[":
        return supported(FocusTransferPane("left"))
    if key == "]":
        return supported(FocusTransferPane("right"))
    if key in {"up", "k"}:
        return supported(MoveTransferCursor(delta=-1, visible_paths=visible_paths))
    if key in {"down", "j"}:
        return supported(MoveTransferCursor(delta=1, visible_paths=visible_paths))
    if key == "shift+up":
        return supported(MoveTransferCursorAndSelectRange(delta=-1, visible_paths=visible_paths))
    if key == "shift+down":
        return supported(MoveTransferCursorAndSelectRange(delta=1, visible_paths=visible_paths))
    if key == "pageup":
        page_size = compute_current_pane_visible_window(state.terminal_height)
        return supported(
            MoveTransferCursorByPage(
                direction="up",
                page_size=page_size,
                visible_paths=visible_paths,
            )
        )
    if key == "pagedown":
        page_size = compute_current_pane_visible_window(state.terminal_height)
        return supported(
            MoveTransferCursorByPage(
                direction="down",
                page_size=page_size,
                visible_paths=visible_paths,
            )
        )
    if key == "home":
        return supported(JumpTransferCursor(position="start", visible_paths=visible_paths))
    if key == "end":
        return supported(JumpTransferCursor(position="end", visible_paths=visible_paths))
    if key == "space" and transfer.pane.cursor_path is not None:
        return supported(
            ToggleTransferSelectionAndAdvance(
                path=transfer.pane.cursor_path,
                visible_paths=visible_paths,
            )
        )
    if key == "a":
        return supported(SelectAllVisibleTransferEntries(paths=visible_paths))
    if key == "escape":
        return supported(ClearTransferSelection())
    if key in {"enter", "l", "right"}:
        return supported(EnterTransferDirectory())
    if key in {"h", "left"}:
        return supported(GoToTransferParent())
    if key == "~":
        return supported(GoToTransferHome())
    if key == "y":
        return supported(TransferCopyToOppositePane())
    if key == "m":
        return supported(TransferMoveToOppositePane())
    if key == ".":
        return supported(ToggleHiddenFiles())
    if key == "z":
        return supported(UndoLastOperation())
    if key == "b":
        return supported(BeginBookmarkSearch())

    if key == "G":
        return supported(BeginGoToPath())

    if key == "H":
        return supported(BeginHistorySearch())

    return warn(
        "Use [], space, y copy, m move, z undo, b bookmarks, "
        "H history, . hidden, or q/2 to close"
    )


def _active_transfer_pane(state: AppState) -> TransferPaneState | None:
    return state.transfer_left if state.active_transfer_pane == "left" else state.transfer_right


def _visible_paths(state: AppState, pane: PaneState) -> tuple[str, ...]:
    return tuple(
        entry.path
        for entry in select_visible_entry_states(
            pane.entries,
            state.directory_size_cache,
            state.show_hidden,
            "",
            False,
            state.sort,
        )
    )
