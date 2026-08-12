from dataclasses import replace
from pathlib import Path

import zivo.state.command_palette as command_palette_module
from tests.state_test_helpers import reduce_state
from zivo.models import (
    ActionsConfig,
    AppConfig,
    BookmarkConfig,
    CustomActionConfig,
    ExternalLaunchRequest,
)
from zivo.state import (
    AttributeInspectionState,
    CommandPaletteState,
    ConfigEditorState,
    DirectoryEntryState,
    HistoryState,
    LoadBrowserSnapshotEffect,
    LoadTransferPaneEffect,
    NotificationState,
    PaneState,
    PendingInputState,
    PendingKeySequenceState,
    RunAttributeInspectionEffect,
    RunConfigSaveEffect,
    RunCustomActionEffect,
    RunDuplicateEffect,
    RunExternalLaunchEffect,
    TransferPaneState,
    build_initial_app_state,
    reduce_app_state,
    select_command_palette_state,
)
from zivo.state.actions import (
    AttributeInspectionLoaded,
    BeginBookmarkSearch,
    BeginCommandPalette,
    BeginGo,
    BrowserSnapshotFailed,
    CancelCommandPalette,
    ConfirmCustomAction,
    DismissAttributeDialog,
    MoveCommandPaletteCursor,
    OpenNewTab,
    SetCommandPaletteQuery,
    SetCursorPath,
    ShowAttributes,
    SubmitCommandPalette,
    ToggleTransferMode,
)
from zivo.state.command_palette import parse_go_query, select_go_candidates


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


def test_submit_command_palette_toggles_narrow_details_view() -> None:
    state = _reduce_state(
        replace(build_initial_app_state(), terminal_width=72),
        BeginCommandPalette(),
    )
    assert state.command_palette is not None
    items = command_palette_module.get_command_palette_items(state)
    item_index = next(
        index for index, item in enumerate(items) if item.id == "toggle_narrow_pane_view"
    )
    state = replace(state, command_palette=replace(state.command_palette, cursor_index=item_index))

    next_state = _reduce_state(state, SubmitCommandPalette())

    assert next_state.ui_mode == "BROWSING"
    assert next_state.command_palette is None
    assert next_state.narrow_pane_view == "details"

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

def test_submit_command_palette_runs_unified_create_flow() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("create"))

    next_state = _reduce_state(state, SubmitCommandPalette())

    assert next_state.ui_mode == "CREATE"
    assert next_state.command_palette is None
    assert next_state.pending_input == PendingInputState(
        prompt="Name or path: ",
        value="",
        create_kind="file",
    )


def test_submit_duplicate_command_starts_duplicate_effect() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("duplicate"))

    result = reduce_app_state(state, SubmitCommandPalette())
    next_state = result.state

    assert next_state.ui_mode == "BUSY"
    assert next_state.command_palette is None
    assert next_state.pending_duplicate_request_id == 1
    assert isinstance(result.effects[0], RunDuplicateEffect)


def test_custom_action_single_file_appears_in_command_palette() -> None:
    file_path = "/home/tadashi/develop/zivo/image.png"
    state = replace(
        build_initial_app_state(
            config=AppConfig(
                actions=ActionsConfig(
                    custom=(
                        CustomActionConfig(
                            name="Optimize PNG",
                            command=("oxipng", "{file}"),
                            when="single_file",
                            extensions=("png",),
                        ),
                    )
                )
            )
        ),
        current_pane=replace(
            build_initial_app_state().current_pane,
            entries=(DirectoryEntryState(file_path, "image.png", "file"),),
            cursor_path=file_path,
        ),
    )
    state = _reduce_state(state, BeginCommandPalette())

    items = command_palette_module.get_command_palette_items(state)

    assert any(item.id == "custom_action:0" and item.label == "Optimize PNG" for item in items)


