import asyncio
from contextlib import nullcontext
from pathlib import Path

import pytest
from rich.text import Text
from textual.css.query import NoMatches
from textual.widgets import DataTable, Label, ListView, Static

from plain import create_app
from plain.models import (
    ExternalLaunchRequest,
    FileMutationResult,
    PasteConflict,
    PasteConflictPrompt,
    PasteExecutionResult,
    PasteRequest,
    PasteSummary,
    TrashDeleteRequest,
)
from plain.services import (
    FakeBrowserSnapshotLoader,
    FakeClipboardOperationService,
    FakeExternalLaunchService,
    FakeFileMutationService,
)
from plain.state import BrowserSnapshot, DirectoryEntryState, PaneState
from plain.ui import (
    CommandPalette,
    ConflictDialog,
    CurrentPathBar,
    HelpBar,
    InputBar,
    StatusBar,
    SummaryBar,
)


def _build_snapshot(
    path: str,
    current_entries: tuple[DirectoryEntryState, ...],
    *,
    child_path: str | None = None,
    child_entries: tuple[DirectoryEntryState, ...] = (),
) -> BrowserSnapshot:
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


async def _wait_for_status_bar(app, timeout: float = 0.5) -> StatusBar:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        try:
            return app.query_one("#status-bar", StatusBar)
        except NoMatches:
            if asyncio.get_running_loop().time() >= deadline:
                raise
            await asyncio.sleep(0.01)


async def _wait_for_current_path_bar(app, timeout: float = 0.5) -> CurrentPathBar:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        try:
            return app.query_one("#current-path-bar", CurrentPathBar)
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


async def _wait_for_snapshot_loaded(app, expected_path: str, timeout: float = 0.5) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        if (
            app.app_state.current_path == expected_path
            and app.app_state.pending_browser_snapshot_request_id is None
            and app.app_state.current_pane.entries
        ):
            return
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError(f"snapshot did not finish for {expected_path}")
        await asyncio.sleep(0.01)


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


async def _wait_for_path(app, expected_path: str, timeout: float = 0.5) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        if (
            app.app_state.current_path == expected_path
            and app.app_state.pending_browser_snapshot_request_id is None
        ):
            return
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError(f"path did not become {expected_path}")
        await asyncio.sleep(0.01)


async def _wait_for_cursor_path(app, expected_path: str, timeout: float = 0.5) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        if app.app_state.current_pane.cursor_path == expected_path:
            return
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError(f"cursor path did not become {expected_path}")
        await asyncio.sleep(0.01)


async def _wait_for_child_entries(
    app,
    expected_names: list[str],
    timeout: float = 0.5,
) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        try:
            child_list = app.query_one("#child-pane-list", ListView)
        except NoMatches:
            child_list = None
        if child_list is not None:
            child_names = [str(item.query_one(Label).renderable) for item in child_list.children]
            if child_names == expected_names:
                return
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError(f"child entries did not become {expected_names}")
        await asyncio.sleep(0.01)


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


def test_create_app_returns_plain_app() -> None:
    app = create_app()

    assert app.title == "Plain"
    assert app.sub_title == "Three-pane shell"


@pytest.mark.asyncio
async def test_app_uses_cwd_for_default_initial_path(tmp_path, monkeypatch) -> None:
    current_entries = (
        DirectoryEntryState(f"{tmp_path}/docs", "docs", "dir"),
        DirectoryEntryState(f"{tmp_path}/README.md", "README.md", "file", size_bytes=20),
    )
    child_entries = (
        DirectoryEntryState(f"{tmp_path}/docs/spec.md", "spec.md", "file"),
    )
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            str(tmp_path): _build_snapshot(
                str(tmp_path),
                current_entries,
                child_path=f"{tmp_path}/docs",
                child_entries=child_entries,
            )
        }
    )
    monkeypatch.chdir(tmp_path)
    app = create_app(snapshot_loader=loader)

    async with app.run_test():
        await _wait_for_snapshot_loaded(app, str(tmp_path))
        await _wait_for_row_count(app, 2)
        current_path_bar = await _wait_for_current_path_bar(app)
        summary_bar = await _wait_for_summary_bar(app)
        status_bar = await _wait_for_status_bar(app)

        assert str(current_path_bar.renderable) == f"Current Path: {tmp_path}"
        assert str(summary_bar.renderable) == (
            "2 items | 0 selected | sort: name asc dirs:on"
        )
        assert str(status_bar.renderable) == ""


@pytest.mark.asyncio
async def test_app_renders_loaded_three_pane_shell() -> None:
    path = "/tmp/plain-app"
    current_entries = (
        DirectoryEntryState(f"{path}/docs", "docs", "dir"),
        DirectoryEntryState(f"{path}/README.md", "README.md", "file", size_bytes=120),
    )
    child_entries = (
        DirectoryEntryState(f"{path}/docs/spec.md", "spec.md", "file"),
    )
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                current_entries,
                child_path=f"{path}/docs",
                child_entries=child_entries,
            )
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test():
        await _wait_for_snapshot_loaded(app, path)
        await _wait_for_row_count(app, 2)

        parent_list = app.query_one("#parent-pane-list", ListView)
        current_table = app.query_one("#current-pane-table", DataTable)
        child_list = app.query_one("#child-pane-list", ListView)
        parent_title = app.query_one("#parent-pane .pane-title", Label)
        current_title = app.query_one("#current-pane .pane-title", Label)
        child_title = app.query_one("#child-pane .pane-title", Label)
        current_path_bar = await _wait_for_current_path_bar(app)
        summary_bar = await _wait_for_summary_bar(app)
        status_bar = await _wait_for_status_bar(app)
        parent_entries = [str(item.query_one(Label).renderable) for item in parent_list.children]
        child_entries = [str(item.query_one(Label).renderable) for item in child_list.children]
        headers = [str(column.label) for column in current_table.ordered_columns]

        assert str(parent_title.renderable) == "Parent Directory"
        assert str(current_title.renderable) == "Current Directory"
        assert str(child_title.renderable) == "Child Directory"
        assert parent_entries == ["plain-app", "sibling"]
        assert headers == ["Sel", "Type", "Name", "Size", "Modified"]
        assert current_table.row_count == 2
        assert child_entries == ["spec.md"]
        assert str(current_path_bar.renderable) == f"Current Path: {path}"
        assert str(summary_bar.renderable) == (
            "2 items | 0 selected | sort: name asc dirs:on"
        )
        assert str(status_bar.renderable) == ""


