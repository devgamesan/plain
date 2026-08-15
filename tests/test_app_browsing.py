"""Test App Browsing tests."""

from tests.support.app import (
    WINDOWS_DRIVES_ROOT,
    AppConfig,
    BehaviorConfig,
    BrowserSnapshot,
    ChildPane,
    CurrentPathBar,
    DataTable,
    DirectoryEntryState,
    DisplayConfig,
    ExternalLaunchRequest,
    FakeBrowserSnapshotLoader,
    FakeDirectorySizeService,
    FakeExternalLaunchService,
    FakeUndoService,
    JumpCursor,
    Label,
    MainPane,
    MouseMove,
    MoveCursor,
    NotificationAction,
    NotificationState,
    PaneState,
    Path,
    SetNotification,
    SetTerminalHeight,
    SidePane,
    Static,
    StatusBar,
    SummaryBar,
    TerminalConfig,
    Text,
    UndoDeletePathStep,
    UndoEntry,
    UndoResult,
    VerticalScroll,
    _build_snapshot,
    _preview_scroll_delta,
    _side_pane_lines,
    _style_without_background,
    _text_has_style,
    _text_style_matches,
    _wait_for_child_entries,
    _wait_for_child_pane_request_count,
    _wait_for_child_pane_runtime_idle,
    _wait_for_child_preview,
    _wait_for_command_palette,
    _wait_for_current_path_bar,
    _wait_for_cursor_path,
    _wait_for_directory_sizes,
    _wait_for_external_launch_count,
    _wait_for_help_bar_text,
    _wait_for_notification_message,
    _wait_for_path,
    _wait_for_row_count,
    _wait_for_snapshot_loaded,
    _wait_for_status_bar,
    _wait_for_status_message,
    _wait_for_summary_bar,
    _wait_for_tab_bar,
    _wait_for_table_cell,
    _wait_for_transfer_right_table,
    asyncio,
    build_initial_app_state,
    compute_current_pane_visible_window,
    create_app,
    os,
    pytest,
    replace,
    select_shell_data,
    threading,
    time,
)
from tests.support.services import (
    BlockingDirectorySizeService,
)


def test_create_app_returns_zivo_app() -> None:
    app = create_app()

    assert app.title == "zivo"
    assert app.sub_title == "Three-pane shell"

def test_create_app_applies_configured_startup_state() -> None:
    app = create_app(
        app_config=AppConfig(
            terminal=TerminalConfig(),
            display=DisplayConfig(
                show_hidden_files=True,
                theme="dracula",
                default_sort_field="modified",
                default_sort_descending=True,
                directories_first=False,
            ),
            behavior=BehaviorConfig(
                confirm_delete=False,
                paste_conflict_action="skip",
            ),
        )
    )

    assert app.app_state.show_hidden is True
    assert app.theme == "dracula"
    assert app.app_state.sort.field == "modified"
    assert app.app_state.sort.descending is True
    assert app.app_state.sort.directories_first is False
    assert app.app_state.confirm_delete is False
    assert app.app_state.paste_conflict_action == "skip"

@pytest.mark.asyncio
async def test_app_loads_directory_sizes_when_enabled() -> None:
    path = str(Path("/tmp/zivo-dir-size").resolve())
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                (
                    DirectoryEntryState(f"{path}/docs", "docs", "dir"),
                    DirectoryEntryState(f"{path}/README.md", "README.md", "file", size_bytes=120),
                ),
                child_path=f"{path}/docs",
                child_entries=(DirectoryEntryState(f"{path}/docs/api", "api", "dir"),),
            )
        }
    )
    directory_size_service = FakeDirectorySizeService(
        results_by_paths={
            (f"{path}/docs",): (
                (f"{path}/docs", 4_200),
            )
        }
    )
    app = create_app(
        snapshot_loader=loader,
        directory_size_service=directory_size_service,
        app_config=AppConfig(
            display=DisplayConfig(show_directory_sizes=True),
        ),
        initial_path=path,
    )

    async with app.run_test(size=(120, 20)):
        await _wait_for_snapshot_loaded(app, path)
        await _wait_for_row_count(app, 2)
        await _wait_for_table_cell(app, "4.1KiB", 0, 2)

        table = app.query_one("#current-pane-table", DataTable)

        assert str(table.get_cell_at((0, 2))) == "4.1KiB"

@pytest.mark.asyncio
async def test_app_applies_directory_size_updates_without_full_current_pane_refresh(
    monkeypatch,
) -> None:
    path = str(Path("/tmp/zivo-dir-size-delta").resolve())
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
    class SlowDirectorySizeService(FakeDirectorySizeService):
        def calculate_sizes(self, paths, *, is_cancelled=None):
            time.sleep(0.05)
            return super().calculate_sizes(paths, is_cancelled=is_cancelled)

    directory_size_service = SlowDirectorySizeService(
        results_by_paths={
            (f"{path}/docs",): (
                (f"{path}/docs", 4_200),
            )
        }
    )
    set_entries_calls = 0
    apply_size_updates_calls = 0
    original_set_entries = MainPane.set_entries
    original_apply_size_updates = MainPane.apply_size_updates

    def wrapped_set_entries(self, entries, cursor_index=None):
        nonlocal set_entries_calls
        set_entries_calls += 1
        return original_set_entries(self, entries, cursor_index)

    def wrapped_apply_size_updates(self, updates):
        nonlocal apply_size_updates_calls
        apply_size_updates_calls += 1
        return original_apply_size_updates(self, updates)

    monkeypatch.setattr(MainPane, "set_entries", wrapped_set_entries)
    monkeypatch.setattr(MainPane, "apply_size_updates", wrapped_apply_size_updates)

    app = create_app(
        snapshot_loader=loader,
        directory_size_service=directory_size_service,
        app_config=AppConfig(
            display=DisplayConfig(show_directory_sizes=True),
        ),
        initial_path=path,
    )

    async with app.run_test(size=(120, 20)):
        await _wait_for_snapshot_loaded(app, path)
        await _wait_for_row_count(app, 2)
        await _wait_for_table_cell(app, "-", 0, 2)
        full_refresh_calls_before_ready = set_entries_calls
        await _wait_for_table_cell(app, "4.1KiB", 0, 2)

        assert set_entries_calls == full_refresh_calls_before_ready
        assert apply_size_updates_calls == 1

@pytest.mark.asyncio
async def test_app_keeps_successful_directory_sizes_when_some_paths_fail() -> None:
    path = str(Path("/tmp/zivo-dir-size-partial").resolve())
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                (
                    DirectoryEntryState(f"{path}/docs", "docs", "dir"),
                    DirectoryEntryState(f"{path}/private", "private", "dir"),
                    DirectoryEntryState(f"{path}/README.md", "README.md", "file", size_bytes=120),
                ),
                child_path=f"{path}/docs",
                child_entries=(DirectoryEntryState(f"{path}/docs/api", "api", "dir"),),
            )
        }
    )
    directory_size_service = FakeDirectorySizeService(
        results_by_paths={
            (f"{path}/docs", f"{path}/private"): (
                (f"{path}/docs", 4_200),
            )
        },
        failures_by_paths={
            (f"{path}/docs", f"{path}/private"): (
                (f"{path}/private", "permission denied"),
            )
        },
    )
    app = create_app(
        snapshot_loader=loader,
        directory_size_service=directory_size_service,
        app_config=AppConfig(
            display=DisplayConfig(show_directory_sizes=True),
        ),
        initial_path=path,
    )

    async with app.run_test():
        await _wait_for_snapshot_loaded(app, path)
        await _wait_for_row_count(app, 3)
        await _wait_for_table_cell(app, "4.1KiB", 0, 2)

        table = app.query_one("#current-pane-table", DataTable)

        assert str(table.get_cell_at((0, 2))) == "4.1KiB"

@pytest.mark.asyncio
async def test_app_uses_cwd_for_default_initial_path(tmp_path, monkeypatch) -> None:
    current_entries = (
        DirectoryEntryState(f"{tmp_path}/docs", "docs", "dir"),
        DirectoryEntryState(f"{tmp_path}/README.md", "README.md", "file", size_bytes=20),
    )
    child_entries = (DirectoryEntryState(f"{tmp_path}/docs/spec.md", "spec.md", "file"),)
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

        assert "Current Path:" in str(current_path_bar.renderable)
        assert str(summary_bar.renderable) == ("2 items | 0 selected | sort: name asc")
        assert str(status_bar.renderable) == ""

@pytest.mark.asyncio
async def test_app_live_snapshot_highlights_current_directory_in_parent_pane(tmp_path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "README.md").write_text("readme\n", encoding="utf-8")
    app = create_app(initial_path=tmp_path)

    async with app.run_test(size=(240, 20)):
        await _wait_for_snapshot_loaded(app, str(tmp_path))
        await _wait_for_row_count(app, 2)

        parent_pane = app.query_one("#parent-pane", SidePane)
        parent_list = app.query_one("#parent-pane-list", Static)
        parent_renderable = parent_list.renderable

        assert app.app_state.parent_pane.cursor_path == str(tmp_path)
        assert isinstance(parent_renderable, Text)
        assert any(
            line.startswith(tmp_path.name[:12])
            for line in parent_renderable.plain.splitlines()
        )
        assert _text_has_style(
            parent_renderable,
            _style_without_background(parent_pane.get_component_rich_style("ft-directory-sel")),
        )

