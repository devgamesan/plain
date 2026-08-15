"""Shared Textual app support for integration and UI tests."""

# Test support intentionally re-exports imported types used by split test modules.
# ruff: noqa: F401

import asyncio
import os
import threading
import time
from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path

import pytest
from rich.style import Style
from rich.text import Text
from textual.containers import VerticalScroll
from textual.css.query import NoMatches
from textual.events import Click, MouseMove
from textual.widgets import DataTable, Label, Static

from zivo import create_app
from zivo.app import _preview_scroll_delta
from zivo.app_overlay_layout import update_pane_visibility
from zivo.models import (
    AppConfig,
    BehaviorConfig,
    DeletePreparationResult,
    DeleteRequest,
    DisplayConfig,
    EditorConfig,
    ExternalLaunchRequest,
    FileMutationResult,
    PasteConflict,
    PasteConflictPrompt,
    PasteExecutionResult,
    PasteRequest,
    PasteSummary,
    ShellCommandResult,
    TerminalConfig,
    TextReplacePreviewEntry,
    TextReplacePreviewResult,
    TextReplaceRequest,
    TextReplaceResult,
    UndoDeletePathStep,
    UndoEntry,
    UndoResult,
)
from zivo.services import (
    FakeAttributeInspectionService,
    FakeBrowserSnapshotLoader,
    FakeClipboardOperationService,
    FakeDirectorySizeService,
    FakeExternalLaunchService,
    FakeFileMutationService,
    FakeFileSearchService,
    FakeGrepSearchService,
    FakeShellCommandService,
    FakeTextReplaceService,
    FakeUndoService,
    LiveExternalLaunchService,
)
from zivo.state import (
    AttributeInspectionState,
    BrowserSnapshot,
    CommandPaletteState,
    DirectoryEntryState,
    FileSearchResultState,
    GrepSearchResultState,
    NotificationAction,
    NotificationState,
    PaneState,
    build_initial_app_state,
)
from zivo.state.actions import (
    ConfigSaveCompleted,
    JumpCursor,
    MoveCursor,
    SetNotification,
    SetTerminalHeight,
)
from zivo.state.command_palette import get_command_palette_items
from zivo.state.selectors import (
    compute_current_pane_visible_window,
    select_command_palette_state,
    select_shell_data,
)
from zivo.ui import (
    AttributeDialog,
    ChildPane,
    CommandPalette,
    ConfigDialog,
    ConflictDialog,
    CurrentPathBar,
    HelpBar,
    InputBar,
    InputDialog,
    ShellCommandDialog,
    SidePane,
    StatusBar,
    SummaryBar,
    TabBar,
)
from zivo.ui.panes import MainPane
from zivo.windows_paths import WINDOWS_DRIVES_ROOT, is_windows_path, paths_equal

skip_if_windows_split_terminal_unsupported = pytest.mark.skipif(
    os.name == "nt",
    reason="split terminal is unsupported on native Windows",
)

def build_snapshot(
    path: str,
    current_entries: tuple[DirectoryEntryState, ...],
    *,
    child_path: str | None = None,
    child_entries: tuple[DirectoryEntryState, ...] = (),
) -> BrowserSnapshot:
    """Build a compact three-pane snapshot for headless app tests."""

    cursor_path = current_entries[0].path if current_entries else None
    parent_path = str(Path(path).parent)
    parent_entries = (
        DirectoryEntryState(path, Path(path).name, "dir"),
        DirectoryEntryState(f"{parent_path}/sibling", "sibling", "dir"),
    )
    return BrowserSnapshot(
        current_path=path,
        parent_pane=PaneState(
            directory_path=parent_path,
            entries=parent_entries,
            cursor_path=path,
        ),
        current_pane=PaneState(
            directory_path=path,
            entries=current_entries,
            cursor_path=cursor_path,
        ),
        child_pane=PaneState(
            directory_path=child_path or path,
            entries=child_entries,
        ),
    )

async def wait_for_snapshot_loaded(app, expected_path: str, timeout: float = 0.5) -> None:
    """Wait until the app has applied the snapshot for ``expected_path``."""

    resolved_expected = str(Path(expected_path).resolve())
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        if (
            app.app_state.current_path == resolved_expected
            and app.app_state.pending_browser_snapshot_request_id is None
            and app.app_state.current_pane.entries
        ):
            return
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError(f"snapshot did not load for {expected_path}")
        await asyncio.sleep(0.01)

