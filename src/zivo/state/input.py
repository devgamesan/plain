"""Keyboard dispatcher that normalizes Textual input into reducer actions."""

import os
import string
from collections.abc import Callable
from dataclasses import dataclass

from .actions import (
    Action,
    ActivateNextTab,
    ActivatePreviousTab,
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
    CancelEmptyTrashConfirmation,
    CancelFilterInput,
    CancelPasteConflict,
    CancelPendingInput,
    CancelShellCommandInput,
    CancelZipCompressConfirmation,
    ClearPendingKeySequence,
    ClearSelection,
    CloseCurrentTab,
    ConfirmArchiveExtract,
    ConfirmDeleteTargets,
    ConfirmEmptyTrash,
    ConfirmFilterInput,
    ConfirmZipCompress,
    CopyPathsToClipboard,
    CopyTargets,
    CutTargets,
    CycleConfigEditorValue,
    CycleFindReplaceField,
    CycleGrepReplaceField,
    CycleGrepReplaceSelectedField,
    CycleGrepSearchField,
    CycleReplaceField,
    DeletePendingInputForward,
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
    MoveCursorByPage,
    MovePendingInputCursor,
    OpenFindResultInEditor,
    OpenGrepResultInEditor,
    OpenNewTab,
    OpenPathInEditor,
    OpenPathWithDefaultApp,
    OpenTerminalAtPath,
    PasteClipboard,
    ReloadDirectory,
    RemoveBookmark,
    ResetHelpBarConfig,
    ResolvePasteConflict,
    SaveConfigEditor,
    SelectAllVisibleEntries,
    SendSplitTerminalInput,
    SetCommandPaletteQuery,
    SetFilterQuery,
    SetFindReplaceField,
    SetGrepReplaceField,
    SetGrepReplaceSelectedField,
    SetGrepSearchField,
    SetNotification,
    SetPendingInputCursor,
    SetPendingInputValue,
    SetPendingKeySequence,
    SetReplaceField,
    SetShellCommandValue,
    SetSort,
    ShowAttributes,
    SubmitCommandPalette,
    SubmitPendingInput,
    SubmitShellCommand,
    ToggleHiddenFiles,
    ToggleSelectionAndAdvance,
    ToggleSplitTerminal,
    UndoLastOperation,
)
from .command_palette import normalize_command_palette_cursor
from .models import (
    AppState,
    DirectoryEntryState,
    FindReplaceFieldId,
    GrepReplaceFieldId,
    GrepReplaceSelectedFieldId,
    GrepSearchFieldId,
    NotificationState,
    ReplaceFieldId,
)
from .reducer_common import format_go_to_path_completion
from .selectors import (
    compute_current_pane_visible_window,
    compute_search_visible_window,
    select_target_paths,
    select_visible_current_entry_states,
)

DispatchedActions = tuple[Action, ...]


@dataclass(frozen=True)
class _BrowsingCtx:
    """_dispatch_browsing_input 内で共有される事前計算コンテキスト."""

    visible_paths: tuple[str, ...]
    cursor_entry: DirectoryEntryState | None
    target_paths: tuple[str, ...]
    filter_is_active: bool


_BrowsingHandler = Callable[[AppState, _BrowsingCtx], DispatchedActions]


def _noop_browsing_handler(_state: AppState, _ctx: _BrowsingCtx) -> DispatchedActions:
    """Consume a browsing key that is handled elsewhere in the UI layer."""

    return ()

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
    "r": "begin_rename",
    "!": "begin_shell_command",
    ":": "begin_command_palette",
    "s": "cycle_sort",
    "d": "delete_targets",
    "D": "permanent_delete_targets",
    "delete": "delete_targets",
    "shift+delete": "permanent_delete_targets",
    "e": "open_in_editor",
    "right": "enter_directory",
    "l": "enter_directory",
    "enter": "enter_or_open",
    "t": "toggle_split_terminal",
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
    "m": "open_file_manager",
    "T": "open_terminal",
    "home": "jump_cursor_start",
    "end": "jump_cursor_end",
    "pageup": "cursor_pageup",
    "pagedown": "cursor_pagedown",
    "o": "open_new_tab",
    "w": "close_current_tab",
    "tab": "activate_next_tab",
    "shift+tab": "activate_previous_tab",
}

CONFLICT_KEYMAP = {
    "escape": "cancel_conflict",
    "o": "overwrite",
    "s": "skip",
    "r": "rename",
}

