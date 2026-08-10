from dataclasses import replace

from tests.test_state_reducer import _reduce_state
from zivo.models import DuplicateAppliedChange, DuplicateSummary, UndoDeletePathStep, UndoEntry
from zivo.state import (
    NotificationAction,
    NotificationState,
    RunDuplicateEffect,
    build_initial_app_state,
    reduce_app_state,
)
from zivo.state.actions import DuplicateCompleted, DuplicateProgress, DuplicateTargets


def test_duplicate_targets_starts_busy_effect_for_cursor_target() -> None:
    result = reduce_app_state(build_initial_app_state(), DuplicateTargets())

    assert result.state.ui_mode == "BUSY"
    assert result.state.pending_duplicate_request_id == 1
    assert result.effects == (
        RunDuplicateEffect(
            request_id=1,
            request=result.effects[0].request,
        ),
    )
    assert result.effects[0].request.source_paths == ("/home/tadashi/develop/zivo/docs",)
    assert result.effects[0].request.destination_dir == "/home/tadashi/develop/zivo"


def test_duplicate_progress_updates_status_and_ignores_stale_requests() -> None:
    state = replace(build_initial_app_state(), pending_duplicate_request_id=4, ui_mode="BUSY")

    next_state = _reduce_state(
        state,
        DuplicateProgress(
            request_id=4,
            completed_entries=1,
            total_entries=2,
            current_path="/tmp/first.txt",
        ),
    )
    assert next_state.notification == NotificationState(
        level="info",
        message="Duplicating 1/2 item(s): first.txt",
    )
    assert _reduce_state(state, replace(DuplicateProgress(4, 1, 2), request_id=99)) == state


def test_duplicate_completion_records_one_undo_for_successful_outputs() -> None:
    state = replace(build_initial_app_state(), pending_duplicate_request_id=4, ui_mode="BUSY")
    output = "/home/tadashi/develop/zivo/docs copy"

    next_state = _reduce_state(
        state,
        DuplicateCompleted(
            request_id=4,
            summary=DuplicateSummary(
                destination_dir="/home/tadashi/develop/zivo",
                total_count=1,
                success_count=1,
            ),
            applied_changes=(
                DuplicateAppliedChange(
                    source_path="/home/tadashi/develop/zivo/docs",
                    destination_path=output,
                ),
            ),
        ),
    )

    assert next_state.ui_mode == "BROWSING"
    assert next_state.pending_duplicate_request_id is None
    assert next_state.undo_stack == (
        UndoEntry(kind="paste_copy", steps=(UndoDeletePathStep(path=output),)),
    )
    assert next_state.post_reload_notification == NotificationState(
        level="info",
        message="Duplicated 1 item(s)",
        action=NotificationAction(
            action_id="notification.undo",
            label="Undo",
            payload=UndoEntry(
                kind="paste_copy",
                steps=(UndoDeletePathStep(path=output),),
            ),
        ),
        auto_dismiss=True,
    )
