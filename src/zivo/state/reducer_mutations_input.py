"""Pending-input and name-conflict mutation handlers."""

from dataclasses import replace
from pathlib import Path

from zivo.archive_utils import default_extract_destination, default_zip_destination
from zivo.models import CreateSymlinkRequest, RenameRequest
from zivo.windows_paths import basename, join_path

from .actions import (
    BeginCreateInput,
    BeginExtractArchiveInput,
    BeginRenameInput,
    BeginSymlinkInput,
    BeginZipCompressInput,
    CancelPendingInput,
    CancelSymlinkOverwriteConfirmation,
    ConfirmSymlinkOverwrite,
    DeletePendingInputForward,
    DismissNameConflict,
    MovePendingInputCursor,
    PasteIntoPendingInput,
    SetPendingInputCursor,
    SetPendingInputValue,
    SubmitPendingInput,
)
from .models import (
    NameConflictState,
    NotificationState,
    PendingInputState,
    SymlinkOverwriteConfirmationState,
)
from .reducer_common import (
    build_extract_archive_request,
    build_file_mutation_request,
    build_zip_compress_request,
    current_entry_for_path,
    finalize,
    is_name_conflict_validation_error,
    is_symlink_destination_conflict_validation_error,
    name_conflict_kind,
    restore_ui_mode_after_pending_input,
    run_archive_prepare_request,
    run_file_mutation_request,
    run_zip_compress_prepare_request,
    validate_pending_input,
)
from .reducer_mutations_common import MutationHandler


def _handle_begin_extract_archive_input(state, action, reduce_state):
    return finalize(
        replace(
            state,
            ui_mode="EXTRACT",
            notification=None,
            pending_input=PendingInputState(
                prompt="Extract to: ",
                value=(dest := default_extract_destination(action.source_path)),
                cursor_pos=len(dest),
                extract_source_path=action.source_path,
            ),
            command_palette=None,
            pending_file_search_request_id=None,
            pending_grep_search_request_id=None,
            delete_confirmation=None,
            archive_extract_confirmation=None,
            archive_extract_progress=None,
            zip_compress_confirmation=None,
            zip_compress_progress=None,
            symlink_overwrite_confirmation=None,
            name_conflict=None,
            attribute_inspection=None,
        )
    )


def _handle_begin_zip_compress_input(state, action, reduce_state):
    return finalize(
        replace(
            state,
            ui_mode="ZIP",
            notification=None,
            pending_input=PendingInputState(
                prompt="Compress to: ",
                value=(
                    dest := default_zip_destination(
                        action.source_paths,
                        state.current_pane.directory_path,
                    )
                ),
                cursor_pos=len(dest),
                zip_source_paths=action.source_paths,
            ),
            command_palette=None,
            pending_file_search_request_id=None,
            pending_grep_search_request_id=None,
            delete_confirmation=None,
            archive_extract_confirmation=None,
            archive_extract_progress=None,
            zip_compress_confirmation=None,
            zip_compress_progress=None,
            symlink_overwrite_confirmation=None,
            name_conflict=None,
            attribute_inspection=None,
        )
    )


def _default_symlink_destination(base_path: str, source_path: str) -> str:
    source_name = basename(source_path)
    return join_path(base_path, f"{source_name}.link")


def _handle_begin_symlink_input(state, action, reduce_state):
    if state.layout_mode == "transfer":
        active_pane = (
            state.transfer_left
            if state.active_transfer_pane == "left"
            else state.transfer_right
        )
        base_path = active_pane.current_path if active_pane is not None else state.current_path
    else:
        base_path = state.current_pane.directory_path
    destination = _default_symlink_destination(base_path, action.source_path)
    return finalize(
        replace(
            state,
            ui_mode="SYMLINK",
            notification=None,
            pending_input=PendingInputState(
                prompt="Create link at: ",
                value=destination,
                cursor_pos=len(destination),
                symlink_source_path=action.source_path,
            ),
            command_palette=None,
            pending_file_search_request_id=None,
            pending_grep_search_request_id=None,
            delete_confirmation=None,
            archive_extract_confirmation=None,
            archive_extract_progress=None,
            zip_compress_confirmation=None,
            zip_compress_progress=None,
            symlink_overwrite_confirmation=None,
            name_conflict=None,
            attribute_inspection=None,
        )
    )


