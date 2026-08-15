"""Test App Config tests."""

from tests.support.app import (
    AppConfig,
    BrowserSnapshot,
    ConfigSaveCompleted,
    DataTable,
    DirectoryEntryState,
    DisplayConfig,
    EditorConfig,
    ExternalLaunchRequest,
    FakeBrowserSnapshotLoader,
    FakeExternalLaunchService,
    FakeShellCommandService,
    LiveExternalLaunchService,
    PaneState,
    Path,
    ShellCommandResult,
    Static,
    _assert_region_vertically_centered,
    _build_snapshot,
    _side_pane_lines,
    _wait_for_app_theme,
    _wait_for_command_palette,
    _wait_for_config_dialog,
    _wait_for_context_input,
    _wait_for_external_launch_count,
    _wait_for_row_count,
    _wait_for_shell_command_dialog,
    _wait_for_snapshot_loaded,
    _wait_for_status_bar,
    _wait_for_summary_bar,
    asyncio,
    create_app,
    nullcontext,
    pytest,
    replace,
    select_shell_data,
)


@pytest.mark.asyncio
async def test_app_config_dialog_dismiss_restores_theme_preview() -> None:
    path = str(Path("/tmp/zivo-command-palette-theme-dismiss").resolve())
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
    app = create_app(
        snapshot_loader=loader,
        config_path="/tmp/zivo/config.toml",
        initial_path=path,
    )

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await pilot.press(":")
        await pilot.press("c", "o", "n", "f", "i", "g")
        await pilot.press("enter")
        await _wait_for_config_dialog(app)

        for _ in range(3):
            await pilot.press("down")
        await pilot.press("enter")
        await _wait_for_app_theme(app, "textual-light")

        assert app.app_state.config.display.theme == "textual-dark"

        await pilot.press("escape")
        await _wait_for_app_theme(app, "textual-dark")

        assert app.app_state.ui_mode == "BROWSING"
        assert app.app_state.config.display.theme == "textual-dark"

@pytest.mark.asyncio
async def test_app_config_dialog_theme_preview_updates_auto_syntax_theme() -> None:
    path = str(Path("/tmp/zivo-command-palette-theme-preview").resolve())
    preview_path = f"{path}/README.md"
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: BrowserSnapshot(
                current_path=path,
                parent_pane=PaneState(
                    directory_path="/tmp",
                    entries=(DirectoryEntryState(path, Path(path).name, "dir"),),
                    cursor_path=path,
                ),
                current_pane=PaneState(
                    directory_path=path,
                    entries=(
                        DirectoryEntryState(
                            preview_path,
                            "README.md",
                            "file",
                            size_bytes=120,
                        ),
                    ),
                    cursor_path=preview_path,
                ),
                child_pane=PaneState(
                    directory_path=path,
                    entries=(),
                    mode="preview",
                    preview_path=preview_path,
                    preview_title="Preview: README.md",
                    preview_content="# heading\nbody\n",
                ),
            )
        }
    )
    app = create_app(
        snapshot_loader=loader,
        config_path="/tmp/zivo/config.toml",
        initial_path=path,
    )

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, path)
        assert select_shell_data(app.app_state).child_pane.syntax_theme == "monokai"

        await pilot.press(":")
        await pilot.press("c", "o", "n", "f", "i", "g")
        await pilot.press("enter")
        await _wait_for_config_dialog(app)
        for _ in range(3):
            await pilot.press("down")
        await pilot.press("enter")
        await _wait_for_app_theme(app, "textual-light")

        assert select_shell_data(app.app_state).child_pane.syntax_theme == "friendly"

        await pilot.press("escape")
        await _wait_for_app_theme(app, "textual-dark")

        assert select_shell_data(app.app_state).child_pane.syntax_theme == "monokai"