TERMINAL_KEYMAP = {
    # Actions handled explicitly in _dispatch_split_terminal_input
    "tab": "terminal_tab",
    "ctrl+q": "close_terminal",
    # Keys handled via _TERMINAL_KEY_SEQUENCES (kept here for binding registration)
    "enter": "terminal_enter",
    "backspace": "terminal_backspace",
    "escape": "terminal_escape",
    "delete": "terminal_delete",
    "home": "terminal_home",
    "end": "terminal_end",
    "pageup": "terminal_pageup",
    "pagedown": "terminal_pagedown",
    "up": "terminal_up",
    "down": "terminal_down",
    "left": "terminal_left",
    "right": "terminal_right",
    "ctrl+c": "terminal_ctrl_c",
    # New keys (binding registration only, handled by _TERMINAL_KEY_SEQUENCES)
    "insert": "terminal_passthrough",
    "f1": "terminal_passthrough",
    "f2": "terminal_passthrough",
    "f3": "terminal_passthrough",
    "f4": "terminal_passthrough",
    "f5": "terminal_passthrough",
    "f6": "terminal_passthrough",
    "f7": "terminal_passthrough",
    "f8": "terminal_passthrough",
    "f9": "terminal_passthrough",
    "f10": "terminal_passthrough",
    "f11": "terminal_passthrough",
    "f12": "terminal_passthrough",
    "shift+up": "terminal_passthrough",
    "shift+down": "terminal_passthrough",
    "shift+left": "terminal_passthrough",
    "shift+right": "terminal_passthrough",
    "ctrl+up": "terminal_passthrough",
    "ctrl+down": "terminal_passthrough",
    "ctrl+left": "terminal_passthrough",
    "ctrl+right": "terminal_passthrough",
    "shift+home": "terminal_passthrough",
    "shift+end": "terminal_passthrough",
    "ctrl+home": "terminal_passthrough",
    "ctrl+end": "terminal_passthrough",
    "ctrl+delete": "terminal_passthrough",
    "ctrl+insert": "terminal_passthrough",
    "ctrl+pageup": "terminal_passthrough",
    "ctrl+pagedown": "terminal_passthrough",
    "shift+pageup": "terminal_passthrough",
    "shift+pagedown": "terminal_passthrough",
    "shift+insert": "terminal_passthrough",
    "shift+delete": "terminal_passthrough",
    "ctrl+shift+up": "terminal_passthrough",
    "ctrl+shift+down": "terminal_passthrough",
    "ctrl+shift+left": "terminal_passthrough",
    "ctrl+shift+right": "terminal_passthrough",
    "ctrl+shift+home": "terminal_passthrough",
    "ctrl+shift+end": "terminal_passthrough",
    "ctrl+shift+pageup": "terminal_passthrough",
    "ctrl+shift+pagedown": "terminal_passthrough",
    "ctrl+shift+insert": "terminal_passthrough",
    "ctrl+shift+delete": "terminal_passthrough",
}

_TERMINAL_KEY_SEQUENCES: dict[str, str] = {
    # Escape key
    "escape": "\x1b",
    # Function keys (VT220 / XTerm)
    "f1": "\x1bOP",
    "f2": "\x1bOQ",
    "f3": "\x1bOR",
    "f4": "\x1bOS",
    "f5": "\x1b[15~",
    "f6": "\x1b[17~",
    "f7": "\x1b[18~",
    "f8": "\x1b[19~",
    "f9": "\x1b[20~",
    "f10": "\x1b[21~",
    "f11": "\x1b[23~",
    "f12": "\x1b[24~",
    # Navigation keys
    "insert": "\x1b[2~",
    "delete": "\x1b[3~",
    "home": "\x1b[H",
    "end": "\x1b[F",
    "pageup": "\x1b[5~",
    "pagedown": "\x1b[6~",
    "up": "\x1b[A",
    "down": "\x1b[B",
    "right": "\x1b[C",
    "left": "\x1b[D",
    # Arrow keys with modifiers (XTerm modifiers)
    "shift+up": "\x1b[1;2A",
    "shift+down": "\x1b[1;2B",
    "shift+right": "\x1b[1;2C",
    "shift+left": "\x1b[1;2D",
    "ctrl+up": "\x1b[1;5A",
    "ctrl+down": "\x1b[1;5B",
    "ctrl+right": "\x1b[1;5C",
    "ctrl+left": "\x1b[1;5D",
    "ctrl+shift+up": "\x1b[1;6A",
    "ctrl+shift+down": "\x1b[1;6B",
    "ctrl+shift+right": "\x1b[1;6C",
    "ctrl+shift+left": "\x1b[1;6D",
    # Home/End with modifiers
    "shift+home": "\x1b[1;2H",
    "shift+end": "\x1b[1;2F",
    "ctrl+home": "\x1b[1;5H",
    "ctrl+end": "\x1b[1;5F",
    "ctrl+shift+home": "\x1b[1;6H",
    "ctrl+shift+end": "\x1b[1;6F",
    # PageUp/PageDown with modifiers
    "ctrl+pageup": "\x1b[5;5~",
    "ctrl+pagedown": "\x1b[6;5~",
    "shift+pageup": "\x1b[5;2~",
    "shift+pagedown": "\x1b[6;2~",
    "ctrl+shift+pageup": "\x1b[5;6~",
    "ctrl+shift+pagedown": "\x1b[6;6~",
    # Insert/Delete with modifiers
    "ctrl+insert": "\x1b[2;5~",
    "shift+insert": "\x1b[2;2~",
    "ctrl+delete": "\x1b[3;5~",
    "shift+delete": "\x1b[3;2~",
    "ctrl+shift+insert": "\x1b[2;6~",
    "ctrl+shift+delete": "\x1b[3;6~",
}

