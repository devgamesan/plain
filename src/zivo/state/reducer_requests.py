"""Reducer request builders and shared transition helpers."""

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from zivo.models import (
    CreatePathRequest,
    CreateSymlinkRequest,
    CreateZipArchiveRequest,
    DeleteRequest,
    ExternalLaunchRequest,
    ExtractArchiveRequest,
    FileMutationResult,
    PasteRequest,
    PasteSummary,
    RenameRequest,
    UndoEntry,
)

from .actions import Action
from .effects import (
    Effect,
    LoadBrowserSnapshotEffect,
    ReduceResult,
    RunArchiveExtractEffect,
    RunArchivePreparationEffect,
    RunClipboardPasteEffect,
    RunExternalLaunchEffect,
    RunFileMutationEffect,
    RunUndoEffect,
    RunZipCompressEffect,
    RunZipCompressPreparationEffect,
)
from .models import HistoryState, NotificationState

ReducerFn = Callable[[object, Action], ReduceResult]


def finalize(next_state, *effects: Effect) -> ReduceResult:
    """Wrap a state transition and optional side effects into a ReduceResult."""

    return ReduceResult(state=next_state, effects=effects)


def run_paste_request(state, request: PasteRequest) -> ReduceResult:
    request_id = state.next_request_id
    next_state = replace(
        state,
        notification=None,
        paste_conflict=None,
        delete_confirmation=None,
        pending_paste_request_id=request_id,
        next_request_id=request_id + 1,
        ui_mode="BUSY",
    )
    return ReduceResult(
        state=next_state,
        effects=(RunClipboardPasteEffect(request_id=request_id, request=request),),
    )


def run_external_launch_request(
    state,
    request: ExternalLaunchRequest,
) -> ReduceResult:
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
    request: RenameRequest | CreatePathRequest | CreateSymlinkRequest | DeleteRequest,
) -> ReduceResult:
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


def run_undo_request(state, entry: UndoEntry) -> ReduceResult:
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
    request_id = state.next_request_id
    next_state = replace(
        state,
        notification=NotificationState(level="info", message="Preparing archive extraction"),
        delete_confirmation=None,
        archive_extract_confirmation=None,
        archive_extract_progress=None,
        pending_archive_prepare_request_id=request_id,
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
    request_id = state.next_request_id
    next_state = replace(
        state,
        notification=NotificationState(level="info", message="Extracting archive..."),
        archive_extract_confirmation=None,
        archive_extract_progress=None,
        pending_archive_extract_request_id=request_id,
        next_request_id=request_id + 1,
        ui_mode="BUSY",
    )
    return ReduceResult(
        state=next_state,
        effects=(RunArchiveExtractEffect(request_id=request_id, request=request),),
    )


def run_zip_compress_prepare_request(
    state,
    request: CreateZipArchiveRequest,
) -> ReduceResult:
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
    request_id = state.next_request_id
    next_state = replace(
        state,
        notification=NotificationState(level="info", message="Compressing as zip..."),
        zip_compress_confirmation=None,
        zip_compress_progress=None,
        pending_zip_compress_request_id=request_id,
        next_request_id=request_id + 1,
        ui_mode="BUSY",
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


def restore_ui_mode_after_pending_input(state) -> str:
    if state.pending_input is None:
        return "BROWSING"
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
    resolved_path = str(Path(path).expanduser().resolve())
    paths = [resolved_path, str(Path(resolved_path).parent)]
    for extra_path in extra_paths:
        if extra_path is not None:
            paths.append(str(Path(extra_path).expanduser().resolve()))
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
    )


def notification_for_paste_summary(summary: PasteSummary) -> NotificationState:
    verb = "Copied" if summary.mode == "copy" else "Moved"
    if summary.failure_count and summary.success_count:
        return NotificationState(
            level="warning",
            message=(
                f"{verb} {summary.success_count}/{summary.total_count} items"
                f" with {summary.failure_count} failure(s)"
            ),
        )
    if summary.failure_count and not summary.success_count and not summary.skipped_count:
        return NotificationState(
            level="error",
            message=f"Failed to {summary.mode} {summary.total_count} item(s)",
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
    return NotificationState(level="info", message=message)


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