@pytest.mark.asyncio
async def test_app_config_dialog_e_opens_config_file_in_editor() -> None:
    path = str(Path("/tmp/zivo-command-palette-config-editor").resolve())
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
    launch_service = FakeExternalLaunchService()
    app = create_app(
        snapshot_loader=loader,
        external_launch_service=launch_service,
        config_path="/tmp/zivo/config.toml",
        initial_path=path,
    )
    app.suspend = nullcontext  # type: ignore[method-assign]

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await pilot.press(":")
        await pilot.press("c", "o", "n", "f", "i", "g")
        await pilot.press("enter")
        await _wait_for_config_dialog(app)
        await pilot.press("e")
        await _wait_for_external_launch_count(app, 1)

        assert launch_service.executed_requests == [
            ExternalLaunchRequest(
                kind="open_editor",
                path="/tmp/zivo/config.toml",
                reload_config_after_exit=True,
            )
        ]

@pytest.mark.asyncio
async def test_app_config_dialog_height_stays_stable_across_settings() -> None:
    path = str(Path("/tmp/zivo-config-dialog-stable-height").resolve())
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
    app = create_app(
        snapshot_loader=loader,
        config_path="/tmp/zivo/config.toml",
        initial_path=path,
    )

    async with app.run_test(size=(100, 30)) as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await pilot.press(":")
        await pilot.press("c", "o", "n", "f", "i", "g")
        await pilot.press("enter")
        dialog = await _wait_for_config_dialog(app)

        initial_height = dialog.region.height

        for _ in range(11):
            await pilot.press("down")
            await asyncio.sleep(0.01)
            assert dialog.region.height == initial_height

@pytest.mark.asyncio
async def test_app_config_save_refreshes_live_external_launch_service() -> None:
    path = str(Path("/tmp/zivo-refresh-editor-config").resolve())
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
    app = create_app(
        snapshot_loader=loader,
        config_path="/tmp/zivo/config.toml",
        initial_path=path,
    )

    async with app.run_test():
        await _wait_for_snapshot_loaded(app, path)

        assert isinstance(app._external_launch_service, LiveExternalLaunchService)
        assert app._external_launch_service.adapter.editor_command_template.command is None

        app._app_state = replace(app.app_state, pending_config_save_request_id=7)
        saved_config = replace(
            app.app_state.config,
            editor=EditorConfig(command="nvim -u NONE"),
        )
        await app.dispatch_actions(
            (
                ConfigSaveCompleted(
                    request_id=7,
                    path="/tmp/zivo/config.toml",
                    config=saved_config,
                ),
            )
        )

        assert isinstance(app._external_launch_service, LiveExternalLaunchService)
        assert (
            app._external_launch_service.adapter.editor_command_template.command == "nvim -u NONE"
        )

@pytest.mark.asyncio
async def test_app_command_palette_toggles_hidden_files() -> None:
    path = str(Path("/tmp/zivo-command-palette-hidden").resolve())
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
    path = str(Path("/tmp/zivo-open-file").resolve())
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
async def test_app_right_on_file_does_not_launch_default_app() -> None:
    path = str(Path("/tmp/zivo-right-file").resolve())
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
        await pilot.press("right")
        await asyncio.sleep(0.05)

        assert launch_service.executed_requests == []
        assert app.app_state.current_path == path
        assert app.app_state.current_pane.cursor_path == f"{path}/README.md"
        assert app.app_state.ui_mode == "BROWSING"

@pytest.mark.asyncio
async def test_app_command_palette_copy_path_copies_cursor_target() -> None:
    path = str(Path("/tmp/zivo-copy-path").resolve())
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
        await pilot.press("c", "o", "p", "y")
        await pilot.press("enter")
        await asyncio.sleep(0.05)

        assert len(launch_service.executed_requests) == 1
        request = launch_service.executed_requests[0]
        assert request.kind == "copy_paths"
        assert request.paths == (f"{path}/docs",)

        status_bar = await _wait_for_status_bar(app)
        assert "info: Copied 1 path to system clipboard" in str(status_bar.renderable)

