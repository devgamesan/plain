"""Runtime helpers for effect scheduling and worker result handling."""

import threading
from collections.abc import Callable, Sequence
from concurrent.futures import CancelledError as FutureCancelledError
from contextlib import nullcontext
from dataclasses import dataclass
from functools import partial
from typing import Any

from textual.app import SuspendNotSupported
from textual.timer import Timer
from textual.worker import Worker, WorkerState

from zivo.models import (
    CreateZipArchivePreparationResult,
    CreateZipArchiveResult,
    ExtractArchivePreparationResult,
    ExtractArchiveResult,
    FileMutationResult,
    PasteConflictPrompt,
    PasteExecutionResult,
    ShellCommandResult,
    TextReplacePreviewResult,
    TextReplaceResult,
    UndoResult,
)
from zivo.services import (
    InvalidFileSearchQueryError,
    InvalidGrepSearchQueryError,
    InvalidTextReplaceQueryError,
)
from zivo.state import (
    ArchiveExtractCompleted,
    ArchiveExtractFailed,
    ArchiveExtractProgress,
    ArchivePreparationCompleted,
    ArchivePreparationFailed,
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
    RunArchiveExtractEffect,
    RunArchivePreparationEffect,
    RunClipboardPasteEffect,
    RunConfigSaveEffect,
    RunDirectorySizeEffect,
    RunExternalLaunchEffect,
    RunFileMutationEffect,
    RunFileSearchEffect,
    RunGrepSearchEffect,
    RunShellCommandEffect,
    RunTextReplaceApplyEffect,
    RunTextReplacePreviewEffect,
    RunUndoEffect,
    RunZipCompressEffect,
    RunZipCompressPreparationEffect,
    ShellCommandCompleted,
    ShellCommandFailed,
    SplitTerminalStarted,
    SplitTerminalStartFailed,
    StartSplitTerminalEffect,
    TextReplaceApplied,
    TextReplaceApplyFailed,
    TextReplacePreviewCompleted,
    TextReplacePreviewFailed,
    UndoCompleted,
    UndoFailed,
    WriteSplitTerminalInputEffect,
    ZipCompressCompleted,
    ZipCompressFailed,
    ZipCompressPreparationCompleted,
    ZipCompressPreparationFailed,
    ZipCompressProgress,
)

CHILD_PANE_DEBOUNCE_SECONDS = 0.03
FILE_SEARCH_DEBOUNCE_SECONDS = 0.2
GREP_SEARCH_DEBOUNCE_SECONDS = 0.2


@dataclass(frozen=True)
class _WorkerSpec:
    name: str
    group: str
    description: str
    exclusive: bool | None = None


@dataclass(frozen=True)
class _TrackingConfig:
    effect_type: type[Any]
    cancel_event_attr: str
    request_id_attr: str


@dataclass(frozen=True)
class _SearchRuntimeConfig:
    debounce_seconds: float
    worker_key: str
    timer_attr: str
    pending_request_attr: str
    service_attr: str
    tracking: _TrackingConfig


CompleteActionHandler = Callable[[Effect, object], tuple[Any, ...]]
FailureActionHandler = Callable[[Effect, BaseException | None, str], tuple[Any, ...]]


_FILE_SEARCH_RUNTIME = _SearchRuntimeConfig(
    debounce_seconds=FILE_SEARCH_DEBOUNCE_SECONDS,
    worker_key="file-search",
    timer_attr="_file_search_timer",
    pending_request_attr="pending_file_search_request_id",
    service_attr="_file_search_service",
    tracking=_TrackingConfig(
        effect_type=RunFileSearchEffect,
        cancel_event_attr="_active_file_search_cancel_event",
        request_id_attr="_active_file_search_request_id",
    ),
)

_GREP_SEARCH_RUNTIME = _SearchRuntimeConfig(
    debounce_seconds=GREP_SEARCH_DEBOUNCE_SECONDS,
    worker_key="grep-search",
    timer_attr="_grep_search_timer",
    pending_request_attr="pending_grep_search_request_id",
    service_attr="_grep_search_service",
    tracking=_TrackingConfig(
        effect_type=RunGrepSearchEffect,
        cancel_event_attr="_active_grep_search_cancel_event",
        request_id_attr="_active_grep_search_request_id",
    ),
)