async def wait_for_widget(app, selector: str, widget_type, timeout: float = 0.5):
    """Wait until a widget matching ``selector`` is mounted."""

    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        try:
            return app.query_one(selector, widget_type)
        except NoMatches:
            if asyncio.get_running_loop().time() >= deadline:
                raise
            await asyncio.sleep(0.01)

def _normalize_rich_style(style: str | Style | None) -> Style | None:
    if style is None:
        return None
    if isinstance(style, Style):
        return style
    return Style.parse(style)

def _style_without_background(style: Style) -> Style:
    return Style(
        color=style.color,
        bold=style.bold,
        dim=style.dim,
        italic=style.italic,
        underline=style.underline,
        blink=style.blink,
        blink2=style.blink2,
        reverse=style.reverse,
        conceal=style.conceal,
        strike=style.strike,
        underline2=style.underline2,
        frame=style.frame,
        encircle=style.encircle,
        overline=style.overline,
        link=style.link,
        meta=style.meta,
    )

def _text_has_style(renderable: Text, expected_style: Style) -> bool:
    return any(_normalize_rich_style(span.style) == expected_style for span in renderable.spans)

def _text_style_matches(text: Text, expected_style: Style) -> bool:
    return _normalize_rich_style(text.style) == expected_style

async def _wait_for_status_bar(app, timeout: float = 0.5) -> StatusBar:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        try:
            return app.query_one("#status-bar", StatusBar)
        except NoMatches:
            if asyncio.get_running_loop().time() >= deadline:
                raise
            await asyncio.sleep(0.01)

async def _wait_for_status_message(app, expected_text: str, timeout: float = 0.5) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        status_bar = await _wait_for_status_bar(app, timeout=timeout)
        if str(status_bar.renderable) == expected_text:
            return
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError(f"status message did not become {expected_text}")
        await asyncio.sleep(0.01)

async def _wait_for_app_theme(app, expected_theme: str, timeout: float = 0.5) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        if app.theme == expected_theme:
            return
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError(f"app theme did not become {expected_theme!r}")
        await asyncio.sleep(0.01)

async def _wait_for_predicate(predicate, *, timeout: float = 0.5, message: str) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        if predicate():
            return
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError(message)
        await asyncio.sleep(0.01)

async def _select_config_setting(
    pilot,
    app,
    expected_line: str,
    *,
    max_steps: int = 24,
) -> None:
    for _ in range(max_steps):
        dialog = await _wait_for_config_dialog(app)
        lines = dialog.query_one("#config-dialog-lines", Static)
        if expected_line in str(lines.renderable):
            return
        await pilot.press("down")
    raise AssertionError(f"config setting was not selected: {expected_line}")

async def _wait_for_current_path_bar(app, timeout: float = 0.5) -> CurrentPathBar:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        try:
            return app.query_one("#current-path-bar", CurrentPathBar)
        except NoMatches:
            if asyncio.get_running_loop().time() >= deadline:
                raise
            await asyncio.sleep(0.01)

async def _wait_for_tab_bar(app, timeout: float = 0.5) -> TabBar:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        try:
            return app.query_one("#tab-bar", TabBar)
        except NoMatches:
            if asyncio.get_running_loop().time() >= deadline:
                raise
            await asyncio.sleep(0.01)

async def _wait_for_context_input(app, timeout: float = 0.5) -> InputBar:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        try:
            return app.query_one("#current-pane-context-input", InputBar)
        except NoMatches:
            if asyncio.get_running_loop().time() >= deadline:
                raise
            await asyncio.sleep(0.01)

async def _wait_for_input_dialog(app, timeout: float = 0.5) -> InputDialog:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        try:
            dialog = app.query_one("#input-dialog", InputDialog)
            if dialog.display:
                return dialog
        except NoMatches:
            pass
        if asyncio.get_running_loop().time() >= deadline:
            raise
        await asyncio.sleep(0.01)

async def _wait_for_summary_bar(app, timeout: float = 0.5) -> SummaryBar:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        try:
            return app.query_one("#current-pane-summary-bar", SummaryBar)
        except NoMatches:
            if asyncio.get_running_loop().time() >= deadline:
                raise
            await asyncio.sleep(0.01)

async def _wait_for_command_palette(app, timeout: float = 0.5) -> CommandPalette:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        try:
            return app.query_one("#command-palette", CommandPalette)
        except NoMatches:
            if asyncio.get_running_loop().time() >= deadline:
                raise
            await asyncio.sleep(0.01)

