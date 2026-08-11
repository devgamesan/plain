# ruff: noqa: F821

import os
from dataclasses import replace
from stat import S_IFREG

import zivo.state.selectors as selectors_module
from tests.state_test_helpers import entry, pane, reduce_state
from zivo.models import (
    ActionsConfig,
    AppConfig,
    BookmarkConfig,
    CreateZipArchiveRequest,
    CustomActionConfig,
    DisplayConfig,
    EditorConfig,
    ExtractArchiveRequest,
    GuiEditorConfig,
    PasteConflict,
    PasteRequest,
    StatusBarActionState,
    UndoDeletePathStep,
    UndoEntry,
)
from zivo.state import (
    ArchiveExtractConfirmationState,
    AttributeInspectionState,
    CommandPaletteState,
    ConfigEditorState,
    CurrentPaneDeltaState,
    DeleteConfirmationState,
    DirectoryEntryState,
    DirectorySizeCacheEntry,
    DirectorySizeDeltaState,
    FileSearchPaletteState,
    FileSearchResultState,
    ForegroundOperationState,
    GrepSearchPaletteState,
    GrepSearchResultState,
    GrfPaletteState,
    GrsPaletteState,
    HistoryAndNavigationPaletteState,
    HistoryState,
    NameConflictState,
    NotificationState,
    PaneState,
    PasteConflictState,
    PendingInputState,
    PendingKeySequenceState,
    PreviewMetadataState,
    ReplacePreviewPaletteState,
    ReplacePreviewResultState,
    RffPaletteState,
    ZipCompressConfirmationState,
    build_initial_app_state,
    build_placeholder_app_state,
    select_attribute_dialog_state,
    select_child_entries,
    select_command_palette_state,
    select_config_dialog_state,
    select_conflict_dialog_state,
    select_current_entries,
    select_current_summary_state,
    select_help_bar_state,
    select_input_bar_state,
    select_parent_entries,
    select_responsive_pane_layout,
    select_shell_data,
    select_status_bar_state,
    select_tab_bar_state,
    select_target_paths,
    select_visible_current_entry_states,
)
from zivo.state import command_palette as command_palette_module
from zivo.state.actions import (
    BeginCommandPalette,
    BeginCreateInput,
    BeginFilterInput,
    ConfirmFilterInput,
    CutTargets,
    OpenNewTab,
    SetCursorPath,
    SetFilterQuery,
    SetNotification,
    SetSort,
    ToggleSelection,
    ToggleTransferMode,
)
from zivo.state.command_palette import CommandPaletteItem
from zivo.state.reducer_common import directory_size_target_paths
from zivo.state.selectors import (
    _has_execute_permission,
    _select_command_palette_window,
    compute_current_pane_visible_window,
    select_input_dialog_state,
)

SEARCH_WORKSPACE_PATH = (
    "search://readme?target=files&hidden=false&root=%2Fhome%2Ftadashi%2Fdevelop%2Fzivo"
)


def build_search_workspace_state():
    result_path = "/home/tadashi/develop/zivo/README.md"
    state = build_initial_app_state()
    return replace(
        state,
        current_path=SEARCH_WORKSPACE_PATH,
        current_pane=pane(
            SEARCH_WORKSPACE_PATH,
            (entry(result_path, "file"),),
            cursor_path=result_path,
        ),
    )


def _reduce_state(state, action):
    return reduce_state(state, action)


def _display_path_for_test(path: str) -> str:
    return command_palette_module._display_path(path)


def test_select_current_entries_applies_filter_and_sort() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, SetFilterQuery("t"))
    state = _reduce_state(
        state,
        SetSort(field="name", descending=True, directories_first=False),
    )

    entries = select_current_entries(state)

    assert [entry.name for entry in entries] == ["tests", "pyproject.toml"]


def test_select_current_entries_sorts_names_naturally() -> None:
    state = replace(
        build_initial_app_state(),
        current_pane=PaneState(
            directory_path="/home/tadashi/develop/zivo",
            entries=(
                entry("/home/tadashi/develop/zivo/file1", "file"),
                entry("/home/tadashi/develop/zivo/file10", "file"),
                entry("/home/tadashi/develop/zivo/file2", "file"),
                entry("/home/tadashi/develop/zivo/file20", "file"),
                entry("/home/tadashi/develop/zivo/dir1", "dir"),
            ),
        ),
    )

    entries = select_current_entries(state)

    assert [item.name for item in entries] == [
        "dir1",
        "file1",
        "file2",
        "file10",
        "file20",
    ]


def test_select_current_entries_sorts_names_naturally_descending() -> None:
    state = replace(
        build_initial_app_state(),
        current_pane=PaneState(
            directory_path="/home/tadashi/develop/zivo",
            entries=(
                entry("/home/tadashi/develop/zivo/file1", "file"),
                entry("/home/tadashi/develop/zivo/file10", "file"),
                entry("/home/tadashi/develop/zivo/file2", "file"),
                entry("/home/tadashi/develop/zivo/dir1", "dir"),
            ),
        ),
    )
    state = _reduce_state(
        state, SetSort(field="name", descending=True, directories_first=True)
    )

    entries = select_current_entries(state)

    assert [item.name for item in entries] == [
        "dir1",
        "file10",
        "file2",
        "file1",
    ]


def test_select_current_entries_hides_hidden_by_default() -> None:
    state = replace(
        build_initial_app_state(),
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
            ),
            cursor_path="/home/tadashi/develop/zivo/docs",
        ),
    )

    entries = select_current_entries(state)

    assert [entry.name for entry in entries] == ["docs"]


def test_build_placeholder_app_state_keeps_parent_pane_empty_at_root() -> None:
    state = build_placeholder_app_state("/")

    expected_root = "C:\\" if os.name == "nt" else "/"
    assert state.current_path == expected_root
    assert state.parent_pane.directory_path == expected_root
    assert state.parent_pane.entries == ()
    assert state.parent_pane.cursor_path is None


def test_select_visible_current_entries_sorts_by_modified_with_missing_values_last() -> None:
    state = replace(
        build_initial_app_state(),
        current_pane=pane(
            "/home/tadashi/develop/zivo",
            (
                entry(
                    "/home/tadashi/develop/zivo/alpha.txt",
                    modified_at=None,
                ),
                entry(
                    "/home/tadashi/develop/zivo/beta.txt",
                    modified_at=build_initial_app_state().current_pane.entries[3].modified_at,
                ),
                entry(
                    "/home/tadashi/develop/zivo/gamma.txt",
                    modified_at=build_initial_app_state().current_pane.entries[4].modified_at,
                ),
            ),
            cursor_path="/home/tadashi/develop/zivo/alpha.txt",
        ),
        sort=replace(build_initial_app_state().sort, field="modified", descending=True),
    )

    entries = select_visible_current_entry_states(state)

    assert [entry.name for entry in entries] == ["alpha.txt", "beta.txt", "gamma.txt"]


def test_select_visible_current_entries_sorts_by_size_without_directories_first() -> None:
    state = replace(
        build_initial_app_state(),
        current_pane=pane(
            "/home/tadashi/develop/zivo",
            (
                entry("/home/tadashi/develop/zivo/docs", kind="dir"),
                entry("/home/tadashi/develop/zivo/alpha.txt", size_bytes=500),
                entry("/home/tadashi/develop/zivo/beta.txt", size_bytes=2_000),
            ),
            cursor_path="/home/tadashi/develop/zivo/docs",
        ),
        sort=replace(
            build_initial_app_state().sort,
            field="size",
            descending=True,
            directories_first=False,
        ),
    )

    entries = select_visible_current_entry_states(state)

    assert [entry.name for entry in entries] == ["beta.txt", "alpha.txt", "docs"]


def test_has_execute_permission_returns_true_for_executable_files() -> None:
    """0o755 (rwxr-xr-x) の場合に True を返すこと"""
    entry_state = DirectoryEntryState(
        "/home/tadashi/develop/zivo/test.sh",
        "test.sh",
        "file",
        permissions_mode=0o755,
    )

    assert _has_execute_permission(entry_state) is True


def test_has_execute_permission_returns_false_for_non_executable_files() -> None:
    """0o644 (rw-r--r--) の場合に False を返すこと"""
    entry_state = DirectoryEntryState(
        "/home/tadashi/develop/zivo/README.md",
        "README.md",
        "file",
        permissions_mode=0o644,
    )

    assert _has_execute_permission(entry_state) is False


def test_has_execute_permission_returns_true_for_execute_only_files() -> None:
    """0o111 (--x--x--x) の場合に True を返すこと"""
    entry_state = DirectoryEntryState(
        "/home/tadashi/develop/zivo/script",
        "script",
        "file",
        permissions_mode=0o111,
    )

    assert _has_execute_permission(entry_state) is True


def test_has_execute_permission_returns_false_for_no_permissions() -> None:
    """0o000 (---------) の場合に False を返すこと"""
    entry_state = DirectoryEntryState(
        "/home/tadashi/develop/zivo/locked",
        "locked",
        "file",
        permissions_mode=0o000,
    )

    assert _has_execute_permission(entry_state) is False


def test_has_execute_permission_returns_false_for_none_permissions() -> None:
    """permissions_mode が None の場合に False を返すこと"""
    entry_state = DirectoryEntryState(
        "/home/tadashi/develop/zivo/unknown",
        "unknown",
        "file",
        permissions_mode=None,
    )

    assert _has_execute_permission(entry_state) is False


def test_select_parent_and_child_entries_hide_hidden_unless_enabled() -> None:
    state = replace(
        build_initial_app_state(),
        parent_pane=PaneState(
            directory_path="/tmp",
            entries=(
                DirectoryEntryState("/tmp/.cache", ".cache", "dir", hidden=True),
                DirectoryEntryState("/tmp/zivo", "zivo", "dir"),
            ),
            cursor_path="/tmp/zivo",
        ),
        current_pane=PaneState(
            directory_path="/home/tadashi/develop/zivo",
            entries=(DirectoryEntryState("/home/tadashi/develop/zivo/docs", "docs", "dir"),),
            cursor_path="/home/tadashi/develop/zivo/docs",
        ),
        child_pane=PaneState(
            directory_path="/home/tadashi/develop/zivo/docs",
            entries=(
                DirectoryEntryState(
                    "/home/tadashi/develop/zivo/docs/.draft.md",
                    ".draft.md",
                    "file",
                    hidden=True,
                ),
                DirectoryEntryState(
                    "/home/tadashi/develop/zivo/docs/spec.md",
                    "spec.md",
                    "file",
                ),
            ),
        ),
    )

    assert [entry.name for entry in select_parent_entries(state)] == ["zivo"]
    assert [entry.name for entry in select_child_entries(state)] == ["spec.md"]

    visible_state = replace(state, show_hidden=True)

    assert [entry.name for entry in select_parent_entries(visible_state)] == [".cache", "zivo"]
    assert [entry.name for entry in select_child_entries(visible_state)] == [
        ".draft.md",
        "spec.md",
    ]


def test_select_parent_entries_marks_current_directory_selected() -> None:
    state = replace(
        build_initial_app_state(),
        parent_pane=PaneState(
            directory_path="/tmp",
            entries=(
                DirectoryEntryState("/tmp/alpha", "alpha", "dir"),
                DirectoryEntryState("/tmp/zivo", "zivo", "dir"),
            ),
            cursor_path="/tmp/zivo",
        ),
    )

    entries = select_parent_entries(state)

    assert [entry.name for entry in entries] == ["alpha", "zivo"]
    assert entries[0].selected is False
    assert entries[1].selected is True


def test_select_child_entries_clears_stale_snapshot_while_request_is_pending() -> None:
    state = replace(
        build_initial_app_state(),
        current_pane=PaneState(
            directory_path="/home/tadashi/develop/zivo",
            entries=(
                DirectoryEntryState("/home/tadashi/develop/zivo/docs", "docs", "dir"),
                DirectoryEntryState("/home/tadashi/develop/zivo/src", "src", "dir"),
            ),
            cursor_path="/home/tadashi/develop/zivo/src",
        ),
        child_pane=PaneState(
            directory_path="/home/tadashi/develop/zivo/docs",
            entries=(
                DirectoryEntryState(
                    "/home/tadashi/develop/zivo/docs/spec.md",
                    "spec.md",
                    "file",
                ),
            ),
        ),
        pending_child_pane_request_id=7,
    )

    assert select_child_entries(state) == ()


def test_select_shell_data_hides_stale_preview_while_request_is_pending() -> None:
    current_path = "/home/tadashi/develop/zivo"
    previous_preview_path = f"{current_path}/README.md"
    requested_preview_path = f"{current_path}/pyproject.toml"
    state = replace(
        build_initial_app_state(),
        current_pane=PaneState(
            directory_path=current_path,
            entries=(
                DirectoryEntryState(previous_preview_path, "README.md", "file"),
                DirectoryEntryState(requested_preview_path, "pyproject.toml", "file"),
            ),
            cursor_path=requested_preview_path,
        ),
        child_pane=PaneState(
            directory_path=current_path,
            entries=(),
            mode="preview",
            preview_path=previous_preview_path,
            preview_content="# Preview\n",
        ),
        pending_child_pane_request_id=7,
    )

    shell = select_shell_data(state)

    assert shell.child_pane.is_preview is True
    assert shell.child_pane.view_kind == "loading"
    assert shell.child_pane.status is not None
    assert shell.child_pane.status.title == "Loading preview…"


