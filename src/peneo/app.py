"""Application assembly for Peneo."""

import threading
from collections.abc import Sequence
from concurrent.futures import CancelledError as FutureCancelledError
from contextlib import nullcontext
from functools import partial
from pathlib import Path

from textual import events
from textual.app import App, ComposeResult, SuspendNotSupported
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.message import Message
from textual.timer import Timer
from textual.worker import Worker, WorkerState

from peneo.adapters import LocalExternalLaunchAdapter
from peneo.models import (
    AppConfig,
    FileMutationResult,
    PasteConflictPrompt,
    PasteExecutionResult,
    ThreePaneShellData,
)
from peneo.services import (
    BrowserSnapshotLoader,
    ClipboardOperationService,
    ConfigSaveService,
    ExternalLaunchService,
    FileMutationService,
    FileSearchService,
    InvalidFileSearchQueryError,
    LiveBrowserSnapshotLoader,
    LiveClipboardOperationService,
    LiveConfigSaveService,
    LiveExternalLaunchService,
    LiveFileMutationService,
    LiveFileSearchService,
    LiveSplitTerminalService,
    SplitTerminalService,
    SplitTerminalSession,
    resolve_config_path,
)
from peneo.state import (
    Action,
    AppState,
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
    Effect,
    ExitCurrentPath,
    ExternalLaunchCompleted,
    ExternalLaunchFailed,
    FileMutationCompleted,
    FileMutationFailed,
    FileSearchCompleted,
    FileSearchFailed,
    LoadBrowserSnapshotEffect,
    LoadChildPaneSnapshotEffect,
    NotificationState,
    ReduceResult,
    RequestBrowserSnapshot,
    RunClipboardPasteEffect,
    RunConfigSaveEffect,
    RunExternalLaunchEffect,
    RunFileMutationEffect,
    RunFileSearchEffect,
    SortState,
    SplitTerminalExited,
    SplitTerminalStarted,
    SplitTerminalStartFailed,
    StartSplitTerminalEffect,
    WriteSplitTerminalInputEffect,
    build_placeholder_app_state,
    dispatch_key_input,
    iter_bound_keys,
    reduce_app_state,
    select_shell_data,
)
from peneo.ui import (
    AttributeDialog,
    CommandPalette,
    ConfigDialog,
    ConflictDialog,
    CurrentPathBar,
    HelpBar,
    MainPane,
    SidePane,
    SplitTerminalPane,
    StatusBar,
)

_FILE_SEARCH_DEBOUNCE_SECONDS = 0.2