_DIRECTORY_SIZE_TRACKING = _TrackingConfig(
    effect_type=RunDirectorySizeEffect,
    cancel_event_attr="_active_directory_size_cancel_event",
    request_id_attr="_active_directory_size_request_id",
)

_CHILD_PANE_TRACKING = _TrackingConfig(
    effect_type=LoadChildPaneSnapshotEffect,
    cancel_event_attr="_active_child_pane_cancel_event",
    request_id_attr="_active_child_pane_request_id",
)

_TRACKING_CONFIGS = (
    _CHILD_PANE_TRACKING,
    _FILE_SEARCH_RUNTIME.tracking,
    _GREP_SEARCH_RUNTIME.tracking,
    _DIRECTORY_SIZE_TRACKING,
)


def sync_runtime_state(app: Any, previous_state: Any, next_state: Any) -> None:
    if previous_state.pending_child_pane_request_id != next_state.pending_child_pane_request_id:
        cancel_pending_child_pane(app)
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
    cancel_pending_child_pane(app)
    cancel_pending_file_search(app)
    cancel_pending_grep_search(app)
    cancel_pending_directory_size(app)


def schedule_effects(app: Any, effects: Sequence[Effect]) -> None:
    for effect in effects:
        _schedule_effect(app, effect)


def _schedule_effect(app: Any, effect: Effect) -> None:
    for effect_type, scheduler in _EFFECT_SCHEDULERS:
        if isinstance(effect, effect_type):
            scheduler(app, effect)
            return


def _run_worker(
    app: Any,
    effect: Effect,
    worker_fn: Callable[[], object],
    spec: _WorkerSpec,
) -> None:
    worker_kwargs = {
        "name": spec.name,
        "group": spec.group,
        "description": spec.description,
        "exit_on_error": False,
        "thread": True,
    }
    if spec.exclusive is not None:
        worker_kwargs["exclusive"] = spec.exclusive
    worker = app.run_worker(worker_fn, **worker_kwargs)
    app._pending_workers[worker.name] = effect


def _cancel_timer(app: Any, timer_attr: str) -> None:
    timer = getattr(app, timer_attr)
    if timer is None:
        return
    cast_timer: Timer = timer
    cast_timer.stop()
    setattr(app, timer_attr, None)


def _set_active_tracking(
    app: Any,
    tracking: _TrackingConfig,
    request_id: int,
    cancel_event: threading.Event,
) -> None:
    setattr(app, tracking.cancel_event_attr, cancel_event)
    setattr(app, tracking.request_id_attr, request_id)


def _cancel_active_tracking(app: Any, tracking: _TrackingConfig) -> None:
    cancel_event = getattr(app, tracking.cancel_event_attr)
    if cancel_event is None:
        return
    cancel_event.set()
    setattr(app, tracking.cancel_event_attr, None)
    setattr(app, tracking.request_id_attr, None)


def _clear_tracking_for_request(app: Any, tracking: _TrackingConfig, request_id: int) -> None:
    if getattr(app, tracking.request_id_attr) != request_id:
        return
    setattr(app, tracking.cancel_event_attr, None)
    setattr(app, tracking.request_id_attr, None)


def schedule_browser_snapshot(app: Any, effect: LoadBrowserSnapshotEffect) -> None:
    if effect.invalidate_paths:
        app._snapshot_loader.invalidate_directory_listing_cache(effect.invalidate_paths)
    _run_worker(
        app,
        effect,
        partial(
            app._snapshot_loader.load_browser_snapshot,
            effect.path,
            effect.cursor_path,
        ),
        _WorkerSpec(
            name=f"browser-snapshot:{effect.request_id}",
            group="browser-snapshot",
            description=effect.path,
            exclusive=True,
        ),
    )


