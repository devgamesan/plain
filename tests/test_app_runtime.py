import asyncio
import threading
from contextlib import nullcontext
from dataclasses import dataclass, field, replace
from types import SimpleNamespace
from typing import Any

from textual.app import SuspendNotSupported
from textual.worker import WorkerState

from zivo.app_runtime import (
    cancel_pending_child_pane,
    cancel_pending_directory_size,
    cancel_pending_file_search,
    cancel_pending_grep_search,
    clear_effect_tracking,
    complete_worker_actions,
    failed_worker_actions,
    handle_worker_state_changed,
    run_foreground_external_launch,
    schedule_browser_snapshot,
    schedule_child_pane_snapshot,
    schedule_file_search,
    schedule_transfer_pane_snapshot,
    schedule_undo,
    start_child_pane_snapshot,
    start_file_search_worker,
    start_grep_search_worker,
    start_split_terminal,
    write_split_terminal_input,
)
from zivo.models import AppConfig, ExternalLaunchRequest, UndoDeletePathStep, UndoEntry, UndoResult
from zivo.services import InvalidFileSearchQueryError
from zivo.state import (
    BrowserSnapshot,
    DirectoryEntryState,
    LoadBrowserSnapshotEffect,
    LoadChildPaneSnapshotEffect,
    LoadTransferPaneEffect,
    PaneState,
    RunConfigSaveEffect,
    RunDirectorySizeEffect,
    RunExternalLaunchEffect,
    RunFileSearchEffect,
    RunGrepSearchEffect,
    RunUndoEffect,
    StartSplitTerminalEffect,
    WriteSplitTerminalInputEffect,
    build_initial_app_state,
)
from zivo.state.actions import (
    BrowserSnapshotLoaded,
    ChildPaneSnapshotLoaded,
    ConfigSaveCompleted,
    DirectorySizesLoaded,
    ExternalLaunchFailed,
    FileSearchCompleted,
    FileSearchFailed,
    SplitTerminalStartFailed,
    UndoCompleted,
)


@dataclass
class _RecordingTimer:
    interval: float
    callback: Any
    name: str
    stopped: bool = False

    def stop(self) -> None:
        self.stopped = True


@dataclass
class _RecordingSnapshotLoader:
    invalidated_paths: list[tuple[str, ...]] = field(default_factory=list)
    load_browser_snapshot_calls: list[tuple[str, str | None]] = field(default_factory=list)
    load_child_pane_snapshot_calls: list[tuple[str, str | None, int]] = field(default_factory=list)
    load_current_pane_snapshot_calls: list[tuple[str, str | None]] = field(default_factory=list)

    def invalidate_directory_listing_cache(self, paths: tuple[str, ...] = ()) -> None:
        self.invalidated_paths.append(paths)

    def load_browser_snapshot(
        self,
        path: str,
        cursor_path: str | None = None,
    ) -> None:
        self.load_browser_snapshot_calls.append((path, cursor_path))
        return None

    def load_child_pane_snapshot(
        self,
        current_path: str,
        cursor_path: str | None,
        *,
        preview_max_bytes: int = 64 * 1024,
    ) -> PaneState:
        self.load_child_pane_snapshot_calls.append((current_path, cursor_path, preview_max_bytes))
        return PaneState(directory_path=current_path, entries=())

    def load_current_pane_snapshot(
        self,
        path: str,
        cursor_path: str | None,
    ) -> tuple[str, PaneState, PaneState]:
        self.load_current_pane_snapshot_calls.append((path, cursor_path))
        pane = PaneState(directory_path=path, entries=(), cursor_path=cursor_path)
        return path, pane, PaneState(directory_path=path, entries=())