@pytest.mark.asyncio
async def test_app_can_start_in_narrow_headless_mode() -> None:
    path = "/tmp/plain-narrow"
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                (DirectoryEntryState(f"{path}/docs", "docs", "dir"),),
                child_path=f"{path}/docs",
            )
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test(size=(72, 20)):
        await _wait_for_snapshot_loaded(app, path)
        await _wait_for_row_count(app, 1)
        assert app.query_one("#body")


@pytest.mark.asyncio
async def test_app_tab_keeps_focus_on_current_pane() -> None:
    path = "/tmp/plain-tab-focus"
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                (
                    DirectoryEntryState(f"{path}/docs", "docs", "dir"),
                    DirectoryEntryState(
                        f"{path}/README.md",
                        "README.md",
                        "file",
                        size_bytes=120,
                    ),
                ),
                child_path=f"{path}/docs",
                child_entries=(DirectoryEntryState(f"{path}/docs/spec.md", "spec.md", "file"),),
            )
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await _wait_for_row_count(app, 2)

        parent_list = app.query_one("#parent-pane-list", ListView)
        current_table = app.query_one("#current-pane-table", DataTable)
        child_list = app.query_one("#child-pane-list", ListView)

        assert parent_list.can_focus is False
        assert child_list.can_focus is False
        assert app.focused is current_table

        await pilot.press("tab", "tab")
        await asyncio.sleep(0.05)

        assert app.focused is current_table


@pytest.mark.asyncio
async def test_app_keyboard_input_updates_selection_and_child_pane() -> None:
    path = "/tmp/plain-keyboard"
    current_entries = (
        DirectoryEntryState(f"{path}/docs", "docs", "dir"),
        DirectoryEntryState(f"{path}/src", "src", "dir"),
        DirectoryEntryState(f"{path}/README.md", "README.md", "file", size_bytes=120),
    )
    docs_child_entries = (
        DirectoryEntryState(f"{path}/docs/spec.md", "spec.md", "file"),
    )
    src_child_entries = (
        DirectoryEntryState(f"{path}/src/main.py", "main.py", "file"),
    )
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                current_entries,
                child_path=f"{path}/docs",
                child_entries=docs_child_entries,
            )
        },
        child_panes={
            (path, f"{path}/src"): PaneState(
                directory_path=f"{path}/src",
                entries=src_child_entries,
            )
        },
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await _wait_for_row_count(app, 3)
        await pilot.press("space")
        await asyncio.sleep(0.05)

        child_list = app.query_one("#child-pane-list", ListView)
        child_names = [str(item.query_one(Label).renderable) for item in child_list.children]
        current_path_bar = await _wait_for_current_path_bar(app)
        summary_bar = await _wait_for_summary_bar(app)
        status_bar = await _wait_for_status_bar(app)

        assert app.app_state.current_pane.selected_paths == {f"{path}/docs"}
        assert app.app_state.current_pane.cursor_path == f"{path}/src"
        assert child_names == ["main.py"]
        assert str(current_path_bar.renderable) == f"Current Path: {path}"
        assert str(summary_bar.renderable) == (
            "3 items | 1 selected | sort: name asc dirs:on"
        )
        assert str(status_bar.renderable) == ""

        current_table = app.query_one("#current-pane-table", DataTable)
        first_row = current_table.get_row_at(0)

        assert isinstance(first_row[0], Text)
        assert first_row[0].plain == "*"
        assert first_row[0].style == "bold green"
        assert first_row[2].plain == "docs"


@pytest.mark.asyncio
async def test_app_cut_marks_row_with_dimmed_style() -> None:
    path = "/tmp/plain-cut"
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                (
                    DirectoryEntryState(f"{path}/docs", "docs", "dir"),
                    DirectoryEntryState(f"{path}/README.md", "README.md", "file", size_bytes=120),
                ),
                child_path=f"{path}/docs",
            )
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await _wait_for_row_count(app, 2)
        await pilot.press("x")
        await asyncio.sleep(0.05)

        current_table = app.query_one("#current-pane-table", DataTable)
        first_row = current_table.get_row_at(0)

        assert app.app_state.clipboard.mode == "cut"
        assert app.app_state.clipboard.paths == (f"{path}/docs",)
        assert isinstance(first_row[2], Text)
        assert first_row[2].plain == "docs"
        assert first_row[2].style == "bright_black dim"


@pytest.mark.asyncio
async def test_app_right_enters_directory_and_backspace_returns_to_parent() -> None:
    root = "/tmp/plain-nav"
    docs = f"{root}/docs"
    root_entries = (
        DirectoryEntryState(docs, "docs", "dir"),
        DirectoryEntryState(f"{root}/README.md", "README.md", "file", size_bytes=120),
    )
    docs_entries = (
        DirectoryEntryState(f"{docs}/guide.md", "guide.md", "file", size_bytes=42),
    )
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            root: _build_snapshot(
                root,
                root_entries,
                child_path=docs,
                child_entries=docs_entries,
            ),
            docs: BrowserSnapshot(
                current_path=docs,
                parent_pane=PaneState(
                    directory_path=root,
                    entries=root_entries,
                    cursor_path=docs,
                ),
                current_pane=PaneState(
                    directory_path=docs,
                    entries=docs_entries,
                    cursor_path=f"{docs}/guide.md",
                ),
                child_pane=PaneState(directory_path=docs, entries=()),
            ),
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=root)

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, root)
        current_path_bar = await _wait_for_current_path_bar(app)
        assert str(current_path_bar.renderable) == f"Current Path: {root}"

        await pilot.press("right")
        await _wait_for_path(app, docs)
        assert str(current_path_bar.renderable) == f"Current Path: {docs}"

        current_table = app.query_one("#current-pane-table", DataTable)
        assert app.app_state.current_path == docs
        assert current_table.cursor_row == 0

        await pilot.press("backspace")
        await _wait_for_path(app, root)
        assert str(current_path_bar.renderable) == f"Current Path: {root}"

        assert app.app_state.current_path == root
        assert app.app_state.current_pane.cursor_path == docs
        assert current_table.cursor_row == 0