def schedule_child_pane_snapshot(app: Any, effect: LoadChildPaneSnapshotEffect) -> None:
    _cancel_timer(app, "_child_pane_timer")
    if CHILD_PANE_DEBOUNCE_SECONDS <= 0:
        start_child_pane_snapshot(app, effect)
        return
    timer = app.set_timer(
        CHILD_PANE_DEBOUNCE_SECONDS,
        partial(start_child_pane_snapshot, app, effect),
        name=f"child-pane-snapshot-debounce:{effect.request_id}",
    )
    setattr(app, "_child_pane_timer", timer)


def start_child_pane_snapshot(app: Any, effect: LoadChildPaneSnapshotEffect) -> None:
    setattr(app, "_child_pane_timer", None)
    if app._app_state.pending_child_pane_request_id != effect.request_id:
        return
    cancel_event = threading.Event()
    _set_active_tracking(app, _CHILD_PANE_TRACKING, effect.request_id, cancel_event)
    loader = partial(
        app._snapshot_loader.load_child_pane_snapshot,
        effect.current_path,
        effect.cursor_path,
        preview_max_bytes=effect.preview_max_bytes,
    )
    if effect.grep_result is not None:
        loader = partial(
            app._snapshot_loader.load_grep_preview,
            effect.current_path,
            effect.grep_result,
            context_lines=effect.grep_context_lines,
            preview_max_bytes=effect.preview_max_bytes,
        )
    _run_worker(
        app,
        effect,
        loader,
        _WorkerSpec(
            name=f"child-pane-snapshot:{effect.request_id}",
            group="child-pane-snapshot",
            description=effect.cursor_path,
            exclusive=True,
        ),
    )


def schedule_clipboard_paste(app: Any, effect: RunClipboardPasteEffect) -> None:
    _run_worker(
        app,
        effect,
        partial(app._clipboard_service.execute_paste, effect.request),
        _WorkerSpec(
            name=f"clipboard-paste:{effect.request_id}",
            group="clipboard-paste",
            description=effect.request.destination_dir,
            exclusive=True,
        ),
    )


def schedule_config_save(app: Any, effect: RunConfigSaveEffect) -> None:
    _run_worker(
        app,
        effect,
        partial(
            app._config_save_service.save,
            path=effect.path,
            config=effect.config,
        ),
        _WorkerSpec(
            name=f"config-save:{effect.request_id}",
            group="config-save",
            description=effect.path,
            exclusive=True,
        ),
    )


def schedule_shell_command(app: Any, effect: RunShellCommandEffect) -> None:
    _run_worker(
        app,
        effect,
        partial(
            app._shell_command_service.execute,
            cwd=effect.cwd,
            command=effect.command,
        ),
        _WorkerSpec(
            name=f"shell-command:{effect.request_id}",
            group="shell-command",
            description=effect.cwd,
            exclusive=True,
        ),
    )


def schedule_directory_sizes(app: Any, effect: RunDirectorySizeEffect) -> None:
    cancel_event = threading.Event()
    _set_active_tracking(app, _DIRECTORY_SIZE_TRACKING, effect.request_id, cancel_event)
    _run_worker(
        app,
        effect,
        partial(
            app._directory_size_service.calculate_sizes,
            effect.paths,
            is_cancelled=cancel_event.is_set,
        ),
        _WorkerSpec(
            name=f"directory-size:{effect.request_id}",
            group="directory-size",
            description=",".join(effect.paths),
            exclusive=True,
        ),
    )


def schedule_file_mutation(app: Any, effect: RunFileMutationEffect) -> None:
    _run_worker(
        app,
        effect,
        partial(app._file_mutation_service.execute, effect.request),
        _WorkerSpec(
            name=f"file-mutation:{effect.request_id}",
            group="file-mutation",
            description=str(effect.request),
            exclusive=True,
        ),
    )


def schedule_undo(app: Any, effect: RunUndoEffect) -> None:
    _run_worker(
        app,
        effect,
        partial(app._undo_service.execute, effect.entry),
        _WorkerSpec(
            name=f"undo:{effect.request_id}",
            group="undo",
            description=effect.entry.kind,
            exclusive=True,
        ),
    )