@dataclass
class _RecordingApp:
    _app_state: Any = field(default_factory=build_initial_app_state)
    _snapshot_loader: Any = field(default_factory=_RecordingSnapshotLoader)
    _pending_workers: dict[str, object] = field(default_factory=dict)
    _child_pane_timer: Any = None
    _file_search_timer: Any = None
    _grep_search_timer: Any = None
    _active_child_pane_cancel_event: threading.Event | None = None
    _active_child_pane_request_id: int | None = None
    _active_file_search_cancel_event: threading.Event | None = None
    _active_file_search_request_id: int | None = None
    _active_grep_search_cancel_event: threading.Event | None = None
    _active_grep_search_request_id: int | None = None
    _active_directory_size_cancel_event: threading.Event | None = None
    _active_directory_size_request_id: int | None = None
    _external_launch_service: Any = field(
        default_factory=lambda: SimpleNamespace(execute=lambda request: None)
    )
    _split_terminal_service: Any = field(
        default_factory=lambda: SimpleNamespace(start=lambda cwd, **kwargs: None)
    )
    _undo_service: Any = field(default_factory=lambda: SimpleNamespace(execute=lambda entry: None))
    _split_terminal_session: Any = None
    suspend_error: BaseException | None = None
    run_worker_calls: list[dict[str, Any]] = field(default_factory=list)
    set_timer_calls: list[dict[str, Any]] = field(default_factory=list)
    call_next_calls: list[tuple[Any, tuple[Any, ...]]] = field(default_factory=list)
    dispatched_actions: list[tuple[Any, ...]] = field(default_factory=list)
    refresh_calls: list[dict[str, Any]] = field(default_factory=list)

    def run_worker(self, worker_fn: Any, **kwargs: Any) -> Any:
        self.run_worker_calls.append({"worker_fn": worker_fn, **kwargs})
        return SimpleNamespace(name=kwargs["name"])

    def set_timer(self, interval: float, callback: Any, *, name: str) -> _RecordingTimer:
        timer = _RecordingTimer(interval=interval, callback=callback, name=name)
        self.set_timer_calls.append(
            {
                "interval": interval,
                "callback": callback,
                "name": name,
                "timer": timer,
            }
        )
        return timer

    def call_next(self, callback: Any, *args: Any) -> None:
        self.call_next_calls.append((callback, args))

    async def dispatch_actions(self, actions: tuple[Any, ...]) -> None:
        self.dispatched_actions.append(actions)

    def refresh(self, **kwargs: Any) -> None:
        self.refresh_calls.append(kwargs)

    def suspend(self) -> Any:
        if self.suspend_error is not None:
            raise self.suspend_error
        return nullcontext()


@dataclass(frozen=True)
class _FailingExternalLaunchService:
    message: str

    def execute(self, request: ExternalLaunchRequest) -> None:
        raise OSError(self.message)


@dataclass(frozen=True)
class _FailingSplitTerminalService:
    message: str

    def start(self, cwd: str, **kwargs: Any) -> None:
        raise OSError(self.message)


@dataclass(frozen=True)
class _FailingSplitTerminalSession:
    message: str

    def write(self, data: str) -> None:
        raise OSError(self.message)


def _scheduled_actions(app: _RecordingApp) -> tuple[Any, ...]:
    callback, args = app.call_next_calls[-1]
    assert callback == app.dispatch_actions
    return args[0]


def test_complete_worker_actions_maps_browser_snapshot_load() -> None:
    snapshot = BrowserSnapshot(
        current_path="/tmp/project",
        parent_pane=PaneState(
            directory_path="/tmp",
            entries=(DirectoryEntryState("/tmp/project", "project", "dir"),),
        ),
        current_pane=PaneState(
            directory_path="/tmp/project",
            entries=(DirectoryEntryState("/tmp/project/README.md", "README.md", "file"),),
            cursor_path="/tmp/project/README.md",
        ),
        child_pane=PaneState(directory_path="/tmp/project", entries=()),
    )

    actions = complete_worker_actions(
        LoadBrowserSnapshotEffect(
            request_id=7,
            path="/tmp/project",
            cursor_path="/tmp/project/README.md",
            blocking=True,
        ),
        snapshot,
    )

    assert actions == (
        BrowserSnapshotLoaded(
            request_id=7,
            snapshot=snapshot,
            blocking=True,
        ),
    )


def test_schedule_browser_snapshot_invalidates_requested_paths_before_worker() -> None:
    loader = _RecordingSnapshotLoader()
    app = _RecordingApp(_snapshot_loader=loader)
    effect = LoadBrowserSnapshotEffect(
        request_id=7,
        path="/tmp/project",
        cursor_path="/tmp/project/docs",
        blocking=True,
        invalidate_paths=("/tmp/project", "/tmp", "/tmp/project/docs"),
    )

    schedule_browser_snapshot(app, effect)
    worker_fn = app.run_worker_calls[0]["worker_fn"]
    worker_fn()

    assert loader.invalidated_paths == [("/tmp/project", "/tmp", "/tmp/project/docs")]
    assert loader.load_browser_snapshot_calls == [("/tmp/project", "/tmp/project/docs")]