PRINTABLE_BINDING_KEYS = tuple((*string.ascii_letters, *string.digits))
PALETTE_EXTRA_KEYS = ("shift+tab",)
_MULTI_KEY_COMMAND_DISPATCH: dict[tuple[str, ...], _BrowsingHandler] = {}


def iter_bound_keys() -> tuple[str, ...]:
    """Return the keys that should be installed as app bindings."""

    return tuple(
        dict.fromkeys(
            (
                *BROWSING_KEYMAP.keys(),
                *CONFLICT_KEYMAP.keys(),
                *TERMINAL_KEYMAP.keys(),
                *PRINTABLE_BINDING_KEYS,
                *PALETTE_EXTRA_KEYS,
                *tuple(
                    dict.fromkeys(
                        key
                        for sequence in _MULTI_KEY_COMMAND_DISPATCH
                        for key in sequence
                    )
                ),
            )
        )
    )


def dispatch_key_input(
    state: AppState,
    *,
    key: str,
    character: str | None = None,
) -> DispatchedActions:
    """データドリブンなキーディスパッチ."""
    character = _normalize_input_character(state, key=key, character=character)

    for condition, dispatcher in _MODE_DISPATCHERS:
        if condition(state):
            return dispatcher(state, key=key, character=character)

    # ここには到達しない（デフォルト条件が必ずマッチする）
    return ()


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


def _dispatch_browsing_input(
    state: AppState, *, key: str, character: str | None
) -> DispatchedActions:
    ctx = _BrowsingCtx(
        visible_paths=_visible_paths(state),
        cursor_entry=_current_entry(state),
        target_paths=select_target_paths(state),
        filter_is_active=state.filter.active and bool(state.filter.query),
    )

    if state.pending_key_sequence is not None:
        return _dispatch_pending_multi_key_input(state, ctx, key=key)

    command = BROWSING_KEYMAP.get(key)

    if command is not None:
        handler = _BROWSING_COMMAND_DISPATCH.get(command)
        if handler is not None:
            return handler(state, ctx)

    # enter キーの生キー特殊処理（enter_or_open コマンドはテーブルに含めない）
    if key == "enter":
        if ctx.cursor_entry is not None and ctx.cursor_entry.kind == "dir":
            return _supported(EnterCursorDirectory())
        if ctx.cursor_entry is not None and ctx.cursor_entry.kind == "file":
            return _supported(OpenPathWithDefaultApp(ctx.cursor_entry.path))

    pending = _start_multi_key_sequence_if_supported(key)
    if pending is not None:
        return pending

    return ()


def _dispatch_split_terminal_input(
    state: AppState,
    *,
    key: str,
    character: str | None,
) -> DispatchedActions:
    command = TERMINAL_KEYMAP.get(key)

    if command == "terminal_tab":
        return _supported(SendSplitTerminalInput("\t"))

    if command == "close_terminal":
        return _supported(ToggleSplitTerminal())

    # Look up escape sequence for special keys (escape, arrows, F-keys, etc.)
    sequence = _TERMINAL_KEY_SEQUENCES.get(key)
    if sequence is not None:
        return _supported(SendSplitTerminalInput(sequence))

    if key == "enter":
        return _supported(SendSplitTerminalInput("\r"))

    if key == "backspace":
        return _supported(SendSplitTerminalInput("\x7f"))

    control_character = _terminal_control_character(key)
    if control_character is not None:
        return _supported(SendSplitTerminalInput(control_character))

    if character and character.isprintable():
        return _supported(SendSplitTerminalInput(character))

    return ()


def _terminal_control_character(key: str) -> str | None:
    if not key.startswith("ctrl+") or key == "ctrl+q":
        return None

    suffix = key[5:]
    if len(suffix) != 1 or not suffix.isalpha():
        return None

    letter = suffix.lower()
    return chr(ord(letter) - ord("a") + 1)


def _active_grep_field_value(state: AppState) -> str:
    if state.command_palette is None:
        return ""
    field = state.command_palette.grep_search_active_field
    if field == "keyword":
        return state.command_palette.grep_search_keyword or state.command_palette.query
    if field == "include":
        return state.command_palette.grep_search_include_extensions
    return state.command_palette.grep_search_exclude_extensions