@pytest.mark.asyncio
async def test_app_can_start_in_narrow_headless_mode() -> None:
    path = str(Path("/tmp/zivo-narrow").resolve())
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
async def test_app_renders_text_preview_in_child_pane_for_file_cursor() -> None:
    path = str(Path("/tmp/zivo-preview").resolve())
    readme = f"{path}/README.md"
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: BrowserSnapshot(
                current_path=path,
                parent_pane=PaneState(
                    directory_path="/tmp",
                    entries=(
                        DirectoryEntryState(path, "zivo-preview", "dir"),
                        DirectoryEntryState("/tmp/sibling", "sibling", "dir"),
                    ),
                    cursor_path=path,
                ),
                current_pane=PaneState(
                    directory_path=path,
                    entries=(DirectoryEntryState(readme, "README.md", "file"),),
                    cursor_path=readme,
                ),
                child_pane=PaneState(
                    directory_path=path,
                    entries=(),
                    mode="preview",
                    preview_path=readme,
                    preview_content="# Title\npreview body\n",
                ),
            )
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test():
        await _wait_for_snapshot_loaded(app, path)
        await _wait_for_row_count(app, 1)
        await _wait_for_child_preview(app, "Preview · README.md", "# Title")

        child_list = app.query_one("#child-pane-list", Static)
        child_list_scroll = app.query_one("#child-pane-list-scroll")
        child_preview_scroll = app.query_one("#child-pane-preview-scroll", VerticalScroll)

        assert child_list.display is False
        assert child_list_scroll.display is False
        assert child_preview_scroll.display is True

@pytest.mark.asyncio
async def test_app_renders_preview_metadata_bar_for_file_cursor() -> None:
    path = str(Path("/tmp/zivo-preview-metadata").resolve())
    readme = f"{path}/README.md"
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: BrowserSnapshot(
                current_path=path,
                parent_pane=PaneState(
                    directory_path="/tmp",
                    entries=(DirectoryEntryState(path, "zivo-preview-metadata", "dir"),),
                    cursor_path=path,
                ),
                current_pane=PaneState(
                    directory_path=path,
                    entries=(
                        DirectoryEntryState(
                            readme,
                            "README.md",
                            "file",
                            size_bytes=2_150,
                            permissions_mode=0o100644,
                            owner="alice",
                            group="staff",
                        ),
                    ),
                    cursor_path=readme,
                ),
                child_pane=PaneState(
                    directory_path=path,
                    entries=(),
                    mode="preview",
                    preview_path=readme,
                    preview_content="# Title\npreview body\n",
                ),
            )
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test(size=(120, 20)):
        await _wait_for_snapshot_loaded(app, path)
        await _wait_for_child_preview(app, "Preview · README.md", "# Title")

        metadata_bar = app.query_one("#child-pane-metadata-bar", Static)

        assert str(metadata_bar.renderable) == "2.1KiB · -rw-r--r-- (644) · alice staff"

@pytest.mark.asyncio
async def test_app_renders_image_preview_in_child_pane_for_file_cursor() -> None:
    path = str(Path("/tmp/zivo-image-preview").resolve())
    image = f"{path}/preview.png"
    preview_content = (
        "\x1b[31m@@\x1b[0m\n"
        "\x1b[32m##\x1b[0m\n"
        "\x1b[34m..\x1b[0m\n"
    ) * 40
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: BrowserSnapshot(
                current_path=path,
                parent_pane=PaneState(
                    directory_path="/tmp",
                    entries=(
                        DirectoryEntryState(path, "zivo-image-preview", "dir"),
                        DirectoryEntryState("/tmp/sibling", "sibling", "dir"),
                    ),
                    cursor_path=path,
                ),
                current_pane=PaneState(
                    directory_path=path,
                    entries=(DirectoryEntryState(image, "preview.png", "file"),),
                    cursor_path=image,
                ),
                child_pane=PaneState(
                    directory_path=path,
                    entries=(),
                    mode="preview",
                    preview_path=image,
                    preview_content=preview_content,
                    preview_kind="image",
                ),
            )
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test():
        await _wait_for_snapshot_loaded(app, path)
        await _wait_for_row_count(app, 1)
        await _wait_for_child_preview(app, "Preview · preview.png", "@@")

@pytest.mark.asyncio
async def test_app_ignores_terminal_response_sequences_in_browsing_mode() -> None:
    path = str(Path("/tmp/zivo-terminal-response").resolve())
    readme = f"{path}/README.md"
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: BrowserSnapshot(
                current_path=path,
                parent_pane=PaneState(
                    directory_path="/tmp",
                    entries=(
                        DirectoryEntryState(path, "zivo-terminal-response", "dir"),
                        DirectoryEntryState("/tmp/sibling", "sibling", "dir"),
                    ),
                    cursor_path=path,
                ),
                current_pane=PaneState(
                    directory_path=path,
                    entries=(DirectoryEntryState(readme, "README.md", "file"),),
                    cursor_path=readme,
                ),
                child_pane=PaneState(
                    directory_path=path,
                    entries=(),
                    mode="preview",
                    preview_path=readme,
                    preview_content="# Title\npreview body\n",
                ),
            )
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test():
        await _wait_for_snapshot_loaded(app, path)
        await _wait_for_row_count(app, 1)
        await app._dispatch_key_press("escape")
        await app._dispatch_key_press("[")
        await app._dispatch_key_press("0")
        await app._dispatch_key_press("c")

        notification = app.app_state.notification
        assert notification is None or "Copied" not in notification.message

@pytest.mark.asyncio
async def test_textual_parser_ignores_terminal_device_attributes_response() -> None:
    from textual._xterm_parser import XTermParser

    from zivo.app_terminal_response import _install_textual_terminal_response_filters

    _install_textual_terminal_response_filters()
    parser = XTermParser()

    events = list(parser.feed("\x1b[0c"))

    assert events == []

@pytest.mark.asyncio
async def test_textual_parser_ignores_terminal_osc_color_response() -> None:
    from textual._xterm_parser import XTermParser

    from zivo.app_terminal_response import _install_textual_terminal_response_filters

    _install_textual_terminal_response_filters()
    parser = XTermParser()

    events = list(parser.feed("\x1b]10;rgb:0000/0000/0000\x1b\\"))

    assert events == []
    assert list(parser.feed("")) == []

@pytest.mark.asyncio
async def test_textual_parser_ignores_split_terminal_osc_color_response() -> None:
    from textual._xterm_parser import XTermParser

    from zivo.app_terminal_response import _install_textual_terminal_response_filters

    _install_textual_terminal_response_filters()
    parser = XTermParser()

    assert list(parser.feed("\x1b]10;rgb:0000")) == []
    assert list(parser.feed("/0000/0000\x1b")) == []
    assert list(parser.feed("\\")) == []
    assert list(parser.feed("")) == []

@pytest.mark.asyncio
async def test_app_browsing_preview_scrolls_with_brackets() -> None:
    path = str(Path("/tmp/zivo-preview-scroll").resolve())
    readme = f"{path}/README.md"
    preview_body = "\n".join(f"line {index:03d}" for index in range(160))
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: BrowserSnapshot(
                current_path=path,
                parent_pane=PaneState(
                    directory_path="/tmp",
                    entries=(
                        DirectoryEntryState(path, "zivo-preview-scroll", "dir"),
                        DirectoryEntryState("/tmp/sibling", "sibling", "dir"),
                    ),
                    cursor_path=path,
                ),
                current_pane=PaneState(
                    directory_path=path,
                    entries=(DirectoryEntryState(readme, "README.md", "file"),),
                    cursor_path=readme,
                ),
                child_pane=PaneState(
                    directory_path=path,
                    entries=(),
                    mode="preview",
                    preview_path=readme,
                    preview_content=preview_body,
                ),
            )
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test():
        await _wait_for_snapshot_loaded(app, path)
        await _wait_for_row_count(app, 1)
        await _wait_for_child_preview(app, "Preview · README.md", "line 000")

        preview_help = app.query_one("#child-pane-preview-help", Label)
        assert str(preview_help.renderable) == (
            "Ctrl+J/K scroll preview  ·  [c] Copy selection"
        )
        assert preview_help.display is True

        child_preview_scroll = app.query_one("#child-pane-preview-scroll", VerticalScroll)
        initial_scroll_y = child_preview_scroll.scroll_y

        await app.action_dispatch_bound_key("ctrl+k")
        await asyncio.sleep(0.05)
        assert child_preview_scroll.scroll_y > initial_scroll_y

        scrolled_down_y = child_preview_scroll.scroll_y
        await app.action_dispatch_bound_key("ctrl+j")
        await asyncio.sleep(0.05)
        assert child_preview_scroll.scroll_y < scrolled_down_y

@pytest.mark.asyncio
async def test_app_selects_preview_text_and_copies_with_existing_copy_key() -> None:
    path = str(Path("/tmp/zivo-preview-selection").resolve())
    readme = f"{path}/README.md"
    selected_source = "alpha beta\ngamma delta\nthird line"
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: BrowserSnapshot(
                current_path=path,
                parent_pane=PaneState(
                    directory_path=str(Path(path).parent),
                    entries=(DirectoryEntryState(path, Path(path).name, "dir"),),
                    cursor_path=path,
                ),
                current_pane=PaneState(
                    directory_path=path,
                    entries=(DirectoryEntryState(readme, "README.md", "file"),),
                    cursor_path=readme,
                ),
                child_pane=PaneState(
                    directory_path=path,
                    entries=(),
                    mode="preview",
                    preview_path=readme,
                    preview_content=selected_source,
                ),
            )
        }
    )
    launch_service = FakeExternalLaunchService()
    app = create_app(
        snapshot_loader=loader,
        external_launch_service=launch_service,
        initial_path=path,
    )

    async with app.run_test(size=(120, 30)) as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await _wait_for_child_preview(app, "Preview · README.md", "alpha beta")
        preview = app.query_one("#child-pane-preview", Static)

        await pilot.mouse_down("#child-pane-preview", offset=(2, 0))
        await pilot._post_mouse_events(
            [MouseMove],
            widget="#child-pane-preview",
            offset=(10, 0),
            button=1,
        )
        await pilot.mouse_up("#child-pane-preview", offset=(10, 0))

        selected_text = app.query_one("#child-pane", ChildPane).selected_preview_text()
        assert selected_text
        assert selected_text in selected_source

        await app.action_dispatch_bound_key("c")
        await _wait_for_external_launch_count(app, 1)

        assert launch_service.executed_requests[0] == ExternalLaunchRequest(
            kind="copy_text",
            text=selected_text,
        )
        await _wait_for_notification_message(app, "Copied selection to system clipboard")

        await app.action_dispatch_bound_key("escape")
        assert app.query_one("#child-pane", ChildPane).selected_preview_text() is None
        assert preview.display is True