def test_schedule_transfer_pane_snapshot_uses_pane_scoped_worker_group() -> None:
    app = _RecordingApp()

    schedule_transfer_pane_snapshot(
        app,
        LoadTransferPaneEffect(request_id=1, pane_id="left", path="/tmp/source"),
    )
    schedule_transfer_pane_snapshot(
        app,
        LoadTransferPaneEffect(request_id=2, pane_id="right", path="/tmp/destination"),
    )

    assert [call["group"] for call in app.run_worker_calls] == [
        "transfer-pane-snapshot:left",
        "transfer-pane-snapshot:right",
    ]
    assert all(call["exclusive"] is True for call in app.run_worker_calls)


def test_complete_worker_actions_maps_directory_size_result() -> None:
    actions = complete_worker_actions(
        RunDirectorySizeEffect(
            request_id=11,
            paths=("/tmp/project/docs",),
        ),
        ((("/tmp/project/docs", 1234),), ()),
    )

    assert actions == (
        DirectorySizesLoaded(
            request_id=11,
            sizes=(("/tmp/project/docs", 1234),),
            failures=(),
        ),
    )


def test_complete_worker_actions_maps_config_save_result() -> None:
    config = AppConfig()

    actions = complete_worker_actions(
        RunConfigSaveEffect(
            request_id=5,
            path="/tmp/config.toml",
            config=config,
        ),
        "/tmp/config.toml",
    )

    assert actions == (
        ConfigSaveCompleted(
            request_id=5,
            path="/tmp/config.toml",
            config=config,
        ),
    )


def test_complete_worker_actions_maps_undo_result() -> None:
    entry = UndoEntry(kind="paste_copy", steps=(UndoDeletePathStep(path="/tmp/copied"),))

    actions = complete_worker_actions(
        RunUndoEffect(request_id=5, entry=entry),
        UndoResult(path=None, message="Undid copied item"),
    )

    assert actions == (
        UndoCompleted(
            request_id=5,
            entry=entry,
            result=UndoResult(path=None, message="Undid copied item"),
        ),
    )


def test_schedule_undo_runs_worker() -> None:
    entry = UndoEntry(kind="paste_copy", steps=(UndoDeletePathStep(path="/tmp/copied"),))
    app = _RecordingApp()
    effect = RunUndoEffect(request_id=3, entry=entry)

    schedule_undo(app, effect)
    worker_fn = app.run_worker_calls[0]["worker_fn"]
    worker_fn()

    assert app.run_worker_calls[0]["name"] == "undo:3"


def test_failed_worker_actions_marks_invalid_file_search_queries() -> None:
    actions = failed_worker_actions(
        RunFileSearchEffect(
            request_id=13,
            root_path="/tmp/project",
            query="re:[",
            show_hidden=False,
        ),
        InvalidFileSearchQueryError("unterminated character set"),
    )

    assert actions == (
        FileSearchFailed(
            request_id=13,
            query="re:[",
            message="unterminated character set",
            invalid_query=True,
        ),
    )


def test_start_file_search_worker_ignores_stale_request() -> None:
    app = _RecordingApp(
        _app_state=replace(build_initial_app_state(), pending_file_search_request_id=99),
    )

    start_file_search_worker(
        app,
        RunFileSearchEffect(
            request_id=7,
            root_path="/tmp/project",
            query="docs",
            show_hidden=False,
        ),
    )

    assert app.run_worker_calls == []
    assert app._pending_workers == {}
    assert app._active_file_search_cancel_event is None
    assert app._active_file_search_request_id is None


def test_start_child_pane_snapshot_ignores_stale_request() -> None:
    app = _RecordingApp(
        _app_state=replace(build_initial_app_state(), pending_child_pane_request_id=99),
    )

    start_child_pane_snapshot(
        app,
        LoadChildPaneSnapshotEffect(
            request_id=7,
            current_path="/tmp/project",
            cursor_path="/tmp/project/docs",
        ),
    )

    assert app.run_worker_calls == []
    assert app._pending_workers == {}
    assert app._active_child_pane_cancel_event is None
    assert app._active_child_pane_request_id is None


