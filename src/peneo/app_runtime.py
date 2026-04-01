"""Runtime helpers for effect scheduling and worker result handling."""

import threading
from collections.abc import Sequence
from concurrent.futures import CancelledError as FutureCancelledError
from contextlib import nullcontext
from functools import partial
from typing import Any

from textual.app import SuspendNotSupported
from textual.timer import Timer
from textual.worker import Worker, WorkerState

from peneo.models import FileMutationResult, PasteConflictPrompt, PasteExecutionResult
from peneo.services import InvalidFileSearchQueryError, InvalidGrepSearchQueryError
from peneo.state import (
    BrowserSnapshotFailed,
    BrowserSnapshotLoaded,
    ChildPaneSnapshotFailed,
    ChildPaneSnapshotLoaded,
    ClipboardPasteCompleted,
    ClipboardPasteFailed,
    ClipboardPasteNeedsResolution,
    CloseSplitTerminalEffect,
    ConfigSaveCompleted,
    ConfigSaveFailed,
    DirectorySizesFailed,
    DirectorySizesLoaded,
    Effect,
    ExternalLaunchCompleted,
    ExternalLaunchFailed,
    FileMutationCompleted,
    FileMutationFailed,
    FileSearchCompleted,
    FileSearchFailed,
    GrepSearchCompleted,
    GrepSearchFailed,
    LoadBrowserSnapshotEffect,
    LoadChildPaneSnapshotEffect,
    NotificationState,
    PasteFromClipboardEffect,
    RunClipboardPasteEffect,
    RunConfigSaveEffect,
    RunDirectorySizeEffect,
    RunExternalLaunchEffect,
    RunFileMutationEffect,
    RunFileSearchEffect,
    RunGrepSearchEffect,
    SetNotification,
    SplitTerminalStarted,
    SplitTerminalStartFailed,
    StartSplitTerminalEffect,
    WriteSplitTerminalInputEffect,
)

FILE_SEARCH_DEBOUNCE_SECONDS = 0.2
GREP_SEARCH_DEBOUNCE_SECONDS = 0.2


def sync_runtime_state(app: Any, previous_state: Any, next_state: Any) -> None:
    if previous_state.pending_file_search_request_id != next_state.pending_file_search_request_id:
        cancel_pending_file_search(app)
    if previous_state.pending_grep_search_request_id != next_state.pending_grep_search_request_id:
        cancel_pending_grep_search(app)
    if (
        previous_state.pending_directory_size_request_id
        != next_state.pending_directory_size_request_id
    ):
        cancel_pending_directory_size(app)


def cancel_pending_runtime_work(app: Any) -> None:
    cancel_pending_file_search(app)
    cancel_pending_grep_search(app)
    cancel_pending_directory_size(app)


def schedule_effects(app: Any, effects: Sequence[Effect]) -> None:
    for effect in effects:
        if isinstance(effect, LoadBrowserSnapshotEffect):
            schedule_browser_snapshot(app, effect)
        elif isinstance(effect, LoadChildPaneSnapshotEffect):
            schedule_child_pane_snapshot(app, effect)
        elif isinstance(effect, RunClipboardPasteEffect):
            schedule_clipboard_paste(app, effect)
        elif isinstance(effect, RunConfigSaveEffect):
            schedule_config_save(app, effect)
        elif isinstance(effect, RunDirectorySizeEffect):
            schedule_directory_sizes(app, effect)
        elif isinstance(effect, RunFileMutationEffect):
            schedule_file_mutation(app, effect)
        elif isinstance(effect, RunExternalLaunchEffect):
            if effect.request.kind == "copy_paths":
                run_copy_paths(app, effect)
            elif effect.request.kind == "open_editor":
                app.call_next(run_foreground_external_launch, app, effect)
            else:
                schedule_external_launch(app, effect)
        elif isinstance(effect, RunFileSearchEffect):
            schedule_file_search(app, effect)
        elif isinstance(effect, RunGrepSearchEffect):
            schedule_grep_search(app, effect)
        elif isinstance(effect, StartSplitTerminalEffect):
            start_split_terminal(app, effect)
        elif isinstance(effect, WriteSplitTerminalInputEffect):
            write_split_terminal_input(app, effect)
        elif isinstance(effect, PasteFromClipboardEffect):
            paste_from_clipboard(app, effect)
        elif isinstance(effect, CloseSplitTerminalEffect):
            close_split_terminal(app)


