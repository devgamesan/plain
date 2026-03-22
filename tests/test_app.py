import asyncio
from pathlib import Path

import pytest
from textual.css.query import NoMatches
from textual.widgets import DataTable, Label, ListView

from plain import create_app
from plain.services import FakeBrowserSnapshotLoader
from plain.state import BrowserSnapshot, DirectoryEntryState, PaneState
from plain.ui import StatusBar


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
        status_bar = await _wait_for_status_bar(app)

        assert str(status_bar.renderable) == (
            f"{tmp_path} | 2 items | 0 selected | sort: name asc | filter: none"
        )


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
        status_bar = await _wait_for_status_bar(app)
        parent_entries = [str(item.query_one(Label).renderable) for item in parent_list.children]
        child_entries = [str(item.query_one(Label).renderable) for item in child_list.children]
        headers = [str(column.label) for column in current_table.ordered_columns]

        assert parent_entries == ["plain-app", "sibling"]
        assert headers == ["種別", "名前", "サイズ", "更新日時"]
        assert current_table.row_count == 2
        assert child_entries == ["spec.md"]
        assert str(status_bar.renderable) == (
            f"{path} | 2 items | 0 selected | sort: name asc | filter: none"
        )


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
        status_bar = await _wait_for_status_bar(app)

        assert app.app_state.current_pane.selected_paths == {f"{path}/docs"}
        assert app.app_state.current_pane.cursor_path == f"{path}/src"
        assert child_names == ["main.py"]
        assert str(status_bar.renderable) == (
            f"{path} | 3 items | 1 selected | sort: name asc | filter: none"
        )


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
        status_bar = app.query_one("#status-bar", StatusBar)
        current_table = app.query_one("#current-pane-table", DataTable)
        child_list = app.query_one("#child-pane-list", ListView)

        await pilot.press("down")
        await asyncio.sleep(0.05)

        assert app.query_one("#body") is body
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
        status_bar = await _wait_for_status_bar(app)

        assert list(child_list.children) == []
        assert str(status_bar.renderable) == (
            f"{path} | 2 items | 0 selected | sort: name asc | filter: none | "
            "error: permission denied"
        )
