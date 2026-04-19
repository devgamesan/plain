from dataclasses import replace
from pathlib import Path

from tests.state_test_helpers import reduce_state
from zivo.models import (
    AppConfig,
    BookmarkConfig,
    ExternalLaunchRequest,
)
from zivo.state import (
    AttributeInspectionState,
    BeginBookmarkSearch,
    BeginCommandPalette,
    BeginGoToPath,
    BeginHistorySearch,
    CancelCommandPalette,
    CommandPaletteState,
    ConfigEditorState,
    DirectoryEntryState,
    DismissAttributeDialog,
    HistoryState,
    LoadBrowserSnapshotEffect,
    MoveCommandPaletteCursor,
    NotificationState,
    PaneState,
    PendingInputState,
    PendingKeySequenceState,
    RunConfigSaveEffect,
    RunExternalLaunchEffect,
    SetCommandPaletteQuery,
    SetCursorPath,
    ShowAttributes,
    StartSplitTerminalEffect,
    SubmitCommandPalette,
    build_initial_app_state,
    reduce_app_state,
)


def _reduce_state(state, action):
    return reduce_state(state, action)


def _viewport_test_entries(
    path: str,
    count: int,
    *,
    hidden_indexes: frozenset[int] = frozenset(),
) -> tuple[DirectoryEntryState, ...]:
    return tuple(
        DirectoryEntryState(
            f"{path}/item_{index:02d}",
            f"item_{index:02d}",
            "file",
            hidden=index in hidden_indexes,
        )
        for index in range(count)
    )


def test_begin_command_palette_sets_mode_and_empty_query() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(state, BeginCommandPalette())

    assert next_state.ui_mode == "PALETTE"
    assert next_state.command_palette is not None
    assert next_state.command_palette.query == ""
    assert next_state.command_palette.cursor_index == 0

def test_begin_command_palette_keeps_current_cursor_path() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        SetCursorPath("/home/tadashi/develop/zivo/tests"),
    )

    next_state = _reduce_state(state, BeginCommandPalette())

    assert next_state.current_pane.cursor_path == "/home/tadashi/develop/zivo/tests"

def test_move_command_palette_cursor_clamps_to_visible_commands() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())

    next_state = _reduce_state(state, MoveCommandPaletteCursor(delta=20))

    assert next_state.command_palette is not None
    assert next_state.command_palette.cursor_index == 20

def test_set_command_palette_query_resets_cursor() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, MoveCommandPaletteCursor(delta=3))

    next_state = _reduce_state(state, SetCommandPaletteQuery("dir"))

    assert next_state.command_palette is not None
    assert next_state.command_palette.query == "dir"
    assert next_state.command_palette.cursor_index == 0

def test_submit_command_palette_runs_create_file_flow() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("create file"))

    next_state = _reduce_state(state, SubmitCommandPalette())

    assert next_state.ui_mode == "CREATE"
    assert next_state.command_palette is None
    assert next_state.pending_input == PendingInputState(
        prompt="New file: ",
        value="",
        create_kind="file",
    )

def test_submit_command_palette_begins_extract_archive_flow() -> None:
    archive_path = "/home/tadashi/develop/zivo/archive.zip"
    state = replace(
        build_initial_app_state(),
        current_pane=replace(
            build_initial_app_state().current_pane,
            entries=(
                DirectoryEntryState(archive_path, "archive.zip", "file"),
                *build_initial_app_state().current_pane.entries[1:],
            ),
            cursor_path=archive_path,
        ),
    )
    state = _reduce_state(state, BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("extract"))

    next_state = _reduce_state(state, SubmitCommandPalette())

    assert next_state.ui_mode == "EXTRACT"
    assert next_state.pending_input is not None
    expected_dest = str(Path("/home/tadashi/develop/zivo/archive").resolve())
    assert next_state.pending_input.value == expected_dest
    assert next_state.pending_input.extract_source_path == archive_path

def test_submit_command_palette_begins_zip_compress_flow() -> None:
    state = replace(
        build_initial_app_state(),
        current_pane=replace(
            build_initial_app_state().current_pane,
            selected_paths=frozenset(
                {
                    "/home/tadashi/develop/zivo/docs",
                    "/home/tadashi/develop/zivo/src",
                }
            ),
        ),
    )
    state = _reduce_state(state, BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("compress"))

    next_state = _reduce_state(state, SubmitCommandPalette())

    assert next_state.ui_mode == "ZIP"
    assert next_state.pending_input is not None
    expected_zip = str(Path("/home/tadashi/develop/zivo/zivo.zip").resolve())
    assert next_state.pending_input.value == expected_zip
    assert next_state.pending_input.zip_source_paths == (
        "/home/tadashi/develop/zivo/docs",
        "/home/tadashi/develop/zivo/src",
    )

