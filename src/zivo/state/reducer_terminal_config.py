"""Terminal, config, external launch, and shell command reducer handlers."""

from dataclasses import replace
from textwrap import shorten
from typing import Callable

from zivo.models import BookmarkConfig, ExternalLaunchRequest, HelpBarConfig

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
    ResetHelpBarConfig,
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
    finalize,
    move_config_cursor_visual,
    notification_for_external_launch,
    run_external_launch_request,
    split_terminal_exit_message,
    sync_child_pane,
)
from .selectors import select_target_paths


def handle_terminal_config_action(
    state: AppState,
    action: Action,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    handler = _TERMINAL_CONFIG_HANDLERS.get(type(action))
    if handler is not None:
        return handler(state, action, reduce_state)  # type: ignore[arg-type]
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


# ---------------------------------------------------------------------------
# Individual handler functions
# ---------------------------------------------------------------------------


def _handle_begin_shell_command_input(
    state: AppState,
    action: BeginShellCommandInput,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return finalize(
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


def _handle_dismiss_config_editor(
    state: AppState,
    action: DismissConfigEditor,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return finalize(
        replace(
            state,
            ui_mode="BROWSING",
            notification=None,
            config_editor=None,
        )
    )


def _handle_cancel_shell_command_input(
    state: AppState,
    action: CancelShellCommandInput,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return finalize(
        replace(
            state,
            ui_mode="BROWSING",
            notification=None,
            shell_command=None,
        )
    )


def _handle_set_shell_command_value(
    state: AppState,
    action: SetShellCommandValue,
    reduce_state: ReducerFn,
) -> ReduceResult:
    if state.shell_command is None:
        return finalize(state)
    return finalize(
        replace(
            state,
            shell_command=replace(state.shell_command, command=action.command),
        )
    )


def _handle_move_config_editor_cursor(
    state: AppState,
    action: MoveConfigEditorCursor,
    reduce_state: ReducerFn,
) -> ReduceResult:
    if state.config_editor is None:
        return finalize(state)
    return finalize(
        replace(
            state,
            config_editor=replace(
                state.config_editor,
                cursor_index=move_config_cursor_visual(
                    state.config_editor.cursor_index, action.delta
                ),
            ),
        )
    )


def _handle_cycle_config_editor_value(
    state: AppState,
    action: CycleConfigEditorValue,
    reduce_state: ReducerFn,
) -> ReduceResult:
    if state.config_editor is None:
        return finalize(state)
    next_draft = cycle_config_editor_value(
        state.config_editor.draft,
        state.config_editor.cursor_index,
        action.delta,
    )
    return finalize(
        replace(
            state,
            config_editor=replace(
                state.config_editor,
                draft=next_draft,
                dirty=next_draft != state.config,
            ),
        )
    )


def _handle_save_config_editor(
    state: AppState,
    action: SaveConfigEditor,
    reduce_state: ReducerFn,
) -> ReduceResult:
    if state.config_editor is None:
        return finalize(state)
    request_id = state.next_request_id
    return finalize(
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


def _handle_submit_shell_command(
    state: AppState,
    action: SubmitShellCommand,
    reduce_state: ReducerFn,
) -> ReduceResult:
    if state.shell_command is None:
        return finalize(state)
    command = state.shell_command.command.strip()
    if not command:
        return finalize(
            replace(
                state,
                notification=NotificationState(
                    level="warning",
                    message="Shell command cannot be empty",
                ),
            )
        )
    request_id = state.next_request_id
    return finalize(
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


def _handle_add_bookmark(
    state: AppState,
    action: AddBookmark,
    reduce_state: ReducerFn,
) -> ReduceResult:
    if action.path in state.config.bookmarks.paths:
        return finalize(
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
    return finalize(
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


def _handle_remove_bookmark(
    state: AppState,
    action: RemoveBookmark,
    reduce_state: ReducerFn,
) -> ReduceResult:
    if action.path not in state.config.bookmarks.paths:
        return finalize(
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
    return finalize(
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


def _handle_reset_help_bar_config(
    state: AppState,
    action: ResetHelpBarConfig,
    reduce_state: ReducerFn,
) -> ReduceResult:
    next_config = replace(
        state.config,
        help_bar=HelpBarConfig(),
    )
    request_id = state.next_request_id
    return finalize(
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


def _handle_open_path_with_default_app(
    state: AppState,
    action: OpenPathWithDefaultApp,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return run_external_launch_request(
        replace(state, notification=None),
        ExternalLaunchRequest(kind="open_file", path=action.path),
    )


def _handle_open_path_in_editor(
    state: AppState,
    action: OpenPathInEditor,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return run_external_launch_request(
        replace(state, notification=None),
        ExternalLaunchRequest(
            kind="open_editor",
            path=action.path,
            line_number=action.line_number,
        ),
    )


def _handle_open_terminal_at_path(
    state: AppState,
    action: OpenTerminalAtPath,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return run_external_launch_request(
        replace(state, notification=None),
        ExternalLaunchRequest(kind="open_terminal", path=action.path),
    )


def _handle_copy_paths_to_clipboard(
    state: AppState,
    action: CopyPathsToClipboard,
    reduce_state: ReducerFn,
) -> ReduceResult:
    target_paths = select_target_paths(state)
    if not target_paths:
        return finalize(
            replace(
                state,
                notification=NotificationState(level="warning", message="Nothing to copy"),
            )
        )
    return run_external_launch_request(
        replace(state, notification=None),
        ExternalLaunchRequest(kind="copy_paths", paths=target_paths),
    )


def _handle_toggle_split_terminal(
    state: AppState,
    action: ToggleSplitTerminal,
    reduce_state: ReducerFn,
) -> ReduceResult:
    if state.split_terminal.visible:
        next_state = replace(
            state,
            split_terminal=SplitTerminalState(),
            notification=None,
        )
        session_id = state.split_terminal.session_id
        if session_id is None:
            return finalize(next_state)
        return finalize(next_state, CloseSplitTerminalEffect(session_id=session_id))

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
    return finalize(
        next_state,
        StartSplitTerminalEffect(session_id=session_id, cwd=state.current_path),
    )


def _handle_focus_split_terminal(
    state: AppState,
    action: FocusSplitTerminal,
    reduce_state: ReducerFn,
) -> ReduceResult:
    if not state.split_terminal.visible or state.split_terminal.status != "running":
        return finalize(state)
    return finalize(
        replace(
            state,
            notification=None,
            split_terminal=replace(state.split_terminal, focus_target=action.target),
        )
    )


def _handle_send_split_terminal_input(
    state: AppState,
    action: SendSplitTerminalInput,
    reduce_state: ReducerFn,
) -> ReduceResult:
    session_id = state.split_terminal.session_id
    if (
        not state.split_terminal.visible
        or state.split_terminal.status != "running"
        or session_id is None
    ):
        return finalize(state)
    return finalize(
        state,
        WriteSplitTerminalInputEffect(session_id=session_id, data=action.data),
    )


def _handle_paste_from_clipboard_to_terminal(
    state: AppState,
    action: PasteFromClipboardToTerminal,
    reduce_state: ReducerFn,
) -> ReduceResult:
    session_id = state.split_terminal.session_id
    if (
        not state.split_terminal.visible
        or state.split_terminal.status != "running"
        or session_id is None
    ):
        return finalize(state)
    return finalize(
        state,
        PasteFromClipboardEffect(session_id=session_id),
    )


def _handle_external_launch_completed(
    state: AppState,
    action: ExternalLaunchCompleted,
    reduce_state: ReducerFn,
) -> ReduceResult:
    notification = notification_for_external_launch(action.request)
    if notification is None:
        return finalize(state)
    return finalize(replace(state, notification=notification))


def _handle_external_launch_failed(
    state: AppState,
    action: ExternalLaunchFailed,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return finalize(
        replace(
            state,
            notification=NotificationState(level="error", message=action.message),
        )
    )


def _handle_shell_command_completed(
    state: AppState,
    action: ShellCommandCompleted,
    reduce_state: ReducerFn,
) -> ReduceResult:
    if state.pending_shell_command_request_id != action.request_id:
        return finalize(state)
    level, message = _notification_for_shell_command(action.result)
    return finalize(
        replace(
            state,
            ui_mode="BROWSING",
            notification=NotificationState(level=level, message=message),
            pending_shell_command_request_id=None,
        )
    )


def _handle_shell_command_failed(
    state: AppState,
    action: ShellCommandFailed,
    reduce_state: ReducerFn,
) -> ReduceResult:
    if state.pending_shell_command_request_id != action.request_id:
        return finalize(state)
    return finalize(
        replace(
            state,
            ui_mode="BROWSING",
            notification=NotificationState(level="error", message=action.message),
            pending_shell_command_request_id=None,
        )
    )


def _handle_split_terminal_started(
    state: AppState,
    action: SplitTerminalStarted,
    reduce_state: ReducerFn,
) -> ReduceResult:
    if state.split_terminal.session_id != action.session_id:
        return finalize(state)
    return finalize(
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


def _handle_split_terminal_start_failed(
    state: AppState,
    action: SplitTerminalStartFailed,
    reduce_state: ReducerFn,
) -> ReduceResult:
    if state.split_terminal.session_id != action.session_id:
        return finalize(state)
    return finalize(
        replace(
            state,
            split_terminal=SplitTerminalState(),
            notification=NotificationState(level="error", message=action.message),
        )
    )


def _handle_split_terminal_output_received(
    state: AppState,
    action: SplitTerminalOutputReceived,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return finalize(state)


def _handle_split_terminal_exited(
    state: AppState,
    action: SplitTerminalExited,
    reduce_state: ReducerFn,
) -> ReduceResult:
    if state.split_terminal.session_id != action.session_id:
        return finalize(state)
    return finalize(
        replace(
            state,
            split_terminal=SplitTerminalState(),
            notification=NotificationState(
                level="info",
                message=split_terminal_exit_message(action.exit_code),
            ),
        )
    )


def _handle_config_save_completed(
    state: AppState,
    action: ConfigSaveCompleted,
    reduce_state: ReducerFn,
) -> ReduceResult:
    if state.pending_config_save_request_id != action.request_id:
        return finalize(state)
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
    return sync_child_pane(next_state, next_state.current_pane.cursor_path, reduce_state)


def _handle_config_save_failed(
    state: AppState,
    action: ConfigSaveFailed,
    reduce_state: ReducerFn,
) -> ReduceResult:
    if state.pending_config_save_request_id != action.request_id:
        return finalize(state)
    return finalize(
        replace(
            state,
            pending_config_save_request_id=None,
            notification=NotificationState(
                level="error",
                message=f"Failed to save config: {action.message}",
            ),
        )
    )


def _handle_set_terminal_height(
    state: AppState,
    action: SetTerminalHeight,
    reduce_state: ReducerFn,
) -> ReduceResult:
    if action.height == state.terminal_height:
        return finalize(state)
    return finalize(replace(state, terminal_height=action.height))


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_TerminalConfigHandler = Callable[[AppState, Action, ReducerFn], ReduceResult]

_TERMINAL_CONFIG_HANDLERS: dict[type[Action], _TerminalConfigHandler] = {
    BeginShellCommandInput: _handle_begin_shell_command_input,
    DismissConfigEditor: _handle_dismiss_config_editor,
    CancelShellCommandInput: _handle_cancel_shell_command_input,
    SetShellCommandValue: _handle_set_shell_command_value,
    MoveConfigEditorCursor: _handle_move_config_editor_cursor,
    CycleConfigEditorValue: _handle_cycle_config_editor_value,
    SaveConfigEditor: _handle_save_config_editor,
    SubmitShellCommand: _handle_submit_shell_command,
    AddBookmark: _handle_add_bookmark,
    RemoveBookmark: _handle_remove_bookmark,
    ResetHelpBarConfig: _handle_reset_help_bar_config,
    OpenPathWithDefaultApp: _handle_open_path_with_default_app,
    OpenPathInEditor: _handle_open_path_in_editor,
    OpenTerminalAtPath: _handle_open_terminal_at_path,
    CopyPathsToClipboard: _handle_copy_paths_to_clipboard,
    ToggleSplitTerminal: _handle_toggle_split_terminal,
    FocusSplitTerminal: _handle_focus_split_terminal,
    SendSplitTerminalInput: _handle_send_split_terminal_input,
    PasteFromClipboardToTerminal: _handle_paste_from_clipboard_to_terminal,
    ExternalLaunchCompleted: _handle_external_launch_completed,
    ExternalLaunchFailed: _handle_external_launch_failed,
    ShellCommandCompleted: _handle_shell_command_completed,
    ShellCommandFailed: _handle_shell_command_failed,
    SplitTerminalStarted: _handle_split_terminal_started,
    SplitTerminalStartFailed: _handle_split_terminal_start_failed,
    SplitTerminalOutputReceived: _handle_split_terminal_output_received,
    SplitTerminalExited: _handle_split_terminal_exited,
    ConfigSaveCompleted: _handle_config_save_completed,
    ConfigSaveFailed: _handle_config_save_failed,
    SetTerminalHeight: _handle_set_terminal_height,
}
