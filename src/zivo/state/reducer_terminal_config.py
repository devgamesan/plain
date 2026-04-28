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
    MoveConfigEditorCursor,
    OpenPathInEditor,
    OpenPathWithDefaultApp,
    OpenTerminalAtPath,
    RemoveBookmark,
    ResetHelpBarConfig,
    SaveConfigEditor,
    SetShellCommandValue,
    SetTerminalHeight,
    ShellCommandCompleted,
    ShellCommandFailed,
    SubmitShellCommand,
)
from .effects import (
    ReduceResult,
    RunConfigSaveEffect,
    RunShellCommandEffect,
)
from .models import AppState, NotificationState, ShellCommandState
from .reducer_common import (
    ReducerFn,
    apply_config_to_runtime_state,
    cycle_config_editor_value,
    finalize,
    move_config_cursor_visual,
    notification_for_external_launch,
    run_external_launch_request,
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
    # shell_commandを保持したままにして、完了時に結果を設定できるようにする
    return finalize(
        replace(
            state,
            ui_mode="BUSY",
            notification=NotificationState(level="info", message="Running shell command..."),
            # shell_command=None,  # 削除：shell_commandを保持
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
        ExternalLaunchRequest(
            kind="open_terminal",
            path=action.path,
            terminal_launch_mode=action.launch_mode,
        ),
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
    # UIモードをSHELLのままにし、実行結果をShellCommandStateに保持する
    # shell_commandがNoneの場合（キャンセルされた場合など）はBROWSINGに戻る
    if state.shell_command is None:
        return finalize(
            replace(
                state,
                ui_mode="BROWSING",
                pending_shell_command_request_id=None,
            )
        )
    return finalize(
        replace(
            state,
            ui_mode="SHELL",
            shell_command=replace(state.shell_command, result=action.result),
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
    ExternalLaunchCompleted: _handle_external_launch_completed,
    ExternalLaunchFailed: _handle_external_launch_failed,
    ShellCommandCompleted: _handle_shell_command_completed,
    ShellCommandFailed: _handle_shell_command_failed,
    ConfigSaveCompleted: _handle_config_save_completed,
    ConfigSaveFailed: _handle_config_save_failed,
    SetTerminalHeight: _handle_set_terminal_height,
}