def test_select_pane_entries_show_directory_sizes_from_cache() -> None:
    state = replace(
        build_initial_app_state(
            config=AppConfig(
                display=replace(
                    AppConfig().display,
                    show_directory_sizes=True,
                )
            )
        ),
        parent_pane=PaneState(
            directory_path="/tmp",
            entries=(DirectoryEntryState("/tmp/zivo", "zivo", "dir"),),
            cursor_path="/tmp/zivo",
        ),
        current_pane=PaneState(
            directory_path="/home/tadashi/develop/zivo",
            entries=(
                DirectoryEntryState("/home/tadashi/develop/zivo/docs", "docs", "dir"),
                DirectoryEntryState(
                    "/home/tadashi/develop/zivo/README.md",
                    "README.md",
                    "file",
                    size_bytes=2_150,
                ),
            ),
            cursor_path="/home/tadashi/develop/zivo/docs",
        ),
        child_pane=PaneState(
            directory_path="/home/tadashi/develop/zivo/docs",
            entries=(DirectoryEntryState("/home/tadashi/develop/zivo/docs/api", "api", "dir"),),
        ),
        directory_size_cache=(
            DirectorySizeCacheEntry(
                "/tmp/zivo",
                "ready",
                size_bytes=3_400_000,
            ),
            DirectorySizeCacheEntry(
                "/home/tadashi/develop/zivo/docs",
                "pending",
            ),
            DirectorySizeCacheEntry(
                "/home/tadashi/develop/zivo/docs/api",
                "ready",
                size_bytes=8_200,
            ),
        ),
    )

    parent_entries = select_parent_entries(state)
    current_entries = select_current_entries(state)
    child_entries = select_child_entries(state)

    assert parent_entries[0].name_detail is None
    assert current_entries[0].size_label == "-"
    assert child_entries[0].name_detail is None


def test_directory_size_target_paths_only_uses_current_pane_directories() -> None:
    state = replace(
        build_initial_app_state(
            config=AppConfig(
                display=replace(
                    AppConfig().display,
                    show_directory_sizes=True,
                )
            )
        ),
        parent_pane=PaneState(
            directory_path="/tmp",
            entries=(DirectoryEntryState("/tmp/zivo", "zivo", "dir"),),
            cursor_path="/tmp/zivo",
        ),
        current_pane=PaneState(
            directory_path="/home/tadashi/develop/zivo",
            entries=(
                DirectoryEntryState("/home/tadashi/develop/zivo/docs", "docs", "dir"),
                DirectoryEntryState(
                    "/home/tadashi/develop/zivo/.cache",
                    ".cache",
                    "dir",
                    hidden=True,
                ),
                DirectoryEntryState(
                    "/home/tadashi/develop/zivo/README.md",
                    "README.md",
                    "file",
                ),
            ),
            cursor_path="/home/tadashi/develop/zivo/docs",
        ),
        child_pane=PaneState(
            directory_path="/home/tadashi/develop/zivo/docs",
            entries=(DirectoryEntryState("/home/tadashi/develop/zivo/docs/api", "api", "dir"),),
        ),
    )

    assert directory_size_target_paths(state) == ("/home/tadashi/develop/zivo/docs",)


def test_directory_size_target_paths_respects_current_hidden_visibility() -> None:
    state = replace(
        build_initial_app_state(
            config=AppConfig(
                display=replace(
                    AppConfig().display,
                    show_directory_sizes=True,
                )
            )
        ),
        current_pane=PaneState(
            directory_path="/home/tadashi/develop/zivo",
            entries=(
                DirectoryEntryState("/home/tadashi/develop/zivo/docs", "docs", "dir"),
                DirectoryEntryState(
                    "/home/tadashi/develop/zivo/.cache",
                    ".cache",
                    "dir",
                    hidden=True,
                ),
            ),
            cursor_path="/home/tadashi/develop/zivo/docs",
        ),
    )

    assert directory_size_target_paths(state) == ("/home/tadashi/develop/zivo/docs",)
    assert directory_size_target_paths(replace(state, show_hidden=True)) == (
        "/home/tadashi/develop/zivo/.cache",
        "/home/tadashi/develop/zivo/docs",
    )


def test_directory_size_target_paths_returns_empty_when_directory_sizes_are_disabled() -> None:
    state = replace(
        build_initial_app_state(),
        config=replace(
            build_initial_app_state().config,
            display=replace(build_initial_app_state().config.display, show_directory_sizes=False),
        ),
        current_pane=PaneState(
            directory_path="/home/tadashi/develop/zivo",
            entries=(DirectoryEntryState("/home/tadashi/develop/zivo/docs", "docs", "dir"),),
            cursor_path="/home/tadashi/develop/zivo/docs",
        ),
    )

    assert directory_size_target_paths(state) == ()


def test_directory_size_target_paths_uses_current_pane_for_size_sort() -> None:
    state = replace(
        build_initial_app_state(),
        current_pane=PaneState(
            directory_path="/home/tadashi/develop/zivo",
            entries=(
                DirectoryEntryState("/home/tadashi/develop/zivo/docs", "docs", "dir"),
                DirectoryEntryState("/home/tadashi/develop/zivo/src", "src", "dir"),
                DirectoryEntryState(
                    "/home/tadashi/develop/zivo/README.md",
                    "README.md",
                    "file",
                ),
            ),
            cursor_path="/home/tadashi/develop/zivo/docs",
        ),
        sort=replace(build_initial_app_state().sort, field="size"),
    )

    assert directory_size_target_paths(state) == (
        "/home/tadashi/develop/zivo/docs",
        "/home/tadashi/develop/zivo/src",
    )


def test_select_visible_current_entries_skip_size_overlay_when_not_sorting_by_size() -> None:
    state = replace(
        build_initial_app_state(),
        directory_size_cache=(
            DirectorySizeCacheEntry(
                "/home/tadashi/develop/zivo/docs",
                "ready",
                size_bytes=4_200,
            ),
        ),
    )

    visible_entries = select_visible_current_entry_states(state)

    assert visible_entries[0].path == "/home/tadashi/develop/zivo/docs"
    assert visible_entries[0].size_bytes is None


def test_select_shell_data_emits_size_delta_updates_for_directory_size_changes() -> None:
    state = replace(
        build_initial_app_state(
            config=AppConfig(
                display=replace(
                    AppConfig().display,
                    show_directory_sizes=True,
                )
            )
        ),
        directory_size_cache=(
            DirectorySizeCacheEntry(
                "/home/tadashi/develop/zivo/docs",
                "ready",
                size_bytes=4_200,
            ),
        ),
        directory_size_delta=DirectorySizeDeltaState(
            changed_paths=("/home/tadashi/develop/zivo/docs",),
            revision=3,
        ),
    )

    shell = select_shell_data(state)
    row_index = next(
        index
        for index, entry in enumerate(select_current_entries(state))
        if entry.path == "/home/tadashi/develop/zivo/docs"
    )

    assert shell.current_entries is None
    assert shell.current_pane_update.mode == "size_delta"
    assert shell.current_pane_update.revision == 3
    assert [
        (update.path, update.size_label, update.row_index)
        for update in shell.current_pane_update.size_updates
    ] == [
        ("/home/tadashi/develop/zivo/docs", "4.1KiB", row_index)
    ]


def test_select_shell_data_emits_row_delta_updates_for_selection_changes() -> None:
    path = "/home/tadashi/develop/zivo/README.md"
    state = replace(
        build_initial_app_state(),
        current_pane=replace(
            build_initial_app_state().current_pane,
            selected_paths=frozenset({path}),
        ),
        current_pane_delta=CurrentPaneDeltaState(
            changed_paths=(path,),
            revision=2,
        ),
    )

    shell = select_shell_data(state)
    row_index = next(
        index for index, entry in enumerate(select_current_entries(state)) if entry.path == path
    )

    assert shell.current_entries is None
    assert shell.current_pane_update.mode == "row_delta"
    assert shell.current_pane_update.revision == 2
    assert [
        (update.path, update.entry.selected, update.row_index)
        for update in shell.current_pane_update.row_updates
    ] == [
        (path, True, row_index)
    ]


def test_select_shell_data_emits_row_delta_updates_for_cut_changes() -> None:
    path = "/home/tadashi/develop/zivo/docs"
    state = replace(
        build_initial_app_state(),
        clipboard=replace(build_initial_app_state().clipboard, mode="cut", paths=(path,)),
        current_pane_delta=CurrentPaneDeltaState(
            changed_paths=(path,),
            revision=4,
        ),
    )

    shell = select_shell_data(state)
    row_index = next(
        index for index, entry in enumerate(select_current_entries(state)) if entry.path == path
    )

    assert shell.current_entries is None
    assert shell.current_pane_update.mode == "row_delta"
    assert shell.current_pane_update.revision == 4
    assert [
        (update.path, update.entry.cut, update.row_index)
        for update in shell.current_pane_update.row_updates
    ] == [
        (path, True, row_index)
    ]


def test_select_shell_data_keeps_full_refresh_when_sorting_by_size() -> None:
    state = replace(
        build_initial_app_state(),
        sort=replace(build_initial_app_state().sort, field="size"),
        current_pane_delta=CurrentPaneDeltaState(
            changed_paths=("/home/tadashi/develop/zivo/docs",),
            revision=7,
        ),
        directory_size_cache=(
            DirectorySizeCacheEntry(
                "/home/tadashi/develop/zivo/docs",
                "ready",
                size_bytes=4_200,
            ),
        ),
        directory_size_delta=DirectorySizeDeltaState(
            changed_paths=("/home/tadashi/develop/zivo/docs",),
            revision=2,
        ),
    )

    shell = select_shell_data(state)

    assert shell.current_pane_update.mode == "full"
    assert shell.current_entries is not None


def test_select_current_summary_counts_selected_absolute_paths() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, ToggleSelection("/home/tadashi/develop/zivo/README.md"))
    state = _reduce_state(state, ToggleSelection("/home/tadashi/develop/zivo/tests"))

    summary = select_current_summary_state(state)

    assert summary.selected_count == 2
    assert summary.item_count == 5


def test_select_target_paths_prefers_selection_in_entry_order() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, ToggleSelection("/home/tadashi/develop/zivo/README.md"))
    state = _reduce_state(state, ToggleSelection("/home/tadashi/develop/zivo/docs"))

    assert select_target_paths(state) == (
        "/home/tadashi/develop/zivo/docs",
        "/home/tadashi/develop/zivo/README.md",
    )


def test_select_target_paths_ignores_hidden_selected_entries_when_hidden_files_are_off() -> None:
    hidden_path = "/home/tadashi/develop/zivo/.env"
    visible_path = "/home/tadashi/develop/zivo/docs"
    state = replace(
        build_initial_app_state(),
        current_pane=pane(
            "/home/tadashi/develop/zivo",
            (
                entry(hidden_path, hidden=True),
                entry(visible_path, kind="dir"),
            ),
            cursor_path=visible_path,
            selected_paths=(hidden_path, visible_path),
        ),
    )

    assert select_target_paths(state) == (visible_path,)


def test_select_target_paths_falls_back_to_cursor() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, SetCursorPath("/home/tadashi/develop/zivo/tests"))

    assert select_target_paths(state) == ("/home/tadashi/develop/zivo/tests",)


def test_select_target_paths_returns_empty_tuple_for_empty_directory() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        current_pane=PaneState(directory_path=state.current_path, entries=(), cursor_path=None),
    )

    assert select_target_paths(state) == ()


def test_select_current_entry_for_path_returns_none_for_filtered_entry() -> None:
    hidden_path = "/home/tadashi/develop/zivo/README.md"
    visible_path = "/home/tadashi/develop/zivo/docs"
    state = replace(
        build_initial_app_state(),
        current_pane=PaneState(
            directory_path="/home/tadashi/develop/zivo",
            entries=(
                DirectoryEntryState(hidden_path, "README.md", "file"),
                DirectoryEntryState(visible_path, "docs", "dir"),
            ),
            cursor_path=visible_path,
        ),
        filter=replace(build_initial_app_state().filter, query="docs", active=True),
    )

    assert selectors_module.select_current_entry_for_path(state, hidden_path) is None
    assert selectors_module.select_current_entry_for_path(state, visible_path) is not None


def test_select_target_file_paths_ignores_hidden_selected_entries_when_hidden_files_are_off(
) -> None:
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

    assert selectors_module.select_target_file_paths(state) == ()


def test_select_current_entries_marks_selected_rows() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, ToggleSelection("/home/tadashi/develop/zivo/README.md"))

    entries = select_current_entries(state)

    assert entries[0].selected is False
    assert entries[4].name == "README.md"
    assert entries[4].selected is True
    assert entries[4].selection_marker == "*"


def test_select_current_entries_marks_cut_rows() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, CutTargets(("/home/tadashi/develop/zivo/docs",)))

    entries = select_current_entries(state)

    assert entries[0].name == "docs"
    assert entries[0].cut is True
    assert entries[1].cut is False


def test_select_child_entries_is_empty_when_cursor_is_file() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, SetCursorPath("/home/tadashi/develop/zivo/README.md"))

    assert select_child_entries(state) == ()


def test_select_shell_data_builds_child_preview_for_text_file() -> None:
    initial_state = build_initial_app_state()
    path = "/home/tadashi/develop/zivo/README.md"
    state = replace(
        initial_state,
        current_pane=replace(initial_state.current_pane, cursor_path=path),
        child_pane=PaneState(
            directory_path="/home/tadashi/develop/zivo",
            entries=(),
            mode="preview",
            preview_path=path,
            preview_content="# Preview\n",
            preview_truncated=True,
        ),
    )

    shell = select_shell_data(state)

    assert shell.child_pane.is_preview is True
    assert shell.child_pane.title == "Preview: README.md (truncated)"
    assert shell.child_pane.preview_path == path
    assert shell.child_pane.preview_content == "# Preview\n"
    assert shell.child_pane.preview_message is None


def test_select_shell_data_builds_child_preview_message_for_unavailable_file() -> None:
    initial_state = build_initial_app_state()
    path = "/home/tadashi/develop/zivo/archive.bin"
    state = replace(
        initial_state,
        current_pane=replace(
            initial_state.current_pane,
            entries=initial_state.current_pane.entries
            + (DirectoryEntryState(path, "archive.bin", "file"),),
            cursor_path=path,
        ),
        child_pane=PaneState(
            directory_path="/home/tadashi/develop/zivo",
            entries=(),
            mode="preview",
            preview_path=path,
            preview_message="Preview unavailable for this file type",
        ),
    )

    shell = select_shell_data(state)

    assert shell.child_pane.is_preview is True
    assert shell.child_pane.title == "Preview: archive.bin"
    assert shell.child_pane.preview_path == path
    assert shell.child_pane.preview_content is None
    assert shell.child_pane.preview_message == "Preview unavailable for this file type"


