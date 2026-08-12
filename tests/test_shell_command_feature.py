from dataclasses import replace

from zivo.app_runtime import complete_worker_actions, failed_worker_actions
from zivo.models import ShellCommandResult
from zivo.state import (
    BackgroundCommandState,
    NotificationAction,
    NotificationState,
    RunShellCommandEffect,
    ShellCommandState,
    build_initial_app_state,
    dispatch_key_input,
    reduce_app_state,
    select_help_bar_state,
    select_shell_command_dialog_state,
)
from zivo.state.actions import (
    ActivateNotificationAction,
    BeginCommandPalette,
    BeginShellCommandInput,
    CancelBackgroundCommand,
    CancelShellCommandInput,
    OpenTerminalAtPath,
    SetCommandPaletteQuery,
    SetNotification,
    SetShellCommandValue,
    ShellCommandCompleted,
    ShellCommandFailed,
    SubmitCommandPalette,
    SubmitShellCommand,
)
from zivo.ui import ShellCommandDialog


def test_dispatch_shell_command_input_updates_value() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="SHELL",
        shell_command=ShellCommandState(cwd="/tmp/project", command="pw"),
    )

    actions = dispatch_key_input(state, key="d", character="d")

    assert actions == (
        SetNotification(None),
        SetShellCommandValue("dpw", cursor_pos=1),
    )


def test_browsing_bang_opens_shell_command_dialog() -> None:
    actions = dispatch_key_input(build_initial_app_state(), key="!", character="!")

    assert actions == (SetNotification(None), BeginShellCommandInput())


def test_dispatch_shell_command_input_backspace_and_escape() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="SHELL",
        shell_command=ShellCommandState(cwd="/tmp/project", command="pwd", cursor_pos=3),
    )

    backspace_actions = dispatch_key_input(state, key="backspace")
    escape_actions = dispatch_key_input(state, key="escape")

    assert backspace_actions == (
        SetNotification(None),
        SetShellCommandValue("pw", cursor_pos=2),
    )
    assert escape_actions == (SetNotification(None), CancelShellCommandInput())


def test_submit_command_palette_opens_shell_command_dialog() -> None:
    state = reduce_app_state(build_initial_app_state(), BeginCommandPalette()).state
    state = reduce_app_state(state, SetCommandPaletteQuery("run shell")).state

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.ui_mode == "SHELL"
    assert result.state.shell_command == ShellCommandState(
        cwd="/home/tadashi/develop/zivo",
        command="",
    )


def test_submit_shell_command_warns_for_empty_command() -> None:
    state = reduce_app_state(build_initial_app_state(), BeginShellCommandInput()).state

    next_state = reduce_app_state(state, SubmitShellCommand()).state

    assert next_state.ui_mode == "SHELL"
    assert next_state.notification == NotificationState(
        level="warning",
        message="Shell command cannot be empty",
    )


def test_submit_shell_command_emits_worker_effect() -> None:
    state = reduce_app_state(build_initial_app_state(), BeginShellCommandInput()).state
    state = reduce_app_state(state, SetShellCommandValue("pwd")).state

    result = reduce_app_state(state, SubmitShellCommand())

    assert result.state.ui_mode == "BUSY"
    assert result.state.pending_shell_command_request_id == 1
    assert result.state.background_command == BackgroundCommandState(
        request_id=1,
        label="Shell command",
    )
    assert result.effects == (
        RunShellCommandEffect(
            request_id=1,
            cwd="/home/tadashi/develop/zivo",
            command="pwd",
        ),
    )


def test_shell_command_completed_shows_result_in_dialog() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        shell_command=ShellCommandState(cwd="/tmp/project", command="ls"),
        pending_shell_command_request_id=4,
    )

    success = reduce_app_state(
        state,
        ShellCommandCompleted(
            request_id=4,
            result=ShellCommandResult(exit_code=0, stdout="first line\nsecond line\n"),
        ),
    ).state
    failure = reduce_app_state(
        state,
        ShellCommandCompleted(
            request_id=4,
            result=ShellCommandResult(exit_code=7, stderr="boom\ntraceback"),
        ),
    ).state

    # UIモードがSHELLのままであること
    assert success.ui_mode == "SHELL"
    assert failure.ui_mode == "SHELL"

    # 実行結果がShellCommandStateに保持されていること
    assert success.shell_command is not None
    assert success.shell_command.result is not None
    assert success.shell_command.result.exit_code == 0
    assert success.shell_command.result.stdout == "first line\nsecond line\n"

    assert failure.shell_command is not None
    assert failure.shell_command.result is not None
    assert failure.shell_command.result.exit_code == 7
    assert failure.shell_command.result.stderr == "boom\ntraceback"

    # 通知が設定されていないこと
    assert success.notification is None
    assert failure.notification is None


