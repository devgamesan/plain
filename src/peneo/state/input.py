"""Keyboard dispatcher that normalizes Textual input into reducer actions."""

import os
import string

from .actions import (
    Action,
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
    CancelArchiveExtractConfirmation,
    CancelCommandPalette,
    CancelDeleteConfirmation,
    CancelFilterInput,
    CancelPasteConflict,
    CancelPendingInput,
    CancelShellCommandInput,
    CancelZipCompressConfirmation,
    ClearSelection,
    ConfirmArchiveExtract,
    ConfirmDeleteTargets,
    ConfirmFilterInput,
    ConfirmZipCompress,
    CopyPathsToClipboard,
    CopyTargets,
    CutTargets,
    CycleConfigEditorValue,
    DismissAttributeDialog,
    DismissConfigEditor,
    DismissNameConflict,
    EnterCursorDirectory,
    ExitCurrentPath,
    GoBack,
    GoForward,
    GoToHomeDirectory,
    GoToParentDirectory,
    JumpCursor,
    MoveCommandPaletteCursor,
    MoveConfigEditorCursor,
    MoveCursor,
    MoveCursorAndSelectRange,
    OpenPathInEditor,
    OpenPathWithDefaultApp,
    PasteClipboard,
    PasteFromClipboardToTerminal,
    ReloadDirectory,
    RemoveBookmark,
    ResolvePasteConflict,
    SaveConfigEditor,
    SelectAllVisibleEntries,
    SendSplitTerminalInput,
    SetCommandPaletteQuery,
    SetFilterQuery,
    SetNotification,
    SetPendingInputValue,
    SetShellCommandValue,
    SetSort,
    ShowAttributes,
    SubmitCommandPalette,
    SubmitPendingInput,
    SubmitShellCommand,
    ToggleHiddenFiles,
    ToggleSelectionAndAdvance,
    ToggleSplitTerminal,
)
from .command_palette import normalize_command_palette_cursor
from .models import AppState, DirectoryEntryState, NotificationState
from .reducer_common import format_go_to_path_completion
from .selectors import (
    compute_search_visible_window,
    select_target_paths,
    select_visible_current_entry_states,
)

DispatchedActions = tuple[Action, ...]

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
    "backspace": "go_to_parent",
    "h": "go_to_parent",
    "f5": "reload_directory",
    "q": "exit_current_path",
    "f2": "begin_rename",
    "!": "begin_shell_command",
    ":": "begin_command_palette",
    "s": "cycle_sort",
    "d": "toggle_directories_first",
    "delete": "delete_targets",
    "e": "open_in_editor",
    "right": "enter_directory",
    "l": "enter_directory",
    "enter": "enter_or_open",
    "ctrl+t": "toggle_split_terminal",
    "ctrl+f": "begin_file_search",
    "ctrl+g": "begin_grep_search",
    "ctrl+a": "select_all",
    "y": "copy_targets",
    "x": "cut_targets",
    "p": "paste_clipboard",
    "home": "cursor_home",
    "end": "cursor_end",
    "alt+left": "go_back",
    "alt+right": "go_forward",
    "alt+home": "go_to_home_directory",
    "ctrl+o": "begin_history_search",
    "ctrl+b": "begin_bookmark_search",
    "b": "toggle_bookmark",
    "c": "copy_paths_to_clipboard",
    "ctrl+j": "begin_go_to_path",
    "ctrl+n": "create_file",
    "ctrl+d": "create_dir",
}

CONFLICT_KEYMAP = {
    "escape": "cancel_conflict",
    "o": "overwrite",
    "s": "skip",
    "r": "rename",
}

TERMINAL_KEYMAP = {
    "tab": "terminal_tab",
    "ctrl+t": "toggle_terminal",
    "ctrl+v": "paste_from_clipboard",
    "enter": "terminal_enter",
    "backspace": "terminal_backspace",
    "delete": "terminal_delete",
    "escape": "terminal_escape",
    "home": "terminal_home",
    "end": "terminal_end",
    "pageup": "terminal_pageup",
    "pagedown": "terminal_pagedown",
    "up": "terminal_up",
    "down": "terminal_down",
    "left": "terminal_left",
    "right": "terminal_right",
    "ctrl+c": "terminal_ctrl_c",
}