def test_select_shell_data_builds_child_preview_for_permission_denied_directory() -> None:
    from zivo.services import PREVIEW_PERMISSION_DENIED_MESSAGE

    initial_state = build_initial_app_state()
    path = "/home/tadashi/develop/zivo/.Trash"
    state = replace(
        initial_state,
        current_pane=replace(
            initial_state.current_pane,
            entries=initial_state.current_pane.entries
            + (DirectoryEntryState(path, ".Trash", "dir"),),
            cursor_path=path,
        ),
        child_pane=PaneState(
            directory_path=path,
            entries=(),
            mode="preview",
            preview_message=PREVIEW_PERMISSION_DENIED_MESSAGE,
        ),
    )

    shell = select_shell_data(state)

    assert shell.child_pane.is_preview is True
    assert shell.child_pane.preview_path == path
    assert shell.child_pane.preview_content is None
    assert shell.child_pane.preview_message == PREVIEW_PERMISSION_DENIED_MESSAGE


def test_select_shell_data_builds_grep_preview_for_palette_selection() -> None:
    initial_state = build_initial_app_state()
    path = "/home/tadashi/develop/zivo/README.md"
    grep_result = GrepSearchResultState(
        path=path,
        display_path="README.md",
        line_number=5,
        line_text="TODO: update docs",
    )
    state = replace(
        initial_state,
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="grep_search",
            query="todo",
            grep_search=GrepSearchPaletteState(results=(grep_result,)),
        ),
        child_pane=PaneState(
            directory_path="/home/tadashi/develop/zivo",
            entries=(),
            mode="preview",
            preview_path=path,
            preview_title="Preview: README.md:5",
            preview_content="line3\nline4\nTODO: update docs\nline6\n",
            preview_start_line=2,
            preview_highlight_line=5,
        ),
    )

    shell = select_shell_data(state)

    assert shell.child_pane.is_preview is True
    assert shell.child_pane.title == "Preview: README.md:5"
    assert shell.child_pane.preview_path == path
    assert shell.child_pane.preview_start_line == 2
    assert shell.child_pane.preview_highlight_line == 5


def test_select_parent_and_child_entries_keep_fixed_name_sort() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        parent_pane=PaneState(
            directory_path="/tmp",
            entries=(
                DirectoryEntryState("/tmp/beta.txt", "beta.txt", "file"),
                DirectoryEntryState("/tmp/alpha", "alpha", "dir"),
                DirectoryEntryState("/tmp/gamma", "gamma", "dir"),
            ),
            cursor_path="/tmp/alpha",
        ),
        current_pane=PaneState(
            directory_path="/home/tadashi/develop/zivo",
            entries=state.current_pane.entries,
            cursor_path="/home/tadashi/develop/zivo/docs",
        ),
        child_pane=PaneState(
            directory_path="/home/tadashi/develop/zivo/docs",
            entries=(
                DirectoryEntryState(
                    "/home/tadashi/develop/zivo/docs/readme.txt",
                    "readme.txt",
                    "file",
                ),
                DirectoryEntryState(
                    "/home/tadashi/develop/zivo/docs/archive",
                    "archive",
                    "dir",
                ),
            ),
        ),
        sort=replace(state.sort, field="modified", descending=True, directories_first=False),
    )
    state = _reduce_state(
        state,
        SetSort(field="modified", descending=True, directories_first=False),
    )

    parent_entries = select_parent_entries(state)
    child_entries = select_child_entries(state)

    assert [entry.name for entry in parent_entries] == ["alpha", "gamma", "beta.txt"]
    assert [entry.name for entry in child_entries] == ["archive", "readme.txt"]


def test_select_shell_data_exposes_visible_cursor_index() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, SetCursorPath("/home/tadashi/develop/zivo/tests"))

    shell = select_shell_data(state)

    assert shell.current_path == "/home/tadashi/develop/zivo"
    assert shell.current_cursor_index == 2
    assert shell.current_cursor_visible is True


def test_select_responsive_pane_layout_uses_width_breakpoints_and_narrow_view() -> None:
    state = build_initial_app_state()

    wide = select_responsive_pane_layout(replace(state, terminal_width=120))
    medium = select_responsive_pane_layout(replace(state, terminal_width=80))
    narrow_current = select_responsive_pane_layout(replace(state, terminal_width=79))
    narrow_details = select_responsive_pane_layout(
        replace(state, terminal_width=79, narrow_pane_view="details")
    )

    assert (wide.width_class, wide.show_parent, wide.show_current, wide.show_child) == (
        "wide",
        True,
        True,
        True,
    )
    assert (medium.width_class, medium.show_parent, medium.show_current, medium.show_child) == (
        "medium",
        False,
        True,
        True,
    )
    assert (narrow_current.show_current, narrow_current.show_child) == (True, False)
    assert (narrow_details.show_current, narrow_details.show_child) == (False, True)


def test_select_shell_data_exposes_semantic_pane_headers() -> None:
    state = build_initial_app_state()
    shell = select_shell_data(state)

    assert shell.parent_heading.startswith("Parent · ")
    assert shell.current_heading.role == "Current"
    assert shell.child_pane.display_title.startswith("Contents · ")


def test_child_preview_moves_size_into_metadata_bar() -> None:
    initial_state = build_initial_app_state()
    path = "/home/tadashi/develop/zivo/README.md"
    state = replace(
        initial_state,
        current_pane=replace(initial_state.current_pane, cursor_path=path),
        child_pane=PaneState(
            directory_path=initial_state.current_path,
            entries=(),
            mode="preview",
            preview_path=path,
            preview_content="# Preview\n",
        ),
    )

    child = select_shell_data(state).child_pane

    assert child.display_title == "Preview · README.md"
    assert [(item.label, item.value) for item in child.metadata_bar] == [
        ("Size", "2.1KiB"),
    ]


def test_child_directory_uses_cached_size_and_permissions_in_metadata_bar() -> None:
    initial_state = build_initial_app_state()
    path = "/home/tadashi/develop/zivo/docs"
    directory = DirectoryEntryState(
        path,
        "docs",
        "dir",
        modified_at=initial_state.current_pane.entries[0].modified_at,
        permissions_mode=0o40755,
    )
    state = replace(
        initial_state,
        current_pane=replace(initial_state.current_pane, entries=(directory,), cursor_path=path),
        child_pane=PaneState(
            directory_path=initial_state.current_path,
            entries=(),
            mode="entries",
        ),
        directory_size_cache=(DirectorySizeCacheEntry(path, "ready", size_bytes=4096),),
    )

    child = select_shell_data(state).child_pane

    assert child.display_title == "Contents · docs · 0 items"
    assert [(item.label, item.value) for item in child.metadata_bar] == [
        ("Size", "4.0KiB"),
        ("Permissions", "drwxr-xr-x (755)"),
    ]


def test_preview_fallback_does_not_duplicate_attribute_bar() -> None:
    initial_state = build_initial_app_state()
    path = f"{initial_state.current_path}/data.bin"
    state = replace(
        initial_state,
        current_pane=replace(
            initial_state.current_pane,
            entries=(DirectoryEntryState(path, "data.bin", "file", size_bytes=2048),),
            cursor_path=path,
        ),
        child_pane=PaneState(
            directory_path=initial_state.current_path,
            entries=(),
            mode="preview",
            preview_path=path,
            preview_reason="unsupported",
            preview_metadata=PreviewMetadataState(
                display_name="data.bin",
                type_label="BIN",
                size_bytes=2048,
            ),
        ),
    )

    child = select_shell_data(state).child_pane

    assert child.metadata_bar == ()


def test_select_shell_data_hides_cursor_while_filtering() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFilterInput())

    shell = select_shell_data(state)

    assert shell.current_cursor_visible is False


def test_select_shell_data_keeps_cursor_visible_in_palette_mode() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())

    shell = select_shell_data(state)

    assert shell.current_cursor_visible is True


def test_select_shell_data_reuses_current_visible_entries(monkeypatch) -> None:
    state = build_initial_app_state()
    call_count = 0
    original = selectors_module.select_visible_current_entry_states

    def wrapped(local_state):
        nonlocal call_count
        call_count += 1
        return original(local_state)

    monkeypatch.setattr(selectors_module, "select_visible_current_entry_states", wrapped)

    shell = select_shell_data(state)

    assert call_count == 1
    assert shell.current_summary.item_count == len(shell.current_entries)


def test_select_shell_data_reuses_pane_entries_when_only_notification_changes() -> None:
    state = build_initial_app_state()

    initial_shell = select_shell_data(state)
    updated_shell = select_shell_data(
        _reduce_state(
            state,
            SetNotification(NotificationState(level="info", message="Ready")),
        )
    )

    assert updated_shell.parent_entries is initial_shell.parent_entries
    assert updated_shell.current_entries is initial_shell.current_entries
    assert updated_shell.child_pane is initial_shell.child_pane


def test_select_shell_data_reuses_current_entries_when_only_cursor_changes() -> None:
    state = build_initial_app_state(
        config=replace(
            build_initial_app_state().config,
            display=replace(build_initial_app_state().config.display, show_directory_sizes=False),
        ),
    )

    initial_shell = select_shell_data(state)
    moved_shell = select_shell_data(
        _reduce_state(
            state,
            SetCursorPath("/home/tadashi/develop/zivo/tests"),
        )
    )

    assert moved_shell.current_entries is initial_shell.current_entries
    assert moved_shell.current_cursor_index == 2
    assert moved_shell.child_pane.entries == ()


def test_select_shell_data_viewport_projection_limits_rendered_entries() -> None:
    path = "/tmp/zivo-viewport-selector"
    current_entries = tuple(
        entry(f"{path}/item_{index:02d}", name=f"item_{index:02d}")
        for index in range(12)
    )
    state = replace(
        build_initial_app_state(current_pane_projection_mode="viewport"),
        terminal_height=12,
        current_pane=pane(path, current_entries, cursor_path=current_entries[0].path),
    )

    shell = select_shell_data(state)

    visible_window = compute_current_pane_visible_window(state.terminal_height)
    assert len(shell.current_entries) == visible_window
    assert [entry.name for entry in shell.current_entries] == [
        f"item_{index:02d}" for index in range(visible_window)
    ]
    assert shell.current_cursor_index == 0
    assert shell.current_summary.item_count == len(current_entries)


def test_select_shell_data_viewport_projection_reuses_window_for_cursor_move_inside_window(
) -> None:
    path = "/tmp/zivo-viewport-selector"
    current_entries = tuple(
        entry(f"{path}/item_{index:02d}", name=f"item_{index:02d}")
        for index in range(12)
    )
    state = replace(
        build_initial_app_state(current_pane_projection_mode="viewport"),
        terminal_height=12,
        current_pane=pane(path, current_entries, cursor_path=current_entries[0].path),
    )

    initial_shell = select_shell_data(state)
    moved_shell = select_shell_data(_reduce_state(state, SetCursorPath(current_entries[3].path)))

    assert moved_shell.current_entries is initial_shell.current_entries
    assert moved_shell.current_cursor_index == 3


def test_select_shell_data_viewport_projection_shifts_window_after_cursor_crosses_edge() -> None:
    path = "/tmp/zivo-viewport-selector"
    current_entries = tuple(
        entry(f"{path}/item_{index:02d}", name=f"item_{index:02d}")
        for index in range(12)
    )
    state = replace(
        build_initial_app_state(current_pane_projection_mode="viewport"),
        terminal_height=12,
        current_pane=pane(path, current_entries, cursor_path=current_entries[0].path),
    )

    initial_shell = select_shell_data(state)
    moved_shell = select_shell_data(_reduce_state(state, SetCursorPath(current_entries[5].path)))

    assert moved_shell.current_entries is not initial_shell.current_entries
    assert [entry.name for entry in moved_shell.current_entries] == [
        "item_02",
        "item_03",
        "item_04",
        "item_05",
        "item_06",
    ]
    assert moved_shell.current_cursor_index == 3


def test_select_shell_data_viewport_projection_skips_offscreen_row_delta_updates() -> None:
    path = "/tmp/zivo-viewport-selector"
    current_entries = tuple(
        entry(f"{path}/item_{index:02d}", name=f"item_{index:02d}")
        for index in range(12)
    )
    offscreen_path = current_entries[-1].path
    state = replace(
        build_initial_app_state(current_pane_projection_mode="viewport"),
        terminal_height=12,
        current_pane=pane(path, current_entries, cursor_path=current_entries[0].path),
        current_pane_delta=CurrentPaneDeltaState(changed_paths=(offscreen_path,), revision=1),
    )

    shell = select_shell_data(
        replace(
            state,
            current_pane=replace(state.current_pane, selected_paths=frozenset({offscreen_path})),
        )
    )

    assert shell.current_entries is None
    assert shell.current_pane_update.mode == "row_delta"
    assert shell.current_pane_update.row_updates == ()


def test_select_shell_data_viewport_projection_skips_offscreen_size_delta_updates() -> None:
    path = "/tmp/zivo-viewport-selector"
    current_entries = tuple(
        entry(f"{path}/item_{index:02d}", name=f"item_{index:02d}", kind="dir")
        for index in range(12)
    )
    offscreen_path = current_entries[-1].path
    state = replace(
        build_initial_app_state(
            current_pane_projection_mode="viewport",
            config=AppConfig(
                display=replace(
                    AppConfig().display,
                    show_directory_sizes=True,
                )
            ),
        ),
        terminal_height=12,
        current_pane=pane(path, current_entries, cursor_path=current_entries[0].path),
        directory_size_cache=(
            DirectorySizeCacheEntry(
                offscreen_path,
                "ready",
                size_bytes=4_200,
            ),
        ),
        directory_size_delta=DirectorySizeDeltaState(changed_paths=(offscreen_path,), revision=2),
    )

    shell = select_shell_data(state)

    assert shell.current_entries is None
    assert shell.current_pane_update.mode == "size_delta"
    assert shell.current_pane_update.revision == 2
    assert shell.current_pane_update.size_updates == ()


def test_select_shell_data_rebuilds_only_current_entries_when_selection_changes() -> None:
    state = build_initial_app_state()

    initial_shell = select_shell_data(state)
    updated_shell = select_shell_data(
        _reduce_state(
            state,
            ToggleSelection("/home/tadashi/develop/zivo/README.md"),
        )
    )

    assert updated_shell.parent_entries is initial_shell.parent_entries
    assert updated_shell.child_pane is initial_shell.child_pane
    assert updated_shell.current_entries is not initial_shell.current_entries