async def _wait_for_attribute_dialog(app, timeout: float = 0.5) -> AttributeDialog:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        try:
            return app.query_one("#attribute-dialog", AttributeDialog)
        except NoMatches:
            if asyncio.get_running_loop().time() >= deadline:
                raise
            await asyncio.sleep(0.01)

async def _wait_for_config_dialog(app, timeout: float = 0.5) -> ConfigDialog:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        try:
            return app.query_one("#config-dialog", ConfigDialog)
        except NoMatches:
            if asyncio.get_running_loop().time() >= deadline:
                raise
            await asyncio.sleep(0.01)

async def _wait_for_shell_command_dialog(app, timeout: float = 0.5) -> ShellCommandDialog:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        try:
            return app.query_one("#shell-command-dialog", ShellCommandDialog)
        except NoMatches:
            if asyncio.get_running_loop().time() >= deadline:
                raise
            await asyncio.sleep(0.01)

def _assert_region_vertically_centered(region, container_region, tolerance: int = 1) -> None:
    expected_y = container_region.y + (container_region.height - region.height) // 2
    assert abs(region.y - expected_y) <= tolerance

async def _wait_for_help_bar_text(app, expected: str, timeout: float = 0.5) -> HelpBar:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        try:
            help_bar = app.query_one("#help-bar", HelpBar)
        except NoMatches:
            help_bar = None
        if help_bar is not None and str(help_bar.renderable) == expected:
            return help_bar
        if asyncio.get_running_loop().time() >= deadline:
            actual = None if help_bar is None else str(help_bar.renderable)
            raise AssertionError(f"help bar did not become {expected!r}; actual={actual!r}")
        await asyncio.sleep(0.01)

async def _wait_for_notification_message(app, expected: str, timeout: float = 0.5) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        notification = app.app_state.notification
        if (
            notification is not None
            and notification.message == expected
            and not app._pending_workers
        ):
            return
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError(f"notification did not become {expected!r}")
        await asyncio.sleep(0.01)

async def _wait_for_directory_sizes(app, timeout: float = 0.5) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        if (
            app.app_state.pending_directory_size_request_id is None
            and app.app_state.directory_size_cache
        ):
            return
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError("directory sizes did not finish loading")
        await asyncio.sleep(0.01)

async def _wait_for_table_cell(
    app, expected: str, row: int, col: int, timeout: float = 5.0
) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        table = app.query_one("#current-pane-table", DataTable)
        if str(table.get_cell_at((row, col))) == expected:
            return
        if asyncio.get_running_loop().time() >= deadline:
            actual = table.get_cell_at((row, col))
            raise AssertionError(f"table cell ({row}, {col}) is {actual!r}, expected {expected!r}")
        await asyncio.sleep(0.01)

async def _wait_for_child_list_label(
    app, expected_substring: str, index: int = 0, timeout: float = 5.0
) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        child_list = app.query_one("#child-pane-list", Static)
        child_lines = _side_pane_lines(child_list)
        try:
            if expected_substring in child_lines[index]:
                return
        except IndexError:
            pass
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError(
                f"child list label at index {index} did not contain {expected_substring!r}"
            )
        await asyncio.sleep(0.01)

def _side_pane_lines(widget: Static) -> list[str]:
    renderable = widget.renderable
    if isinstance(renderable, Text):
        return renderable.plain.splitlines()
    return str(renderable).splitlines()

async def _wait_for_row_count(app, expected_count: int, timeout: float = 0.5) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        try:
            table = app.query_one("#current-pane-table", DataTable)
        except NoMatches:
            table = None
        if table is not None and table.row_count == expected_count:
            return
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError(f"table row_count did not become {expected_count}")
        await asyncio.sleep(0.01)

async def _wait_for_transfer_right_table(app, timeout: float = 0.5) -> DataTable:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        try:
            return app.query_one("#transfer-right-pane-table", DataTable)
        except NoMatches:
            if asyncio.get_running_loop().time() >= deadline:
                raise
            await asyncio.sleep(0.01)

async def _wait_for_path(app, expected_path: str, timeout: float = 0.5) -> None:
    resolved_expected = (
        expected_path if is_windows_path(expected_path) else str(Path(expected_path).resolve())
    )
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        if (
            paths_equal(app.app_state.current_path, resolved_expected)
            and app.app_state.pending_browser_snapshot_request_id is None
        ):
            return
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError(f"path did not become {expected_path}")
        await asyncio.sleep(0.01)