@pytest.mark.asyncio
async def test_app_backspace_can_move_above_initial_directory() -> None:
    initial_path = "/tmp/plain-nav/deeper"
    parent_path = "/tmp/plain-nav"
    grandparent_path = "/tmp"
    parent_entries = (
        DirectoryEntryState(initial_path, "deeper", "dir"),
        DirectoryEntryState(f"{parent_path}/sibling", "sibling", "dir"),
    )
    grandparent_entries = (
        DirectoryEntryState(parent_path, "plain-nav", "dir"),
        DirectoryEntryState("/tmp/other", "other", "dir"),
    )
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            initial_path: BrowserSnapshot(
                current_path=initial_path,
                parent_pane=PaneState(
                    directory_path=parent_path,
                    entries=parent_entries,
                    cursor_path=initial_path,
                ),
                current_pane=PaneState(
                    directory_path=initial_path,
                    entries=(DirectoryEntryState(f"{initial_path}/file.txt", "file.txt", "file"),),
                    cursor_path=f"{initial_path}/file.txt",
                ),
                child_pane=PaneState(directory_path=initial_path, entries=()),
            ),
            parent_path: BrowserSnapshot(
                current_path=parent_path,
                parent_pane=PaneState(
                    directory_path=grandparent_path,
                    entries=grandparent_entries,
                    cursor_path=parent_path,
                ),
                current_pane=PaneState(
                    directory_path=parent_path,
                    entries=parent_entries,
                    cursor_path=initial_path,
                ),
                child_pane=PaneState(directory_path=initial_path, entries=()),
            ),
            grandparent_path: BrowserSnapshot(
                current_path=grandparent_path,
                parent_pane=PaneState(
                    directory_path="/",
                    entries=(DirectoryEntryState("/tmp", "tmp", "dir"),),
                    cursor_path=grandparent_path,
                ),
                current_pane=PaneState(
                    directory_path=grandparent_path,
                    entries=grandparent_entries,
                    cursor_path=parent_path,
                ),
                child_pane=PaneState(directory_path=parent_path, entries=()),
            ),
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=initial_path)

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, initial_path)
        await pilot.press("backspace")
        await _wait_for_path(app, parent_path)
        await pilot.press("left")
        await _wait_for_path(app, grandparent_path)

        assert app.app_state.current_pane.cursor_path == parent_path


@pytest.mark.asyncio
async def test_app_f5_keeps_cursor_when_entry_still_exists() -> None:
    path = "/tmp/plain-reload"
    initial_entries = (
        DirectoryEntryState(f"{path}/docs", "docs", "dir"),
        DirectoryEntryState(f"{path}/src", "src", "dir"),
    )
    reloaded_entries = (
        DirectoryEntryState(f"{path}/docs", "docs", "dir"),
        DirectoryEntryState(f"{path}/src", "src", "dir"),
        DirectoryEntryState(f"{path}/tests", "tests", "dir"),
    )
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                initial_entries,
                child_path=f"{path}/docs",
                child_entries=(DirectoryEntryState(f"{path}/docs/spec.md", "spec.md", "file"),),
            )
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await pilot.press("down")
        await asyncio.sleep(0.05)

        loader.snapshots[path] = _build_snapshot(
            path,
            reloaded_entries,
            child_path=f"{path}/src",
            child_entries=(DirectoryEntryState(f"{path}/src/main.py", "main.py", "file"),),
        )

        await pilot.press("f5")
        await _wait_for_snapshot_loaded(app, path)

        current_table = app.query_one("#current-pane-table", DataTable)
        assert app.app_state.current_pane.cursor_path == f"{path}/src"
        assert current_table.cursor_row == 1


@pytest.mark.asyncio
async def test_app_f5_falls_back_to_first_row_when_cursor_disappears() -> None:
    path = "/tmp/plain-reload-fallback"
    initial_entries = (
        DirectoryEntryState(f"{path}/docs", "docs", "dir"),
        DirectoryEntryState(f"{path}/src", "src", "dir"),
    )
    reloaded_entries = (
        DirectoryEntryState(f"{path}/docs", "docs", "dir"),
    )
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                initial_entries,
                child_path=f"{path}/docs",
                child_entries=(DirectoryEntryState(f"{path}/docs/spec.md", "spec.md", "file"),),
            )
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await pilot.press("down")
        await asyncio.sleep(0.05)

        loader.snapshots[path] = _build_snapshot(
            path,
            reloaded_entries,
            child_path=f"{path}/docs",
            child_entries=(DirectoryEntryState(f"{path}/docs/spec.md", "spec.md", "file"),),
        )

        await pilot.press("f5")
        await _wait_for_snapshot_loaded(app, path)

        current_table = app.query_one("#current-pane-table", DataTable)
        assert app.app_state.current_pane.cursor_path == f"{path}/docs"
        assert current_table.cursor_row == 0


@pytest.mark.asyncio
async def test_app_f5_drops_selection_for_missing_entries() -> None:
    path = "/tmp/plain-reload-selection"
    initial_entries = (
        DirectoryEntryState(f"{path}/docs", "docs", "dir"),
        DirectoryEntryState(f"{path}/src", "src", "dir"),
    )
    reloaded_entries = (
        DirectoryEntryState(f"{path}/src", "src", "dir"),
    )
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                initial_entries,
                child_path=f"{path}/docs",
                child_entries=(DirectoryEntryState(f"{path}/docs/spec.md", "spec.md", "file"),),
            )
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await pilot.press("space")
        await asyncio.sleep(0.05)

        loader.snapshots[path] = _build_snapshot(
            path,
            reloaded_entries,
            child_path=f"{path}/src",
            child_entries=(DirectoryEntryState(f"{path}/src/main.py", "main.py", "file"),),
        )

        await pilot.press("f5")
        await _wait_for_snapshot_loaded(app, path)

        summary_bar = await _wait_for_summary_bar(app)
        status_bar = await _wait_for_status_bar(app)

        assert app.app_state.current_pane.selected_paths == set()
        assert app.app_state.current_pane.cursor_path == f"{path}/src"
        assert str(summary_bar.renderable) == (
            "1 items | 0 selected | sort: name asc dirs:on"
        )
        assert str(status_bar.renderable) == ""