PRINTABLE_BINDING_KEYS = tuple((*string.ascii_letters, *string.digits))


def iter_bound_keys() -> tuple[str, ...]:
    """Return the keys that should be installed as app bindings."""

    return tuple(
        dict.fromkeys(
            (
                *BROWSING_KEYMAP.keys(),
                *CONFLICT_KEYMAP.keys(),
                *TERMINAL_KEYMAP.keys(),
                *PRINTABLE_BINDING_KEYS,
            )
        )
    )


def dispatch_key_input(
    state: AppState,
    *,
    key: str,
    character: str | None = None,
) -> DispatchedActions:
    """Return reducer actions for the current mode and key press."""

    character = _normalize_input_character(state, key=key, character=character)

    if _terminal_has_focus(state):
        return _dispatch_split_terminal_input(key=key, character=character)

    if state.ui_mode == "FILTER":
        return _dispatch_filter_input(state, key=key, character=character)

    if state.ui_mode == "CONFIRM":
        return _dispatch_confirm_input(state, key)

    if state.ui_mode == "DETAIL":
        return _dispatch_detail_input(key)

    if state.ui_mode == "CONFIG":
        return _dispatch_config_input(state, key)

    if state.ui_mode == "BUSY":
        return _warn("Input ignored while processing")

    if state.ui_mode == "PALETTE":
        return _dispatch_command_palette_input(state, key=key, character=character)

    if state.ui_mode in {"RENAME", "CREATE", "EXTRACT", "ZIP"}:
        return _dispatch_pending_input(state, key=key, character=character)

    if state.ui_mode == "SHELL":
        return _dispatch_shell_command_input(state, key=key, character=character)

    return _dispatch_browsing_input(state, key)


def _normalize_input_character(
    state: AppState,
    *,
    key: str,
    character: str | None,
) -> str | None:
    resolved_character = _resolve_printable_character(key=key, character=character)
    if resolved_character is None:
        return None

    if _terminal_has_focus(state):
        return resolved_character

    if state.ui_mode in {"PALETTE", "RENAME", "CREATE", "EXTRACT", "ZIP", "SHELL"}:
        return resolved_character

    if state.ui_mode == "FILTER" and not resolved_character.isspace():
        return resolved_character

    return None


def _resolve_printable_character(*, key: str, character: str | None) -> str | None:
    if character is not None and character.isprintable():
        return character

    if key == "space":
        return " "

    if len(key) == 1 and key.isprintable():
        return key

    return None


