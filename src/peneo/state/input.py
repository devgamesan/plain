"""Keyboard dispatcher that normalizes Textual input into reducer actions."""

from .actions import (
    Action,
    BeginCommandPalette,
    BeginDeleteTargets,
    BeginFilterInput,
    BeginRenameInput,
    CancelCommandPalette,
    CancelDeleteConfirmation,
    CancelFilterInput,
    CancelPasteConflict,
    CancelPendingInput,
    ClearSelection,
    ConfirmDeleteTargets,
    ConfirmFilterInput,
    CopyTargets,
    CutTargets,
    DismissNameConflict,
    EnterCursorDirectory,
    GoToParentDirectory,
    MoveCommandPaletteCursor,
    MoveCursor,
    OpenPathInEditor,
    OpenPathWithDefaultApp,
    PasteClipboard,
    ReloadDirectory,
    ResolvePasteConflict,
    SetCommandPaletteQuery,
    SetFilterQuery,
    SetNotification,
    SetPendingInputValue,
    SetSort,
    SubmitCommandPalette,
    SubmitPendingInput,
    ToggleSelectionAndAdvance,
)
from .models import AppState, DirectoryEntryState, NotificationState
from .selectors import select_target_paths, select_visible_current_entry_states

DispatchedActions = tuple[Action, ...]

BROWSING_KEYMAP = {
    "up": "cursor_up",
    "down": "cursor_down",
    "k": "cursor_up",
    "j": "cursor_down",
    "space": "toggle_selection",
    "escape": "clear_selection",
    "/": "begin_filter",
    "left": "go_to_parent",
    "backspace": "go_to_parent",
    "h": "go_to_parent",
    "f5": "reload_directory",
    "f2": "begin_rename",
    ":": "begin_command_palette",
    "s": "cycle_sort",
    "d": "toggle_directories_first",
    "delete": "delete_targets",
    "e": "open_in_editor",
    "right": "enter_directory",
    "l": "enter_directory",
    "enter": "enter_or_open",
    "y": "copy_targets",
    "x": "cut_targets",
    "p": "paste_clipboard",
}

CONFLICT_KEYMAP = {
    "escape": "cancel_conflict",
    "o": "overwrite",
    "s": "skip",
    "r": "rename",
}


def iter_bound_keys() -> tuple[str, ...]:
    """Return the keys that should be installed as app bindings."""

    return tuple(dict.fromkeys((*BROWSING_KEYMAP.keys(), *CONFLICT_KEYMAP.keys())))


def dispatch_key_input(
    state: AppState,
    *,
    key: str,
    character: str | None = None,
) -> DispatchedActions:
    """Return reducer actions for the current mode and key press."""

    if state.ui_mode == "FILTER":
        return _dispatch_filter_input(state, key=key, character=character)

    if state.ui_mode == "CONFIRM":
        return _dispatch_confirm_input(state, key)

    if state.ui_mode == "BUSY":
        return _warn("Input ignored while processing")

    if state.ui_mode == "PALETTE":
        return _dispatch_command_palette_input(state, key=key, character=character)

    if state.ui_mode in {"RENAME", "CREATE"}:
        return _dispatch_pending_input(state, key=key, character=character)

    return _dispatch_browsing_input(state, key)


def _dispatch_browsing_input(state: AppState, key: str) -> DispatchedActions:
    visible_paths = _visible_paths(state)
    cursor_entry = _current_entry(state)
    target_paths = select_target_paths(state)
    filter_is_active = state.filter.active and bool(state.filter.query)
    command = BROWSING_KEYMAP.get(key)

    if command == "cursor_up":
        return _supported(MoveCursor(delta=-1, visible_paths=visible_paths))

    if command == "cursor_down":
        return _supported(MoveCursor(delta=1, visible_paths=visible_paths))

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

    if command == "begin_filter":
        return _supported(BeginFilterInput())

    if command == "copy_targets":
        return _supported(CopyTargets(target_paths))

    if command == "cut_targets":
        return _supported(CutTargets(target_paths))

    if command == "paste_clipboard":
        return _supported(PasteClipboard())

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

    if command == "begin_command_palette":
        return _supported(BeginCommandPalette())

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

    if command == "delete_targets":
        if not target_paths:
            return _warn("Nothing to delete")
        return _supported(BeginDeleteTargets(target_paths))

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


def _dispatch_command_palette_input(
    state: AppState,
    *,
    key: str,
    character: str | None,
) -> DispatchedActions:
    if key == "escape":
        return _supported(CancelCommandPalette())

    if key in {"up", "k"}:
        return _supported(MoveCommandPaletteCursor(delta=-1))

    if key in {"down", "j"}:
        return _supported(MoveCommandPaletteCursor(delta=1))

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