@pytest.mark.asyncio
async def test_app_navigation_clears_selection_in_new_directory() -> None:
    root = "/tmp/plain-selection-nav"
    docs = f"{root}/docs"
    root_entries = (
        DirectoryEntryState(docs, "docs", "dir"),
    )
    docs_entries = (
        DirectoryEntryState(f"{docs}/guide.md", "guide.md", "file", size_bytes=42),
    )
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            root: _build_snapshot(
                root,
                root_entries,
                child_path=docs,
                child_entries=docs_entries,
            ),
            docs: BrowserSnapshot(
                current_path=docs,
                parent_pane=PaneState(
                    directory_path=root,
                    entries=root_entries,
                    cursor_path=docs,
                ),
                current_pane=PaneState(
                    directory_path=docs,
                    entries=docs_entries,
                    cursor_path=f"{docs}/guide.md",
                ),
                child_pane=PaneState(directory_path=docs, entries=()),
            ),
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=root)

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, root)
        await pilot.press("space")
        await asyncio.sleep(0.05)
        await pilot.press("right")
        await _wait_for_path(app, docs)

        summary_bar = await _wait_for_summary_bar(app)
        status_bar = await _wait_for_status_bar(app)

        assert app.app_state.current_pane.selected_paths == set()
        assert app.app_state.current_path == docs
        assert str(summary_bar.renderable) == (
            "1 items | 0 selected | sort: name asc dirs:on"
        )
        assert str(status_bar.renderable) == ""


@pytest.mark.asyncio
async def test_app_refresh_updates_widgets_in_place() -> None:
    path = "/tmp/plain-refresh"
    current_entries = (
        DirectoryEntryState(f"{path}/docs", "docs", "dir"),
        DirectoryEntryState(f"{path}/src", "src", "dir"),
    )
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                current_entries,
                child_path=f"{path}/docs",
                child_entries=(DirectoryEntryState(f"{path}/docs/spec.md", "spec.md", "file"),),
            )
        },
        child_panes={
            (path, f"{path}/src"): PaneState(
                directory_path=f"{path}/src",
                entries=(DirectoryEntryState(f"{path}/src/main.py", "main.py", "file"),),
            )
        },
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await _wait_for_row_count(app, 2)

        body = app.query_one("#body")
        current_path_bar = app.query_one("#current-path-bar", CurrentPathBar)
        summary_bar = app.query_one("#current-pane-summary-bar", SummaryBar)
        status_bar = app.query_one("#status-bar", StatusBar)
        current_table = app.query_one("#current-pane-table", DataTable)
        child_list = app.query_one("#child-pane-list", ListView)

        await pilot.press("down")
        await asyncio.sleep(0.05)

        assert app.query_one("#body") is body
        assert app.query_one("#current-path-bar", CurrentPathBar) is current_path_bar
        assert app.query_one("#current-pane-summary-bar", SummaryBar) is summary_bar
        assert app.query_one("#status-bar", StatusBar) is status_bar
        assert app.query_one("#current-pane-table", DataTable) is current_table
        assert app.query_one("#child-pane-list", ListView) is child_list


@pytest.mark.asyncio
async def test_app_refresh_keeps_parent_pane_items_when_entries_are_unchanged() -> None:
    path = "/tmp/plain-parent-stable"
    current_entries = (
        DirectoryEntryState(f"{path}/docs", "docs", "dir"),
        DirectoryEntryState(f"{path}/src", "src", "dir"),
    )
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                current_entries,
                child_path=f"{path}/docs",
                child_entries=(DirectoryEntryState(f"{path}/docs/spec.md", "spec.md", "file"),),
            )
        },
        child_panes={
            (path, f"{path}/src"): PaneState(
                directory_path=f"{path}/src",
                entries=(DirectoryEntryState(f"{path}/src/main.py", "main.py", "file"),),
            )
        },
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await _wait_for_row_count(app, 2)

        parent_list = app.query_one("#parent-pane-list", ListView)
        parent_items = tuple(parent_list.children)

        await pilot.press("down")
        await asyncio.sleep(0.05)

        assert tuple(app.query_one("#parent-pane-list", ListView).children) == parent_items


@pytest.mark.asyncio
async def test_app_file_cursor_clears_child_pane() -> None:
    path = "/tmp/plain-file"
    current_entries = (
        DirectoryEntryState(f"{path}/docs", "docs", "dir"),
        DirectoryEntryState(f"{path}/README.md", "README.md", "file", size_bytes=120),
    )
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                current_entries,
                child_path=f"{path}/docs",
                child_entries=(DirectoryEntryState(f"{path}/docs/spec.md", "spec.md", "file"),),
            )
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await _wait_for_row_count(app, 2)
        await pilot.press("down")
        await asyncio.sleep(0.05)

        child_list = app.query_one("#child-pane-list", ListView)

        assert app.app_state.current_pane.cursor_path == f"{path}/README.md"
        assert list(child_list.children) == []


@pytest.mark.asyncio
async def test_app_child_snapshot_failure_shows_error() -> None:
    path = "/tmp/plain-failure"
    current_entries = (
        DirectoryEntryState(f"{path}/docs", "docs", "dir"),
        DirectoryEntryState(f"{path}/src", "src", "dir"),
    )
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                current_entries,
                child_path=f"{path}/docs",
                child_entries=(DirectoryEntryState(f"{path}/docs/spec.md", "spec.md", "file"),),
            )
        },
        child_failure_messages={(path, f"{path}/src"): "permission denied"},
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await _wait_for_row_count(app, 2)
        await pilot.press("down")
        await asyncio.sleep(0.05)

        child_list = app.query_one("#child-pane-list", ListView)
        current_path_bar = await _wait_for_current_path_bar(app)
        summary_bar = await _wait_for_summary_bar(app)
        status_bar = await _wait_for_status_bar(app)

        assert list(child_list.children) == []
        assert str(current_path_bar.renderable) == f"Current Path: {path}"
        assert str(summary_bar.renderable) == "2 items | 0 selected | sort: name asc dirs:on"
        assert str(status_bar.renderable) == "error: permission denied"


