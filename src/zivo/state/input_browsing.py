"""Browsing-mode key bindings and dispatcher."""

from .actions import (
    Action,
    ActivateNextTab,
    ActivatePreviousTab,
    ActivateTabByIndex,
    AddBookmark,
    BeginBookmarkSearch,
    BeginCommandPalette,
    BeginCreateInput,
    BeginDeleteTargets,
    BeginFileSearch,
    BeginFilterInput,
    BeginGoToPath,
    BeginGrepSearch,
    BeginHistorySearch,
    BeginRenameInput,
    BeginShellCommandInput,
    CancelFilterInput,
    ClearPendingKeySequence,
    ClearSelection,
    CloseCurrentTab,
    CopyPathsToClipboard,
    CopyTargets,
    CutTargets,
    EnterCursorDirectory,
    ExitCurrentPath,
    GoBack,
    GoForward,
    GoToHomeDirectory,
    GoToParentDirectory,
    JumpCursor,
    MoveCursor,
    MoveCursorAndSelectRange,
    MoveCursorByPage,
    OpenNewTab,
    OpenPathInEditor,
    OpenPathInGuiEditor,
    OpenPathWithDefaultApp,
    OpenTerminalAtPath,
    PasteClipboard,
    ReloadDirectory,
    RemoveBookmark,
    SelectAllVisibleEntries,
    SetNotification,
    SetPendingKeySequence,
    SetSort,
    ShowAttributes,
    ToggleHiddenFiles,
    ToggleSearchWorkspaceGrepDisplayMode,
    ToggleSelectionAndAdvance,
    ToggleTransferMode,
    TransferSearchWorkspaceSelection,
    UndoLastOperation,
)
from .input_common import (
    BrowsingCtx,
    BrowsingHandler,
    DispatchedActions,
    current_entry,
    supported,
    visible_paths,
    warn,
)
from .models import AppState, NotificationState
from .search_workspace_helpers import decode_grep_result_path
from .selectors import compute_current_pane_visible_window, select_target_paths

BROWSING_KEYMAP = {
    "up": "cursor_up",
    "shift+up": "cursor_up_selecting",
    "down": "cursor_down",
    "shift+down": "cursor_down_selecting",
    "i": "show_attributes",
    "k": "cursor_up",
    "j": "cursor_down",
    ".": "toggle_hidden",
    "space": "toggle_selection",
    "escape": "clear_selection",
    "/": "begin_filter",
    "left": "go_to_parent",
    "h": "go_to_parent",
    "R": "reload_directory",
    "q": "exit_current_path",
    "p": "toggle_transfer_mode",
    "r": "begin_rename",
    "!": "begin_shell_command",
    ":": "begin_command_palette",
    "s": "cycle_sort",
    "d": "delete_targets",
    "D": "permanent_delete_targets",
    "delete": "delete_targets",
    "shift+delete": "permanent_delete_targets",
    "e": "open_in_editor",
    "O": "open_in_gui_editor",
    "right": "enter_directory",
    "l": "enter_directory",
    "enter": "enter_or_open",
    "t": "open_terminal",
    "f": "begin_file_search",
    "g": "begin_grep_search",
    "a": "select_all",
    "c": "copy_targets",
    "x": "cut_targets",
    "v": "paste_clipboard",
    "z": "undo_last_operation",
    "~": "go_to_home_directory",
    "H": "begin_history_search",
    "b": "begin_bookmark_search",
    "B": "toggle_bookmark",
    "C": "copy_paths_to_clipboard",
    "G": "begin_go_to_path",
    "n": "create_file",
    "N": "create_dir",
    "[": "preview_pageup",
    "]": "preview_pagedown",
    "{": "go_back",
    "}": "go_forward",
    "M": "open_file_manager",
    "T": "open_terminal_window",
    "home": "jump_cursor_start",
    "end": "jump_cursor_end",
    "pageup": "cursor_pageup",
    "pagedown": "cursor_pagedown",
    "o": "open_new_tab",
    "w": "close_current_tab",
    "tab": "activate_next_tab",
    "shift+tab": "activate_previous_tab",
}

SEARCH_WORKSPACE_EXTRA_KEYS = ("m",)


