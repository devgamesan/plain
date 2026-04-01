import threading
from contextlib import nullcontext
from dataclasses import dataclass, field, replace
from types import SimpleNamespace
from typing import Any

from textual.app import SuspendNotSupported

from peneo.app_runtime import (
    cancel_pending_directory_size,
    cancel_pending_file_search,
    cancel_pending_grep_search,
    clear_effect_tracking,
    complete_worker_actions,
    failed_worker_actions,
    run_foreground_external_launch,
    start_file_search_worker,
    start_grep_search_worker,
    start_split_terminal,
    write_split_terminal_input,
)
from peneo.models import AppConfig, ExternalLaunchRequest
from peneo.services import InvalidFileSearchQueryError
from peneo.state import (
    BrowserSnapshot,
    BrowserSnapshotLoaded,
    ConfigSaveCompleted,
    DirectoryEntryState,
    DirectorySizesLoaded,
    ExternalLaunchFailed,
    FileSearchFailed,
    LoadBrowserSnapshotEffect,
    PaneState,
    RunConfigSaveEffect,
    RunDirectorySizeEffect,
    RunExternalLaunchEffect,
    RunFileSearchEffect,
    RunGrepSearchEffect,
    SplitTerminalStartFailed,
    StartSplitTerminalEffect,
    WriteSplitTerminalInputEffect,
    build_initial_app_state,
)


@dataclass
class _RecordingApp:
    _app_state: Any = field(default_factory=build_initial_app_state)
    _pending_workers: dict[str, object] = field(default_factory=dict)
    _file_search_timer: Any = None
    _grep_search_timer: Any = None
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
    _split_terminal_session: Any = None
    suspend_error: BaseException | None = None
    run_worker_calls: list[dict[str, Any]] = field(default_factory=list)
    call_next_calls: list[tuple[Any, tuple[Any, ...]]] = field(default_factory=list)
    refresh_calls: list[dict[str, Any]] = field(default_factory=list)

    def run_worker(self, worker_fn: Any, **kwargs: Any) -> Any:
        self.run_worker_calls.append(kwargs)
        return SimpleNamespace(name=kwargs["name"])

    def call_next(self, callback: Any, *args: Any) -> None:
        self.call_next_calls.append((callback, args))

    def dispatch_actions(self, actions: tuple[Any, ...]) -> None:
        return None

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


def test_cancel_pending_runtime_helpers_clear_active_tracking() -> None:
    app = _RecordingApp()
    file_search_cancel = threading.Event()
    grep_search_cancel = threading.Event()
    directory_size_cancel = threading.Event()
    app._active_file_search_cancel_event = file_search_cancel
    app._active_file_search_request_id = 3
    app._active_grep_search_cancel_event = grep_search_cancel
    app._active_grep_search_request_id = 4
    app._active_directory_size_cancel_event = directory_size_cancel
    app._active_directory_size_request_id = 5

    cancel_pending_file_search(app)
    cancel_pending_grep_search(app)
    cancel_pending_directory_size(app)

    assert file_search_cancel.is_set()
    assert app._active_file_search_cancel_event is None
    assert app._active_file_search_request_id is None
    assert grep_search_cancel.is_set()
    assert app._active_grep_search_cancel_event is None
    assert app._active_grep_search_request_id is None
    assert directory_size_cancel.is_set()
    assert app._active_directory_size_cancel_event is None
    assert app._active_directory_size_request_id is None


def test_clear_effect_tracking_only_clears_matching_request() -> None:
    app = _RecordingApp()
    file_search_cancel = threading.Event()
    grep_search_cancel = threading.Event()
    directory_size_cancel = threading.Event()
    app._active_file_search_cancel_event = file_search_cancel
    app._active_file_search_request_id = 3
    app._active_grep_search_cancel_event = grep_search_cancel
    app._active_grep_search_request_id = 4
    app._active_directory_size_cancel_event = directory_size_cancel
    app._active_directory_size_request_id = 5

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

    assert app._active_file_search_cancel_event is None
    assert app._active_file_search_request_id is None
    assert app._active_grep_search_cancel_event is grep_search_cancel
    assert app._active_grep_search_request_id == 4
    assert app._active_directory_size_cancel_event is directory_size_cancel
    assert app._active_directory_size_request_id == 5


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