def _active_replace_field_value(state: AppState) -> str:
    if state.command_palette is None:
        return ""
    field = state.command_palette.replace_active_field
    if field == "find":
        return state.command_palette.replace_find_text
    return state.command_palette.replace_replacement_text


def _active_find_replace_field_value(state: AppState) -> str:
    if state.command_palette is None:
        return ""
    field = state.command_palette.rff_active_field
    if field == "filename":
        return state.command_palette.rff_filename_query
    if field == "find":
        return state.command_palette.rff_find_text
    return state.command_palette.rff_replacement_text


def _active_grep_replace_field_value(state: AppState) -> str:
    if state.command_palette is None:
        return ""
    field = state.command_palette.grf_active_field
    if field == "keyword":
        return state.command_palette.grf_keyword or state.command_palette.query
    if field == "replace":
        return state.command_palette.grf_replacement_text
    if field == "filename":
        return state.command_palette.grf_filename_filter
    if field == "include":
        return state.command_palette.grf_include_extensions
    return state.command_palette.grf_exclude_extensions


def _active_grep_replace_selected_field_value(state: AppState) -> str:
    if state.command_palette is None:
        return ""
    field = state.command_palette.grs_active_field
    if field == "keyword":
        return state.command_palette.grs_keyword or state.command_palette.query
    return state.command_palette.grs_replacement_text


def _palette_extra_rows(palette_source: str | None) -> int:
    if palette_source == "replace_in_found_files":
        return 3
    if palette_source == "replace_in_grep_files":
        return 5
    if palette_source == "grep_replace_selected":
        return 2
    if palette_source in {"grep_search", "replace_text"}:
        return 2
    return 0