def dispatch_browsing_input(
    state: AppState,
    *,
    key: str,
    character: str | None,
    multi_key_command_dispatch: dict[tuple[str, ...], BrowsingHandler],
) -> DispatchedActions:
    ctx = BrowsingCtx(
        visible_paths=visible_paths(state),
        cursor_entry=current_entry(state),
        target_paths=select_target_paths(state),
        filter_is_active=state.filter.active and bool(state.filter.query),
    )

    if state.pending_key_sequence is not None:
        return dispatch_pending_multi_key_input(
            state,
            ctx,
            key=key,
            multi_key_command_dispatch=multi_key_command_dispatch,
        )

    direct_tab_actions = dispatch_direct_tab_input(state, key=key)
    if direct_tab_actions:
        return direct_tab_actions

    if state.search_workspace is not None:
        return dispatch_search_workspace_input(state, ctx, key=key)

    command = BROWSING_KEYMAP.get(key)
    if command is not None:
        handler = BROWSING_COMMAND_DISPATCH.get(command)
        if handler is not None:
            return handler(state, ctx)

    if key == "enter":
        if ctx.cursor_entry is not None and ctx.cursor_entry.kind == "dir":
            return supported(EnterCursorDirectory())
        if ctx.cursor_entry is not None and ctx.cursor_entry.kind == "file":
            return supported(OpenPathWithDefaultApp(ctx.cursor_entry.path))

    pending = start_multi_key_sequence_if_supported(key, multi_key_command_dispatch)
    if pending is not None:
        return pending

    return ()


def dispatch_search_workspace_input(
    state: AppState,
    ctx: BrowsingCtx,
    *,
    key: str,
) -> DispatchedActions:
    if key in {"up", "k"}:
        return handle_cursor_up(state, ctx)
    if key in {"down", "j"}:
        return handle_cursor_down(state, ctx)
    if key == "pageup":
        return handle_cursor_pageup(state, ctx)
    if key == "pagedown":
        return handle_cursor_pagedown(state, ctx)
    if key == "home":
        return handle_jump_cursor_start(state, ctx)
    if key == "end":
        return handle_jump_cursor_end(state, ctx)
    if key == "space":
        return handle_toggle_selection(state, ctx)
    if key == "escape":
        return supported(ClearSelection())
    if key == "/":
        return supported(BeginFilterInput())
    if key == "s":
        return handle_cycle_sort(state, ctx)
    if key == "m":
        if state.search_workspace is not None and state.search_workspace.kind == "grep":
            return supported(ToggleSearchWorkspaceGrepDisplayMode())
        # For find workspace, 'm' key triggers transfer (move mode)
        if state.search_workspace is not None and state.search_workspace.kind == "find":
            return supported(TransferSearchWorkspaceSelection(mode="move"))
        return ()
    if key == "y":
        # 'y' key triggers transfer (copy mode) for all search workspaces
        return supported(TransferSearchWorkspaceSelection(mode="copy"))
    if key == ":":
        return supported(BeginCommandPalette())
    if key == "enter":
        return handle_enter_search_workspace_file_open(state, ctx)
    if key == "C":
        return supported(CopyPathsToClipboard())
    if key == "w":
        return supported(CloseCurrentTab())
    if key == "tab":
        return supported(ActivateNextTab())
    if key == "shift+tab":
        return supported(ActivatePreviousTab())
    return warn(
        "Search workspace: ↑↓ move | / filter | s sort | m view/find | "
        "y copy | Space select | Enter open | C copy paths"
    )


def handle_enter_search_workspace_file_open(state: AppState, ctx: BrowsingCtx) -> DispatchedActions:
    """Handle Enter key in search workspace to open file."""
    if state.search_workspace is None or state.current_pane.cursor_path is None:
        return warn("No file selected")

    cursor_path = state.current_pane.cursor_path
    if state.search_workspace.kind == "grep":
        decoded = decode_grep_result_path(cursor_path)
        if decoded is not None:
            real_path, line_number = decoded
            return supported(
                OpenPathInGuiEditor(real_path, line_number=line_number, column_number=1)
            )
        if cursor_path:
            return supported(OpenPathInGuiEditor(cursor_path))
        return warn("Invalid grep result path")
    else:
        # Find workspace: open with default app
        return supported(OpenPathWithDefaultApp(cursor_path))


def noop_browsing_handler(_state: AppState, _ctx: BrowsingCtx) -> DispatchedActions:
    return ()