def schedule_archive_preparation(app: Any, effect: RunArchivePreparationEffect) -> None:
    _run_worker(
        app,
        effect,
        partial(app._archive_extract_service.prepare, effect.request),
        _WorkerSpec(
            name=f"archive-prepare:{effect.request_id}",
            group="archive-prepare",
            description=effect.request.source_path,
            exclusive=True,
        ),
    )


def schedule_archive_extract(app: Any, effect: RunArchiveExtractEffect) -> None:
    _run_worker(
        app,
        effect,
        partial(
            app._archive_extract_service.execute,
            effect.request,
            progress_callback=partial(report_archive_extract_progress, app, effect.request_id),
        ),
        _WorkerSpec(
            name=f"archive-extract:{effect.request_id}",
            group="archive-extract",
            description=effect.request.source_path,
            exclusive=True,
        ),
    )


def schedule_zip_compress_preparation(app: Any, effect: RunZipCompressPreparationEffect) -> None:
    _run_worker(
        app,
        effect,
        partial(app._zip_compress_service.prepare, effect.request),
        _WorkerSpec(
            name=f"zip-compress-prepare:{effect.request_id}",
            group="zip-compress-prepare",
            description=effect.request.destination_path,
            exclusive=True,
        ),
    )


def schedule_zip_compress(app: Any, effect: RunZipCompressEffect) -> None:
    _run_worker(
        app,
        effect,
        partial(
            app._zip_compress_service.execute,
            effect.request,
            progress_callback=partial(report_zip_compress_progress, app, effect.request_id),
        ),
        _WorkerSpec(
            name=f"zip-compress:{effect.request_id}",
            group="zip-compress",
            description=effect.request.destination_path,
            exclusive=True,
        ),
    )


def schedule_external_launch(app: Any, effect: RunExternalLaunchEffect) -> None:
    _run_worker(
        app,
        effect,
        partial(app._external_launch_service.execute, effect.request),
        _WorkerSpec(
            name=f"external-launch:{effect.request_id}",
            group="external-launch",
            description=str(effect.request),
        ),
    )


def schedule_file_search(app: Any, effect: RunFileSearchEffect) -> None:
    _schedule_search_effect(app, effect, _FILE_SEARCH_RUNTIME)


def start_file_search_worker(app: Any, effect: RunFileSearchEffect) -> None:
    _start_search_worker(app, effect, _FILE_SEARCH_RUNTIME)


def schedule_grep_search(app: Any, effect: RunGrepSearchEffect) -> None:
    _schedule_search_effect(app, effect, _GREP_SEARCH_RUNTIME)


def schedule_text_replace_preview(app: Any, effect: RunTextReplacePreviewEffect) -> None:
    _run_worker(
        app,
        effect,
        partial(app._text_replace_service.preview, effect.request),
        _WorkerSpec(
            name=f"text-replace-preview:{effect.request_id}",
            group="text-replace-preview",
            description="preview replacement",
            exclusive=True,
        ),
    )


def schedule_text_replace_apply(app: Any, effect: RunTextReplaceApplyEffect) -> None:
    _run_worker(
        app,
        effect,
        partial(app._text_replace_service.apply, effect.request),
        _WorkerSpec(
            name=f"text-replace-apply:{effect.request_id}",
            group="text-replace-apply",
            description="apply replacement",
            exclusive=True,
        ),
    )


def start_grep_search_worker(app: Any, effect: RunGrepSearchEffect) -> None:
    _start_search_worker(app, effect, _GREP_SEARCH_RUNTIME)


def _schedule_search_effect(
    app: Any,
    effect: RunFileSearchEffect | RunGrepSearchEffect,
    config: _SearchRuntimeConfig,
) -> None:
    _cancel_timer(app, config.timer_attr)
    timer = app.set_timer(
        config.debounce_seconds,
        partial(_start_search_worker, app, effect, config),
        name=f"{config.worker_key}-debounce:{effect.request_id}",
    )
    setattr(app, config.timer_attr, timer)


