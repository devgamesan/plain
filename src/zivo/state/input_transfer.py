"""Keyboard handling for the two-pane transfer layout."""

from pathlib import Path

from zivo.models import BulkRenameTarget

from .actions import (
    BeginBookmarkSearch,
    BeginBulkRename,
    BeginCommandPalette,
    BeginCreateInput,
    BeginDeleteTargets,
    BeginExitCurrentPath,
    BeginGo,
    BeginRenameInput,
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
from .input_common import (
    DispatchedActions,
    dispatch_direct_tab_input,
    supported,
    supported_preserving_notification,
    warn,
)
from .models import AppState, PaneState, TransferPaneState
from .selectors import compute_current_pane_visible_window

TRANSFER_KEYMAP = {
    "D",
    "N",
    "n",
    "c",
    "d",
    "delete",
    "shift+delete",
    "r",
    "~",
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
    "left",
    "m",
    ".",
    "z",
    "b",
    "G",
    "tab",
    "shift+tab",
    ":",
    "p",
    "q",
}

TRANSFER_HELP_LINES = (
    (
        ("enter", "dir"),
        (".", "hidden"),
        ("Tab", "switch-pane"),
        ("p/Esc", "close"),
        ("q", "quit"),
    ),
    (
        ("space", "select"),
        ("c", "copy-to-pane"),
        ("m", "move-to-pane"),
        ("d", "delete"),
        ("r", "rename"),
        ("z", "undo"),
    ),
    (("n", "new-file"), ("N", "new-dir"), ("G", "go"), (":", "palette")),
)

REMOVED_DIRECT_KEYS = frozenset({"i", "C", "B", "M", "O", "T", "H", "R"})

# Keys removed from transfer-mode direct operation, consolidated into Tab/c/m.
# Kept separate from REMOVED_DIRECT_KEYS because x/v stay valid in browsing mode.
TRANSFER_REMOVED_DIRECT_KEYS = frozenset({"x", "v", "y", "[", "]"})


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

    direct_tab_actions = dispatch_direct_tab_input(state, key=key)
    if direct_tab_actions:
        return direct_tab_actions

    if key in REMOVED_DIRECT_KEYS:
        return ()

    if key in TRANSFER_REMOVED_DIRECT_KEYS:
        return ()

    # Only two panes exist, so Tab and shift+tab both focus the opposite pane.
    if key in {"tab", "shift+tab"}:
        opposite = "right" if state.active_transfer_pane == "left" else "left"
        return supported(FocusTransferPane(opposite))
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
    if key == "G":
        return supported(BeginGo())
    if key == "c":
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
        if state.notification is not None and state.notification.action is not None:
            return supported_preserving_notification(BeginCommandPalette())
        return supported(BeginCommandPalette())
    if key == "p":
        return supported(ToggleTransferMode())
    if key == "q":
        return supported(BeginExitCurrentPath())

    if key == "n":
        return supported(BeginCreateInput("file"))

    if key == "N":
        return supported(BeginCreateInput("dir"))

    if key in {"d", "delete", "D", "shift+delete"}:
        selected_paths = tuple(
            path
            for path in visible_paths
            if path in transfer.pane.selected_paths
        )
        target_paths = selected_paths if selected_paths else (
            (transfer.pane.cursor_path,) if transfer.pane.cursor_path else ()
        )
        mode = "permanent" if key in {"D", "shift+delete"} else "trash"
        if not target_paths:
            message = (
                "Nothing to permanently delete"
                if mode == "permanent"
                else "Nothing to delete"
            )
            return warn(message)
        return supported(BeginDeleteTargets(target_paths, mode=mode))

    if key == "r":
        selected_paths = tuple(
            path for path in transfer.pane.selected_paths
        )
        target_paths = selected_paths if selected_paths else (
            (transfer.pane.cursor_path,) if transfer.pane.cursor_path else ()
        )
        if len(target_paths) >= 2:
            return supported(
                BeginBulkRename(
                    parent_dir=transfer.current_path,
                    targets=tuple(
                        BulkRenameTarget(path, Path(path).name) for path in target_paths
                    ),
                )
            )
        if len(target_paths) != 1:
            return warn("Rename requires a single target")
        return supported(BeginRenameInput(target_paths[0]))

    return warn(
        "Use Tab to switch pane, space select, c copy-to-pane, "
        "m move-to-pane, d trash, D permanent-delete, r rename, z undo, "
        "b bookmarks, . hidden, n new-file, N new-dir, : palette, or p/Esc to close"
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
