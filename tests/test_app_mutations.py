"""Test App Mutations tests."""

from tests.support.app import (
    AppConfig,
    BehaviorConfig,
    Click,
    CommandPalette,
    ConflictDialog,
    DataTable,
    DeletePreparationResult,
    DeleteRequest,
    DirectoryEntryState,
    DisplayConfig,
    FakeBrowserSnapshotLoader,
    FakeClipboardOperationService,
    FakeFileMutationService,
    FakeFileSearchService,
    FileMutationResult,
    FileSearchResultState,
    HelpBar,
    PaneState,
    PasteConflict,
    PasteConflictPrompt,
    PasteExecutionResult,
    PasteRequest,
    PasteSummary,
    Path,
    Static,
    Style,
    TerminalConfig,
    _build_snapshot,
    _pane_visibility_app,
    _side_pane_lines,
    _wait_for_child_entries,
    _wait_for_child_list_label,
    _wait_for_context_input,
    _wait_for_cursor_path,
    _wait_for_file_search_results,
    _wait_for_input_dialog,
    _wait_for_path,
    _wait_for_predicate,
    _wait_for_request_count,
    _wait_for_row_count,
    _wait_for_snapshot_loaded,
    _wait_for_status_bar,
    _wait_for_status_message,
    _wait_for_summary_bar,
    asyncio,
    compute_current_pane_visible_window,
    create_app,
    pytest,
    select_command_palette_state,
    update_pane_visibility,
)


@pytest.mark.asyncio
async def test_app_escape_clears_active_filter_before_selection() -> None:
    path = str(Path("/tmp/zivo-filter-escape-priority").resolve())
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
    path = str(Path("/tmp/zivo-rename-mode").resolve())
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
        await pilot.press("r")
        await asyncio.sleep(0.05)

        help_bar = app.query_one("#help-bar", HelpBar)
        input_dialog = await _wait_for_input_dialog(app)

        assert app.app_state.ui_mode == "RENAME"
        assert str(help_bar.renderable) == "type name | enter apply | esc cancel"
        assert input_dialog.display is True
        assert input_dialog.state is not None
        assert input_dialog.state.title == "Rename"
        assert input_dialog.state.prompt == "Rename: "
        assert input_dialog.state.hint == "enter apply | esc cancel"

@pytest.mark.asyncio
async def test_app_rename_name_conflict_dialog_returns_to_input(tmp_path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "src").mkdir()
    app = create_app(initial_path=tmp_path)

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, str(tmp_path))
        await pilot.press("r")
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

        input_dialog = await _wait_for_input_dialog(app)

        assert app.app_state.ui_mode == "RENAME"
        assert dialog.display is False
        assert input_dialog.display is True
        assert input_dialog.state is not None
        assert input_dialog.state.title == "Rename"
        assert input_dialog.state.prompt == "Rename: "
        assert input_dialog.state.value == "src"

@pytest.mark.asyncio
async def test_app_rename_round_trip_updates_status_bar(tmp_path) -> None:
    (tmp_path / "docs").mkdir()
    app = create_app(initial_path=tmp_path)

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, str(tmp_path))
        await pilot.press("r")
        await asyncio.sleep(0.05)
        for _ in range(4):
            await pilot.press("backspace")
        await pilot.press("m", "a", "n", "u", "a", "l", "s", "enter")
        await _wait_for_predicate(
            lambda: app.app_state.ui_mode == "BROWSING",
            timeout=1.0,
            message="rename did not return to browsing mode",
        )
        await _wait_for_status_message(
            app,
            "info: Renamed to manuals   Undo",
            timeout=1.0,
        )

        assert (tmp_path / "manuals").is_dir()
        assert app.app_state.ui_mode == "BROWSING"

@pytest.mark.asyncio
async def test_app_create_name_conflict_dialog_returns_to_input(tmp_path) -> None:
    (tmp_path / "docs").mkdir()
    app = create_app(initial_path=tmp_path)

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, str(tmp_path))
        await pilot.press(":")
        await pilot.press("c", "r", "e", "a", "t", "e")
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

        input_dialog = await _wait_for_input_dialog(app)

        assert app.app_state.ui_mode == "CREATE"
        assert dialog.display is False
        assert input_dialog.display is True
        assert input_dialog.state is not None
        assert input_dialog.state.title == "Create"
        assert input_dialog.state.prompt == "Name or path: "
        assert input_dialog.state.value == "docs"

@pytest.mark.asyncio
async def test_app_paste_conflict_dialog_round_trip() -> None:
    path = str(Path("/tmp/zivo-paste-conflict").resolve())
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
        await pilot.press("c")
        await pilot.press("v")
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

        assert app.app_state.ui_mode == "BROWSING"

