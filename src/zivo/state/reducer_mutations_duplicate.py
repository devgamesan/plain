"""Same-directory duplicate reducer handlers."""

from dataclasses import replace
from pathlib import Path

from zivo.models import DuplicateRequest

from .actions import DuplicateCompleted, DuplicateFailed, DuplicateProgress, DuplicateTargets
from .effects import ReduceResult, RunDuplicateEffect
from .models import AppState, NotificationState
from .reducer_common import (
    ReducerFn,
    finalize,
    notification_for_duplicate_summary,
    request_snapshot_refresh,
)
from .reducer_mutations_common import push_undo_entry, undo_entry_for_duplicate
from .selectors import select_target_paths


def run_duplicate_request(
    state: AppState,
    request: DuplicateRequest,
) -> ReduceResult:
    """Start duplicate execution with a fresh service-side name preflight."""

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
    return ReduceResult(
        state=replace(
            state,
            command_palette=None,
            notification=NotificationState(
                level="info",
                message=f"Duplicating {len(request.source_paths)} item(s)...",
            ),
            pending_duplicate_request_id=request_id,
            pending_duplicate_request=request,
            ui_mode="BUSY",
            next_request_id=request_id + 1,
        ),
        effects=(RunDuplicateEffect(request_id=request_id, request=request),),
    )


def _handle_duplicate_targets(state: AppState, action, reduce_state: ReducerFn) -> ReduceResult:
    del action, reduce_state
    target_paths = select_target_paths(state)
    if not target_paths:
        return finalize(
            replace(
                state,
                notification=NotificationState(
                    level="warning",
                    message="Duplicate requires a target",
                ),
            )
        )
    return run_duplicate_request(
        state,
        DuplicateRequest(
            source_paths=target_paths,
            destination_dir=state.current_pane.directory_path,
        ),
    )


def _handle_duplicate_progress(state: AppState, action, reduce_state: ReducerFn) -> ReduceResult:
    del reduce_state
    if action.request_id != state.pending_duplicate_request_id:
        return finalize(state)
    current = Path(action.current_path).name if action.current_path else ""
    suffix = f": {current}" if current else ""
    return finalize(
        replace(
            state,
            notification=NotificationState(
                level="info",
                message=(
                    f"Duplicating {action.completed_entries}/{action.total_entries} item(s){suffix}"
                ),
            ),
        )
    )


def _handle_duplicate_completed(state: AppState, action, reduce_state: ReducerFn) -> ReduceResult:
    del reduce_state
    if action.request_id != state.pending_duplicate_request_id:
        return finalize(state)
    summary = action.summary
    notification = notification_for_duplicate_summary(
        summary,
        request=state.pending_duplicate_request,
        undo_entry=undo_entry_for_duplicate(action.applied_changes),
        applied_changes_count=len(action.applied_changes),
    )
    next_state = replace(
        state,
        command_palette=None,
        notification=None,
        post_reload_notification=notification,
        pending_duplicate_request_id=None,
        pending_duplicate_request=None,
        undo_stack=push_undo_entry(
            state,
            undo_entry_for_duplicate(action.applied_changes),
        ),
        ui_mode="BROWSING",
    )
    return request_snapshot_refresh(next_state)


def _handle_duplicate_failed(state: AppState, action, reduce_state: ReducerFn) -> ReduceResult:
    del reduce_state
    if action.request_id != state.pending_duplicate_request_id:
        return finalize(state)
    return finalize(
        replace(
            state,
            notification=NotificationState(level="error", message=action.message),
            pending_duplicate_request_id=None,
            pending_duplicate_request=None,
            ui_mode="BROWSING",
        )
    )


DUPLICATE_MUTATION_HANDLERS = {
    DuplicateTargets: _handle_duplicate_targets,
    DuplicateProgress: _handle_duplicate_progress,
    DuplicateCompleted: _handle_duplicate_completed,
    DuplicateFailed: _handle_duplicate_failed,
}
