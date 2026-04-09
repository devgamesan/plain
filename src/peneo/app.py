"""Application assembly for Peneo."""

import threading
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.css.query import NoMatches
from textual.message import Message
from textual.timer import Timer
from textual.worker import Worker

from peneo.adapters import LocalExternalLaunchAdapter
from peneo.app_runtime import (
    cancel_pending_runtime_work,
    handle_worker_state_changed,
    schedule_effects,
    sync_runtime_state,
)
from peneo.app_shell import build_body, refresh_shell, resize_split_terminal_session
from peneo.models import (
    AppConfig,
    ThreePaneShellData,
)
from peneo.services import (
    ArchiveExtractService,
    BrowserSnapshotLoader,
    ClipboardOperationService,
    ConfigSaveService,
    DirectorySizeService,
    ExternalLaunchService,
    FileMutationService,
    FileSearchService,
    GrepSearchService,
    LiveArchiveExtractService,
    LiveBrowserSnapshotLoader,
    LiveClipboardOperationService,
    LiveConfigSaveService,
    LiveDirectorySizeService,
    LiveExternalLaunchService,
    LiveFileMutationService,
    LiveFileSearchService,
    LiveGrepSearchService,
    LiveShellCommandService,
    LiveSplitTerminalService,
    LiveZipCompressService,
    ShellCommandService,
    SplitTerminalService,
    SplitTerminalSession,
    ZipCompressService,
    resolve_config_path,
)
from peneo.state import (
    Action,
    AppState,
    Effect,
    ExitCurrentPath,
    NotificationState,
    ReduceResult,
    RequestBrowserSnapshot,
    SetTerminalHeight,
    SortState,
    SplitTerminalExited,
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
    ShellCommandDialog,
    SplitTerminalPane,
    StatusBar,
)


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
        min-width: 20;
        border: round $surface;
        background: $boost;
    }

    .side-pane {
        width: 0.9fr;
    }

    .main-pane {
        width: 2.2fr;
        min-width: 44;
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

    .pane-table {
        scrollbar-size: 0 0;
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
        min-height: 8;
        max-height: 1fr;
        margin: 0 2;
        padding: 0 1;
        border: round $accent;
        background: $surface;
    }

    #command-palette.-expanded {
        height: 1fr;
    }

    #command-palette-title {
        color: $accent;
        text-style: bold;
    }

    #command-palette-query {
        margin: 0 0 1 0;
    }

    #command-palette-items {
        height: auto;
        max-height: 1fr;
    }

    #command-palette.-expanded #command-palette-items {
        height: 1fr;
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

    .overlay-layer {
        display: none;
        overlay: screen;
        position: absolute;
        offset: 0 0;
        width: 1fr;
        height: 1fr;
    }

    #command-palette-layer {
        align-horizontal: center;
    }

    .dialog-layer {
        align: center middle;
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

    #shell-command-dialog {
        display: none;
        height: auto;
        min-height: 8;
        margin: 0 2;
        padding: 1 2;
        border: round $accent;
        background: $surface;
    }

    #shell-command-dialog-title {
        text-style: bold;
        color: $accent;
    }

    #shell-command-dialog-cwd {
        color: $text-muted;
    }

    #shell-command-dialog-input {
        margin: 1 0;
    }

    #shell-command-dialog-options {
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
        directory_size_service: DirectorySizeService | None = None,
        file_mutation_service: FileMutationService | None = None,
        archive_extract_service: ArchiveExtractService | None = None,
        zip_compress_service: ZipCompressService | None = None,
        external_launch_service: ExternalLaunchService | None = None,
        file_search_service: FileSearchService | None = None,
        grep_search_service: GrepSearchService | None = None,
        shell_command_service: ShellCommandService | None = None,
        split_terminal_service: SplitTerminalService | None = None,
        *,
        app_config: AppConfig | None = None,
        config_path: str | None = None,
        startup_notification: NotificationState | None = None,
        initial_path: str | Path | None = None,
        current_pane_projection_mode: Literal["full", "viewport"] = "viewport",
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
            show_help_bar=self._app_config.display.show_help_bar,
            sort=_initial_sort_state(self._app_config),
            confirm_delete=self._app_config.behavior.confirm_delete,
            paste_conflict_action=self._app_config.behavior.paste_conflict_action,
            post_reload_notification=startup_notification,
            current_pane_projection_mode=current_pane_projection_mode,
        )
        self._snapshot_loader = snapshot_loader or LiveBrowserSnapshotLoader()
        self._clipboard_service = clipboard_service or LiveClipboardOperationService()
        self._config_save_service = config_save_service or LiveConfigSaveService()
        self._directory_size_service = directory_size_service or LiveDirectorySizeService()
        self._file_mutation_service = file_mutation_service or LiveFileMutationService()
        self._archive_extract_service = archive_extract_service or LiveArchiveExtractService()
        self._zip_compress_service = zip_compress_service or LiveZipCompressService()
        self._uses_live_external_launch_service = external_launch_service is None
        self._external_launch_service = (
            external_launch_service or self._build_external_launch_service(self._app_config)
        )
        self._file_search_service = file_search_service or LiveFileSearchService()
        self._grep_search_service = grep_search_service or LiveGrepSearchService()
        self._shell_command_service = shell_command_service or LiveShellCommandService()
        self._split_terminal_service = split_terminal_service or LiveSplitTerminalService()
        self._pending_workers: dict[str, Effect] = {}
        self._split_terminal_session: SplitTerminalSession | None = None
        self._child_pane_timer: Timer | None = None
        self._active_child_pane_cancel_event: threading.Event | None = None
        self._active_child_pane_request_id: int | None = None
        self._file_search_timer: Timer | None = None
        self._active_file_search_cancel_event: threading.Event | None = None
        self._active_file_search_request_id: int | None = None
        self._grep_search_timer: Timer | None = None
        self._active_grep_search_cancel_event: threading.Event | None = None
        self._active_grep_search_request_id: int | None = None
        self._active_directory_size_cancel_event: threading.Event | None = None
        self._active_directory_size_request_id: int | None = None

    @property
    def app_state(self) -> AppState:
        """Expose the reducer-managed state for tests and integrations."""

        return self._app_state

    def compose(self) -> ComposeResult:
        shell = select_shell_data(self._app_state)
        yield CurrentPathBar(shell.current_path, id="current-path-bar")
        yield self._build_body(shell)
        yield Container(
            CommandPalette(shell.command_palette, id="command-palette"),
            id="command-palette-layer",
            classes="overlay-layer",
        )
        yield Container(
            ConflictDialog(shell.conflict_dialog, id="conflict-dialog"),
            id="conflict-dialog-layer",
            classes="overlay-layer dialog-layer",
        )
        yield Container(
            AttributeDialog(shell.attribute_dialog, id="attribute-dialog"),
            id="attribute-dialog-layer",
            classes="overlay-layer dialog-layer",
        )
        yield Container(
            ConfigDialog(shell.config_dialog, id="config-dialog"),
            id="config-dialog-layer",
            classes="overlay-layer dialog-layer",
        )
        yield Container(
            ShellCommandDialog(shell.shell_command_dialog, id="shell-command-dialog"),
            id="shell-command-dialog-layer",
            classes="overlay-layer dialog-layer",
        )
        yield HelpBar(shell.help, id="help-bar")
        yield StatusBar(shell.status, id="status-bar")

    _PANE_VISIBILITY_NARROW_THRESHOLD = 66
    _PANE_VISIBILITY_MEDIUM_THRESHOLD = 100

    def _update_pane_visibility(self, width: int) -> None:
        """Show or hide side panes based on terminal width."""
        try:
            parent_pane = self.query_one("#parent-pane")
            child_pane = self.query_one("#child-pane")
        except NoMatches:
            return

        if width >= self._PANE_VISIBILITY_MEDIUM_THRESHOLD:
            parent_pane.display = True
            child_pane.display = True
        elif width >= self._PANE_VISIBILITY_NARROW_THRESHOLD:
            parent_pane.display = False
            child_pane.display = True
        else:
            parent_pane.display = False
            child_pane.display = False

    async def on_mount(self) -> None:
        """Load the initial directory snapshot after the UI mounts."""

        await self.dispatch_actions((
            SetTerminalHeight(height=self.size.height),
            RequestBrowserSnapshot(self._initial_path, blocking=True),
        ))
        self.call_after_refresh(lambda: self._update_pane_visibility(self.size.width))

    def on_unmount(self) -> None:
        """Ensure the embedded terminal session is stopped when the app exits."""

        cancel_pending_runtime_work(self)
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

        await self._dispatch_key_press(key)

    def _build_body(self, shell: ThreePaneShellData) -> Vertical:
        return build_body(shell)

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
        sync_runtime_state(self, previous_state, self._app_state)
        if previous_state.config.display.theme != self._app_state.config.display.theme:
            self.theme = self._app_state.config.display.theme
        if previous_state.config != self._app_state.config:
            self._sync_external_launch_service()
        if changed:
            await self._refresh_shell()
        schedule_effects(self, effects)

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
        await handle_worker_state_changed(self, event)

    async def on_resize(self, event: events.Resize) -> None:
        """Keep the split-terminal PTY dimensions roughly aligned with the viewport."""

        await self.dispatch_actions((SetTerminalHeight(height=event.size.height),))
        self._update_pane_visibility(event.size.width)

        if self._split_terminal_session is None or not self._app_state.split_terminal.visible:
            return
        self.call_after_refresh(self._resize_split_terminal_session)

    async def _refresh_shell(self) -> None:
        await refresh_shell(
            self,
            self._app_state,
            select_shell_data(self._app_state),
            self._split_terminal_session,
        )
        self._update_pane_visibility(self.size.width)

    def _resize_split_terminal_session(self) -> None:
        resize_split_terminal_session(
            self,
            self._app_state,
            self._split_terminal_session,
        )