def test_select_shell_data_includes_selected_cut_and_contextual_models() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        ToggleSelection("/home/tadashi/develop/zivo/README.md"),
    )
    state = _reduce_state(state, CutTargets(("/home/tadashi/develop/zivo/docs",)))
    state = replace(
        state,
        filter=replace(state.filter, query="read", active=True),
        current_pane_delta=CurrentPaneDeltaState(),
        notification=NotificationState(level="info", message="Ready"),
    )

    shell = select_shell_data(state)

    assert [entry.name for entry in shell.current_entries] == ["README.md"]
    assert shell.current_entries[0].selected is True
    assert shell.parent_entries[0].cut is False
    assert shell.current_context_input is not None
    assert shell.current_context_input.value == "read"
    assert shell.current_summary.sort_label == "name asc"
    assert shell.status.message == "Ready"


def test_select_current_summary_state_keeps_summary_format() -> None:
    state = build_initial_app_state()

    summary = select_current_summary_state(state)

    assert (
        f"{summary.item_count} items | {summary.selected_count} selected | "
        f"sort: {summary.sort_label}"
    ) == "5 items | 0 selected | sort: name asc"


def test_select_status_bar_exposes_notification_level() -> None:
    state = build_initial_app_state()
    state = _reduce_state(
        state,
        SetNotification(NotificationState(level="error", message="load failed")),
    )

    status = select_status_bar_state(state)

    assert status.message == "load failed"
    assert status.message_level == "error"


def test_select_status_bar_exposes_foreground_progress_and_cancel() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        foreground_operation=ForegroundOperationState(
            operation_id=3,
            kind="copy",
            completed=2,
            total=5,
            current_path="/tmp/very-long-operation-target.txt",
        ),
    )

    status = select_status_bar_state(state)
    help_state = select_help_bar_state(state)

    assert "Copy 2/5" in (status.message or "")
    assert status.action == StatusBarActionState(action_id="operation.cancel", label="Cancel")
    assert help_state.lines == ("Esc cancel",)


def test_select_status_bar_and_help_bar_keep_operation_visible_while_browsing() -> None:
    state = replace(
        build_initial_app_state(),
        foreground_operation=ForegroundOperationState(
            operation_id=3,
            kind="copy",
            completed=1,
            total=4,
            current_path="/tmp/current.txt",
        ),
    )

    status = select_status_bar_state(state)
    help_state = select_help_bar_state(state)

    assert "Copy 1/4" in (status.message or "")
    assert status.action == StatusBarActionState(action_id="operation.cancel", label="Cancel")
    assert help_state.lines[0].startswith("Esc cancel | ")
    assert len(help_state.lines) == 3


def test_select_help_bar_defaults_to_browsing_shortcuts() -> None:
    state = build_initial_app_state()

    help_state = select_help_bar_state(state)
    split_terminal_hint = " | t term" if os.name == "posix" else ""

    assert help_state.lines == (
        "enter open | e edit | / filter | s sort | . hidden | [ ] bk/fwd | q quit",
        "space select | c copy | x cut | v paste | d delete | r rename | z undo",
        f"f find | g grep | n new-file | N new-dir{split_terminal_hint} | : palette",
    )
    assert help_state.text == (
        "enter open | e edit | / filter | s sort | . hidden | [ ] bk/fwd | q quit\n"
        "space select | c copy | x cut | v paste | d delete | r rename | z undo\n"
        f"f find | g grep | n new-file | N new-dir{split_terminal_hint} | : palette"
    )


def test_select_help_bar_for_search_workspace_shows_available_actions_only() -> None:
    state = build_search_workspace_state()

    help_state = select_help_bar_state(state)

    assert help_state.lines == (
        "enter open | e edit | / filter | s sort | . hidden | "
        "[ ] bk/fwd | q quit",
        "space select | c copy | z undo",
        ": palette",
    )
    assert "x cut" not in help_state.text
    assert "d delete" not in help_state.text
    assert "f find" not in help_state.text


def test_select_help_bar_for_transfer_mode_prioritizes_transfer_actions() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())

    help_state = select_help_bar_state(state)

    assert help_state.lines == (
        "enter dir | . hidden | Tab switch-pane | p/Esc close | q quit",
        "space select | c copy-to-pane | m move-to-pane | d delete | r rename | z undo",
        "n new-file | N new-dir | : palette",
    )
    assert help_state.text == (
        "enter dir | . hidden | Tab switch-pane | p/Esc close | q quit\n"
        "space select | c copy-to-pane | m move-to-pane | d delete | r rename | z undo\n"
        "n new-file | N new-dir | : palette"
    )


def test_select_help_bar_for_busy_mode() -> None:
    state = replace(build_initial_app_state(), ui_mode="BUSY")

    help_state = select_help_bar_state(state)

    assert help_state.text == "processing..."


def test_select_help_bar_for_split_terminal_focus() -> None:
    state = replace(
        build_initial_app_state(),
        split_terminal=replace(
            build_initial_app_state().split_terminal,
            visible=True,
            status="running",
            focus_target="terminal",
        ),
    )

    help_state = select_help_bar_state(state)

    assert help_state.text == "type in terminal | ctrl+q close"


def test_select_command_palette_state_marks_selected_and_enabled_items() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())

    palette_state = select_command_palette_state(state)

    assert palette_state is not None
    assert palette_state.title.startswith("Command Palette")
    assert [item.category for item in palette_state.items[:3]] == [
        "Navigate",
        "Navigate",
        "Navigate",
    ]
    assert palette_state.items[0].selected is True
    assert palette_state.items[0].enabled is True
    assert any(item.label == "Go back" and not item.enabled for item in palette_state.items)
    assert any(item.label == "Go forward" and not item.enabled for item in palette_state.items)


def test_removed_direct_shortcuts_remain_available_without_palette_shortcuts() -> None:
    state = replace(build_initial_app_state(), command_palette=CommandPaletteState())
    items = {
        item.label: item
        for item in command_palette_module.get_command_palette_items(state)
    }

    labels = {
        "Show attributes",
        "Copy path",
        "Bookmark this directory",
        "Go to path",
        "Open current directory with file manager",
        "Edit with GUI editor",
        "Open current directory with terminal",
        "History search",
        "Reload directory",
    }

    assert labels <= items.keys()
    assert all(items[label].shortcut is None for label in labels)


def test_command_palette_exposes_one_dynamic_narrow_view_command() -> None:
    state = replace(
        build_initial_app_state(),
        terminal_width=72,
        command_palette=CommandPaletteState(),
    )

    items = command_palette_module.get_command_palette_items(state)
    narrow_items = [item for item in items if item.id == "toggle_narrow_pane_view"]

    assert len(narrow_items) == 1
    assert narrow_items[0].label == "Show preview or contents"
    assert narrow_items[0].shortcut == "tab"
    assert narrow_items[0].enabled is True

    details = replace(state, narrow_pane_view="details")
    details_item = next(
        item
        for item in command_palette_module.get_command_palette_items(details)
        if item.id == "toggle_narrow_pane_view"
    )
    assert details_item.label == "Back to file list"


def test_command_palette_items_for_search_workspace_explain_unavailable_actions() -> None:
    state = replace(
        build_search_workspace_state(),
        config=AppConfig(
            bookmarks=BookmarkConfig(paths=(SEARCH_WORKSPACE_PATH,)),
            actions=ActionsConfig(
                custom=(CustomActionConfig(name="Format project", command=("format",)),)
            ),
        ),
        command_palette=CommandPaletteState(),
    )

    items = {
        item.label: item for item in command_palette_module.get_command_palette_items(state)
    }
    labels = list(items)

    assert "History search" in labels
    assert "Show bookmarks" in labels
    assert "Go back" in labels
    assert "Go forward" in labels
    assert "Go to path" in labels
    assert "Go to home directory" in labels
    assert "Undo last file operation" in labels
    assert "New tab" in labels
    assert "Next tab" in labels
    assert "Previous tab" in labels
    assert "Close current tab" in labels
    assert "Exit" in labels
    assert "Select all" in labels
    assert "Show attributes" in labels
    assert "Edit with terminal editor" in labels
    assert "Edit with GUI editor" in labels
    assert "Copy path" in labels
    assert "Show hidden files" in labels
    assert "About zivo" in labels
    assert "Edit config" in labels

    assert "Find files" in labels
    assert "Grep search" in labels
    assert "Reload directory" in labels
    assert "Toggle transfer mode" in labels
    assert "Format project" in labels
    assert items["Format project"].enabled is False
    assert items["Format project"].disabled_reason == "Unavailable in Search Workspace"
    for label in (
        "Rename",
        "Change permissions",
        "Change owner",
        "Make symlink",
        "Compress as zip",
        "Extract archive",
        "Move to trash",
        "Open current directory with file manager",
        "Open current directory with terminal",
        "Run shell command",
        "Create file",
        "Create directory",
    ):
        assert items[label].enabled is False
        assert items[label].disabled_reason == "Unavailable in Search Workspace"


def test_command_palette_distinguishes_file_and_current_directory_launchers() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())

    items = {item.id: item for item in command_palette_module.get_command_palette_items(state)}

    assert items["open"].label == "Open"
    assert items["open"].enabled is False
    assert items["edit_with_terminal_editor"].enabled is False
    assert items["edit_with_gui_editor"].enabled is False
    assert items["open_current_directory_with_file_manager"].enabled is True
    assert items["open_current_directory_with_terminal"].enabled is True
    assert "open_current_directory_in_gui_editor" not in items


def test_select_command_palette_state_shows_single_target_commands_when_filtered() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = replace(
        state,
        command_palette=replace(state.command_palette, query="rename"),
    )

    palette_state = select_command_palette_state(state)

    assert palette_state is not None
    assert [item.label for item in palette_state.items] == ["Rename"]
    assert palette_state.items[0].enabled is True


def test_select_command_palette_state_shows_chmod_for_single_target() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = replace(
        state,
        command_palette=replace(state.command_palette, query="permissions"),
    )

    palette_state = select_command_palette_state(state)

    assert palette_state is not None
    assert [item.label for item in palette_state.items] == [
        "Change permissions",
        "Change permissions recursively",
    ]
    assert palette_state.items[0].enabled is True
    assert palette_state.items[1].enabled is True


def test_select_command_palette_state_shows_chown_for_single_target() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = replace(
        state,
        command_palette=replace(state.command_palette, query="owner"),
    )

    palette_state = select_command_palette_state(state)

    assert palette_state is not None
    assert [item.label for item in palette_state.items] == [
        "Change owner",
        "Change owner recursively",
    ]
    assert palette_state.items[0].enabled is True
    assert palette_state.items[1].enabled is True


def test_select_command_palette_state_shows_chmod_for_selection() -> None:
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
    state = replace(
        state,
        command_palette=replace(state.command_palette, query="permissions"),
    )

    palette_state = select_command_palette_state(state)

    assert palette_state is not None
    assert [item.label for item in palette_state.items] == [
        "Change permissions",
        "Change permissions recursively",
    ]
    assert palette_state.items[0].enabled is True
    assert palette_state.items[1].enabled is True


def test_select_command_palette_state_shows_chown_for_selection() -> None:
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
    state = replace(
        state,
        command_palette=replace(state.command_palette, query="owner"),
    )

    palette_state = select_command_palette_state(state)

    assert palette_state is not None
    assert [item.label for item in palette_state.items] == [
        "Change owner",
        "Change owner recursively",
    ]
    assert palette_state.items[0].enabled is True
    assert palette_state.items[1].enabled is True


def test_command_palette_hides_chmod_on_windows(monkeypatch) -> None:
    monkeypatch.setattr(command_palette_module.platform, "system", lambda: "Windows")
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())

    labels = [
        item.label
        for item in command_palette_module.get_command_palette_items(state)
    ]

    assert "Change permissions" not in labels
    assert "Change permissions recursively" not in labels
    assert "Change owner" not in labels
    assert "Change owner recursively" not in labels


def test_select_command_palette_state_enables_history_navigation_items() -> None:
    state = replace(
        _reduce_state(build_initial_app_state(), BeginCommandPalette()),
        history=HistoryState(
            back=("/tmp/a",),
            forward=("/tmp/b",),
        ),
    )

    palette_state = select_command_palette_state(state)

    assert palette_state is not None
    assert any(item.label == "Go back" and item.enabled for item in palette_state.items)
    assert any(item.label == "Go forward" and item.enabled for item in palette_state.items)


def test_select_command_palette_state_in_transfer_mode_shows_transfer_commands_only() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())
    state = _reduce_state(state, BeginCommandPalette())

    palette_state = select_command_palette_state(state)

    assert palette_state is not None
    labels = [item.label for item in palette_state.items]
    assert "History search" in labels
    assert "Copy to opposite pane" in labels
    assert "Move to opposite pane" in labels
    assert "Close transfer mode" in labels
    assert "Find files" not in labels
    assert "Toggle split terminal" not in labels


def test_select_command_palette_state_shows_bookmark_items() -> None:
    state = build_initial_app_state(
        config=AppConfig(
            bookmarks=BookmarkConfig(
                paths=(
                    "/home/tadashi/src",
                    "/home/tadashi/docs",
                )
            )
        )
    )
    state = replace(
        _reduce_state(state, BeginCommandPalette()),
        command_palette=CommandPaletteState(source="bookmarks", query="docs"),
    )

    palette_state = select_command_palette_state(state)

    assert palette_state is not None
    assert palette_state.title == "Bookmarks"
    assert [item.label for item in palette_state.items] == [
        _display_path_for_test("/home/tadashi/docs")
    ]
    assert palette_state.empty_message == "No bookmarks"