def _dispatch_browsing_input(state: AppState, key: str) -> DispatchedActions:
    visible_paths = _visible_paths(state)
    cursor_entry = _current_entry(state)
    target_paths = select_target_paths(state)
    filter_is_active = state.filter.active and bool(state.filter.query)
    command = BROWSING_KEYMAP.get(key)

    if command == "cursor_up":
        if state.current_pane.selection_anchor_path is not None:
            return _supported(
                ClearSelection(),
                MoveCursor(delta=-1, visible_paths=visible_paths),
            )
        return _supported(MoveCursor(delta=-1, visible_paths=visible_paths))

    if command == "cursor_down":
        if state.current_pane.selection_anchor_path is not None:
            return _supported(
                ClearSelection(),
                MoveCursor(delta=1, visible_paths=visible_paths),
            )
        return _supported(MoveCursor(delta=1, visible_paths=visible_paths))

    if command == "cursor_up_selecting":
        return _supported(
            MoveCursorAndSelectRange(delta=-1, visible_paths=visible_paths)
        )

    if command == "cursor_down_selecting":
        return _supported(
            MoveCursorAndSelectRange(delta=1, visible_paths=visible_paths)
        )

    if command == "cursor_home":
        return _supported(JumpCursor(position="start", visible_paths=visible_paths))

    if command == "cursor_end":
        return _supported(JumpCursor(position="end", visible_paths=visible_paths))

    if command == "toggle_selection" and state.current_pane.cursor_path is not None:
        return _supported(
            ToggleSelectionAndAdvance(
                path=state.current_pane.cursor_path,
                visible_paths=visible_paths,
            )
        )

    if command == "clear_selection":
        if filter_is_active:
            return _supported(CancelFilterInput())
        return _supported(ClearSelection())

    if command == "select_all":
        return _supported(SelectAllVisibleEntries(visible_paths))

    if command == "begin_filter":
        return _supported(BeginFilterInput())

    if command == "begin_bookmark_search":
        return _supported(BeginBookmarkSearch())

    if command == "toggle_bookmark":
        if state.current_path in state.config.bookmarks.paths:
            return _supported(RemoveBookmark(path=state.current_path))
        return _supported(AddBookmark(path=state.current_path))

    if command == "copy_targets":
        return _supported(CopyTargets(target_paths))

    if command == "cut_targets":
        return _supported(CutTargets(target_paths))

    if command == "copy_paths_to_clipboard":
        return _supported(CopyPathsToClipboard())

    if command == "paste_clipboard":
        return _supported(PasteClipboard())

    if command == "go_back":
        return _supported(GoBack())

    if command == "go_forward":
        return _supported(GoForward())

    if command == "go_to_parent":
        return _supported(GoToParentDirectory())

    if command == "reload_directory":
        return _supported(ReloadDirectory())

    if command == "begin_rename":
        if not target_paths:
            return _warn("Nothing to rename")
        if len(target_paths) != 1:
            return _warn("Rename requires a single target")
        return _supported(BeginRenameInput(target_paths[0]))

    if command == "begin_shell_command":
        return _supported(BeginShellCommandInput())

    if command == "begin_command_palette":
        return _supported(BeginCommandPalette())

    if command == "begin_file_search":
        return _supported(BeginFileSearch())

    if command == "begin_grep_search":
        return _supported(BeginGrepSearch())

    if command == "begin_history_search":
        return _supported(BeginHistorySearch())

    if command == "begin_go_to_path":
        return _supported(BeginGoToPath())

    if command == "go_to_home_directory":
        return _supported(GoToHomeDirectory())

    if command == "create_file":
        return _supported(BeginCreateInput("file"))

    if command == "create_dir":
        return _supported(BeginCreateInput("dir"))

    if command == "toggle_split_terminal":
        return _supported(ToggleSplitTerminal())

    if command == "exit_current_path":
        return _supported(ExitCurrentPath())

    if command == "cycle_sort":
        return _supported(_next_sort_action(state))

    if command == "toggle_directories_first":
        return _supported(
            SetSort(
                field=state.sort.field,
                descending=state.sort.descending,
                directories_first=not state.sort.directories_first,
            )
        )

    if command == "toggle_hidden":
        return _supported(ToggleHiddenFiles())

    if command == "delete_targets":
        if not target_paths:
            return _warn("Nothing to delete")
        return _supported(BeginDeleteTargets(target_paths))

    if command == "show_attributes":
        return _supported(ShowAttributes())

    if command == "open_in_editor":
        if cursor_entry is not None and cursor_entry.kind == "file":
            return _supported(OpenPathInEditor(cursor_entry.path))
        return _warn("Editor launch requires a file")

    if command == "enter_directory":
        if cursor_entry is not None and cursor_entry.kind == "dir":
            return _supported(EnterCursorDirectory())
        return ()

    if key == "enter":
        if cursor_entry is not None and cursor_entry.kind == "dir":
            return _supported(EnterCursorDirectory())
        if cursor_entry is not None and cursor_entry.kind == "file":
            return _supported(OpenPathWithDefaultApp(cursor_entry.path))
        return ()

    return ()


def _dispatch_split_terminal_input(
    *,
    key: str,
    character: str | None,
) -> DispatchedActions:
    command = TERMINAL_KEYMAP.get(key)

    if command == "terminal_tab":
        return _supported(SendSplitTerminalInput("\t"))

    if command == "toggle_terminal":
        return _supported(ToggleSplitTerminal())

    if command == "paste_from_clipboard":
        return _supported(PasteFromClipboardToTerminal())

    if command == "terminal_escape":
        return _supported(ToggleSplitTerminal())

    if key == "enter":
        return _supported(SendSplitTerminalInput("\r"))

    if key == "backspace":
        return _supported(SendSplitTerminalInput("\x7f"))

    if key == "delete":
        return _supported(SendSplitTerminalInput("\x1b[3~"))

    if key == "escape":
        return _supported(SendSplitTerminalInput("\x1b"))

    if key == "home":
        return _supported(SendSplitTerminalInput("\x1b[H"))

    if key == "end":
        return _supported(SendSplitTerminalInput("\x1b[F"))

    if key == "pageup":
        return _supported(SendSplitTerminalInput("\x1b[5~"))

    if key == "pagedown":
        return _supported(SendSplitTerminalInput("\x1b[6~"))

    if key == "up":
        return _supported(SendSplitTerminalInput("\x1b[A"))

    if key == "down":
        return _supported(SendSplitTerminalInput("\x1b[B"))

    if key == "left":
        return _supported(SendSplitTerminalInput("\x1b[D"))

    if key == "right":
        return _supported(SendSplitTerminalInput("\x1b[C"))

    if key == "ctrl+c":
        return _supported(SendSplitTerminalInput("\x03"))

    control_character = _terminal_control_character(key)
    if control_character is not None:
        return _supported(SendSplitTerminalInput(control_character))

    if character and character.isprintable():
        return _supported(SendSplitTerminalInput(character))

    return ()


