import asyncio
from pathlib import Path

import pytest
from rich.text import Text
from textual.css.query import NoMatches
from textual.widgets import DataTable, Label, ListView

from plain import create_app
from plain.services import FakeBrowserSnapshotLoader
from plain.state import BrowserSnapshot, DirectoryEntryState, PaneState
from plain.ui import CurrentPathBar, StatusBar


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
        status_bar = await _wait_for_status_bar(app)

        assert str(current_path_bar.renderable) == f"Current Path: {tmp_path}"
        assert str(status_bar.renderable) == "2 items | 0 selected | sort: name asc | filter: none"


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
        assert str(status_bar.renderable) == "2 items | 0 selected | sort: name asc | filter: none"


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
        status_bar = await _wait_for_status_bar(app)

        assert app.app_state.current_pane.selected_paths == {f"{path}/docs"}
        assert app.app_state.current_pane.cursor_path == f"{path}/src"
        assert child_names == ["main.py"]
        assert str(current_path_bar.renderable) == f"Current Path: {path}"
        assert str(status_bar.renderable) == "3 items | 1 selected | sort: name asc | filter: none"

        current_table = app.query_one("#current-pane-table", DataTable)
        first_row = current_table.get_row_at(0)

        assert isinstance(first_row[0], Text)
        assert first_row[0].plain == "*"
        assert first_row[0].style == "bold green"
        assert first_row[2].plain == "docs"


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

        status_bar = await _wait_for_status_bar(app)

        assert app.app_state.current_pane.selected_paths == set()
        assert app.app_state.current_pane.cursor_path == f"{path}/src"
        assert str(status_bar.renderable) == "1 items | 0 selected | sort: name asc | filter: none"


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

        status_bar = await _wait_for_status_bar(app)

        assert app.app_state.current_pane.selected_paths == set()
        assert app.app_state.current_path == docs
        assert str(status_bar.renderable) == "1 items | 0 selected | sort: name asc | filter: none"


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
        status_bar = app.query_one("#status-bar", StatusBar)
        current_table = app.query_one("#current-pane-table", DataTable)
        child_list = app.query_one("#child-pane-list", ListView)

        await pilot.press("down")
        await asyncio.sleep(0.05)

        assert app.query_one("#body") is body
        assert app.query_one("#current-path-bar", CurrentPathBar) is current_path_bar
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
        status_bar = await _wait_for_status_bar(app)

        assert list(child_list.children) == []
        assert str(current_path_bar.renderable) == f"Current Path: {path}"
        assert str(status_bar.renderable) == (
            "2 items | 0 selected | sort: name asc | filter: none | "
            "error: permission denied"
        )
