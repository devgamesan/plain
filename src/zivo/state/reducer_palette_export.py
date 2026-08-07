"""Grep export reducer handlers."""

from dataclasses import replace
from pathlib import Path

from .actions import (
    BeginGrepExport,
    CancelGrepExport,
    GrepExportCompleted,
    GrepExportFailed,
    SetGrepExportFilename,
    SetGrepExportFormat,
    SubmitGrepExport,
)
from .effects import ReduceResult, RunGrepExportEffect
from .models import (
    AppState,
    GrepExportDialogState,
    GrepSearchResultState,
    NotificationState,
)
from .reducer_common import finalize


def _get_current_grep_results(state: AppState) -> tuple[GrepSearchResultState, ...]:
    if state.command_palette is None:
        return ()
    source = state.command_palette.source
    if source == "grep_search":
        return state.command_palette.grep_search.results
    if source == "replace_in_grep_files":
        return state.command_palette.grf.grep_results
    if source == "grep_replace_selected":
        return state.command_palette.grs.grep_results
    return ()


def _get_current_grep_keyword(state: AppState) -> str:
    if state.command_palette is None:
        return ""
    source = state.command_palette.source
    if source == "grep_search":
        return state.command_palette.grep_search.keyword
    if source == "replace_in_grep_files":
        return state.command_palette.grf.keyword
    if source == "grep_replace_selected":
        return state.command_palette.grs.keyword
    return ""


def handle_begin_grep_export(state: AppState, action: BeginGrepExport) -> ReduceResult:
    del action
    if state.command_palette is None:
        return finalize(state)
    results = _get_current_grep_results(state)
    if not results:
        return finalize(
            replace(
                state,
                notification=NotificationState(
                    level="warning", message="No grep results to export"
                ),
            )
        )
    default_path = str(Path(state.current_path) / "grep_results.txt")
    return finalize(
        replace(
            state,
            ui_mode="GREP_EXPORT",
            grep_export_dialog=GrepExportDialogState(
                filename=default_path,
                format="single_line",
                context_lines=state.config.display.grep_preview_context_lines,
            ),
        )
    )


def handle_cancel_grep_export(state: AppState, action: CancelGrepExport) -> ReduceResult:
    del action
    next_state = replace(
        state,
        ui_mode="PALETTE",
        grep_export_dialog=None,
        pending_grep_export_request_id=None,
    )
    return finalize(next_state)


def handle_set_grep_export_format(
    state: AppState, action: SetGrepExportFormat
) -> ReduceResult:
    if state.grep_export_dialog is None:
        return finalize(state)
    return finalize(
        replace(
            state,
            grep_export_dialog=replace(state.grep_export_dialog, format=action.format),
        )
    )


def handle_set_grep_export_filename(
    state: AppState, action: SetGrepExportFilename
) -> ReduceResult:
    if state.grep_export_dialog is None:
        return finalize(state)
    return finalize(
        replace(
            state,
            grep_export_dialog=replace(
                state.grep_export_dialog,
                filename=action.filename,
                cursor_pos=action.cursor_pos,
            ),
        )
    )


def handle_submit_grep_export(state: AppState, action: SubmitGrepExport) -> ReduceResult:
    del action
    if state.grep_export_dialog is None or state.command_palette is None:
        return finalize(state)

    dialog = state.grep_export_dialog
    if not dialog.filename.strip():
        return finalize(
            replace(
                state,
                notification=NotificationState(level="error", message="Filename cannot be empty"),
            )
        )

    output_path = str(Path(state.current_path) / dialog.filename.strip())

    if Path(output_path).exists():
        return finalize(
            replace(
                state,
                notification=NotificationState(
                    level="warning",
                    message=f"File already exists: {output_path}",
                ),
            )
        )

    results = _get_current_grep_results(state)
    search_query = _get_current_grep_keyword(state)
    request_id = state.next_request_id

    return finalize(
        replace(
            state,
            pending_grep_export_request_id=request_id,
            grep_export_dialog=None,
            ui_mode="PALETTE",
            next_request_id=request_id + 1,
        ),
        RunGrepExportEffect(
            request_id=request_id,
            output_path=output_path,
            format=dialog.format,
            context_lines=dialog.context_lines,
            results=results,
            search_query=search_query,
        ),
    )


def handle_grep_export_completed(
    state: AppState, action: GrepExportCompleted
) -> ReduceResult:
    if action.request_id != state.pending_grep_export_request_id:
        return finalize(state)
    return finalize(
        replace(
            state,
            pending_grep_export_request_id=None,
            notification=NotificationState(
                level="info",
                message=f"Exported {action.exported_results} results to {action.destination_path}",
            ),
        )
    )


def handle_grep_export_failed(
    state: AppState, action: GrepExportFailed
) -> ReduceResult:
    if action.request_id != state.pending_grep_export_request_id:
        return finalize(state)
    return finalize(
        replace(
            state,
            pending_grep_export_request_id=None,
            notification=NotificationState(level="error", message=action.message),
        )
    )
