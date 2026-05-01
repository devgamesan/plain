"""Runtime scheduling helpers for execution-oriented effects."""

import subprocess
import sys
import threading
from concurrent.futures import CancelledError as FutureCancelledError
from contextlib import nullcontext
from functools import partial
from pathlib import Path
from typing import Any

from textual.app import SuspendNotSupported

from zivo.app_runtime_core import WorkerSpec, run_worker
from zivo.models import CustomActionResult
from zivo.state import (
    ExitCurrentPathEffect,
    RunArchiveExtractEffect,
    RunArchivePreparationEffect,
    RunAttributeInspectionEffect,
    RunClipboardPasteEffect,
    RunConfigSaveEffect,
    RunCustomActionEffect,
    RunExternalLaunchEffect,
    RunFileMutationEffect,
    RunShellCommandEffect,
    RunUndoEffect,
    RunZipCompressEffect,
    RunZipCompressPreparationEffect,
)
from zivo.state.actions import (
    ArchiveExtractProgress,
    CustomActionCompleted,
    CustomActionFailed,
    ExternalLaunchCompleted,
    ExternalLaunchFailed,
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


def schedule_custom_action(app: Any, effect: RunCustomActionEffect) -> None:
    if effect.request.mode == "terminal":
        run_terminal_custom_action(app, effect)
        return
    if effect.request.mode == "terminal_window":
        run_terminal_window_custom_action(app, effect)
        return
    run_worker(
        app,
        effect,
        partial(app._custom_action_service.execute, effect.request),
        WorkerSpec(
            name=f"custom-action:{effect.request_id}",
            group="custom-action",
            description=effect.request.name,
            exclusive=True,
        ),
    )


def run_terminal_custom_action(app: Any, effect: RunCustomActionEffect) -> None:
    suspend_context = nullcontext()
    try:
        suspend_context = app.suspend()
    except SuspendNotSupported:
        app.call_next(
            app.dispatch_actions,
            (
                CustomActionFailed(
                    request_id=effect.request_id,
                    request=effect.request,
                    message="Terminal custom actions require suspend support",
                ),
            ),
        )
        return

    try:
        with suspend_context:
            subprocess.run(
                list(effect.request.command),
                cwd=effect.request.cwd,
                check=True,
                stdin=sys.stdin,
                stdout=sys.stdout,
                stderr=sys.stderr,
            )
    except (OSError, subprocess.CalledProcessError) as error:
        app.refresh(repaint=True, layout=True)
        app.call_next(
            app.dispatch_actions,
            (
                CustomActionFailed(
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
            CustomActionCompleted(
                request_id=effect.request_id,
                request=effect.request,
                result=CustomActionResult(effect.request.name),
            ),
        ),
    )


def run_terminal_window_custom_action(app: Any, effect: RunCustomActionEffect) -> None:
    try:
        app._external_launch_service.run_in_terminal_window(
            effect.request.cwd, effect.request.command
        )
    except OSError as error:
        app.call_next(
            app.dispatch_actions,
            (
                CustomActionFailed(
                    request_id=effect.request_id,
                    request=effect.request,
                    message=str(error) or "Failed to open terminal window",
                ),
            ),
        )
        return

    app.call_next(
        app.dispatch_actions,
        (
            CustomActionCompleted(
                request_id=effect.request_id,
                request=effect.request,
                result=CustomActionResult(effect.request.name),
            ),
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


def run_foreground_external_launch(app: Any, effect: RunExternalLaunchEffect) -> None:
    suspend_context = nullcontext()
    try:
        suspend_context = app.suspend()
    except SuspendNotSupported:
        _run_detached_external_launch(app, effect)
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


def _run_detached_external_launch(app: Any, effect: RunExternalLaunchEffect) -> None:
    import subprocess

    request = effect.request
    try:
        adapter = getattr(app._external_launch_service, "adapter", None)
        if adapter is None or not hasattr(adapter, "_editor_candidates"):
            raise OSError("Editor launch not supported on this terminal")
        path = request.path
        line_number = request.line_number
        commands = adapter._editor_candidates(path, line_number)
        if not commands:
            raise OSError("No supported terminal editor found")
        cmd = list(commands[0])
        cwd = str(Path(path).parent)
        try:
            subprocess.run(
                cmd,
                cwd=cwd,
                check=True,
                stdin=sys.stdin,
                stdout=sys.stdout,
                stderr=sys.stderr,
            )
            app.call_next(
                app.dispatch_actions,
                (
                    ExternalLaunchCompleted(
                        request_id=effect.request_id,
                        request=effect.request,
                    ),
                ),
            )
            return
        except subprocess.CalledProcessError as error:
            raise OSError(str(error) or f"{cmd[0]} failed") from error
    except OSError as error:
        app.call_next(
            app.dispatch_actions,
            (
                ExternalLaunchFailed(
                    request_id=effect.request_id,
                    request=effect.request,
                    message=str(error) or "Editor launch failed",
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


def schedule_exit_current_path(app: Any, effect: ExitCurrentPathEffect) -> None:
    app.exit(result=app._app_state.current_path, return_code=effect.return_code)