def _terminal_control_character(key: str) -> str | None:
    if not key.startswith("ctrl+") or key in ("ctrl+t", "ctrl+v"):
        return None

    suffix = key[5:]
    if len(suffix) != 1 or not suffix.isalpha():
        return None

    letter = suffix.lower()
    return chr(ord(letter) - ord("a") + 1)

def _dispatch_command_palette_input(
    state: AppState,
    *,
    key: str,
    character: str | None,
) -> DispatchedActions:
    if (
        key == "tab"
        and state.command_palette is not None
        and state.command_palette.source == "go_to_path"
    ):
        candidates = state.command_palette.go_to_path_candidates
        if not candidates:
            return _warn("No matching directory to complete")

        selected_path = candidates[
            normalize_command_palette_cursor(state, state.command_palette.cursor_index)
        ]
        completed_query = format_go_to_path_completion(
            selected_path,
            state.command_palette.query,
            state.current_path,
            append_separator=len(candidates) == 1,
        )
        if len(candidates) == 1 and completed_query != os.sep:
            completed_query = completed_query.rstrip(os.sep) + os.sep
        return _supported(SetCommandPaletteQuery(completed_query))

    if key == "escape":
        return _supported(CancelCommandPalette())

    if key in {"up", "k"}:
        return _supported(MoveCommandPaletteCursor(delta=-1))

    if key in {"down", "j"}:
        return _supported(MoveCommandPaletteCursor(delta=1))

    if key == "pageup":
        visible = compute_search_visible_window(state.terminal_height)
        return _supported(MoveCommandPaletteCursor(delta=-visible))

    if key == "pagedown":
        visible = compute_search_visible_window(state.terminal_height)
        return _supported(MoveCommandPaletteCursor(delta=visible))

    if key == "home":
        return _supported(MoveCommandPaletteCursor(delta=-999999))

    if key == "end":
        return _supported(MoveCommandPaletteCursor(delta=999999))

    if key == "enter":
        return _supported(SubmitCommandPalette())

    if key == "backspace":
        current_query = state.command_palette.query if state.command_palette is not None else ""
        return _supported(SetCommandPaletteQuery(current_query[:-1]))

    if character and character.isprintable():
        current_query = state.command_palette.query if state.command_palette is not None else ""
        return _supported(SetCommandPaletteQuery(f"{current_query}{character}"))

    return _warn("Use arrows, type to filter, Enter to run, or Esc to cancel")


def _dispatch_filter_input(
    state: AppState,
    *,
    key: str,
    character: str | None,
) -> DispatchedActions:
    if key == "escape":
        return _supported(CancelFilterInput())

    if key in {"down", "enter"}:
        return _supported(ConfirmFilterInput())

    if key == "backspace":
        next_query = state.filter.query[:-1]
        return _supported(SetFilterQuery(next_query, active=bool(next_query)))

    if character and character.isprintable() and not character.isspace():
        return _supported(SetFilterQuery(f"{state.filter.query}{character}", active=True))

    return _warn("This key is unavailable while editing the filter")