def _dispatch_command_palette_input(
    state: AppState,
    *,
    key: str,
    character: str | None,
) -> DispatchedActions:
    palette_source = state.command_palette.source if state.command_palette is not None else None
    search_palette = palette_source in {"file_search", "grep_search"}

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

    if key == "tab" and palette_source == "grep_search":
        return _supported(CycleGrepSearchField(delta=1))

    if key == "shift+tab" and palette_source == "grep_search":
        return _supported(CycleGrepSearchField(delta=-1))

    if key == "tab" and palette_source == "replace_text":
        return _supported(CycleReplaceField(delta=1))

    if key == "shift+tab" and palette_source == "replace_text":
        return _supported(CycleReplaceField(delta=-1))

    if key == "tab" and palette_source == "replace_in_found_files":
        return _supported(CycleFindReplaceField(delta=1))

    if key == "shift+tab" and palette_source == "replace_in_found_files":
        return _supported(CycleFindReplaceField(delta=-1))

    if key == "tab" and palette_source == "replace_in_grep_files":
        return _supported(CycleGrepReplaceField(delta=1))

    if key == "shift+tab" and palette_source == "replace_in_grep_files":
        return _supported(CycleGrepReplaceField(delta=-1))

    if key == "tab" and palette_source == "grep_replace_selected":
        return _supported(CycleGrepReplaceSelectedField(delta=1))

    if key == "shift+tab" and palette_source == "grep_replace_selected":
        return _supported(CycleGrepReplaceSelectedField(delta=-1))

    if key == "up" or (key == "k" and not search_palette):
        return _supported(MoveCommandPaletteCursor(delta=-1))

    if key == "down" or (key == "j" and not search_palette):
        return _supported(MoveCommandPaletteCursor(delta=1))

    if key == "ctrl+n":
        return _supported(MoveCommandPaletteCursor(delta=1))

    if key == "ctrl+p":
        return _supported(MoveCommandPaletteCursor(delta=-1))

    if key == "pageup":
        extra_rows = _palette_extra_rows(palette_source)
        visible = compute_search_visible_window(state.terminal_height, extra_rows=extra_rows)
        return _supported(MoveCommandPaletteCursor(delta=-visible))

    if key == "pagedown":
        extra_rows = _palette_extra_rows(palette_source)
        visible = compute_search_visible_window(state.terminal_height, extra_rows=extra_rows)
        return _supported(MoveCommandPaletteCursor(delta=visible))

    if key == "home":
        return _supported(MoveCommandPaletteCursor(delta=-999999))

    if key == "end":
        return _supported(MoveCommandPaletteCursor(delta=999999))

    if key == "enter":
        return _supported(SubmitCommandPalette())

    if key == "backspace":
        if palette_source == "grep_search":
            return _supported(
                SetGrepSearchField(
                    field=state.command_palette.grep_search_active_field,
                    value=_active_grep_field_value(state)[:-1],
                )
            )
        if palette_source == "replace_text":
            return _supported(
                SetReplaceField(
                    field=state.command_palette.replace_active_field,
                    value=_active_replace_field_value(state)[:-1],
                )
            )
        if palette_source == "replace_in_found_files":
            return _supported(
                SetFindReplaceField(
                    field=state.command_palette.rff_active_field,
                    value=_active_find_replace_field_value(state)[:-1],
                )
            )
        if palette_source == "replace_in_grep_files":
            return _supported(
                SetGrepReplaceField(
                    field=state.command_palette.grf_active_field,
                    value=_active_grep_replace_field_value(state)[:-1],
                )
            )
        if palette_source == "grep_replace_selected":
            return _supported(
                SetGrepReplaceSelectedField(
                    field=state.command_palette.grs_active_field,
                    value=_active_grep_replace_selected_field_value(state)[:-1],
                )
            )
        current_query = state.command_palette.query if state.command_palette is not None else ""
        return _supported(SetCommandPaletteQuery(current_query[:-1]))

    if key == "ctrl+e" and state.command_palette is not None:
        if state.command_palette.source == "grep_search":
            return _supported(OpenGrepResultInEditor())
        if state.command_palette.source == "file_search":
            return _supported(OpenFindResultInEditor())

    if character and character.isprintable():
        if palette_source == "grep_search":
            active_field: GrepSearchFieldId = state.command_palette.grep_search_active_field
            return _supported(
                SetGrepSearchField(
                    field=active_field,
                    value=f"{_active_grep_field_value(state)}{character}",
                )
            )
        if palette_source == "replace_text":
            active_field: ReplaceFieldId = state.command_palette.replace_active_field
            return _supported(
                SetReplaceField(
                    field=active_field,
                    value=f"{_active_replace_field_value(state)}{character}",
                )
            )
        if palette_source == "replace_in_found_files":
            active_field_rff: FindReplaceFieldId = state.command_palette.rff_active_field
            return _supported(
                SetFindReplaceField(
                    field=active_field_rff,
                    value=f"{_active_find_replace_field_value(state)}{character}",
                )
            )
        if palette_source == "replace_in_grep_files":
            active_field_grf: GrepReplaceFieldId = state.command_palette.grf_active_field
            return _supported(
                SetGrepReplaceField(
                    field=active_field_grf,
                    value=f"{_active_grep_replace_field_value(state)}{character}",
                )
            )
        if palette_source == "grep_replace_selected":
            active_field_grs: GrepReplaceSelectedFieldId = state.command_palette.grs_active_field
            return _supported(
                SetGrepReplaceSelectedField(
                    field=active_field_grs,
                    value=f"{_active_grep_replace_selected_field_value(state)}{character}",
                )
            )
        current_query = state.command_palette.query if state.command_palette is not None else ""
        return _supported(SetCommandPaletteQuery(f"{current_query}{character}"))

    if search_palette:
        if state.command_palette is not None and state.command_palette.source == "grep_search":
            return _warn("Use Tab/Shift+Tab, type, arrows, Enter, Ctrl+e, or Esc")
        return _warn("Use arrows, type to filter, Enter, Ctrl+e for editor, or Esc")

    if palette_source == "replace_text":
        return _warn("Use Tab/Shift+Tab, type, arrows or Ctrl+n/p, Enter to apply, or Esc")

    if palette_source == "replace_in_found_files":
        return _warn("Use Tab/Shift+Tab, type, arrows or Ctrl+n/p, Enter to apply, or Esc")

    if palette_source == "replace_in_grep_files":
        return _warn("Use Tab/Shift+Tab, type, arrows or Ctrl+n/p, Enter to apply, or Esc")

    if palette_source == "grep_replace_selected":
        return _warn("Use Tab/Shift+Tab, type, arrows or Ctrl+n/p, Enter to apply, or Esc")

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


def _dispatch_confirm_input(
    state: AppState, *, key: str, character: str | None
) -> DispatchedActions:
    if state.delete_confirmation is not None:
        if key == "escape":
            return _supported(CancelDeleteConfirmation())
        if key == "enter":
            return _supported(ConfirmDeleteTargets())
        return _warn("Use Enter to confirm delete or Esc to cancel")

    if state.empty_trash_confirmation is not None:
        if key == "escape":
            return _supported(CancelEmptyTrashConfirmation())
        if key == "enter":
            return _supported(ConfirmEmptyTrash())
        return _warn("Use Enter to confirm empty trash or Esc to cancel")

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


