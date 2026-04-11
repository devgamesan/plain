"""Mutation and clipboard reducer handlers."""

from dataclasses import replace
from pathlib import Path
from typing import Callable, Literal

from peneo.archive_utils import default_extract_destination, default_zip_destination
from peneo.models import DeleteRequest, PasteRequest, RenameRequest

from .actions import (
    Action,
    ArchiveExtractCompleted,
    ArchiveExtractFailed,
    ArchiveExtractProgress,
    ArchivePreparationCompleted,
    ArchivePreparationFailed,
    BeginCreateInput,
    BeginDeleteTargets,
    BeginEmptyTrash,
    BeginExtractArchiveInput,
    BeginRenameInput,
    BeginZipCompressInput,
    CancelArchiveExtractConfirmation,
    CancelDeleteConfirmation,
    CancelEmptyTrashConfirmation,
    CancelPasteConflict,
    CancelPendingInput,
    CancelZipCompressConfirmation,
    ClearSelection,
    ClipboardPasteCompleted,
    ClipboardPasteFailed,
    ClipboardPasteNeedsResolution,
    ConfirmArchiveExtract,
    ConfirmDeleteTargets,
    ConfirmEmptyTrash,
    ConfirmZipCompress,
    CopyTargets,
    CutTargets,
    DismissNameConflict,
    FileMutationCompleted,
    FileMutationFailed,
    PasteClipboard,
    RequestBrowserSnapshot,
    ResolvePasteConflict,
    SelectAllVisibleEntries,
    SetPendingInputValue,
    SubmitPendingInput,
    ToggleSelection,
    ToggleSelectionAndAdvance,
    ZipCompressCompleted,
    ZipCompressFailed,
    ZipCompressPreparationCompleted,
    ZipCompressPreparationFailed,
    ZipCompressProgress,
)
from .effects import ReduceResult
from .models import (
    AppState,
    ArchiveExtractConfirmationState,
    ArchiveExtractProgressState,
    ClipboardState,
    DeleteConfirmationState,
    EmptyTrashConfirmationState,
    NameConflictState,
    NotificationState,
    PasteConflictState,
    PendingInputState,
    ZipCompressConfirmationState,
    ZipCompressProgressState,
)
from .reducer_common import (
    ReducerFn,
    active_current_entries,
    browser_snapshot_invalidation_paths,
    build_extract_archive_request,
    build_file_mutation_request,
    build_zip_compress_request,
    current_entry_for_path,
    current_entry_paths,
    cursor_path_after_file_mutation,
    finalize,
    format_clipboard_message,
    is_name_conflict_validation_error,
    move_cursor,
    name_conflict_kind,
    normalize_selected_paths,
    notification_for_paste_summary,
    request_snapshot_refresh,
    restore_ui_mode_after_pending_input,
    run_archive_extract_request,
    run_archive_prepare_request,
    run_file_mutation_request,
    run_paste_request,
    run_zip_compress_prepare_request,
    run_zip_compress_request,
    sync_child_pane,
    validate_pending_input,
)


def _detect_platform() -> Literal["linux", "darwin"] | None:
    """Detect the current platform."""
    import platform as platform_module

    system = platform_module.system()
    if system == "Linux":
        return "linux"
    elif system == "Darwin":
        return "darwin"
    return None


# ---------------------------------------------------------------------------
# Input Initiation
# ---------------------------------------------------------------------------