def test_select_command_palette_state_shows_go_to_path_candidates() -> None:
    state = replace(
        _reduce_state(build_initial_app_state(), BeginCommandPalette()),
        command_palette=CommandPaletteState(
            source="go_to_path",
            query="do",
            cursor_index=1,
            history_and_navigation=HistoryAndNavigationPaletteState(
                go_to_path_candidates=(
                    "/home/tadashi/docs",
                    "/home/tadashi/downloads",
                ),
            ),
        ),
    )

    palette_state = select_command_palette_state(state)

    assert palette_state is not None
    assert palette_state.title == "Go to path"
    assert [item.label for item in palette_state.items] == [
        _display_path_for_test("/home/tadashi/docs"),
        _display_path_for_test("/home/tadashi/downloads"),
    ]
    assert palette_state.items[1].selected is True
    assert palette_state.empty_message == "No matching directories"


def test_select_help_bar_state_for_go_to_path_palette_mentions_tab_completion() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(source="go_to_path"),
    )

    help_bar = select_help_bar_state(state)

    assert help_bar.lines == (
        "type path | ↑↓ or Ctrl+j/k select | tab complete | enter jump | esc cancel",
    )


def test_select_help_bar_state_for_history_palette() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(source="history"),
    )

    help_bar = select_help_bar_state(state)

    assert help_bar.lines == (
        "type path | ↑↓ or Ctrl+j/k select | enter jump | esc cancel",
    )


def test_select_help_bar_state_for_bookmarks_palette() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(source="bookmarks"),
    )

    help_bar = select_help_bar_state(state)

    assert help_bar.lines == (
        "type path | ↑↓ or Ctrl+j/k select | enter jump | esc cancel",
    )


def test_select_help_bar_state_for_file_search_palette() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(source="file_search"),
    )

    help_bar = select_help_bar_state(state)

    assert help_bar.lines == (
        "type filename | ↑↓ or Ctrl+j/k select | enter jump | "
        "Ctrl+w workspace | Ctrl+e edit | Ctrl+o GUI | esc cancel",
    )


def test_select_help_bar_state_for_grep_search_palette() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(source="grep_search"),
    )

    help_bar = select_help_bar_state(state)

    assert help_bar.lines == (
        "type text / tab fields / ↑↓ or Ctrl+j/k select | "
        "enter jump | Ctrl+e edit | Ctrl+o GUI | "
        "Ctrl+x export | esc cancel",
    )


def test_select_help_bar_state_for_command_palette() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(),
    )

    help_bar = select_help_bar_state(state)

    assert help_bar.lines == (
        "type command | ↑↓ or Ctrl+j/k select | enter run | esc cancel",
    )


def test_select_help_bar_state_for_config_editor() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
        ),
    )

    help_bar = select_help_bar_state(state)

    assert help_bar.lines == (
        "↑↓ or Ctrl+j/k choose | ←→ or Enter change | s save | e advanced config",
        "esc close",
    )


def test_select_command_palette_state_for_grep_search_includes_input_fields() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="grep_search",
            query="todo",
            grep_search=GrepSearchPaletteState(
                keyword="todo",
                filename_filter="main",
                include_extensions="py,ts",
                exclude_extensions="log",
                active_field="exclude",
            ),
        ),
    )

    palette_state = select_command_palette_state(state)

    assert palette_state is not None
    assert [field.label for field in palette_state.input_fields] == [
        "Keyword",
        "Scope",
        "Filter: Filename",
        "Include extensions",
        "Exclude extensions",
    ]
    assert [field.value for field in palette_state.input_fields] == [
        "todo", "current directory", "main", "py,ts", "log"
    ]
    assert [field.active for field in palette_state.input_fields] == [
        False,
        False,
        False,
        False,
        True,
    ]


def test_select_command_palette_state_for_text_replace_includes_input_fields() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="replace_text",
            replace_preview=ReplacePreviewPaletteState(
                find_text="todo",
                replacement_text="done",
                active_field="replace",
                preview_results=(
                    ReplacePreviewResultState(
                        path="/home/tadashi/develop/zivo/README.md",
                        display_path="README.md",
                        diff_text="--- before\n+++ after\n@@\n-todo item\n+done item\n",
                        match_count=2,
                        first_match_line_number=8,
                        first_match_before="todo item",
                        first_match_after="done item",
                    ),
                ),
                total_match_count=2,
                target_paths=("/home/tadashi/develop/zivo/README.md",),
            ),
        ),
    )

    palette_state = select_command_palette_state(state)

    assert palette_state is not None
    assert palette_state.title == "Replace Text (1 file(s), 2 match(es)) (1-1 / 1)"
    assert [field.label for field in palette_state.input_fields] == [
        "Scope",
        "Find",
        "Replace",
        "Filter: Filename",
        "Include extensions",
        "Exclude extensions",
    ]
    assert [field.value for field in palette_state.input_fields] == [
        "Current directory",
        "todo",
        "done",
        "",
        "",
        "",
    ]
    assert [field.active for field in palette_state.input_fields] == [
        False,
        False,
        True,
        False,
        False,
        False,
    ]
    assert [item.label for item in palette_state.items] == [
        "README.md (2): 8: todo item"
    ]
    assert palette_state.empty_message == "Preview shown in right pane. Press Enter to apply."


def test_select_command_palette_state_go_to_path_can_show_candidates_without_selection() -> None:
    state = replace(
        _reduce_state(build_initial_app_state(), BeginCommandPalette()),
        command_palette=CommandPaletteState(
            source="go_to_path",
            query="docs/",
            history_and_navigation=HistoryAndNavigationPaletteState(
                go_to_path_candidates=(
                    "/home/tadashi/docs/api",
                    "/home/tadashi/docs/guides",
                ),
                go_to_path_selection_active=False,
            ),
        ),
    )

    palette_state = select_command_palette_state(state)

    assert palette_state is not None
    assert [item.selected for item in palette_state.items] == [False, False]


def test_select_command_palette_state_filters_query() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = replace(
        state,
            command_palette=replace(state.command_palette, query="create"),
    )

    palette_state = select_command_palette_state(state)

    assert palette_state is not None
    assert [item.label for item in palette_state.items] == ["Create"]


def test_select_command_palette_state_uses_hidden_toggle_label_from_state() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = replace(
        state,
        command_palette=replace(state.command_palette, query="hidden"),
    )

    palette_state = select_command_palette_state(state)

    assert palette_state is not None
    assert [item.label for item in palette_state.items] == ["Show hidden files"]
    assert palette_state.items[0].shortcut == "."

    visible_state = replace(state, show_hidden=True)
    visible_palette_state = select_command_palette_state(visible_state)

    assert visible_palette_state is not None
    assert [item.label for item in visible_palette_state.items] == ["Hide hidden files"]
    assert visible_palette_state.items[0].shortcut == "."


def test_select_command_palette_state_switches_bookmark_command_label() -> None:
    state = build_initial_app_state()
    palette_state = select_command_palette_state(
        replace(
            _reduce_state(state, BeginCommandPalette()),
            command_palette=replace(CommandPaletteState(), query="bookmark"),
        )
    )

    assert palette_state is not None
    assert any(item.label == "Bookmark this directory" for item in palette_state.items)
    assert any(
        item.label == "Bookmark this directory" and item.shortcut is None
        for item in palette_state.items
    )

    bookmarked_state = build_initial_app_state(
        config=AppConfig(
            bookmarks=BookmarkConfig(
                paths=("/home/tadashi/develop/zivo",)
            )
        )
    )
    bookmarked_palette_state = select_command_palette_state(
        replace(
            _reduce_state(bookmarked_state, BeginCommandPalette()),
            command_palette=replace(CommandPaletteState(), query="bookmark"),
        )
    )

    assert bookmarked_palette_state is not None
    assert any(item.label == "Remove bookmark" for item in bookmarked_palette_state.items)
    assert any(
        item.label == "Remove bookmark" and item.shortcut is None
        for item in bookmarked_palette_state.items
    )


def test_select_command_palette_state_disables_select_all_without_visible_entries() -> None:
    state = replace(
        build_initial_app_state(),
        current_pane=PaneState(
            directory_path="/home/tadashi/develop/zivo",
            entries=(
                DirectoryEntryState(
                    "/home/tadashi/develop/zivo/.env",
                    ".env",
                    "file",
                    hidden=True,
                ),
            ),
            cursor_path=None,
        ),
    )
    palette_state = select_command_palette_state(
        replace(
            _reduce_state(state, BeginCommandPalette()),
            command_palette=replace(CommandPaletteState(), query="select all"),
        )
    )

    assert palette_state is not None
    assert [item.label for item in palette_state.items] == ["Select all"]
    assert palette_state.items[0].enabled is False


def test_select_command_palette_state_enables_select_all_with_visible_entries() -> None:
    state = select_command_palette_state(
        replace(
            _reduce_state(build_initial_app_state(), BeginCommandPalette()),
            command_palette=replace(CommandPaletteState(), query="select all"),
        )
    )

    assert state is not None
    assert [item.label for item in state.items] == ["Select all"]
    assert state.items[0].enabled is True
    assert state.items[0].shortcut == "a"


def test_select_command_palette_state_shows_extract_archive_for_supported_file() -> None:
    archive_path = "/home/tadashi/develop/zivo/archive.tar.gz"
    state = replace(
        build_initial_app_state(),
        current_pane=PaneState(
            directory_path="/home/tadashi/develop/zivo",
            entries=(
                DirectoryEntryState(archive_path, "archive.tar.gz", "file"),
            ),
            cursor_path=archive_path,
        ),
    )
    palette_state = select_command_palette_state(
        replace(
            _reduce_state(state, BeginCommandPalette()),
            command_palette=replace(CommandPaletteState(), query="extract"),
        )
    )

    assert palette_state is not None
    assert [item.label for item in palette_state.items] == ["Extract archive"]


def test_select_command_palette_state_shows_single_target_shortcuts() -> None:
    state = select_command_palette_state(
        replace(
            _reduce_state(build_initial_app_state(), BeginCommandPalette()),
            command_palette=replace(CommandPaletteState(), query="attributes"),
        )
    )

    assert state is not None
    assert [item.label for item in state.items] == ["Show attributes"]
    assert [item.shortcut for item in state.items] == [None]


def test_select_command_palette_state_shows_copy_path_shortcut() -> None:
    state = select_command_palette_state(
        replace(
            _reduce_state(build_initial_app_state(), BeginCommandPalette()),
            command_palette=replace(CommandPaletteState(), query="copy path"),
        )
    )

    assert state is not None
    assert [item.label for item in state.items] == ["Copy path"]
    assert state.items[0].shortcut is None


def test_select_command_palette_state_shows_compress_as_zip_for_multiple_targets() -> None:
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
    palette_state = select_command_palette_state(
        replace(
            _reduce_state(state, BeginCommandPalette()),
            command_palette=replace(CommandPaletteState(), query="compress"),
        )
    )

    assert palette_state is not None
    assert [item.label for item in palette_state.items] == ["Compress as zip"]


def test_select_command_palette_state_shows_replace_text_for_selected_files() -> None:
    state = replace(
        build_initial_app_state(),
        current_pane=PaneState(
            directory_path="/home/tadashi/develop/zivo",
            entries=(
                DirectoryEntryState("/home/tadashi/develop/zivo/README.md", "README.md", "file"),
                DirectoryEntryState("/home/tadashi/develop/zivo/src", "src", "dir"),
            ),
            cursor_path="/home/tadashi/develop/zivo/README.md",
            selected_paths=frozenset({"/home/tadashi/develop/zivo/README.md"}),
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


def test_select_command_palette_state_shows_replace_text_for_cursor_file() -> None:
    state = replace(
        build_initial_app_state(),
        current_pane=replace(
            build_initial_app_state().current_pane,
            cursor_path="/home/tadashi/develop/zivo/README.md",
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


def test_select_input_bar_state_formats_extract_mode() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="EXTRACT",
        pending_input=PendingInputState(
            prompt="Extract to: ",
            value="/tmp/output/archive",
            extract_source_path="/home/tadashi/develop/zivo/archive.zip",
        ),
    )

    input_state = select_input_dialog_state(state)

    assert input_state is not None
    assert input_state.title == "Extract"
    assert input_state.prompt == "Extract to: "
    assert input_state.hint == "enter apply | esc cancel"


def test_select_input_bar_state_formats_zip_mode() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="ZIP",
        pending_input=PendingInputState(
            prompt="Compress to: ",
            value="/tmp/output.zip",
            zip_source_paths=("/home/tadashi/develop/zivo/docs",),
        ),
    )

    input_state = select_input_dialog_state(state)

    assert input_state is not None
    assert input_state.title == "Compress"
    assert input_state.prompt == "Compress to: "
    assert input_state.hint == "enter apply | esc cancel"


def test_select_attribute_dialog_state_formats_selected_entry() -> None:
    state = replace(
        build_initial_app_state(),
        attribute_inspection=AttributeInspectionState(
            name="README.md",
            kind="file",
            path="/home/tadashi/develop/zivo/README.md",
            size_bytes=2_150,
            modified_at=build_initial_app_state().current_pane.entries[3].modified_at,
            hidden=False,
            permissions_mode=S_IFREG | 0o644,
        ),
    )

    dialog = select_attribute_dialog_state(state)

    assert dialog is not None
    assert dialog.title == "Attributes: README.md"
    assert "Name: README.md" in dialog.lines
    assert "Type: File" in dialog.lines
    assert "Symlink: No" in dialog.lines
    assert "Path: /home/tadashi/develop/zivo/README.md" in dialog.lines
    assert "Size: 2.1KiB" in dialog.lines
    assert "Hidden: No" in dialog.lines
    assert "Permissions: -rw-r--r-- (644)" in dialog.lines
    assert dialog.options == ("enter close", "esc close")


def test_select_config_dialog_state_formats_editor_lines() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
            cursor_index=3,
            dirty=True,
        ),
    )

    dialog = select_config_dialog_state(state)

    assert dialog is not None
    assert dialog.title == "Config Editor (Basic Settings)*"
    assert "Path: /tmp/zivo/config.toml" in dialog.lines
    assert "  ── Editors ──" in dialog.lines
    assert "  Editor command: system default" in dialog.lines
    assert "  GUI editor: VS Code" in dialog.lines
    assert "  ── Appearance ──" in dialog.lines
    assert "> Theme: textual-dark" in dialog.lines
    assert "  Text preview: true" in dialog.lines
    assert "  Image preview: true" in dialog.lines
    assert "  Preview syntax theme: auto" in dialog.lines
    assert "  ── Sorting ──" in dialog.lines
    assert "  Default sort field: name" in dialog.lines
    assert "  ── Selected Setting ──" in dialog.lines
    assert "  Theme" in dialog.lines
    assert "  Sets the application theme used by the panes, dialogs, and status UI." in dialog.lines
    assert "  Changing this here previews the theme immediately before saving." in dialog.lines
    assert "  Current behavior: `textual-dark`." in dialog.lines
    hint = "Editor presets: system default, nvim, vim, nano, hx, micro, emacs -nw, edit"
    assert hint in dialog.lines
    assert (
        "GUI editor presets: VS Code, VSCodium, Cursor, Sublime Text, Zed, "
        "JetBrains IDEA, PyCharm, WebStorm, Kate"
    ) in dialog.lines
    assert "  ── Advanced Settings ──" in dialog.lines
    assert "  Edit config.toml with e for advanced, custom, and future settings." in dialog.lines
    assert "  Saving here preserves settings that are not shown above." in dialog.lines
    assert dialog.options == (
        "↑↓/Ctrl+j/k choose",
        "←→/enter change",
        "s save",
        "e advanced config",
        "esc close",
    )


