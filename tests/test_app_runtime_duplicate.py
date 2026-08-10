from zivo.app_runtime import complete_worker_actions
from zivo.models import (
    DuplicateAppliedChange,
    DuplicateExecutionResult,
    DuplicateRequest,
    DuplicateSummary,
)
from zivo.state import RunDuplicateEffect
from zivo.state.actions import DuplicateCompleted


def test_complete_worker_actions_maps_duplicate_result() -> None:
    effect = RunDuplicateEffect(
        request_id=7,
        request=DuplicateRequest(("/tmp/report.pdf",), "/tmp"),
    )
    result = DuplicateExecutionResult(
        summary=DuplicateSummary(destination_dir="/tmp", total_count=1, success_count=1),
        applied_changes=(
            DuplicateAppliedChange("/tmp/report.pdf", "/tmp/report copy.pdf"),
        ),
    )

    assert complete_worker_actions(effect, result) == (
        DuplicateCompleted(
            request_id=7,
            summary=result.summary,
            applied_changes=result.applied_changes,
        ),
    )