def _handle_begin_extract_archive_input(
    state: AppState,
    action: BeginExtractArchiveInput,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    return finalize(
        replace(
            state,
            ui_mode="EXTRACT",
            notification=None,
            pending_input=PendingInputState(
                prompt="Extract to: ",
                value=default_extract_destination(action.source_path),
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
            name_conflict=None,
            attribute_inspection=None,
        )
    )


def _handle_begin_zip_compress_input(
    state: AppState,
    action: BeginZipCompressInput,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    return finalize(
        replace(
            state,
            ui_mode="ZIP",
            notification=None,
            pending_input=PendingInputState(
                prompt="Compress to: ",
                value=default_zip_destination(
                    action.source_paths,
                    state.current_pane.directory_path,
                ),
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
            name_conflict=None,
            attribute_inspection=None,
        )
    )


def _handle_begin_rename_input(
    state: AppState,
    action: BeginRenameInput,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
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
            name_conflict=None,
            attribute_inspection=None,
        )
    )


def _handle_begin_delete_targets(
    state: AppState,
    action: BeginDeleteTargets,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    if not action.paths:
        return finalize(state)
    if action.mode == "permanent" or state.confirm_delete:
        return finalize(
            replace(
                state,
                ui_mode="CONFIRM",
                notification=None,
                pending_input=None,
                command_palette=None,
                pending_file_search_request_id=None,
                pending_grep_search_request_id=None,
                paste_conflict=None,
                delete_confirmation=DeleteConfirmationState(
                    paths=action.paths,
                    mode=action.mode,
                ),
                archive_extract_confirmation=None,
                archive_extract_progress=None,
                zip_compress_confirmation=None,
                zip_compress_progress=None,
                name_conflict=None,
                attribute_inspection=None,
            )
        )
    return run_file_mutation_request(
        replace(
            state,
            notification=None,
            paste_conflict=None,
            delete_confirmation=None,
            archive_extract_confirmation=None,
            archive_extract_progress=None,
            zip_compress_confirmation=None,
            zip_compress_progress=None,
            name_conflict=None,
            attribute_inspection=None,
        ),
        DeleteRequest(paths=action.paths, mode=action.mode),
    )


def _handle_begin_create_input(
    state: AppState,
    action: BeginCreateInput,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
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
            name_conflict=None,
            attribute_inspection=None,
        )
    )


def _handle_begin_empty_trash(
    state: AppState,
    action: BeginEmptyTrash,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    platform_kind = _detect_platform()
    if platform_kind not in ("linux", "darwin"):
        return finalize(
            replace(
                state,
                notification=NotificationState(
                    level="error",
                    message="Empty trash is not supported on this platform",
                ),
            )
        )

    return finalize(
        replace(
            state,
            ui_mode="CONFIRM",
            notification=None,
            pending_input=None,
            command_palette=None,
            pending_file_search_request_id=None,
            pending_grep_search_request_id=None,
            paste_conflict=None,
            delete_confirmation=None,
            empty_trash_confirmation=EmptyTrashConfirmationState(
                platform=platform_kind,
            ),
            archive_extract_confirmation=None,
            archive_extract_progress=None,
            zip_compress_confirmation=None,
            zip_compress_progress=None,
            name_conflict=None,
            attribute_inspection=None,
        )
    )


# ---------------------------------------------------------------------------
# Pending Input Lifecycle
# ---------------------------------------------------------------------------


def _handle_set_pending_input_value(
    state: AppState,
    action: SetPendingInputValue,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    if state.pending_input is None:
        return finalize(state)
    return finalize(
        replace(
            state,
            pending_input=replace(state.pending_input, value=action.value),
        )
    )


def _handle_cancel_pending_input(
    state: AppState,
    action: CancelPendingInput,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
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
            name_conflict=None,
            attribute_inspection=None,
        )
    )


def _handle_submit_pending_input(
    state: AppState,
    action: SubmitPendingInput,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
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


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


def _handle_toggle_selection(
    state: AppState,
    action: ToggleSelection,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    if action.path not in current_entry_paths(state):
        return finalize(state)
    active_entries = active_current_entries(state)
    selected_paths = set(
        normalize_selected_paths(
            state.current_pane.selected_paths,
            active_entries,
        )
    )
    if action.path in selected_paths:
        selected_paths.remove(action.path)
    else:
        selected_paths.add(action.path)
    return finalize(
        replace(
            state,
            current_pane=replace(
                state.current_pane,
                selected_paths=frozenset(selected_paths),
                selection_anchor_path=None,
            ),
        )
    )


def _handle_toggle_selection_and_advance(
    state: AppState,
    action: ToggleSelectionAndAdvance,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    if action.path not in current_entry_paths(state):
        return finalize(state)
    active_entries = active_current_entries(state)
    selected_paths = set(
        normalize_selected_paths(
            state.current_pane.selected_paths,
            active_entries,
        )
    )
    if action.path in selected_paths:
        selected_paths.remove(action.path)
    else:
        selected_paths.add(action.path)
    cursor_path = move_cursor(action.path, action.visible_paths, 1)
    next_state = replace(
        state,
        current_pane=replace(
            state.current_pane,
            cursor_path=cursor_path,
            selected_paths=frozenset(selected_paths),
            selection_anchor_path=None,
        ),
        notification=None,
    )
    return sync_child_pane(next_state, cursor_path, reduce_state)


def _handle_clear_selection(
    state: AppState,
    action: ClearSelection,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    return finalize(
        replace(
            state,
            current_pane=replace(
                state.current_pane,
                selected_paths=frozenset(),
                selection_anchor_path=None,
            ),
        )
    )


def _handle_select_all_visible_entries(
    state: AppState,
    action: SelectAllVisibleEntries,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    active_entries = active_current_entries(state)
    selected_paths = normalize_selected_paths(
        frozenset(action.paths),
        active_entries,
    )
    return finalize(
        replace(
            state,
            current_pane=replace(
                state.current_pane,
                selected_paths=selected_paths,
                selection_anchor_path=None,
            ),
            notification=None,
        )
    )


# ---------------------------------------------------------------------------
# Clipboard and Paste
# ---------------------------------------------------------------------------


def _handle_copy_targets(
    state: AppState,
    action: CopyTargets,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    if not action.paths:
        return finalize(
            replace(
                state,
                notification=NotificationState(level="warning", message="Nothing to copy"),
            )
        )
    return finalize(
        replace(
            state,
            clipboard=ClipboardState(mode="copy", paths=action.paths),
            notification=NotificationState(
                level="info",
                message=format_clipboard_message("Copied", action.paths),
            ),
        )
    )


def _handle_cut_targets(
    state: AppState,
    action: CutTargets,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    if not action.paths:
        return finalize(
            replace(
                state,
                notification=NotificationState(level="warning", message="Nothing to cut"),
            )
        )
    return finalize(
        replace(
            state,
            clipboard=ClipboardState(mode="cut", paths=action.paths),
            notification=NotificationState(
                level="info",
                message=format_clipboard_message("Cut", action.paths),
            ),
        )
    )


def _handle_paste_clipboard(
    state: AppState,
    action: PasteClipboard,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    if state.clipboard.mode == "none" or not state.clipboard.paths:
        return finalize(
            replace(
                state,
                notification=NotificationState(level="warning", message="Clipboard is empty"),
            )
        )

    request = PasteRequest(
        mode=state.clipboard.mode,
        source_paths=state.clipboard.paths,
        destination_dir=state.current_pane.directory_path,
    )
    return run_paste_request(state, request)


def _handle_resolve_paste_conflict(
    state: AppState,
    action: ResolvePasteConflict,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    if state.paste_conflict is None:
        return finalize(state)
    request = replace(
        state.paste_conflict.request,
        conflict_resolution=action.resolution,
    )
    return run_paste_request(
        replace(
            state,
            paste_conflict=None,
            delete_confirmation=None,
            command_palette=None,
            ui_mode="BROWSING",
            notification=None,
        ),
        request,
    )


def _handle_cancel_paste_conflict(
    state: AppState,
    action: CancelPasteConflict,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    return finalize(
        replace(
            state,
            paste_conflict=None,
            delete_confirmation=None,
            ui_mode="BROWSING",
            notification=NotificationState(level="warning", message="Paste cancelled"),
        )
    )


def _handle_clipboard_paste_needs_resolution(
    state: AppState,
    action: ClipboardPasteNeedsResolution,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    if action.request_id != state.pending_paste_request_id or not action.conflicts:
        return finalize(state)
    if state.paste_conflict_action != "prompt":
        request = replace(
            action.request,
            conflict_resolution=state.paste_conflict_action,
        )
        return run_paste_request(
            replace(
                state,
                paste_conflict=None,
                delete_confirmation=None,
                name_conflict=None,
                notification=None,
                pending_paste_request_id=None,
                ui_mode="BROWSING",
            ),
            request,
        )
    return finalize(
        replace(
            state,
            paste_conflict=PasteConflictState(
                request=action.request,
                conflicts=action.conflicts,
                first_conflict=action.conflicts[0],
            ),
            delete_confirmation=None,
            name_conflict=None,
            pending_paste_request_id=None,
            ui_mode="CONFIRM",
        )
    )


def _handle_clipboard_paste_completed(
    state: AppState,
    action: ClipboardPasteCompleted,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    if action.request_id != state.pending_paste_request_id:
        return finalize(state)

    next_clipboard = state.clipboard
    if state.clipboard.mode == "cut" and action.summary.success_count > 0:
        next_clipboard = ClipboardState()

    next_state = replace(
        state,
        clipboard=next_clipboard,
        notification=None,
        paste_conflict=None,
        delete_confirmation=None,
        name_conflict=None,
        post_reload_notification=notification_for_paste_summary(action.summary),
        pending_paste_request_id=None,
        ui_mode="BROWSING",
    )
    return request_snapshot_refresh(next_state)


def _handle_clipboard_paste_failed(
    state: AppState,
    action: ClipboardPasteFailed,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    if action.request_id != state.pending_paste_request_id:
        return finalize(state)
    return finalize(
        replace(
            state,
            notification=NotificationState(level="error", message=action.message),
            paste_conflict=None,
            delete_confirmation=None,
            name_conflict=None,
            pending_paste_request_id=None,
            ui_mode="BROWSING",
        )
    )


# ---------------------------------------------------------------------------
# Confirmations and Cancellations
# ---------------------------------------------------------------------------


def _handle_confirm_delete_targets(
    state: AppState,
    action: ConfirmDeleteTargets,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    if state.delete_confirmation is None:
        return finalize(state)
    return run_file_mutation_request(
        replace(
            state,
            delete_confirmation=None,
            paste_conflict=None,
            notification=None,
        ),
        DeleteRequest(
            paths=state.delete_confirmation.paths,
            mode=state.delete_confirmation.mode,
        ),
    )


def _handle_confirm_archive_extract(
    state: AppState,
    action: ConfirmArchiveExtract,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    if state.archive_extract_confirmation is None:
        return finalize(state)
    return run_archive_extract_request(
        replace(
            state,
            archive_extract_confirmation=None,
            archive_extract_progress=None,
            zip_compress_confirmation=None,
            zip_compress_progress=None,
            notification=None,
        ),
        state.archive_extract_confirmation.request,
    )


def _handle_confirm_zip_compress(
    state: AppState,
    action: ConfirmZipCompress,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    if state.zip_compress_confirmation is None:
        return finalize(state)
    return run_zip_compress_request(
        replace(
            state,
            zip_compress_confirmation=None,
            zip_compress_progress=None,
            notification=None,
        ),
        state.zip_compress_confirmation.request,
    )


def _handle_confirm_empty_trash(
    state: AppState,
    action: ConfirmEmptyTrash,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    if state.empty_trash_confirmation is None:
        return finalize(state)

    from peneo.services import resolve_trash_service

    trash_service = resolve_trash_service()
    removed_count, error_message = trash_service.empty_trash()

    if error_message and removed_count == 0:
        return finalize(
            replace(
                state,
                ui_mode="BROWSING",
                notification=NotificationState(level="error", message=error_message),
                empty_trash_confirmation=None,
            )
        )

    if error_message:
        message = error_message
        level = "warning"
    else:
        noun = "item" if removed_count == 1 else "items"
        message = f"Emptied {removed_count} {noun} from trash"
        level = "info"

    return finalize(
        replace(
            state,
            ui_mode="BROWSING",
            notification=NotificationState(level=level, message=message),
            empty_trash_confirmation=None,
        )
    )


def _handle_cancel_delete_confirmation(
    state: AppState,
    action: CancelDeleteConfirmation,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    message = (
        "Permanent delete cancelled"
        if state.delete_confirmation is not None
        and state.delete_confirmation.mode == "permanent"
        else "Delete cancelled"
    )
    return finalize(
        replace(
            state,
            delete_confirmation=None,
            ui_mode="BROWSING",
            notification=NotificationState(level="warning", message=message),
        )
    )


def _handle_cancel_archive_extract_confirmation(
    state: AppState,
    action: CancelArchiveExtractConfirmation,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    if state.archive_extract_confirmation is None:
        return finalize(state)
    return finalize(
        replace(
            state,
            archive_extract_confirmation=None,
            archive_extract_progress=None,
            zip_compress_confirmation=None,
            zip_compress_progress=None,
            notification=NotificationState(level="warning", message="Extraction cancelled"),
            ui_mode=restore_ui_mode_after_pending_input(state),
        )
    )


def _handle_cancel_zip_compress_confirmation(
    state: AppState,
    action: CancelZipCompressConfirmation,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    if state.zip_compress_confirmation is None:
        return finalize(state)
    return finalize(
        replace(
            state,
            zip_compress_confirmation=None,
            zip_compress_progress=None,
            notification=NotificationState(
                level="warning",
                message="Zip compression cancelled",
            ),
            ui_mode=restore_ui_mode_after_pending_input(state),
        )
    )


def _handle_cancel_empty_trash_confirmation(
    state: AppState,
    action: CancelEmptyTrashConfirmation,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    return finalize(
        replace(
            state,
            ui_mode="BROWSING",
            notification=None,
            empty_trash_confirmation=None,
        )
    )


def _handle_dismiss_name_conflict(
    state: AppState,
    action: DismissNameConflict,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
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


# ---------------------------------------------------------------------------
# Async Completions and Failures
# ---------------------------------------------------------------------------


def _handle_archive_preparation_completed(
    state: AppState,
    action: ArchivePreparationCompleted,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    if action.request_id != state.pending_archive_prepare_request_id:
        return finalize(state)

    if action.conflict_count > 0 and action.first_conflict_path is not None:
        return finalize(
            replace(
                state,
                notification=None,
                pending_archive_prepare_request_id=None,
                archive_extract_progress=None,
                archive_extract_confirmation=ArchiveExtractConfirmationState(
                    request=action.request,
                    conflict_count=action.conflict_count,
                    first_conflict_path=action.first_conflict_path,
                    total_entries=action.total_entries,
                ),
                ui_mode="CONFIRM",
            )
        )

    return run_archive_extract_request(
        replace(
            state,
            notification=None,
            pending_archive_prepare_request_id=None,
            archive_extract_confirmation=None,
            archive_extract_progress=None,
            zip_compress_confirmation=None,
            zip_compress_progress=None,
        ),
        action.request,
    )


def _handle_archive_preparation_failed(
    state: AppState,
    action: ArchivePreparationFailed,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    if action.request_id != state.pending_archive_prepare_request_id:
        return finalize(state)
    return finalize(
        replace(
            state,
            notification=NotificationState(level="error", message=action.message),
            pending_archive_prepare_request_id=None,
            archive_extract_confirmation=None,
            archive_extract_progress=None,
            zip_compress_confirmation=None,
            zip_compress_progress=None,
            ui_mode=restore_ui_mode_after_pending_input(state),
        )
    )


def _handle_archive_extract_progress(
    state: AppState,
    action: ArchiveExtractProgress,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    if action.request_id != state.pending_archive_extract_request_id:
        return finalize(state)

    message = f"Extracting archive {action.completed_entries}/{action.total_entries}"
    if action.current_path is not None:
        message = f"{message}: {Path(action.current_path).name}"
    return finalize(
        replace(
            state,
            archive_extract_progress=ArchiveExtractProgressState(
                completed_entries=action.completed_entries,
                total_entries=action.total_entries,
                current_path=action.current_path,
            ),
            notification=NotificationState(level="info", message=message),
        )
    )


def _handle_archive_extract_completed(
    state: AppState,
    action: ArchiveExtractCompleted,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    if action.request_id != state.pending_archive_extract_request_id:
        return finalize(state)

    next_state = replace(
        state,
        notification=None,
        pending_input=None,
        archive_extract_confirmation=None,
        archive_extract_progress=None,
        pending_archive_prepare_request_id=None,
        pending_archive_extract_request_id=None,
        zip_compress_confirmation=None,
        zip_compress_progress=None,
        post_reload_notification=NotificationState(
            level=action.result.level,
            message=action.result.message,
        ),
        ui_mode="BROWSING",
    )
    return reduce_state(
        next_state,
        RequestBrowserSnapshot(
            path=str(Path(action.result.destination_path).parent),
            cursor_path=action.result.destination_path,
            blocking=True,
            invalidate_paths=browser_snapshot_invalidation_paths(
                str(Path(action.result.destination_path).parent),
                action.result.destination_path,
            ),
        ),
    )


def _handle_archive_extract_failed(
    state: AppState,
    action: ArchiveExtractFailed,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    if action.request_id != state.pending_archive_extract_request_id:
        return finalize(state)
    return finalize(
        replace(
            state,
            notification=NotificationState(level="error", message=action.message),
            pending_archive_extract_request_id=None,
            archive_extract_progress=None,
            archive_extract_confirmation=None,
            zip_compress_confirmation=None,
            zip_compress_progress=None,
            ui_mode=restore_ui_mode_after_pending_input(state),
        )
    )


def _handle_zip_compress_preparation_completed(
    state: AppState,
    action: ZipCompressPreparationCompleted,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    if action.request_id != state.pending_zip_compress_prepare_request_id:
        return finalize(state)

    if action.destination_exists:
        return finalize(
            replace(
                state,
                notification=None,
                pending_zip_compress_prepare_request_id=None,
                zip_compress_progress=None,
                zip_compress_confirmation=ZipCompressConfirmationState(
                    request=action.request,
                    total_entries=action.total_entries,
                ),
                ui_mode="CONFIRM",
            )
        )

    return run_zip_compress_request(
        replace(
            state,
            notification=None,
            pending_zip_compress_prepare_request_id=None,
            zip_compress_confirmation=None,
            zip_compress_progress=None,
        ),
        action.request,
    )


def _handle_zip_compress_preparation_failed(
    state: AppState,
    action: ZipCompressPreparationFailed,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    if action.request_id != state.pending_zip_compress_prepare_request_id:
        return finalize(state)
    return finalize(
        replace(
            state,
            notification=NotificationState(level="error", message=action.message),
            pending_zip_compress_prepare_request_id=None,
            zip_compress_confirmation=None,
            zip_compress_progress=None,
            ui_mode=restore_ui_mode_after_pending_input(state),
        )
    )


def _handle_zip_compress_progress(
    state: AppState,
    action: ZipCompressProgress,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    if action.request_id != state.pending_zip_compress_request_id:
        return finalize(state)

    message = f"Compressing as zip {action.completed_entries}/{action.total_entries}"
    if action.current_path is not None:
        message = f"{message}: {Path(action.current_path).name}"
    return finalize(
        replace(
            state,
            zip_compress_progress=ZipCompressProgressState(
                completed_entries=action.completed_entries,
                total_entries=action.total_entries,
                current_path=action.current_path,
            ),
            notification=NotificationState(level="info", message=message),
        )
    )


def _handle_zip_compress_completed(
    state: AppState,
    action: ZipCompressCompleted,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    if action.request_id != state.pending_zip_compress_request_id:
        return finalize(state)

    next_state = replace(
        state,
        notification=None,
        pending_input=None,
        zip_compress_confirmation=None,
        zip_compress_progress=None,
        pending_zip_compress_prepare_request_id=None,
        pending_zip_compress_request_id=None,
        post_reload_notification=NotificationState(
            level=action.result.level,
            message=action.result.message,
        ),
        ui_mode="BROWSING",
    )
    return reduce_state(
        next_state,
        RequestBrowserSnapshot(
            path=str(Path(action.result.destination_path).parent),
            cursor_path=action.result.destination_path,
            blocking=True,
            invalidate_paths=browser_snapshot_invalidation_paths(
                str(Path(action.result.destination_path).parent),
                action.result.destination_path,
            ),
        ),
    )


def _handle_zip_compress_failed(
    state: AppState,
    action: ZipCompressFailed,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    if action.request_id != state.pending_zip_compress_request_id:
        return finalize(state)
    return finalize(
        replace(
            state,
            notification=NotificationState(level="error", message=action.message),
            pending_zip_compress_request_id=None,
            zip_compress_progress=None,
            zip_compress_confirmation=None,
            ui_mode=restore_ui_mode_after_pending_input(state),
        )
    )


def _handle_file_mutation_completed(
    state: AppState,
    action: FileMutationCompleted,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    if action.request_id != state.pending_file_mutation_request_id:
        return finalize(state)
    selected_paths = state.current_pane.selected_paths
    if action.result.removed_paths:
        selected_paths = frozenset(
            path for path in selected_paths if path not in action.result.removed_paths
        )
    next_state = replace(
        state,
        notification=None,
        current_pane=replace(
            state.current_pane,
            selected_paths=selected_paths,
            selection_anchor_path=None,
        ),
        pending_input=None,
        delete_confirmation=None,
        archive_extract_confirmation=None,
        archive_extract_progress=None,
        zip_compress_confirmation=None,
        zip_compress_progress=None,
        name_conflict=None,
        pending_file_mutation_request_id=None,
        post_reload_notification=NotificationState(
            level=action.result.level,
            message=action.result.message,
        ),
        ui_mode="BROWSING",
    )
    return request_snapshot_refresh(
        next_state,
        cursor_path=cursor_path_after_file_mutation(state, action.result),
        keep_current_cursor=not bool(action.result.removed_paths),
    )


def _handle_file_mutation_failed(
    state: AppState,
    action: FileMutationFailed,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    if action.request_id != state.pending_file_mutation_request_id:
        return finalize(state)
    return finalize(
        replace(
            state,
            notification=NotificationState(level="error", message=action.message),
            pending_file_mutation_request_id=None,
            delete_confirmation=None,
            archive_extract_confirmation=None,
            archive_extract_progress=None,
            zip_compress_confirmation=None,
            zip_compress_progress=None,
            name_conflict=None,
            ui_mode=restore_ui_mode_after_pending_input(state),
        )
    )


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_MutationHandler = Callable[[AppState, Action, ReducerFn], ReduceResult | None]

_MUTATION_HANDLERS: dict[type[Action], _MutationHandler] = {
    BeginExtractArchiveInput: _handle_begin_extract_archive_input,
    BeginZipCompressInput: _handle_begin_zip_compress_input,
    BeginRenameInput: _handle_begin_rename_input,
    BeginDeleteTargets: _handle_begin_delete_targets,
    BeginCreateInput: _handle_begin_create_input,
    BeginEmptyTrash: _handle_begin_empty_trash,
    SetPendingInputValue: _handle_set_pending_input_value,
    CancelPendingInput: _handle_cancel_pending_input,
    SubmitPendingInput: _handle_submit_pending_input,
    ToggleSelection: _handle_toggle_selection,
    ToggleSelectionAndAdvance: _handle_toggle_selection_and_advance,
    ClearSelection: _handle_clear_selection,
    SelectAllVisibleEntries: _handle_select_all_visible_entries,
    CopyTargets: _handle_copy_targets,
    CutTargets: _handle_cut_targets,
    PasteClipboard: _handle_paste_clipboard,
    ResolvePasteConflict: _handle_resolve_paste_conflict,
    CancelPasteConflict: _handle_cancel_paste_conflict,
    ClipboardPasteNeedsResolution: _handle_clipboard_paste_needs_resolution,
    ClipboardPasteCompleted: _handle_clipboard_paste_completed,
    ClipboardPasteFailed: _handle_clipboard_paste_failed,
    ConfirmDeleteTargets: _handle_confirm_delete_targets,
    ConfirmArchiveExtract: _handle_confirm_archive_extract,
    ConfirmZipCompress: _handle_confirm_zip_compress,
    ConfirmEmptyTrash: _handle_confirm_empty_trash,
    CancelDeleteConfirmation: _handle_cancel_delete_confirmation,
    CancelArchiveExtractConfirmation: _handle_cancel_archive_extract_confirmation,
    CancelZipCompressConfirmation: _handle_cancel_zip_compress_confirmation,
    CancelEmptyTrashConfirmation: _handle_cancel_empty_trash_confirmation,
    DismissNameConflict: _handle_dismiss_name_conflict,
    ArchivePreparationCompleted: _handle_archive_preparation_completed,
    ArchivePreparationFailed: _handle_archive_preparation_failed,
    ArchiveExtractProgress: _handle_archive_extract_progress,
    ArchiveExtractCompleted: _handle_archive_extract_completed,
    ArchiveExtractFailed: _handle_archive_extract_failed,
    ZipCompressPreparationCompleted: _handle_zip_compress_preparation_completed,
    ZipCompressPreparationFailed: _handle_zip_compress_preparation_failed,
    ZipCompressProgress: _handle_zip_compress_progress,
    ZipCompressCompleted: _handle_zip_compress_completed,
    ZipCompressFailed: _handle_zip_compress_failed,
    FileMutationCompleted: _handle_file_mutation_completed,
    FileMutationFailed: _handle_file_mutation_failed,
}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def handle_mutation_action(
    state: AppState,
    action: Action,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    handler = _MUTATION_HANDLERS.get(type(action))
    if handler is not None:
        return handler(state, action, reduce_state)  # type: ignore[arg-type]
    return None
