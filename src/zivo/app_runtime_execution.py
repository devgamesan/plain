"""Runtime scheduling helpers for execution-oriented effects."""

import threading
from concurrent.futures import CancelledError as FutureCancelledError
from contextlib import nullcontext
from functools import partial
from typing import Any

from textual.app import SuspendNotSupported

from zivo.app_runtime_core import WorkerSpec, run_worker
from zivo.state import (
    CloseSplitTerminalEffect,
    RunArchiveExtractEffect,
    RunArchivePreparationEffect,
    RunAttributeInspectionEffect,
    RunClipboardPasteEffect,
    RunConfigSaveEffect,
    RunExternalLaunchEffect,
    RunFileMutationEffect,
    RunShellCommandEffect,
    RunUndoEffect,
    RunZipCompressEffect,
    RunZipCompressPreparationEffect,
    StartSplitTerminalEffect,
    WriteSplitTerminalInputEffect,
)
from zivo.state.actions import (
    ArchiveExtractProgress,
    ExternalLaunchCompleted,
    ExternalLaunchFailed,
    SplitTerminalStarted,
    SplitTerminalStartFailed,
    ZipCompressProgress,
)


def schedule_clipboard_paste(app: Any, effect: RunClipboardPasteEffect) -> None:
    run_worker(
        app,
        effect,
        partial(app._clipboard_service.execute_paste, effect.request),
        WorkerSpec(
            name=f"clipboard-paste:{effect.request_id}",
            group="clipboard-paste",
            description=effect.request.destination_dir,
            exclusive=True,
        ),
    )


def schedule_config_save(app: Any, effect: RunConfigSaveEffect) -> None:
    run_worker(
        app,
        effect,
        partial(
            app._config_save_service.save,
            path=effect.path,
            config=effect.config,
        ),
        WorkerSpec(
            name=f"config-save:{effect.request_id}",
            group="config-save",
            description=effect.path,
            exclusive=True,
        ),
    )


def schedule_shell_command(app: Any, effect: RunShellCommandEffect) -> None:
    run_worker(
        app,
        effect,
        partial(
            app._shell_command_service.execute,
            cwd=effect.cwd,
            command=effect.command,
        ),
        WorkerSpec(
            name=f"shell-command:{effect.request_id}",
            group="shell-command",
            description=effect.cwd,
            exclusive=True,
        ),
    )


def schedule_attribute_inspection(app: Any, effect: RunAttributeInspectionEffect) -> None:
    run_worker(
        app,
        effect,
        partial(app._attribute_inspection_service.inspect, effect.path),
        WorkerSpec(
            name=f"attribute-inspection:{effect.request_id}",
            group="attribute-inspection",
            description=effect.path,
            exclusive=True,
        ),
    )


def schedule_file_mutation(app: Any, effect: RunFileMutationEffect) -> None:
    run_worker(
        app,
        effect,
        partial(app._file_mutation_service.execute, effect.request),
        WorkerSpec(
            name=f"file-mutation:{effect.request_id}",
            group="file-mutation",
            description=str(effect.request),
            exclusive=True,
        ),
    )


def schedule_undo(app: Any, effect: RunUndoEffect) -> None:
    run_worker(
        app,
        effect,
        partial(app._undo_service.execute, effect.entry),
        WorkerSpec(
            name=f"undo:{effect.request_id}",
            group="undo",
            description=effect.entry.kind,
            exclusive=True,
        ),
    )


def schedule_archive_preparation(app: Any, effect: RunArchivePreparationEffect) -> None:
    run_worker(
        app,
        effect,
        partial(app._archive_extract_service.prepare, effect.request),
        WorkerSpec(
            name=f"archive-prepare:{effect.request_id}",
            group="archive-prepare",
            description=effect.request.source_path,
            exclusive=True,
        ),
    )


def schedule_archive_extract(app: Any, effect: RunArchiveExtractEffect) -> None:
    run_worker(
        app,
        effect,
        partial(
            app._archive_extract_service.execute,
            effect.request,
            progress_callback=partial(report_archive_extract_progress, app, effect.request_id),
        ),
        WorkerSpec(
            name=f"archive-extract:{effect.request_id}",
            group="archive-extract",
            description=effect.request.source_path,
            exclusive=True,
        ),
    )


def schedule_zip_compress_preparation(app: Any, effect: RunZipCompressPreparationEffect) -> None:
    run_worker(
        app,
        effect,
        partial(app._zip_compress_service.prepare, effect.request),
        WorkerSpec(
            name=f"zip-compress-prepare:{effect.request_id}",
            group="zip-compress-prepare",
            description=effect.request.destination_path,
            exclusive=True,
        ),
    )


def schedule_zip_compress(app: Any, effect: RunZipCompressEffect) -> None:
    run_worker(
        app,
        effect,
        partial(
            app._zip_compress_service.execute,
            effect.request,
            progress_callback=partial(report_zip_compress_progress, app, effect.request_id),
        ),
        WorkerSpec(
            name=f"zip-compress:{effect.request_id}",
            group="zip-compress",
            description=effect.request.destination_path,
            exclusive=True,
        ),
    )


def schedule_external_launch(app: Any, effect: RunExternalLaunchEffect) -> None:
    run_worker(
        app,
        effect,
        partial(app._external_launch_service.execute, effect.request),
        WorkerSpec(
            name=f"external-launch:{effect.request_id}",
            group="external-launch",
            description=str(effect.request),
        ),
    )