def dispatch_direct_tab_input(state: AppState, *, key: str) -> DispatchedActions:
    if len(key) != 1 or not key.isdigit():
        return ()

    tab_number = 10 if key == "0" else int(key)
    tab_count = len(state.browser_tabs) if state.browser_tabs else 1
    if tab_number > tab_count:
        return warn(f"Tab {tab_number} is not open")
    return supported(ActivateTabByIndex(tab_number - 1))


def simple(action_cls: type[Action]) -> BrowsingHandler:
    def handler(_state: AppState, _ctx: BrowsingCtx) -> DispatchedActions:
        return supported(action_cls())

    return handler


def matching_multi_key_sequences(
    multi_key_command_dispatch: dict[tuple[str, ...], BrowsingHandler],
    prefix: tuple[str, ...],
) -> tuple[tuple[str, ...], ...]:
    return tuple(
        sequence
        for sequence in multi_key_command_dispatch
        if len(sequence) >= len(prefix) and sequence[: len(prefix)] == prefix
    )


def next_multi_key_steps(
    multi_key_command_dispatch: dict[tuple[str, ...], BrowsingHandler],
    prefix: tuple[str, ...],
) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                sequence[len(prefix)]
                for sequence in matching_multi_key_sequences(multi_key_command_dispatch, prefix)
                if len(sequence) > len(prefix)
            }
        )
    )


def start_multi_key_sequence_if_supported(
    key: str,
    multi_key_command_dispatch: dict[tuple[str, ...], BrowsingHandler],
) -> DispatchedActions | None:
    possible_next_keys = next_multi_key_steps(multi_key_command_dispatch, (key,))
    if not possible_next_keys:
        return None
    return supported(
        SetPendingKeySequence(
            keys=(key,),
            possible_next_keys=possible_next_keys,
        )
    )


def insert_clear_pending_key_sequence(actions: DispatchedActions) -> DispatchedActions:
    if not actions:
        return (ClearPendingKeySequence(),)
    if isinstance(actions[0], SetNotification):
        return (actions[0], ClearPendingKeySequence(), *actions[1:])
    return (ClearPendingKeySequence(), *actions)


def dispatch_pending_multi_key_input(
    state: AppState,
    ctx: BrowsingCtx,
    *,
    key: str,
    multi_key_command_dispatch: dict[tuple[str, ...], BrowsingHandler],
) -> DispatchedActions:
    prefix = state.pending_key_sequence.keys
    if key == "escape":
        return supported(ClearPendingKeySequence())

    next_prefix = (*prefix, key)
    handler = multi_key_command_dispatch.get(next_prefix)
    if handler is not None:
        return insert_clear_pending_key_sequence(handler(state, ctx))

    possible_next_keys = next_multi_key_steps(multi_key_command_dispatch, next_prefix)
    if possible_next_keys:
        return supported(
            SetPendingKeySequence(
                keys=next_prefix,
                possible_next_keys=possible_next_keys,
            )
        )

    return (
        SetNotification(
            NotificationState(
                level="warning",
                message=f"No multi-key command matches {''.join(next_prefix)!r}",
            )
        ),
        ClearPendingKeySequence(),
    )


def next_sort_action(state: AppState) -> SetSort:
    cycle = (
        ("name", False),
        ("name", True),
        ("modified", True),
        ("modified", False),
        ("size", True),
        ("size", False),
    )
    current = (state.sort.field, state.sort.descending)
    current_index = cycle.index(current) if current in cycle else 0
    next_field, next_descending = cycle[(current_index + 1) % len(cycle)]
    return SetSort(field=next_field, descending=next_descending)


def handle_cursor_up_selecting(_state: AppState, ctx: BrowsingCtx) -> DispatchedActions:
    return supported(MoveCursorAndSelectRange(delta=-1, visible_paths=ctx.visible_paths))


def handle_cursor_down_selecting(_state: AppState, ctx: BrowsingCtx) -> DispatchedActions:
    return supported(MoveCursorAndSelectRange(delta=1, visible_paths=ctx.visible_paths))


def handle_jump_cursor_start(_state: AppState, ctx: BrowsingCtx) -> DispatchedActions:
    return supported(JumpCursor(position="start", visible_paths=ctx.visible_paths))


def handle_jump_cursor_end(_state: AppState, ctx: BrowsingCtx) -> DispatchedActions:
    return supported(JumpCursor(position="end", visible_paths=ctx.visible_paths))


