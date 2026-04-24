"""Dialog and non-browsing mode input dispatchers."""

from .actions import (
    CancelArchiveExtractConfirmation,
    CancelDeleteConfirmation,
    CancelEmptyTrashConfirmation,
    CancelFilterInput,
    CancelPasteConflict,
    CancelPendingInput,
    CancelReplaceConfirmation,
    CancelShellCommandInput,
    CancelZipCompressConfirmation,
    ConfirmArchiveExtract,
    ConfirmDeleteTargets,
    ConfirmEmptyTrash,
    ConfirmFilterInput,
    ConfirmReplaceTargets,
    ConfirmZipCompress,
    CycleConfigEditorValue,
    DeletePendingInputForward,
    DismissAttributeDialog,
    DismissConfigEditor,
    DismissNameConflict,
    MoveConfigEditorCursor,
    MovePendingInputCursor,
    OpenPathInEditor,
    ResetHelpBarConfig,
    ResolvePasteConflict,
    SaveConfigEditor,
    SetFilterQuery,
    SetPendingInputCursor,
    SetPendingInputValue,
    SetShellCommandValue,
    SubmitPendingInput,
    SubmitShellCommand,
)
from .input_common import DispatchedActions, supported, warn
from .models import AppState


def _get_filter_query(state: AppState) -> str:
    """Get the current filter query based on the layout mode."""
    if state.layout_mode == "transfer":
        transfer = (
            state.transfer_left
            if state.active_transfer_pane == "left"
            else state.transfer_right
        )
        return transfer.filter.query if transfer else ""
    return state.filter.query


def dispatch_filter_input(
    state: AppState,
    *,
    key: str,
    character: str | None,
) -> DispatchedActions:
    if key == "escape":
        return supported(CancelFilterInput())

    if key in {"down", "enter"}:
        return supported(ConfirmFilterInput())

    current_query = _get_filter_query(state)

    if key == "backspace":
        next_query = current_query[:-1]
        return supported(SetFilterQuery(next_query, active=bool(next_query)))

    if character and character.isprintable() and not character.isspace():
        return supported(SetFilterQuery(f"{current_query}{character}", active=True))

    return warn("This key is unavailable while editing the filter")


def dispatch_confirm_input(
    state: AppState, *, key: str, character: str | None
) -> DispatchedActions:
    if state.delete_confirmation is not None:
        if key == "escape":
            return supported(CancelDeleteConfirmation())
        if key == "enter":
            return supported(ConfirmDeleteTargets())
        return warn("Use Enter to confirm delete or Esc to cancel")

    if state.empty_trash_confirmation is not None:
        if key == "escape":
            return supported(CancelEmptyTrashConfirmation())
        if key == "enter":
            return supported(ConfirmEmptyTrash())
        return warn("Use Enter to confirm empty trash or Esc to cancel")

    if state.archive_extract_confirmation is not None:
        if key == "escape":
            return supported(CancelArchiveExtractConfirmation())
        if key == "enter":
            return supported(ConfirmArchiveExtract())
        return warn("Use Enter to continue extraction or Esc to return")

    if state.zip_compress_confirmation is not None:
        if key == "escape":
            return supported(CancelZipCompressConfirmation())
        if key == "enter":
            return supported(ConfirmZipCompress())
        return warn("Use Enter to overwrite the zip or Esc to return")

    if state.replace_confirmation is not None:
        if key == "escape":
            return supported(CancelReplaceConfirmation())
        if key == "enter":
            return supported(ConfirmReplaceTargets())
        return warn("Use Enter to confirm replace or Esc to cancel")

    if state.name_conflict is not None:
        if key in {"enter", "escape"}:
            return supported(DismissNameConflict())
        return warn("Use Enter or Esc to return to name editing")

    if key == "escape":
        return supported(CancelPasteConflict())

    if key == "o":
        return supported(ResolvePasteConflict("overwrite"))

    if key == "s":
        return supported(ResolvePasteConflict("skip"))

    if key == "r":
        return supported(ResolvePasteConflict("rename"))

    return warn("Use o, s, r, or Esc while resolving paste conflicts")


def dispatch_input_dialog_input(
    state: AppState,
    *,
    key: str,
    character: str | None,
) -> DispatchedActions:
    if key == "escape":
        return supported(CancelPendingInput())

    if key == "enter":
        return supported(SubmitPendingInput())

    if key == "backspace":
        pending = state.pending_input
        if pending is None or pending.cursor_pos == 0:
            return supported()
        pos = pending.cursor_pos
        new_value = pending.value[: pos - 1] + pending.value[pos:]
        return supported(SetPendingInputValue(new_value, pos - 1))

    if key == "delete":
        return supported(DeletePendingInputForward())

    if key == "left":
        return supported(MovePendingInputCursor(delta=-1))

    if key == "right":
        return supported(MovePendingInputCursor(delta=1))

    if key == "home":
        return supported(SetPendingInputCursor(cursor_pos=0))

    if key == "end":
        pending = state.pending_input
        end_pos = len(pending.value) if pending is not None else 0
        return supported(SetPendingInputCursor(cursor_pos=end_pos))

    if key == "ctrl+v":
        return supported()

    if character and character.isprintable():
        pending = state.pending_input
        if pending is None:
            return supported()
        pos = pending.cursor_pos
        new_value = pending.value[:pos] + character + pending.value[pos:]
        return supported(SetPendingInputValue(new_value, pos + 1))

    return warn("Use Enter to apply, Esc to cancel, or paste")


def dispatch_shell_command_input(
    state: AppState,
    *,
    key: str,
    character: str | None,
) -> DispatchedActions:
    if key == "escape":
        return supported(CancelShellCommandInput())

    if key == "enter":
        return supported(SubmitShellCommand())

    if key == "backspace":
        current_command = state.shell_command.command if state.shell_command is not None else ""
        return supported(SetShellCommandValue(current_command[:-1]))

    if character and character.isprintable():
        current_command = state.shell_command.command if state.shell_command is not None else ""
        return supported(SetShellCommandValue(f"{current_command}{character}"))

    return warn("Use Enter to run or Esc to cancel")


def dispatch_detail_input(
    state: AppState, *, key: str, character: str | None
) -> DispatchedActions:
    if key in {"enter", "escape"}:
        return supported(DismissAttributeDialog())

    return warn("Use Enter or Esc to close the attributes dialog")


def dispatch_config_input(
    state: AppState, *, key: str, character: str | None
) -> DispatchedActions:
    if key == "escape":
        return supported(DismissConfigEditor())

    if key in {"up", "k", "ctrl+p"}:
        return supported(MoveConfigEditorCursor(delta=-1))

    if key in {"down", "j", "ctrl+n"}:
        return supported(MoveConfigEditorCursor(delta=1))

    if key in {"left", "h"}:
        return supported(CycleConfigEditorValue(delta=-1))

    if key in {"right", "l", "enter", "space"}:
        return supported(CycleConfigEditorValue(delta=1))

    if key == "s":
        return supported(SaveConfigEditor())

    if key == "e":
        return supported(OpenPathInEditor(state.config_path))

    if key == "r":
        return supported(ResetHelpBarConfig())

    return warn(
        "Use ↑↓ or Ctrl+n/p to choose, ←→ or Enter to change, "
        "s to save, e to edit the file, r to reset help, or Esc to close"
    )
