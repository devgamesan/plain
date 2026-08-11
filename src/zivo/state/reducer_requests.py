"""Reducer request builders and shared transition helpers."""

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from zivo.models import (
    ChmodRequest,
    ChownRequest,
    CreatePathRequest,
    CreateSymlinkRequest,
    CreateZipArchiveRequest,
    DeleteRequest,
    DuplicateRequest,
    DuplicateSummary,
    ExternalLaunchRequest,
    ExtractArchiveRequest,
    FileMutationResult,
    PasteRequest,
    PasteSummary,
    RecursiveChmodRequest,
    RecursiveChownRequest,
    RenameRequest,
    UndoEntry,
)
from zivo.windows_paths import (
    is_windows_drives_root,
    is_windows_path,
    normalize_windows_path,
)

from .actions import Action
from .effects import (
    Effect,
    LoadBrowserSnapshotEffect,
    ReduceResult,
    RunArchiveExtractEffect,
    RunArchivePreparationEffect,
    RunClipboardPasteEffect,
    RunDeletePreparationEffect,
    RunExternalLaunchEffect,
    RunFileMutationEffect,
    RunUndoEffect,
    RunZipCompressEffect,
    RunZipCompressPreparationEffect,
)
from .models import (
    ForegroundOperationState,
    HistoryState,
    NotificationAction,
    NotificationDetails,
    NotificationFailureDetail,
    NotificationState,
    resolve_parent_directory_path,
)

ReducerFn = Callable[[object, Action], ReduceResult]
FileMutationRequest = (
    RenameRequest
    | CreatePathRequest
    | CreateSymlinkRequest
    | DeleteRequest
    | ChmodRequest
    | RecursiveChmodRequest
    | ChownRequest
    | RecursiveChownRequest
)


def finalize(next_state, *effects: Effect) -> ReduceResult:
    """Wrap a state transition and optional side effects into a ReduceResult."""

    return ReduceResult(state=next_state, effects=effects)


def run_paste_request(
    state,
    request: PasteRequest,
    *,
    force_conflict_prompt: bool = False,
) -> ReduceResult:
    if state.foreground_operation is not None:
        return finalize(
            replace(
                state,
                notification=NotificationState(
                    level="warning",
                    message=(
                        f"{state.foreground_operation.kind.title()} is already in progress"
                    ),
                ),
            )
        )
    request_id = state.next_request_id
    next_state = replace(
        state,
        command_palette=None,
        notification=None,
        paste_conflict=None,
        delete_confirmation=None,
        pending_paste_request_id=request_id,
        pending_paste_request=request,
        pending_paste_retry_requires_confirmation=force_conflict_prompt,
        next_request_id=request_id + 1,
        # The confirmed file transfer continues in a worker while the user
        # keeps browsing.  Conflict resolution is still handled in the
        # foreground by the worker result reducer.
        ui_mode="BROWSING",
        foreground_operation=ForegroundOperationState(
            operation_id=request_id,
            kind="copy" if request.mode == "copy" else "move",
            total=len(request.source_paths),
            message=("Copying" if request.mode == "copy" else "Moving"),
        ),
    )
    return ReduceResult(
        state=next_state,
        effects=(RunClipboardPasteEffect(request_id=request_id, request=request),),
    )


def run_external_launch_request(
    state,
    request: ExternalLaunchRequest,
) -> ReduceResult:
    if state.foreground_operation is not None and request.kind in {
        "open_file",
        "open_editor",
        "open_gui_editor",
        "open_terminal",
    }:
        return finalize(
            replace(
                state,
                notification=NotificationState(
                    level="warning",
                    message=(
                        f"{state.foreground_operation.kind.title()} is already in progress"
                    ),
                ),
            )
        )
    request_id = state.next_request_id
    next_state = replace(
        state,
        next_request_id=request_id + 1,
    )
    return ReduceResult(
        state=next_state,
        effects=(RunExternalLaunchEffect(request_id=request_id, request=request),),
    )


def run_file_mutation_request(
    state,
    request: FileMutationRequest,
) -> ReduceResult:
    if state.foreground_operation is not None:
        return finalize(
            replace(
                state,
                notification=NotificationState(
                    level="warning",
                    message=(
                        f"{state.foreground_operation.kind.title()} is already in progress"
                    ),
                ),
            )
        )
    request_id = state.next_request_id
    next_state = replace(
        state,
        notification=None,
        delete_confirmation=None,
        pending_file_mutation_request_id=request_id,
        next_request_id=request_id + 1,
        ui_mode="BUSY",
    )
    return ReduceResult(
        state=next_state,
        effects=(RunFileMutationEffect(request_id=request_id, request=request),),
    )