def test_submit_custom_action_enters_confirmation_with_expanded_command() -> None:
    file_path = "/home/tadashi/develop/zivo/image.png"
    state = replace(
        build_initial_app_state(
            config=AppConfig(
                actions=ActionsConfig(
                    custom=(
                        CustomActionConfig(
                            name="Optimize PNG",
                            command=("oxipng", "-o", "4", "{file}"),
                            when="single_file",
                            cwd="{cwd}",
                            extensions=("png",),
                        ),
                    )
                )
            )
        ),
        current_pane=replace(
            build_initial_app_state().current_pane,
            entries=(DirectoryEntryState(file_path, "image.png", "file"),),
            cursor_path=file_path,
        ),
    )
    state = _reduce_state(state, BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("Optimize"))

    next_state = _reduce_state(state, SubmitCommandPalette())

    assert next_state.ui_mode == "CONFIRM"
    assert next_state.custom_action_confirmation is not None
    assert next_state.custom_action_confirmation.request.name == "Optimize PNG"
    assert next_state.custom_action_confirmation.request.command == (
        "oxipng",
        "-o",
        "4",
        file_path,
    )
    assert next_state.custom_action_confirmation.request.mode == "background"


def test_confirm_custom_action_emits_run_effect() -> None:
    file_path = "/home/tadashi/develop/zivo/image.png"
    state = replace(
        build_initial_app_state(
            config=AppConfig(
                actions=ActionsConfig(
                    custom=(
                        CustomActionConfig(
                            name="Optimize PNG",
                            command=("oxipng", "{file}"),
                            when="single_file",
                        ),
                    )
                )
            )
        ),
        current_pane=replace(
            build_initial_app_state().current_pane,
            entries=(DirectoryEntryState(file_path, "image.png", "file"),),
            cursor_path=file_path,
        ),
    )
    state = _reduce_state(state, BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("Optimize"))
    state = _reduce_state(state, SubmitCommandPalette())

    result = reduce_app_state(state, ConfirmCustomAction())

    assert result.state.pending_custom_action_request_id == 1
    assert any(
        isinstance(effect, RunCustomActionEffect)
        and effect.request.command == ("oxipng", file_path)
        for effect in result.effects
    )


def test_submit_command_palette_runs_create_symlink_flow() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("symlink"))

    next_state = _reduce_state(state, SubmitCommandPalette())

    assert next_state.ui_mode == "SYMLINK"
    assert next_state.command_palette is None
    assert next_state.pending_input is not None
    assert next_state.pending_input.prompt == "Create link at: "
    assert next_state.pending_input.symlink_source_path == "/home/tadashi/develop/zivo/docs"
    assert next_state.pending_input.value.endswith(("/docs.link", "\\docs.link"))

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

def test_begin_bookmark_search_enters_bookmarks_filtered_go_mode() -> None:
    next_state = _reduce_state(build_initial_app_state(), BeginBookmarkSearch())

    assert next_state.ui_mode == "PALETTE"
    assert next_state.command_palette is not None
    assert next_state.command_palette.source == "go"
    assert next_state.command_palette.history_and_navigation.go_source_filter == "bookmarks"

def test_submit_command_palette_opens_new_tab_in_transfer_mode() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        layout_mode="transfer",
        active_transfer_pane="left",
        transfer_left=TransferPaneState(
            pane=PaneState(directory_path="/tmp/a", entries=(), cursor_path="/tmp/a"),
            current_path="/tmp/a",
        ),
        transfer_right=TransferPaneState(
            pane=PaneState(directory_path="/tmp/b", entries=(), cursor_path="/tmp/b"),
            current_path="/tmp/b",
        ),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="commands",
            query="new tab",
            cursor_index=0,
        ),
    )

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.command_palette is None
    assert len(result.state.browser_tabs) == 2
    assert result.state.active_tab_index == 1
    # New tab should preserve transfer mode state
    assert result.state.layout_mode == "transfer"
    assert result.state.transfer_left is not None
    assert result.state.transfer_right is not None


def test_submit_command_palette_closes_current_tab_in_transfer_mode() -> None:
    state = build_initial_app_state()
    # Create a second tab first
    state = reduce_app_state(state, OpenNewTab()).state
    initial_tab_count = len(state.browser_tabs)

    state = replace(
        state,
        layout_mode="transfer",
        active_transfer_pane="left",
        transfer_left=TransferPaneState(
            pane=PaneState(directory_path="/tmp/a", entries=(), cursor_path="/tmp/a"),
            current_path="/tmp/a",
        ),
        transfer_right=TransferPaneState(
            pane=PaneState(directory_path="/tmp/b", entries=(), cursor_path="/tmp/b"),
            current_path="/tmp/b",
        ),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="commands",
            query="close current tab",
            cursor_index=0,
        ),
    )

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.command_palette is None
    assert len(result.state.browser_tabs) == initial_tab_count - 1


