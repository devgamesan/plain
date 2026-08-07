"""Dialog and non-browsing mode input dispatchers."""

from .actions import (
    AdvancePermanentDeleteConfirmation,
    CancelArchiveExtractConfirmation,
    CancelCustomActionConfirmation,
    CancelDeleteConfirmation,
    CancelExitConfirmation,
    CancelFilterInput,
    CancelPasteConflict,
    CancelPendingInput,
    CancelReplaceConfirmation,
    CancelShellCommandInput,
    CancelSymlinkOverwriteConfirmation,
    CancelZipCompressConfirmation,
    ConfirmArchiveExtract,
    ConfirmCustomAction,
    ConfirmDeleteTargets,
    ConfirmExitCurrentPath,
    ConfirmFilterInput,
    ConfirmReplaceTargets,
    ConfirmSymlinkOverwrite,
    ConfirmZipCompress,
    CycleConfigEditorValue,
    DeletePendingInputForward,
    DismissAboutDialog,
    DismissAttributeDialog,
    DismissConfigEditor,
    DismissNameConflict,
    MoveConfigEditorCursor,
    MovePendingInputCursor,
    MoveShellCommandCursor,
    OpenPathInEditor,
    OpenTerminalAtPath,
    ResolvePasteConflict,
    SaveConfigEditor,
    SetFilterQuery,
    SetPendingInputCursor,
    SetPendingInputValue,
    SetShellCommandCursor,
    SetShellCommandValue,
    SubmitPendingInput,
    SubmitShellCommand,
    TogglePendingInputRecursive,
)
from .input_common import DispatchedActions, supported, warn
from .models import AppState
from .reducer_pending_input import complete_pending_input_path


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

    if key == "backspace":
        next_query = state.filter.query[:-1]
        return supported(SetFilterQuery(next_query, active=bool(next_query)))

    if character and character.isprintable() and not character.isspace():
        return supported(SetFilterQuery(f"{state.filter.query}{character}", active=True))

    return warn("This key is unavailable while editing the filter")


def dispatch_confirm_input(
    state: AppState, *, key: str, character: str | None
) -> DispatchedActions:
    if state.delete_confirmation is not None:
        confirmation = state.delete_confirmation
        if key == "escape":
            return supported(CancelDeleteConfirmation())
        if (
            confirmation.requires_additional_confirmation
            and not confirmation.additional_confirmation_armed
            and key == "enter"
        ):
            return supported(AdvancePermanentDeleteConfirmation())
        if confirmation.additional_confirmation_armed and key == "D":
            return supported(ConfirmDeleteTargets())
        if not confirmation.requires_additional_confirmation and key == "enter":
            return supported(ConfirmDeleteTargets())
        if confirmation.additional_confirmation_armed:
            return warn("Use D to permanently delete or Esc to cancel")
        if confirmation.requires_additional_confirmation:
            return warn("Use Enter to review permanent delete or Esc to cancel")
        return warn("Use Enter to confirm delete or Esc to cancel")

    if state.exit_confirmation is not None:
        if key == "escape":
            return supported(CancelExitConfirmation())
        if key == "enter":
            return supported(ConfirmExitCurrentPath())
        return warn("Use Enter to confirm exit or Esc to cancel")

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

    if state.symlink_overwrite_confirmation is not None:
        if key == "escape":
            return supported(CancelSymlinkOverwriteConfirmation())
        if key == "enter":
            return supported(ConfirmSymlinkOverwrite())
        return warn("Use Enter to overwrite the destination or Esc to return")

    if state.custom_action_confirmation is not None:
        if key == "escape":
            return supported(CancelCustomActionConfirmation())
        if key == "enter":
            return supported(ConfirmCustomAction())
        return warn("Use Enter to run the custom action or Esc to cancel")

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

    if key == "tab" and state.ui_mode in {"CHMOD", "CHOWN"}:
        return supported(TogglePendingInputRecursive())

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

    if key == "tab":
        completed = complete_pending_input_path(state)
        if completed is None:
            return warn("No matching path to complete")
        return supported(SetPendingInputValue(completed, len(completed)))

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
    # 結果表示状態でESCキーを押した場合、ダイアログを閉じてBROWSINGモードに戻る
    if state.shell_command is not None and state.shell_command.result is not None:
        if key == "escape":
            return supported(CancelShellCommandInput())
        if key == "r":
            return supported(SubmitShellCommand())
        if key == "t":
            return supported(OpenTerminalAtPath(state.shell_command.cwd))
        return warn("Use r to rerun, t to open a terminal, or Esc to close")

    if key == "escape":
        return supported(CancelShellCommandInput())

    if key == "enter":
        return supported(SubmitShellCommand())

    if key == "backspace":
        if state.shell_command is None or state.shell_command.cursor_pos == 0:
            return supported()
        pos = state.shell_command.cursor_pos
        new_value = state.shell_command.command[: pos - 1] + state.shell_command.command[pos:]
        return supported(SetShellCommandValue(new_value, pos - 1))

    if key == "delete":
        if state.shell_command is None:
            return supported()
        pos = state.shell_command.cursor_pos
        if pos >= len(state.shell_command.command):
            return supported()
        new_value = state.shell_command.command[:pos] + state.shell_command.command[pos + 1 :]
        return supported(SetShellCommandValue(new_value, pos))

    if key == "left":
        return supported(MoveShellCommandCursor(delta=-1))

    if key == "right":
        return supported(MoveShellCommandCursor(delta=1))

    if key == "home":
        return supported(SetShellCommandCursor(cursor_pos=0))

    if key == "end":
        if state.shell_command is None:
            return supported()
        end_pos = len(state.shell_command.command)
        return supported(SetShellCommandCursor(cursor_pos=end_pos))

    if key == "ctrl+v":
        return supported()

    if character and character.isprintable():
        if state.shell_command is None:
            return supported()
        pos = state.shell_command.cursor_pos
        new_value = (
            state.shell_command.command[:pos]
            + character
            + state.shell_command.command[pos:]
        )
        return supported(SetShellCommandValue(new_value, pos + 1))

    return warn("Use Enter to run or Esc to cancel")


def dispatch_about_input(
    state: AppState, *, key: str, character: str | None
) -> DispatchedActions:
    if key in {"enter", "escape"}:
        return supported(DismissAboutDialog())

    return warn("Use Enter or Esc to close the about dialog")


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

    if key in {"up", "k", "ctrl+k"}:
        return supported(MoveConfigEditorCursor(delta=-1))

    if key in {"down", "j", "ctrl+j"}:
        return supported(MoveConfigEditorCursor(delta=1))

    if key in {"left", "h"}:
        return supported(CycleConfigEditorValue(delta=-1))

    if key in {"right", "l", "enter", "space"}:
        return supported(CycleConfigEditorValue(delta=1))

    if key == "s":
        return supported(SaveConfigEditor())

    if key == "e":
        return supported(OpenPathInEditor(state.config_path))

    return warn(
        "Use ↑↓ or Ctrl+j/k to choose, ←→ or Enter to change, "
        "s to save, e to edit the file, or Esc to close"
    )
