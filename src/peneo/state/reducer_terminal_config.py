"""Terminal, config, external launch, and shell command reducer handlers."""

from dataclasses import replace
from textwrap import shorten

from peneo.models import BookmarkConfig, ExternalLaunchRequest

from .actions import (
    Action,
    AddBookmark,
    BeginShellCommandInput,
    CancelShellCommandInput,
    ConfigSaveCompleted,
    ConfigSaveFailed,
    CopyPathsToClipboard,
    CycleConfigEditorValue,
    DismissConfigEditor,
    ExternalLaunchCompleted,
    ExternalLaunchFailed,
    FocusSplitTerminal,
    MoveConfigEditorCursor,
    OpenPathInEditor,
    OpenPathWithDefaultApp,
    OpenTerminalAtPath,
    PasteFromClipboardToTerminal,
    RemoveBookmark,
    SaveConfigEditor,
    SendSplitTerminalInput,
    SetShellCommandValue,
    SetTerminalHeight,
    ShellCommandCompleted,
    ShellCommandFailed,
    SplitTerminalExited,
    SplitTerminalOutputReceived,
    SplitTerminalStarted,
    SplitTerminalStartFailed,
    SubmitShellCommand,
    ToggleSplitTerminal,
)
from .effects import (
    CloseSplitTerminalEffect,
    PasteFromClipboardEffect,
    ReduceResult,
    RunConfigSaveEffect,
    RunShellCommandEffect,
    StartSplitTerminalEffect,
    WriteSplitTerminalInputEffect,
)
from .models import AppState, NotificationState, ShellCommandState, SplitTerminalState
from .reducer_common import (
    ReducerFn,
    apply_config_to_runtime_state,
    cycle_config_editor_value,
    done,
    maybe_request_directory_sizes,
    normalize_config_editor_cursor,
    notification_for_external_launch,
    run_external_launch_request,
    split_terminal_exit_message,
)
from .selectors import select_target_paths