def test_select_child_syntax_theme_tracks_builtin_theme_brightness() -> None:
    assert selectors_module._select_child_syntax_theme("solarized-light", "auto") == "friendly"
    assert selectors_module._select_child_syntax_theme("dracula", "auto") == "monokai"


def test_select_child_syntax_theme_prefers_explicit_preview_style() -> None:
    assert selectors_module._select_child_syntax_theme("solarized-light", "xcode") == "xcode"
    assert selectors_module._select_child_syntax_theme("dracula", "one-dark") == "one-dark"


def test_select_config_dialog_state_shows_custom_editor_command_hint() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=AppConfig(editor=EditorConfig(command="nvim -u NONE")),
        ),
    )

    dialog = select_config_dialog_state(state)

    assert dialog is not None
    assert "> Editor command: custom (raw config only)" in dialog.lines
    assert "Custom editor command: nvim -u NONE" in dialog.lines
    assert (
        "  Current behavior: custom raw command `nvim -u NONE` is preserved."
        in dialog.lines
    )
    assert "  Custom commands can only be edited in the raw config file with `e`." in dialog.lines

def test_select_config_dialog_state_shows_custom_gui_editor_hint() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=AppConfig(
                gui_editor=GuiEditorConfig(
                    command="my-editor --line {line} {path}",
                    fallback_command="my-editor {path}",
                ),
            ),
            cursor_index=1,
        ),
    )

    dialog = select_config_dialog_state(state)

    assert dialog is not None
    assert "> GUI editor: custom (raw config only)" in dialog.lines
    assert "  Current behavior: custom raw GUI editor templates are preserved." in dialog.lines
    assert (
        "  Custom GUI editor templates can only be edited in the raw config file with `e`."
        in dialog.lines
    )


def test_select_config_dialog_state_formats_directories_first_detail() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=AppConfig(display=DisplayConfig(directories_first=False)),
            cursor_index=15,
        ),
    )

    dialog = select_config_dialog_state(state)

    assert dialog is not None
    assert "> Directories first: false" in dialog.lines
    assert (
        "  Controls whether directories stay grouped before files in sorted lists."
        in dialog.lines
    )
    assert "  Current behavior: directories are mixed into the main sort order." in dialog.lines


def test_select_command_palette_state_for_file_search_results() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = replace(
        state,
        command_palette=CommandPaletteState(
            source="file_search",
            query="read",
            file_search=FileSearchPaletteState(
                results=(
                    FileSearchResultState(
                        path="/home/tadashi/develop/zivo/README.md",
                        display_path="README.md",
                    ),
                ),
            ),
        ),
    )

    palette_state = select_command_palette_state(state)

    assert palette_state is not None
    assert palette_state.title == "Find All (1-1 / 1)"
    assert palette_state.empty_message == "No matching files"
    assert [item.label for item in palette_state.items] == ["README.md"]


def test_select_command_palette_state_shows_searching_message_while_file_search_is_pending(
) -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = replace(
        state,
        command_palette=CommandPaletteState(
            source="file_search",
            query=".py",
            file_search=FileSearchPaletteState(),
        ),
        pending_file_search_request_id=7,
    )

    palette_state = select_command_palette_state(state)

    assert palette_state is not None
    assert palette_state.title == "Find All"
    assert palette_state.empty_message == "Searching files..."
    assert palette_state.items == ()


def test_select_command_palette_state_shows_regex_error_message() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = replace(
        state,
        command_palette=CommandPaletteState(
            source="file_search",
            query="re:[",
            file_search=FileSearchPaletteState(
                error_message="Invalid regex: unterminated character set",
            ),
        ),
    )

    palette_state = select_command_palette_state(state)

    assert palette_state is not None
    assert palette_state.title == "Find All"
    assert palette_state.empty_message == "Invalid regex: unterminated character set"
    assert palette_state.items == ()


def test_select_command_palette_state_windows_large_file_search_results() -> None:
    results = tuple(
        FileSearchResultState(
            path=f"/home/tadashi/develop/zivo/src/module_{index}.py",
            display_path=f"src/module_{index}.py",
        )
        for index in range(20)
    )
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = replace(
        state,
        command_palette=CommandPaletteState(
            source="file_search",
            query=".py",
            cursor_index=10,
            file_search=FileSearchPaletteState(results=results),
        ),
    )

    palette_state = select_command_palette_state(state)

    assert palette_state is not None
    assert palette_state.title == "Find All (5-17 / 20)"
    assert [item.label for item in palette_state.items] == [
        "src/module_4.py",
        "src/module_5.py",
        "src/module_6.py",
        "src/module_7.py",
        "src/module_8.py",
        "src/module_9.py",
        "src/module_10.py",
        "src/module_11.py",
        "src/module_12.py",
        "src/module_13.py",
        "src/module_14.py",
        "src/module_15.py",
        "src/module_16.py",
    ]
    assert palette_state.items[6].selected is True
    assert palette_state.has_more_items is True


def test_select_command_palette_state_for_grep_search_results() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = replace(
        state,
        command_palette=CommandPaletteState(
            source="grep_search",
            query="todo",
            grep_search=GrepSearchPaletteState(
                results=(
                    GrepSearchResultState(
                        path="/home/tadashi/develop/zivo/src/zivo/app.py",
                        display_path="src/zivo/app.py",
                        line_number=42,
                        line_text="TODO: update palette",
                    ),
                ),
            ),
        ),
    )

    palette_state = select_command_palette_state(state)

    assert palette_state is not None
    assert palette_state.title == "Grep (1-1 / 1)"
    assert [item.label for item in palette_state.items] == [
        "src/zivo/app.py:42: TODO: update palette"
    ]


def test_select_command_palette_state_windows_large_grep_search_results() -> None:
    results = tuple(
        GrepSearchResultState(
            path=f"/home/tadashi/develop/zivo/src/module_{index}.py",
            display_path=f"src/module_{index}.py",
            line_number=index + 1,
            line_text="TODO: update palette",
        )
        for index in range(20)
    )
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = replace(
        state,
        command_palette=CommandPaletteState(
            source="grep_search",
            query="todo",
            cursor_index=10,
            grep_search=GrepSearchPaletteState(results=results),
        ),
    )

    palette_state = select_command_palette_state(state)

    assert palette_state is not None
    assert palette_state.title == "Grep (6-16 / 20)"
    assert len(palette_state.items) == 11
    assert palette_state.items[5].selected is True
    assert palette_state.has_more_items is True


def test_select_command_palette_state_shows_grep_searching_message() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = replace(
        state,
        command_palette=CommandPaletteState(
            source="grep_search",
            query="todo",
            grep_search=GrepSearchPaletteState(results=()),
        ),
        pending_grep_search_request_id=9,
    )

    palette_state = select_command_palette_state(state)

    assert palette_state is not None
    assert palette_state.title == "Grep"
    assert palette_state.empty_message == "Searching matches..."


def test_select_input_bar_state_for_create_mode() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCreateInput("file"))
    state = replace(
        state,
        pending_input=PendingInputState(
            prompt="Name or path: ", value="notes.txt", create_kind="file"
        ),
    )

    input_dialog = select_input_dialog_state(state)

    assert input_dialog is not None
    assert input_dialog.title == "Create"
    assert input_dialog.prompt == "Name or path: "
    assert input_dialog.value == "notes.txt"
    assert input_dialog.hint == "tab switch type | enter apply | esc cancel"


def test_select_input_dialog_state_shows_recursive_safety_details() -> None:
    state = build_initial_app_state()
    target = state.current_pane.entries[0]
    state = replace(
        state,
        ui_mode="CHMOD",
        pending_input=PendingInputState(
            prompt="Permissions: ",
            value="755",
            chmod_target_paths=(target.path,),
        ),
    )

    input_dialog = select_input_dialog_state(state)

    assert input_dialog is not None
    assert input_dialog.title == "Change Permissions"
    assert input_dialog.hint == "tab toggle recursive | enter apply | esc cancel"
    assert input_dialog.details == (
        "Targets: 1 (1 directory)",
        "Recursive: No",
        "Symlinks are skipped and never followed.",
    )


def test_select_input_bar_state_for_symlink_mode() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="SYMLINK",
        pending_input=PendingInputState(
            prompt="Create link at: ",
            value="/tmp/docs.link",
            cursor_pos=14,
            symlink_source_path="/tmp/docs",
        ),
    )

    input_dialog = select_input_dialog_state(state)

    assert input_dialog is not None
    assert input_dialog.title == "Create Symlink"
    assert input_dialog.prompt == "Create link at: "
    assert input_dialog.hint == "tab complete | enter apply | esc cancel"


def test_select_input_bar_state_for_filter_mode() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFilterInput())
    state = _reduce_state(state, SetFilterQuery("spec"))

    input_bar = select_input_bar_state(state)

    assert input_bar is not None
    assert input_bar.mode_label == "FILTER"
    assert input_bar.prompt == "Filter: "
    assert input_bar.value == "spec"
    assert input_bar.hint == "enter/down apply | esc clear"


def test_select_input_bar_state_keeps_active_filter_visible_after_confirm() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFilterInput())
    state = _reduce_state(state, SetFilterQuery("spec"))
    state = _reduce_state(state, ConfirmFilterInput())

    input_bar = select_input_bar_state(state)

    assert input_bar is not None
    assert input_bar.mode_label == "FILTER"
    assert input_bar.prompt == "Filter: "
    assert input_bar.value == "spec"
    assert input_bar.hint == "esc clear"


def test_select_input_bar_state_for_pending_key_sequence() -> None:
    state = replace(
        build_initial_app_state(),
        pending_key_sequence=PendingKeySequenceState(
            keys=("y",),
            possible_next_keys=("y",),
        ),
        filter=replace(build_initial_app_state().filter, query="spec", active=True),
    )

    input_bar = select_input_bar_state(state)

    assert input_bar is not None
    assert input_bar.mode_label == "KEYS"
    assert input_bar.prompt == "Prefix: "
    assert input_bar.value == "y"
    assert input_bar.hint == "await y | esc cancel"


def test_select_help_bar_state_for_filter_mode() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFilterInput())

    help_state = select_help_bar_state(state)

    assert help_state.text == "type filter | enter/down apply | esc clear"


def test_select_conflict_dialog_state_formats_first_conflict() -> None:
    conflict = PasteConflict(
        source_path="/home/tadashi/develop/zivo/docs",
        destination_path="/home/tadashi/develop/zivo/docs",
    )
    state = replace(
        build_initial_app_state(),
        paste_conflict=PasteConflictState(
            request=PasteRequest(
                mode="copy",
                source_paths=("/home/tadashi/develop/zivo/docs",),
                destination_dir="/home/tadashi/develop/zivo",
            ),
            conflicts=(conflict,),
            first_conflict=conflict,
        ),
    )

    dialog = select_conflict_dialog_state(state)

    assert dialog is not None
    assert dialog.title == "Paste Conflict"
    assert "o overwrite" in dialog.options


def test_select_conflict_dialog_state_formats_delete_confirmation() -> None:
    state = replace(
        build_initial_app_state(),
        delete_confirmation=DeleteConfirmationState(
            paths=(
                "/home/tadashi/develop/zivo/docs",
                "/home/tadashi/develop/zivo/src",
            )
        ),
    )

    dialog = select_conflict_dialog_state(state)

    assert dialog is not None
    assert dialog.title == "Delete Confirmation"
    assert dialog.options == ("enter confirm", "esc cancel")


def test_select_conflict_dialog_state_formats_permanent_delete_confirmation() -> None:
    state = replace(
        build_initial_app_state(),
        delete_confirmation=DeleteConfirmationState(
            paths=("/home/tadashi/develop/zivo/docs",),
            mode="permanent",
            total_size_bytes=2048,
        ),
    )

    dialog = select_conflict_dialog_state(state)

    assert dialog is not None
    assert dialog.title == "Permanent Delete Confirmation"
    assert "This cannot be undone" in dialog.message
    assert "2.0KiB" in dialog.message
    assert "docs" in dialog.message
    assert dialog.options == ("enter confirm", "esc cancel")


def test_select_conflict_dialog_state_formats_additional_permanent_delete_confirmation(
) -> None:
    state = replace(
        build_initial_app_state(),
        delete_confirmation=DeleteConfirmationState(
            paths=("/tmp/docs", "/tmp/src", "/tmp/tests", "/tmp/README.md"),
            mode="permanent",
            total_size_bytes=4096,
            contains_directory=True,
            additional_confirmation_armed=True,
        ),
    )

    dialog = select_conflict_dialog_state(state)

    assert dialog is not None
    assert dialog.title == "Final Permanent Delete Confirmation"
    assert "4 items" in dialog.message
    assert "4.0KiB" in dialog.message
    assert "docs, src, tests, and 1 more" in dialog.message
    assert dialog.options == ("D permanently delete", "esc cancel")