def start_split_terminal(app: Any, effect: StartSplitTerminalEffect) -> None:
    if app._split_terminal_service is None:
        app.call_next(
            app.dispatch_actions,
            (
                SplitTerminalStartFailed(
                    session_id=effect.session_id,
                    message="Split terminal is not supported on this platform",
                ),
            ),
        )
        return
    try:
        session = app._split_terminal_service.start(
            effect.cwd,
            on_output=partial(handle_split_terminal_output, app, effect.session_id),
            on_exit=partial(handle_split_terminal_exit, app, effect.session_id),
        )
    except OSError as error:
        app.call_next(
            app.dispatch_actions,
            (
                SplitTerminalStartFailed(
                    session_id=effect.session_id,
                    message=str(error) or "Failed to open split terminal",
                ),
            ),
        )
        return

    app._split_terminal_session = session
    app.call_next(
        app.dispatch_actions,
        (
            SplitTerminalStarted(session_id=effect.session_id, cwd=effect.cwd),
        ),
    )


def write_split_terminal_input(app: Any, effect: WriteSplitTerminalInputEffect) -> None:
    if app._app_state.split_terminal.session_id != effect.session_id:
        return
    if app._split_terminal_session is None:
        return
    try:
        app._split_terminal_session.write(effect.data)
    except OSError as error:
        app.call_next(
            app.dispatch_actions,
            (
                SplitTerminalStartFailed(
                    session_id=effect.session_id,
                    message=str(error) or "Failed to write to split terminal",
                ),
            ),
        )


def close_split_terminal(app: Any) -> None:
    if app._split_terminal_session is None:
        return
    try:
        app._split_terminal_session.close()
    finally:
        app._split_terminal_session = None


def run_foreground_external_launch(app: Any, effect: RunExternalLaunchEffect) -> None:
    suspend_context = nullcontext()
    try:
        suspend_context = app.suspend()
    except SuspendNotSupported as error:
        app.call_next(
            app.dispatch_actions,
            (
                ExternalLaunchFailed(
                    request_id=effect.request_id,
                    request=effect.request,
                    message=str(error),
                ),
            ),
        )
        return

    try:
        with suspend_context:
            app._external_launch_service.execute(effect.request)
    except OSError as error:
        app.refresh(repaint=True, layout=True)
        app.call_next(
            app.dispatch_actions,
            (
                ExternalLaunchFailed(
                    request_id=effect.request_id,
                    request=effect.request,
                    message=str(error) or "Operation failed",
                ),
            ),
        )
        return

    app.refresh(repaint=True, layout=True)
    app.call_next(
        app.dispatch_actions,
        (
            ExternalLaunchCompleted(
                request_id=effect.request_id,
                request=effect.request,
            ),
        ),
    )


def run_copy_paths(app: Any, effect: RunExternalLaunchEffect) -> None:
    try:
        app._external_launch_service.execute(effect.request)
    except OSError as error:
        app.call_next(
            app.dispatch_actions,
            (
                ExternalLaunchFailed(
                    request_id=effect.request_id,
                    request=effect.request,
                    message=str(error) or "Operation failed",
                ),
            ),
        )
        return

    app.call_next(
        app.dispatch_actions,
        (
            ExternalLaunchCompleted(
                request_id=effect.request_id,
                request=effect.request,
            ),
        ),
    )


def handle_split_terminal_output(app: Any, session_id: int, data: str) -> None:
    message = app.SplitTerminalOutput(session_id=session_id, data=data)
    try:
        if app._thread_id == threading.get_ident():
            app.post_message(message)
            return
        app.call_from_thread(app.post_message, message)
    except (RuntimeError, FutureCancelledError):
        return


def handle_split_terminal_exit(app: Any, session_id: int, exit_code: int | None) -> None:
    message = app.SplitTerminalExitedMessage(session_id=session_id, exit_code=exit_code)
    try:
        if app._thread_id == threading.get_ident():
            app.post_message(message)
            return
        app.call_from_thread(app.post_message, message)
    except (RuntimeError, FutureCancelledError):
        return


def report_archive_extract_progress(
    app: Any,
    request_id: int,
    completed_entries: int,
    total_entries: int,
    current_path: str | None,
) -> None:
    actions = (
        ArchiveExtractProgress(
            request_id=request_id,
            completed_entries=completed_entries,
            total_entries=total_entries,
            current_path=current_path,
        ),
    )
    try:
        if app._thread_id == threading.get_ident():
            app.call_next(app.dispatch_actions, actions)
            return
        app.call_from_thread(app.call_next, app.dispatch_actions, actions)
    except (RuntimeError, FutureCancelledError):
        return


def report_zip_compress_progress(
    app: Any,
    request_id: int,
    completed_entries: int,
    total_entries: int,
    current_path: str | None,
) -> None:
    actions = (
        ZipCompressProgress(
            request_id=request_id,
            completed_entries=completed_entries,
            total_entries=total_entries,
            current_path=current_path,
        ),
    )
    try:
        if app._thread_id == threading.get_ident():
            app.call_next(app.dispatch_actions, actions)
            return
        app.call_from_thread(app.call_next, app.dispatch_actions, actions)
    except (RuntimeError, FutureCancelledError):
        return


def schedule_external_launch_effect(app: Any, effect: RunExternalLaunchEffect) -> None:
    if effect.request.kind == "copy_paths":
        run_copy_paths(app, effect)
        return
    if effect.request.kind == "open_editor":
        app.call_next(run_foreground_external_launch, app, effect)
        return
    if (
        effect.request.kind == "open_terminal"
        and effect.request.terminal_launch_mode == "foreground"
    ):
        app.call_next(run_foreground_external_launch, app, effect)
        return
    schedule_external_launch(app, effect)


def close_split_terminal_effect(app: Any, effect: CloseSplitTerminalEffect) -> None:
    close_split_terminal(app)