def _handle_begin_rename_input(state, action, reduce_state):
    if state.layout_mode == "transfer":
        active_pane = (
            state.transfer_left
            if state.active_transfer_pane == "left"
            else state.transfer_right
        )
        entry = (
            next(
                (
                    candidate
                    for candidate in active_pane.pane.entries
                    if candidate.path == action.path
                ),
                None,
            )
            if active_pane is not None
            else None
        )
    else:
        entry = current_entry_for_path(state, action.path)
    if entry is None:
        return finalize(state)
    return finalize(
        replace(
            state,
            ui_mode="RENAME",
            notification=None,
            pending_input=PendingInputState(
                prompt="Rename: ",
                value=entry.name,
                cursor_pos=len(entry.name),
                target_path=entry.path,
            ),
            command_palette=None,
            pending_file_search_request_id=None,
            pending_grep_search_request_id=None,
            delete_confirmation=None,
            archive_extract_confirmation=None,
            archive_extract_progress=None,
            zip_compress_confirmation=None,
            zip_compress_progress=None,
            symlink_overwrite_confirmation=None,
            name_conflict=None,
            attribute_inspection=None,
        )
    )


def _handle_begin_create_input(state, action, reduce_state):
    prompt = "New file: " if action.kind == "file" else "New directory: "
    return finalize(
        replace(
            state,
            ui_mode="CREATE",
            notification=None,
            pending_input=PendingInputState(
                prompt=prompt,
                create_kind=action.kind,
            ),
            command_palette=None,
            pending_file_search_request_id=None,
            pending_grep_search_request_id=None,
            delete_confirmation=None,
            archive_extract_confirmation=None,
            archive_extract_progress=None,
            zip_compress_confirmation=None,
            zip_compress_progress=None,
            symlink_overwrite_confirmation=None,
            name_conflict=None,
            attribute_inspection=None,
        )
    )


def _handle_set_pending_input_value(state, action, reduce_state):
    if state.pending_input is None:
        return finalize(state)
    return finalize(
        replace(
            state,
            pending_input=replace(
                state.pending_input,
                value=action.value,
                cursor_pos=action.cursor_pos,
            ),
        )
    )


def _handle_paste_into_pending_input(state, action, reduce_state):
    if state.pending_input is None:
        return finalize(state)
    pasted = "".join(c for c in action.text if c.isprintable())
    if not pasted:
        return finalize(state)
    value = state.pending_input.value
    pos = state.pending_input.cursor_pos
    new_value = value[:pos] + pasted + value[pos:]
    return finalize(
        replace(
            state,
            pending_input=replace(
                state.pending_input,
                value=new_value,
                cursor_pos=pos + len(pasted),
            ),
        )
    )


def _handle_move_pending_input_cursor(state, action, reduce_state):
    if state.pending_input is None:
        return finalize(state)
    max_pos = len(state.pending_input.value)
    new_pos = max(0, min(max_pos, state.pending_input.cursor_pos + action.delta))
    return finalize(
        replace(
            state,
            pending_input=replace(state.pending_input, cursor_pos=new_pos),
        )
    )


def _handle_set_pending_input_cursor(state, action, reduce_state):
    if state.pending_input is None:
        return finalize(state)
    max_pos = len(state.pending_input.value)
    new_pos = max(0, min(max_pos, action.cursor_pos))
    return finalize(
        replace(
            state,
            pending_input=replace(state.pending_input, cursor_pos=new_pos),
        )
    )


def _handle_delete_pending_input_forward(state, action, reduce_state):
    if state.pending_input is None:
        return finalize(state)
    value = state.pending_input.value
    pos = state.pending_input.cursor_pos
    if pos >= len(value):
        return finalize(state)
    new_value = value[:pos] + value[pos + 1 :]
    return finalize(
        replace(
            state,
            pending_input=replace(state.pending_input, value=new_value),
        )
    )


def _handle_cancel_pending_input(state, action, reduce_state):
    return finalize(
        replace(
            state,
            ui_mode="BROWSING",
            notification=None,
            pending_input=None,
            command_palette=None,
            pending_file_search_request_id=None,
            pending_grep_search_request_id=None,
            pending_archive_prepare_request_id=None,
            pending_archive_extract_request_id=None,
            pending_zip_compress_prepare_request_id=None,
            pending_zip_compress_request_id=None,
            delete_confirmation=None,
            archive_extract_confirmation=None,
            archive_extract_progress=None,
            zip_compress_confirmation=None,
            zip_compress_progress=None,
            symlink_overwrite_confirmation=None,
            name_conflict=None,
            attribute_inspection=None,
        )
    )