def test_select_conflict_dialog_state_formats_extract_confirmation() -> None:
    state = replace(
        build_initial_app_state(),
        archive_extract_confirmation=ArchiveExtractConfirmationState(
            request=ExtractArchiveRequest(
                source_path="/home/tadashi/develop/zivo/archive.zip",
                destination_path="/tmp/output/archive",
            ),
            conflict_count=2,
            first_conflict_path="/tmp/output/archive/notes.txt",
            total_entries=5,
        ),
    )

    dialog = select_conflict_dialog_state(state)

    assert dialog is not None
    assert dialog.title == "Extract Archive Confirmation"
    assert "2 archive path(s) already exist" in dialog.message
    assert dialog.options == ("enter continue", "esc return to input")


def test_select_conflict_dialog_state_formats_zip_confirmation() -> None:
    state = replace(
        build_initial_app_state(),
        zip_compress_confirmation=ZipCompressConfirmationState(
            request=CreateZipArchiveRequest(
                source_paths=("/home/tadashi/develop/zivo/docs",),
                destination_path="/home/tadashi/develop/zivo/docs.zip",
                root_dir="/home/tadashi/develop/zivo",
            ),
            total_entries=4,
        ),
    )

    dialog = select_conflict_dialog_state(state)

    assert dialog is not None
    assert dialog.title == "Zip Compression Confirmation"
    assert "docs.zip already exists" in dialog.message
    assert dialog.options == ("enter overwrite", "esc return to input")


def test_select_conflict_dialog_state_formats_rename_conflict() -> None:
    state = replace(
        build_initial_app_state(),
        name_conflict=NameConflictState(kind="rename", name="src"),
    )

    dialog = select_conflict_dialog_state(state)

    assert dialog is not None
    assert dialog.title == "Rename Conflict"
    assert dialog.options == ("enter return to input", "esc return to input")


def test_select_conflict_dialog_state_formats_create_directory_conflict() -> None:
    state = replace(
        build_initial_app_state(),
        name_conflict=NameConflictState(kind="create_dir", name="docs"),
    )

    dialog = select_conflict_dialog_state(state)

    assert dialog is not None
    assert dialog.title == "Create Directory Conflict"
    assert "creating the directory" in dialog.message


def test_select_help_bar_for_paste_conflict_uses_generic_guidance() -> None:
    conflict = PasteConflict(
        source_path="/home/tadashi/develop/zivo/docs",
        destination_path="/home/tadashi/develop/zivo/docs",
    )
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        paste_conflict=PasteConflictState(
            request=PasteRequest(
                mode="copy",
                source_paths=("/home/tadashi/develop/zivo/docs",),
                destination_dir="/home/tadashi/develop/zivo",
            ),
            conflicts=(conflict,),
            first_conflict=conflict,
        ),
    )

    help_state = select_help_bar_state(state)

    assert help_state.text == "resolve conflict in dialog"


def test_select_help_bar_for_name_conflict() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        name_conflict=NameConflictState(kind="create_file", name="docs"),
    )

    help_state = select_help_bar_state(state)

    assert help_state.text == "enter return to input | esc return to input"


def test_select_help_bar_for_delete_confirmation() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        delete_confirmation=DeleteConfirmationState(
            paths=("/home/tadashi/develop/zivo/docs",),
        ),
    )

    help_state = select_help_bar_state(state)

    assert help_state.text == "enter confirm delete | esc cancel"


def test_select_help_bar_for_permanent_delete_confirmation() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        delete_confirmation=DeleteConfirmationState(
            paths=("/home/tadashi/develop/zivo/docs",),
            mode="permanent",
        ),
    )

    help_state = select_help_bar_state(state)

    assert help_state.text == "enter confirm permanent delete | esc cancel"


def test_select_help_bar_for_armed_permanent_delete_confirmation() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        delete_confirmation=DeleteConfirmationState(
            paths=("/tmp/docs",),
            mode="permanent",
            contains_directory=True,
            additional_confirmation_armed=True,
        ),
    )

    help_state = select_help_bar_state(state)

    assert help_state.text == "D permanently delete | esc cancel"


def test_select_help_bar_for_attribute_dialog() -> None:
    state = replace(build_initial_app_state(), ui_mode="DETAIL")

    help_state = select_help_bar_state(state)

    assert help_state.text == "enter close | esc close"


class TestComputeSearchVisibleWindow:
    """Tests for dynamic search window size calculation."""

    def test_default_terminal_height(self) -> None:
        assert selectors_module.compute_search_visible_window(24) == 14

    def test_large_terminal(self) -> None:
        assert selectors_module.compute_search_visible_window(48) == 38

    def test_very_large_terminal(self) -> None:
        assert selectors_module.compute_search_visible_window(80) == 70

    def test_small_terminal_uses_minimum(self) -> None:
        assert selectors_module.compute_search_visible_window(10) == 3

    def test_tiny_terminal_uses_minimum(self) -> None:
        assert selectors_module.compute_search_visible_window(1) == 3

    def test_extra_rows_reduce_visible_window(self) -> None:
        assert selectors_module.compute_search_visible_window(24, extra_rows=2) == 12


class TestSelectSearchWindowWithDynamicSize:
    """Tests for _select_file_search_window with dynamic terminal height."""

    def test_large_terminal_shows_more_items(self) -> None:
        results = tuple(
            FileSearchResultState(
                path=f"/home/tadashi/develop/zivo/src/module_{index}.py",
                display_path=f"src/module_{index}.py",
            )
            for index in range(30)
        )
        state = _reduce_state(
            replace(build_initial_app_state(), terminal_height=48),
            BeginCommandPalette(),
        )
        state = replace(
            state,
            command_palette=CommandPaletteState(
                source="file_search",
                query=".py",
                cursor_index=15,
                file_search=FileSearchPaletteState(results=results),
            ),
        )

        palette_state = select_command_palette_state(state)

        assert palette_state is not None
        assert len(palette_state.items) == 30
        assert palette_state.items[15].selected is True
        assert palette_state.has_more_items is False


class TestSelectCommandPaletteWindow:
    """Tests for _select_command_palette_window scrolling algorithm."""

    def test_empty_list(self) -> None:
        """空リストの場合は空のタプルが返されること"""
        items: tuple[CommandPaletteItem, ...] = ()
        result, title = _select_command_palette_window(items, 0)

        assert result == ()
        assert title == "Command Palette"

    def test_short_list(self) -> None:
        """ウィンドウサイズ以下の場合は全アイテムが表示されること"""
        items = tuple(
            CommandPaletteItem(id=f"item_{i}", label=f"Item {i}", shortcut=None, enabled=True)
            for i in range(5)
        )
        result, title = _select_command_palette_window(items, 2)

        assert len(result) == 5
        assert title == "Command Palette"
        assert result[2][0] == 2  # カーソル位置が2であること

    def test_exact_window_size(self) -> None:
        """ウィンドウサイズと同じ長さの場合は全アイテムが表示されること"""
        items = tuple(
            CommandPaletteItem(id=f"item_{i}", label=f"Item {i}", shortcut=None, enabled=True)
            for i in range(8)
        )
        result, title = _select_command_palette_window(items, 4)

        assert len(result) == 8
        assert title == "Command Palette"

    def test_center_alignment(self) -> None:
        """中央付近のアイテム選択時に中央揃えが維持されること"""
        items = tuple(
            CommandPaletteItem(id=f"item_{i}", label=f"Item {i}", shortcut=None, enabled=True)
            for i in range(20)
        )
        # 中央のアイテム（インデックス10）を選択
        result, title = _select_command_palette_window(items, 10)

        assert len(result) == 8  # ウィンドウサイズ
        assert title == "Command Palette (7-14 / 20)"
        # カーソルが中央に配置されること
        cursor_position_in_window = next(i for i, (idx, _) in enumerate(result) if idx == 10)
        assert cursor_position_in_window == 4  # ウィンドウの中央（0始まりで4）

    def test_top_boundary(self) -> None:
        """先頭付近のアイテム選択時に先頭から表示されること"""
        items = tuple(
            CommandPaletteItem(id=f"item_{i}", label=f"Item {i}", shortcut=None, enabled=True)
            for i in range(20)
        )
        # 先頭のアイテム（インデックス0）を選択
        result, title = _select_command_palette_window(items, 0)

        assert len(result) == 8
        assert title == "Command Palette (1-8 / 20)"
        assert result[0][0] == 0  # 先頭から表示

    def test_bottom_boundary(self) -> None:
        """末尾付近のアイテム選択時に末尾が見えること（主要なバグ修正）"""
        items = tuple(
            CommandPaletteItem(id=f"item_{i}", label=f"Item {i}", shortcut=None, enabled=True)
            for i in range(14)
        )
        # 最後のアイテム（インデックス13）を選択
        result, title = _select_command_palette_window(items, 13)

        assert len(result) == 8
        assert title == "Command Palette (7-14 / 14)"
        # 最後のアイテムが表示されていること
        assert result[-1][0] == 13
        assert result[-1][1].label == "Item 13"

    def test_last_item_visible(self) -> None:
        """最後のアイテムが必ず表示されること"""
        items = tuple(
            CommandPaletteItem(id=f"item_{i}", label=f"Item {i}", shortcut=None, enabled=True)
            for i in range(15)
        )
        # 最後のアイテム（インデックス14）を選択
        result, title = _select_command_palette_window(items, 14)

        assert len(result) == 8
        assert result[-1][0] == 14  # 最後のアイテムが表示されている
        assert result[0][0] == 7  # 先頭はインデックス7

    def test_second_last_item_visible(self) -> None:
        """最後から2番目のアイテムと最後のアイテムが両方表示されること"""
        items = tuple(
            CommandPaletteItem(id=f"item_{i}", label=f"Item {i}", shortcut=None, enabled=True)
            for i in range(14)
        )
        # 最後から2番目のアイテム（インデックス12）を選択
        result, title = _select_command_palette_window(items, 12)

        assert len(result) == 8
        # 最後から2番目と最後のアイテムが両方表示されていること
        visible_indices = [idx for idx, _ in result]
        assert 12 in visible_indices
        assert 13 in visible_indices
        assert result[-1][0] == 13  # 最後のアイテムが表示されている



class TestCommandPaletteDynamicWindow:
    """コマンドパレットの動的表示ウィンドウ計算のテスト."""

    def test_go_to_path_uses_dynamic_window_size(self) -> None:
        """Go to pathで48行端末の場合40件まで表示できること."""
        state = replace(
            _reduce_state(build_initial_app_state(), BeginCommandPalette()),
            terminal_height=48,
            command_palette=CommandPaletteState(
                source="go_to_path",
                query="",
                cursor_index=0,
                history_and_navigation=HistoryAndNavigationPaletteState(
                    go_to_path_candidates=tuple(f"/path/{i}" for i in range(25)),
                ),
            ),
        )

        palette_state = select_command_palette_state(state)

        assert palette_state is not None
        assert len(palette_state.items) == 25
        assert palette_state.has_more_items is False

    def test_go_to_path_small_terminal_uses_minimum(self) -> None:
        """Go to pathで小さな端末の場合最小3件表示されること."""
        state = replace(
            _reduce_state(build_initial_app_state(), BeginCommandPalette()),
            terminal_height=10,
            command_palette=CommandPaletteState(
                source="go_to_path",
                query="",
                cursor_index=0,
                history_and_navigation=HistoryAndNavigationPaletteState(
                    go_to_path_candidates=tuple(f"/path/{i}" for i in range(10)),
                ),
            ),
        )

        palette_state = select_command_palette_state(state)

        assert palette_state is not None
        assert len(palette_state.items) == 3

    def test_directory_history_uses_dynamic_window_size(self) -> None:
        """Directory Historyで48行端末なら全候補を表示できること."""
        state = replace(
            build_initial_app_state(),
            terminal_height=48,
            history=HistoryState(
                back=tuple(f"/history/{i}" for i in range(25)),
                forward=(),
            ),
            ui_mode="PALETTE",
            command_palette=CommandPaletteState(
                source="history",
                history_and_navigation=HistoryAndNavigationPaletteState(
                    history_results=tuple(f"/history/{i}" for i in range(25)),
                ),
            ),
        )

        palette_state = select_command_palette_state(state)

        assert palette_state is not None
        assert len(palette_state.items) == 25
        assert palette_state.has_more_items is False

    def test_bookmarks_uses_dynamic_window_size(self) -> None:
        """Bookmarksで48行端末なら全候補を表示できること."""
        state = replace(
            build_initial_app_state(),
            terminal_height=48,
            config=replace(
                build_initial_app_state().config,
                bookmarks=BookmarkConfig(paths=tuple(f"/bookmark/{i}" for i in range(25))),
            ),
            ui_mode="PALETTE",
            command_palette=CommandPaletteState(source="bookmarks"),
        )

        palette_state = select_command_palette_state(state)

        assert palette_state is not None
        assert len(palette_state.items) == 25
        assert palette_state.has_more_items is False

    def test_default_command_palette_keeps_all_commands_scrollable(self) -> None:
        """通常のコマンド一覧は末尾までスクロールできること."""

        state = replace(
            _reduce_state(build_initial_app_state(), BeginCommandPalette()),
            terminal_height=24,
        )

        palette_state = select_command_palette_state(state)

        assert palette_state is not None
        assert len(palette_state.items) > 14
        assert palette_state.has_more_items is True


def test_select_tab_bar_state_marks_active_tab() -> None:
    state = _reduce_state(build_initial_app_state(), OpenNewTab())

    tab_bar = select_tab_bar_state(state)

    assert [tab.label for tab in tab_bar.tabs] == ["zivo", "zivo"]
    assert [tab.active for tab in tab_bar.tabs] == [False, True]


def test_command_palette_tab_commands_have_no_direct_shortcut() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())

    palette_state = select_command_palette_state(state)

    assert palette_state is not None
    items = {item.label: item for item in palette_state.items}
    assert items["New tab"].shortcut == "o"
    assert items["Next tab"].shortcut is None
    assert items["Previous tab"].shortcut is None
    assert items["Close current tab"].shortcut == "w"
    assert items["Close current tab"].enabled is False


def test_command_palette_includes_undo_item_and_disables_when_empty() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())

    items = {
        item.label: item for item in command_palette_module.get_command_palette_items(state)
    }
    assert items["Undo last file operation"].shortcut == "z"
    assert items["Undo last file operation"].enabled is False
    assert items["Undo last file operation"].disabled_reason == "No operation to undo"