def test_submit_command_palette_select_all_in_transfer_mode() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())
    state = _reduce_state(state, BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("select all"))

    next_state = _reduce_state(state, SubmitCommandPalette())

    assert next_state.transfer_left is not None
    assert next_state.transfer_left.pane.selected_paths == frozenset(
        {
            "/home/tadashi/develop/zivo/docs",
            "/home/tadashi/develop/zivo/src",
            "/home/tadashi/develop/zivo/tests",
            "/home/tadashi/develop/zivo/README.md",
            "/home/tadashi/develop/zivo/pyproject.toml",
        }
    )


def test_submit_command_palette_reloads_active_transfer_pane() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())
    state = _reduce_state(state, BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("reload"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.command_palette is None
    assert any(
        isinstance(effect, LoadTransferPaneEffect)
        and effect.pane_id == "left"
        and effect.path == "/home/tadashi/develop/zivo"
        for effect in result.effects
    )


def test_submit_command_palette_begins_rename_in_transfer_mode() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())
    state = _reduce_state(state, BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("rename"))

    next_state = _reduce_state(state, SubmitCommandPalette())

    assert next_state.ui_mode == "RENAME"
    assert next_state.pending_input is not None
    assert next_state.pending_input.value == "docs"


def test_submit_command_palette_begins_chmod_in_transfer_mode() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())
    assert state.transfer_left is not None
    docs_entry = replace(state.transfer_left.pane.entries[0], permissions_mode=0o40755)
    state = replace(
        state,
        transfer_left=replace(
            state.transfer_left,
            pane=replace(
                state.transfer_left.pane,
                entries=(docs_entry, *state.transfer_left.pane.entries[1:]),
            ),
        ),
    )
    state = _reduce_state(state, BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("permissions"))

    next_state = _reduce_state(state, SubmitCommandPalette())

    assert next_state.ui_mode == "CHMOD"
    assert next_state.pending_input is not None
    assert next_state.pending_input.value == "755"
    assert next_state.pending_input.chmod_target_paths == (
        "/home/tadashi/develop/zivo/docs",
    )
    assert next_state.pending_input.chmod_recursive is False


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
    state = _reduce_state(state, SetCommandPaletteQuery("copy path"))

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

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.ui_mode == "DETAIL"
    assert result.state.command_palette is None
    assert result.state.attribute_inspection is not None
    assert result.state.attribute_inspection.name == "docs"
    assert result.state.attribute_inspection.kind == "dir"
    assert result.state.attribute_inspection.path == "/home/tadashi/develop/zivo/docs"
    assert result.state.pending_attribute_inspection_request_id == 1
    assert result.effects == (
        RunAttributeInspectionEffect(
            request_id=1,
            path="/home/tadashi/develop/zivo/docs",
        ),
    )

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
    assert next_state.pending_attribute_inspection_request_id is None

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