def handle_cursor_pageup(state: AppState, ctx: BrowsingCtx) -> DispatchedActions:
    page_size = compute_current_pane_visible_window(state.terminal_height)
    return supported(
        MoveCursorByPage(direction="up", page_size=page_size, visible_paths=ctx.visible_paths)
    )


def handle_cursor_pagedown(state: AppState, ctx: BrowsingCtx) -> DispatchedActions:
    page_size = compute_current_pane_visible_window(state.terminal_height)
    return supported(
        MoveCursorByPage(direction="down", page_size=page_size, visible_paths=ctx.visible_paths)
    )


def handle_select_all(_state: AppState, ctx: BrowsingCtx) -> DispatchedActions:
    return supported(SelectAllVisibleEntries(ctx.visible_paths))


def handle_copy_targets(_state: AppState, ctx: BrowsingCtx) -> DispatchedActions:
    return supported(CopyTargets(ctx.target_paths))


def handle_cut_targets(_state: AppState, ctx: BrowsingCtx) -> DispatchedActions:
    return supported(CutTargets(ctx.target_paths))


def handle_create_file(_state: AppState, _ctx: BrowsingCtx) -> DispatchedActions:
    return supported(BeginCreateInput("file"))


def handle_create_dir(_state: AppState, _ctx: BrowsingCtx) -> DispatchedActions:
    return supported(BeginCreateInput("dir"))


def handle_open_terminal_foreground(state: AppState, _ctx: BrowsingCtx) -> DispatchedActions:
    return supported(OpenTerminalAtPath(state.current_path, launch_mode="foreground"))


def handle_open_terminal_window(state: AppState, _ctx: BrowsingCtx) -> DispatchedActions:
    return supported(OpenTerminalAtPath(state.current_path))


def handle_open_file_manager(state: AppState, _ctx: BrowsingCtx) -> DispatchedActions:
    return supported(OpenPathWithDefaultApp(state.current_path))


def handle_cursor_up(state: AppState, ctx: BrowsingCtx) -> DispatchedActions:
    if state.current_pane.selection_anchor_path is not None:
        return supported(ClearSelection(), MoveCursor(delta=-1, visible_paths=ctx.visible_paths))
    return supported(MoveCursor(delta=-1, visible_paths=ctx.visible_paths))


def handle_cursor_down(state: AppState, ctx: BrowsingCtx) -> DispatchedActions:
    if state.current_pane.selection_anchor_path is not None:
        return supported(ClearSelection(), MoveCursor(delta=1, visible_paths=ctx.visible_paths))
    return supported(MoveCursor(delta=1, visible_paths=ctx.visible_paths))


def handle_toggle_selection(state: AppState, ctx: BrowsingCtx) -> DispatchedActions:
    if state.current_pane.cursor_path is not None:
        return supported(
            ToggleSelectionAndAdvance(
                path=state.current_pane.cursor_path,
                visible_paths=ctx.visible_paths,
            )
        )
    return ()


def handle_clear_selection(_state: AppState, ctx: BrowsingCtx) -> DispatchedActions:
    if ctx.filter_is_active:
        return supported(CancelFilterInput())
    return supported(ClearSelection())


def handle_toggle_bookmark(state: AppState, _ctx: BrowsingCtx) -> DispatchedActions:
    if state.current_path in state.config.bookmarks.paths:
        return supported(RemoveBookmark(path=state.current_path))
    return supported(AddBookmark(path=state.current_path))


def handle_begin_rename(_state: AppState, ctx: BrowsingCtx) -> DispatchedActions:
    if not ctx.target_paths:
        return warn("Nothing to rename")
    if len(ctx.target_paths) != 1:
        return warn("Rename requires a single target")
    return supported(BeginRenameInput(ctx.target_paths[0]))


def handle_cycle_sort(state: AppState, _ctx: BrowsingCtx) -> DispatchedActions:
    return supported(next_sort_action(state))


def handle_delete_targets(_state: AppState, ctx: BrowsingCtx) -> DispatchedActions:
    if not ctx.target_paths:
        return warn("Nothing to delete")
    return supported(BeginDeleteTargets(ctx.target_paths, mode="trash"))