def run_delete_prepare_request(state, request: DeleteRequest) -> ReduceResult:
    if state.foreground_operation is not None:
        return finalize(
            replace(
                state,
                notification=NotificationState(
                    level="warning",
                    message=(
                        f"{state.foreground_operation.kind.title()} is already in progress"
                    ),
                ),
            )
        )
    request_id = state.next_request_id
    next_state = replace(
        state,
        notification=NotificationState(level="info", message="Inspecting delete targets"),
        delete_confirmation=None,
        pending_delete_prepare_request_id=request_id,
        next_request_id=request_id + 1,
        ui_mode="BUSY",
    )
    return ReduceResult(
        state=next_state,
        effects=(RunDeletePreparationEffect(request_id=request_id, request=request),),
    )


def run_undo_request(state, entry: UndoEntry) -> ReduceResult:
    if state.foreground_operation is not None:
        return finalize(
            replace(
                state,
                notification=NotificationState(
                    level="warning",
                    message=(
                        f"{state.foreground_operation.kind.title()} is already in progress"
                    ),
                ),
            )
        )
    request_id = state.next_request_id
    next_state = replace(
        state,
        notification=None,
        pending_undo_entry=entry,
        pending_undo_request_id=request_id,
        next_request_id=request_id + 1,
        ui_mode="BUSY",
    )
    return ReduceResult(
        state=next_state,
        effects=(RunUndoEffect(request_id=request_id, entry=entry),),
    )


def run_archive_prepare_request(
    state,
    request: ExtractArchiveRequest,
) -> ReduceResult:
    if state.foreground_operation is not None:
        return finalize(
            replace(
                state,
                notification=NotificationState(
                    level="warning",
                    message=(
                        f"{state.foreground_operation.kind.title()} is already in progress"
                    ),
                ),
            )
        )
    request_id = state.next_request_id
    next_state = replace(
        state,
        notification=NotificationState(level="info", message="Preparing archive extraction"),
        delete_confirmation=None,
        archive_extract_confirmation=None,
        archive_extract_progress=None,
        pending_archive_prepare_request_id=request_id,
        pending_archive_prepare_request=request,
        next_request_id=request_id + 1,
        ui_mode="BUSY",
    )
    return ReduceResult(
        state=next_state,
        effects=(RunArchivePreparationEffect(request_id=request_id, request=request),),
    )


def run_archive_extract_request(
    state,
    request: ExtractArchiveRequest,
) -> ReduceResult:
    if state.foreground_operation is not None:
        return finalize(
            replace(
                state,
                notification=NotificationState(
                    level="warning",
                    message=(
                        f"{state.foreground_operation.kind.title()} is already in progress"
                    ),
                ),
            )
        )
    request_id = state.next_request_id
    next_state = replace(
        state,
        notification=NotificationState(level="info", message="Extracting archive..."),
        archive_extract_confirmation=None,
        archive_extract_progress=None,
        pending_input=None,
        pending_archive_prepare_request=None,
        pending_archive_extract_request_id=request_id,
        next_request_id=request_id + 1,
        ui_mode="BROWSING",
        foreground_operation=ForegroundOperationState(
            operation_id=request_id,
            kind="extract",
            message="Extracting archive",
        ),
    )
    return ReduceResult(
        state=next_state,
        effects=(RunArchiveExtractEffect(request_id=request_id, request=request),),
    )


def run_zip_compress_prepare_request(
    state,
    request: CreateZipArchiveRequest,
) -> ReduceResult:
    if state.foreground_operation is not None:
        return finalize(
            replace(
                state,
                notification=NotificationState(
                    level="warning",
                    message=(
                        f"{state.foreground_operation.kind.title()} is already in progress"
                    ),
                ),
            )
        )
    request_id = state.next_request_id
    next_state = replace(
        state,
        notification=NotificationState(level="info", message="Preparing zip compression"),
        delete_confirmation=None,
        archive_extract_confirmation=None,
        archive_extract_progress=None,
        zip_compress_confirmation=None,
        zip_compress_progress=None,
        pending_zip_compress_prepare_request_id=request_id,
        pending_zip_compress_prepare_request=request,
        next_request_id=request_id + 1,
        ui_mode="BUSY",
    )
    return ReduceResult(
        state=next_state,
        effects=(RunZipCompressPreparationEffect(request_id=request_id, request=request),),
    )