@pytest.mark.asyncio
async def test_app_command_palette_opens_current_directory_with_terminal() -> None:
    path = str(Path("/tmp/zivo-open-terminal").resolve())
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
        await pilot.press(
            "c", "u", "r", "r", "e", "n", "t", " ", "d", "i", "r", "e", "c",
            "t", "o", "r", "y", " ", "w", "i", "t", "h", " ", "t", "e", "r",
            "m", "i", "n", "a", "l",
        )
        await pilot.press("enter")
        await _wait_for_external_launch_count(app, 1)

        assert launch_service.executed_requests == [
            ExternalLaunchRequest(
                kind="open_terminal",
                path=path,
                terminal_launch_mode="window",
            )
        ]
        assert app.app_state.ui_mode == "BROWSING"




    path = str(Path("/tmp/zivo-open-file-manager").resolve())
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
        await pilot.press("m", "a", "n", "a", "g", "e", "r")
        await pilot.press("enter")
        await _wait_for_external_launch_count(app, 1)

        assert launch_service.executed_requests == [
            ExternalLaunchRequest(kind="open_file", path=path)
        ]
        assert app.app_state.ui_mode == "BROWSING"

@pytest.mark.asyncio
async def test_app_command_palette_runs_shell_command_and_shows_result() -> None:
    path = str(Path("/tmp/zivo-shell-command").resolve())
    shell_command_service = FakeShellCommandService(
        results={
            (path, "pwd"): ShellCommandResult(exit_code=0, stdout=f"{path}\n"),
        }
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
        shell_command_service=shell_command_service,
        initial_path=path,
    )

    async with app.run_test() as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await pilot.press(":")
        await pilot.press("s", "h", "e", "l", "l", "enter")
        await asyncio.sleep(0.05)

        dialog = await _wait_for_shell_command_dialog(app)
        title = dialog.query_one("#shell-command-dialog-title", Static)

        assert app.app_state.ui_mode == "SHELL"
        assert title.renderable == "Run Shell Command"
        guidance = dialog.query_one("#shell-command-dialog-guidance", Static)
        assert guidance.renderable == "Runs in the background; use t for interactive commands."

        await pilot.press("p", "w", "d", "enter")
        # 結果が表示されるまで待機
        await asyncio.sleep(0.1)

        assert shell_command_service.executed_commands == [(path, "pwd")]
        # UIモードがSHELLのままであること
        assert app.app_state.ui_mode == "SHELL"
        # 結果がShellCommandStateに保持されていること
        assert app.app_state.shell_command is not None
        assert app.app_state.shell_command.result is not None
        assert app.app_state.shell_command.result.exit_code == 0
        assert app.app_state.shell_command.result.stdout == f"{path}\n"
        # ダイアログが開いたままであること
        assert dialog.display is True
        # タイトルが結果表示モードになっていること
        assert title.renderable == "Shell Command Result"

        await pilot.press("r")
        await asyncio.sleep(0.1)
        assert shell_command_service.executed_commands == [(path, "pwd"), (path, "pwd")]

        # ESCキーでダイアログを閉じる
        await pilot.press("escape")
        await asyncio.sleep(0.05)
        assert app.app_state.ui_mode == "BROWSING"
        assert dialog.display is False

@pytest.mark.asyncio
async def test_app_pressing_bang_opens_shell_command_dialog() -> None:
    path = str(Path("/tmp/zivo-shell-command-keybinding").resolve())
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
        await pilot.press("!")
        await asyncio.sleep(0.05)

        dialog = await _wait_for_shell_command_dialog(app)

        assert app.app_state.ui_mode == "SHELL"
        assert dialog.display is True

        await pilot.press("escape")
        await asyncio.sleep(0.05)

        assert app.app_state.ui_mode == "BROWSING"

@pytest.mark.asyncio
async def test_app_shell_command_dialog_overlay_is_centered_without_resizing_main_pane() -> None:
    path = str(Path("/tmp/zivo-shell-dialog-overlay").resolve())
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

    async with app.run_test(size=(80, 24)) as pilot:
        await _wait_for_snapshot_loaded(app, path)
        current_pane = app.query_one("#current-pane")
        main_pane_width = current_pane.region.width

        await pilot.press("!")
        await asyncio.sleep(0.05)

        dialog = await _wait_for_shell_command_dialog(app)
        dialog_layer = app.query_one("#shell-command-dialog-layer")

        _assert_region_vertically_centered(dialog.region, dialog_layer.region)
        assert dialog.region.bottom <= dialog_layer.region.bottom
        assert current_pane.region.width == main_pane_width