def _dispatch_input_dialog_input(
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
        pending = state.pending_input
        if pending is None or pending.cursor_pos == 0:
            return _supported()
        pos = pending.cursor_pos
        new_value = pending.value[: pos - 1] + pending.value[pos:]
        return _supported(SetPendingInputValue(new_value, pos - 1))

    if key == "delete":
        return _supported(DeletePendingInputForward())

    if key == "left":
        return _supported(MovePendingInputCursor(delta=-1))

    if key == "right":
        return _supported(MovePendingInputCursor(delta=1))

    if key == "home":
        return _supported(SetPendingInputCursor(cursor_pos=0))

    if key == "end":
        pending = state.pending_input
        end_pos = len(pending.value) if pending is not None else 0
        return _supported(SetPendingInputCursor(cursor_pos=end_pos))

    if key == "ctrl+v":
        return _supported()  # handled by on_key in app.py

    if character and character.isprintable():
        pending = state.pending_input
        if pending is None:
            return _supported()
        pos = pending.cursor_pos
        new_value = pending.value[:pos] + character + pending.value[pos:]
        return _supported(SetPendingInputValue(new_value, pos + 1))

    return _warn("Use Enter to apply, Esc to cancel, or paste")


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


def _dispatch_detail_input(
    state: AppState, *, key: str, character: str | None
) -> DispatchedActions:
    if key in {"enter", "escape"}:
        return _supported(DismissAttributeDialog())

    return _warn("Use Enter or Esc to close the attributes dialog")


def _dispatch_config_input(
    state: AppState, *, key: str, character: str | None
) -> DispatchedActions:
    if key == "escape":
        return _supported(DismissConfigEditor())

    if key in {"up", "k", "ctrl+p"}:
        return _supported(MoveConfigEditorCursor(delta=-1))

    if key in {"down", "j", "ctrl+n"}:
        return _supported(MoveConfigEditorCursor(delta=1))

    if key in {"left", "h"}:
        return _supported(CycleConfigEditorValue(delta=-1))

    if key in {"right", "l", "enter", "space"}:
        return _supported(CycleConfigEditorValue(delta=1))

    if key == "s":
        return _supported(SaveConfigEditor())

    if key == "e":
        return _supported(OpenPathInEditor(state.config_path))

    if key == "r":
        return _supported(ResetHelpBarConfig())

    return _warn(
        "Use ↑↓ or Ctrl+n/p to choose, ←→ or Enter to change, "
        "s to save, e to edit the file, r to reset help, or Esc to close"
    )


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


def _simple(action_cls: type[Action]) -> _BrowsingHandler:
    """ゼロ引数アクションクラスを _BrowsingHandler に適合させるアダプタ."""

    def handler(_state: AppState, _ctx: _BrowsingCtx) -> DispatchedActions:
        return _supported(action_cls())

    return handler


def _warn(message: str) -> DispatchedActions:
    return (SetNotification(NotificationState(level="warning", message=message)),)


def _matching_multi_key_sequences(prefix: tuple[str, ...]) -> tuple[tuple[str, ...], ...]:
    return tuple(
        sequence
        for sequence in _MULTI_KEY_COMMAND_DISPATCH
        if len(sequence) >= len(prefix) and sequence[: len(prefix)] == prefix
    )


def _next_multi_key_steps(prefix: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                sequence[len(prefix)]
                for sequence in _matching_multi_key_sequences(prefix)
                if len(sequence) > len(prefix)
            }
        )
    )


def _start_multi_key_sequence_if_supported(key: str) -> DispatchedActions | None:
    possible_next_keys = _next_multi_key_steps((key,))
    if not possible_next_keys:
        return None
    return _supported(
        SetPendingKeySequence(
            keys=(key,),
            possible_next_keys=possible_next_keys,
        )
    )


def _insert_clear_pending_key_sequence(actions: DispatchedActions) -> DispatchedActions:
    if not actions:
        return (ClearPendingKeySequence(),)
    if isinstance(actions[0], SetNotification):
        return (actions[0], ClearPendingKeySequence(), *actions[1:])
    return (ClearPendingKeySequence(), *actions)


