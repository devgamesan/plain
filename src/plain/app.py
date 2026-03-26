"""Application assembly for Plain."""

from collections.abc import Sequence
from functools import partial
from pathlib import Path

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.css.query import NoMatches
from textual.worker import Worker, WorkerState

from plain.models import (
    FileMutationResult,
    PasteConflictPrompt,
    PasteExecutionResult,
    ThreePaneShellData,
)
from plain.services import (
    BrowserSnapshotLoader,
    ClipboardOperationService,
    ExternalLaunchService,
    FileMutationService,
    LiveBrowserSnapshotLoader,
    LiveClipboardOperationService,
    LiveExternalLaunchService,
    LiveFileMutationService,
)
from plain.state import (
    Action,
    AppState,
    BrowserSnapshotFailed,
    BrowserSnapshotLoaded,
    ChildPaneSnapshotFailed,
    ChildPaneSnapshotLoaded,
    ClipboardPasteCompleted,
    ClipboardPasteFailed,
    ClipboardPasteNeedsResolution,
    Effect,
    ExternalLaunchCompleted,
    ExternalLaunchFailed,
    FileMutationCompleted,
    FileMutationFailed,
    LoadBrowserSnapshotEffect,
    LoadChildPaneSnapshotEffect,
    LoadRecursiveFilterEffect,
    RecursiveFilterFailed,
    RecursiveFilterLoaded,
    ReduceResult,
    RequestBrowserSnapshot,
    RunClipboardPasteEffect,
    RunExternalLaunchEffect,
    RunFileMutationEffect,
    build_placeholder_app_state,
    dispatch_key_input,
    iter_bound_keys,
    reduce_app_state,
    select_shell_data,
)
from plain.ui import (
    CommandPalette,
    ConflictDialog,
    CurrentPathBar,
    HelpBar,
    MainPane,
    SidePane,
    StatusBar,
)