def _dispatch_confirm_input(state: AppState, key: str) -> DispatchedActions:
    if state.delete_confirmation is not None:
        if key == "escape":
            return _supported(CancelDeleteConfirmation())
        if key == "enter":
            return _supported(ConfirmDeleteTargets())
        return _warn("Use Enter to confirm delete or Esc to cancel")

    if state.archive_extract_confirmation is not None:
        if key == "escape":
            return _supported(CancelArchiveExtractConfirmation())
        if key == "enter":
            return _supported(ConfirmArchiveExtract())
        return _warn("Use Enter to continue extraction or Esc to return")

    if state.zip_compress_confirmation is not None:
        if key == "escape":
            return _supported(CancelZipCompressConfirmation())
        if key == "enter":
            return _supported(ConfirmZipCompress())
        return _warn("Use Enter to overwrite the zip or Esc to return")

    if state.name_conflict is not None:
        if key in {"enter", "escape"}:
            return _supported(DismissNameConflict())
        return _warn("Use Enter or Esc to return to name editing")

    if key == "escape":
        return _supported(CancelPasteConflict())

    if key == "o":
        return _supported(ResolvePasteConflict("overwrite"))

    if key == "s":
        return _supported(ResolvePasteConflict("skip"))

    if key == "r":
        return _supported(ResolvePasteConflict("rename"))

    return _warn("Use o, s, r, or Esc while resolving paste conflicts")


def _dispatch_pending_input(
    state: AppState,
    *,
    key: str,
    character: str | None,
) -> DispatchedActions:
    if key == "escape":
        return _supported(CancelPendingInput())

    if key == "enter":
        return _supported(SubmitPendingInput())

    if key == "backspace":
        current_value = state.pending_input.value if state.pending_input is not None else ""
        return _supported(SetPendingInputValue(current_value[:-1]))

    if character and character.isprintable():
        current_value = state.pending_input.value if state.pending_input is not None else ""
        return _supported(SetPendingInputValue(f"{current_value}{character}"))

    return _warn("Use Enter to apply or Esc to cancel")


def _dispatch_shell_command_input(
    state: AppState,
    *,
    key: str,
    character: str | None,
) -> DispatchedActions:
    if key == "escape":
        return _supported(CancelShellCommandInput())

    if key == "enter":
        return _supported(SubmitShellCommand())

    if key == "backspace":
        current_command = state.shell_command.command if state.shell_command is not None else ""
        return _supported(SetShellCommandValue(current_command[:-1]))

    if character and character.isprintable():
        current_command = state.shell_command.command if state.shell_command is not None else ""
        return _supported(SetShellCommandValue(f"{current_command}{character}"))

    return _warn("Use Enter to run or Esc to cancel")


def _dispatch_detail_input(key: str) -> DispatchedActions:
    if key in {"enter", "escape"}:
        return _supported(DismissAttributeDialog())

    return _warn("Use Enter or Esc to close the attributes dialog")


def _dispatch_config_input(state: AppState, key: str) -> DispatchedActions:
    if key == "escape":
        return _supported(DismissConfigEditor())

    if key in {"up", "k"}:
        return _supported(MoveConfigEditorCursor(delta=-1))

    if key in {"down", "j"}:
        return _supported(MoveConfigEditorCursor(delta=1))

    if key in {"left", "h"}:
        return _supported(CycleConfigEditorValue(delta=-1))

    if key in {"right", "l", "enter", "space"}:
        return _supported(CycleConfigEditorValue(delta=1))

    if key == "s":
        return _supported(SaveConfigEditor())

    if key == "e":
        return _supported(OpenPathInEditor(state.config_path))

    return _warn("Use arrows to change values, s to save, e to edit the file, or Esc to close")


def _visible_paths(state: AppState) -> tuple[str, ...]:
    return tuple(entry.path for entry in select_visible_current_entry_states(state))


def _current_entry(state: AppState) -> DirectoryEntryState | None:
    cursor_path = state.current_pane.cursor_path
    for entry in select_visible_current_entry_states(state):
        if entry.path == cursor_path:
            return entry
    return None


def _supported(*actions: Action) -> DispatchedActions:
    return (SetNotification(None), *actions)


def _warn(message: str) -> DispatchedActions:
    return (SetNotification(NotificationState(level="warning", message=message)),)


def _terminal_has_focus(state: AppState) -> bool:
    return (
        state.ui_mode == "BROWSING"
        and state.split_terminal.visible
        and state.split_terminal.focus_target == "terminal"
    )


def _next_sort_action(state: AppState) -> SetSort:
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
    return SetSort(
        field=next_field,
        descending=next_descending,
    )