def schedule_browser_snapshot(app: Any, effect: LoadBrowserSnapshotEffect) -> None:
    worker = app.run_worker(
        partial(
            app._snapshot_loader.load_browser_snapshot,
            effect.path,
            effect.cursor_path,
        ),
        name=f"browser-snapshot:{effect.request_id}",
        group="browser-snapshot",
        description=effect.path,
        exit_on_error=False,
        exclusive=True,
        thread=True,
    )
    app._pending_workers[worker.name] = effect


def schedule_child_pane_snapshot(app: Any, effect: LoadChildPaneSnapshotEffect) -> None:
    worker = app.run_worker(
        partial(
            app._snapshot_loader.load_child_pane_snapshot,
            effect.current_path,
            effect.cursor_path,
        ),
        name=f"child-pane-snapshot:{effect.request_id}",
        group="child-pane-snapshot",
        description=effect.cursor_path,
        exit_on_error=False,
        exclusive=True,
        thread=True,
    )
    app._pending_workers[worker.name] = effect


def schedule_clipboard_paste(app: Any, effect: RunClipboardPasteEffect) -> None:
    worker = app.run_worker(
        partial(app._clipboard_service.execute_paste, effect.request),
        name=f"clipboard-paste:{effect.request_id}",
        group="clipboard-paste",
        description=effect.request.destination_dir,
        exit_on_error=False,
        exclusive=True,
        thread=True,
    )
    app._pending_workers[worker.name] = effect


def schedule_config_save(app: Any, effect: RunConfigSaveEffect) -> None:
    worker = app.run_worker(
        partial(
            app._config_save_service.save,
            path=effect.path,
            config=effect.config,
        ),
        name=f"config-save:{effect.request_id}",
        group="config-save",
        description=effect.path,
        exit_on_error=False,
        exclusive=True,
        thread=True,
    )
    app._pending_workers[worker.name] = effect


def schedule_directory_sizes(app: Any, effect: RunDirectorySizeEffect) -> None:
    cancel_event = threading.Event()
    app._active_directory_size_cancel_event = cancel_event
    app._active_directory_size_request_id = effect.request_id
    worker = app.run_worker(
        partial(
            app._directory_size_service.calculate_sizes,
            effect.paths,
            is_cancelled=cancel_event.is_set,
        ),
        name=f"directory-size:{effect.request_id}",
        group="directory-size",
        description=",".join(effect.paths),
        exit_on_error=False,
        exclusive=True,
        thread=True,
    )
    app._pending_workers[worker.name] = effect


def schedule_file_mutation(app: Any, effect: RunFileMutationEffect) -> None:
    worker = app.run_worker(
        partial(app._file_mutation_service.execute, effect.request),
        name=f"file-mutation:{effect.request_id}",
        group="file-mutation",
        description=str(effect.request),
        exit_on_error=False,
        exclusive=True,
        thread=True,
    )
    app._pending_workers[worker.name] = effect


def schedule_external_launch(app: Any, effect: RunExternalLaunchEffect) -> None:
    worker = app.run_worker(
        partial(app._external_launch_service.execute, effect.request),
        name=f"external-launch:{effect.request_id}",
        group="external-launch",
        description=str(effect.request),
        exit_on_error=False,
        thread=True,
    )
    app._pending_workers[worker.name] = effect


def schedule_file_search(app: Any, effect: RunFileSearchEffect) -> None:
    cancel_file_search_timer(app)
    app._file_search_timer = app.set_timer(
        FILE_SEARCH_DEBOUNCE_SECONDS,
        partial(start_file_search_worker, app, effect),
        name=f"file-search-debounce:{effect.request_id}",
    )


def start_file_search_worker(app: Any, effect: RunFileSearchEffect) -> None:
    app._file_search_timer = None
    if app._app_state.pending_file_search_request_id != effect.request_id:
        return
    cancel_event = threading.Event()
    app._active_file_search_cancel_event = cancel_event
    app._active_file_search_request_id = effect.request_id
    worker = app.run_worker(
        partial(
            app._file_search_service.search,
            effect.root_path,
            effect.query,
            show_hidden=effect.show_hidden,
            is_cancelled=cancel_event.is_set,
        ),
        name=f"file-search:{effect.request_id}",
        group="file-search",
        description=effect.query,
        exit_on_error=False,
        exclusive=True,
        thread=True,
    )
    app._pending_workers[worker.name] = effect


