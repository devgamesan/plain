"""Grep export reducer handlers."""

from dataclasses import replace
from pathlib import Path

from .actions import (
    GrepExportCompleted,
    GrepExportFailed,
    SaveGrepResults,
)
from .effects import ReduceResult, RunGrepExportEffect
from .models import (
    AppState,
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


def handle_save_grep_results(state: AppState, action: SaveGrepResults) -> ReduceResult:
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
    output_path = str(Path(state.current_path) / "grep_results.txt")
    if Path(output_path).exists():
        return finalize(
            replace(
                state,
                notification=NotificationState(
                    level="warning", message=f"File already exists: {output_path}"
                ),
            )
        )
    request_id = state.next_request_id
    return finalize(
        replace(
            state,
            pending_grep_export_request_id=request_id,
            next_request_id=request_id + 1,
        ),
        RunGrepExportEffect(
            request_id=request_id,
            output_path=output_path,
            context_lines=state.config.display.grep_preview_context_lines,
            results=results,
        )
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
                auto_dismiss=True,
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
