"""Application assembly for zivo."""

import re
import threading
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from textual import events
from textual.app import App, ComposeResult, ScreenStackError
from textual.binding import Binding
from textual.containers import Container, Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.keys import Keys
from textual.timer import Timer
from textual.worker import Worker

from zivo.adapters import LocalExternalLaunchAdapter
from zivo.app_runtime import (
    handle_worker_state_changed,
    schedule_effects,
    sync_runtime_state,
)
from zivo.app_shell import (
    build_body,
    refresh_shell,
)
from zivo.models import (
    AppConfig,
    ThreePaneShellData,
)
from zivo.services import (
    ArchiveExtractService,
    AttributeInspectionService,
    BrowserSnapshotLoader,
    ClipboardOperationService,
    ConfigSaveService,
    CustomActionService,
    DirectorySizeService,
    ExternalLaunchService,
    FileMutationService,
    FileSearchService,
    GrepSearchService,
    LiveArchiveExtractService,
    LiveAttributeInspectionService,
    LiveBrowserSnapshotLoader,
    LiveClipboardOperationService,
    LiveConfigSaveService,
    LiveCustomActionService,
    LiveDirectorySizeService,
    LiveExternalLaunchService,
    LiveFileMutationService,
    LiveFileSearchService,
    LiveGrepSearchService,
    LiveShellCommandService,
    LiveTextReplaceService,
    LiveUndoService,
    LiveZipCompressService,
    ShellCommandService,
    TextReplaceService,
    UndoService,
    ZipCompressService,
    resolve_config_path,
)
from zivo.state import (
    AppState,
    Effect,
    NotificationState,
    ReduceResult,
    SortState,
    build_placeholder_app_state,
    dispatch_key_input,
    iter_bound_keys,
    reduce_app_state,
    resolve_parent_directory_path,
    select_shell_data,
)
from zivo.state.actions import (
    Action,
    EnterCursorDirectory,
    EnterTransferDirectory,
    ExitCurrentPath,
    FocusTransferPane,
    OpenPathWithDefaultApp,
    RequestBrowserSnapshot,
    SetCursorPath,
    SetTerminalHeight,
    SetTransferCursorPath,
)
from zivo.ui import (
    AttributeDialog,
    ChildPane,
    CommandPalette,
    ConfigDialog,
    ConflictDialog,
    CurrentPathBar,
    HelpBar,
    InputDialog,
    MainPane,
    ShellCommandDialog,
    SidePane,
    StatusBar,
)


def _active_app_theme(state: AppState) -> str:
    """Return the live theme shown in the UI, including config-editor previews."""

    if state.ui_mode == "CONFIG" and state.config_editor is not None:
        return state.config_editor.draft.display.theme
    return state.config.display.theme


_BROWSING_PREVIEW_SCROLL_KEYS: dict[str, int] = {
    "[": -20,
    "]": 20,
}

_REPLACE_PREVIEW_SCROLL_KEYS: dict[str, int] = {
    "shift+up": -20,
    "shift+down": 20,
}

_REPLACE_PREVIEW_SCROLL_SOURCES = frozenset(
    {
        "replace_text",
        "replace_in_found_files",
        "replace_in_grep_files",
        "grep_replace_selected",
    }
)
_TEXTUAL_TERMINAL_RESPONSE_FILTERS_INSTALLED = False
_TERMINAL_DEVICE_ATTRIBUTES_RESPONSE_RE = re.compile(r"\x1b\[(?:\?[\d;]*|[\d;]*)c\Z")
_TERMINAL_WINDOW_RESPONSE_RE = re.compile(r"\x1b\[(?:4|6|8);[\d;]+t\Z")
_TERMINAL_COLOR_RESPONSE_RE = re.compile(r"\x1b\]1[01];.*(?:\x07|\x1b\\)\Z", re.DOTALL)
_ESCAPE = "\x1b"
_OSC_INTRODUCER = "]"
_OSC_TERMINATOR = "\\"
_OSC_BEL = "\x07"


