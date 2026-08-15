"""Test App Layout tests."""

from tests.support.app import (
    DataTable,
    DirectoryEntryState,
    FakeBrowserSnapshotLoader,
    MainPane,
    Path,
    Static,
    Style,
    _build_snapshot,
    _wait_for_predicate,
    _wait_for_snapshot_loaded,
    create_app,
    pytest,
)


@pytest.mark.asyncio
async def test_app_renders_empty_directory_action_and_routes_it_to_create_flow() -> None:
    path = str(Path("/tmp/zivo-empty-state").resolve())
    loader = FakeBrowserSnapshotLoader(
        snapshots={path: _build_snapshot(path, (), child_path=path, child_entries=())}
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test(size=(120, 20)):
        await _wait_for_predicate(
            lambda: app.app_state.pending_browser_snapshot_request_id is None,
            message="empty directory snapshot did not finish",
        )
        status = app.query_one("#current-pane-status", Static)
        assert status.display is True
        assert "Empty directory" in str(status.renderable)
        assert "[n] New file" in str(status.renderable)
        assert "[N] New directory" in str(status.renderable)

        await app.on_main_pane_action_clicked(MainPane.ActionClicked("create_file"))

        assert app.app_state.ui_mode == "CREATE"
        assert app.app_state.pending_input is not None
        assert app.app_state.pending_input.create_kind == "file"

@pytest.mark.asyncio
async def test_app_header_click_uses_set_sort_reducer_path() -> None:
    path = str(Path("/tmp/zivo-header-sort").resolve())
    entries = (
        DirectoryEntryState(f"{path}/alpha", "alpha", "dir", size_bytes=10),
        DirectoryEntryState(f"{path}/beta.txt", "beta.txt", "file", size_bytes=20),
    )
    loader = FakeBrowserSnapshotLoader(
        snapshots={path: _build_snapshot(path, entries, child_path=path)}
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test(size=(120, 20)) as pilot:
        await _wait_for_snapshot_loaded(app, path)
        table = app.query_one("#current-pane-table", DataTable)

        class _HeaderClick:
            style = Style(meta={"row": -1, "column": 2})

            def stop(self) -> None:
                return None

        await table._on_click(_HeaderClick())
        await pilot.pause()

        assert app.app_state.sort.field == "size"
        assert app.app_state.sort.descending is True
        assert "Size ↓" in table.columns["size"].label.plain

        await table._on_click(_HeaderClick())
        await pilot.pause()
        assert app.app_state.sort.field == "size"
        assert app.app_state.sort.descending is False
