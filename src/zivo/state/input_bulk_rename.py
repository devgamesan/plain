"""Keyboard dispatcher for the bulk rename overlay."""

from .actions import (
    ApplyBulkRename,
    CancelBulkRename,
    CycleBulkRenameField,
    SetBulkRenameBaseName,
)
from .input_common import DispatchedActions, supported
from .models import AppState


def dispatch_bulk_rename_input(
    state: AppState,
    *,
    key: str,
    character: str | None = None,
) -> DispatchedActions:
    """Route base-name text and the two dialog actions."""

    editor = state.bulk_rename
    if editor is None:
        return ()

    if key == "escape":
        return supported(CancelBulkRename())
    if key == "tab":
        return supported(CycleBulkRenameField(1))
    if key == "shift+tab":
        return supported(CycleBulkRenameField(-1))
    if key == "enter":
        if editor.active_field == "apply":
            return supported(ApplyBulkRename())
        if editor.active_field == "cancel":
            return supported(CancelBulkRename())
        return ()
    if editor.active_field != "base_name":
        return ()
    if key == "backspace":
        return supported(SetBulkRenameBaseName(editor.base_name[:-1]))
    if character:
        return supported(SetBulkRenameBaseName(editor.base_name + character))
    return ()