@pytest.mark.asyncio
async def test_app_displays_browsing_help_bar() -> None:
    path = "/tmp/plain-help"
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                (DirectoryEntryState(f"{path}/docs", "docs", "dir"),),
                child_path=f"{path}/docs",
            )
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test():
        await _wait_for_snapshot_loaded(app, path)
        await asyncio.sleep(0.05)
        help_bar = app.query_one("#help-bar", HelpBar)

        assert str(help_bar.renderable) == (
            "Enter open | e edit | / filter | Space select | y copy | x cut | p paste | "
            "s sort | d dirs | F2 rename | : palette"
        )


@pytest.mark.asyncio
async def test_app_colon_shows_command_palette() -> None:
    path = "/tmp/plain-command-palette"
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                (DirectoryEntryState(f"{path}/docs", "docs", "dir"),),
                child_path=f"{path}/docs",
            )
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await pilot.press(":")
        await asyncio.sleep(0.05)

        palette = await _wait_for_command_palette(app)
        items = palette.query_one("#command-palette-items", Static)

        assert app.app_state.ui_mode == "PALETTE"
        assert palette.display is True
        assert "Create file" in str(items.renderable)


@pytest.mark.asyncio
async def test_app_command_palette_create_file_opens_context_input() -> None:
    path = "/tmp/plain-command-palette-create"
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                (DirectoryEntryState(f"{path}/docs", "docs", "dir"),),
                child_path=f"{path}/docs",
            )
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await pilot.press(":")
        await pilot.press("enter")
        await asyncio.sleep(0.05)

        input_bar = await _wait_for_context_input(app)

        assert app.app_state.ui_mode == "CREATE"
        assert input_bar.display is True
        assert str(input_bar.renderable) == "[NEW FILE] New file: _  enter apply | esc cancel"


@pytest.mark.asyncio
async def test_app_command_palette_toggles_hidden_files() -> None:
    path = "/tmp/plain-command-palette-hidden"
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                (
                    DirectoryEntryState(f"{path}/docs", "docs", "dir"),
                    DirectoryEntryState(f"{path}/.env", ".env", "file", hidden=True),
                ),
                child_path=f"{path}/docs",
            )
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await _wait_for_row_count(app, 1)
        await pilot.press(":")
        await pilot.press("h", "i", "d", "d", "e", "n")
        await pilot.press("enter")
        await _wait_for_row_count(app, 2)

        assert app.app_state.show_hidden is True

        status_bar = await _wait_for_status_bar(app)
        assert "info: Hidden files shown" in str(status_bar.renderable)

        await pilot.press(":")
        await pilot.press("h", "i", "d", "d", "e", "n")
        await pilot.press("enter")
        await _wait_for_row_count(app, 1)

        assert app.app_state.show_hidden is False


@pytest.mark.asyncio
async def test_app_enter_on_file_launches_default_app() -> None:
    path = "/tmp/plain-open-file"
    launch_service = FakeExternalLaunchService()
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                (
                    DirectoryEntryState(f"{path}/docs", "docs", "dir"),
                    DirectoryEntryState(f"{path}/README.md", "README.md", "file"),
                ),
                child_path=f"{path}/docs",
            )
        }
    )
    app = create_app(
        snapshot_loader=loader,
        external_launch_service=launch_service,
        initial_path=path,
    )

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await pilot.press("down")
        await pilot.press("enter")
        await _wait_for_external_launch_count(app, 1)

        assert launch_service.executed_requests == [
            ExternalLaunchRequest(kind="open_file", path=f"{path}/README.md")
        ]
        assert app.app_state.ui_mode == "BROWSING"


@pytest.mark.asyncio
async def test_app_command_palette_copy_path_copies_cursor_target() -> None:
    path = "/tmp/plain-copy-path"
    copied_text: list[str] = []
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                (
                    DirectoryEntryState(f"{path}/docs", "docs", "dir"),
                    DirectoryEntryState(f"{path}/README.md", "README.md", "file"),
                ),
                child_path=f"{path}/docs",
            )
        }
    )
    app = create_app(
        snapshot_loader=loader,
        initial_path=path,
    )
    app.copy_to_clipboard = copied_text.append  # type: ignore[method-assign]

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await pilot.press(":")
        await pilot.press("c", "o", "p", "y")
        await pilot.press("enter")
        await asyncio.sleep(0.05)

        assert copied_text == [f"{path}/docs"]

        status_bar = await _wait_for_status_bar(app)
        assert "info: Copied 1 path to system clipboard" in str(status_bar.renderable)


@pytest.mark.asyncio
async def test_app_command_palette_open_terminal_launches_current_directory() -> None:
    path = "/tmp/plain-open-terminal"
    launch_service = FakeExternalLaunchService()
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                (
                    DirectoryEntryState(f"{path}/docs", "docs", "dir"),
                    DirectoryEntryState(f"{path}/README.md", "README.md", "file"),
                ),
                child_path=f"{path}/docs",
            )
        }
    )
    app = create_app(
        snapshot_loader=loader,
        external_launch_service=launch_service,
        initial_path=path,
    )

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await pilot.press(":")
        await pilot.press("t", "e", "r", "m", "i", "n", "a", "l")
        await pilot.press("enter")
        await _wait_for_external_launch_count(app, 1)

        assert launch_service.executed_requests == [
            ExternalLaunchRequest(kind="open_terminal", path=path)
        ]
        assert app.app_state.ui_mode == "BROWSING"


@pytest.mark.asyncio
async def test_app_pressing_e_launches_editor_for_file() -> None:
    path = "/tmp/plain-open-editor"
    launch_service = FakeExternalLaunchService()
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                (
                    DirectoryEntryState(f"{path}/docs", "docs", "dir"),
                    DirectoryEntryState(f"{path}/README.md", "README.md", "file"),
                ),
                child_path=f"{path}/docs",
            )
        }
    )
    app = create_app(
        snapshot_loader=loader,
        external_launch_service=launch_service,
        initial_path=path,
    )
    app.suspend = nullcontext  # type: ignore[method-assign]

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await pilot.press("down")
        await pilot.press("e")
        await _wait_for_external_launch_count(app, 1)

        assert launch_service.executed_requests == [
            ExternalLaunchRequest(kind="open_editor", path=f"{path}/README.md")
        ]
        assert app.app_state.ui_mode == "BROWSING"