def run_zip_compress_request(
    state,
    request: CreateZipArchiveRequest,
) -> ReduceResult:
    if state.foreground_operation is not None:
        return finalize(
            replace(
                state,
                notification=NotificationState(
                    level="warning",
                    message=(
                        f"{state.foreground_operation.kind.title()} is already in progress"
                    ),
                ),
            )
        )
    request_id = state.next_request_id
    next_state = replace(
        state,
        notification=NotificationState(level="info", message="Compressing as zip..."),
        zip_compress_confirmation=None,
        zip_compress_progress=None,
        pending_input=None,
        pending_zip_compress_prepare_request=None,
        pending_zip_compress_request_id=request_id,
        next_request_id=request_id + 1,
        ui_mode="BROWSING",
        foreground_operation=ForegroundOperationState(
            operation_id=request_id,
            kind="compress",
            message="Compressing as zip",
        ),
    )
    return ReduceResult(
        state=next_state,
        effects=(RunZipCompressEffect(request_id=request_id, request=request),),
    )


def cursor_path_after_file_mutation(
    state,
    result: FileMutationResult,
) -> str | None:
    active_entries = state.current_pane.entries
    if result.removed_paths:
        remaining_paths = [
            entry.path
            for entry in active_entries
            if entry.path not in result.removed_paths
        ]
        if not remaining_paths:
            return None
        current_cursor = state.current_pane.cursor_path
        if current_cursor is not None and current_cursor not in result.removed_paths:
            return current_cursor
        original_paths = [entry.path for entry in active_entries]
        if current_cursor in original_paths:
            current_index = original_paths.index(current_cursor)
            if current_index < len(remaining_paths):
                return remaining_paths[current_index]
        return remaining_paths[-1]
    return result.path


def cursor_path_after_transfer_move(pane, removed_paths: set[str]) -> str | None:
    """Pick a transfer-pane cursor after a move removes some source paths.

    Mirrors :func:`cursor_path_after_file_mutation`: keep the cursor when it
    survives, otherwise fall back to the next visible entry at the same display
    position, then the last remaining entry.
    """

    active_entries = pane.entries
    if not removed_paths:
        return pane.cursor_path
    remaining_paths = [
        entry.path for entry in active_entries if entry.path not in removed_paths
    ]
    if not remaining_paths:
        return None
    current_cursor = pane.cursor_path
    if current_cursor is not None and current_cursor not in removed_paths:
        return current_cursor
    original_paths = [entry.path for entry in active_entries]
    if current_cursor in original_paths:
        current_index = original_paths.index(current_cursor)
        if current_index < len(remaining_paths):
            return remaining_paths[current_index]
    return remaining_paths[-1]


def restore_ui_mode_after_pending_input(state) -> str:
    if state.pending_input is None:
        return "BROWSING"
    if (
        state.pending_input.chmod_target_path is not None
        or state.pending_input.chmod_target_paths is not None
    ):
        return "CHMOD"
    if state.pending_input.chown_target_paths is not None:
        return "CHOWN"
    if state.pending_input.extract_source_path is not None:
        return "EXTRACT"
    if state.pending_input.zip_source_paths is not None:
        return "ZIP"
    if state.pending_input.symlink_source_path is not None:
        return "SYMLINK"
    if state.pending_input.create_kind is not None:
        return "CREATE"
    return "RENAME"


def browser_snapshot_invalidation_paths(
    path: str,
    *extra_paths: str | None,
) -> tuple[str, ...]:
    def _normalize(path_value: str) -> str:
        if is_windows_path(path_value):
            return normalize_windows_path(path_value)
        return str(Path(path_value).expanduser().resolve())

    if is_windows_drives_root(path):
        paths = [path]
    else:
        resolved_path = _normalize(path)
        _, parent_path = resolve_parent_directory_path(resolved_path)
        paths = [resolved_path]
        if parent_path is not None:
            paths.append(parent_path)
    for extra_path in extra_paths:
        if extra_path is not None:
            if is_windows_drives_root(extra_path):
                paths.append(extra_path)
            else:
                paths.append(_normalize(extra_path))
    return tuple(dict.fromkeys(paths))