def test_start_grep_search_worker_ignores_stale_request() -> None:
    app = _RecordingApp(
        _app_state=replace(build_initial_app_state(), pending_grep_search_request_id=99),
    )

    start_grep_search_worker(
        app,
        RunGrepSearchEffect(
            request_id=7,
            root_path="/tmp/project",
            query="TODO",
            show_hidden=False,
        ),
    )

    assert app.run_worker_calls == []
    assert app._pending_workers == {}
    assert app._active_grep_search_cancel_event is None
    assert app._active_grep_search_request_id is None


def test_schedule_file_search_replaces_existing_timer() -> None:
    app = _RecordingApp()
    existing_timer = _RecordingTimer(interval=0.1, callback=lambda: None, name="old-file-search")
    app._file_search_timer = existing_timer

    schedule_file_search(
        app,
        RunFileSearchEffect(
            request_id=5,
            root_path="/tmp/project",
            query="docs",
            show_hidden=False,
        ),
    )

    assert existing_timer.stopped is True
    assert len(app.set_timer_calls) == 1
    assert app.set_timer_calls[0]["name"] == "file-search-debounce:5"
    assert app._file_search_timer is app.set_timer_calls[0]["timer"]


def test_schedule_child_pane_snapshot_replaces_existing_timer() -> None:
    app = _RecordingApp(
        _app_state=replace(build_initial_app_state(), pending_child_pane_request_id=5),
    )
    existing_timer = _RecordingTimer(
        interval=0.1,
        callback=lambda: None,
        name="old-child-pane",
    )
    app._child_pane_timer = existing_timer

    schedule_child_pane_snapshot(
        app,
        LoadChildPaneSnapshotEffect(
            request_id=5,
            current_path="/tmp/project",
            cursor_path="/tmp/project/docs",
        ),
    )

    assert existing_timer.stopped is True
    assert len(app.set_timer_calls) == 1
    assert app.set_timer_calls[0]["name"] == "child-pane-snapshot-debounce:5"
    assert app._child_pane_timer is app.set_timer_calls[0]["timer"]
    assert app.run_worker_calls == []


def test_start_child_pane_snapshot_passes_preview_max_bytes_to_loader() -> None:
    app = _RecordingApp(
        _app_state=replace(build_initial_app_state(), pending_child_pane_request_id=5),
    )
    effect = LoadChildPaneSnapshotEffect(
        request_id=5,
        current_path="/tmp/project",
        cursor_path="/tmp/project/README.md",
        preview_max_bytes=128 * 1024,
    )

    start_child_pane_snapshot(app, effect)

    assert len(app.run_worker_calls) == 1
    worker_fn = app.run_worker_calls[0]["worker_fn"]
    worker_fn()
    assert app._snapshot_loader.load_child_pane_snapshot_calls == [
        ("/tmp/project", "/tmp/project/README.md", 128 * 1024)
    ]


def test_cancel_pending_runtime_helpers_clear_active_tracking() -> None:
    app = _RecordingApp()
    child_pane_timer = _RecordingTimer(interval=0.1, callback=lambda: None, name="child-pane")
    file_search_timer = _RecordingTimer(interval=0.1, callback=lambda: None, name="file-search")
    grep_search_timer = _RecordingTimer(interval=0.1, callback=lambda: None, name="grep-search")
    child_pane_cancel = threading.Event()
    file_search_cancel = threading.Event()
    grep_search_cancel = threading.Event()
    directory_size_cancel = threading.Event()
    app._child_pane_timer = child_pane_timer
    app._file_search_timer = file_search_timer
    app._grep_search_timer = grep_search_timer
    app._active_child_pane_cancel_event = child_pane_cancel
    app._active_child_pane_request_id = 2
    app._active_file_search_cancel_event = file_search_cancel
    app._active_file_search_request_id = 3
    app._active_grep_search_cancel_event = grep_search_cancel
    app._active_grep_search_request_id = 4
    app._active_directory_size_cancel_event = directory_size_cancel
    app._active_directory_size_request_id = 5

    cancel_pending_child_pane(app)
    cancel_pending_file_search(app)
    cancel_pending_grep_search(app)
    cancel_pending_directory_size(app)

    assert child_pane_timer.stopped is True
    assert app._child_pane_timer is None
    assert child_pane_cancel.is_set()
    assert app._active_child_pane_cancel_event is None
    assert app._active_child_pane_request_id is None
    assert file_search_timer.stopped is True
    assert app._file_search_timer is None
    assert file_search_cancel.is_set()
    assert app._active_file_search_cancel_event is None
    assert app._active_file_search_request_id is None
    assert grep_search_timer.stopped is True
    assert app._grep_search_timer is None
    assert grep_search_cancel.is_set()
    assert app._active_grep_search_cancel_event is None
    assert app._active_grep_search_request_id is None
    assert directory_size_cancel.is_set()
    assert app._active_directory_size_cancel_event is None
    assert app._active_directory_size_request_id is None


