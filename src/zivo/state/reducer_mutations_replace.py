"""Replace confirmation handlers."""

from dataclasses import replace

from zivo.models import TextReplaceRequest

from .actions_mutations import CancelReplaceConfirmation, ConfirmReplaceTargets
from .effects import (
    ReduceResult,
    RunTextReplaceApplyEffect,
)
from .models import (
    AppState,
    NotificationState,
    ReplaceConfirmationState,
)
from .reducer_common import browser_snapshot_invalidation_paths, finalize


def _handle_begin_replace_confirmation(
    state: AppState,
    mode: str,
    find_text: str,
    replacement_text: str,
    target_paths: tuple[str, ...],
    total_match_count: int,
) -> ReduceResult:
    """Display the replace confirmation dialog."""
    return finalize(
        replace(
            state,
            ui_mode="CONFIRM",
            notification=None,
            replace_confirmation=ReplaceConfirmationState(
                mode=mode,
                find_text=find_text,
                replacement_text=replacement_text,
                target_paths=target_paths,
                total_match_count=total_match_count,
            ),
        )
    )


def _handle_confirm_replace_targets(
    state: AppState,
    action: ConfirmReplaceTargets,
    reduce_state,
) -> ReduceResult:
    """Execute the replace operation after confirmation."""
    if state.replace_confirmation is None:
        return finalize(state)

    confirmation = state.replace_confirmation
    request_id = state.next_request_id
    request = TextReplaceRequest(
        paths=confirmation.target_paths,
        find_text=confirmation.find_text,
        replace_text=confirmation.replacement_text,
    )

    # First, request browser snapshot to restore browsing state
    from .actions import RequestBrowserSnapshot

    snapshot_result = reduce_state(
        replace(
            state,
            ui_mode="BROWSING",
            replace_confirmation=None,
            command_palette=None,
            pending_replace_apply_request_id=request_id,
            next_request_id=request_id + 1,
            notification=NotificationState(level="info", message="Applying replacement..."),
        ),
        RequestBrowserSnapshot(
            path=state.current_path,
            cursor_path=state.current_pane.cursor_path,
            blocking=True,
            invalidate_paths=browser_snapshot_invalidation_paths(state.current_path),
        ),
    )

    # Then, add the replace effect to the result
    return finalize(
        replace(
            snapshot_result.state,
            pending_replace_apply_request_id=request_id,
        ),
        RunTextReplaceApplyEffect(request_id=request_id, request=request),
    )


def _handle_cancel_replace_confirmation(
    state: AppState,
    action: CancelReplaceConfirmation,
) -> ReduceResult:
    """Cancel the replace operation and return to the command palette."""
    if state.replace_confirmation is None:
        return finalize(state)

    return finalize(
        replace(
            state,
            ui_mode="PALETTE",
            replace_confirmation=None,
            notification=None,
        )
    )


REPLACE_MUTATION_HANDLERS = {
    ConfirmReplaceTargets: lambda state, action, reduce_state: _handle_confirm_replace_targets(
        state, action, reduce_state
    ),
    CancelReplaceConfirmation: _handle_cancel_replace_confirmation,
}