def test_submit_command_palette_opens_selected_file_with_default_app() -> None:
    path = "/home/tadashi/develop/zivo/README.md"
    state = _reduce_state(build_initial_app_state(), SetCursorPath(path))
    state = _reduce_state(state, BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("open"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.ui_mode == "BROWSING"
    assert result.effects == (
        RunExternalLaunchEffect(
            request_id=state.next_request_id,
            request=ExternalLaunchRequest(kind="open_file", path=path),
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

def test_submit_command_palette_opens_current_directory_with_terminal() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(
        state, SetCommandPaletteQuery("current directory with terminal")
    )

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
                terminal_launch_mode="window",
            ),
        ),
    )

def test_submit_command_palette_begins_go_search() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("go"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.ui_mode == "PALETTE"
    assert result.state.command_palette is not None
    assert result.state.command_palette.source == "go"

def test_submit_command_palette_does_not_expose_legacy_bookmark_search() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("show bookmarks"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.ui_mode == "PALETTE"
    assert result.state.command_palette is not None
    assert result.state.notification is not None
    assert result.state.notification.level == "warning"


def test_command_palette_exposes_one_unified_go_command() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())

    item_ids = {item.id for item in command_palette_module.get_command_palette_items(state)}

    assert "go" in item_ids
    assert not item_ids.intersection({"history_search", "bookmark_search", "go_to_path"})


def test_unified_go_command_advertises_g_shortcut_in_browser_and_transfer() -> None:
    browser_state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    transfer_state = _reduce_state(
        _reduce_state(build_initial_app_state(), ToggleTransferMode()),
        BeginCommandPalette(),
    )

    for state in (browser_state, transfer_state):
        go_item = next(
            item for item in command_palette_module.get_command_palette_items(state)
            if item.id == "go"
        )
        assert go_item.shortcut == "G"


def test_go_candidates_merge_bookmark_and_recent_sources(tmp_path) -> None:
    bookmarked = tmp_path / "bookmarked"
    recent = tmp_path / "recent"
    bookmarked.mkdir()
    recent.mkdir()
    state = replace(
        build_initial_app_state(
            config=AppConfig(bookmarks=BookmarkConfig(paths=(str(bookmarked),)))
        ),
        history=HistoryState(visited_all=(str(recent), str(bookmarked))),
    )

    candidates = select_go_candidates(state)

    merged = next(candidate for candidate in candidates if candidate.path == str(bookmarked))
    assert merged.sources == ("bookmark", "recent")
    assert next(candidate.path for candidate in candidates if candidate.path == str(recent)) == str(
        recent
    )


def test_go_query_promotes_existing_direct_path(tmp_path) -> None:
    destination = tmp_path / "destination"
    destination.mkdir()
    state = _reduce_state(build_initial_app_state(), BeginGo())
    state = _reduce_state(state, SetCommandPaletteQuery(str(destination)))

    items = command_palette_module.get_command_palette_items(state)

    assert items
    assert items[0].id == "go_direct"
    assert items[0].path == str(destination.resolve())


def test_go_view_announces_source_filters() -> None:
    state = _reduce_state(build_initial_app_state(), BeginGo())

    view = select_command_palette_state(state)

    assert view is not None
    assert view.footer_message is not None
    assert "@bookmark" in view.footer_message
    assert "@history" in view.footer_message


def test_bookmark_go_view_updates_filter_announcement_from_query() -> None:
    state = _reduce_state(build_initial_app_state(), BeginBookmarkSearch())
    state = _reduce_state(state, SetCommandPaletteQuery("@history"))

    view = select_command_palette_state(state)

    assert view is not None
    assert view.title == "Go — Recent"
    assert view.footer_message == "Recent filter active | type to search, Enter go"


def test_bookmark_go_query_activates_open_tab_after_filter_override() -> None:
    from zivo.state.models import browser_tab_from_app_state

    state = build_initial_app_state()
    active_tab = replace(browser_tab_from_app_state(state), current_path="/tmp/current")
    other_tab = replace(browser_tab_from_app_state(state), current_path="/tmp/other")
    state = replace(state, current_path="/tmp/current", browser_tabs=(active_tab, other_tab))
    state = _reduce_state(state, BeginBookmarkSearch())
    state = _reduce_state(state, SetCommandPaletteQuery("@tab"))
    state = _reduce_state(state, MoveCommandPaletteCursor(1))

    result = _reduce_state(state, SubmitCommandPalette())

    assert result.active_tab_index == 1
    assert result.current_path == "/tmp/other"


def test_go_query_supports_source_filters(tmp_path) -> None:
    bookmarked = tmp_path / "bookmarked"
    recent = tmp_path / "recent"
    bookmarked.mkdir()
    recent.mkdir()
    state = replace(
        build_initial_app_state(
            config=AppConfig(bookmarks=BookmarkConfig(paths=(str(bookmarked),)))
        ),
        history=HistoryState(visited_all=(str(recent),)),
    )

    assert parse_go_query("@history") == ("recent", "")
    assert parse_go_query("@bookmark book") == ("bookmarks", "book")
    recent_candidates = select_go_candidates(state, query="@history")
    bookmark_candidates = select_go_candidates(state, query="@bookmark")
    assert tuple(candidate.path for candidate in recent_candidates) == (str(recent),)
    assert tuple(candidate.path for candidate in bookmark_candidates) == (str(bookmarked),)


def test_go_navigation_error_keeps_the_go_palette_open(tmp_path) -> None:
    destination = tmp_path / "destination"
    destination.mkdir()
    state = _reduce_state(build_initial_app_state(), BeginGo())
    state = _reduce_state(state, SetCommandPaletteQuery(str(destination)))
    submitted = _reduce_state(state, SubmitCommandPalette())

    assert submitted.ui_mode == "BUSY"
    assert submitted.command_palette is None
    assert submitted.pending_go_palette is not None

    failed = _reduce_state(
        submitted,
        BrowserSnapshotFailed(request_id=1, message="Permission denied", blocking=True),
    )

    assert failed.ui_mode == "PALETTE"
    assert failed.command_palette is not None
    assert failed.command_palette.source == "go"
    assert failed.notification is not None
    assert failed.notification.message == "Permission denied"

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
    assert result.state.pending_attribute_inspection_request_id == 1
    assert result.state.attribute_inspection == AttributeInspectionState(
        name="docs",
        kind="dir",
        path="/home/tadashi/develop/zivo/docs",
        size_bytes=None,
        modified_at=state.current_pane.entries[0].modified_at,
        hidden=False,
        permissions_mode=state.current_pane.entries[0].permissions_mode,
    )
    assert result.effects == (
        RunAttributeInspectionEffect(
            request_id=1,
            path="/home/tadashi/develop/zivo/docs",
        ),
    )


def test_attribute_inspection_loaded_replaces_placeholder_dialog_state() -> None:
    state = reduce_app_state(build_initial_app_state(), ShowAttributes()).state

    next_state = reduce_app_state(
        state,
        AttributeInspectionLoaded(
            request_id=1,
            inspection=AttributeInspectionState(
                name="docs",
                kind="dir",
                path="/home/tadashi/develop/zivo/docs",
                modified_at=state.current_pane.entries[0].modified_at,
                permissions_mode=0o40755,
                owner="tadashi",
                group="staff",
            ),
        ),
    ).state

    assert next_state.pending_attribute_inspection_request_id is None
    assert next_state.attribute_inspection == AttributeInspectionState(
        name="docs",
        kind="dir",
        path="/home/tadashi/develop/zivo/docs",
        modified_at=state.current_pane.entries[0].modified_at,
        permissions_mode=0o40755,
        owner="tadashi",
        group="staff",
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


def test_select_command_palette_disables_replace_text_for_hidden_selected_file() -> None:
    hidden_path = "/home/tadashi/develop/zivo/.env"
    visible_path = "/home/tadashi/develop/zivo/README.md"
    state = replace(
        build_initial_app_state(),
        current_pane=PaneState(
            directory_path="/home/tadashi/develop/zivo",
            entries=(
                DirectoryEntryState(hidden_path, ".env", "file", hidden=True),
                DirectoryEntryState(visible_path, "README.md", "file"),
            ),
            cursor_path=visible_path,
            selected_paths=frozenset({hidden_path}),
        ),
    )

    palette_state = select_command_palette_state(
        replace(
            _reduce_state(state, BeginCommandPalette()),
            command_palette=replace(CommandPaletteState(), query="replace text"),
        )
    )

    assert palette_state is not None
    assert [item.label for item in palette_state.items] == ["Replace text"]
    assert palette_state.items[0].enabled is True

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
        message="No directory history in this direction",
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



def test_submit_command_palette_begins_rename_with_single_target() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("rename"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.ui_mode == "RENAME"
    assert result.state.command_palette is None
    assert result.state.pending_input is not None
    assert result.state.pending_input.prompt == "Rename: "


def test_submit_command_palette_begins_chmod_with_single_target() -> None:
    state = build_initial_app_state()
    docs_entry = replace(state.current_pane.entries[0], permissions_mode=0o40755)
    state = replace(
        state,
        current_pane=replace(
            state.current_pane,
            entries=(docs_entry, *state.current_pane.entries[1:]),
        ),
    )
    state = _reduce_state(state, BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("permissions"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.ui_mode == "CHMOD"
    assert result.state.command_palette is None
    assert result.state.pending_input is not None
    assert result.state.pending_input.prompt == "Permissions: "
    assert result.state.pending_input.value == "755"


def test_submit_command_palette_begins_chmod_with_selection() -> None:
    state = build_initial_app_state()
    docs_entry = replace(state.current_pane.entries[0], permissions_mode=0o40755)
    src_entry = state.current_pane.entries[1]
    state = replace(
        state,
        current_pane=replace(
            state.current_pane,
            entries=(docs_entry, *state.current_pane.entries[1:]),
            selected_paths=frozenset({docs_entry.path, src_entry.path}),
        ),
    )
    state = _reduce_state(state, BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("permissions"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.ui_mode == "CHMOD"
    assert result.state.command_palette is None
    assert result.state.pending_input is not None
    assert result.state.pending_input.prompt == "Permissions: "
    assert result.state.pending_input.value == "755"
    assert result.state.pending_input.chmod_target_paths == (
        "/home/tadashi/develop/zivo/docs",
        "/home/tadashi/develop/zivo/src",
    )
    assert result.state.pending_input.chmod_recursive is False


def test_submit_command_palette_begins_chown_with_selection() -> None:
    state = build_initial_app_state()
    docs_entry = replace(state.current_pane.entries[0], owner="alice", group="staff")
    src_entry = state.current_pane.entries[1]
    state = replace(
        state,
        current_pane=replace(
            state.current_pane,
            entries=(docs_entry, *state.current_pane.entries[1:]),
            selected_paths=frozenset({docs_entry.path, src_entry.path}),
        ),
    )
    state = _reduce_state(state, BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("owner"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.ui_mode == "CHOWN"
    assert result.state.command_palette is None
    assert result.state.pending_input is not None
    assert result.state.pending_input.prompt == "Owner: "
    assert result.state.pending_input.value == "alice:staff"
    assert result.state.pending_input.chown_target_paths == (
        "/home/tadashi/develop/zivo/docs",
        "/home/tadashi/develop/zivo/src",
    )
    assert result.state.pending_input.chown_recursive is False


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
    state = _reduce_state(state, SetCommandPaletteQuery("copy path"))

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


def test_submit_command_palette_begins_terminal_window_custom_action_confirmation() -> None:
    state = replace(
        build_initial_app_state(
            config=AppConfig(
                actions=ActionsConfig(
                    custom=(
                        CustomActionConfig(
                            name="Open lazygit in new terminal",
                            command=("lazygit",),
                            when="always",
                            mode="terminal_window",
                            cwd="{cwd}",
                        ),
                    )
                )
            )
        ),
    )
    state = _reduce_state(state, BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("lazygit in new"))

    next_state = _reduce_state(state, SubmitCommandPalette())

    assert next_state.ui_mode == "CONFIRM"
    assert next_state.custom_action_confirmation is not None
    assert next_state.custom_action_confirmation.request.name == "Open lazygit in new terminal"
    assert next_state.custom_action_confirmation.request.command == ("lazygit",)
    assert next_state.custom_action_confirmation.request.mode == "terminal_window"


def test_confirm_terminal_window_custom_action_stays_in_browsing() -> None:
    state = replace(
        build_initial_app_state(
            config=AppConfig(
                actions=ActionsConfig(
                    custom=(
                        CustomActionConfig(
                            name="Open lazygit in new terminal",
                            command=("lazygit",),
                            when="always",
                            mode="terminal_window",
                            cwd="{cwd}",
                        ),
                    )
                )
            )
        ),
    )
    state = _reduce_state(state, BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("lazygit in new"))
    state = _reduce_state(state, SubmitCommandPalette())

    result = reduce_app_state(state, ConfirmCustomAction())

    assert result.state.ui_mode == "BROWSING"
    assert result.state.pending_custom_action_request_id == 1
    assert any(
        isinstance(effect, RunCustomActionEffect)
        and effect.request.mode == "terminal_window"
        for effect in result.effects
    )