def test_clear_effect_tracking_only_clears_matching_request() -> None:
    app = _RecordingApp()
    child_pane_cancel = threading.Event()
    file_search_cancel = threading.Event()
    grep_search_cancel = threading.Event()
    directory_size_cancel = threading.Event()
    app._active_child_pane_cancel_event = child_pane_cancel
    app._active_child_pane_request_id = 2
    app._active_file_search_cancel_event = file_search_cancel
    app._active_file_search_request_id = 3
    app._active_grep_search_cancel_event = grep_search_cancel
    app._active_grep_search_request_id = 4
    app._active_directory_size_cancel_event = directory_size_cancel
    app._active_directory_size_request_id = 5

    clear_effect_tracking(
        app,
        LoadChildPaneSnapshotEffect(
            request_id=99,
            current_path="/tmp/project",
            cursor_path="/tmp/project/docs",
        ),
    )
    clear_effect_tracking(
        app,
        LoadChildPaneSnapshotEffect(
            request_id=2,
            current_path="/tmp/project",
            cursor_path="/tmp/project/docs",
        ),
    )
    clear_effect_tracking(
        app,
        RunFileSearchEffect(
            request_id=99,
            root_path="/tmp/project",
            query="docs",
            show_hidden=False,
        ),
    )
    clear_effect_tracking(
        app,
        RunFileSearchEffect(
            request_id=3,
            root_path="/tmp/project",
            query="docs",
            show_hidden=False,
        ),
    )

    assert app._active_child_pane_cancel_event is None
    assert app._active_child_pane_request_id is None
    assert app._active_file_search_cancel_event is None
    assert app._active_file_search_request_id is None
    assert app._active_grep_search_cancel_event is grep_search_cancel
    assert app._active_grep_search_request_id == 4
    assert app._active_directory_size_cancel_event is directory_size_cancel
    assert app._active_directory_size_request_id == 5


def test_handle_worker_state_changed_clears_child_pane_tracking_and_dispatches_actions() -> None:
    app = _RecordingApp()
    cancel_event = threading.Event()
    effect = LoadChildPaneSnapshotEffect(
        request_id=3,
        current_path="/tmp/project",
        cursor_path="/tmp/project/docs",
    )
    pane = PaneState(
        directory_path="/tmp/project/docs",
        entries=(DirectoryEntryState("/tmp/project/docs/README.md", "README.md", "file"),),
    )
    app._pending_workers["child-pane-snapshot:3"] = effect
    app._active_child_pane_cancel_event = cancel_event
    app._active_child_pane_request_id = 3

    asyncio.run(
        handle_worker_state_changed(
            app,
            SimpleNamespace(
                worker=SimpleNamespace(
                    name="child-pane-snapshot:3",
                    result=pane,
                    error=None,
                ),
                state=WorkerState.SUCCESS,
            ),
        )
    )

    assert app._pending_workers == {}
    assert app._active_child_pane_cancel_event is None
    assert app._active_child_pane_request_id is None
    assert app.dispatched_actions == [
        (
            ChildPaneSnapshotLoaded(
                request_id=3,
                pane=pane,
            ),
        )
    ]