@pytest.mark.asyncio
async def test_app_mouse_click_moves_current_cursor() -> None:
    path = str(Path("/tmp/zivo-mouse-current").resolve())
    docs_path = f"{path}/docs"
    readme_path = f"{path}/README.md"
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                (
                    DirectoryEntryState(docs_path, "docs", "dir"),
                    DirectoryEntryState(readme_path, "README.md", "file"),
                ),
                child_path=docs_path,
                child_entries=(DirectoryEntryState(f"{docs_path}/guide.md", "guide.md", "file"),),
            )
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test(size=(120, 20)):
        await _wait_for_snapshot_loaded(app, path)
        await _wait_for_row_count(app, 2)
        pane = app.query_one("#current-pane", MainPane)

        assert app.app_state.current_pane.cursor_path == docs_path

        await pane.handle_table_row_clicked(1)

        assert app.app_state.current_pane.cursor_path == readme_path
        await app.action_dispatch_bound_key("up")
        assert app.app_state.current_pane.cursor_path == docs_path

@pytest.mark.asyncio
async def test_app_mouse_double_click_enters_directory() -> None:
    path = str(Path("/tmp/zivo-mouse-enter").resolve())
    docs_path = f"{path}/docs"
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                (
                    DirectoryEntryState(docs_path, "docs", "dir"),
                    DirectoryEntryState(f"{path}/README.md", "README.md", "file"),
                ),
                child_path=docs_path,
                child_entries=(DirectoryEntryState(f"{docs_path}/guide.md", "guide.md", "file"),),
            ),
            docs_path: _build_snapshot(
                docs_path,
                (DirectoryEntryState(f"{docs_path}/guide.md", "guide.md", "file"),),
                child_path=docs_path,
            ),
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test(size=(120, 20)):
        await _wait_for_snapshot_loaded(app, path)
        pane = app.query_one("#current-pane", MainPane)

        await pane.handle_table_row_clicked(0)
        await pane.handle_table_row_clicked(0)
        await _wait_for_snapshot_loaded(app, docs_path)

        assert app.app_state.current_path == docs_path

@pytest.mark.asyncio
async def test_app_row_selected_double_click_enters_directory() -> None:
    path = str(Path("/tmp/zivo-row-selected-enter").resolve())
    docs_path = f"{path}/docs"
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                (
                    DirectoryEntryState(docs_path, "docs", "dir"),
                    DirectoryEntryState(f"{path}/README.md", "README.md", "file"),
                ),
                child_path=docs_path,
                child_entries=(DirectoryEntryState(f"{docs_path}/guide.md", "guide.md", "file"),),
            ),
            docs_path: _build_snapshot(
                docs_path,
                (DirectoryEntryState(f"{docs_path}/guide.md", "guide.md", "file"),),
                child_path=docs_path,
            ),
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test(size=(120, 20)):
        await _wait_for_snapshot_loaded(app, path)
        pane = app.query_one("#current-pane", MainPane)
        await pane.handle_table_row_clicked(0)
        await pane.handle_table_row_clicked(0)
        await _wait_for_snapshot_loaded(app, docs_path)

        assert app.app_state.current_path == docs_path

@pytest.mark.asyncio
async def test_app_parent_pane_dir_single_click_enters_directory() -> None:
    path = str(Path("/tmp/zivo-parent-dir-click/current").resolve())
    parent_path = str(Path(path).parent)
    sibling_path = f"{parent_path}/sibling"
    sibling_file = f"{sibling_path}/notes.txt"
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: BrowserSnapshot(
                current_path=path,
                parent_pane=PaneState(
                    directory_path=parent_path,
                    entries=(
                        DirectoryEntryState(path, "current", "dir"),
                        DirectoryEntryState(sibling_path, "sibling", "dir"),
                    ),
                    cursor_path=path,
                ),
                current_pane=PaneState(
                    directory_path=path,
                    entries=(DirectoryEntryState(f"{path}/README.md", "README.md", "file"),),
                    cursor_path=f"{path}/README.md",
                ),
                child_pane=PaneState(
                    directory_path=path,
                    entries=(),
                ),
            ),
            sibling_path: BrowserSnapshot(
                current_path=sibling_path,
                parent_pane=PaneState(
                    directory_path=parent_path,
                    entries=(
                        DirectoryEntryState(path, "current", "dir"),
                        DirectoryEntryState(sibling_path, "sibling", "dir"),
                    ),
                    cursor_path=sibling_path,
                ),
                current_pane=PaneState(
                    directory_path=sibling_path,
                    entries=(
                        DirectoryEntryState(sibling_file, "notes.txt", "file"),
                    ),
                    cursor_path=sibling_file,
                ),
                child_pane=PaneState(
                    directory_path=sibling_path,
                    entries=(),
                    mode="preview",
                    preview_path=sibling_file,
                    preview_content="hello world",
                ),
            ),
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test(size=(120, 20)):
        await _wait_for_snapshot_loaded(app, path)
        await app.on_side_pane_entry_clicked(
            SidePane.EntryClicked("parent-pane", sibling_path, double_click=False)
        )
        await _wait_for_snapshot_loaded(app, sibling_path)

        assert app.app_state.current_path == sibling_path
        assert app.app_state.current_pane.cursor_path == sibling_file
        assert app.app_state.child_pane.mode == "preview"
        assert app.app_state.child_pane.preview_path == sibling_file
        assert app.app_state.child_pane.preview_content == "hello world"

        shell = select_shell_data(app.app_state)
        assert shell.child_pane.preview_path == sibling_file
        assert shell.child_pane.preview_content == "hello world"

@pytest.mark.asyncio
async def test_app_parent_pane_file_single_click_does_nothing() -> None:
    path = str(Path("/tmp/zivo-parent-file-single/current").resolve())
    parent_path = str(Path(path).parent)
    parent_file = f"{parent_path}/notes.txt"
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: BrowserSnapshot(
                current_path=path,
                parent_pane=PaneState(
                    directory_path=parent_path,
                    entries=(
                        DirectoryEntryState(path, "current", "dir"),
                        DirectoryEntryState(parent_file, "notes.txt", "file"),
                    ),
                    cursor_path=path,
                ),
                current_pane=PaneState(
                    directory_path=path,
                    entries=(DirectoryEntryState(f"{path}/README.md", "README.md", "file"),),
                    cursor_path=f"{path}/README.md",
                ),
                child_pane=PaneState(
                    directory_path=path,
                    entries=(),
                ),
            ),
        }
    )
    external_launch_service = FakeExternalLaunchService()
    app = create_app(
        snapshot_loader=loader,
        external_launch_service=external_launch_service,
        initial_path=path,
    )

    async with app.run_test():
        await _wait_for_snapshot_loaded(app, path)
        await app.on_side_pane_entry_clicked(
            SidePane.EntryClicked("parent-pane", parent_file, double_click=False)
        )

        assert app.app_state.current_path == path
        assert len(external_launch_service.executed_requests) == 0

@pytest.mark.asyncio
async def test_app_child_pane_dir_single_click_enters_directory() -> None:
    path = str(Path("/tmp/zivo-child-dir-click").resolve())
    docs_path = f"{path}/docs"
    guide_md = f"{docs_path}/guide.md"
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                (
                    DirectoryEntryState(docs_path, "docs", "dir"),
                    DirectoryEntryState(f"{path}/README.md", "README.md", "file"),
                ),
                child_path=path,
                child_entries=(DirectoryEntryState(docs_path, "docs", "dir"),),
            ),
            docs_path: BrowserSnapshot(
                current_path=docs_path,
                parent_pane=PaneState(
                    directory_path=str(Path(docs_path).parent),
                    entries=(
                        DirectoryEntryState(docs_path, "docs", "dir"),
                        DirectoryEntryState(f"{path}/sibling", "sibling", "dir"),
                    ),
                    cursor_path=docs_path,
                ),
                current_pane=PaneState(
                    directory_path=docs_path,
                    entries=(DirectoryEntryState(guide_md, "guide.md", "file"),),
                    cursor_path=guide_md,
                ),
                child_pane=PaneState(
                    directory_path=docs_path,
                    entries=(),
                    mode="preview",
                    preview_path=guide_md,
                    preview_content="# Guide\ndetail\n",
                ),
            ),
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test(size=(120, 20)):
        await _wait_for_snapshot_loaded(app, path)
        await app.on_child_pane_entry_clicked(
            ChildPane.EntryClicked("child-pane", docs_path, double_click=False)
        )
        await _wait_for_snapshot_loaded(app, docs_path)

        assert app.app_state.current_path == docs_path
        assert app.app_state.current_pane.cursor_path == guide_md
        assert app.app_state.child_pane.mode == "preview"
        assert app.app_state.child_pane.preview_path == guide_md

        shell = select_shell_data(app.app_state)
        assert shell.child_pane.preview_path == guide_md
        assert shell.child_pane.preview_content is not None

@pytest.mark.asyncio
async def test_app_child_pane_file_single_click_does_nothing() -> None:
    path = str(Path("/tmp/zivo-child-file-single").resolve())
    child_file = f"{path}/notes.txt"
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                (DirectoryEntryState(f"{path}/README.md", "README.md", "file"),),
                child_path=path,
                child_entries=(
                    DirectoryEntryState(f"{path}/README.md", "README.md", "file"),
                    DirectoryEntryState(child_file, "notes.txt", "file"),
                ),
            ),
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test(size=(120, 20)):
        await _wait_for_snapshot_loaded(app, path)
        await app.on_child_pane_entry_clicked(
            ChildPane.EntryClicked("child-pane", child_file, double_click=False)
        )

        assert app.app_state.current_path == path