class PeneoApp(App[None]):
    """Three-pane shell with reducer-driven file operations."""

    class SplitTerminalOutput(Message):
        """Forward PTY output from background threads into the app loop."""

        def __init__(self, session_id: int, data: str) -> None:
            self.session_id = session_id
            self.data = data
            super().__init__()

    class SplitTerminalExitedMessage(Message):
        """Forward PTY exit notifications into the app loop."""

        def __init__(self, session_id: int, exit_code: int | None) -> None:
            self.session_id = session_id
            self.exit_code = exit_code
            super().__init__()

    TITLE = "Peneo"
    SUB_TITLE = "Three-pane shell"
    BINDINGS = [
        Binding(key, f"dispatch_bound_key('{key}')", show=False, priority=True)
        for key in iter_bound_keys()
    ]
    CSS = """
    Screen {
        layout: vertical;
    }

    #body {
        height: 1fr;
        layout: vertical;
    }

    #browser-row {
        height: 1fr;
        layout: horizontal;
    }

    .pane {
        height: 1fr;
        min-width: 24;
        border: round $surface;
        background: $boost;
    }

    .side-pane {
        width: 1fr;
    }

    .main-pane {
        width: 2fr;
        min-width: 40;
    }

    .pane-title {
        height: 1;
        padding: 0 1;
        background: $surface;
        color: $text-muted;
        text-style: bold;
    }

    .pane-list,
    .pane-table {
        height: 1fr;
    }

    .pane-entry {
        padding: 0 1;
    }

    .pane-summary {
        height: 1;
        padding: 0 1;
        background: $surface;
        color: $text;
    }

    #current-path-bar,
    #status-bar {
        height: 1;
        padding: 0 1;
    }

    #help-bar {
        height: auto;
        min-height: 1;
        padding: 0 1;
    }

    #current-path-bar {
        background: $boost;
        color: $text;
        text-style: bold;
    }

    #help-bar {
        background: $panel;
        color: $text-muted;
    }

    #command-palette {
        display: none;
        height: auto;
        min-height: 4;
        max-height: 13;
        margin: 0 2;
        padding: 0 1;
        border: round $accent;
        background: $surface;
    }

    #command-palette-title {
        color: $accent;
        text-style: bold;
    }

    #command-palette-query {
        margin: 0 0 1 0;
    }

    #status-bar {
        background: $surface;
        color: $text;
    }

    .pane-context-input {
        height: 1;
        padding: 0 1;
        background: $panel;
        color: $text;
        text-style: bold;
    }

    #conflict-dialog {
        display: none;
        height: auto;
        min-height: 6;
        margin: 0 2;
        padding: 1 2;
        border: round $warning;
        background: $surface;
    }

    #conflict-dialog-title {
        text-style: bold;
        color: $warning;
    }

    #conflict-dialog-message {
        margin: 0 0 1 0;
    }

    #conflict-dialog-options {
        padding: 0 1;
        background: $boost;
        color: $warning;
        text-style: bold;
    }

    #attribute-dialog {
        display: none;
        height: auto;
        min-height: 8;
        margin: 0 2;
        padding: 1 2;
        border: round $accent;
        background: $surface;
    }

    #attribute-dialog-title {
        text-style: bold;
        color: $accent;
    }

    #attribute-dialog-lines {
        margin: 0 0 1 0;
    }

    #attribute-dialog-options {
        padding: 0 1;
        background: $boost;
        color: $accent;
        text-style: bold;
    }

    #config-dialog {
        display: none;
        height: auto;
        min-height: 10;
        margin: 0 2;
        padding: 1 2;
        border: round $accent;
        background: $surface;
    }

    #config-dialog-title {
        text-style: bold;
        color: $accent;
    }

    #config-dialog-lines {
        margin: 0 0 1 0;
    }

    #config-dialog-options {
        padding: 0 1;
        background: $boost;
        color: $accent;
        text-style: bold;
    }

    #split-terminal {
        display: none;
        height: 1fr;
        min-height: 6;
        border: round $accent;
        background: $surface;
    }

    #split-terminal.-visible {
        display: block;
    }

    #split-terminal.-focused {
        border: round $success;
    }
    """

    def __init__(
        self,
        snapshot_loader: BrowserSnapshotLoader | None = None,
        clipboard_service: ClipboardOperationService | None = None,
        config_save_service: ConfigSaveService | None = None,
        file_mutation_service: FileMutationService | None = None,
        external_launch_service: ExternalLaunchService | None = None,
        file_search_service: FileSearchService | None = None,
        split_terminal_service: SplitTerminalService | None = None,
        *,
        app_config: AppConfig | None = None,
        config_path: str | None = None,
        startup_notification: NotificationState | None = None,
        initial_path: str | Path | None = None,
    ) -> None:
        super().__init__()
        self._app_config = app_config or AppConfig()
        self.theme = self._app_config.display.theme
        self._initial_path = str(Path(initial_path or Path.cwd()).expanduser().resolve())
        self._app_state: AppState = build_placeholder_app_state(
            self._initial_path,
            config=self._app_config,
            config_path=config_path or str(resolve_config_path()),
            show_hidden=self._app_config.display.show_hidden_files,
            sort=_initial_sort_state(self._app_config),
            confirm_delete=self._app_config.behavior.confirm_delete,
            paste_conflict_action=self._app_config.behavior.paste_conflict_action,
            post_reload_notification=startup_notification,
        )
        self._snapshot_loader = snapshot_loader or LiveBrowserSnapshotLoader()
        self._clipboard_service = clipboard_service or LiveClipboardOperationService()
        self._config_save_service = config_save_service or LiveConfigSaveService()
        self._file_mutation_service = file_mutation_service or LiveFileMutationService()
        self._uses_live_external_launch_service = external_launch_service is None
        self._external_launch_service = (
            external_launch_service or self._build_external_launch_service(self._app_config)
        )
        self._file_search_service = file_search_service or LiveFileSearchService()
        self._split_terminal_service = split_terminal_service or LiveSplitTerminalService()
        self._pending_workers: dict[str, Effect] = {}
        self._split_terminal_session: SplitTerminalSession | None = None
        self._file_search_timer: Timer | None = None
        self._active_file_search_cancel_event: threading.Event | None = None
        self._active_file_search_request_id: int | None = None

    @property
    def app_state(self) -> AppState:
        """Expose the reducer-managed state for tests and integrations."""

        return self._app_state

    def compose(self) -> ComposeResult:
        shell = select_shell_data(self._app_state)
        yield CurrentPathBar(shell.current_path, id="current-path-bar")
        yield self._build_body(shell)
        yield CommandPalette(shell.command_palette, id="command-palette")
        yield ConflictDialog(shell.conflict_dialog, id="conflict-dialog")
        yield AttributeDialog(shell.attribute_dialog, id="attribute-dialog")
        yield ConfigDialog(shell.config_dialog, id="config-dialog")
        yield HelpBar(shell.help, id="help-bar")
        yield StatusBar(shell.status, id="status-bar")

    async def on_mount(self) -> None:
        """Load the initial directory snapshot after the UI mounts."""

        await self.dispatch_actions((RequestBrowserSnapshot(self._initial_path, blocking=True),))

    def on_unmount(self) -> None:
        """Ensure the embedded terminal session is stopped when the app exits."""

        self._cancel_pending_file_search()
        if self._split_terminal_session is None:
            return
        self._split_terminal_session.close()
        self._split_terminal_session = None

    async def on_key(self, event: events.Key) -> None:
        """Normalize keyboard input into reducer actions."""

        handled = await self._dispatch_key_press(event.key, character=event.character)
        if handled:
            event.stop()
            event.prevent_default()

    async def action_dispatch_bound_key(self, key: str) -> None:
        """Handle priority key bindings through the central dispatcher."""

        character = None
        if self._app_state.ui_mode in {"FILTER", "RENAME", "CREATE", "PALETTE"} or (
            self._app_state.ui_mode == "BROWSING"
            and self._app_state.split_terminal.visible
            and self._app_state.split_terminal.focus_target == "terminal"
        ):
            if key == "space":
                if self._app_state.ui_mode in {"RENAME", "CREATE", "PALETTE"} or (
                    self._app_state.ui_mode == "BROWSING"
                    and self._app_state.split_terminal.focus_target == "terminal"
                ):
                    character = " "
            elif len(key) == 1 and key.isprintable():
                character = key
        await self._dispatch_key_press(key, character=character)

    def _build_body(self, shell: ThreePaneShellData) -> Vertical:
        return Vertical(
            Horizontal(
                SidePane(
                    "Parent Directory",
                    shell.parent_entries,
                    id="parent-pane",
                    classes="pane side-pane",
                ),
                MainPane(
                    "Current Directory",
                    shell.current_entries,
                    summary=shell.current_summary,
                    cursor_index=shell.current_cursor_index,
                    context_input=shell.current_context_input,
                    id="current-pane",
                    classes="pane main-pane",
                ),
                SidePane(
                    "Child Directory",
                    shell.child_entries,
                    id="child-pane",
                    classes="pane side-pane",
                ),
                id="browser-row",
            ),
            SplitTerminalPane(shell.split_terminal, id="split-terminal"),
            id="body",
        )

    async def _dispatch_key_press(
        self,
        key: str,
        *,
        character: str | None = None,
    ) -> bool:
        actions = dispatch_key_input(
            self._app_state,
            key=key,
            character=character,
        )
        if not actions:
            return False
        await self.dispatch_actions(actions)
        return True

    async def dispatch_actions(self, actions: Sequence[Action]) -> None:
        """Apply reducer actions, refresh the UI, and schedule any effects."""

        previous_state = self._app_state
        changed, effects = self._apply_actions(actions)
        self._sync_file_search_state(previous_state, self._app_state)
        if previous_state.config.display.theme != self._app_state.config.display.theme:
            self.theme = self._app_state.config.display.theme
        if previous_state.config != self._app_state.config:
            self._sync_external_launch_service()
        if changed:
            await self._refresh_shell()
        self._schedule_effects(effects)

    def _build_external_launch_service(self, app_config: AppConfig) -> LiveExternalLaunchService:
        return LiveExternalLaunchService(
            adapter=LocalExternalLaunchAdapter(
                terminal_command_templates=app_config.terminal,
                editor_command_template=app_config.editor,
            )
        )

    def _sync_external_launch_service(self) -> None:
        if not self._uses_live_external_launch_service:
            return
        self._external_launch_service = self._build_external_launch_service(self._app_state.config)

    def _apply_actions(self, actions: Sequence[Action]) -> tuple[bool, tuple[Effect, ...]]:
        state = self._app_state
        changed = False
        effects: list[Effect] = []

        for action in actions:
            if isinstance(action, ExitCurrentPath):
                self.exit(result=state.current_path, return_code=action.return_code)
                continue
            result: ReduceResult = reduce_app_state(state, action)
            next_state = result.state
            if next_state != state:
                changed = True
            state = next_state
            effects.extend(result.effects)

        self._app_state = state
        return changed, tuple(effects)

    def _schedule_effects(self, effects: Sequence[Effect]) -> None:
        for effect in effects:
            if isinstance(effect, LoadBrowserSnapshotEffect):
                self._schedule_browser_snapshot(effect)
            elif isinstance(effect, LoadChildPaneSnapshotEffect):
                self._schedule_child_pane_snapshot(effect)
            elif isinstance(effect, RunClipboardPasteEffect):
                self._schedule_clipboard_paste(effect)
            elif isinstance(effect, RunConfigSaveEffect):
                self._schedule_config_save(effect)
            elif isinstance(effect, RunFileMutationEffect):
                self._schedule_file_mutation(effect)
            elif isinstance(effect, RunExternalLaunchEffect):
                if effect.request.kind == "copy_paths":
                    self._schedule_system_clipboard_copy(effect)
                elif effect.request.kind == "open_editor":
                    self.call_next(self._run_foreground_external_launch, effect)
                else:
                    self._schedule_external_launch(effect)
            elif isinstance(effect, RunFileSearchEffect):
                self._schedule_file_search(effect)
            elif isinstance(effect, StartSplitTerminalEffect):
                self._start_split_terminal(effect)
            elif isinstance(effect, WriteSplitTerminalInputEffect):
                self._write_split_terminal_input(effect)
            elif isinstance(effect, CloseSplitTerminalEffect):
                self._close_split_terminal(effect)

    def _schedule_browser_snapshot(self, effect: LoadBrowserSnapshotEffect) -> None:
        worker = self.run_worker(
            partial(
                self._snapshot_loader.load_browser_snapshot,
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
        self._pending_workers[worker.name] = effect

    def _schedule_child_pane_snapshot(self, effect: LoadChildPaneSnapshotEffect) -> None:
        worker = self.run_worker(
            partial(
                self._snapshot_loader.load_child_pane_snapshot,
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
        self._pending_workers[worker.name] = effect

    def _schedule_clipboard_paste(self, effect: RunClipboardPasteEffect) -> None:
        worker = self.run_worker(
            partial(self._clipboard_service.execute_paste, effect.request),
            name=f"clipboard-paste:{effect.request_id}",
            group="clipboard-paste",
            description=effect.request.destination_dir,
            exit_on_error=False,
            exclusive=True,
            thread=True,
        )
        self._pending_workers[worker.name] = effect

    def _schedule_config_save(self, effect: RunConfigSaveEffect) -> None:
        worker = self.run_worker(
            partial(
                self._config_save_service.save,
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
        self._pending_workers[worker.name] = effect

    def _schedule_file_mutation(self, effect: RunFileMutationEffect) -> None:
        worker = self.run_worker(
            partial(self._file_mutation_service.execute, effect.request),
            name=f"file-mutation:{effect.request_id}",
            group="file-mutation",
            description=str(effect.request),
            exit_on_error=False,
            exclusive=True,
            thread=True,
        )
        self._pending_workers[worker.name] = effect

    def _schedule_external_launch(self, effect: RunExternalLaunchEffect) -> None:
        worker = self.run_worker(
            partial(self._external_launch_service.execute, effect.request),
            name=f"external-launch:{effect.request_id}",
            group="external-launch",
            description=str(effect.request),
            exit_on_error=False,
            thread=True,
        )
        self._pending_workers[worker.name] = effect

    def _schedule_file_search(self, effect: RunFileSearchEffect) -> None:
        self._cancel_file_search_timer()
        self._file_search_timer = self.set_timer(
            _FILE_SEARCH_DEBOUNCE_SECONDS,
            partial(self._start_file_search_worker, effect),
            name=f"file-search-debounce:{effect.request_id}",
        )

    def _start_file_search_worker(self, effect: RunFileSearchEffect) -> None:
        self._file_search_timer = None
        if self._app_state.pending_file_search_request_id != effect.request_id:
            return
        cancel_event = threading.Event()
        self._active_file_search_cancel_event = cancel_event
        self._active_file_search_request_id = effect.request_id
        worker = self.run_worker(
            partial(
                self._file_search_service.search,
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
        self._pending_workers[worker.name] = effect

    def _sync_file_search_state(self, previous_state: AppState, next_state: AppState) -> None:
        if (
            previous_state.pending_file_search_request_id
            == next_state.pending_file_search_request_id
        ):
            return
        self._cancel_pending_file_search()

    def _cancel_pending_file_search(self) -> None:
        self._cancel_file_search_timer()
        self._cancel_active_file_search()

    def _cancel_file_search_timer(self) -> None:
        if self._file_search_timer is None:
            return
        self._file_search_timer.stop()
        self._file_search_timer = None

    def _cancel_active_file_search(self) -> None:
        if self._active_file_search_cancel_event is None:
            return
        self._active_file_search_cancel_event.set()
        self._active_file_search_cancel_event = None
        self._active_file_search_request_id = None

    def _start_split_terminal(self, effect: StartSplitTerminalEffect) -> None:
        try:
            session = self._split_terminal_service.start(
                effect.cwd,
                on_output=partial(self._handle_split_terminal_output, effect.session_id),
                on_exit=partial(self._handle_split_terminal_exit, effect.session_id),
            )
        except OSError as error:
            self.call_next(
                self.dispatch_actions,
                (
                    SplitTerminalStartFailed(
                        session_id=effect.session_id,
                        message=str(error) or "Failed to open split terminal",
                    ),
                ),
            )
            return

        self._split_terminal_session = session
        self.call_next(
            self.dispatch_actions,
            (
                SplitTerminalStarted(session_id=effect.session_id, cwd=effect.cwd),
            ),
        )

    def _write_split_terminal_input(self, effect: WriteSplitTerminalInputEffect) -> None:
        if self._app_state.split_terminal.session_id != effect.session_id:
            return
        if self._split_terminal_session is None:
            return
        try:
            self._split_terminal_session.write(effect.data)
        except OSError as error:
            self.call_next(
                self.dispatch_actions,
                (
                    SplitTerminalStartFailed(
                        session_id=effect.session_id,
                        message=str(error) or "Failed to write to split terminal",
                    ),
                ),
            )

    def _close_split_terminal(self, effect: CloseSplitTerminalEffect) -> None:
        if self._split_terminal_session is None:
            return
        try:
            self._split_terminal_session.close()
        finally:
            self._split_terminal_session = None

    def _schedule_system_clipboard_copy(self, effect: RunExternalLaunchEffect) -> None:
        try:
            self.copy_to_clipboard("\n".join(effect.request.paths))
        except Exception as error:  # pragma: no cover
            self.call_next(
                self.dispatch_actions,
                (
                    ExternalLaunchFailed(
                        request_id=effect.request_id,
                        request=effect.request,
                        message=str(error) or "Failed to copy to system clipboard",
                    ),
                ),
            )
            return

        self.call_next(
            self.dispatch_actions,
            (
                ExternalLaunchCompleted(
                    request_id=effect.request_id,
                    request=effect.request,
                ),
            ),
        )

    def _run_foreground_external_launch(self, effect: RunExternalLaunchEffect) -> None:
        suspend_context = nullcontext()
        try:
            suspend_context = self.suspend()
        except SuspendNotSupported as error:
            self.call_next(
                self.dispatch_actions,
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
                self._external_launch_service.execute(effect.request)
        except OSError as error:
            self.refresh(repaint=True, layout=True)
            self.call_next(
                self.dispatch_actions,
                (
                    ExternalLaunchFailed(
                        request_id=effect.request_id,
                        request=effect.request,
                        message=str(error) or "Operation failed",
                    ),
                ),
            )
            return

        self.refresh(repaint=True, layout=True)
        self.call_next(
            self.dispatch_actions,
            (
                ExternalLaunchCompleted(
                    request_id=effect.request_id,
                    request=effect.request,
                ),
            ),
        )

    def _handle_split_terminal_output(self, session_id: int, data: str) -> None:
        message = self.SplitTerminalOutput(session_id=session_id, data=data)
        try:
            if self._thread_id == threading.get_ident():
                self.post_message(message)
                return
            self.call_from_thread(self.post_message, message)
        except (RuntimeError, FutureCancelledError):
            return

    def _handle_split_terminal_exit(self, session_id: int, exit_code: int | None) -> None:
        message = self.SplitTerminalExitedMessage(session_id=session_id, exit_code=exit_code)
        try:
            if self._thread_id == threading.get_ident():
                self.post_message(message)
                return
            self.call_from_thread(self.post_message, message)
        except (RuntimeError, FutureCancelledError):
            return

    async def on_peneo_app_split_terminal_output(
        self,
        message: SplitTerminalOutput,
    ) -> None:
        split_terminal_state = self._app_state.split_terminal
        if (
            not split_terminal_state.visible
            or split_terminal_state.session_id != message.session_id
        ):
            return
        try:
            split_terminal = self.query_one("#split-terminal", SplitTerminalPane)
        except NoMatches:
            return
        split_terminal.append_output(message.data)

    async def on_peneo_app_split_terminal_exited_message(
        self,
        message: SplitTerminalExitedMessage,
    ) -> None:
        self._split_terminal_session = None
        await self.dispatch_actions(
            (
                SplitTerminalExited(
                    session_id=message.session_id,
                    exit_code=message.exit_code,
                ),
            )
        )

    async def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Convert worker completion back into reducer actions."""

        effect = self._pending_workers.get(event.worker.name)
        if effect is None:
            return

        if event.state in {WorkerState.PENDING, WorkerState.RUNNING}:
            return

        self._pending_workers.pop(event.worker.name, None)
        if (
            isinstance(effect, RunFileSearchEffect)
            and effect.request_id == self._active_file_search_request_id
        ):
            self._active_file_search_cancel_event = None
            self._active_file_search_request_id = None

        if event.state == WorkerState.CANCELLED:
            return

        if event.state == WorkerState.SUCCESS:
            if isinstance(effect, LoadBrowserSnapshotEffect):
                await self.dispatch_actions(
                    (
                        BrowserSnapshotLoaded(
                            request_id=effect.request_id,
                            snapshot=event.worker.result,
                            blocking=effect.blocking,
                        ),
                    )
                )
                return

            if isinstance(effect, LoadChildPaneSnapshotEffect):
                await self.dispatch_actions(
                    (
                        ChildPaneSnapshotLoaded(
                            request_id=effect.request_id,
                            pane=event.worker.result,
                        ),
                    )
                )
                return

            result = event.worker.result
            if isinstance(result, PasteConflictPrompt):
                await self.dispatch_actions(
                    (
                        ClipboardPasteNeedsResolution(
                            request_id=effect.request_id,
                            request=result.request,
                            conflicts=result.conflicts,
                        ),
                    )
                )
                return

            if isinstance(result, PasteExecutionResult):
                await self.dispatch_actions(
                    (
                        ClipboardPasteCompleted(
                            request_id=effect.request_id,
                            summary=result.summary,
                        ),
                    )
                )
                return

            if isinstance(result, FileMutationResult):
                await self.dispatch_actions(
                    (
                        FileMutationCompleted(
                            request_id=effect.request_id,
                            result=result,
                        ),
                    )
                )
                return

            if isinstance(effect, RunConfigSaveEffect):
                await self.dispatch_actions(
                    (
                        ConfigSaveCompleted(
                            request_id=effect.request_id,
                            path=event.worker.result,
                            config=effect.config,
                        ),
                    )
                )
                return

            if isinstance(effect, RunExternalLaunchEffect):
                await self.dispatch_actions(
                    (
                        ExternalLaunchCompleted(
                            request_id=effect.request_id,
                            request=effect.request,
                        ),
                    )
                )
                return

            if isinstance(effect, RunFileSearchEffect):
                await self.dispatch_actions(
                    (
                        FileSearchCompleted(
                            request_id=effect.request_id,
                            query=effect.query,
                            results=event.worker.result,
                        ),
                    )
                )
                return

        message = str(event.worker.error) or "Operation failed"
        if isinstance(effect, LoadBrowserSnapshotEffect):
            await self.dispatch_actions(
                (
                    BrowserSnapshotFailed(
                        request_id=effect.request_id,
                        message=message,
                        blocking=effect.blocking,
                    ),
                )
            )
            return

        if isinstance(effect, LoadChildPaneSnapshotEffect):
            await self.dispatch_actions(
                (
                    ChildPaneSnapshotFailed(
                        request_id=effect.request_id,
                        message=message,
                    ),
                )
            )
            return

        if isinstance(effect, RunFileMutationEffect):
            await self.dispatch_actions(
                (
                    FileMutationFailed(
                        request_id=effect.request_id,
                        message=message,
                    ),
                )
            )
            return

        if isinstance(effect, RunConfigSaveEffect):
            await self.dispatch_actions(
                (
                    ConfigSaveFailed(
                        request_id=effect.request_id,
                        message=message,
                    ),
                )
            )
            return

        if isinstance(effect, RunExternalLaunchEffect):
            await self.dispatch_actions(
                (
                    ExternalLaunchFailed(
                        request_id=effect.request_id,
                        request=effect.request,
                        message=message,
                    ),
                )
            )
            return

        if isinstance(effect, RunFileSearchEffect):
            invalid_query = isinstance(event.worker.error, InvalidFileSearchQueryError)
            await self.dispatch_actions(
                (
                    FileSearchFailed(
                        request_id=effect.request_id,
                        query=effect.query,
                        message=message,
                        invalid_query=invalid_query,
                    ),
                )
            )
            return

        await self.dispatch_actions(
            (
                ClipboardPasteFailed(
                    request_id=effect.request_id,
                    message=message,
                ),
            )
        )

    async def on_resize(self, event: events.Resize) -> None:
        """Keep the split-terminal PTY dimensions roughly aligned with the viewport."""

        if self._split_terminal_session is None or not self._app_state.split_terminal.visible:
            return
        self.call_after_refresh(self._resize_split_terminal_session)

    async def _refresh_shell(self) -> None:
        shell = select_shell_data(self._app_state)
        try:
            current_path_bar = self.query_one("#current-path-bar", CurrentPathBar)
            parent_pane = self.query_one("#parent-pane", SidePane)
            current_pane = self.query_one("#current-pane", MainPane)
            child_pane = self.query_one("#child-pane", SidePane)
            split_terminal = self.query_one("#split-terminal", SplitTerminalPane)
            command_palette = self.query_one("#command-palette", CommandPalette)
            help_bar = self.query_one("#help-bar", HelpBar)
            status_bar = self.query_one("#status-bar", StatusBar)
            conflict_dialog = self.query_one("#conflict-dialog", ConflictDialog)
            attribute_dialog = self.query_one("#attribute-dialog", AttributeDialog)
            config_dialog = self.query_one("#config-dialog", ConfigDialog)
        except NoMatches:
            selectors = (
                "#current-path-bar",
                "#body",
                "#split-terminal",
                "#command-palette",
                "#help-bar",
                "#status-bar",
                "#conflict-dialog",
                "#attribute-dialog",
                "#config-dialog",
            )
            for selector in selectors:
                try:
                    await self.query_one(selector).remove()
                except NoMatches:
                    pass
            await self.mount(CurrentPathBar(shell.current_path, id="current-path-bar"))
            await self.mount(self._build_body(shell))
            await self.mount(CommandPalette(shell.command_palette, id="command-palette"))
            await self.mount(HelpBar(shell.help, id="help-bar"))
            await self.mount(StatusBar(shell.status, id="status-bar"))
            await self.mount(ConflictDialog(shell.conflict_dialog, id="conflict-dialog"))
            await self.mount(AttributeDialog(shell.attribute_dialog, id="attribute-dialog"))
            await self.mount(ConfigDialog(shell.config_dialog, id="config-dialog"))
            return

        current_path_bar.set_path(shell.current_path)
        await parent_pane.set_entries(shell.parent_entries)
        current_pane.set_summary(shell.current_summary)
        current_pane.set_entries(shell.current_entries, shell.current_cursor_index)
        current_pane.set_context_input(shell.current_context_input)
        await child_pane.set_entries(shell.child_entries)
        split_terminal.set_state(shell.split_terminal)
        self._resize_split_terminal_session()
        command_palette.set_state(shell.command_palette)
        help_bar.set_state(shell.help)
        status_bar.set_state(shell.status)
        conflict_dialog.set_state(shell.conflict_dialog)
        attribute_dialog.set_state(shell.attribute_dialog)
        config_dialog.set_state(shell.config_dialog)

        if (
            self._app_state.ui_mode == "BROWSING"
            and self._app_state.split_terminal.visible
            and self._app_state.split_terminal.focus_target == "terminal"
        ):
            self.set_focus(split_terminal)
        else:
            try:
                self.set_focus(current_pane.query_one("#current-pane-table"))
            except NoMatches:
                pass

    def _resize_split_terminal_session(self) -> None:
        if self._split_terminal_session is None or not self._app_state.split_terminal.visible:
            return
        try:
            split_terminal = self.query_one("#split-terminal", SplitTerminalPane)
        except NoMatches:
            return
        columns, rows = split_terminal.terminal_dimensions()
        self._split_terminal_session.resize(columns=columns, rows=rows)


def create_app(
    snapshot_loader: BrowserSnapshotLoader | None = None,
    clipboard_service: ClipboardOperationService | None = None,
    config_save_service: ConfigSaveService | None = None,
    file_mutation_service: FileMutationService | None = None,
    external_launch_service: ExternalLaunchService | None = None,
    file_search_service: FileSearchService | None = None,
    split_terminal_service: SplitTerminalService | None = None,
    *,
    app_config: AppConfig | None = None,
    config_path: str | None = None,
    startup_notification: NotificationState | None = None,
    initial_path: str | Path | None = None,
) -> PeneoApp:
    """Create the application instance."""

    return PeneoApp(
        snapshot_loader=snapshot_loader,
        clipboard_service=clipboard_service,
        config_save_service=config_save_service,
        file_mutation_service=file_mutation_service,
        external_launch_service=external_launch_service,
        file_search_service=file_search_service,
        split_terminal_service=split_terminal_service,
        app_config=app_config,
        config_path=config_path,
        startup_notification=startup_notification,
        initial_path=initial_path,
    )


def _initial_sort_state(config: AppConfig) -> SortState:
    return SortState(
        field=config.display.default_sort_field,
        descending=config.display.default_sort_descending,
        directories_first=config.display.directories_first,
    )