def test_begin_history_search_enters_history_mode() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        history=HistoryState(
            back=("/tmp/a", "/tmp/b"),
            forward=("/tmp/c",),
            visited_all=("/home/tadashi/develop/zivo", "/tmp/a", "/tmp/b", "/tmp/c"),
        ),
    )
    next_state = _reduce_state(state, BeginHistorySearch())

    assert next_state.ui_mode == "PALETTE"
    assert next_state.command_palette is not None
    assert next_state.command_palette.source == "history"
    assert next_state.command_palette.history_results == (
        "/home/tadashi/develop/zivo",
        "/tmp/a",
        "/tmp/b",
        "/tmp/c",
    )

def test_begin_history_search_with_empty_history() -> None:
    next_state = _reduce_state(build_initial_app_state(), BeginHistorySearch())

    assert next_state.ui_mode == "PALETTE"
    assert next_state.command_palette is not None
    assert next_state.command_palette.source == "history"
    assert next_state.command_palette.history_results == ()

def test_begin_bookmark_search_enters_bookmarks_mode() -> None:
    next_state = _reduce_state(build_initial_app_state(), BeginBookmarkSearch())

    assert next_state.ui_mode == "PALETTE"
    assert next_state.command_palette == CommandPaletteState(source="bookmarks")

def test_begin_go_to_path_enters_palette_mode() -> None:
    next_state = _reduce_state(build_initial_app_state(), BeginGoToPath())

    assert next_state.ui_mode == "PALETTE"
    assert next_state.command_palette == CommandPaletteState(source="go_to_path")

def test_submit_history_palette_navigates_to_selected_directory() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="history",
            history_results=("/tmp/a", "/tmp/b", "/tmp/c"),
            cursor_index=1,
        ),
    )

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.command_palette is None
    assert any(
        isinstance(e, LoadBrowserSnapshotEffect) and e.path == "/tmp/b"
        for e in result.effects
    )

def test_submit_history_palette_with_empty_history_shows_warning() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="history",
            history_results=(),
        ),
    )

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.notification is not None
    assert result.state.notification.message == "No directory history"

def test_submit_bookmarks_palette_navigates_to_selected_directory(tmp_path) -> None:
    bookmarked_path = tmp_path / "project"
    bookmarked_path.mkdir()
    state = build_initial_app_state(
        config=AppConfig(bookmarks=BookmarkConfig(paths=(str(bookmarked_path),)))
    )
    state = replace(
        state,
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(source="bookmarks"),
    )

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.command_palette is None
    assert result.effects == (
        LoadBrowserSnapshotEffect(
            request_id=1,
            path=str(bookmarked_path),
            cursor_path=None,
            blocking=True,
        ),
    )

def test_submit_bookmarks_palette_with_invalid_path_shows_error() -> None:
    state = build_initial_app_state(
        config=AppConfig(bookmarks=BookmarkConfig(paths=("/tmp/does-not-exist",)))
    )
    state = replace(
        state,
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(source="bookmarks"),
    )

    next_state = _reduce_state(state, SubmitCommandPalette())

    assert next_state.notification == NotificationState(
        level="error",
        message="Bookmarked path does not exist or is not a directory",
    )

def test_set_command_palette_query_updates_go_to_path_candidates(tmp_path) -> None:
    state = _reduce_state(
        replace(build_initial_app_state(), current_path=str(tmp_path)),
        BeginGoToPath(),
    )
    (tmp_path / "docs").mkdir()
    (tmp_path / "downloads").mkdir()

    next_state = _reduce_state(
        state,
        SetCommandPaletteQuery("do"),
    )

    assert next_state.command_palette is not None
    assert next_state.command_palette.go_to_path_candidates == (
        str(tmp_path / "docs"),
        str(tmp_path / "downloads"),
    )