@pytest.mark.asyncio
async def test_app_hides_text_preview_in_child_pane_when_preview_disabled() -> None:
    path = str(Path("/tmp/zivo-preview-disabled").resolve())
    readme = f"{path}/README.md"
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: BrowserSnapshot(
                current_path=path,
                parent_pane=PaneState(
                    directory_path="/tmp",
                    entries=(
                        DirectoryEntryState(path, "zivo-preview-disabled", "dir"),
                        DirectoryEntryState("/tmp/sibling", "sibling", "dir"),
                    ),
                    cursor_path=path,
                ),
                current_pane=PaneState(
                    directory_path=path,
                    entries=(DirectoryEntryState(readme, "README.md", "file"),),
                    cursor_path=readme,
                ),
                child_pane=PaneState(
                    directory_path=path,
                    entries=(),
                    mode="preview",
                    preview_path=readme,
                    preview_content="# Title\npreview body\n",
                ),
            )
        }
    )
    app = create_app(
        snapshot_loader=loader,
        initial_path=path,
        app_config=AppConfig(display=DisplayConfig(enable_text_preview=False)),
    )

    async with app.run_test():
        await _wait_for_snapshot_loaded(app, path)
        await _wait_for_row_count(app, 1)
        await _wait_for_child_preview(
            app,
            "Preview · README.md",
            "Preview disabled in settings",
        )

        child_list = app.query_one("#child-pane-list", Static)
        child_preview_scroll = app.query_one("#child-pane-preview-scroll", VerticalScroll)

        assert child_list.display is False
        assert child_preview_scroll.display is True
        preview = app.query_one("#child-pane-preview", Static)
        assert "[:] Edit config" in str(preview.renderable)

@pytest.mark.asyncio
async def test_app_updates_child_preview_when_cursor_moves_between_files() -> None:
    path = str(Path("/tmp/zivo-preview-switch").resolve())
    readme = f"{path}/README.md"
    config = f"{path}/config.toml"
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: BrowserSnapshot(
                current_path=path,
                parent_pane=PaneState(
                    directory_path="/tmp",
                    entries=(
                        DirectoryEntryState(path, "zivo-preview-switch", "dir"),
                        DirectoryEntryState("/tmp/sibling", "sibling", "dir"),
                    ),
                    cursor_path=path,
                ),
                current_pane=PaneState(
                    directory_path=path,
                    entries=(
                        DirectoryEntryState(readme, "README.md", "file"),
                        DirectoryEntryState(config, "config.toml", "file"),
                    ),
                    cursor_path=readme,
                ),
                child_pane=PaneState(
                    directory_path=path,
                    entries=(),
                    mode="preview",
                    preview_path=readme,
                    preview_content="# Title\npreview body\n",
                ),
            )
        },
        child_panes={
            (path, config): PaneState(
                directory_path=path,
                entries=(),
                mode="preview",
                preview_path=config,
                preview_content="[display]\nenable_text_preview = true\n",
            ),
        },
        child_delay_seconds={
            (path, config): 0.2,
        },
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test(size=(120, 20)):
        await _wait_for_snapshot_loaded(app, path)
        await _wait_for_row_count(app, 2)
        await _wait_for_child_preview(app, "Preview · README.md", "# Title")

        await app.dispatch_actions(
            (
                MoveCursor(
                    delta=1,
                    visible_paths=(readme, config),
                ),
            )
        )
        await _wait_for_cursor_path(app, config)
        await _wait_for_child_preview(
            app,
            "Preview · config.toml · loading",
            "Loading preview…",
            timeout=1.0,
        )
        await _wait_for_child_preview(app, "Preview · config.toml", "enable_text_preview = true")
        await _wait_for_child_pane_runtime_idle(app, timeout=1.0)

@pytest.mark.asyncio
async def test_app_renders_preview_message_for_unsupported_file_cursor() -> None:
    path = str(Path("/tmp/zivo-preview-unsupported").resolve())
    binary = f"{path}/archive.bin"
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: BrowserSnapshot(
                current_path=path,
                parent_pane=PaneState(
                    directory_path="/tmp",
                    entries=(
                        DirectoryEntryState(path, "zivo-preview-unsupported", "dir"),
                        DirectoryEntryState("/tmp/sibling", "sibling", "dir"),
                    ),
                    cursor_path=path,
                ),
                current_pane=PaneState(
                    directory_path=path,
                    entries=(DirectoryEntryState(binary, "archive.bin", "file"),),
                    cursor_path=binary,
                ),
                child_pane=PaneState(
                    directory_path=path,
                    entries=(),
                    mode="preview",
                    preview_path=binary,
                    preview_message="Preview unavailable for this file type",
                ),
            )
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test():
        await _wait_for_snapshot_loaded(app, path)
        await _wait_for_row_count(app, 1)
        await _wait_for_child_preview(
            app,
            "Preview · archive.bin",
            "Preview unavailable for this file type",
        )

@pytest.mark.asyncio
async def test_app_renders_preview_message_for_permission_denied_file_cursor() -> None:
    path = str(Path("/tmp/zivo-preview-permission-denied").resolve())
    readme = f"{path}/README.md"
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: BrowserSnapshot(
                current_path=path,
                parent_pane=PaneState(
                    directory_path="/tmp",
                    entries=(
                        DirectoryEntryState(path, "zivo-preview-permission-denied", "dir"),
                        DirectoryEntryState("/tmp/sibling", "sibling", "dir"),
                    ),
                    cursor_path=path,
                ),
                current_pane=PaneState(
                    directory_path=path,
                    entries=(DirectoryEntryState(readme, "README.md", "file"),),
                    cursor_path=readme,
                ),
                child_pane=PaneState(
                    directory_path=path,
                    entries=(),
                    mode="preview",
                    preview_path=readme,
                    preview_message="Preview unavailable: permission denied",
                ),
            )
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test():
        await _wait_for_snapshot_loaded(app, path)
        await _wait_for_row_count(app, 1)
        await _wait_for_child_preview(
            app,
            "Preview · README.md",
            "Preview unavailable: permission denied",
        )

@pytest.mark.asyncio
async def test_app_keeps_long_labels_readable_at_wide_breakpoint() -> None:
    path = str(Path("/tmp/zivo-narrow-truncate").resolve())
    current_entries = (
        DirectoryEntryState(
            f"{path}/reducer_common_directory",
            "reducer_common_directory",
            "dir",
        ),
        DirectoryEntryState(f"{path}/reducer_common.py", "reducer_common.py", "file"),
    )
    child_entries = (
        DirectoryEntryState(
            f"{path}/reducer_common_directory/child_reducer_entry_name_that_keeps_going.py",
            "child_reducer_entry_name_that_keeps_going.py",
            "file",
        ),
    )
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: BrowserSnapshot(
                current_path=path,
                parent_pane=PaneState(
                    directory_path="/tmp",
                    entries=(
                        DirectoryEntryState(
                            path,
                            "parent_directory_with_long_name_that_keeps_going.py",
                            "dir",
                        ),
                        DirectoryEntryState("/tmp/sibling", "another_parent_entry.py", "file"),
                    ),
                    cursor_path=path,
                ),
                current_pane=PaneState(
                    directory_path=path,
                    entries=current_entries,
                    cursor_path=current_entries[0].path,
                ),
                child_pane=PaneState(
                    directory_path=current_entries[0].path,
                    entries=child_entries,
                ),
            )
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test(size=(120, 20)):
        await _wait_for_snapshot_loaded(app, path)
        await _wait_for_row_count(app, 2)
        await asyncio.sleep(0.05)

        parent_list = app.query_one("#parent-pane-list", Static)
        child_list = app.query_one("#child-pane-list", Static)
        current_table = app.query_one("#current-pane-table", DataTable)

        parent_label = _side_pane_lines(parent_list)[0]
        child_label = _side_pane_lines(child_list)[0]
        current_name = current_table.get_row_at(0)[1]

        assert "~" in parent_label
        # At the wide breakpoint the child pane may have enough width to keep
        # the long filename intact; its semantic header and list remain mounted.
        assert child_label
        assert isinstance(current_name, Text)
        assert "~" in current_name.plain

@pytest.mark.asyncio
async def test_app_tab_keeps_focus_on_current_pane() -> None:
    path = str(Path("/tmp/zivo-tab-focus").resolve())
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

    async with app.run_test(size=(120, 20)) as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await _wait_for_row_count(app, 2)

        parent_list = app.query_one("#parent-pane-list", Static)
        current_table = app.query_one("#current-pane-table", DataTable)
        child_list = app.query_one("#child-pane-list", Static)

        assert parent_list.can_focus is False
        assert child_list.can_focus is False
        assert app.focused is current_table

        await pilot.press("tab", "tab")
        await asyncio.sleep(0.05)

        assert app.focused is current_table

@pytest.mark.asyncio
async def test_app_hides_tab_bar_until_multiple_tabs_are_open() -> None:
    path = str(Path("/tmp/zivo-single-tab").resolve())
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

    async with app.run_test(size=(120, 20)):
        await _wait_for_snapshot_loaded(app, path)

        tab_bar = await _wait_for_tab_bar(app)

        assert tab_bar.display is False