def _start_search_worker(
    app: Any,
    effect: RunFileSearchEffect | RunGrepSearchEffect,
    config: _SearchRuntimeConfig,
) -> None:
    setattr(app, config.timer_attr, None)
    if getattr(app._app_state, config.pending_request_attr) != effect.request_id:
        return
    cancel_event = threading.Event()
    _set_active_tracking(app, config.tracking, effect.request_id, cancel_event)
    service = getattr(app, config.service_attr)
    search_kwargs = {
        "show_hidden": effect.show_hidden,
        "is_cancelled": cancel_event.is_set,
    }
    if isinstance(effect, RunGrepSearchEffect):
        search_kwargs["include_globs"] = effect.include_globs
        search_kwargs["exclude_globs"] = effect.exclude_globs
    _run_worker(
        app,
        effect,
        partial(
            service.search,
            effect.root_path,
            effect.query,
            **search_kwargs,
        ),
        _WorkerSpec(
            name=f"{config.worker_key}:{effect.request_id}",
            group=config.worker_key,
            description=_describe_search_effect(effect),
            exclusive=True,
        ),
    )


def _describe_search_effect(effect: RunFileSearchEffect | RunGrepSearchEffect) -> str:
    if isinstance(effect, RunFileSearchEffect):
        return effect.query
    parts = [effect.query]
    if effect.include_globs:
        parts.append(f"include={','.join(effect.include_globs)}")
    if effect.exclude_globs:
        parts.append(f"exclude={','.join(effect.exclude_globs)}")
    return " | ".join(part for part in parts if part)


def cancel_pending_file_search(app: Any) -> None:
    _cancel_pending_search(app, _FILE_SEARCH_RUNTIME)


def cancel_file_search_timer(app: Any) -> None:
    _cancel_timer(app, _FILE_SEARCH_RUNTIME.timer_attr)


def cancel_active_file_search(app: Any) -> None:
    _cancel_active_tracking(app, _FILE_SEARCH_RUNTIME.tracking)


def cancel_pending_grep_search(app: Any) -> None:
    _cancel_pending_search(app, _GREP_SEARCH_RUNTIME)


def cancel_grep_search_timer(app: Any) -> None:
    _cancel_timer(app, _GREP_SEARCH_RUNTIME.timer_attr)


def cancel_active_grep_search(app: Any) -> None:
    _cancel_active_tracking(app, _GREP_SEARCH_RUNTIME.tracking)


def cancel_pending_directory_size(app: Any) -> None:
    _cancel_active_tracking(app, _DIRECTORY_SIZE_TRACKING)


def cancel_pending_child_pane(app: Any) -> None:
    _cancel_timer(app, "_child_pane_timer")
    _cancel_active_tracking(app, _CHILD_PANE_TRACKING)


def _cancel_pending_search(app: Any, config: _SearchRuntimeConfig) -> None:
    _cancel_timer(app, config.timer_attr)
    _cancel_active_tracking(app, config.tracking)


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


def _schedule_external_launch_effect(app: Any, effect: RunExternalLaunchEffect) -> None:
    if effect.request.kind == "copy_paths":
        run_copy_paths(app, effect)
        return
    if effect.request.kind == "open_editor":
        app.call_next(run_foreground_external_launch, app, effect)
        return
    schedule_external_launch(app, effect)


def _close_split_terminal_effect(app: Any, effect: CloseSplitTerminalEffect) -> None:
    close_split_terminal(app)


_EFFECT_SCHEDULERS = (
    (LoadBrowserSnapshotEffect, schedule_browser_snapshot),
    (LoadChildPaneSnapshotEffect, schedule_child_pane_snapshot),
    (RunArchivePreparationEffect, schedule_archive_preparation),
    (RunArchiveExtractEffect, schedule_archive_extract),
    (RunZipCompressPreparationEffect, schedule_zip_compress_preparation),
    (RunZipCompressEffect, schedule_zip_compress),
    (RunClipboardPasteEffect, schedule_clipboard_paste),
    (RunConfigSaveEffect, schedule_config_save),
    (RunDirectorySizeEffect, schedule_directory_sizes),
    (RunFileMutationEffect, schedule_file_mutation),
    (RunUndoEffect, schedule_undo),
    (RunExternalLaunchEffect, _schedule_external_launch_effect),
    (RunShellCommandEffect, schedule_shell_command),
    (RunFileSearchEffect, schedule_file_search),
    (RunGrepSearchEffect, schedule_grep_search),
    (RunTextReplacePreviewEffect, schedule_text_replace_preview),
    (RunTextReplaceApplyEffect, schedule_text_replace_apply),
    (StartSplitTerminalEffect, start_split_terminal),
    (WriteSplitTerminalInputEffect, write_split_terminal_input),
    (CloseSplitTerminalEffect, _close_split_terminal_effect),
)