async def _wait_for_cursor_path(app, expected_path: str, timeout: float = 0.5) -> None:
    resolved_expected = (
        expected_path if is_windows_path(expected_path) else str(Path(expected_path).resolve())
    )
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        if paths_equal(app.app_state.current_pane.cursor_path, resolved_expected):
            return
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError(f"cursor path did not become {expected_path}")
        await asyncio.sleep(0.01)

async def _wait_for_list_entries(
    app,
    list_selector: str,
    expected_names: list[str],
    timeout: float = 0.5,
) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        try:
            pane_list = app.query_one(list_selector, Static)
        except NoMatches:
            pane_list = None
        if pane_list is not None:
            actual_names = _side_pane_lines(pane_list)
            if actual_names == expected_names:
                return
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError(f"{list_selector} entries did not become {expected_names}")
        await asyncio.sleep(0.01)

async def _wait_for_child_entries(
    app,
    expected_names: list[str],
    timeout: float = 0.5,
) -> None:
    await _wait_for_list_entries(app, "#child-pane-list", expected_names, timeout=timeout)

async def _wait_for_child_preview(
    app,
    expected_title: str,
    expected_snippet: str,
    timeout: float = 0.5,
) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        try:
            child_title = app.query_one("#child-pane .pane-title", Label)
            preview = app.query_one("#child-pane-preview", Static)
        except NoMatches:
            child_title = None
            preview = None
        if child_title is not None and preview is not None and preview.display:
            code = getattr(preview.renderable, "code", None)
            rendered_text = code if code is not None else str(preview.renderable)
            if (
                str(child_title.renderable) == expected_title
                and expected_snippet in rendered_text
            ):
                return
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError(
                "child preview did not become "
                f"title={expected_title!r} snippet={expected_snippet!r}"
            )
        await asyncio.sleep(0.01)

async def _wait_for_parent_entries(
    app,
    expected_names: list[str],
    timeout: float = 0.5,
) -> None:
    await _wait_for_list_entries(app, "#parent-pane-list", expected_names, timeout=timeout)

async def _wait_for_external_launch_count(app, expected_count: int, timeout: float = 0.5) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        service = getattr(app, "_external_launch_service", None)
        executed_requests = getattr(service, "executed_requests", None)
        if executed_requests is not None and len(executed_requests) == expected_count:
            return
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError(f"external launches did not become {expected_count}")
        await asyncio.sleep(0.01)

async def _wait_for_request_count(service, expected_count: int, timeout: float = 0.5) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        if len(service.executed_requests) >= expected_count:
            return
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError(f"search request count did not reach {expected_count}")
        await asyncio.sleep(0.01)

async def _wait_for_file_search_results(
    app,
    expected_paths: list[str],
    timeout: float = 0.5,
) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        palette = app.app_state.command_palette
        actual_paths = (
            [result.display_path for result in palette.file_search.results]
            if palette is not None
            else None
        )
        if actual_paths == expected_paths:
            return
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError(f"file search results did not become {expected_paths!r}")
        await asyncio.sleep(0.01)

async def _wait_for_child_pane_request_count(
    loader,
    expected_count: int,
    timeout: float = 0.5,
) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        if len(loader.executed_child_pane_requests) >= expected_count:
            return
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError(f"child pane request count did not reach {expected_count}")
        await asyncio.sleep(0.01)

async def _wait_for_child_pane_runtime_idle(app, timeout: float = 0.5) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        pending_child_workers = [
            name for name in app._pending_workers if name.startswith("child-pane-snapshot:")
        ]
        if (
            app.app_state.pending_child_pane_request_id is None
            and app._child_pane_timer is None
            and not pending_child_workers
        ):
            # Let the message pump finish any refresh already scheduled by a completed worker
            # before the test context tears the app down.
            await asyncio.sleep(0.05)
            return
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError("child pane runtime did not become idle")
        await asyncio.sleep(0.01)

def _pane_visibility_app(path: str = str(Path("/tmp/zivo-pane-vis").resolve())):
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                (DirectoryEntryState(f"{path}/docs", "docs", "dir"),),
                child_path=f"{path}/docs",
            )
        }
    )
    return create_app(snapshot_loader=loader, initial_path=path)

_build_snapshot = build_snapshot
_wait_for_snapshot_loaded = wait_for_snapshot_loaded