@pytest.mark.asyncio
async def test_app_number_keys_switch_between_browser_tabs() -> None:
    path = str(Path("/tmp/zivo-tabs").resolve())
    docs_path = f"{path}/docs"
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                (
                    DirectoryEntryState(docs_path, "docs", "dir"),
                    DirectoryEntryState(f"{path}/README.md", "README.md", "file"),
                ),
                child_path=docs_path,
                child_entries=(DirectoryEntryState(f"{docs_path}/guide.md", "guide.md", "file"),),
            ),
            docs_path: _build_snapshot(
                docs_path,
                (DirectoryEntryState(f"{docs_path}/guide.md", "guide.md", "file"),),
                child_path=docs_path,
            ),
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test(size=(120, 20)) as pilot:
        await _wait_for_snapshot_loaded(app, path)
        current_table = app.query_one("#current-pane-table", DataTable)

        await pilot.press("o")
        await asyncio.sleep(0.05)

        tab_bar = await _wait_for_tab_bar(app)
        assert tab_bar.display is True
        assert "[1:zivo-tabs]" in str(tab_bar.renderable)
        assert "[2:zivo-tabs]" in str(tab_bar.renderable)
        assert "[+]" in str(tab_bar.renderable)
        assert app.focused is current_table

        await pilot.press("enter")
        await _wait_for_snapshot_loaded(app, docs_path)

        current_path_bar = await _wait_for_current_path_bar(app)
        assert "Current Path:" in str(current_path_bar.renderable)

        await pilot.press("1")
        await _wait_for_snapshot_loaded(app, path)
        current_path_bar = await _wait_for_current_path_bar(app)
        assert "Current Path:" in str(current_path_bar.renderable)
        assert app.focused is current_table

        await pilot.press("2")
        await _wait_for_snapshot_loaded(app, docs_path)
        current_path_bar = await _wait_for_current_path_bar(app)
        assert "Current Path:" in str(current_path_bar.renderable)
        assert app.focused is current_table

@pytest.mark.asyncio
async def test_app_keyboard_input_updates_selection_and_child_pane() -> None:
    path = str(Path("/tmp/zivo-keyboard").resolve())
    current_entries = (
        DirectoryEntryState(f"{path}/docs", "docs", "dir"),
        DirectoryEntryState(f"{path}/src", "src", "dir"),
        DirectoryEntryState(f"{path}/README.md", "README.md", "file", size_bytes=120),
    )
    docs_child_entries = (DirectoryEntryState(f"{path}/docs/spec.md", "spec.md", "file"),)
    src_child_entries = (DirectoryEntryState(f"{path}/src/main.py", "main.py", "file"),)
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

    async with app.run_test(size=(120, 20)) as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await _wait_for_row_count(app, 3)
        await pilot.press("space")
        await _wait_for_child_entries(app, ["main.py"], timeout=1.0)

        child_list = app.query_one("#child-pane-list", Static)
        child_names = _side_pane_lines(child_list)
        current_path_bar = await _wait_for_current_path_bar(app)
        summary_bar = await _wait_for_summary_bar(app)
        status_bar = await _wait_for_status_bar(app)

        assert app.app_state.current_pane.selected_paths == {f"{path}/docs"}
        assert app.app_state.current_pane.cursor_path == f"{path}/src"
        assert child_names == ["main.py"]
        assert "Current Path:" in str(current_path_bar.renderable)
        assert str(summary_bar.renderable) == ("3 items | 1 selected | sort: name asc")
        assert str(status_bar.renderable) == ""

        current_table = app.query_one("#current-pane-table", DataTable)
        current_pane = app.query_one("#current-pane", MainPane)
        first_row = current_table.get_row_at(0)

        assert isinstance(first_row[0], Text)
        assert first_row[0].plain == "*"
        assert _text_style_matches(
            first_row[0],
            _style_without_background(
                current_pane.get_component_rich_style("ft-directory-sel-table")
            ),
        )
        assert first_row[1].plain == "docs"
        await _wait_for_child_pane_runtime_idle(app, timeout=1.0)

@pytest.mark.asyncio
async def test_app_child_pane_updates_immediately_on_rapid_cursor_moves() -> None:
    path = str(Path("/tmp/zivo-child-pane-debounce").resolve())
    current_entries = (
        DirectoryEntryState(f"{path}/docs", "docs", "dir"),
        DirectoryEntryState(f"{path}/src", "src", "dir"),
        DirectoryEntryState(f"{path}/tests", "tests", "dir"),
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
            ),
            (path, f"{path}/tests"): PaneState(
                directory_path=f"{path}/tests",
                entries=(
                    DirectoryEntryState(f"{path}/tests/test_main.py", "test_main.py", "file"),
                ),
            ),
        },
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test(size=(120, 20)) as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await _wait_for_row_count(app, 3)
        await pilot.press("down", "down")
        await _wait_for_cursor_path(app, f"{path}/tests")
        await _wait_for_child_entries(app, ["test_main.py"], timeout=1.0)
        await _wait_for_child_pane_request_count(loader, 2, timeout=1.0)
        assert loader.executed_child_pane_requests == [
            (path, f"{path}/src"),
            (path, f"{path}/tests"),
        ]
        await _wait_for_child_pane_runtime_idle(app, timeout=1.0)

@pytest.mark.asyncio
async def test_app_hides_stale_child_entries_while_new_child_snapshot_is_pending() -> None:
    path = str(Path("/tmp/zivo-child-pane-pending").resolve())
    child_snapshot_release_event = threading.Event()
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
            ),
        },
        child_snapshot_release_events={
            (path, f"{path}/src"): child_snapshot_release_event,
        },
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test(size=(120, 20)) as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await _wait_for_row_count(app, 2)
        await _wait_for_child_entries(app, ["spec.md"])

        await pilot.press("down")
        await _wait_for_cursor_path(app, f"{path}/src")
        try:
            await _wait_for_child_pane_request_count(loader, 1, timeout=1.0)
            await pilot.pause()

            loading_child_pane = select_shell_data(app.app_state).child_pane
            assert loading_child_pane.header_title == "Contents · src · loading"
            assert loading_child_pane.entries == ()
            assert loading_child_pane.status is not None
            assert loading_child_pane.status.kind == "loading"
            assert loading_child_pane.status.title == "Loading directory…"

            await _wait_for_child_preview(
                app,
                "Contents · src · loading",
                "Loading directory…",
                timeout=2.0,
            )
        finally:
            child_snapshot_release_event.set()
        await _wait_for_child_entries(app, ["main.py"], timeout=1.0)
        await _wait_for_child_pane_runtime_idle(app, timeout=1.0)

@pytest.mark.asyncio
async def test_app_shift_down_selects_range_and_down_clears_it() -> None:
    path = str(Path("/tmp/zivo-range-selection").resolve())
    current_entries = (
        DirectoryEntryState(f"{path}/docs", "docs", "dir"),
        DirectoryEntryState(f"{path}/src", "src", "dir"),
        DirectoryEntryState(f"{path}/tests", "tests", "dir"),
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
            ),
            (path, f"{path}/tests"): PaneState(
                directory_path=f"{path}/tests",
                entries=(
                    DirectoryEntryState(f"{path}/tests/test_main.py", "test_main.py", "file"),
                ),
            ),
        },
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test(size=(120, 20)):
        await _wait_for_snapshot_loaded(app, path)
        await _wait_for_row_count(app, 3)

        await app.action_dispatch_bound_key("shift+down")
        await asyncio.sleep(0.05)

        assert app.app_state.current_pane.selected_paths == {f"{path}/docs", f"{path}/src"}
        assert app.app_state.current_pane.cursor_path == f"{path}/src"
        assert app.app_state.current_pane.selection_anchor_path == f"{path}/docs"

        await app.action_dispatch_bound_key("down")
        await asyncio.sleep(0.05)

        assert app.app_state.current_pane.selected_paths == set()
        assert app.app_state.current_pane.cursor_path == f"{path}/tests"
        assert app.app_state.current_pane.selection_anchor_path is None

@pytest.mark.asyncio
async def test_app_cut_marks_row_with_dimmed_style() -> None:
    path = str(Path("/tmp/zivo-cut").resolve())
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

    async with app.run_test(size=(120, 20)) as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await _wait_for_row_count(app, 2)
        await pilot.press("x")
        await asyncio.sleep(0.05)

        current_table = app.query_one("#current-pane-table", DataTable)
        current_pane = app.query_one("#current-pane", MainPane)
        first_row = current_table.get_row_at(0)

        assert app.app_state.clipboard.mode == "cut"
        assert app.app_state.clipboard.paths == (f"{path}/docs",)
        assert isinstance(first_row[1], Text)
        assert first_row[1].plain == "docs"
        assert _text_style_matches(
            first_row[1],
            _style_without_background(current_pane.get_component_rich_style("ft-directory-cut")),
        )

@pytest.mark.asyncio
async def test_app_cut_uses_targeted_row_updates(monkeypatch) -> None:
    path = str(Path("/tmp/zivo-cut-row-delta").resolve())
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
    set_entries_calls = 0
    apply_row_updates_calls = 0
    original_set_entries = MainPane.set_entries
    original_apply_row_updates = MainPane.apply_row_updates

    def wrapped_set_entries(self, entries, cursor_index=None):
        nonlocal set_entries_calls
        set_entries_calls += 1
        return original_set_entries(self, entries, cursor_index)

    def wrapped_apply_row_updates(self, updates):
        nonlocal apply_row_updates_calls
        apply_row_updates_calls += 1
        return original_apply_row_updates(self, updates)

    monkeypatch.setattr(MainPane, "set_entries", wrapped_set_entries)
    monkeypatch.setattr(MainPane, "apply_row_updates", wrapped_apply_row_updates)

    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await _wait_for_row_count(app, 2)
        full_refresh_calls_before_cut = set_entries_calls

        await pilot.press("x")
        await asyncio.sleep(0.05)

        assert set_entries_calls == full_refresh_calls_before_cut
        assert apply_row_updates_calls == 1