def _complete_browser_snapshot(
    effect: LoadBrowserSnapshotEffect,
    result: object,
) -> tuple[Any, ...]:
    return (
        BrowserSnapshotLoaded(
            request_id=effect.request_id,
            snapshot=result,
            blocking=effect.blocking,
        ),
    )


def _complete_child_pane_snapshot(
    effect: LoadChildPaneSnapshotEffect,
    result: object,
) -> tuple[Any, ...]:
    return (
        ChildPaneSnapshotLoaded(
            request_id=effect.request_id,
            pane=result,
        ),
    )


def _complete_clipboard_paste_conflicts(
    effect: Effect,
    result: PasteConflictPrompt,
) -> tuple[Any, ...]:
    return (
        ClipboardPasteNeedsResolution(
            request_id=effect.request_id,
            request=result.request,
            conflicts=result.conflicts,
        ),
    )


def _complete_clipboard_paste(
    effect: Effect,
    result: PasteExecutionResult,
) -> tuple[Any, ...]:
    return (
        ClipboardPasteCompleted(
            request_id=effect.request_id,
            summary=result.summary,
            applied_changes=result.applied_changes,
        ),
    )


def _complete_file_mutation(effect: Effect, result: FileMutationResult) -> tuple[Any, ...]:
    return (
        FileMutationCompleted(
            request_id=effect.request_id,
            result=result,
        ),
    )


def _complete_undo(effect: RunUndoEffect, result: UndoResult) -> tuple[Any, ...]:
    return (
        UndoCompleted(
            request_id=effect.request_id,
            entry=effect.entry,
            result=result,
        ),
    )


def _complete_archive_preparation(
    effect: RunArchivePreparationEffect,
    result: ExtractArchivePreparationResult,
) -> tuple[Any, ...]:
    first_conflict_path = None
    if result.conflicts:
        first_conflict_path = result.conflicts[0].destination_path
    return (
        ArchivePreparationCompleted(
            request_id=effect.request_id,
            request=result.request,
            total_entries=result.total_entries,
            conflict_count=len(result.conflicts),
            first_conflict_path=first_conflict_path,
        ),
    )


def _complete_archive_extract(
    effect: RunArchiveExtractEffect,
    result: ExtractArchiveResult,
) -> tuple[Any, ...]:
    return (
        ArchiveExtractCompleted(
            request_id=effect.request_id,
            result=result,
        ),
    )


def _complete_zip_compress_preparation(
    effect: RunZipCompressPreparationEffect,
    result: CreateZipArchivePreparationResult,
) -> tuple[Any, ...]:
    return (
        ZipCompressPreparationCompleted(
            request_id=effect.request_id,
            request=result.request,
            total_entries=result.total_entries,
            destination_exists=result.destination_exists,
        ),
    )


def _complete_zip_compress(
    effect: RunZipCompressEffect,
    result: CreateZipArchiveResult,
) -> tuple[Any, ...]:
    return (
        ZipCompressCompleted(
            request_id=effect.request_id,
            result=result,
        ),
    )


def _complete_config_save(effect: RunConfigSaveEffect, result: object) -> tuple[Any, ...]:
    return (
        ConfigSaveCompleted(
            request_id=effect.request_id,
            path=result,
            config=effect.config,
        ),
    )


def _complete_directory_sizes(
    effect: RunDirectorySizeEffect,
    result: object,
) -> tuple[Any, ...]:
    sizes, failures = result
    return (
        DirectorySizesLoaded(
            request_id=effect.request_id,
            sizes=sizes,
            failures=failures,
        ),
    )