@pytest.mark.asyncio
async def test_app_pressing_e_refreshes_after_editor_returns() -> None:
    path = "/tmp/plain-open-editor-refresh"
    launch_service = FakeExternalLaunchService()
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                (
                    DirectoryEntryState(f"{path}/docs", "docs", "dir"),
                    DirectoryEntryState(f"{path}/README.md", "README.md", "file"),
                ),
                child_path=f"{path}/docs",
            )
        }
    )
    app = create_app(
        snapshot_loader=loader,
        external_launch_service=launch_service,
        initial_path=path,
    )
    app.suspend = nullcontext  # type: ignore[method-assign]

    refresh_calls: list[tuple[bool, bool, bool]] = []
    original_refresh = app.refresh

    def tracked_refresh(*, repaint: bool = True, layout: bool = False, recompose: bool = False):
        refresh_calls.append((repaint, layout, recompose))
        return original_refresh(repaint=repaint, layout=layout, recompose=recompose)

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, path)
        app.refresh = tracked_refresh  # type: ignore[method-assign]
        await pilot.press("down")
        await pilot.press("e")
        await _wait_for_external_launch_count(app, 1)

        assert (True, True, False) in refresh_calls


@pytest.mark.asyncio
async def test_app_external_launch_failure_surfaces_error_notification() -> None:
    path = "/tmp/plain-open-failure"
    request = ExternalLaunchRequest(kind="open_file", path=f"{path}/README.md")
    launch_service = FakeExternalLaunchService(
        failure_messages={request: "Failed to open /tmp/plain-open-failure/README.md: denied"}
    )
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                (
                    DirectoryEntryState(f"{path}/docs", "docs", "dir"),
                    DirectoryEntryState(f"{path}/README.md", "README.md", "file"),
                ),
                child_path=f"{path}/docs",
            )
        }
    )
    app = create_app(
        snapshot_loader=loader,
        external_launch_service=launch_service,
        initial_path=path,
    )

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await pilot.press("down")
        await pilot.press("enter")
        await _wait_for_external_launch_count(app, 1)

        status_bar = await _wait_for_status_bar(app)
        assert "error: Failed to open /tmp/plain-open-failure/README.md: denied" in str(
            status_bar.renderable
        )


@pytest.mark.asyncio
async def test_app_sort_shortcuts_keep_side_panes_fixed_and_update_status_bar() -> None:
    path = "/tmp/plain-sort-shortcuts"
    parent_path = "/tmp"
    child_path = f"{path}/zeta"
    snapshot = BrowserSnapshot(
        current_path=path,
        parent_pane=PaneState(
            directory_path=parent_path,
            entries=(
                DirectoryEntryState(f"{parent_path}/beta.txt", "beta.txt", "file"),
                DirectoryEntryState(f"{parent_path}/alpha", "alpha", "dir"),
                DirectoryEntryState(path, "plain-sort-shortcuts", "dir"),
            ),
            cursor_path=path,
        ),
        current_pane=PaneState(
            directory_path=path,
            entries=(
                DirectoryEntryState(f"{path}/zeta", "zeta", "dir"),
                DirectoryEntryState(f"{path}/alpha.txt", "alpha.txt", "file", size_bytes=10),
                DirectoryEntryState(f"{path}/beta", "beta", "dir"),
            ),
            cursor_path=f"{path}/zeta",
        ),
        child_pane=PaneState(
            directory_path=child_path,
            entries=(
                DirectoryEntryState(f"{child_path}/notes.txt", "notes.txt", "file", size_bytes=5),
                DirectoryEntryState(f"{child_path}/archive", "archive", "dir"),
            ),
        ),
    )
    loader = FakeBrowserSnapshotLoader(snapshots={path: snapshot})
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await _wait_for_row_count(app, 3)

        await pilot.press("d")
        await pilot.press("s")
        await asyncio.sleep(0.05)

        parent_list = app.query_one("#parent-pane-list", ListView)
        child_list = app.query_one("#child-pane-list", ListView)
        summary_bar = await _wait_for_summary_bar(app)

        assert app.app_state.sort.field == "name"
        assert app.app_state.sort.descending is True
        assert app.app_state.sort.directories_first is False
        assert [str(item.query_one(Label).renderable) for item in parent_list.children] == [
            "alpha",
            "plain-sort-shortcuts",
            "beta.txt",
        ]
        assert [str(item.query_one(Label).renderable) for item in child_list.children] == [
            "archive",
            "notes.txt",
        ]
        assert str(summary_bar.renderable) == (
            "3 items | 0 selected | sort: name desc dirs:off"
        )


@pytest.mark.asyncio
async def test_app_filter_mode_accepts_printable_bound_keys() -> None:
    path = "/tmp/plain-filter-keys"
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                (DirectoryEntryState(f"{path}/docs", "docs", "dir"),),
                child_path=f"{path}/docs",
            )
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await pilot.press("/")
        await pilot.press("y", "x", "p")
        await asyncio.sleep(0.05)

        input_bar = await _wait_for_context_input(app)

        assert app.app_state.ui_mode == "FILTER"
        assert app.app_state.filter.query == "yxp"
        assert str(input_bar.renderable) == "[FILTER] Filter: yxp  enter/down apply | esc clear"


@pytest.mark.asyncio
async def test_app_confirmed_filter_stays_visible_in_current_pane() -> None:
    path = "/tmp/plain-filter-confirm"
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                (
                    DirectoryEntryState(f"{path}/docs", "docs", "dir"),
                    DirectoryEntryState(f"{path}/notes.txt", "notes.txt", "file"),
                ),
                child_path=f"{path}/docs",
            )
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await pilot.press("/")
        await pilot.press("d", "o", "c", "s")
        await pilot.press("enter")
        await asyncio.sleep(0.05)

        input_bar = await _wait_for_context_input(app)

        assert app.app_state.ui_mode == "BROWSING"
        assert app.app_state.filter.active is True
        assert app.app_state.filter.query == "docs"
        assert input_bar.display is True
        assert str(input_bar.renderable) == "[FILTER] Filter: docs  esc clear"