@pytest.mark.asyncio
async def test_app_right_enters_directory_and_left_returns_to_parent() -> None:
    root = str(Path("/tmp/zivo-nav").resolve())
    docs = f"{root}/docs"
    root_entries = (
        DirectoryEntryState(docs, "docs", "dir"),
        DirectoryEntryState(f"{root}/README.md", "README.md", "file", size_bytes=120),
    )
    docs_entries = (DirectoryEntryState(f"{docs}/guide.md", "guide.md", "file", size_bytes=42),)
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
        assert "Current Path:" in str(current_path_bar.renderable)

        await pilot.press("right")
        await _wait_for_path(app, docs)
        assert "Current Path:" in str(current_path_bar.renderable)

        current_table = app.query_one("#current-pane-table", DataTable)
        assert app.app_state.current_path == docs
        assert current_table.cursor_row == 0

        await pilot.press("left")
        await _wait_for_path(app, root)
        assert "Current Path:" in str(current_path_bar.renderable)

        assert app.app_state.current_path == root
        assert app.app_state.current_pane.cursor_path == docs
        assert current_table.cursor_row == 0

@pytest.mark.asyncio
async def test_app_left_can_move_above_initial_directory() -> None:
    initial_path = str(Path("/tmp/zivo-nav/deeper").resolve())
    parent_path = str(Path("/tmp/zivo-nav").resolve())
    grandparent_path = "/tmp"
    parent_entries = (
        DirectoryEntryState(initial_path, "deeper", "dir"),
        DirectoryEntryState(f"{parent_path}/sibling", "sibling", "dir"),
    )
    grandparent_entries = (
        DirectoryEntryState(parent_path, "zivo-nav", "dir"),
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
        await pilot.press("left")
        await _wait_for_path(app, parent_path)
        await pilot.press("left")
        await _wait_for_path(app, grandparent_path)

        assert app.app_state.current_pane.cursor_path == parent_path

@pytest.mark.asyncio
async def test_app_left_on_windows_drive_root_returns_to_drive_list(monkeypatch) -> None:
    monkeypatch.setattr("zivo.windows_paths.platform.system", lambda: "Windows")
    drive_entries = (
        DirectoryEntryState("C:\\", "C:\\", "dir"),
        DirectoryEntryState("D:\\", "D:\\", "dir"),
    )
    c_drive_entries = (
        DirectoryEntryState("C:\\Users", "Users", "dir"),
        DirectoryEntryState("C:\\Temp", "Temp", "dir"),
    )
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            WINDOWS_DRIVES_ROOT: BrowserSnapshot(
                current_path=WINDOWS_DRIVES_ROOT,
                parent_pane=PaneState(
                    directory_path=WINDOWS_DRIVES_ROOT,
                    entries=(),
                ),
                current_pane=PaneState(
                    directory_path=WINDOWS_DRIVES_ROOT,
                    entries=drive_entries,
                    cursor_path="C:\\",
                ),
                child_pane=PaneState(directory_path="C:\\", entries=c_drive_entries),
            ),
            "C:\\": BrowserSnapshot(
                current_path="C:\\",
                parent_pane=PaneState(
                    directory_path=WINDOWS_DRIVES_ROOT,
                    entries=drive_entries,
                    cursor_path="C:\\",
                ),
                current_pane=PaneState(
                    directory_path="C:\\",
                    entries=c_drive_entries,
                    cursor_path="C:\\Users",
                ),
                child_pane=PaneState(directory_path="C:\\Users", entries=()),
            ),
        }
    )
    app = create_app(snapshot_loader=loader, initial_path="C:\\")

    async with app.run_test() as pilot:
        await _wait_for_path(app, "C:\\")
        current_path_bar = await _wait_for_current_path_bar(app)
        assert "Current Path:" in str(current_path_bar.renderable)

        await pilot.press("left")
        await _wait_for_path(app, WINDOWS_DRIVES_ROOT)
        assert "Drives" in str(current_path_bar.renderable)
        assert app.app_state.current_pane.cursor_path == "C:\\"

@pytest.mark.asyncio
async def test_app_palette_reload_keeps_cursor_when_entry_still_exists() -> None:
    path = str(Path("/tmp/zivo-reload").resolve())
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

        await pilot.press(":")
        await pilot.press("r", "e", "l", "o", "a", "d", "enter")
        await _wait_for_snapshot_loaded(app, path)

        current_table = app.query_one("#current-pane-table", DataTable)
        assert app.app_state.current_pane.cursor_path == f"{path}/src"
        assert current_table.cursor_row == 1

@pytest.mark.asyncio
async def test_app_palette_reload_falls_back_to_first_row_when_cursor_disappears() -> None:
    path = str(Path("/tmp/zivo-reload-fallback").resolve())
    initial_entries = (
        DirectoryEntryState(f"{path}/docs", "docs", "dir"),
        DirectoryEntryState(f"{path}/src", "src", "dir"),
    )
    reloaded_entries = (DirectoryEntryState(f"{path}/docs", "docs", "dir"),)
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

        await pilot.press(":")
        await pilot.press("r", "e", "l", "o", "a", "d", "enter")
        await _wait_for_snapshot_loaded(app, path)

        current_table = app.query_one("#current-pane-table", DataTable)
        assert app.app_state.current_pane.cursor_path == f"{path}/docs"
        assert current_table.cursor_row == 0

@pytest.mark.asyncio
async def test_app_palette_reload_drops_selection_for_missing_entries() -> None:
    path = str(Path("/tmp/zivo-reload-selection").resolve())
    initial_entries = (
        DirectoryEntryState(f"{path}/docs", "docs", "dir"),
        DirectoryEntryState(f"{path}/src", "src", "dir"),
    )
    reloaded_entries = (DirectoryEntryState(f"{path}/src", "src", "dir"),)
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

        await pilot.press(":")
        await pilot.press("r", "e", "l", "o", "a", "d", "enter")
        await _wait_for_snapshot_loaded(app, path)

        summary_bar = await _wait_for_summary_bar(app)
        status_bar = await _wait_for_status_bar(app)

        assert app.app_state.current_pane.selected_paths == set()
        assert app.app_state.current_pane.cursor_path == f"{path}/src"
        assert str(summary_bar.renderable) == ("1 items | 0 selected | sort: name asc")
        assert str(status_bar.renderable) == ""

@pytest.mark.asyncio
async def test_app_navigation_clears_selection_in_new_directory() -> None:
    root = str(Path("/tmp/zivo-selection-nav").resolve())
    docs = f"{root}/docs"
    root_entries = (DirectoryEntryState(docs, "docs", "dir"),)
    docs_entries = (DirectoryEntryState(f"{docs}/guide.md", "guide.md", "file", size_bytes=42),)
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
        assert str(summary_bar.renderable) == ("1 items | 0 selected | sort: name asc")
        assert str(status_bar.renderable) == ""

@pytest.mark.asyncio
async def test_app_refresh_updates_widgets_in_place() -> None:
    path = str(Path("/tmp/zivo-refresh").resolve())
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
        child_list = app.query_one("#child-pane-list", Static)

        await pilot.press("down")
        await asyncio.sleep(0.05)

        assert app.query_one("#body") is body
        assert app.query_one("#current-path-bar", CurrentPathBar) is current_path_bar
        assert app.query_one("#current-pane-summary-bar", SummaryBar) is summary_bar
        assert app.query_one("#status-bar", StatusBar) is status_bar
        assert app.query_one("#current-pane-table", DataTable) is current_table
        assert app.query_one("#child-pane-list", Static) is child_list

@pytest.mark.asyncio
async def test_app_cursor_move_does_not_rebuild_current_table_rows(monkeypatch) -> None:
    path = str(Path("/tmp/zivo-cursor-stable").resolve())
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

        current_table = app.query_one("#current-pane-table", DataTable)
        original_clear = DataTable.clear
        original_add_row = DataTable.add_row
        clear_calls = 0
        add_row_calls = 0

        def counting_clear(self, columns: bool = False):
            nonlocal clear_calls
            if self is current_table:
                clear_calls += 1
            return original_clear(self, columns=columns)

        def counting_add_row(self, *cells, **kwargs):
            nonlocal add_row_calls
            if self is current_table:
                add_row_calls += 1
            return original_add_row(self, *cells, **kwargs)

        monkeypatch.setattr(DataTable, "clear", counting_clear)
        monkeypatch.setattr(DataTable, "add_row", counting_add_row)

        await pilot.press("down")
        await asyncio.sleep(0.05)

        assert clear_calls == 0
        assert add_row_calls == 0
        assert current_table.cursor_row == 1

@pytest.mark.asyncio
async def test_app_refresh_keeps_parent_pane_items_when_entries_are_unchanged() -> None:
    path = str(Path("/tmp/zivo-parent-stable").resolve())
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

        parent_list = app.query_one("#parent-pane-list", Static)

        await pilot.press("down")
        await asyncio.sleep(0.05)

        assert app.query_one("#parent-pane-list", Static) is parent_list