def _handle_submit_pending_input(state, action, reduce_state):
    if state.pending_input is None:
        return finalize(state)
    validation_error = validate_pending_input(state)
    if validation_error is not None:
        if is_name_conflict_validation_error(state, validation_error):
            return finalize(
                replace(
                    state,
                    ui_mode="CONFIRM",
                    notification=None,
                    paste_conflict=None,
                    delete_confirmation=None,
                    name_conflict=NameConflictState(
                        kind=name_conflict_kind(state),
                        name=state.pending_input.value,
                    ),
                )
            )
        if is_symlink_destination_conflict_validation_error(state, validation_error):
            request = build_file_mutation_request(state)
            if isinstance(request, CreateSymlinkRequest):
                return finalize(
                    replace(
                        state,
                        ui_mode="CONFIRM",
                        notification=None,
                        paste_conflict=None,
                        delete_confirmation=None,
                        symlink_overwrite_confirmation=SymlinkOverwriteConfirmationState(
                            request=CreateSymlinkRequest(
                                source_path=request.source_path,
                                destination_path=request.destination_path,
                                overwrite=True,
                            )
                        ),
                    )
                )
        return finalize(
            replace(
                state,
                notification=NotificationState(level="error", message=validation_error),
                name_conflict=None,
            )
        )
    request = build_file_mutation_request(state)
    extract_request = build_extract_archive_request(state)
    zip_request = build_zip_compress_request(state)
    if extract_request is not None:
        return run_archive_prepare_request(state, extract_request)
    if zip_request is not None:
        return run_zip_compress_prepare_request(state, zip_request)
    if request is None:
        return finalize(state)
    if isinstance(request, RenameRequest):
        current_name = Path(request.source_path).name
        if current_name == request.new_name:
            return finalize(
                replace(
                    state,
                    ui_mode="BROWSING",
                    pending_input=None,
                    notification=NotificationState(level="info", message="Name unchanged"),
                )
            )
    return run_file_mutation_request(state, request)


def _handle_dismiss_name_conflict(state, action, reduce_state):
    if state.name_conflict is None:
        return finalize(state)
    return finalize(
        replace(
            state,
            notification=None,
            name_conflict=None,
            ui_mode=restore_ui_mode_after_pending_input(state),
        )
    )


def _handle_confirm_symlink_overwrite(state, action, reduce_state):
    if state.symlink_overwrite_confirmation is None or state.pending_input is None:
        return finalize(state)
    return run_file_mutation_request(
        replace(
            state,
            ui_mode="SYMLINK",
            notification=None,
            symlink_overwrite_confirmation=None,
            pending_input=replace(state.pending_input, symlink_overwrite=True),
        ),
        state.symlink_overwrite_confirmation.request,
    )


def _handle_cancel_symlink_overwrite_confirmation(state, action, reduce_state):
    if state.symlink_overwrite_confirmation is None:
        return finalize(state)
    return finalize(
        replace(
            state,
            symlink_overwrite_confirmation=None,
            notification=NotificationState(level="warning", message="Symlink creation cancelled"),
            ui_mode=restore_ui_mode_after_pending_input(state),
        )
    )


INPUT_MUTATION_HANDLERS: dict[type, MutationHandler] = {
    BeginExtractArchiveInput: _handle_begin_extract_archive_input,
    BeginZipCompressInput: _handle_begin_zip_compress_input,
    BeginRenameInput: _handle_begin_rename_input,
    BeginCreateInput: _handle_begin_create_input,
    BeginSymlinkInput: _handle_begin_symlink_input,
    SetPendingInputValue: _handle_set_pending_input_value,
    MovePendingInputCursor: _handle_move_pending_input_cursor,
    SetPendingInputCursor: _handle_set_pending_input_cursor,
    DeletePendingInputForward: _handle_delete_pending_input_forward,
    PasteIntoPendingInput: _handle_paste_into_pending_input,
    CancelPendingInput: _handle_cancel_pending_input,
    SubmitPendingInput: _handle_submit_pending_input,
    ConfirmSymlinkOverwrite: _handle_confirm_symlink_overwrite,
    CancelSymlinkOverwriteConfirmation: _handle_cancel_symlink_overwrite_confirmation,
    DismissNameConflict: _handle_dismiss_name_conflict,
}