def create_app(
    snapshot_loader: BrowserSnapshotLoader | None = None,
    clipboard_service: ClipboardOperationService | None = None,
    config_save_service: ConfigSaveService | None = None,
    directory_size_service: DirectorySizeService | None = None,
    file_mutation_service: FileMutationService | None = None,
    archive_extract_service: ArchiveExtractService | None = None,
    zip_compress_service: ZipCompressService | None = None,
    external_launch_service: ExternalLaunchService | None = None,
    file_search_service: FileSearchService | None = None,
    grep_search_service: GrepSearchService | None = None,
    shell_command_service: ShellCommandService | None = None,
    split_terminal_service: SplitTerminalService | None = None,
    *,
    app_config: AppConfig | None = None,
    config_path: str | None = None,
    startup_notification: NotificationState | None = None,
    initial_path: str | Path | None = None,
    current_pane_projection_mode: Literal["full", "viewport"] = "viewport",
) -> PeneoApp:
    """Create the application instance.

    The projection mode override is retained for tests and manual benchmarks.
    Normal runtime uses viewport projection by default.
    """

    return PeneoApp(
        snapshot_loader=snapshot_loader,
        clipboard_service=clipboard_service,
        config_save_service=config_save_service,
        directory_size_service=directory_size_service,
        file_mutation_service=file_mutation_service,
        archive_extract_service=archive_extract_service,
        zip_compress_service=zip_compress_service,
        external_launch_service=external_launch_service,
        file_search_service=file_search_service,
        grep_search_service=grep_search_service,
        shell_command_service=shell_command_service,
        split_terminal_service=split_terminal_service,
        app_config=app_config,
        config_path=config_path,
        startup_notification=startup_notification,
        initial_path=initial_path,
        current_pane_projection_mode=current_pane_projection_mode,
    )


def _initial_sort_state(config: AppConfig) -> SortState:
    return SortState(
        field=config.display.default_sort_field,
        descending=config.display.default_sort_descending,
        directories_first=config.display.directories_first,
    )
