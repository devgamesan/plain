from dataclasses import replace

from zivo.app_runtime import complete_worker_actions, failed_worker_actions
from zivo.models import ShellCommandResult
from zivo.state import (
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
    BeginCommandPalette,
    BeginShellCommandInput,
    CancelShellCommandInput,
    SetCommandPaletteQuery,
    SetNotification,
    SetShellCommandValue,
    ShellCommandCompleted,
    ShellCommandFailed,
    SubmitCommandPalette,
    SubmitShellCommand,
)


def test_dispatch_shell_command_input_updates_value() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="SHELL",
        shell_command=ShellCommandState(cwd="/tmp/project", command="pw"),
    )

    actions = dispatch_key_input(state, key="d", character="d")

    assert actions == (SetNotification(None), SetShellCommandValue("pwd"))


def test_browsing_bang_opens_shell_command_dialog() -> None:
    actions = dispatch_key_input(build_initial_app_state(), key="!", character="!")

    assert actions == (SetNotification(None), BeginShellCommandInput())


def test_dispatch_shell_command_input_backspace_and_escape() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="SHELL",
        shell_command=ShellCommandState(cwd="/tmp/project", command="pwd"),
    )

    backspace_actions = dispatch_key_input(state, key="backspace")
    escape_actions = dispatch_key_input(state, key="escape")

    assert backspace_actions == (SetNotification(None), SetShellCommandValue("pw"))
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
    assert result.effects == (
        RunShellCommandEffect(
            request_id=1,
            cwd="/home/tadashi/develop/zivo",
            command="pwd",
        ),
    )


def test_shell_command_completed_formats_notifications() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
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

    assert success.notification == NotificationState(level="info", message="first line")
    assert failure.notification == NotificationState(
        level="error",
        message="Command failed (7): boom",
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
    assert help_bar.lines == ("type command | enter run | esc cancel",)


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