def test_command_palette_enables_undo_item_when_stack_is_present() -> None:
    state = replace(
        _reduce_state(build_initial_app_state(), BeginCommandPalette()),
        undo_stack=(UndoEntry(kind="paste_copy", steps=(UndoDeletePathStep("/tmp/copied"),)),),
    )

    items = {
        item.label: item for item in command_palette_module.get_command_palette_items(state)
    }
    assert items["Undo last file operation"].enabled is True


def test_selected_files_grep_item_enabled_with_selection() -> None:
    """Test that selected-files-grep item is enabled when files are selected."""
    state = reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = replace(
        state,
        current_pane=replace(
            state.current_pane,
            entries=(
                DirectoryEntryState(
                    "/home/tadashi/develop/zivo/src/main.py",
                    "main.py",
                    "file",
                ),
                DirectoryEntryState(
                    "/home/tadashi/develop/zivo/src/utils.py",
                    "utils.py",
                    "file",
                ),
            ),
            selected_paths=frozenset({
                "/home/tadashi/develop/zivo/src/main.py",
                "/home/tadashi/develop/zivo/src/utils.py",
            }),
        ),
    )

    items = selectors_module.get_command_palette_items(state)
    selected_files_grep_items = [item for item in items if item.id == "selected_files_grep"]

    assert len(selected_files_grep_items) == 1
    assert selected_files_grep_items[0].enabled is True


def test_selected_files_grep_item_disabled_without_selection() -> None:
    """Test that selected-files-grep item is disabled when no files are selected."""
    state = reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = replace(
        state,
        current_pane=replace(
            state.current_pane,
            entries=(
                DirectoryEntryState(
                    "/home/tadashi/develop/zivo/src/main.py",
                    "main.py",
                    "file",
                ),
            ),
            selected_paths=frozenset(),
        ),
    )

    items = selectors_module.get_command_palette_items(state)
    selected_files_grep_items = [item for item in items if item.id == "selected_files_grep"]

    assert len(selected_files_grep_items) == 1
    assert selected_files_grep_items[0].enabled is False


def test_selected_files_grep_command_opens_palette() -> None:
    """Test that selected-files-grep command opens the command palette."""
    state = reduce_state(
        build_initial_app_state(),
        BeginSelectedFilesGrep(
            target_paths=("/home/tadashi/develop/zivo/src/main.py",)
        ),
    )

    assert state.ui_mode == "PALETTE"
    assert state.command_palette is not None
    assert state.command_palette.source == "selected_files_grep"


def test_detect_preview_disabled_message_returns_none_for_directory() -> None:
    """Test that preview disabled message is None for directories."""
    from zivo.state.selectors_panes import _detect_preview_disabled_message

    entry = DirectoryEntryState("/home/tadashi/docs", "docs", "dir")
    message = _detect_preview_disabled_message(
        entry,
        enable_text_preview=False,
        enable_image_preview=False,
        enable_pdf_preview=False,
        enable_office_preview=False,
    )
    assert message is None


def test_select_shell_data_builds_sfg_preview_for_palette_selection() -> None:
    initial_state = build_initial_app_state()
    path = "/home/tadashi/develop/zivo/README.md"
    grep_result = GrepSearchResultState(
        path=path,
        display_path="README.md",
        line_number=5,
        line_text="TODO: update docs",
    )
    state = replace(
        initial_state,
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="selected_files_grep",
            query="todo",
            sfg=SfgPaletteState(
                target_paths=(path,),
                results=(grep_result,),
            ),
        ),
        child_pane=PaneState(
            directory_path="/home/tadashi/develop/zivo",
            entries=(),
            mode="preview",
            preview_path=path,
            preview_title="Preview: README.md:5",
            preview_content="line3\nline4\nTODO: update docs\nline6\n",
            preview_start_line=2,
            preview_highlight_line=5,
        ),
    )

    shell = select_shell_data(state)

    assert shell.child_pane.is_preview is True
    assert shell.child_pane.title == "Preview: README.md:5"
    assert shell.child_pane.preview_path == path
    assert shell.child_pane.preview_start_line == 2
    assert shell.child_pane.preview_highlight_line == 5


def test_select_shell_data_builds_sfg_preview_falls_back_to_empty_for_no_results() -> None:
    initial_state = build_initial_app_state()
    state = replace(
        initial_state,
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="selected_files_grep",
            query="todo",
            sfg=SfgPaletteState(results=()),
        ),
    )

    shell = select_shell_data(state)

    assert shell.child_pane.is_preview is False
    assert shell.child_pane.title == "Child Directory"


def test_select_shell_data_builds_sfg_preview_falls_back_to_empty_when_preview_disabled() -> None:
    initial_state = build_initial_app_state()
    config = replace(
        initial_state.config,
        display=replace(initial_state.config.display, enable_text_preview=False),
    )
    path = "/home/tadashi/develop/zivo/README.md"
    grep_result = GrepSearchResultState(
        path=path,
        display_path="README.md",
        line_number=5,
        line_text="TODO: update docs",
    )
    state = replace(
        initial_state,
        config=config,
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="selected_files_grep",
            query="todo",
            sfg=SfgPaletteState(results=(grep_result,)),
        ),
    )

    shell = select_shell_data(state)

    assert shell.child_pane.is_preview is False
    assert shell.child_pane.title == "Child Directory"


def test_detect_preview_disabled_message_returns_none_for_null_cursor() -> None:
    """Test that preview disabled message is None for null cursor."""
    from zivo.state.selectors_panes import _detect_preview_disabled_message

    message = _detect_preview_disabled_message(
        None,
        enable_text_preview=False,
        enable_image_preview=False,
        enable_pdf_preview=False,
        enable_office_preview=False,
    )
    assert message is None


def test_detect_preview_disabled_message_for_pdf_file() -> None:
    """Test that PDF preview disabled message is returned for PDF files."""
    from zivo.state.selectors_panes import _detect_preview_disabled_message

    entry = DirectoryEntryState("/home/tadashi/docs/test.pdf", "test.pdf", "file")
    message = _detect_preview_disabled_message(
        entry,
        enable_text_preview=True,
        enable_image_preview=True,
        enable_pdf_preview=False,
        enable_office_preview=True,
    )
    assert message == "PDF preview is disabled"


def test_detect_preview_disabled_message_for_office_file() -> None:
    """Test that Office preview disabled message is returned for Office files."""
    from zivo.state.selectors_panes import _detect_preview_disabled_message

    # Test .docx
    entry = DirectoryEntryState(
        "/home/tadashi/docs/test.docx", "test.docx", "file"
    )
    message = _detect_preview_disabled_message(
        entry,
        enable_text_preview=True,
        enable_image_preview=True,
        enable_pdf_preview=True,
        enable_office_preview=False,
    )
    assert message == "Office file preview is disabled"

    # Test .xlsx
    entry = DirectoryEntryState(
        "/home/tadashi/docs/test.xlsx", "test.xlsx", "file"
    )
    message = _detect_preview_disabled_message(
        entry,
        enable_text_preview=True,
        enable_image_preview=True,
        enable_pdf_preview=True,
        enable_office_preview=False,
    )
    assert message == "Office file preview is disabled"

    # Test .pptx
    entry = DirectoryEntryState(
        "/home/tadashi/docs/test.pptx", "test.pptx", "file"
    )
    message = _detect_preview_disabled_message(
        entry,
        enable_text_preview=True,
        enable_image_preview=True,
        enable_pdf_preview=True,
        enable_office_preview=False,
    )
    assert message == "Office file preview is disabled"


def test_detect_preview_disabled_message_for_text_file() -> None:
    """Test that text preview disabled message is returned for text files."""
    from zivo.state.selectors_panes import _detect_preview_disabled_message

    entry = DirectoryEntryState("/home/tadashi/docs/test.txt", "test.txt", "file")
    message = _detect_preview_disabled_message(
        entry,
        enable_text_preview=False,
        enable_image_preview=True,
        enable_pdf_preview=True,
        enable_office_preview=True,
    )
    assert message == "Text preview is disabled"


def test_detect_preview_disabled_message_for_image_file() -> None:
    from zivo.state.selectors_panes import _detect_preview_disabled_message

    entry = DirectoryEntryState("/home/tadashi/docs/test.png", "test.png", "file")
    message = _detect_preview_disabled_message(
        entry,
        enable_text_preview=True,
        enable_image_preview=False,
        enable_pdf_preview=True,
        enable_office_preview=True,
    )
    assert message == "Image preview is disabled"


def test_detect_preview_disabled_message_for_all_previews_disabled() -> None:
    """Test that generic preview disabled message is returned when all previews are disabled."""
    from zivo.state.selectors_panes import _detect_preview_disabled_message

    entry = DirectoryEntryState("/home/tadashi/docs/test.txt", "test.txt", "file")
    message = _detect_preview_disabled_message(
        entry,
        enable_text_preview=False,
        enable_image_preview=False,
        enable_pdf_preview=False,
        enable_office_preview=False,
    )
    assert message == "Preview is disabled"


def test_detect_preview_disabled_message_returns_none_when_enabled() -> None:
    """Test that no message is returned when preview is enabled."""
    from zivo.state.selectors_panes import _detect_preview_disabled_message

    entry = DirectoryEntryState("/home/tadashi/docs/test.txt", "test.txt", "file")
    message = _detect_preview_disabled_message(
        entry,
        enable_text_preview=True,
        enable_image_preview=True,
        enable_pdf_preview=True,
        enable_office_preview=True,
    )
    assert message is None


def test_select_command_palette_state_rff_preview_title_with_counts() -> None:
    preview_result = ReplacePreviewResultState(
        path="/home/tadashi/develop/zivo/README.md",
        display_path="README.md",
        diff_text="--- before\n+++ after\n@@\n-todo item\n+done item\n",
        match_count=2,
        first_match_line_number=8,
        first_match_before="todo item",
        first_match_after="done item",
    )
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="replace_in_found_files",
            rff=RffPaletteState(
                preview_results=(preview_result,),
                total_match_count=2,
            ),
        ),
    )
    palette_state = select_command_palette_state(state)
    assert palette_state is not None
    assert palette_state.title == "Replace in Found Files (1 file(s), 2 match(es)) (1-1 / 1)"


def test_select_command_palette_state_rff_preview_title_without_results() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="replace_in_found_files",
        ),
    )
    palette_state = select_command_palette_state(state)
    assert palette_state is not None
    assert palette_state.title == "Replace in Found Files"


def test_select_command_palette_state_grf_preview_title_with_counts() -> None:
    preview_result = ReplacePreviewResultState(
        path="/home/tadashi/develop/zivo/README.md",
        display_path="README.md",
        diff_text="--- before\n+++ after\n@@\n-todo item\n+done item\n",
        match_count=2,
        first_match_line_number=8,
        first_match_before="todo item",
        first_match_after="done item",
    )
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="replace_in_grep_files",
            grf=GrfPaletteState(
                preview_results=(preview_result,),
                total_match_count=2,
            ),
        ),
    )
    palette_state = select_command_palette_state(state)
    assert palette_state is not None
    assert palette_state.title == "Replace in Grep Results (1 file(s), 2 match(es)) (1-1 / 1)"


def test_select_command_palette_state_grs_preview_title_with_counts() -> None:
    preview_result = ReplacePreviewResultState(
        path="/home/tadashi/develop/zivo/README.md",
        display_path="README.md",
        diff_text="--- before\n+++ after\n@@\n-todo item\n+done item\n",
        match_count=2,
        first_match_line_number=8,
        first_match_before="todo item",
        first_match_after="done item",
    )
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="grep_replace_selected",
            grs=GrsPaletteState(
                preview_results=(preview_result,),
                total_match_count=2,
            ),
        ),
    )
    palette_state = select_command_palette_state(state)
    assert palette_state is not None
    assert palette_state.title == "Replace in Selected Files (1 file(s), 2 match(es)) (1-1 / 1)"


def test_select_shell_data_distinguishes_empty_and_filtered_empty_directory() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        current_pane=PaneState(directory_path=state.current_path, entries=()),
    )

    shell = select_shell_data(state)
    assert shell.current_pane_status is not None
    assert shell.current_pane_status.kind == "empty"
    assert [action.action_id for action in shell.current_pane_status.actions] == [
        "create_file",
        "create_dir",
    ]
    assert [action.shortcut for action in shell.current_pane_status.actions] == ["n", "N"]

    filtered = replace(
        state,
        current_pane=PaneState(
            directory_path=state.current_path,
            entries=(DirectoryEntryState(f"{state.current_path}/README.md", "README.md", "file"),),
        ),
        filter=replace(state.filter, query="[report]", active=True),
    )
    filtered_shell = select_shell_data(filtered)
    assert filtered_shell.current_pane_status is not None
    assert filtered_shell.current_pane_status.kind == "filtered_empty"
    assert filtered_shell.current_pane_status.title == 'No matches for "[report]"'
    assert filtered_shell.current_pane_status.actions[0].action_id == "clear_filter"
    assert filtered_shell.current_pane_status.actions[0].shortcut == "Esc"


def test_select_shell_data_builds_typed_metadata_fallback() -> None:
    state = build_initial_app_state()
    target = f"{state.current_path}/data.bin"
    state = replace(
        state,
        current_pane=PaneState(
            directory_path=state.current_path,
            entries=(DirectoryEntryState(target, "data.bin", "file"),),
            cursor_path=target,
        ),
        child_pane=PaneState(
            directory_path=state.current_path,
            entries=(),
            mode="preview",
            preview_path=target,
            preview_reason="unsupported",
            preview_metadata=PreviewMetadataState(
                display_name="data.bin",
                type_label="BIN",
                size_bytes=2048,
                owner="alice",
                group="staff",
            ),
        ),
    )

    fallback = select_shell_data(state).child_pane
    assert fallback.view_kind == "unsupported"
    assert fallback.status is not None
    assert fallback.status.actions[0].action_id == "show_attributes"
    assert [(item.label, item.value) for item in fallback.metadata] == [
        ("Name", "data.bin"),
        ("Type", "BIN"),
        ("Size", "2.0KiB"),
        ("Owner/group", "alice/staff"),
    ]