def test_handle_worker_state_changed_clears_matching_tracking_and_dispatches_actions() -> None:
    app = _RecordingApp()
    file_search_cancel = threading.Event()
    grep_search_cancel = threading.Event()
    effect = RunFileSearchEffect(
        request_id=3,
        root_path="/tmp/project",
        query="docs",
        show_hidden=False,
    )
    app._pending_workers["file-search:3"] = effect
    app._active_file_search_cancel_event = file_search_cancel
    app._active_file_search_request_id = 3
    app._active_grep_search_cancel_event = grep_search_cancel
    app._active_grep_search_request_id = 4

    asyncio.run(
        handle_worker_state_changed(
            app,
            SimpleNamespace(
                worker=SimpleNamespace(
                    name="file-search:3",
                    result=("README.md",),
                    error=None,
                ),
                state=WorkerState.SUCCESS,
            ),
        )
    )

    assert app._pending_workers == {}
    assert app._active_file_search_cancel_event is None
    assert app._active_file_search_request_id is None
    assert app._active_grep_search_cancel_event is grep_search_cancel
    assert app._active_grep_search_request_id == 4
    assert app.dispatched_actions == [
        (
            FileSearchCompleted(
                request_id=3,
                query="docs",
                results=("README.md",),
            ),
        )
    ]


def test_handle_worker_state_changed_cleans_up_cancelled_workers_without_dispatch() -> None:
    app = _RecordingApp()
    cancel_event = threading.Event()
    effect = RunGrepSearchEffect(
        request_id=9,
        root_path="/tmp/project",
        query="TODO",
        show_hidden=False,
    )
    app._pending_workers["grep-search:9"] = effect
    app._active_grep_search_cancel_event = cancel_event
    app._active_grep_search_request_id = 9

    asyncio.run(
        handle_worker_state_changed(
            app,
            SimpleNamespace(
                worker=SimpleNamespace(name="grep-search:9", result=None, error=None),
                state=WorkerState.CANCELLED,
            ),
        )
    )

    assert app._pending_workers == {}
    assert app._active_grep_search_cancel_event is None
    assert app._active_grep_search_request_id is None
    assert app.dispatched_actions == []


def test_run_foreground_external_launch_maps_suspend_failures() -> None:
    request = ExternalLaunchRequest(kind="open_editor", path="/tmp/project/README.md")
    app = _RecordingApp(suspend_error=SuspendNotSupported("suspend unavailable"))

    run_foreground_external_launch(
        app,
        RunExternalLaunchEffect(request_id=8, request=request),
    )

    assert app.refresh_calls == []
    assert _scheduled_actions(app) == (
        ExternalLaunchFailed(
            request_id=8,
            request=request,
            message="suspend unavailable",
        ),
    )


def test_run_foreground_external_launch_maps_os_errors_to_failure_actions() -> None:
    request = ExternalLaunchRequest(kind="open_editor", path="/tmp/project/README.md")
    app = _RecordingApp(
        _external_launch_service=_FailingExternalLaunchService("editor failed"),
    )

    run_foreground_external_launch(
        app,
        RunExternalLaunchEffect(request_id=8, request=request),
    )

    assert app.refresh_calls == [{"repaint": True, "layout": True}]
    assert _scheduled_actions(app) == (
        ExternalLaunchFailed(
            request_id=8,
            request=request,
            message="editor failed",
        ),
    )


def test_start_split_terminal_maps_start_failures() -> None:
    app = _RecordingApp(
        _split_terminal_service=_FailingSplitTerminalService("pty unavailable"),
    )

    start_split_terminal(
        app,
        StartSplitTerminalEffect(session_id=4, cwd="/tmp/project"),
    )

    assert app._split_terminal_session is None
    assert _scheduled_actions(app) == (
        SplitTerminalStartFailed(
            session_id=4,
            message="pty unavailable",
        ),
    )


def test_write_split_terminal_input_maps_write_failures() -> None:
    state = build_initial_app_state()
    app = _RecordingApp(
        _app_state=replace(
            state,
            split_terminal=replace(state.split_terminal, session_id=4),
        ),
        _split_terminal_session=_FailingSplitTerminalSession("write failed"),
    )

    write_split_terminal_input(
        app,
        WriteSplitTerminalInputEffect(session_id=4, data="ls"),
    )

    assert _scheduled_actions(app) == (
        SplitTerminalStartFailed(
            session_id=4,
            message="write failed",
        ),
    )