def test_set_command_palette_query_resolves_relative_go_to_path_candidates(tmp_path) -> None:
    state = _reduce_state(
        replace(build_initial_app_state(), current_path=str(tmp_path)),
        BeginGoToPath(),
    )
    (tmp_path / "projects").mkdir()
    (tmp_path / "projects" / "zivo").mkdir()

    next_state = _reduce_state(state, SetCommandPaletteQuery("projects/z"))

    assert next_state.command_palette is not None
    assert next_state.command_palette.go_to_path_candidates == (
        str(tmp_path / "projects" / "zivo"),
    )

def test_submit_go_to_path_palette_requests_snapshot(tmp_path) -> None:
    state = _reduce_state(
        replace(build_initial_app_state(), current_path=str(tmp_path)),
        BeginGoToPath(),
    )
    target_path = tmp_path / "docs"
    target_path.mkdir()
    state = _reduce_state(
        state,
        SetCommandPaletteQuery("do"),
    )

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.ui_mode == "BUSY"
    assert result.state.command_palette is None
    assert result.effects == (
        LoadBrowserSnapshotEffect(
            request_id=1,
            path=str(target_path),
            cursor_path=None,
            blocking=True,
        ),
    )

def test_submit_go_to_path_palette_uses_selected_candidate(tmp_path) -> None:
    state = _reduce_state(
        replace(build_initial_app_state(), current_path=str(tmp_path)),
        BeginGoToPath(),
    )
    (tmp_path / "alpha").mkdir()
    (tmp_path / "beta").mkdir()
    state = _reduce_state(state, SetCommandPaletteQuery(""))
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            query=str(tmp_path),
            go_to_path_candidates=(str(tmp_path / "alpha"), str(tmp_path / "beta")),
            cursor_index=1,
        ),
    )

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.effects == (
        LoadBrowserSnapshotEffect(
            request_id=1,
            path=str(tmp_path / "beta"),
            cursor_path=None,
            blocking=True,
        ),
    )

