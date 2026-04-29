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
    assert help_bar.lines == ("press esc to close",)


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