def test_shell_timeout_returns_to_browsing_with_result_action() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        shell_command=ShellCommandState(cwd="/tmp/project", command="slow"),
        pending_shell_command_request_id=4,
        background_command=BackgroundCommandState(4, "Shell command"),
    )
    timed_out = ShellCommandResult(
        exit_code=-15,
        stdout="started\n",
        termination_reason="timed_out",
        timeout_seconds=300,
    )

    result = reduce_app_state(
        state,
        ShellCommandCompleted(request_id=4, result=timed_out),
    ).state

    assert result.ui_mode == "BROWSING"
    assert result.background_command is None
    assert result.shell_command is not None
    assert result.shell_command.result == timed_out
    assert result.notification == NotificationState(
        level="warning",
        message="Command stopped after 300 seconds",
        action=NotificationAction(
            action_id="notification.shell_result",
            label="Result",
        ),
    )

    reopened = reduce_app_state(
        result,
        ActivateNotificationAction(
            action_id="notification.shell_result",
            revision=result.notification_revision,
        ),
    ).state
    assert reopened.ui_mode == "SHELL"
    assert reopened.notification is None
    assert reopened.shell_command is not None
    assert reopened.shell_command.result == timed_out


def test_busy_escape_requests_background_command_cancel() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        background_command=BackgroundCommandState(8, "Shell command"),
    )

    assert dispatch_key_input(state, key="escape") == (CancelBackgroundCommand(),)

    next_state = reduce_app_state(state, CancelBackgroundCommand()).state
    assert next_state.background_command == BackgroundCommandState(
        8,
        "Shell command",
        cancel_requested=True,
    )
    assert next_state.notification == NotificationState(
        level="info",
        message="Stopping command...",
    )


def test_select_shell_command_dialog_state_and_help() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="SHELL",
        shell_command=ShellCommandState(cwd="/tmp/project", command="pwd"),
    )

    dialog = select_shell_command_dialog_state(state)
    help_bar = select_help_bar_state(state)

    assert dialog is not None
    assert dialog.cwd == "/tmp/project"
    assert dialog.command == "pwd"
    assert dialog.result is None
    assert dialog.guidance == "Runs in the background; use t for interactive commands."
    assert help_bar.lines == ("type command | enter run | esc cancel",)


def test_select_shell_command_dialog_state_with_result() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="SHELL",
        shell_command=ShellCommandState(
            cwd="/tmp/project",
            command="pwd",
            result=ShellCommandResult(exit_code=0, stdout="/tmp/project\n"),
        ),
    )

    dialog = select_shell_command_dialog_state(state)
    help_bar = select_help_bar_state(state)

    assert dialog is not None
    assert dialog.title == "Shell Command Result"
    assert dialog.cwd == "/tmp/project"
    assert dialog.command == "pwd"
    assert dialog.result is not None
    assert dialog.result.exit_code == 0
    assert dialog.result.stdout == "/tmp/project\n"
    assert dialog.options == ("r rerun", "t terminal", "esc close")
    assert help_bar.lines == ("r rerun | t terminal | esc close",)


def test_shell_command_dialog_renders_timeout_and_stream_truncation() -> None:
    rendered = ShellCommandDialog._render_result(
        ShellCommandResult(
            exit_code=-15,
            stdout="prefix\n[... middle output omitted ...]\nsuffix",
            stderr="error",
            stdout_truncated=True,
            stderr_truncated=True,
            termination_reason="timed_out",
            output_limit_bytes=1024 * 1024,
            timeout_seconds=300,
        )
    ).plain

    assert "[Timed out after 300 seconds]" in rendered
    assert "(exit code -15)" in rendered
    assert "stdout: middle output omitted after 1 MiB" in rendered
    assert "stderr: middle output omitted after 1 MiB" in rendered


def test_shell_command_result_shortcuts_rerun_or_open_terminal() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="SHELL",
        shell_command=ShellCommandState(
            cwd="/tmp/project",
            command="pwd",
            result=ShellCommandResult(exit_code=1, stderr="failed"),
        ),
    )

    assert dispatch_key_input(state, key="r", character="r") == (
        SetNotification(None),
        SubmitShellCommand(),
    )
    assert dispatch_key_input(state, key="t", character="t") == (
        SetNotification(None),
        OpenTerminalAtPath("/tmp/project"),
    )


def test_runtime_maps_shell_command_actions() -> None:
    effect = RunShellCommandEffect(request_id=9, cwd="/tmp/project", command="pwd")

    completed = complete_worker_actions(
        effect,
        ShellCommandResult(exit_code=0, stdout="/tmp/project\n"),
    )
    failed = failed_worker_actions(effect, OSError("spawn failed"))

    assert completed == (
        ShellCommandCompleted(
            request_id=9,
            result=ShellCommandResult(exit_code=0, stdout="/tmp/project\n"),
        ),
    )
    assert failed == (ShellCommandFailed(request_id=9, message="spawn failed"),)