def handle_terminal_config_action(
    state: AppState,
    action: Action,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    if isinstance(action, BeginShellCommandInput):
        return done(
            replace(
                state,
                ui_mode="SHELL",
                notification=None,
                pending_input=None,
                command_palette=None,
                shell_command=ShellCommandState(cwd=state.current_path),
                pending_file_search_request_id=None,
                pending_grep_search_request_id=None,
                paste_conflict=None,
                delete_confirmation=None,
                name_conflict=None,
                attribute_inspection=None,
            )
        )

    if isinstance(action, DismissConfigEditor):
        return done(
            replace(
                state,
                ui_mode="BROWSING",
                notification=None,
                config_editor=None,
            )
        )

    if isinstance(action, CancelShellCommandInput):
        return done(
            replace(
                state,
                ui_mode="BROWSING",
                notification=None,
                shell_command=None,
            )
        )

    if isinstance(action, SetShellCommandValue):
        if state.shell_command is None:
            return done(state)
        return done(
            replace(
                state,
                shell_command=replace(state.shell_command, command=action.command),
            )
        )

    if isinstance(action, MoveConfigEditorCursor):
        if state.config_editor is None:
            return done(state)
        return done(
            replace(
                state,
                config_editor=replace(
                    state.config_editor,
                    cursor_index=normalize_config_editor_cursor(
                        state.config_editor.cursor_index + action.delta
                    ),
                ),
            )
        )

    if isinstance(action, CycleConfigEditorValue):
        if state.config_editor is None:
            return done(state)
        next_draft = cycle_config_editor_value(
            state.config_editor.draft,
            state.config_editor.cursor_index,
            action.delta,
        )
        return done(
            replace(
                state,
                config_editor=replace(
                    state.config_editor,
                    draft=next_draft,
                    dirty=next_draft != state.config,
                ),
            )
        )

    if isinstance(action, SaveConfigEditor):
        if state.config_editor is None:
            return done(state)
        request_id = state.next_request_id
        return done(
            replace(
                state,
                notification=None,
                pending_config_save_request_id=request_id,
                next_request_id=request_id + 1,
            ),
            RunConfigSaveEffect(
                request_id=request_id,
                path=state.config_editor.path,
                config=state.config_editor.draft,
            ),
        )

    if isinstance(action, SubmitShellCommand):
        if state.shell_command is None:
            return done(state)
        command = state.shell_command.command.strip()
        if not command:
            return done(
                replace(
                    state,
                    notification=NotificationState(
                        level="warning",
                        message="Shell command cannot be empty",
                    ),
                )
            )
        request_id = state.next_request_id
        return done(
            replace(
                state,
                ui_mode="BUSY",
                notification=NotificationState(level="info", message="Running shell command..."),
                shell_command=None,
                pending_shell_command_request_id=request_id,
                next_request_id=request_id + 1,
            ),
            RunShellCommandEffect(
                request_id=request_id,
                cwd=state.current_path,
                command=command,
            ),
        )

    if isinstance(action, AddBookmark):
        if action.path in state.config.bookmarks.paths:
            return done(
                replace(
                    state,
                    notification=NotificationState(
                        level="info",
                        message="Directory is already bookmarked",
                    ),
                )
            )
        next_config = replace(
            state.config,
            bookmarks=BookmarkConfig(
                paths=(*state.config.bookmarks.paths, action.path),
            ),
        )
        request_id = state.next_request_id
        return done(
            replace(
                state,
                notification=None,
                pending_config_save_request_id=request_id,
                next_request_id=request_id + 1,
            ),
            RunConfigSaveEffect(
                request_id=request_id,
                path=state.config_path,
                config=next_config,
            ),
        )

    if isinstance(action, RemoveBookmark):
        if action.path not in state.config.bookmarks.paths:
            return done(
                replace(
                    state,
                    notification=NotificationState(
                        level="warning",
                        message="Directory is not bookmarked",
                    ),
                )
            )
        next_config = replace(
            state.config,
            bookmarks=BookmarkConfig(
                paths=tuple(path for path in state.config.bookmarks.paths if path != action.path),
            ),
        )
        request_id = state.next_request_id
        return done(
            replace(
                state,
                notification=None,
                pending_config_save_request_id=request_id,
                next_request_id=request_id + 1,
            ),
            RunConfigSaveEffect(
                request_id=request_id,
                path=state.config_path,
                config=next_config,
            ),
        )

    if isinstance(action, OpenPathWithDefaultApp):
        return run_external_launch_request(
            replace(state, notification=None),
            ExternalLaunchRequest(kind="open_file", path=action.path),
        )

    if isinstance(action, OpenPathInEditor):
        return run_external_launch_request(
            replace(state, notification=None),
            ExternalLaunchRequest(kind="open_editor", path=action.path),
        )

    if isinstance(action, OpenTerminalAtPath):
        return run_external_launch_request(
            replace(state, notification=None),
            ExternalLaunchRequest(kind="open_terminal", path=action.path),
        )

    if isinstance(action, CopyPathsToClipboard):
        target_paths = select_target_paths(state)
        if not target_paths:
            return done(
                replace(
                    state,
                    notification=NotificationState(level="warning", message="Nothing to copy"),
                )
            )
        return run_external_launch_request(
            replace(state, notification=None),
            ExternalLaunchRequest(kind="copy_paths", paths=target_paths),
        )

    if isinstance(action, ToggleSplitTerminal):
        if state.split_terminal.visible:
            next_state = replace(
                state,
                split_terminal=SplitTerminalState(),
                notification=None,
            )
            session_id = state.split_terminal.session_id
            if session_id is None:
                return done(next_state)
            return done(next_state, CloseSplitTerminalEffect(session_id=session_id))

        session_id = state.next_request_id
        next_state = replace(
            state,
            notification=None,
            next_request_id=session_id + 1,
            split_terminal=SplitTerminalState(
                visible=True,
                focus_target="terminal",
                status="starting",
                cwd=state.current_path,
                session_id=session_id,
            ),
        )
        return done(
            next_state,
            StartSplitTerminalEffect(session_id=session_id, cwd=state.current_path),
        )

    if isinstance(action, FocusSplitTerminal):
        if not state.split_terminal.visible or state.split_terminal.status != "running":
            return done(state)
        return done(
            replace(
                state,
                notification=None,
                split_terminal=replace(state.split_terminal, focus_target=action.target),
            )
        )

    if isinstance(action, SendSplitTerminalInput):
        session_id = state.split_terminal.session_id
        if (
            not state.split_terminal.visible
            or state.split_terminal.status != "running"
            or session_id is None
        ):
            return done(state)
        return done(
            state,
            WriteSplitTerminalInputEffect(session_id=session_id, data=action.data),
        )

    if isinstance(action, PasteFromClipboardToTerminal):
        session_id = state.split_terminal.session_id
        if (
            not state.split_terminal.visible
            or state.split_terminal.status != "running"
            or session_id is None
        ):
            return done(state)
        return done(
            state,
            PasteFromClipboardEffect(session_id=session_id),
        )

    if isinstance(action, ExternalLaunchCompleted):
        notification = notification_for_external_launch(action.request)
        if notification is None:
            return done(state)
        return done(replace(state, notification=notification))

    if isinstance(action, ExternalLaunchFailed):
        return done(
            replace(
                state,
                notification=NotificationState(level="error", message=action.message),
            )
        )

    if isinstance(action, ShellCommandCompleted):
        if state.pending_shell_command_request_id != action.request_id:
            return done(state)
        level, message = _notification_for_shell_command(action.result)
        return done(
            replace(
                state,
                ui_mode="BROWSING",
                notification=NotificationState(level=level, message=message),
                pending_shell_command_request_id=None,
            )
        )

    if isinstance(action, ShellCommandFailed):
        if state.pending_shell_command_request_id != action.request_id:
            return done(state)
        return done(
            replace(
                state,
                ui_mode="BROWSING",
                notification=NotificationState(level="error", message=action.message),
                pending_shell_command_request_id=None,
            )
        )

    if isinstance(action, SplitTerminalStarted):
        if state.split_terminal.session_id != action.session_id:
            return done(state)
        return done(
            replace(
                state,
                split_terminal=replace(
                    state.split_terminal,
                    status="running",
                    cwd=action.cwd,
                ),
                notification=NotificationState(level="info", message="Split terminal opened"),
            )
        )

    if isinstance(action, SplitTerminalStartFailed):
        if state.split_terminal.session_id != action.session_id:
            return done(state)
        return done(
            replace(
                state,
                split_terminal=SplitTerminalState(),
                notification=NotificationState(level="error", message=action.message),
            )
        )

    if isinstance(action, SplitTerminalOutputReceived):
        return done(state)

    if isinstance(action, SplitTerminalExited):
        if state.split_terminal.session_id != action.session_id:
            return done(state)
        return done(
            replace(
                state,
                split_terminal=SplitTerminalState(),
                notification=NotificationState(
                    level="info",
                    message=split_terminal_exit_message(action.exit_code),
                ),
            )
        )

    if isinstance(action, ConfigSaveCompleted):
        if state.pending_config_save_request_id != action.request_id:
            return done(state)
        next_config_editor = state.config_editor
        if next_config_editor is not None:
            next_config_editor = replace(
                next_config_editor,
                path=action.path,
                draft=action.config,
                dirty=False,
            )
        next_state = apply_config_to_runtime_state(
            replace(
                state,
                config=action.config,
                config_path=action.path,
                config_editor=next_config_editor,
                pending_config_save_request_id=None,
                notification=NotificationState(
                    level="info",
                    message=f"Config saved: {action.path}",
                ),
            ),
            action.config,
        )
        return maybe_request_directory_sizes(next_state, reduce_state)

    if isinstance(action, ConfigSaveFailed):
        if state.pending_config_save_request_id != action.request_id:
            return done(state)
        return done(
            replace(
                state,
                pending_config_save_request_id=None,
                notification=NotificationState(
                    level="error",
                    message=f"Failed to save config: {action.message}",
                ),
            )
        )

    if isinstance(action, SetTerminalHeight):
        if action.height == state.terminal_height:
            return done(state)
        return done(replace(state, terminal_height=action.height))

    return None


def _notification_for_shell_command(result) -> tuple[str, str]:
    if result.exit_code == 0:
        detail = _first_shell_output_line(result.stdout)
        if detail is None:
            return ("info", "Shell command finished successfully")
        return ("info", _truncate_shell_notification(detail))

    detail = _first_shell_output_line(result.stderr) or _first_shell_output_line(result.stdout)
    if detail is None:
        return ("error", f"Shell command failed with exit code {result.exit_code}")
    return (
        "error",
        _truncate_shell_notification(f"Command failed ({result.exit_code}): {detail}"),
    )


def _first_shell_output_line(output: str) -> str | None:
    for line in output.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def _truncate_shell_notification(message: str) -> str:
    return shorten(message, width=120, placeholder="...")