@pytest.mark.asyncio
async def test_app_delete_confirmation_round_trip() -> None:
    path = str(Path("/tmp/zivo-delete-confirm").resolve())
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
    delete_request = DeleteRequest(paths=(docs, src), mode="trash")
    mutation_service = FakeFileMutationService(
        results={
            delete_request: FileMutationResult(
                path=None,
                message="Moved 2 items to trash",
                removed_paths=(docs, src),
            )
        },
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
        assert str(help_bar.renderable) == "enter confirm move to trash | esc cancel"
        assert dialog.display is True

        await pilot.press("enter")
        await asyncio.sleep(0.05)

        status_bar = await _wait_for_status_bar(app)
        assert app.app_state.ui_mode == "BROWSING"
        assert str(status_bar.renderable) == "info: Moved 2 items to trash"

@pytest.mark.asyncio
async def test_app_delete_skips_confirmation_when_disabled() -> None:
    path = str(Path("/tmp/zivo-delete-without-confirm").resolve())
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
    delete_request = DeleteRequest(paths=(docs, src), mode="trash")
    mutation_service = FakeFileMutationService(
        results={
            delete_request: FileMutationResult(
                path=None,
                message="Moved 2 items to trash",
                removed_paths=(docs, src),
            )
        }
    )
    app = create_app(
        snapshot_loader=loader,
        file_mutation_service=mutation_service,
        initial_path=path,
        app_config=AppConfig(
            terminal=TerminalConfig(),
            display=DisplayConfig(),
            behavior=BehaviorConfig(
                confirm_delete=False,
                paste_conflict_action="prompt",
            ),
        ),
    )

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await pilot.press("space")
        await pilot.press("space")
        await pilot.press("delete")
        await asyncio.sleep(0.05)

        status_bar = await _wait_for_status_bar(app)
        dialog = app.query_one("#conflict-dialog", ConflictDialog)

        assert app.app_state.ui_mode == "BROWSING"
        assert app.app_state.delete_confirmation is None
        assert dialog.display is False
        assert str(status_bar.renderable) == "info: Moved 2 items to trash"

@pytest.mark.asyncio
async def test_app_permanent_delete_always_confirms() -> None:
    path = str(Path("/tmp/zivo-permanent-delete").resolve())
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
    delete_request = DeleteRequest(paths=(docs, src), mode="permanent")
    mutation_service = FakeFileMutationService(
        results={
            delete_request: FileMutationResult(
                path=None,
                message="Permanently deleted 2 items",
                removed_paths=(docs, src),
            )
        },
        preparation_results={
            delete_request: DeletePreparationResult(
                request=delete_request,
                total_size_bytes=8192,
                contains_directory=True,
            )
        },
    )
    app = create_app(
        snapshot_loader=loader,
        file_mutation_service=mutation_service,
        initial_path=path,
        app_config=AppConfig(
            terminal=TerminalConfig(),
            display=DisplayConfig(),
            behavior=BehaviorConfig(
                confirm_delete=False,
                paste_conflict_action="prompt",
            ),
        ),
    )

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await pilot.press("space")
        await pilot.press("space")
        await pilot.press("shift+delete")
        await asyncio.sleep(0.05)

        help_bar = app.query_one("#help-bar", HelpBar)
        dialog = app.query_one("#conflict-dialog", ConflictDialog)
        dialog_message = dialog.query_one("#conflict-dialog-message", Static)

        assert app.app_state.ui_mode == "CONFIRM"
        assert str(help_bar.renderable) == "enter review permanently delete | esc cancel"
        assert dialog.display is True
        assert "Permanently delete 2 items? This cannot be undone." in str(
            dialog_message.renderable
        )
        assert "Size: 8.0KiB" in str(dialog_message.renderable)
        assert "Targets: docs, src" in str(dialog_message.renderable)
        assert "This cannot be undone" in str(dialog_message.renderable)

        await pilot.press("enter")
        await asyncio.sleep(0.05)

        assert str(help_bar.renderable) == "D permanently delete | esc cancel"

        await pilot.press("D")
        await asyncio.sleep(0.05)

        status_bar = await _wait_for_status_bar(app)
        assert app.app_state.ui_mode == "BROWSING"
        assert str(status_bar.renderable) == "info: Permanently deleted 2 items"

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

        await pilot.press("c")
        await asyncio.sleep(0.05)

        assert app.app_state.clipboard.mode == "copy"
        assert app.app_state.clipboard.paths == (str(notes_file),)

        await pilot.press("up")
        await pilot.press("up")
        await _wait_for_cursor_path(app, str(docs_dir))

        await pilot.press("enter")
        await _wait_for_path(app, str(docs_dir))
        await _wait_for_row_count(app, 1)

        await pilot.press("v")
        await _wait_for_row_count(app, 2, timeout=2.0)

        status_bar = await _wait_for_status_bar(app)
        assert (docs_dir / "notes.txt").is_file()
        assert str(status_bar.renderable) == "info: Copied 1 item(s)   Undo"

        await pilot.press("left")
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
        await asyncio.sleep(0.05)

        summary_bar = await _wait_for_summary_bar(app)
        assert str(summary_bar.renderable) == ("4 items | 0 selected | sort: name desc")

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
        visible_window = compute_current_pane_visible_window(app.app_state.terminal_height)
        await _wait_for_row_count(app, visible_window, timeout=2.0)
        await _wait_for_child_entries(app, ["child-0000.txt"], timeout=2.0)

        for _ in range(150):
            await pilot.press("down")

        await _wait_for_cursor_path(app, str(tmp_path / "dir-0150"), timeout=2.0)
        await _wait_for_child_entries(app, ["child-0150.txt"], timeout=2.0)

        current_table = app.query_one("#current-pane-table", DataTable)
        assert current_table.row_count == visible_window
        assert current_table.cursor_row == visible_window - 1

@pytest.mark.asyncio
async def test_app_cursor_move_refreshes_large_child_pane_without_remount(
    monkeypatch,
) -> None:
    path = str(Path("/tmp/zivo-large-child-pane").resolve())
    current_entries = (
        DirectoryEntryState(f"{path}/docs", "docs", "dir"),
        DirectoryEntryState(f"{path}/src", "src", "dir"),
    )
    docs_child_entries = tuple(
        DirectoryEntryState(
            f"{path}/docs/child-{index:04d}.txt",
            f"child-{index:04d}.txt",
            "file",
        )
        for index in range(1000)
    )
    src_child_entries = tuple(
        DirectoryEntryState(
            f"{path}/src/module-{index:04d}.py",
            f"module-{index:04d}.py",
            "file",
        )
        for index in range(1000)
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

    async with app.run_test(size=(80, 24)) as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await _wait_for_row_count(app, 2)
        visible_window = compute_current_pane_visible_window(app.app_state.terminal_height)
        await _wait_for_child_list_label(
            app,
            f"child-{visible_window - 1:04d}.txt",
            index=visible_window - 1,
            timeout=2.0,
        )

        child_list = app.query_one("#child-pane-list", Static)
        original_update = Static.update
        update_calls = 0

        def counting_update(self, *args, **kwargs):
            nonlocal update_calls
            if self is child_list:
                update_calls += 1
            return original_update(self, *args, **kwargs)

        monkeypatch.setattr(Static, "update", counting_update)

        await pilot.press("down")
        await _wait_for_child_list_label(
            app,
            f"module-{visible_window - 1:04d}.py",
            index=visible_window - 1,
            timeout=2.0,
        )

        assert app.query_one("#child-pane-list", Static) is child_list
        assert len(_side_pane_lines(child_list)) == visible_window
        assert update_calls == 1

@pytest.mark.asyncio
async def test_app_hides_both_side_panes_at_narrow_width() -> None:
    app = _pane_visibility_app()

    async with app.run_test(size=(60, 20)):
        await _wait_for_snapshot_loaded(app, "/tmp/zivo-pane-vis")
        parent = app.query_one("#parent-pane")
        child = app.query_one("#child-pane")
        assert not parent.display
        assert not child.display

@pytest.mark.asyncio
async def test_app_tab_toggles_current_and_details_views_at_narrow_width() -> None:
    app = _pane_visibility_app()

    async with app.run_test(size=(60, 20)) as pilot:
        await _wait_for_snapshot_loaded(app, "/tmp/zivo-pane-vis")
        current = app.query_one("#current-pane")
        child = app.query_one("#child-pane")
        assert current.display
        assert not child.display

        await pilot.press("tab")
        await asyncio.sleep(0.05)

        assert app.app_state.narrow_pane_view == "details"
        assert not current.display
        assert child.display

        await pilot.press("tab")
        await asyncio.sleep(0.05)
        assert app.app_state.narrow_pane_view == "current"
        assert current.display
        assert not child.display

@pytest.mark.asyncio
async def test_app_hides_parent_pane_at_medium_width() -> None:
    app = _pane_visibility_app()

    async with app.run_test(size=(80, 20)):
        await _wait_for_snapshot_loaded(app, "/tmp/zivo-pane-vis")
        parent = app.query_one("#parent-pane")
        child = app.query_one("#child-pane")
        assert not parent.display
        assert child.display

@pytest.mark.asyncio
async def test_app_shows_all_panes_at_wide_width() -> None:
    app = _pane_visibility_app()

    async with app.run_test(size=(120, 20)):
        await _wait_for_snapshot_loaded(app, "/tmp/zivo-pane-vis")
        parent = app.query_one("#parent-pane")
        child = app.query_one("#child-pane")
        assert parent.display
        assert child.display

@pytest.mark.asyncio
async def test_app_toggles_pane_visibility_on_resize() -> None:
    app = _pane_visibility_app()

    async with app.run_test(size=(120, 20)):
        await _wait_for_snapshot_loaded(app, "/tmp/zivo-pane-vis")

        parent = app.query_one("#parent-pane")
        child = app.query_one("#child-pane")
        assert parent.display
        assert child.display

        update_pane_visibility(app, 60)
        assert not parent.display
        assert not child.display

        update_pane_visibility(app, 80)
        assert not parent.display
        assert child.display

        update_pane_visibility(app, 120)
        assert parent.display
        assert child.display

class TestCommandPaletteClick:
    """Tests for command palette mouse-click support."""

    @staticmethod
    def test_render_items_embeds_click_meta() -> None:
        from zivo.models.shell_data import CommandPaletteItemViewState, CommandPaletteViewState

        items = (
            CommandPaletteItemViewState(label="a.txt", shortcut=None, enabled=True, selected=True),
            CommandPaletteItemViewState(label="b.txt", shortcut=None, enabled=True, selected=False),
            CommandPaletteItemViewState(label="c.txt", shortcut=None, enabled=True, selected=False),
        )
        state = CommandPaletteViewState(
            title="Test",
            query="",
            items=items,
            empty_message="none",
        )
        rendered = CommandPalette._render_items(state, 80)
        indices = []
        for span in rendered.spans:
            idx = span.style.meta.get("palette_item_index") if span.style.meta else None
            if idx is not None and idx not in indices:
                indices.append(idx)
        assert indices == [0, 1, 2]

    @pytest.mark.asyncio
    async def test_single_click_moves_cursor_to_item(self, tmp_path) -> None:
        (tmp_path / "a.txt").write_text("a\n", encoding="utf-8")
        (tmp_path / "b.txt").write_text("b\n", encoding="utf-8")
        (tmp_path / "c.txt").write_text("c\n", encoding="utf-8")
        file_search_service = FakeFileSearchService(
            results_by_query={
                (str(tmp_path), "test", False): (
                    FileSearchResultState(path=f"{tmp_path}/a.txt", display_path="a.txt"),
                    FileSearchResultState(path=f"{tmp_path}/b.txt", display_path="b.txt"),
                    FileSearchResultState(path=f"{tmp_path}/c.txt", display_path="c.txt"),
                )
            }
        )
        app = create_app(file_search_service=file_search_service, initial_path=str(tmp_path))

        async with app.run_test(size=(72, 24)) as pilot:
            await _wait_for_snapshot_loaded(app, str(tmp_path))
            await pilot.press("f")
            await pilot.press("t", "e", "s", "t")
            await _wait_for_request_count(file_search_service, 1)
            await _wait_for_file_search_results(
                app,
                ["a.txt", "b.txt", "c.txt"],
            )
            palette = app.query_one("#command-palette", CommandPalette)

            # First item (index 0) is already selected, click item at index 2
            event = Click(None, 0, 2, 0, 0, 0, False, False, False)
            event.style = Style(meta={"palette_item_index": 2})
            await palette.on_click(event)

            palette_state = select_command_palette_state(app.app_state)
            assert palette_state is not None
            assert palette_state.items[2].selected
            assert not palette_state.items[0].selected

    @pytest.mark.asyncio
    async def test_double_click_submits_item(self, tmp_path) -> None:
        (tmp_path / "a.txt").write_text("a\n", encoding="utf-8")
        file_search_service = FakeFileSearchService(
            results_by_query={
                (str(tmp_path), "test", False): (
                    FileSearchResultState(path=f"{tmp_path}/a.txt", display_path="a.txt"),
                )
            }
        )
        app = create_app(file_search_service=file_search_service, initial_path=str(tmp_path))

        async with app.run_test(size=(72, 24)) as pilot:
            await _wait_for_snapshot_loaded(app, str(tmp_path))
            await pilot.press("f")
            await pilot.press("t", "e", "s", "t")
            await _wait_for_request_count(file_search_service, 1)
            await _wait_for_file_search_results(app, ["a.txt"])
            palette = app.query_one("#command-palette", CommandPalette)

            # Reset double-click state
            palette._last_clicked_index = -1

            # First click (sets _last_clicked_index)
            event1 = Click(None, 0, 0, 0, 0, 0, False, False, False)
            event1.style = Style(meta={"palette_item_index": 0})
            await palette.on_click(event1)

            # Second click on same index → double-click → SubmitCommandPalette
            event2 = Click(None, 0, 0, 0, 0, 0, False, False, False)
            event2.style = Style(meta={"palette_item_index": 0})
            await palette.on_click(event2)

            # After SubmitCommandPalette, palette should be closed
            assert app.app_state.command_palette is None