@pytest.mark.asyncio
async def test_app_filter_down_confirms_and_returns_to_browsing() -> None:
    path = "/tmp/plain-filter-down"
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                (
                    DirectoryEntryState(f"{path}/docs", "docs", "dir"),
                    DirectoryEntryState(f"{path}/notes.txt", "notes.txt", "file"),
                ),
                child_path=f"{path}/docs",
            )
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await pilot.press("/")
        await pilot.press("d", "o", "c", "s")
        await pilot.press("down")
        await asyncio.sleep(0.05)

        input_bar = await _wait_for_context_input(app)

        assert app.app_state.ui_mode == "BROWSING"
        assert app.app_state.filter.active is True
        assert app.app_state.filter.query == "docs"
        assert input_bar.display is True
        assert str(input_bar.renderable) == "[FILTER] Filter: docs  esc clear"


@pytest.mark.asyncio
async def test_app_escape_clears_active_filter_before_selection() -> None:
    path = "/tmp/plain-filter-escape-priority"
    docs = f"{path}/docs"
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                (
                    DirectoryEntryState(docs, "docs", "dir"),
                    DirectoryEntryState(f"{path}/notes.txt", "notes.txt", "file"),
                ),
                child_path=docs,
            )
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await pilot.press("/")
        await pilot.press("d", "o", "c", "s", "enter")
        await pilot.press("space")
        await pilot.press("escape")
        await asyncio.sleep(0.05)

        input_bar = await _wait_for_context_input(app)

        assert app.app_state.filter.query == ""
        assert app.app_state.filter.active is False
        assert app.app_state.current_pane.selected_paths == {docs}
        assert input_bar.display is False



@pytest.mark.asyncio
async def test_app_rename_mode_shows_context_input_and_updates_help() -> None:
    path = "/tmp/plain-rename-mode"
    docs = f"{path}/docs"
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                (DirectoryEntryState(docs, "docs", "dir"),),
                child_path=docs,
            )
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await pilot.press("f2")
        await asyncio.sleep(0.05)

        help_bar = app.query_one("#help-bar", HelpBar)
        input_bar = await _wait_for_context_input(app)

        assert app.app_state.ui_mode == "RENAME"
        assert str(help_bar.renderable) == "type name | enter apply | esc cancel"
        assert input_bar.display is True
        assert str(input_bar.renderable) == "[RENAME] Rename: docs  enter apply | esc cancel"


@pytest.mark.asyncio
async def test_app_rename_name_conflict_dialog_returns_to_input(tmp_path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "src").mkdir()
    app = create_app(initial_path=tmp_path)

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, str(tmp_path))
        await pilot.press("f2")
        await asyncio.sleep(0.05)
        for _ in range(4):
            await pilot.press("backspace")
        await pilot.press("s", "r", "c", "enter")
        await asyncio.sleep(0.05)

        help_bar = app.query_one("#help-bar", HelpBar)
        dialog = app.query_one("#conflict-dialog", ConflictDialog)

        assert app.app_state.ui_mode == "CONFIRM"
        assert str(help_bar.renderable) == "enter return to input | esc return to input"
        assert dialog.display is True

        await pilot.press("enter")
        await asyncio.sleep(0.05)

        input_bar = await _wait_for_context_input(app)

        assert app.app_state.ui_mode == "RENAME"
        assert dialog.display is False
        assert str(input_bar.renderable) == "[RENAME] Rename: src  enter apply | esc cancel"


@pytest.mark.asyncio
async def test_app_rename_round_trip_updates_status_bar(tmp_path) -> None:
    (tmp_path / "docs").mkdir()
    app = create_app(initial_path=tmp_path)

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, str(tmp_path))
        await pilot.press("f2")
        await asyncio.sleep(0.05)
        for _ in range(4):
            await pilot.press("backspace")
        await pilot.press("m", "a", "n", "u", "a", "l", "s", "enter")
        await asyncio.sleep(0.1)

        status_bar = await _wait_for_status_bar(app)

        assert (tmp_path / "manuals").is_dir()
        assert app.app_state.ui_mode == "BROWSING"
        assert str(status_bar.renderable) == "info: Renamed to manuals"


@pytest.mark.asyncio
async def test_app_create_name_conflict_dialog_returns_to_input(tmp_path) -> None:
    (tmp_path / "docs").mkdir()
    app = create_app(initial_path=tmp_path)

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, str(tmp_path))
        await pilot.press(":")
        await pilot.press("enter")
        await asyncio.sleep(0.05)
        await pilot.press("d", "o", "c", "s", "enter")
        await asyncio.sleep(0.05)

        help_bar = app.query_one("#help-bar", HelpBar)
        dialog = app.query_one("#conflict-dialog", ConflictDialog)

        assert app.app_state.ui_mode == "CONFIRM"
        assert str(help_bar.renderable) == "enter return to input | esc return to input"
        assert dialog.display is True

        await pilot.press("escape")
        await asyncio.sleep(0.05)

        input_bar = await _wait_for_context_input(app)

        assert app.app_state.ui_mode == "CREATE"
        assert dialog.display is False
        assert str(input_bar.renderable) == "[NEW FILE] New file: docs  enter apply | esc cancel"