def request_snapshot_refresh(
    state,
    *,
    cursor_path: str | None = None,
    keep_current_cursor: bool = True,
) -> ReduceResult:
    request_id = state.next_request_id
    resolved_cursor_path = (
        state.current_pane.cursor_path
        if keep_current_cursor and cursor_path is None
        else cursor_path
    )
    next_state = replace(
        state,
        pending_browser_snapshot_request_id=request_id,
        pending_child_pane_request_id=None,
        next_request_id=request_id + 1,
    )
    return ReduceResult(
        state=next_state,
        effects=(
            LoadBrowserSnapshotEffect(
                request_id=request_id,
                path=state.current_path,
                cursor_path=resolved_cursor_path,
                blocking=False,
                invalidate_paths=browser_snapshot_invalidation_paths(
                    state.current_path,
                    resolved_cursor_path,
                ),
                enable_image_preview=state.config.display.enable_image_preview,
                enable_pdf_preview=state.config.display.enable_pdf_preview,
                enable_office_preview=state.config.display.enable_office_preview,
            ),
        ),
    )


def format_clipboard_message(prefix: str, paths: tuple[str, ...]) -> str:
    noun = "item" if len(paths) == 1 else "items"
    return f"{prefix} {len(paths)} {noun} to clipboard"


def notification_for_external_launch(
    request: ExternalLaunchRequest,
) -> NotificationState | None:
    if request.kind != "copy_paths":
        return None
    noun = "path" if len(request.paths) == 1 else "paths"
    return NotificationState(
        level="info",
        message=f"Copied {len(request.paths)} {noun} to system clipboard",
        auto_dismiss=True,
    )


def _notification_details(
    failures,
    *,
    skipped_count: int = 0,
    skipped_paths: tuple[str, ...] = (),
    unprocessed_paths: tuple[str, ...] = (),
) -> NotificationDetails:
    return NotificationDetails(
        failure_count=len(failures),
        failures=tuple(
            NotificationFailureDetail(
                path=failure.destination_path or failure.source_path,
                reason=failure.message,
            )
            for failure in failures
        ),
        skipped_count=skipped_count,
        skipped_paths=skipped_paths,
        unprocessed_count=len(unprocessed_paths),
        unprocessed_paths=unprocessed_paths,
    )


def notification_for_paste_summary(
    summary: PasteSummary,
    *,
    request: PasteRequest | None = None,
    undo_entry: UndoEntry | None = None,
) -> NotificationState:
    verb = "Copied" if summary.mode == "copy" else "Moved"
    if summary.cancelled or summary.unprocessed_count or summary.skipped_paths:
        message = f"{verb} {summary.success_count}/{summary.total_count} items"
        if summary.skipped_count:
            message += f", skipped {summary.skipped_count}"
        if summary.failure_count:
            message += f", failed {summary.failure_count}"
        if summary.cancelled or summary.unprocessed_count:
            message += f", {summary.unprocessed_count} not processed"
        return NotificationState(
            level="warning",
            message=message,
            action=(
                NotificationAction(
                    action_id="notification.details",
                    label="Details",
                )
                if summary.failure_count or summary.unprocessed_count or summary.skipped_paths
                else None
            ),
            details=(
                _notification_details(
                    summary.failures,
                    skipped_count=summary.skipped_count,
                    skipped_paths=summary.skipped_paths,
                    unprocessed_paths=summary.unprocessed_paths,
                )
                if summary.failure_count or summary.unprocessed_count or summary.skipped_paths
                else None
            ),
        )
    if summary.failure_count and summary.success_count:
        details = _notification_details(summary.failures)
        return NotificationState(
            level="warning",
            message=(
                f"{verb} {summary.success_count}/{summary.total_count} items"
                f" with {summary.failure_count} failure(s)"
            ),
            action=NotificationAction(
                action_id="notification.details",
                label="Details",
            ),
            details=details,
        )
    if summary.failure_count and not summary.success_count and not summary.skipped_count:
        retryable = (
            request is not None
            and request.conflict_resolution is None
            and summary.overwrote_count == 0
        )
        details = _notification_details(summary.failures)
        return NotificationState(
            level="error",
            message=f"Failed to {summary.mode} {summary.total_count} item(s)",
            action=(
                NotificationAction(
                    action_id="notification.retry",
                    label="Retry",
                    payload=request,
                )
                if retryable
                else NotificationAction(
                    action_id="notification.details",
                    label="Details",
                )
            ),
            details=None if retryable else details,
        )
    if summary.failure_count:
        return NotificationState(
            level="warning",
            message=(
                f"{verb} {summary.success_count}/{summary.total_count} items"
                f" with {summary.failure_count} failure(s)"
            ),
            action=NotificationAction(
                action_id="notification.details",
                label="Details",
            ),
            details=_notification_details(summary.failures),
        )
    if summary.skipped_count and not summary.success_count and not summary.failure_count:
        return NotificationState(
            level="info",
            message=f"Skipped {summary.skipped_count} conflicting item(s)",
        )
    message = f"{verb} {summary.success_count} item(s)"
    if summary.skipped_count:
        message += f", skipped {summary.skipped_count}"
    if summary.overwrote_count:
        message += ", undo unavailable for overwritten items"
    final_success = (
        summary.success_count > 0
        and summary.failure_count == 0
        and summary.skipped_count == 0
    )
    undoable_success = final_success and summary.overwrote_count == 0
    return NotificationState(
        level="info",
        message=message,
        action=(
            NotificationAction(
                action_id="notification.undo",
                label="Undo",
                payload=undo_entry,
            )
            if undoable_success and undo_entry is not None
            else None
        ),
        auto_dismiss=final_success,
    )