def schedule_grep_search(app: Any, effect: RunGrepSearchEffect) -> None:
    cancel_grep_search_timer(app)
    app._grep_search_timer = app.set_timer(
        GREP_SEARCH_DEBOUNCE_SECONDS,
        partial(start_grep_search_worker, app, effect),
        name=f"grep-search-debounce:{effect.request_id}",
    )


def start_grep_search_worker(app: Any, effect: RunGrepSearchEffect) -> None:
    app._grep_search_timer = None
    if app._app_state.pending_grep_search_request_id != effect.request_id:
        return
    cancel_event = threading.Event()
    app._active_grep_search_cancel_event = cancel_event
    app._active_grep_search_request_id = effect.request_id
    worker = app.run_worker(
        partial(
            app._grep_search_service.search,
            effect.root_path,
            effect.query,
            show_hidden=effect.show_hidden,
            is_cancelled=cancel_event.is_set,
        ),
        name=f"grep-search:{effect.request_id}",
        group="grep-search",
        description=effect.query,
        exit_on_error=False,
        exclusive=True,
        thread=True,
    )
    app._pending_workers[worker.name] = effect


def cancel_pending_file_search(app: Any) -> None:
    cancel_file_search_timer(app)
    cancel_active_file_search(app)


def cancel_file_search_timer(app: Any) -> None:
    if app._file_search_timer is None:
        return
    timer: Timer = app._file_search_timer
    timer.stop()
    app._file_search_timer = None


def cancel_active_file_search(app: Any) -> None:
    if app._active_file_search_cancel_event is None:
        return
    app._active_file_search_cancel_event.set()
    app._active_file_search_cancel_event = None
    app._active_file_search_request_id = None


def cancel_pending_grep_search(app: Any) -> None:
    cancel_grep_search_timer(app)
    cancel_active_grep_search(app)


def cancel_grep_search_timer(app: Any) -> None:
    if app._grep_search_timer is None:
        return
    timer: Timer = app._grep_search_timer
    timer.stop()
    app._grep_search_timer = None


def cancel_active_grep_search(app: Any) -> None:
    if app._active_grep_search_cancel_event is None:
        return
    app._active_grep_search_cancel_event.set()
    app._active_grep_search_cancel_event = None
    app._active_grep_search_request_id = None


def cancel_pending_directory_size(app: Any) -> None:
    if app._active_directory_size_cancel_event is None:
        return
    app._active_directory_size_cancel_event.set()
    app._active_directory_size_cancel_event = None
    app._active_directory_size_request_id = None


def start_split_terminal(app: Any, effect: StartSplitTerminalEffect) -> None:
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