@pytest.mark.asyncio
async def test_app_paste_conflict_dialog_round_trip() -> None:
    path = "/tmp/plain-paste-conflict"
    docs = f"{path}/docs"
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                (DirectoryEntryState(docs, "docs", "dir"),),
                child_path=docs,
            )
        }
    )
    initial_request = PasteRequest(
        mode="copy",
        source_paths=(docs,),
        destination_dir=path,
    )
    rename_request = PasteRequest(
        mode="copy",
        source_paths=(docs,),
        destination_dir=path,
        conflict_resolution="rename",
    )
    clipboard_service = FakeClipboardOperationService(
        results={
            initial_request: PasteConflictPrompt(
                request=initial_request,
                conflicts=(PasteConflict(source_path=docs, destination_path=docs),),
            ),
            rename_request: PasteExecutionResult(
                summary=PasteSummary(
                    mode="copy",
                    destination_dir=path,
                    total_count=1,
                    success_count=1,
                    skipped_count=0,
                )
            ),
        }
    )
    app = create_app(
        snapshot_loader=loader,
        clipboard_service=clipboard_service,
        initial_path=path,
    )

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await pilot.press("y")
        await pilot.press("p")
        await asyncio.sleep(0.05)

        help_bar = app.query_one("#help-bar", HelpBar)
        dialog = app.query_one("#conflict-dialog", ConflictDialog)
        dialog_options = dialog.query_one("#conflict-dialog-options", Static)

        assert app.app_state.ui_mode == "CONFIRM"
        assert str(help_bar.renderable) == "resolve conflict in dialog"
        assert dialog.display is True
        assert str(dialog_options.renderable) == (
            "Actions: o overwrite | s skip | r rename | esc cancel"
        )

        await pilot.press("r")
        await asyncio.sleep(0.05)

        status_bar = await _wait_for_status_bar(app)
        assert app.app_state.ui_mode == "BROWSING"
        assert str(status_bar.renderable) == "info: Copied 1 item(s)"


@pytest.mark.asyncio
async def test_app_delete_confirmation_round_trip() -> None:
    path = "/tmp/plain-delete-confirm"
    docs = f"{path}/docs"
    src = f"{path}/src"
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                (
                    DirectoryEntryState(docs, "docs", "dir"),
                    DirectoryEntryState(src, "src", "dir"),
                ),
                child_path=docs,
            )
        }
    )
    delete_request = TrashDeleteRequest(paths=(docs, src))
    mutation_service = FakeFileMutationService(
        results={
            delete_request: FileMutationResult(
                path=None,
                message="Trashed 2 items",
                removed_paths=(docs, src),
            )
        }
    )
    app = create_app(
        snapshot_loader=loader,
        file_mutation_service=mutation_service,
        initial_path=path,
    )

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await pilot.press("space")
        await pilot.press("space")
        await pilot.press("delete")
        await asyncio.sleep(0.05)

        help_bar = app.query_one("#help-bar", HelpBar)
        dialog = app.query_one("#conflict-dialog", ConflictDialog)

        assert app.app_state.ui_mode == "CONFIRM"
        assert str(help_bar.renderable) == "enter confirm delete | esc cancel"
        assert dialog.display is True

        await pilot.press("enter")
        await asyncio.sleep(0.05)

        status_bar = await _wait_for_status_bar(app)
        assert app.app_state.ui_mode == "BROWSING"
        assert str(status_bar.renderable) == "info: Trashed 2 items"


@pytest.mark.asyncio
async def test_app_main_flow_round_trip_on_live_filesystem(tmp_path) -> None:
    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "guide.md").write_text("guide")
    notes_file = tmp_path / "notes.txt"
    notes_file.write_text("notes")
    todo_file = tmp_path / "todo.txt"
    todo_file.write_text("todo")

    app = create_app(initial_path=tmp_path)

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, str(tmp_path))
        await _wait_for_row_count(app, 4)

        await pilot.press("down")
        await _wait_for_cursor_path(app, str(docs_dir))
        await _wait_for_child_entries(app, ["guide.md"])

        await pilot.press("down")
        await _wait_for_cursor_path(app, str(notes_file))

        await pilot.press("space")
        await _wait_for_cursor_path(app, str(todo_file))
        assert app.app_state.current_pane.selected_paths == {str(notes_file)}

        await pilot.press("y")
        await asyncio.sleep(0.05)

        assert app.app_state.clipboard.mode == "copy"
        assert app.app_state.clipboard.paths == (str(notes_file),)

        await pilot.press("up")
        await pilot.press("up")
        await _wait_for_cursor_path(app, str(docs_dir))

        await pilot.press("enter")
        await _wait_for_path(app, str(docs_dir))
        await _wait_for_row_count(app, 1)

        await pilot.press("p")
        await _wait_for_row_count(app, 2, timeout=2.0)

        status_bar = await _wait_for_status_bar(app)
        assert (docs_dir / "notes.txt").is_file()
        assert str(status_bar.renderable) == "info: Copied 1 item(s)"

        await pilot.press("backspace")
        await _wait_for_path(app, str(tmp_path))
        await _wait_for_row_count(app, 4)

        await pilot.press("/")
        await pilot.press("n", "o", "t", "e", "s", "enter")
        await _wait_for_row_count(app, 1)

        assert app.app_state.filter.active is True
        assert app.app_state.filter.query == "notes"

        await pilot.press("escape")
        await _wait_for_row_count(app, 4)
        assert app.app_state.filter.active is False

        await pilot.press("s")
        await pilot.press("d")
        await asyncio.sleep(0.05)

        summary_bar = await _wait_for_summary_bar(app)
        assert str(summary_bar.renderable) == (
            "4 items | 0 selected | sort: name desc dirs:off"
        )


@pytest.mark.asyncio
async def test_app_large_directory_smoke_with_1000_entries(tmp_path) -> None:
    for index in range(200):
        directory = tmp_path / f"dir-{index:04d}"
        directory.mkdir()
        (directory / f"child-{index:04d}.txt").write_text("child")

    for index in range(800):
        (tmp_path / f"file-{index:04d}.txt").write_text("file")

    app = create_app(initial_path=tmp_path)

    async with app.run_test(size=(80, 20)) as pilot:
        await _wait_for_snapshot_loaded(app, str(tmp_path), timeout=2.0)
        await _wait_for_row_count(app, 1000, timeout=2.0)
        await _wait_for_child_entries(app, ["child-0000.txt"], timeout=2.0)

        for _ in range(150):
            await pilot.press("down")

        await _wait_for_cursor_path(app, str(tmp_path / "dir-0150"), timeout=2.0)
        await _wait_for_child_entries(app, ["child-0150.txt"], timeout=2.0)

        current_table = app.query_one("#current-pane-table", DataTable)
        assert current_table.row_count == 1000
        assert current_table.cursor_row == 150
