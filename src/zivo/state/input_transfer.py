"""Keyboard handling for the two-pane transfer layout."""

from .actions import (
    ActivateNextTab,
    ActivatePreviousTab,
    BeginBookmarkSearch,
    BeginCommandPalette,
    BeginCreateInput,
    BeginDeleteTargets,
    BeginGoToPath,
    BeginHistorySearch,
    BeginRenameInput,
    ClearTransferSelection,
    CopyTargets,
    CutTargets,
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
    "G",
    "N",
    "c",
    "d",
    "r",
    "v",
    "x",
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
    ":",
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
        if transfer.pane.selected_paths:
            return supported(ClearTransferSelection())
        return supported(ToggleTransferMode())
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
    if key == ":":
        return supported(BeginCommandPalette())

    if key == "N":
        return supported(BeginCreateInput("dir"))

    if key == "d":
        selected_paths = tuple(
            path
            for path in visible_paths
            if path in transfer.pane.selected_paths
        )
        target_paths = selected_paths if selected_paths else (
            (transfer.pane.cursor_path,) if transfer.pane.cursor_path else ()
        )
        if not target_paths:
            return warn("Nothing to delete")
        return supported(BeginDeleteTargets(target_paths, mode="trash"))

    if key == "r":
        selected_paths = tuple(
            path for path in transfer.pane.selected_paths
        )
        target_paths = selected_paths if selected_paths else (
            (transfer.pane.cursor_path,) if transfer.pane.cursor_path else ()
        )
        if len(target_paths) != 1:
            return warn("Rename requires a single target")
        return supported(BeginRenameInput(target_paths[0]))

    if key == "G":
        return supported(BeginGoToPath())

    if key == "H":
        return supported(BeginHistorySearch())

    if key == "c":
        selected_paths = tuple(
            path
            for path in visible_paths
            if path in transfer.pane.selected_paths
        )
        target_paths = selected_paths if selected_paths else (
            (transfer.pane.cursor_path,) if transfer.pane.cursor_path else ()
        )
        if not target_paths:
            return warn("Nothing to copy")
        return supported(CopyTargets(target_paths))

    if key == "x":
        selected_paths = tuple(
            path
            for path in visible_paths
            if path in transfer.pane.selected_paths
        )
        target_paths = selected_paths if selected_paths else (
            (transfer.pane.cursor_path,) if transfer.pane.cursor_path else ()
        )
        if not target_paths:
            return warn("Nothing to cut")
        return supported(CutTargets(target_paths))

    if key == "v":
        return supported(PasteClipboardToTransferPane())

    return warn(
        "Use [], space, c copy, x cut, v paste, y copy-to-pane, m move-to-pane, "
        "d delete, r rename, z undo, b bookmarks, H history, . hidden, or Esc to close"
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