def _complete_external_launch(
    effect: RunExternalLaunchEffect,
    result: object,
) -> tuple[Any, ...]:
    return (
        ExternalLaunchCompleted(
            request_id=effect.request_id,
            request=effect.request,
        ),
    )


def _complete_shell_command(
    effect: RunShellCommandEffect,
    result: ShellCommandResult,
) -> tuple[Any, ...]:
    return (
        ShellCommandCompleted(
            request_id=effect.request_id,
            result=result,
        ),
    )


def _complete_file_search(effect: RunFileSearchEffect, result: object) -> tuple[Any, ...]:
    return (
        FileSearchCompleted(
            request_id=effect.request_id,
            query=effect.query,
            results=result,
        ),
    )


def _complete_grep_search(effect: RunGrepSearchEffect, result: object) -> tuple[Any, ...]:
    return (
        GrepSearchCompleted(
            request_id=effect.request_id,
            query=effect.query,
            results=result,
        ),
    )


def _complete_text_replace_preview(
    effect: RunTextReplacePreviewEffect,
    result: TextReplacePreviewResult,
) -> tuple[Any, ...]:
    return (
        TextReplacePreviewCompleted(
            request_id=effect.request_id,
            result=result,
        ),
    )


def _complete_text_replace_apply(
    effect: RunTextReplaceApplyEffect,
    result: TextReplaceResult,
) -> tuple[Any, ...]:
    return (
        TextReplaceApplied(
            request_id=effect.request_id,
            result=result,
        ),
    )


ExtraFieldBuilder = Callable[[Effect, BaseException | None, str], Any]


def _make_failed_handler(
    event_cls: type,
    *,
    extra_field_builders: dict[str, ExtraFieldBuilder] | None = None,
) -> FailureActionHandler:
    builders = extra_field_builders or {}

    def handler(effect: Effect, error: BaseException | None, message: str) -> tuple[Any, ...]:
        kwargs: dict[str, Any] = {"request_id": effect.request_id, "message": message}
        for name, builder in builders.items():
            kwargs[name] = builder(effect, error, message)
        return (event_cls(**kwargs),)

    return handler


_failed_browser_snapshot = _make_failed_handler(
    BrowserSnapshotFailed,
    extra_field_builders={"blocking": lambda e, _err, _msg: e.blocking},
)
_failed_child_pane_snapshot = _make_failed_handler(ChildPaneSnapshotFailed)
_failed_clipboard_paste = _make_failed_handler(ClipboardPasteFailed)
_failed_file_mutation = _make_failed_handler(FileMutationFailed)
_failed_archive_preparation = _make_failed_handler(ArchivePreparationFailed)
_failed_archive_extract = _make_failed_handler(ArchiveExtractFailed)
_failed_zip_compress_preparation = _make_failed_handler(ZipCompressPreparationFailed)
_failed_zip_compress = _make_failed_handler(ZipCompressFailed)
_failed_config_save = _make_failed_handler(ConfigSaveFailed)
_failed_directory_sizes = _make_failed_handler(
    DirectorySizesFailed,
    extra_field_builders={"paths": lambda e, _err, _msg: e.paths},
)
_failed_external_launch = _make_failed_handler(
    ExternalLaunchFailed,
    extra_field_builders={"request": lambda e, _err, _msg: e.request},
)
_failed_shell_command = _make_failed_handler(ShellCommandFailed)
_failed_undo = _make_failed_handler(UndoFailed)
_failed_file_search = _make_failed_handler(
    FileSearchFailed,
    extra_field_builders={
        "query": lambda e, _err, _msg: e.query,
        "invalid_query": lambda _e, err, _msg: isinstance(err, InvalidFileSearchQueryError),
    },
)
_failed_grep_search = _make_failed_handler(
    GrepSearchFailed,
    extra_field_builders={
        "query": lambda e, _err, _msg: e.query,
        "invalid_query": lambda _e, err, _msg: isinstance(err, InvalidGrepSearchQueryError),
    },
)
_failed_text_replace_preview = _make_failed_handler(
    TextReplacePreviewFailed,
    extra_field_builders={
        "invalid_query": lambda _e, err, _msg: isinstance(err, InvalidTextReplaceQueryError),
    },
)
_failed_text_replace_apply = _make_failed_handler(TextReplaceApplyFailed)


