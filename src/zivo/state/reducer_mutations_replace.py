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
    ForegroundOperationState,
    NotificationState,
    ReplaceConfirmationState,
)
from .reducer_common import finalize


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
    request = TextReplaceRequest(
        paths=confirmation.target_paths,
        find_text=confirmation.find_text,
        replace_text=confirmation.replacement_text,
    )

    return finalize(
        replace(
            state,
            # The confirmation is the foreground step; the confirmed
            # replacement itself runs while browsing remains available.
            ui_mode="BROWSING",
            replace_confirmation=None,
            command_palette=None,
            pending_input=None,
            pending_replace_apply_request_id=request_id,
            next_request_id=request_id + 1,
            notification=NotificationState(level="info", message="Applying replacement..."),
            foreground_operation=ForegroundOperationState(
                operation_id=request_id,
                kind="replace",
                total=len(request.paths),
                message="Applying replacement",
            ),
        ),
        RunTextReplaceApplyEffect(request_id=request_id, request=request),
    )


def _handle_cancel_replace_confirmation(
    state: AppState,
    action: CancelReplaceConfirmation,
    reduce_state=None,
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