def notification_for_duplicate_summary(
    summary: DuplicateSummary,
    *,
    request: DuplicateRequest | None = None,
    undo_entry: UndoEntry | None = None,
    applied_changes_count: int = 0,
) -> NotificationState:
    if summary.failure_count and summary.success_count:
        details = _notification_details(summary.failures)
        return NotificationState(
            level="warning",
            message=(
                f"Duplicated {summary.success_count}/{summary.total_count} item(s); "
                f"{summary.failure_count} failed"
            ),
            action=NotificationAction(
                action_id="notification.details",
                label="Details",
            ),
            details=details,
        )
    if summary.failure_count and summary.success_count == 0:
        retryable = request is not None and applied_changes_count == 0
        return NotificationState(
            level="error",
            message=f"Duplicate failed for {summary.failure_count} item(s)",
            action=(
                NotificationAction(
                    action_id="notification.retry",
                    label="Retry",
                    payload=request,
                )
                if retryable
                else NotificationAction(
                    action_id="notification.details",
                    label="Details",
                )
            ),
            details=(
                None
                if retryable
                else _notification_details(summary.failures)
            ),
        )
    pure_success = summary.success_count > 0 and summary.failure_count == 0
    return NotificationState(
        level="info",
        message=f"Duplicated {summary.success_count} item(s)",
        action=(
            NotificationAction(
                action_id="notification.undo",
                label="Undo",
                payload=undo_entry,
            )
            if pure_success and undo_entry is not None
            else None
        ),
        auto_dismiss=pure_success,
    )


def build_history_after_snapshot_load(
    state,
    next_path: str,
) -> HistoryState:
    previous_path = state.current_path
    new_history = state.history

    if not state.history.back and not state.history.forward:
        if next_path != previous_path:
            new_history = HistoryState(
                back=(previous_path,),
                forward=(),
                visited_all=(previous_path, next_path),
            )
        return new_history

    if next_path != previous_path:
        history = state.history
        if history.forward and next_path == history.forward[0]:
            new_history = HistoryState(
                back=(*history.back, previous_path),
                forward=history.forward[1:],
                visited_all=history.visited_all,
            )
        elif history.back and next_path == history.back[-1]:
            new_history = HistoryState(
                back=history.back[:-1],
                forward=(previous_path, *history.forward),
                visited_all=history.visited_all,
            )
        else:
            visited_all = history.visited_all
            if not visited_all or visited_all[-1] != next_path:
                visited_all = (*visited_all, next_path)
            new_history = HistoryState(
                back=(*history.back, previous_path),
                forward=(),
                visited_all=visited_all,
            )
    else:
        new_history = HistoryState(
            back=state.history.back,
            forward=state.history.forward,
            visited_all=state.history.visited_all,
        )
    return new_history
