from dataclasses import replace

from zivo.models import (
    CustomActionExecutionRequest,
    CustomActionResult,
    ShellCommandResult,
)
from zivo.state import BackgroundCommandState, NotificationState, build_initial_app_state
from zivo.state.actions import CustomActionCompleted
from zivo.state.reducer import reduce_app_state


def _request() -> CustomActionExecutionRequest:
    return CustomActionExecutionRequest(
        name="Check project",
        command=("check",),
        cwd="/tmp/project",
        mode="background",
    )


def _running_state():
    return replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        pending_custom_action_request_id=7,
        background_command=BackgroundCommandState(7, "Check project"),
    )


def test_truncated_background_custom_action_warns_and_returns_to_browsing() -> None:
    result = reduce_app_state(
        _running_state(),
        CustomActionCompleted(
            request_id=7,
            request=_request(),
            result=CustomActionResult(
                name="Check project",
                result=ShellCommandResult(
                    exit_code=0,
                    stdout="done\n",
                    stdout_truncated=True,
                ),
            ),
        ),
    ).state

    assert result.ui_mode == "BROWSING"
    assert result.background_command is None
    assert result.notification == NotificationState(
        level="warning",
        message="done; output omitted",
    )


def test_timed_out_background_custom_action_reports_error() -> None:
    result = reduce_app_state(
        _running_state(),
        CustomActionCompleted(
            request_id=7,
            request=_request(),
            result=CustomActionResult(
                name="Check project",
                result=ShellCommandResult(
                    exit_code=-15,
                    termination_reason="timed_out",
                    timeout_seconds=300,
                ),
            ),
        ),
    ).state

    assert result.ui_mode == "BROWSING"
    assert result.background_command is None
    assert result.notification == NotificationState(
        level="error",
        message="Check project stopped after 300 seconds",
    )


def test_cancelled_background_custom_action_reports_warning() -> None:
    result = reduce_app_state(
        _running_state(),
        CustomActionCompleted(
            request_id=7,
            request=_request(),
            result=CustomActionResult(
                name="Check project",
                result=ShellCommandResult(
                    exit_code=-15,
                    termination_reason="cancelled",
                ),
            ),
        ),
    ).state

    assert result.ui_mode == "BROWSING"
    assert result.notification == NotificationState(
        level="warning",
        message="Check project cancelled",
    )