def handle_permanent_delete_targets(_state: AppState, ctx: BrowsingCtx) -> DispatchedActions:
    if not ctx.target_paths:
        return warn("Nothing to permanently delete")
    return supported(BeginDeleteTargets(ctx.target_paths, mode="permanent"))


def handle_open_in_editor(_state: AppState, ctx: BrowsingCtx) -> DispatchedActions:
    if ctx.cursor_entry is not None and ctx.cursor_entry.kind == "file":
        return supported(OpenPathInEditor(ctx.cursor_entry.path))
    return warn("Editor launch requires a file")


def handle_open_in_gui_editor(_state: AppState, ctx: BrowsingCtx) -> DispatchedActions:
    if ctx.cursor_entry is not None and ctx.cursor_entry.kind == "file":
        return supported(OpenPathInGuiEditor(ctx.cursor_entry.path))
    return warn("GUI editor launch requires a file")


def handle_enter_directory(_state: AppState, ctx: BrowsingCtx) -> DispatchedActions:
    if ctx.cursor_entry is not None and ctx.cursor_entry.kind == "dir":
        return supported(EnterCursorDirectory())
    return ()


BROWSING_SIMPLE_DISPATCH: dict[str, type[Action]] = {
    "begin_filter": BeginFilterInput,
    "begin_bookmark_search": BeginBookmarkSearch,
    "begin_shell_command": BeginShellCommandInput,
    "begin_command_palette": BeginCommandPalette,
    "begin_file_search": BeginFileSearch,
    "begin_grep_search": BeginGrepSearch,
    "begin_history_search": BeginHistorySearch,
    "begin_go_to_path": BeginGoToPath,
    "go_to_home_directory": GoToHomeDirectory,
    "reload_directory": ReloadDirectory,
    "go_back": GoBack,
    "go_forward": GoForward,
    "go_to_parent": GoToParentDirectory,
    "toggle_hidden": ToggleHiddenFiles,
    "copy_paths_to_clipboard": CopyPathsToClipboard,
    "paste_clipboard": PasteClipboard,
    "undo_last_operation": UndoLastOperation,
    "open_new_tab": OpenNewTab,
    "close_current_tab": CloseCurrentTab,
    "activate_next_tab": ActivateNextTab,
    "activate_previous_tab": ActivatePreviousTab,
    "exit_current_path": ExitCurrentPath,
    "show_attributes": ShowAttributes,
    "toggle_transfer_mode": ToggleTransferMode,
}

BROWSING_PARAM_DISPATCH: dict[str, BrowsingHandler] = {
    "cursor_up_selecting": handle_cursor_up_selecting,
    "cursor_down_selecting": handle_cursor_down_selecting,
    "jump_cursor_start": handle_jump_cursor_start,
    "jump_cursor_end": handle_jump_cursor_end,
    "cursor_pageup": handle_cursor_pageup,
    "cursor_pagedown": handle_cursor_pagedown,
    "select_all": handle_select_all,
    "copy_targets": handle_copy_targets,
    "cut_targets": handle_cut_targets,
    "create_file": handle_create_file,
    "create_dir": handle_create_dir,
    "open_terminal": handle_open_terminal_foreground,
    "open_terminal_window": handle_open_terminal_window,
    "open_file_manager": handle_open_file_manager,
    "preview_pageup": noop_browsing_handler,
    "preview_pagedown": noop_browsing_handler,
}

BROWSING_COMPLEX_DISPATCH: dict[str, BrowsingHandler] = {
    "cursor_up": handle_cursor_up,
    "cursor_down": handle_cursor_down,
    "toggle_selection": handle_toggle_selection,
    "clear_selection": handle_clear_selection,
    "toggle_bookmark": handle_toggle_bookmark,
    "begin_rename": handle_begin_rename,
    "cycle_sort": handle_cycle_sort,
    "delete_targets": handle_delete_targets,
    "permanent_delete_targets": handle_permanent_delete_targets,
    "open_in_editor": handle_open_in_editor,
    "open_in_gui_editor": handle_open_in_gui_editor,
    "enter_directory": handle_enter_directory,
}

BROWSING_COMMAND_DISPATCH: dict[str, BrowsingHandler] = {
    **{name: simple(cls) for name, cls in BROWSING_SIMPLE_DISPATCH.items()},
    **BROWSING_PARAM_DISPATCH,
    **BROWSING_COMPLEX_DISPATCH,
}
