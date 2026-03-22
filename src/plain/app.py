"""Application assembly for Plain."""

from collections.abc import Sequence
from functools import partial
from pathlib import Path

from textual import events
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.css.query import NoMatches
from textual.worker import Worker, WorkerState

from plain.models import ThreePaneShellData
from plain.services import BrowserSnapshotLoader, LiveBrowserSnapshotLoader
from plain.state import (
    Action,
    AppState,
    BrowserSnapshotFailed,
    BrowserSnapshotLoaded,
    ChildPaneSnapshotFailed,
    ChildPaneSnapshotLoaded,
    Effect,
    LoadBrowserSnapshotEffect,
    LoadChildPaneSnapshotEffect,
    ReduceResult,
    RequestBrowserSnapshot,
    build_placeholder_app_state,
    dispatch_key_input,
    reduce_app_state,
    select_shell_data,
)
from plain.ui import MainPane, SidePane, StatusBar


class PlainApp(App[None]):
    """Minimal three-pane shell used as the initial UI skeleton."""

    TITLE = "Plain"
    SUB_TITLE = "Three-pane shell"
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

    #status-bar {
        height: 1;
        padding: 0 1;
        background: $surface;
        color: $text;
    }
    """

    def __init__(
        self,
        snapshot_loader: BrowserSnapshotLoader | None = None,
        *,
        initial_path: str | Path | None = None,
    ) -> None:
        super().__init__()
        self._initial_path = str(Path(initial_path or Path.cwd()).expanduser().resolve())
        self._app_state: AppState = build_placeholder_app_state(self._initial_path)
        self._snapshot_loader = snapshot_loader or LiveBrowserSnapshotLoader()
        self._pending_workers: dict[str, Effect] = {}

    @property
    def app_state(self) -> AppState:
        """Expose the reducer-managed state for tests and integrations."""

        return self._app_state

    def compose(self) -> ComposeResult:
        shell = select_shell_data(self._app_state)
        yield self._build_body(shell)
        yield StatusBar(shell.status, id="status-bar")

    async def on_mount(self) -> None:
        """Load the initial directory snapshot after the UI mounts."""

        await self.dispatch_actions((RequestBrowserSnapshot(self._initial_path, blocking=True),))

    async def on_key(self, event: events.Key) -> None:
        """Normalize keyboard input into reducer actions."""

        actions = dispatch_key_input(
            self._app_state,
            key=event.key,
            character=event.character,
        )
        if not actions:
            return

        event.stop()
        event.prevent_default()

        await self.dispatch_actions(actions)

    def _build_body(self, shell: ThreePaneShellData) -> Horizontal:
        return Horizontal(
            SidePane(
                "親ディレクトリ",
                shell.parent_entries,
                id="parent-pane",
                classes="pane side-pane",
            ),
            MainPane(
                "カレントディレクトリ",
                shell.current_entries,
                id="current-pane",
                classes="pane main-pane",
            ),
            SidePane(
                "子ディレクトリ",
                shell.child_entries,
                id="child-pane",
                classes="pane side-pane",
            ),
            id="body",
        )

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

            await self.dispatch_actions(
                (
                    ChildPaneSnapshotLoaded(
                        request_id=effect.request_id,
                        pane=event.worker.result,
                    ),
                )
            )
            return

        message = str(event.worker.error) or "ディレクトリ読み込みに失敗しました"
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

        await self.dispatch_actions(
            (
                ChildPaneSnapshotFailed(
                    request_id=effect.request_id,
                    message=message,
                ),
            )
        )

    async def _refresh_shell(self) -> None:
        shell = select_shell_data(self._app_state)
        try:
            parent_pane = self.query_one("#parent-pane", SidePane)
            current_pane = self.query_one("#current-pane", MainPane)
            child_pane = self.query_one("#child-pane", SidePane)
            status_bar = self.query_one("#status-bar", StatusBar)
        except NoMatches:
            try:
                await self.query_one("#body").remove()
            except NoMatches:
                pass
            try:
                await self.query_one("#status-bar").remove()
            except NoMatches:
                pass
            await self.mount(self._build_body(shell))
            await self.mount(StatusBar(shell.status, id="status-bar"))
            return

        await parent_pane.set_entries(shell.parent_entries)
        current_pane.set_entries(shell.current_entries)
        await child_pane.set_entries(shell.child_entries)
        status_bar.set_state(shell.status)


def create_app(
    snapshot_loader: BrowserSnapshotLoader | None = None,
    *,
    initial_path: str | Path | None = None,
) -> PlainApp:
    """Create the application instance."""
    return PlainApp(snapshot_loader=snapshot_loader, initial_path=initial_path)