def test_submit_go_to_path_palette_with_trailing_separator_uses_query_directory(tmp_path) -> None:
    state = _reduce_state(
        replace(build_initial_app_state(), current_path=str(tmp_path)),
        BeginGoToPath(),
    )
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "api").mkdir()
    state = _reduce_state(state, SetCommandPaletteQuery("docs/"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.effects == (
        LoadBrowserSnapshotEffect(
            request_id=1,
            path=str(tmp_path / "docs"),
            cursor_path=None,
            blocking=True,
        ),
    )

def test_submit_go_to_path_palette_with_invalid_directory_shows_error() -> None:
    state = _reduce_state(build_initial_app_state(), BeginGoToPath())
    state = _reduce_state(
        state,
        SetCommandPaletteQuery("/path/that/does/not/exist"),
    )

    next_state = _reduce_state(state, SubmitCommandPalette())

    assert next_state.ui_mode == "PALETTE"
    assert next_state.notification == NotificationState(
        level="error",
        message="Path does not exist or is not a directory",
    )
    state = _reduce_state(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        BeginCommandPalette(),
    )
    state = _reduce_state(state, SetCommandPaletteQuery("config"))

    next_state = _reduce_state(state, SubmitCommandPalette())

    assert next_state.ui_mode == "CONFIG"
    assert next_state.command_palette is None
    assert next_state.config_editor == ConfigEditorState(
        path="/tmp/zivo/config.toml",
        draft=next_state.config,
    )

def test_submit_command_palette_runs_copy_path_flow() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("copy"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.ui_mode == "BROWSING"
    assert result.state.command_palette is None
    assert result.state.next_request_id == 2
    assert result.effects == (
        RunExternalLaunchEffect(
            request_id=1,
            request=ExternalLaunchRequest(
                kind="copy_paths",
                paths=("/home/tadashi/develop/zivo/docs",),
            ),
        ),
    )

def test_submit_command_palette_opens_attribute_dialog_for_single_target() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("attr"))

    next_state = _reduce_state(state, SubmitCommandPalette())

    assert next_state.ui_mode == "DETAIL"
    assert next_state.command_palette is None
    assert next_state.attribute_inspection is not None
    assert next_state.attribute_inspection.name == "docs"
    assert next_state.attribute_inspection.kind == "dir"
    assert next_state.attribute_inspection.path == "/home/tadashi/develop/zivo/docs"
    assert next_state.attribute_inspection.permissions_mode is None

def test_dismiss_attribute_dialog_returns_to_browsing() -> None:
    initial_state = build_initial_app_state()
    state = replace(
        initial_state,
        ui_mode="DETAIL",
        attribute_inspection=AttributeInspectionState(
            name="docs",
            kind="dir",
            path="/home/tadashi/develop/zivo/docs",
        ),
    )

    next_state = _reduce_state(state, DismissAttributeDialog())

    assert next_state.ui_mode == "BROWSING"
    assert next_state.attribute_inspection is None

def test_submit_command_palette_opens_current_directory_in_file_manager() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("manager"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.ui_mode == "BROWSING"
    assert result.state.command_palette is None
    assert result.state.next_request_id == 2
    assert result.effects == (
        RunExternalLaunchEffect(
            request_id=1,
            request=ExternalLaunchRequest(
                kind="open_file",
                path="/home/tadashi/develop/zivo",
            ),
        ),
    )

def test_submit_command_palette_warns_when_query_has_no_match() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("zzz"))

    next_state = _reduce_state(state, SubmitCommandPalette())

    assert next_state.ui_mode == "PALETTE"
    assert next_state.notification == NotificationState(
        level="warning",
        message="No matching command",
    )

def test_submit_command_palette_toggles_hidden_files() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("hidden"))

    next_state = _reduce_state(state, SubmitCommandPalette())

    assert next_state.ui_mode == "BROWSING"
    assert next_state.command_palette is None
    assert next_state.show_hidden is True
    assert next_state.notification == NotificationState(
        level="info",
        message="Hidden files shown",
    )

def test_submit_command_palette_runs_open_terminal_flow() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("open terminal"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.ui_mode == "BROWSING"
    assert result.state.command_palette is None
    assert result.state.next_request_id == 2
    assert result.effects == (
        RunExternalLaunchEffect(
            request_id=1,
            request=ExternalLaunchRequest(
                kind="open_terminal",
                path="/home/tadashi/develop/zivo",
            ),
        ),
    )

def test_submit_command_palette_begins_history_search() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("history search"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.ui_mode == "PALETTE"
    assert result.state.command_palette is not None
    assert result.state.command_palette.source == "history"

def test_submit_command_palette_begins_bookmark_search() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("show bookmarks"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.ui_mode == "PALETTE"
    assert result.state.command_palette is not None
    assert result.state.command_palette.source == "bookmarks"

def test_submit_command_palette_adds_current_directory_bookmark() -> None:
    state = _reduce_state(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        BeginCommandPalette(),
    )
    state = _reduce_state(state, SetCommandPaletteQuery("bookmark this directory"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.command_palette is None
    assert result.effects == (
        RunConfigSaveEffect(
            request_id=1,
            path="/tmp/zivo/config.toml",
            config=AppConfig(
                bookmarks=BookmarkConfig(paths=("/home/tadashi/develop/zivo",))
            ),
        ),
    )

def test_show_attributes_enters_detail_mode_for_single_target() -> None:
    state = build_initial_app_state()

    result = reduce_app_state(state, ShowAttributes())

    assert result.state.ui_mode == "DETAIL"
    assert result.state.attribute_inspection == AttributeInspectionState(
        name="docs",
        kind="dir",
        path="/home/tadashi/develop/zivo/docs",
        size_bytes=None,
        modified_at=state.current_pane.entries[0].modified_at,
        hidden=False,
        permissions_mode=state.current_pane.entries[0].permissions_mode,
    )

def test_show_attributes_warns_without_single_target() -> None:
    state = replace(
        build_initial_app_state(),
        current_pane=replace(
            build_initial_app_state().current_pane,
            selected_paths=frozenset(
                {
                    "/home/tadashi/develop/zivo/docs",
                    "/home/tadashi/develop/zivo/src",
                }
            ),
        ),
    )

    next_state = _reduce_state(state, ShowAttributes())

    assert next_state.notification == NotificationState(
        level="warning",
        message="Show attributes requires a single target",
    )

def test_submit_command_palette_removes_current_directory_bookmark() -> None:
    state = _reduce_state(
        build_initial_app_state(
            config_path="/tmp/zivo/config.toml",
            config=AppConfig(
                bookmarks=BookmarkConfig(paths=("/home/tadashi/develop/zivo", "/home/tadashi/src"))
            ),
        ),
        BeginCommandPalette(),
    )
    state = _reduce_state(state, SetCommandPaletteQuery("remove bookmark"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.command_palette is None
    assert result.effects == (
        RunConfigSaveEffect(
            request_id=1,
            path="/tmp/zivo/config.toml",
            config=AppConfig(
                bookmarks=BookmarkConfig(paths=("/home/tadashi/src",))
            ),
        ),
    )

def test_submit_command_palette_goes_back() -> None:
    state = replace(
        _reduce_state(build_initial_app_state(), BeginCommandPalette()),
        history=HistoryState(
            back=("/home/tadashi/downloads",),
            forward=(),
        ),
    )
    state = _reduce_state(state, SetCommandPaletteQuery("go back"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.ui_mode == "BUSY"
    assert result.state.command_palette is None
    assert len(result.effects) == 1
    assert isinstance(result.effects[0], LoadBrowserSnapshotEffect)
    assert result.effects[0].path == "/home/tadashi/downloads"

def test_submit_command_palette_go_forward_is_unavailable_without_history() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("go forward"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.ui_mode == "PALETTE"
    assert result.state.command_palette is not None
    assert result.state.notification == NotificationState(
        level="warning",
        message="Go forward is not available yet",
    )

def test_submit_command_palette_reloads_directory() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("reload directory"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.command_palette is None
    assert len(result.effects) == 1
    assert isinstance(result.effects[0], LoadBrowserSnapshotEffect)

def test_submit_command_palette_goes_to_home_directory() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("go to home directory"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.ui_mode == "BUSY"
    assert result.state.command_palette is None
    assert len(result.effects) == 1
    assert isinstance(result.effects[0], LoadBrowserSnapshotEffect)

def test_submit_command_palette_toggles_split_terminal() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("split terminal"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.ui_mode == "BROWSING"
    assert result.state.command_palette is None
    assert result.state.split_terminal.visible is True
    assert len(result.effects) == 1
    assert isinstance(result.effects[0], StartSplitTerminalEffect)

def test_submit_command_palette_begins_rename_with_single_target() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("rename"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.ui_mode == "RENAME"
    assert result.state.command_palette is None
    assert result.state.pending_input is not None
    assert result.state.pending_input.prompt == "Rename: "

def test_submit_command_palette_deletes_targets() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("trash"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.ui_mode == "CONFIRM"
    assert result.state.command_palette is None
    assert result.state.delete_confirmation is not None

def test_submit_command_palette_uses_selected_paths_for_copy_path() -> None:
    initial_state = build_initial_app_state()
    state = replace(
        initial_state,
        current_pane=replace(
            initial_state.current_pane,
            selected_paths=frozenset(
                {
                    "/home/tadashi/develop/zivo/docs",
                    "/home/tadashi/develop/zivo/src",
                }
            ),
        ),
    )
    state = _reduce_state(state, BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("copy"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.effects == (
        RunExternalLaunchEffect(
            request_id=1,
            request=ExternalLaunchRequest(
                kind="copy_paths",
                paths=(
                    "/home/tadashi/develop/zivo/docs",
                    "/home/tadashi/develop/zivo/src",
                ),
            ),
        ),
    )

def test_submit_command_palette_select_all_uses_visible_entries() -> None:
    initial_state = build_initial_app_state()
    state = replace(
        initial_state,
        current_pane=PaneState(
            directory_path="/home/tadashi/develop/zivo",
            entries=(
                DirectoryEntryState(
                    "/home/tadashi/develop/zivo/.env",
                    ".env",
                    "file",
                    hidden=True,
                ),
                DirectoryEntryState("/home/tadashi/develop/zivo/docs", "docs", "dir"),
                DirectoryEntryState("/home/tadashi/develop/zivo/src", "src", "dir"),
            ),
            cursor_path="/home/tadashi/develop/zivo/docs",
        ),
        filter=replace(initial_state.filter, query="s", active=True),
    )
    state = _reduce_state(state, BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("select all"))

    next_state = _reduce_state(state, SubmitCommandPalette())

    assert next_state.current_pane.selected_paths == frozenset(
        {
            "/home/tadashi/develop/zivo/docs",
            "/home/tadashi/develop/zivo/src",
        }
    )

def test_cancel_command_palette_returns_to_browsing() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())

    next_state = _reduce_state(state, CancelCommandPalette())

    assert next_state.ui_mode == "BROWSING"
    assert next_state.command_palette is None

def test_begin_command_palette_clears_pending_key_sequence() -> None:
    state = replace(
        build_initial_app_state(),
        pending_key_sequence=PendingKeySequenceState(
            keys=("y",),
            possible_next_keys=("y",),
        ),
    )

    next_state = _reduce_state(state, BeginCommandPalette())

    assert next_state.ui_mode == "PALETTE"
    assert next_state.pending_key_sequence is None