class PlainApp(App[None]):
    """Three-pane shell with reducer-driven file operations."""

    TITLE = "Plain"
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
    #help-bar,
    #status-bar {
        height: 1;
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
        max-height: 12;
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
    """

    def __init__(
        self,
        snapshot_loader: BrowserSnapshotLoader | None = None,
        clipboard_service: ClipboardOperationService | None = None,
        file_mutation_service: FileMutationService | None = None,
        external_launch_service: ExternalLaunchService | None = None,
        *,
        initial_path: str | Path | None = None,
    ) -> None:
        super().__init__()
        self._initial_path = str(Path(initial_path or Path.cwd()).expanduser().resolve())
        self._app_state: AppState = build_placeholder_app_state(self._initial_path)
        self._snapshot_loader = snapshot_loader or LiveBrowserSnapshotLoader()
        self._clipboard_service = clipboard_service or LiveClipboardOperationService()
        self._file_mutation_service = file_mutation_service or LiveFileMutationService()
        self._external_launch_service = external_launch_service or LiveExternalLaunchService()
        self._pending_workers: dict[str, Effect] = {}

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
        yield HelpBar(shell.help, id="help-bar")
        yield StatusBar(shell.status, id="status-bar")

    async def on_mount(self) -> None:
        """Load the initial directory snapshot after the UI mounts."""

        await self.dispatch_actions((RequestBrowserSnapshot(self._initial_path, blocking=True),))

    async def on_key(self, event: events.Key) -> None:
        """Normalize keyboard input into reducer actions."""

        handled = await self._dispatch_key_press(event.key, character=event.character)
        if handled:
            event.stop()
            event.prevent_default()

    async def action_dispatch_bound_key(self, key: str) -> None:
        """Handle priority key bindings through the central dispatcher."""

        character = None
        if self._app_state.ui_mode in {"FILTER", "RENAME", "CREATE", "PALETTE"}:
            if key == "space":
                if self._app_state.ui_mode in {"RENAME", "CREATE", "PALETTE"}:
                    character = " "
            elif len(key) == 1 and key.isprintable():
                character = key
        await self._dispatch_key_press(key, character=character)

    def _build_body(self, shell: ThreePaneShellData) -> Horizontal:
        return Horizontal(
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

        changed, effects = self._apply_actions(actions)
        if changed:
            await self._refresh_shell()
        self._schedule_effects(effects)

    def _apply_actions(self, actions: Sequence[Action]) -> tuple[bool, tuple[Effect, ...]]:
        state = self._app_state
        changed = False
        effects: list[Effect] = []

        for action in actions:
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
            elif isinstance(effect, LoadRecursiveFilterEffect):
                self._schedule_recursive_filter(effect)
            elif isinstance(effect, RunClipboardPasteEffect):
                self._schedule_clipboard_paste(effect)
            elif isinstance(effect, RunFileMutationEffect):
                self._schedule_file_mutation(effect)
            elif isinstance(effect, RunExternalLaunchEffect):
                self._schedule_external_launch(effect)

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

    def _schedule_recursive_filter(self, effect: LoadRecursiveFilterEffect) -> None:
        worker = self.run_worker(
            partial(
                self._snapshot_loader.load_recursive_entries,
                effect.path,
                effect.query,
            ),
            name=f"recursive-filter:{effect.request_id}",
            group="recursive-filter",
            description=f"{effect.path}:{effect.query}",
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

    async def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Convert worker completion back into reducer actions."""

        effect = self._pending_workers.get(event.worker.name)
        if effect is None:
            return

        if event.state in {WorkerState.PENDING, WorkerState.RUNNING}:
            return

        self._pending_workers.pop(event.worker.name, None)

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

            if isinstance(effect, LoadRecursiveFilterEffect):
                await self.dispatch_actions(
                    (
                        RecursiveFilterLoaded(
                            request_id=effect.request_id,
                            entries=event.worker.result,
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

            if isinstance(effect, RunExternalLaunchEffect):
                await self.dispatch_actions(
                    (ExternalLaunchCompleted(request_id=effect.request_id),)
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

        if isinstance(effect, LoadRecursiveFilterEffect):
            await self.dispatch_actions(
                (
                    RecursiveFilterFailed(
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

        await self.dispatch_actions(
            (
                ClipboardPasteFailed(
                    request_id=effect.request_id,
                    message=message,
                ),
            )
        )

    async def _refresh_shell(self) -> None:
        shell = select_shell_data(self._app_state)
        try:
            current_path_bar = self.query_one("#current-path-bar", CurrentPathBar)
            parent_pane = self.query_one("#parent-pane", SidePane)
            current_pane = self.query_one("#current-pane", MainPane)
            child_pane = self.query_one("#child-pane", SidePane)
            command_palette = self.query_one("#command-palette", CommandPalette)
            help_bar = self.query_one("#help-bar", HelpBar)
            status_bar = self.query_one("#status-bar", StatusBar)
            conflict_dialog = self.query_one("#conflict-dialog", ConflictDialog)
        except NoMatches:
            selectors = (
                "#current-path-bar",
                "#body",
                "#command-palette",
                "#help-bar",
                "#status-bar",
                "#conflict-dialog",
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
            return

        current_path_bar.set_path(shell.current_path)
        await parent_pane.set_entries(shell.parent_entries)
        current_pane.set_summary(shell.current_summary)
        current_pane.set_entries(shell.current_entries, shell.current_cursor_index)
        current_pane.set_context_input(shell.current_context_input)
        await child_pane.set_entries(shell.child_entries)
        command_palette.set_state(shell.command_palette)
        help_bar.set_state(shell.help)
        status_bar.set_state(shell.status)
        conflict_dialog.set_state(shell.conflict_dialog)


def create_app(
    snapshot_loader: BrowserSnapshotLoader | None = None,
    clipboard_service: ClipboardOperationService | None = None,
    file_mutation_service: FileMutationService | None = None,
    external_launch_service: ExternalLaunchService | None = None,
    *,
    initial_path: str | Path | None = None,
) -> PlainApp:
    """Create the application instance."""

    return PlainApp(
        snapshot_loader=snapshot_loader,
        clipboard_service=clipboard_service,
        file_mutation_service=file_mutation_service,
        external_launch_service=external_launch_service,
        initial_path=initial_path,
    )