def paste_from_clipboard(app: Any, effect: PasteFromClipboardEffect) -> None:
    if app._app_state.split_terminal.session_id != effect.session_id:
        return
    if app._split_terminal_session is None:
        return
    try:
        clipboard_text = app._external_launch_service.get_from_clipboard()
        app._split_terminal_session.write(clipboard_text)
    except OSError as error:
        message = str(error) or "Failed to read clipboard"
        app.call_next(
            app.dispatch_actions,
            (SetNotification(NotificationState(level="warning", message=message)),),
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


def complete_worker_actions(effect: Effect, result: object) -> tuple[Any, ...]:
    if isinstance(effect, LoadBrowserSnapshotEffect):
        return (
            BrowserSnapshotLoaded(
                request_id=effect.request_id,
                snapshot=result,
                blocking=effect.blocking,
            ),
        )

    if isinstance(effect, LoadChildPaneSnapshotEffect):
        return (
            ChildPaneSnapshotLoaded(
                request_id=effect.request_id,
                pane=result,
            ),
        )

    if isinstance(result, PasteConflictPrompt):
        return (
            ClipboardPasteNeedsResolution(
                request_id=effect.request_id,
                request=result.request,
                conflicts=result.conflicts,
            ),
        )

    if isinstance(result, PasteExecutionResult):
        return (
            ClipboardPasteCompleted(
                request_id=effect.request_id,
                summary=result.summary,
            ),
        )

    if isinstance(result, FileMutationResult):
        return (
            FileMutationCompleted(
                request_id=effect.request_id,
                result=result,
            ),
        )

    if isinstance(effect, RunConfigSaveEffect):
        return (
            ConfigSaveCompleted(
                request_id=effect.request_id,
                path=result,
                config=effect.config,
            ),
        )

    if isinstance(effect, RunDirectorySizeEffect):
        return (
            DirectorySizesLoaded(
                request_id=effect.request_id,
                sizes=result[0],
                failures=result[1],
            ),
        )

    if isinstance(effect, RunExternalLaunchEffect):
        return (
            ExternalLaunchCompleted(
                request_id=effect.request_id,
                request=effect.request,
            ),
        )

    if isinstance(effect, RunFileSearchEffect):
        return (
            FileSearchCompleted(
                request_id=effect.request_id,
                query=effect.query,
                results=result,
            ),
        )

    if isinstance(effect, RunGrepSearchEffect):
        return (
            GrepSearchCompleted(
                request_id=effect.request_id,
                query=effect.query,
                results=result,
            ),
        )

    return ()


def failed_worker_actions(effect: Effect, error: BaseException | None) -> tuple[Any, ...]:
    message = str(error) or "Operation failed"

    if isinstance(effect, LoadBrowserSnapshotEffect):
        return (
            BrowserSnapshotFailed(
                request_id=effect.request_id,
                message=message,
                blocking=effect.blocking,
            ),
        )

    if isinstance(effect, LoadChildPaneSnapshotEffect):
        return (
            ChildPaneSnapshotFailed(
                request_id=effect.request_id,
                message=message,
            ),
        )

    if isinstance(effect, RunFileMutationEffect):
        return (
            FileMutationFailed(
                request_id=effect.request_id,
                message=message,
            ),
        )

    if isinstance(effect, RunConfigSaveEffect):
        return (
            ConfigSaveFailed(
                request_id=effect.request_id,
                message=message,
            ),
        )

    if isinstance(effect, RunDirectorySizeEffect):
        return (
            DirectorySizesFailed(
                request_id=effect.request_id,
                paths=effect.paths,
                message=message,
            ),
        )

    if isinstance(effect, RunExternalLaunchEffect):
        return (
            ExternalLaunchFailed(
                request_id=effect.request_id,
                request=effect.request,
                message=message,
            ),
        )

    if isinstance(effect, RunFileSearchEffect):
        return (
            FileSearchFailed(
                request_id=effect.request_id,
                query=effect.query,
                message=message,
                invalid_query=isinstance(error, InvalidFileSearchQueryError),
            ),
        )

    if isinstance(effect, RunGrepSearchEffect):
        return (
            GrepSearchFailed(
                request_id=effect.request_id,
                query=effect.query,
                message=message,
                invalid_query=isinstance(error, InvalidGrepSearchQueryError),
            ),
        )

    return (
        ClipboardPasteFailed(
            request_id=effect.request_id,
            message=message,
        ),
    )


def clear_effect_tracking(app: Any, effect: Effect) -> None:
    if (
        isinstance(effect, RunFileSearchEffect)
        and effect.request_id == app._active_file_search_request_id
    ):
        app._active_file_search_cancel_event = None
        app._active_file_search_request_id = None
    if (
        isinstance(effect, RunGrepSearchEffect)
        and effect.request_id == app._active_grep_search_request_id
    ):
        app._active_grep_search_cancel_event = None
        app._active_grep_search_request_id = None
    if (
        isinstance(effect, RunDirectorySizeEffect)
        and effect.request_id == app._active_directory_size_request_id
    ):
        app._active_directory_size_cancel_event = None
        app._active_directory_size_request_id = None


async def handle_worker_state_changed(app: Any, event: Worker.StateChanged) -> None:
    effect = app._pending_workers.get(event.worker.name)
    if effect is None:
        return

    if event.state in {WorkerState.PENDING, WorkerState.RUNNING}:
        return

    app._pending_workers.pop(event.worker.name, None)
    clear_effect_tracking(app, effect)

    if event.state == WorkerState.CANCELLED:
        return

    if event.state == WorkerState.SUCCESS:
        actions = complete_worker_actions(effect, event.worker.result)
        if actions:
            await app.dispatch_actions(actions)
        return

    await app.dispatch_actions(failed_worker_actions(effect, event.worker.error))