@pytest.mark.asyncio
async def test_app_pressing_e_launches_editor_for_file() -> None:
    path = str(Path("/tmp/zivo-open-editor").resolve())
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
    path = str(Path("/tmp/zivo-open-editor-refresh").resolve())
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
    path = str(Path("/tmp/zivo-open-failure").resolve())
    request = ExternalLaunchRequest(kind="open_file", path=f"{path}/README.md")
    launch_service = FakeExternalLaunchService(
        failure_messages={request: "Failed to open /tmp/zivo-open-failure/README.md: denied"}
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
        assert "error: Failed to open /tmp/zivo-open-failure/README.md: denied" in str(
            status_bar.renderable
        )

@pytest.mark.asyncio
async def test_app_sort_shortcuts_keep_side_panes_fixed_and_update_status_bar() -> None:
    path = str(Path("/tmp/zivo-sort-shortcuts").resolve())
    parent_path = "/tmp"
    child_path = f"{path}/zeta"
    snapshot = BrowserSnapshot(
        current_path=path,
        parent_pane=PaneState(
            directory_path=parent_path,
            entries=(
                DirectoryEntryState(f"{parent_path}/beta.txt", "beta.txt", "file"),
                DirectoryEntryState(f"{parent_path}/alpha", "alpha", "dir"),
                DirectoryEntryState(path, "zivo-sort-shortcuts", "dir"),
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
    app = create_app(
        snapshot_loader=loader,
        initial_path=path,
        app_config=AppConfig(
            display=DisplayConfig(directories_first=False),
        ),
    )

    async with app.run_test(size=(240, 24)) as pilot:
        await _wait_for_snapshot_loaded(app, path)
        await _wait_for_row_count(app, 3)

        await pilot.press("s")
        await asyncio.sleep(0.05)

        parent_list = app.query_one("#parent-pane-list", Static)
        child_list = app.query_one("#child-pane-list", Static)
        summary_bar = await _wait_for_summary_bar(app)

        assert app.app_state.sort.field == "name"
        assert app.app_state.sort.descending is True
        assert app.app_state.sort.directories_first is False
        assert _side_pane_lines(parent_list) == [
            "alpha",
            "zivo-sort-shortcuts",
            "beta.txt",
        ]
        assert _side_pane_lines(child_list) == [
            "archive",
            "notes.txt",
        ]
        assert str(summary_bar.renderable) == ("3 items | 0 selected | sort: name desc")

@pytest.mark.asyncio
async def test_app_filter_mode_accepts_printable_bound_keys() -> None:
    path = str(Path("/tmp/zivo-filter-keys").resolve())
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
        current_table = app.query_one("#current-pane-table", DataTable)

        assert app.app_state.ui_mode == "FILTER"
        assert app.app_state.filter.query == "yxp"
        assert current_table.show_cursor is False
        assert str(input_bar.renderable) == "[FILTER] Filter: yxp_  enter/down apply | esc clear"

@pytest.mark.asyncio
async def test_app_action_dispatch_bound_key_uses_dispatcher_character_rules() -> None:
    path = str(Path("/tmp/zivo-palette-bound-space").resolve())
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
        await app.action_dispatch_bound_key("space")
        await app.action_dispatch_bound_key("y")
        await asyncio.sleep(0.05)

        palette = await _wait_for_command_palette(app)

        assert app.app_state.ui_mode == "PALETTE"
        assert app.app_state.command_palette is not None
        assert app.app_state.command_palette.query == " y"
        assert palette.display is True

@pytest.mark.asyncio
async def test_app_confirmed_filter_stays_visible_in_current_pane() -> None:
    path = str(Path("/tmp/zivo-filter-confirm").resolve())
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
        assert str(input_bar.renderable) == "[FILTER] Filter: docs_  esc clear"

@pytest.mark.asyncio
async def test_app_filter_down_confirms_and_returns_to_browsing() -> None:
    path = str(Path("/tmp/zivo-filter-down").resolve())
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
        assert str(input_bar.renderable) == "[FILTER] Filter: docs_  esc clear"
