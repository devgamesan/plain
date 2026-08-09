"""Keyboard dispatcher for the bulk rename overlay."""

from .actions import (
    ApplyBulkRename,
    ApplyBulkRenameFindReplace,
    CancelBulkRename,
    CycleBulkRenameField,
    DeleteBulkRenameTextBackward,
    DeleteBulkRenameTextForward,
    MoveBulkRenameCursor,
    MoveBulkRenameTextCursor,
    PasteIntoBulkRename,
    SetBulkRenameEditing,
    SetBulkRenameFindReplace,
    SetBulkRenameName,
    SetBulkRenameTextCursor,
)
from .input_common import DispatchedActions, supported
from .models import AppState


def _set_find_replace(state: AppState, *, find_text: str, replace_text: str):
    return supported(SetBulkRenameFindReplace(find_text=find_text, replace_text=replace_text))


def dispatch_bulk_rename_input(
    state: AppState,
    *,
    key: str,
    character: str | None = None,
) -> DispatchedActions:
    editor = state.bulk_rename
    if editor is None:
        return ()

    if editor.editing:
        if key == "escape":
            return supported(SetBulkRenameEditing(False))
        if key == "enter":
            return supported(SetBulkRenameEditing(False))
        if key == "left":
            return supported(MoveBulkRenameTextCursor(-1))
        if key == "right":
            return supported(MoveBulkRenameTextCursor(1))
        if key == "home":
            return supported(SetBulkRenameTextCursor(0))
        if key == "end":
            return supported(
                SetBulkRenameTextCursor(len(editor.items[editor.cursor_index].new_name))
            )
        if key == "backspace":
            return supported(DeleteBulkRenameTextBackward())
        if key == "delete":
            return supported(DeleteBulkRenameTextForward())
        if character:
            item = editor.items[editor.cursor_index]
            position = editor.text_cursor_pos
            value = item.new_name[:position] + character + item.new_name[position:]
            return supported(
                SetBulkRenameName(row_index=editor.cursor_index, value=value),
                SetBulkRenameTextCursor(position + len(character)),
            )
        return ()

    if key == "escape":
        return supported(CancelBulkRename())
    if key in {"up", "k"}:
        return supported(MoveBulkRenameCursor(-1))
    if key in {"down", "j"}:
        return supported(MoveBulkRenameCursor(1))
    if key == "tab":
        return supported(CycleBulkRenameField(1))
    if key == "shift+tab":
        return supported(CycleBulkRenameField(-1))
    if key == "enter":
        if editor.active_field == "table":
            return supported(SetBulkRenameEditing(True))
        if editor.active_field == "replace_action":
            return supported(ApplyBulkRenameFindReplace())
        if editor.active_field == "apply":
            return supported(ApplyBulkRename())
        if editor.active_field == "cancel":
            return supported(CancelBulkRename())
        return ()
    if key == "backspace" and editor.active_field in {"find", "replace"}:
        find_text = editor.find_text
        replace_text = editor.replace_text
        if editor.active_field == "find":
            find_text = find_text[:-1]
        else:
            replace_text = replace_text[:-1]
        return _set_find_replace(state, find_text=find_text, replace_text=replace_text)
    if character and editor.active_field in {"find", "replace"}:
        find_text = editor.find_text
        replace_text = editor.replace_text
        if editor.active_field == "find":
            find_text += character
        else:
            replace_text += character
        return _set_find_replace(state, find_text=find_text, replace_text=replace_text)
    if character and editor.active_field == "table":
        item = editor.items[editor.cursor_index]
        return supported(
            SetBulkRenameEditing(True),
            PasteIntoBulkRename(character),
        )
    return ()