def _preview_scroll_delta(state: AppState, key: str) -> int | None:
    """Return scroll delta for preview key bindings, or None if not applicable."""

    if (
        state.ui_mode == "BROWSING"
        and state.layout_mode != "transfer"
        and state.child_pane.mode == "preview"
    ):
        return _BROWSING_PREVIEW_SCROLL_KEYS.get(key)
    if state.ui_mode == "PALETTE" and state.command_palette is not None:
        if state.command_palette.source in _REPLACE_PREVIEW_SCROLL_SOURCES:
            return _REPLACE_PREVIEW_SCROLL_KEYS.get(key)
    return None


class zivoApp(App[None]):
    """Three-pane shell with reducer-driven file operations."""

    TITLE = "zivo"
    SUB_TITLE = "Three-pane shell"
    TERMINAL_RESPONSE_ESCAPE_TIMEOUT_SECONDS = 0.05
    BINDINGS = [
        Binding("ctrl+p", "dispatch_bound_key('ctrl+p')", show=False, priority=True),
        Binding("ctrl+n", "dispatch_bound_key('ctrl+n')", show=False, priority=True),
        *[Binding(key, f"dispatch_bound_key('{key}')", show=False, priority=True)
          for key in iter_bound_keys()
        ]
    ]
    CSS_PATH = "app.tcss"

    def __init__(
        self,
        snapshot_loader: BrowserSnapshotLoader | None = None,
        attribute_inspection_service: AttributeInspectionService | None = None,
        clipboard_service: ClipboardOperationService | None = None,
        config_save_service: ConfigSaveService | None = None,
        directory_size_service: DirectorySizeService | None = None,
        file_mutation_service: FileMutationService | None = None,
        archive_extract_service: ArchiveExtractService | None = None,
        zip_compress_service: ZipCompressService | None = None,
        external_launch_service: ExternalLaunchService | None = None,
        file_search_service: FileSearchService | None = None,
        grep_search_service: GrepSearchService | None = None,
        text_replace_service: TextReplaceService | None = None,
        shell_command_service: ShellCommandService | None = None,
        custom_action_service: CustomActionService | None = None,
        undo_service: UndoService | None = None,
        *,
        app_config: AppConfig | None = None,
        config_path: str | None = None,
        startup_notification: NotificationState | None = None,
        initial_path: str | Path | None = None,
        current_pane_projection_mode: Literal["full", "viewport"] = "viewport",
    ) -> None:
        super().__init__()
        _install_textual_terminal_response_filters()
        self._app_config = app_config or AppConfig()
        self.theme = self._app_config.display.theme
        self._initial_path = resolve_parent_directory_path(str(initial_path or Path.cwd()))[0]
        self._app_state: AppState = build_placeholder_app_state(
            self._initial_path,
            config=self._app_config,
            config_path=config_path or str(resolve_config_path()),
            show_hidden=self._app_config.display.show_hidden_files,
            show_help_bar=self._app_config.display.show_help_bar,
            sort=_initial_sort_state(self._app_config),
            confirm_delete=self._app_config.behavior.confirm_delete,
            confirm_exit=self._app_config.behavior.confirm_exit,
            paste_conflict_action=self._app_config.behavior.paste_conflict_action,
            post_reload_notification=startup_notification,
            current_pane_projection_mode=current_pane_projection_mode,
        )
        self._snapshot_loader = snapshot_loader or LiveBrowserSnapshotLoader()
        self._attribute_inspection_service = (
            attribute_inspection_service or LiveAttributeInspectionService()
        )
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
        self._text_replace_service = text_replace_service or LiveTextReplaceService()
        self._shell_command_service = shell_command_service or LiveShellCommandService()
        self._custom_action_service = custom_action_service or LiveCustomActionService()
        self._undo_service = undo_service or LiveUndoService()
        self._pending_workers: dict[str, Effect] = {}
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
        self._pending_terminal_response_escape = False
        self._swallowing_terminal_response = False
        self._terminal_response_escape_deadline = 0.0
        self._last_mouse_click_key: tuple[str, str] | None = None

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
        yield Container(
            InputDialog(shell.input_dialog, id="input-dialog"),
            id="input-dialog-layer",
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

        if self._app_state.layout_mode == "transfer":
            parent_pane.display = False
            child_pane.display = False
            return

        if width >= self._PANE_VISIBILITY_MEDIUM_THRESHOLD:
            parent_pane.display = True
        elif width >= self._PANE_VISIBILITY_NARROW_THRESHOLD:
            parent_pane.display = False
        else:
            parent_pane.display = False

        if width >= self._PANE_VISIBILITY_NARROW_THRESHOLD:
            child_pane.display = True
        else:
            child_pane.display = False

    def _get_target_overlay_pane(self) -> MainPane | None:
        """
        Get the target pane for overlay positioning based on current mode.

        In transfer mode, overlays the opposite pane to keep the active pane visible.
        In browser mode, overlays the current pane.

        Returns:
            MainPane instance if found, None otherwise
        """
        # Transfer mode with active left pane -> overlay on right pane
        if (
            self._app_state.layout_mode == "transfer"
            and self._app_state.active_transfer_pane == "left"
        ):
            try:
                return self.query_one("#transfer-right-pane", MainPane)
            except NoMatches:
                # Fallback to current pane if right pane doesn't exist
                pass

        # Default: current pane (browser mode or transfer mode with active right pane)
        try:
            return self.query_one("#current-pane", MainPane)
        except NoMatches:
            return None

    def _update_command_palette_geometry(self) -> None:
        """Constrain the command palette overlay to the appropriate pane."""

        try:
            command_palette_layer = self.query_one("#command-palette-layer", Container)
            browser_row = self.query_one("#browser-row")
        except NoMatches:
            return

        # Determine target pane based on mode and active pane
        target_pane = self._get_target_overlay_pane()
        if target_pane is None:
            return

        pane_region = target_pane.region
        row_region = browser_row.region
        if pane_region.width <= 0 or pane_region.height <= 0:
            return

        command_palette_layer.styles.width = pane_region.width
        command_palette_layer.styles.height = pane_region.height
        command_palette_layer.styles.offset = (
            pane_region.x,
            row_region.y,
        )

    def _update_config_dialog_geometry(self) -> None:
        """Constrain the config dialog overlay to the appropriate pane."""

        try:
            config_dialog_layer = self.query_one("#config-dialog-layer", Container)
            browser_row = self.query_one("#browser-row")
        except NoMatches:
            return

        # Determine target pane based on mode and active pane
        target_pane = self._get_target_overlay_pane()
        if target_pane is None:
            return

        pane_region = target_pane.region
        row_region = browser_row.region
        if pane_region.width <= 0 or pane_region.height <= 0:
            return

        config_dialog_layer.styles.width = pane_region.width
        config_dialog_layer.styles.height = pane_region.height
        config_dialog_layer.styles.offset = (
            pane_region.x,
            row_region.y,
        )

    def _update_input_dialog_geometry(self) -> None:
        """Constrain the input dialog overlay to the appropriate pane."""

        try:
            input_dialog_layer = self.query_one("#input-dialog-layer", Container)
            browser_row = self.query_one("#browser-row")
        except NoMatches:
            return

        # Determine target pane based on mode and active pane
        target_pane = self._get_target_overlay_pane()
        if target_pane is None:
            return

        pane_region = target_pane.region
        row_region = browser_row.region
        if pane_region.width <= 0 or pane_region.height <= 0:
            return

        input_dialog_layer.styles.width = pane_region.width
        input_dialog_layer.styles.height = pane_region.height
        input_dialog_layer.styles.offset = (
            pane_region.x,
            row_region.y,
        )

    async def on_mount(self) -> None:
        """Load the initial directory snapshot after the UI mounts."""

        await self.dispatch_actions((
            SetTerminalHeight(height=self.size.height),
            RequestBrowserSnapshot(self._initial_path, blocking=True),
        ))
        self.call_after_refresh(self._sync_overlay_layout)

    async def on_key(self, event: events.Key) -> None:
        """Normalize keyboard input into reducer actions."""

        if (
            event.key == "ctrl+v"
            and self._app_state.ui_mode in {"RENAME", "CREATE", "EXTRACT", "ZIP", "SYMLINK"}
            and self._app_state.pending_input is not None
        ):
            text = self._external_launch_service.get_from_clipboard()
            if text:
                from zivo.state.actions import PasteIntoPendingInput

                await self.dispatch_actions((PasteIntoPendingInput(text=text),))
            event.stop()
            event.prevent_default()
            return

        if (
            event.key == "ctrl+v"
            and self._app_state.ui_mode == "SHELL"
            and self._app_state.shell_command is not None
        ):
            text = self._external_launch_service.get_from_clipboard()
            if text:
                from zivo.state.actions import PasteIntoShellCommand

                await self.dispatch_actions((PasteIntoShellCommand(text=text),))
            event.stop()
            event.prevent_default()
            return

        scroll_delta = _preview_scroll_delta(self._app_state, event.key)
        if scroll_delta is not None:
            try:
                child_pane = self.query_one("#child-pane", ChildPane)
            except NoMatches:
                return
            child_pane.scroll_preview(scroll_delta)
            event.stop()
            event.prevent_default()
            return

        handled = await self._dispatch_key_press(event.key, character=event.character)
        if handled:
            event.stop()
            event.prevent_default()

    async def on_paste(self, event: events.Paste) -> None:
        """Handle clipboard paste in input dialog modes."""

        if self._app_state.ui_mode in {"RENAME", "CREATE", "EXTRACT", "ZIP", "SYMLINK"}:
            if self._app_state.pending_input is not None:
                from zivo.state.actions import PasteIntoPendingInput

                await self.dispatch_actions(
                    (PasteIntoPendingInput(text=event.text),)
                )
                event.stop()
                event.prevent_default()
                return

        if self._app_state.ui_mode == "SHELL" and self._app_state.shell_command is not None:
            from zivo.state.actions import PasteIntoShellCommand

            await self.dispatch_actions(
                (PasteIntoShellCommand(text=event.text),)
            )
            event.stop()
            event.prevent_default()

    async def on_click(self, event: events.Click) -> None:
        """Handle bubbled mouse clicks for side panes and previews."""

        widget = event.widget
        widget_id = getattr(widget, "id", None)
        meta = event.style.meta

        if widget_id == "child-pane-preview":
            try:
                preview = self.query_one("#child-pane-preview-scroll", VerticalScroll)
            except NoMatches:
                return
            self.set_focus(preview)
            return

        entry_path = meta.get("entry_path")
        if not isinstance(entry_path, str):
            return

        if widget_id == "parent-pane-list":
            if self._is_double_click("parent-pane", entry_path):
                await self.dispatch_actions((RequestBrowserSnapshot(entry_path, blocking=True),))
            return

        if widget_id == "child-pane-list" and self._is_double_click("child-pane", entry_path):
            await self._open_or_enter_path(entry_path)

    async def on_main_pane_entry_clicked(self, message: MainPane.EntryClicked) -> None:
        """Handle bubbled click messages from the center / transfer panes."""

        await self._handle_main_pane_click(
            message.pane_id,
            message.path,
            double_click=message.double_click,
        )

    async def action_dispatch_bound_key(self, key: str) -> None:
        """Handle priority key bindings through the central dispatcher."""

        scroll_delta = _preview_scroll_delta(self._app_state, key)
        if scroll_delta is not None:
            try:
                child_pane = self.query_one("#child-pane", ChildPane)
            except NoMatches:
                return
            child_pane.scroll_preview(scroll_delta)
            return

        await self._dispatch_key_press(key)

    def _build_body(self, shell: ThreePaneShellData) -> Vertical:
        return build_body(
            shell,
        )

    async def _dispatch_key_press(
        self,
        key: str,
        *,
        character: str | None = None,
    ) -> bool:
        if self._should_swallow_terminal_response_key(key):
            return True
        actions = dispatch_key_input(
            self._app_state,
            key=key,
            character=character,
        )
        if not actions:
            return False
        await self.dispatch_actions(actions)
        return True

    def _should_swallow_terminal_response_key(self, key: str) -> bool:
        now = time.monotonic()
        if (
            self._pending_terminal_response_escape
            and now > self._terminal_response_escape_deadline
        ):
            self._pending_terminal_response_escape = False
            self._swallowing_terminal_response = False

        if self._swallowing_terminal_response:
            if len(key) == 1:
                if _is_terminal_response_final_byte(key):
                    self._swallowing_terminal_response = False
                    self._pending_terminal_response_escape = False
                return True
            self._swallowing_terminal_response = False
            self._pending_terminal_response_escape = False
            return False

        if self._pending_terminal_response_escape:
            if len(key) == 1 and key in {"[", "]", "O", "P", "^", "_", "X"}:
                self._swallowing_terminal_response = True
                return True
            self._pending_terminal_response_escape = False

        if key == "escape":
            self._pending_terminal_response_escape = True
            self._terminal_response_escape_deadline = (
                now + self.TERMINAL_RESPONSE_ESCAPE_TIMEOUT_SECONDS
            )
            self._swallowing_terminal_response = False

        return False

    async def dispatch_actions(self, actions: Sequence[Action]) -> None:
        """Apply reducer actions, refresh the UI, and schedule any effects."""

        previous_state = self._app_state
        previous_theme = _active_app_theme(previous_state)
        changed, effects = self._apply_actions(actions)
        sync_runtime_state(self, previous_state, self._app_state)
        next_theme = _active_app_theme(self._app_state)
        theme_changed = previous_theme != next_theme
        layout_changed = previous_state.layout_mode != self._app_state.layout_mode
        if theme_changed:
            self.theme = next_theme
        if previous_state.config != self._app_state.config:
            self._sync_external_launch_service()
        if layout_changed:
            try:
                await self.query_one("#body").remove()
            except NoMatches:
                pass
        if changed or theme_changed or layout_changed:
            await self._refresh_shell(theme_changed=theme_changed)
        schedule_effects(self, effects)

    def _build_external_launch_service(self, app_config: AppConfig) -> LiveExternalLaunchService:
        return LiveExternalLaunchService(
            adapter=LocalExternalLaunchAdapter(
                terminal_command_templates=app_config.terminal,
                editor_command_template=app_config.editor,
                gui_editor_command_template=app_config.gui_editor,
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

    async def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        await handle_worker_state_changed(self, event)

    async def on_resize(self, event: events.Resize) -> None:
        """Update the terminal height on resize."""

        await self.dispatch_actions((SetTerminalHeight(height=event.size.height),))
        self._sync_overlay_layout(event.size.width)

    async def on_side_pane_entry_clicked(self, message: SidePane.EntryClicked) -> None:
        """Handle left parent-pane double clicks from the widget message path."""

        if message.pane_id != "parent-pane" or not message.double_click:
            return
        entry = next(
            (entry for entry in self._app_state.parent_pane.entries if entry.path == message.path),
            None,
        )
        if entry is None:
            return
        if entry.kind == "dir":
            await self.dispatch_actions((RequestBrowserSnapshot(message.path, blocking=True),))
            return
        await self.dispatch_actions((OpenPathWithDefaultApp(message.path),))

    async def on_child_pane_entry_clicked(self, message: ChildPane.EntryClicked) -> None:
        """Handle right child-pane double clicks from the widget message path."""

        if not message.double_click:
            return
        await self._open_or_enter_path(message.path)

    def on_child_pane_preview_clicked(self, _message: ChildPane.PreviewClicked) -> None:
        """Move focus to the preview scroll container when the preview is clicked."""

        try:
            preview = self.query_one("#child-pane-preview-scroll", VerticalScroll)
        except NoMatches:
            return
        self.set_focus(preview)

    async def _refresh_shell(self, *, theme_changed: bool = False) -> None:
        try:
            await refresh_shell(
                self,
                self._app_state,
                select_shell_data(self._app_state),
                theme_changed=theme_changed,
            )
            self.call_after_refresh(self._sync_overlay_layout)
        except ScreenStackError:
            return

    def _sync_overlay_layout(self, width: int | None = None) -> None:
        """Refresh side-pane visibility and overlay geometry together."""

        self._update_pane_visibility(self.size.width if width is None else width)
        self._update_command_palette_geometry()
        self._update_config_dialog_geometry()
        self._update_input_dialog_geometry()

    async def _handle_main_pane_click(
        self,
        pane_id: str | None,
        path: str,
        *,
        double_click: bool,
    ) -> None:
        if self._app_state.layout_mode == "transfer":
            pane = "right" if pane_id == "transfer-right-pane" else "left"
            actions: list[Action] = []
            if self._app_state.active_transfer_pane != pane:
                actions.append(FocusTransferPane(pane))
            actions.append(SetTransferCursorPath(path))
            if double_click:
                actions.append(EnterTransferDirectory())
            await self.dispatch_actions(tuple(actions))
            return

        actions = [SetCursorPath(path)]
        if double_click:
            await self.dispatch_actions(tuple(actions))
            await self._open_or_enter_path(path)
            return
        await self.dispatch_actions(tuple(actions))

    async def _open_or_enter_path(self, path: str) -> None:
        shell = select_shell_data(self._app_state)
        current_paths = {entry.path for entry in shell.current_entries or ()}
        child_paths = {entry.path for entry in shell.child_pane.entries}
        if path in current_paths:
            entry = next(
                (entry for entry in self._app_state.current_pane.entries if entry.path == path),
                None,
            )
            if entry is None:
                return
            if entry.kind == "dir":
                await self.dispatch_actions((SetCursorPath(path), EnterCursorDirectory()))
            else:
                await self.dispatch_actions((SetCursorPath(path), OpenPathWithDefaultApp(path)))
            return
        if path in child_paths:
            entry = next(
                (entry for entry in self._app_state.child_pane.entries if entry.path == path),
                None,
            )
            if entry is None:
                return
            if entry.kind == "dir":
                await self.dispatch_actions((RequestBrowserSnapshot(path, blocking=True),))
            else:
                await self.dispatch_actions((OpenPathWithDefaultApp(path),))

    def _is_double_click(self, pane_id: str, path: str) -> bool:
        key = (pane_id, path)
        double_click = key == self._last_mouse_click_key
        self._last_mouse_click_key = key
        return double_click

    def _path_for_table_row(self, pane_id: str, row_index: int) -> str | None:
        if row_index < 0:
            return None
        shell = select_shell_data(self._app_state)
        if self._app_state.layout_mode == "transfer":
            transfer = (
                shell.transfer_right if pane_id == "transfer-right-pane" else shell.transfer_left
            )
            if transfer is None or row_index >= len(transfer.entries):
                return None
            return transfer.entries[row_index].path
        current_entries = shell.current_entries or ()
        if row_index >= len(current_entries):
            return None
        return current_entries[row_index].path


def create_app(
    snapshot_loader: BrowserSnapshotLoader | None = None,
    attribute_inspection_service: AttributeInspectionService | None = None,
    clipboard_service: ClipboardOperationService | None = None,
    config_save_service: ConfigSaveService | None = None,
    directory_size_service: DirectorySizeService | None = None,
    file_mutation_service: FileMutationService | None = None,
    archive_extract_service: ArchiveExtractService | None = None,
    zip_compress_service: ZipCompressService | None = None,
    external_launch_service: ExternalLaunchService | None = None,
    file_search_service: FileSearchService | None = None,
    grep_search_service: GrepSearchService | None = None,
    text_replace_service: TextReplaceService | None = None,
    shell_command_service: ShellCommandService | None = None,
    undo_service: UndoService | None = None,
    *,
    app_config: AppConfig | None = None,
    config_path: str | None = None,
    startup_notification: NotificationState | None = None,
    initial_path: str | Path | None = None,
    current_pane_projection_mode: Literal["full", "viewport"] = "viewport",
) -> zivoApp:
    """Create the application instance.

    The projection mode override is retained for tests and manual benchmarks.
    Normal runtime uses viewport projection by default.
    """

    return zivoApp(
        snapshot_loader=snapshot_loader,
        attribute_inspection_service=attribute_inspection_service,
        clipboard_service=clipboard_service,
        config_save_service=config_save_service,
        directory_size_service=directory_size_service,
        file_mutation_service=file_mutation_service,
        archive_extract_service=archive_extract_service,
        zip_compress_service=zip_compress_service,
        external_launch_service=external_launch_service,
        file_search_service=file_search_service,
        grep_search_service=grep_search_service,
        text_replace_service=text_replace_service,
        shell_command_service=shell_command_service,
        undo_service=undo_service,
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


def _is_terminal_response_final_byte(key: str) -> bool:
    if len(key) != 1:
        return False
    codepoint = ord(key)
    return 0x40 <= codepoint <= 0x7E


def _install_textual_terminal_response_filters() -> None:
    global _TEXTUAL_TERMINAL_RESPONSE_FILTERS_INSTALLED
    if _TEXTUAL_TERMINAL_RESPONSE_FILTERS_INSTALLED:
        return

    import textual._xterm_parser as xterm_parser

    original_feed = xterm_parser.XTermParser.feed
    original = xterm_parser.XTermParser._sequence_to_key_events

    def _filter_terminal_response_chunk(self, data: str) -> str:
        pending_escape = getattr(self, "_zivo_pending_escape", False)
        in_osc = getattr(self, "_zivo_in_osc", False)
        osc_saw_escape = getattr(self, "_zivo_osc_saw_escape", False)

        if not data:
            if pending_escape and not in_osc:
                data = _ESCAPE
            else:
                data = ""
            pending_escape = False
            in_osc = False
            osc_saw_escape = False
            self._zivo_pending_escape = pending_escape
            self._zivo_in_osc = in_osc
            self._zivo_osc_saw_escape = osc_saw_escape
            return data

        filtered: list[str] = []
        index = 0

        if pending_escape:
            pending_escape = False
            if data.startswith(_OSC_INTRODUCER):
                in_osc = True
                index = 1
            else:
                filtered.append(_ESCAPE)

        while index < len(data):
            character = data[index]
            if in_osc:
                if osc_saw_escape:
                    osc_saw_escape = False
                    if character == _OSC_TERMINATOR:
                        in_osc = False
                    index += 1
                    continue
                if character == _OSC_BEL:
                    in_osc = False
                    index += 1
                    continue
                if character == _ESCAPE:
                    osc_saw_escape = True
                index += 1
                continue

            if character == _ESCAPE:
                next_index = index + 1
                if next_index >= len(data):
                    pending_escape = True
                    index += 1
                    continue
                if data[next_index] == _OSC_INTRODUCER:
                    in_osc = True
                    index += 2
                    continue

            filtered.append(character)
            index += 1

        self._zivo_pending_escape = pending_escape
        self._zivo_in_osc = in_osc
        self._zivo_osc_saw_escape = osc_saw_escape
        return "".join(filtered)

    def _wrapped_feed(self, data: str):
        filtered = _filter_terminal_response_chunk(self, data)
        if data and not filtered:
            return ()
        return original_feed(self, filtered)

    def _wrapped(self, sequence: str):
        if (
            _TERMINAL_DEVICE_ATTRIBUTES_RESPONSE_RE.fullmatch(sequence)
            or _TERMINAL_WINDOW_RESPONSE_RE.fullmatch(sequence)
            or _TERMINAL_COLOR_RESPONSE_RE.fullmatch(sequence)
        ):
            yield events.Key(Keys.Ignore, sequence)
            return
        yield from original(self, sequence)

    xterm_parser.XTermParser.feed = _wrapped_feed
    xterm_parser.XTermParser._sequence_to_key_events = _wrapped
    _TEXTUAL_TERMINAL_RESPONSE_FILTERS_INSTALLED = True