@pytest.mark.asyncio
async def test_app_selection_toggle_avoids_rebuilding_large_current_pane(monkeypatch) -> None:
    path = str(Path("/tmp/zivo-large-selection").resolve())
    current_entries = tuple(
        DirectoryEntryState(f"{path}/file_{index:04d}.txt", f"file_{index:04d}.txt", "file")
        for index in range(1000)
    )
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                current_entries,
            )
        }
    )
    set_entries_calls = 0
    apply_row_updates_calls = 0
    original_set_entries = MainPane.set_entries
    original_apply_row_updates = MainPane.apply_row_updates

    def wrapped_set_entries(self, entries, cursor_index=None):
        nonlocal set_entries_calls
        set_entries_calls += 1
        return original_set_entries(self, entries, cursor_index)

    def wrapped_apply_row_updates(self, updates):
        nonlocal apply_row_updates_calls
        apply_row_updates_calls += 1
        return original_apply_row_updates(self, updates)

    monkeypatch.setattr(MainPane, "set_entries", wrapped_set_entries)
    monkeypatch.setattr(MainPane, "apply_row_updates", wrapped_apply_row_updates)

    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, path)
        visible_window = compute_current_pane_visible_window(app.app_state.terminal_height)
        await _wait_for_row_count(app, visible_window, timeout=2.0)

        current_table = app.query_one("#current-pane-table", DataTable)
        original_clear = DataTable.clear
        original_add_row = DataTable.add_row
        clear_calls = 0
        add_row_calls = 0

        def counting_clear(self, columns: bool = False):
            nonlocal clear_calls
            if self is current_table:
                clear_calls += 1
            return original_clear(self, columns=columns)

        def counting_add_row(self, *cells, **kwargs):
            nonlocal add_row_calls
            if self is current_table:
                add_row_calls += 1
            return original_add_row(self, *cells, **kwargs)

        monkeypatch.setattr(DataTable, "clear", counting_clear)
        monkeypatch.setattr(DataTable, "add_row", counting_add_row)
        full_refresh_calls_before_toggle = set_entries_calls

        await pilot.press("space")
        await asyncio.sleep(0.05)

        first_row = current_table.get_row_at(0)

        assert clear_calls == 0
        assert add_row_calls == 0
        assert set_entries_calls <= full_refresh_calls_before_toggle + 1
        assert apply_row_updates_calls == 1
        assert app.app_state.current_pane.selected_paths == {f"{path}/file_0000.txt"}
        assert current_table.cursor_row == 1
        assert isinstance(first_row[0], Text)
        assert first_row[0].plain == "*"

@pytest.mark.asyncio
async def test_app_directory_size_update_avoids_rebuilding_large_current_pane(monkeypatch) -> None:
    path = str(Path("/tmp/zivo-large-dir-size").resolve())
    current_entries = tuple(
        DirectoryEntryState(f"{path}/dir_{index:04d}", f"dir_{index:04d}", "dir")
        for index in range(1000)
    )
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                current_entries,
                child_path=current_entries[0].path,
            )
        }
    )
    directory_size_service = BlockingDirectorySizeService()
    app = create_app(
        snapshot_loader=loader,
        directory_size_service=directory_size_service,
        app_config=AppConfig(display=DisplayConfig(show_directory_sizes=True)),
        initial_path=path,
    )

    async with app.run_test(size=(120, 20)):
        await _wait_for_snapshot_loaded(app, path)
        visible_window = compute_current_pane_visible_window(app.app_state.terminal_height)
        await _wait_for_row_count(app, visible_window, timeout=2.0)

        current_table = app.query_one("#current-pane-table", DataTable)
        original_clear = DataTable.clear
        original_add_row = DataTable.add_row
        clear_calls = 0
        add_row_calls = 0

        def counting_clear(self, columns: bool = False):
            nonlocal clear_calls
            if self is current_table:
                clear_calls += 1
            return original_clear(self, columns=columns)

        def counting_add_row(self, *cells, **kwargs):
            nonlocal add_row_calls
            if self is current_table:
                add_row_calls += 1
            return original_add_row(self, *cells, **kwargs)

        monkeypatch.setattr(DataTable, "clear", counting_clear)
        monkeypatch.setattr(DataTable, "add_row", counting_add_row)

        directory_size_service.release()
        await _wait_for_directory_sizes(app, timeout=2.0)
        await _wait_for_table_cell(app, "1000 B", 0, 2, timeout=2.0)

        assert clear_calls == 0
        assert add_row_calls == 0

@pytest.mark.asyncio
async def test_app_default_viewport_projection_limits_rendered_rows_for_large_directory() -> None:
    path = str(Path("/tmp/zivo-viewport-large").resolve())
    current_entries = tuple(
        DirectoryEntryState(f"{path}/file_{index:04d}.txt", f"file_{index:04d}.txt", "file")
        for index in range(1000)
    )
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                current_entries,
            )
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test(size=(120, 20)):
        await _wait_for_snapshot_loaded(app, path)
        visible_window = compute_current_pane_visible_window(app.app_state.terminal_height)
        await _wait_for_row_count(app, visible_window, timeout=2.0)

        table = app.query_one("#current-pane-table", DataTable)
        first_row = table.get_row_at(0)

        assert table.row_count == visible_window
        assert isinstance(first_row[1], Text)
        assert first_row[1].plain == "file_0000.txt"
        assert app.app_state.current_pane_window_start == 0

@pytest.mark.asyncio
async def test_app_default_viewport_projection_shifts_window_after_cursor_crosses_edge() -> None:
    path = str(Path("/tmp/zivo-viewport-scroll").resolve())
    current_entries = tuple(
        DirectoryEntryState(f"{path}/file_{index:04d}.txt", f"file_{index:04d}.txt", "file")
        for index in range(40)
    )
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                current_entries,
            )
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test(size=(120, 20)) as pilot:
        await _wait_for_snapshot_loaded(app, path)
        visible_window = compute_current_pane_visible_window(app.app_state.terminal_height)
        await _wait_for_row_count(app, visible_window, timeout=2.0)

        table = app.query_one("#current-pane-table", DataTable)
        for _ in range(visible_window):
            await pilot.press("down")
        await _wait_for_cursor_path(app, current_entries[visible_window].path, timeout=2.0)
        await _wait_for_table_cell(app, "file_0002.txt", 0, 1, timeout=2.0)

        last_row = table.get_row_at(table.row_count - 1)

        assert table.row_count == visible_window
        assert isinstance(last_row[1], Text)
        assert last_row[1].plain == f"file_{visible_window + 1:04d}.txt"
        assert app.app_state.current_pane_window_start == 2

@pytest.mark.asyncio
async def test_app_default_viewport_projection_pages_and_jumps_without_losing_cursor() -> None:
    path = str(Path("/tmp/zivo-viewport-page-jump").resolve())
    current_entries = tuple(
        DirectoryEntryState(f"{path}/file_{index:04d}.txt", f"file_{index:04d}.txt", "file")
        for index in range(40)
    )
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                current_entries,
            )
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test(size=(120, 20)):
        await _wait_for_snapshot_loaded(app, path)
        visible_window = compute_current_pane_visible_window(app.app_state.terminal_height)
        visible_paths = tuple(entry.path for entry in current_entries)
        await _wait_for_row_count(app, visible_window, timeout=2.0)

        await app.dispatch_actions(
            (MoveCursor(delta=visible_window, visible_paths=visible_paths),)
        )
        await _wait_for_cursor_path(app, current_entries[visible_window].path, timeout=2.0)
        await _wait_for_table_cell(app, "file_0002.txt", 0, 1, timeout=2.0)
        assert app.app_state.current_pane_window_start == 2

        await app.dispatch_actions(
            (MoveCursor(delta=-visible_window, visible_paths=visible_paths),)
        )
        await _wait_for_cursor_path(app, current_entries[0].path, timeout=2.0)
        await _wait_for_table_cell(app, "file_0000.txt", 0, 1, timeout=2.0)
        assert app.app_state.current_pane_window_start == 0

        await app.dispatch_actions((JumpCursor(position="end", visible_paths=visible_paths),))
        window_start_at_end = len(current_entries) - visible_window
        await _wait_for_cursor_path(app, current_entries[-1].path, timeout=2.0)
        await _wait_for_table_cell(
            app,
            f"file_{window_start_at_end:04d}.txt",
            0,
            1,
            timeout=2.0,
        )
        assert app.app_state.current_pane_window_start == window_start_at_end

        await app.dispatch_actions((JumpCursor(position="start", visible_paths=visible_paths),))
        await _wait_for_cursor_path(app, current_entries[0].path, timeout=2.0)
        await _wait_for_table_cell(app, "file_0000.txt", 0, 1, timeout=2.0)
        assert app.app_state.current_pane_window_start == 0

@pytest.mark.asyncio
async def test_app_default_viewport_projection_recalculates_window_after_resize() -> None:
    path = str(Path("/tmp/zivo-viewport-resize").resolve())
    current_entries = tuple(
        DirectoryEntryState(f"{path}/file_{index:04d}.txt", f"file_{index:04d}.txt", "file")
        for index in range(40)
    )
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                current_entries,
            )
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test(size=(120, 20)):
        await _wait_for_snapshot_loaded(app, path)
        visible_window = compute_current_pane_visible_window(app.app_state.terminal_height)
        visible_paths = tuple(entry.path for entry in current_entries)
        await _wait_for_row_count(app, visible_window, timeout=2.0)

        await app.dispatch_actions(
            (MoveCursor(delta=visible_window, visible_paths=visible_paths),)
        )
        await _wait_for_cursor_path(app, current_entries[visible_window].path, timeout=2.0)

        await app.dispatch_actions((SetTerminalHeight(height=12),))

        resized_window = compute_current_pane_visible_window(12)
        resized_window_start = visible_window - resized_window + 1
        await _wait_for_row_count(app, resized_window, timeout=2.0)
        await _wait_for_table_cell(
            app,
            f"file_{resized_window_start:04d}.txt",
            0,
            1,
            timeout=2.0,
        )

        assert app.app_state.current_pane_window_start == resized_window_start
        assert app.app_state.current_pane.cursor_path == current_entries[visible_window].path

@pytest.mark.asyncio
async def test_app_file_cursor_clears_child_pane() -> None:
    path = str(Path("/tmp/zivo-file").resolve())
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
        await _wait_for_child_entries(app, [])

        child_list = app.query_one("#child-pane-list", Static)

        assert app.app_state.current_pane.cursor_path == f"{path}/README.md"
        assert _side_pane_lines(child_list) == []