_RESULT_COMPLETE_HANDLERS: tuple[tuple[type[Any], CompleteActionHandler], ...] = (
    (PasteConflictPrompt, _complete_clipboard_paste_conflicts),
    (PasteExecutionResult, _complete_clipboard_paste),
    (ExtractArchivePreparationResult, _complete_archive_preparation),
    (ExtractArchiveResult, _complete_archive_extract),
    (CreateZipArchivePreparationResult, _complete_zip_compress_preparation),
    (CreateZipArchiveResult, _complete_zip_compress),
    (FileMutationResult, _complete_file_mutation),
    (UndoResult, _complete_undo),
)

_COMPLETE_ACTION_HANDLERS: tuple[tuple[type[Any], CompleteActionHandler], ...] = (
    (LoadBrowserSnapshotEffect, _complete_browser_snapshot),
    (LoadChildPaneSnapshotEffect, _complete_child_pane_snapshot),
    (RunConfigSaveEffect, _complete_config_save),
    (RunDirectorySizeEffect, _complete_directory_sizes),
    (RunExternalLaunchEffect, _complete_external_launch),
    (RunShellCommandEffect, _complete_shell_command),
    (RunFileSearchEffect, _complete_file_search),
    (RunGrepSearchEffect, _complete_grep_search),
    (RunTextReplacePreviewEffect, _complete_text_replace_preview),
    (RunTextReplaceApplyEffect, _complete_text_replace_apply),
)

_FAILED_ACTION_HANDLERS: tuple[tuple[type[Any], FailureActionHandler], ...] = (
    (LoadBrowserSnapshotEffect, _failed_browser_snapshot),
    (LoadChildPaneSnapshotEffect, _failed_child_pane_snapshot),
    (RunArchivePreparationEffect, _failed_archive_preparation),
    (RunArchiveExtractEffect, _failed_archive_extract),
    (RunZipCompressPreparationEffect, _failed_zip_compress_preparation),
    (RunZipCompressEffect, _failed_zip_compress),
    (RunClipboardPasteEffect, _failed_clipboard_paste),
    (RunFileMutationEffect, _failed_file_mutation),
    (RunConfigSaveEffect, _failed_config_save),
    (RunDirectorySizeEffect, _failed_directory_sizes),
    (RunExternalLaunchEffect, _failed_external_launch),
    (RunShellCommandEffect, _failed_shell_command),
    (RunUndoEffect, _failed_undo),
    (RunFileSearchEffect, _failed_file_search),
    (RunGrepSearchEffect, _failed_grep_search),
    (RunTextReplacePreviewEffect, _failed_text_replace_preview),
    (RunTextReplaceApplyEffect, _failed_text_replace_apply),
)


def _find_handler(
    value: object,
    handlers: tuple[tuple[type[Any], Callable[..., tuple[Any, ...]]], ...],
) -> Callable[..., tuple[Any, ...]] | None:
    for value_type, handler in handlers:
        if isinstance(value, value_type):
            return handler
    return None


def complete_worker_actions(effect: Effect, result: object) -> tuple[Any, ...]:
    handler = _find_handler(result, _RESULT_COMPLETE_HANDLERS)
    if handler is not None:
        return handler(effect, result)
    handler = _find_handler(effect, _COMPLETE_ACTION_HANDLERS)
    if handler is None:
        return ()
    return handler(effect, result)


def failed_worker_actions(effect: Effect, error: BaseException | None) -> tuple[Any, ...]:
    message = str(error) or "Operation failed"
    handler = _find_handler(effect, _FAILED_ACTION_HANDLERS)
    if handler is None:
        return ()
    return handler(effect, error, message)


def clear_effect_tracking(app: Any, effect: Effect) -> None:
    for tracking in _TRACKING_CONFIGS:
        if isinstance(effect, tracking.effect_type):
            _clear_tracking_for_request(app, tracking, effect.request_id)
            return


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