def _dispatch_pending_multi_key_input(
    state: AppState,
    ctx: _BrowsingCtx,
    *,
    key: str,
) -> DispatchedActions:
    prefix = state.pending_key_sequence.keys
    if key == "escape":
        return _supported(ClearPendingKeySequence())

    next_prefix = (*prefix, key)
    handler = _MULTI_KEY_COMMAND_DISPATCH.get(next_prefix)
    if handler is not None:
        return _insert_clear_pending_key_sequence(handler(state, ctx))

    possible_next_keys = _next_multi_key_steps(next_prefix)
    if possible_next_keys:
        return _supported(
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


# ---------------------------------------------------------------------------
# Browsing mode command handlers
# ---------------------------------------------------------------------------

# --- Parameterized handlers (Category B) ---


def _handle_cursor_up_selecting(
    _state: AppState, ctx: _BrowsingCtx
) -> DispatchedActions:
    return _supported(MoveCursorAndSelectRange(delta=-1, visible_paths=ctx.visible_paths))


def _handle_cursor_down_selecting(
    _state: AppState, ctx: _BrowsingCtx
) -> DispatchedActions:
    return _supported(MoveCursorAndSelectRange(delta=1, visible_paths=ctx.visible_paths))


def _handle_jump_cursor_start(
    _state: AppState, ctx: _BrowsingCtx
) -> DispatchedActions:
    return _supported(JumpCursor(position="start", visible_paths=ctx.visible_paths))


def _handle_jump_cursor_end(
    _state: AppState, ctx: _BrowsingCtx
) -> DispatchedActions:
    return _supported(JumpCursor(position="end", visible_paths=ctx.visible_paths))


def _handle_cursor_pageup(state: AppState, ctx: _BrowsingCtx) -> DispatchedActions:
    page_size = compute_current_pane_visible_window(state.terminal_height)
    return _supported(
        MoveCursorByPage(direction="up", page_size=page_size, visible_paths=ctx.visible_paths)
    )


def _handle_cursor_pagedown(state: AppState, ctx: _BrowsingCtx) -> DispatchedActions:
    page_size = compute_current_pane_visible_window(state.terminal_height)
    return _supported(
        MoveCursorByPage(direction="down", page_size=page_size, visible_paths=ctx.visible_paths)
    )


def _handle_select_all(_state: AppState, ctx: _BrowsingCtx) -> DispatchedActions:
    return _supported(SelectAllVisibleEntries(ctx.visible_paths))


def _handle_copy_targets(_state: AppState, ctx: _BrowsingCtx) -> DispatchedActions:
    return _supported(CopyTargets(ctx.target_paths))


def _handle_cut_targets(_state: AppState, ctx: _BrowsingCtx) -> DispatchedActions:
    return _supported(CutTargets(ctx.target_paths))


def _handle_create_file(_state: AppState, _ctx: _BrowsingCtx) -> DispatchedActions:
    return _supported(BeginCreateInput("file"))


def _handle_create_dir(_state: AppState, _ctx: _BrowsingCtx) -> DispatchedActions:
    return _supported(BeginCreateInput("dir"))


def _handle_open_terminal(state: AppState, _ctx: _BrowsingCtx) -> DispatchedActions:
    return _supported(OpenTerminalAtPath(state.current_path))


def _handle_open_file_manager(state: AppState, _ctx: _BrowsingCtx) -> DispatchedActions:
    return _supported(OpenPathWithDefaultApp(state.current_path))


# --- State-dependent handlers (Category C) ---


def _handle_cursor_up(state: AppState, ctx: _BrowsingCtx) -> DispatchedActions:
    if state.current_pane.selection_anchor_path is not None:
        return _supported(
            ClearSelection(),
            MoveCursor(delta=-1, visible_paths=ctx.visible_paths),
        )
    return _supported(MoveCursor(delta=-1, visible_paths=ctx.visible_paths))


def _handle_cursor_down(state: AppState, ctx: _BrowsingCtx) -> DispatchedActions:
    if state.current_pane.selection_anchor_path is not None:
        return _supported(
            ClearSelection(),
            MoveCursor(delta=1, visible_paths=ctx.visible_paths),
        )
    return _supported(MoveCursor(delta=1, visible_paths=ctx.visible_paths))


def _handle_toggle_selection(state: AppState, ctx: _BrowsingCtx) -> DispatchedActions:
    if state.current_pane.cursor_path is not None:
        return _supported(
            ToggleSelectionAndAdvance(
                path=state.current_pane.cursor_path,
                visible_paths=ctx.visible_paths,
            )
        )
    return ()


def _handle_clear_selection(_state: AppState, ctx: _BrowsingCtx) -> DispatchedActions:
    if ctx.filter_is_active:
        return _supported(CancelFilterInput())
    return _supported(ClearSelection())


def _handle_toggle_bookmark(state: AppState, _ctx: _BrowsingCtx) -> DispatchedActions:
    if state.current_path in state.config.bookmarks.paths:
        return _supported(RemoveBookmark(path=state.current_path))
    return _supported(AddBookmark(path=state.current_path))


def _handle_begin_rename(_state: AppState, ctx: _BrowsingCtx) -> DispatchedActions:
    if not ctx.target_paths:
        return _warn("Nothing to rename")
    if len(ctx.target_paths) != 1:
        return _warn("Rename requires a single target")
    return _supported(BeginRenameInput(ctx.target_paths[0]))


def _handle_cycle_sort(state: AppState, _ctx: _BrowsingCtx) -> DispatchedActions:
    return _supported(_next_sort_action(state))


def _handle_delete_targets(_state: AppState, ctx: _BrowsingCtx) -> DispatchedActions:
    if not ctx.target_paths:
        return _warn("Nothing to delete")
    return _supported(BeginDeleteTargets(ctx.target_paths, mode="trash"))


def _handle_permanent_delete_targets(
    _state: AppState, ctx: _BrowsingCtx
) -> DispatchedActions:
    if not ctx.target_paths:
        return _warn("Nothing to permanently delete")
    return _supported(BeginDeleteTargets(ctx.target_paths, mode="permanent"))


def _handle_open_in_editor(_state: AppState, ctx: _BrowsingCtx) -> DispatchedActions:
    if ctx.cursor_entry is not None and ctx.cursor_entry.kind == "file":
        return _supported(OpenPathInEditor(ctx.cursor_entry.path))
    return _warn("Editor launch requires a file")


def _handle_enter_directory(_state: AppState, ctx: _BrowsingCtx) -> DispatchedActions:
    if ctx.cursor_entry is not None and ctx.cursor_entry.kind == "dir":
        return _supported(EnterCursorDirectory())
    return ()


# ---------------------------------------------------------------------------
# Browsing mode dispatch tables
# ---------------------------------------------------------------------------

_BROWSING_SIMPLE_DISPATCH: dict[str, type[Action]] = {
    "begin_filter": BeginFilterInput,
    "begin_bookmark_search": BeginBookmarkSearch,
    "begin_shell_command": BeginShellCommandInput,
    "begin_command_palette": BeginCommandPalette,
    "begin_file_search": BeginFileSearch,
    "begin_grep_search": BeginGrepSearch,
    "begin_history_search": BeginHistorySearch,
    "begin_go_to_path": BeginGoToPath,
    "go_to_home_directory": GoToHomeDirectory,
    "toggle_split_terminal": ToggleSplitTerminal,
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
}

_BROWSING_PARAM_DISPATCH: dict[str, _BrowsingHandler] = {
    "cursor_up_selecting": _handle_cursor_up_selecting,
    "cursor_down_selecting": _handle_cursor_down_selecting,
    "jump_cursor_start": _handle_jump_cursor_start,
    "jump_cursor_end": _handle_jump_cursor_end,
    "cursor_pageup": _handle_cursor_pageup,
    "cursor_pagedown": _handle_cursor_pagedown,
    "select_all": _handle_select_all,
    "copy_targets": _handle_copy_targets,
    "cut_targets": _handle_cut_targets,
    "create_file": _handle_create_file,
    "create_dir": _handle_create_dir,
    "open_terminal": _handle_open_terminal,
    "open_file_manager": _handle_open_file_manager,
    "preview_pageup": _noop_browsing_handler,
    "preview_pagedown": _noop_browsing_handler,
}

_BROWSING_COMPLEX_DISPATCH: dict[str, _BrowsingHandler] = {
    "cursor_up": _handle_cursor_up,
    "cursor_down": _handle_cursor_down,
    "toggle_selection": _handle_toggle_selection,
    "clear_selection": _handle_clear_selection,
    "toggle_bookmark": _handle_toggle_bookmark,
    "begin_rename": _handle_begin_rename,
    "cycle_sort": _handle_cycle_sort,
    "delete_targets": _handle_delete_targets,
    "permanent_delete_targets": _handle_permanent_delete_targets,
    "open_in_editor": _handle_open_in_editor,
    "enter_directory": _handle_enter_directory,
}

_BROWSING_COMMAND_DISPATCH: dict[str, _BrowsingHandler] = {
    **{name: _simple(cls) for name, cls in _BROWSING_SIMPLE_DISPATCH.items()},
    **_BROWSING_PARAM_DISPATCH,
    **_BROWSING_COMPLEX_DISPATCH,
}


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


# モード判定条件とディスパッチャのタプルリスト
# 各タプル: (条件述語関数, ディスパッチャ関数)
# タプルの順序が優先順位を表す
_MODE_DISPATCHERS = (
    # ターミナルフォーカスは ui_mode より優先
    (lambda state: _terminal_has_focus(state), _dispatch_split_terminal_input),
    # ui_mode ベースのディスパッチ
    (lambda state: state.ui_mode == "FILTER", _dispatch_filter_input),
    (lambda state: state.ui_mode == "CONFIRM", _dispatch_confirm_input),
    (lambda state: state.ui_mode == "DETAIL", _dispatch_detail_input),
    (lambda state: state.ui_mode == "CONFIG", _dispatch_config_input),
    (
        lambda state: state.ui_mode == "BUSY",
        lambda state, **_: _warn("Input ignored while processing"),
    ),
    (lambda state: state.ui_mode == "PALETTE", _dispatch_command_palette_input),
    (
        lambda state: state.ui_mode in {"RENAME", "CREATE", "EXTRACT", "ZIP"},
        _dispatch_input_dialog_input,
    ),
    (lambda state: state.ui_mode == "SHELL", _dispatch_shell_command_input),
    # デフォルト（BROWSING）
    (lambda state: True, _dispatch_browsing_input),
)