@pytest.mark.asyncio
async def test_app_child_snapshot_failure_shows_error() -> None:
    path = str(Path("/tmp/zivo-failure").resolve())
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
        await _wait_for_child_entries(app, [], timeout=1.0)
        await _wait_for_status_message(app, "error: permission denied", timeout=1.0)

        child_list = app.query_one("#child-pane-list", Static)
        current_path_bar = await _wait_for_current_path_bar(app)
        summary_bar = await _wait_for_summary_bar(app)
        status_bar = await _wait_for_status_bar(app)

        assert _side_pane_lines(child_list) == []
        assert "Current Path:" in str(current_path_bar.renderable)
        assert str(summary_bar.renderable) == "2 items | 0 selected | sort: name asc"
        assert str(status_bar.renderable) == "error: permission denied"
        await _wait_for_child_pane_runtime_idle(app, timeout=1.0)

@pytest.mark.asyncio
async def test_app_displays_browsing_help_bar() -> None:
    path = str(Path("/tmp/zivo-help").resolve())
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
    split_terminal_hint = " | t term" if os.name == "posix" else ""
    expected_help = (
        "enter open | e edit | / filter | s sort | . hidden | [ ] bk/fwd | q quit\n"
        "space select | c copy | x cut | v paste | d trash | r rename | z undo\n"
            f"f find | g grep | G go | n new-file | N new-dir{split_terminal_hint} | : palette"
    )

    async with app.run_test():
        await _wait_for_snapshot_loaded(app, path)
        help_bar = await _wait_for_help_bar_text(app, expected_help)

        assert str(help_bar.renderable) == expected_help

@pytest.mark.asyncio
async def test_app_transfer_mode_refreshes_left_cursor_and_focuses_right_pane() -> None:
    path = str(Path("/tmp/zivo-transfer-focus").resolve())
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                (
                    DirectoryEntryState(f"{path}/docs", "docs", "dir"),
                    DirectoryEntryState(f"{path}/src", "src", "dir"),
                    DirectoryEntryState(f"{path}/README.md", "README.md", "file"),
                ),
                child_path=f"{path}/docs",
            )
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test(size=(120, 20)) as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await _wait_for_row_count(app, 3)

        await pilot.press("p")
        right_table = await _wait_for_transfer_right_table(app)
        left_table = app.query_one("#current-pane-table", DataTable)
        left_pane = app.query_one("#current-pane", MainPane)
        right_pane = app.query_one("#transfer-right-pane", MainPane)

        assert left_table.cursor_row == 0
        assert right_table.cursor_row == 0
        assert left_pane.has_class("active-transfer-pane")
        assert not right_pane.has_class("active-transfer-pane")

        await pilot.press("down")
        await pilot.pause()

        assert app.app_state.transfer_left is not None
        assert app.app_state.transfer_left.pane.cursor_path == f"{path}/src"
        assert left_table.cursor_row == 1

        await pilot.press("tab")
        await pilot.pause()

        assert app.app_state.active_transfer_pane == "right"
        assert not left_pane.has_class("active-transfer-pane")
        assert right_pane.has_class("active-transfer-pane")
        assert app.focused is right_table

@pytest.mark.asyncio
async def test_app_transfer_mode_mouse_click_updates_active_pane_and_cursor() -> None:
    path = str(Path("/tmp/zivo-transfer-mouse").resolve())
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                (
                    DirectoryEntryState(f"{path}/docs", "docs", "dir"),
                    DirectoryEntryState(f"{path}/src", "src", "dir"),
                    DirectoryEntryState(f"{path}/README.md", "README.md", "file"),
                ),
                child_path=f"{path}/docs",
            )
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test(size=(120, 20)) as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await _wait_for_row_count(app, 3)
        await pilot.press("p")
        await _wait_for_transfer_right_table(app)

        await app._handle_main_pane_click("transfer-right-pane", f"{path}/src", double_click=False)

        assert app.app_state.active_transfer_pane == "right"
        assert app.app_state.transfer_right is not None
        assert app.app_state.transfer_right.pane.cursor_path == f"{path}/src"

@pytest.mark.asyncio
async def test_app_displays_transfer_help_bar() -> None:
    path = str(Path("/tmp/zivo-transfer-help").resolve())
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
    expected_help = (
        "enter dir | . hidden | Tab switch-pane | p/Esc close | q quit\n"
        "space select | c copy-to-pane | m move-to-pane | d trash | r rename | z undo\n"
            "n new-file | N new-dir | G go | : palette"
    )

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await pilot.press("p")
        help_bar = await _wait_for_help_bar_text(app, expected_help)

        assert str(help_bar.renderable) == expected_help

@pytest.mark.asyncio
async def test_app_opens_command_palette_from_transfer_mode_with_colon() -> None:
    path = str(Path("/tmp/zivo-transfer-palette").resolve())
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
        await pilot.press("p")
        notification = NotificationState(
            level="error",
            message="Paste failed",
            action=NotificationAction(
                action_id="notification.retry",
                label="Retry",
            ),
        )
        await app.dispatch_actions((SetNotification(notification),))
        await pilot.press(":")
        palette = await _wait_for_command_palette(app)

        assert app.app_state.ui_mode == "PALETTE"
        assert palette.display is True
        assert app.app_state.notification == notification
        assert "Suggested" in str(
            palette.query_one("#command-palette-items", Static).renderable
        )

def test_transfer_mode_does_not_use_preview_scroll_keys_for_child_preview() -> None:
    state = replace(
        build_initial_app_state(),
        layout_mode="transfer",
        child_pane=PaneState(directory_path="/tmp", entries=(), mode="preview"),
    )

    assert _preview_scroll_delta(state, "[") is None
    assert _preview_scroll_delta(state, "]") is None

@pytest.mark.asyncio
async def test_app_pressing_z_runs_undo() -> None:
    path = str(Path("/tmp/zivo-undo").resolve())
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                (DirectoryEntryState(f"{path}/docs", "docs", "dir"),),
                child_path=f"{path}/docs",
            )
        }
    )
    undo_entry = UndoEntry(
        kind="paste_copy",
        steps=(UndoDeletePathStep(path=f"{path}/docs copy"),),
    )
    undo_service = FakeUndoService(
        results={
            undo_entry: UndoResult(
                path=None,
                message="Undid copied item",
                removed_paths=(f"{path}/docs copy",),
            )
        }
    )
    app = create_app(snapshot_loader=loader, undo_service=undo_service, initial_path=path)

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, path)
        app._app_state = replace(app.app_state, undo_stack=(undo_entry,))
        await pilot.press("z")
        await _wait_for_status_message(app, "info: Undid copied item", timeout=1.0)

        assert app.app_state.undo_stack == ()

@pytest.mark.asyncio
@pytest.mark.skip(reason="Exit confirmation requires manual testing")
async def test_app_pressing_q_shows_exit_confirmation_dialog() -> None:
    path = str(Path("/tmp/zivo-quit").resolve())
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
        await pilot.press("q")
        await asyncio.sleep(0.05)
        assert app.app_state.exit_confirmation is not None
        assert app.app_state.ui_mode == "CONFIRM"
        await pilot.press("enter")
        await asyncio.sleep(0.05)

    assert app.return_value == path

@pytest.mark.asyncio
async def test_app_colon_shows_command_palette() -> None:
    path = str(Path("/tmp/zivo-command-palette").resolve())
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
        notification = NotificationState(
            level="error",
            message="Paste failed",
            action=NotificationAction(
                action_id="notification.details",
                label="Details",
            ),
        )
        await app.dispatch_actions((SetNotification(notification),))
        await pilot.press(":")
        await asyncio.sleep(0.05)

        palette = await _wait_for_command_palette(app)
        items = palette.query_one("#command-palette-items", Static)

        assert app.app_state.ui_mode == "PALETTE"
        assert palette.display is True
        assert app.app_state.notification == notification
        assert "Suggested" in str(items.renderable)
        assert "Details" in str(items.renderable)
        assert "Enter folder" in str(items.renderable)

@pytest.mark.asyncio
async def test_app_command_palette_overlay_stays_top_aligned_without_resizing_main_pane() -> None:
    path = str(Path("/tmp/zivo-command-palette-overlay").resolve())
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
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test(size=(80, 24)) as pilot:
        await _wait_for_snapshot_loaded(app, path)
        current_pane = app.query_one("#current-pane")
        main_pane_width = current_pane.region.width

        await pilot.press(":")
        await asyncio.sleep(0.05)

        palette = await _wait_for_command_palette(app)
        palette_layer = app.query_one("#command-palette-layer")

        assert palette.region.y == palette_layer.region.y
        assert palette.region.bottom <= palette_layer.region.bottom
        assert "-expanded" in palette.classes
        assert current_pane.region.width == main_pane_width

@pytest.mark.asyncio
async def test_app_command_palette_stays_compact_when_filtered_results_fit() -> None:
    path = str(Path("/tmp/zivo-command-palette-compact").resolve())
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
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test(size=(80, 24)) as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await pilot.press(":")
        await pilot.press("r", "e", "n", "a", "m", "e")
        await asyncio.sleep(0.05)

        palette = await _wait_for_command_palette(app)
        palette_layer = app.query_one("#command-palette-layer")
        items = palette.query_one("#command-palette-items", Static)

        assert "-expanded" not in palette.classes
        assert palette.region.bottom < palette_layer.region.bottom
        assert "Rename" in str(items.renderable)

@pytest.mark.asyncio
async def test_app_palette_keeps_current_table_cursor_row() -> None:
    path = str(Path("/tmp/zivo-command-palette-cursor").resolve())
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                (
                    DirectoryEntryState(f"{path}/docs", "docs", "dir"),
                    DirectoryEntryState(f"{path}/src", "src", "dir"),
                    DirectoryEntryState(f"{path}/README.md", "README.md", "file"),
                ),
                child_path=f"{path}/docs",
            )
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=path)

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, path)
        current_table = app.query_one("#current-pane-table", DataTable)

        await pilot.press("down")
        await asyncio.sleep(0.05)
        assert current_table.cursor_row == 1

        await pilot.press(":")
        await asyncio.sleep(0.05)

        assert app.app_state.ui_mode == "PALETTE"
        assert current_table.cursor_row == 1
        assert current_table.show_cursor is True
