"""Selector tests for pane, preview, and projection behavior."""
from tests.support.paths import TEST_HOME, TEST_PROJECT_ROOT
from tests.support.selectors import (
    AppConfig,
    BeginCommandPalette,
    BeginFilterInput,
    CommandPaletteState,
    CurrentPaneDeltaState,
    CutTargets,
    DirectoryEntryState,
    DirectorySizeCacheEntry,
    DirectorySizeDeltaState,
    GrepSearchPaletteState,
    GrepSearchResultState,
    NotificationState,
    OpenNewTab,
    PaneState,
    PreviewMetadataState,
    SetCursorPath,
    SetFilterQuery,
    SetNotification,
    SetSort,
    ToggleSelection,
    _has_execute_permission,
    _reduce_state,
    build_initial_app_state,
    build_placeholder_app_state,
    compute_current_pane_visible_window,
    directory_size_target_paths,
    entry,
    os,
    pane,
    pytest,
    replace,
    select_child_entries,
    select_command_palette_state,
    select_current_entries,
    select_current_summary_state,
    select_parent_entries,
    select_responsive_pane_layout,
    select_shell_data,
    select_tab_bar_state,
    select_target_paths,
    select_visible_current_entry_states,
    selectors_module,
)


def test_build_placeholder_app_state_keeps_parent_pane_empty_at_root() -> None:
    state = build_placeholder_app_state("/")

    expected_root = "C:\\" if os.name == "nt" else "/"
    assert state.current_path == expected_root
    assert state.parent_pane.directory_path == expected_root
    assert state.parent_pane.entries == ()
    assert state.parent_pane.cursor_path is None

def test_command_palette_tab_commands_have_no_direct_shortcut() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = replace(state, command_palette=replace(state.command_palette, query="tab"))

    palette_state = select_command_palette_state(state)

    assert palette_state is not None
    items = {item.label: item for item in palette_state.items}
    assert items["New tab"].shortcut == "o"
    assert items["Next tab"].shortcut is None
    assert items["Previous tab"].shortcut is None
    assert items["Close current tab"].shortcut == "w"
    assert items["Close current tab"].enabled is False

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
            directory_path=TEST_PROJECT_ROOT,
            entries=(
                DirectoryEntryState(TEST_PROJECT_ROOT + '/docs', "docs", "dir"),
                DirectoryEntryState(
                    TEST_PROJECT_ROOT + '/.cache',
                    ".cache",
                    "dir",
                    hidden=True,
                ),
                DirectoryEntryState(
                    TEST_PROJECT_ROOT + '/README.md',
                    "README.md",
                    "file",
                ),
            ),
            cursor_path=TEST_PROJECT_ROOT + '/docs',
        ),
        child_pane=PaneState(
            directory_path=TEST_PROJECT_ROOT + '/docs',
            entries=(DirectoryEntryState(TEST_PROJECT_ROOT + '/docs/api', "api", "dir"),),
        ),
    )

    assert directory_size_target_paths(state) == (TEST_PROJECT_ROOT + '/docs',)

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
            directory_path=TEST_PROJECT_ROOT,
            entries=(
                DirectoryEntryState(TEST_PROJECT_ROOT + '/docs', "docs", "dir"),
                DirectoryEntryState(
                    TEST_PROJECT_ROOT + '/.cache',
                    ".cache",
                    "dir",
                    hidden=True,
                ),
            ),
            cursor_path=TEST_PROJECT_ROOT + '/docs',
        ),
    )

    assert directory_size_target_paths(state) == (TEST_PROJECT_ROOT + '/docs',)
    assert directory_size_target_paths(replace(state, show_hidden=True)) == (
        TEST_PROJECT_ROOT + '/.cache',
        TEST_PROJECT_ROOT + '/docs',
    )

def test_directory_size_target_paths_returns_empty_when_directory_sizes_are_disabled() -> None:
    state = replace(
        build_initial_app_state(),
        config=replace(
            build_initial_app_state().config,
            display=replace(build_initial_app_state().config.display, show_directory_sizes=False),
        ),
        current_pane=PaneState(
            directory_path=TEST_PROJECT_ROOT,
            entries=(DirectoryEntryState(TEST_PROJECT_ROOT + '/docs', "docs", "dir"),),
            cursor_path=TEST_PROJECT_ROOT + '/docs',
        ),
    )

    assert directory_size_target_paths(state) == ()

def test_directory_size_target_paths_uses_current_pane_for_size_sort() -> None:
    state = replace(
        build_initial_app_state(),
        current_pane=PaneState(
            directory_path=TEST_PROJECT_ROOT,
            entries=(
                DirectoryEntryState(TEST_PROJECT_ROOT + '/docs', "docs", "dir"),
                DirectoryEntryState(TEST_PROJECT_ROOT + '/src', "src", "dir"),
                DirectoryEntryState(
                    TEST_PROJECT_ROOT + '/README.md',
                    "README.md",
                    "file",
                ),
            ),
            cursor_path=TEST_PROJECT_ROOT + '/docs',
        ),
        sort=replace(build_initial_app_state().sort, field="size"),
    )

    assert directory_size_target_paths(state) == (
        TEST_PROJECT_ROOT + '/docs',
        TEST_PROJECT_ROOT + '/src',
    )

def test_has_execute_permission_returns_false_for_no_permissions() -> None:
    """0o000 (---------) の場合に False を返すこと"""
    entry_state = DirectoryEntryState(
        TEST_PROJECT_ROOT + '/locked',
        "locked",
        "file",
        permissions_mode=0o000,
    )

    assert _has_execute_permission(entry_state) is False

def test_has_execute_permission_returns_false_for_non_executable_files() -> None:
    """0o644 (rw-r--r--) の場合に False を返すこと"""
    entry_state = DirectoryEntryState(
        TEST_PROJECT_ROOT + '/README.md',
        "README.md",
        "file",
        permissions_mode=0o644,
    )

    assert _has_execute_permission(entry_state) is False

def test_has_execute_permission_returns_false_for_none_permissions() -> None:
    """permissions_mode が None の場合に False を返すこと"""
    entry_state = DirectoryEntryState(
        TEST_PROJECT_ROOT + '/unknown',
        "unknown",
        "file",
        permissions_mode=None,
    )

    assert _has_execute_permission(entry_state) is False

def test_has_execute_permission_returns_true_for_executable_files() -> None:
    """0o755 (rwxr-xr-x) の場合に True を返すこと"""
    entry_state = DirectoryEntryState(
        TEST_PROJECT_ROOT + '/test.sh',
        "test.sh",
        "file",
        permissions_mode=0o755,
    )

    assert _has_execute_permission(entry_state) is True

def test_has_execute_permission_returns_true_for_execute_only_files() -> None:
    """0o111 (--x--x--x) の場合に True を返すこと"""
    entry_state = DirectoryEntryState(
        TEST_PROJECT_ROOT + '/script',
        "script",
        "file",
        permissions_mode=0o111,
    )

    assert _has_execute_permission(entry_state) is True

def test_select_child_entries_clears_stale_snapshot_while_request_is_pending() -> None:
    state = replace(
        build_initial_app_state(),
        current_pane=PaneState(
            directory_path=TEST_PROJECT_ROOT,
            entries=(
                DirectoryEntryState(TEST_PROJECT_ROOT + '/docs', "docs", "dir"),
                DirectoryEntryState(TEST_PROJECT_ROOT + '/src', "src", "dir"),
            ),
            cursor_path=TEST_PROJECT_ROOT + '/src',
        ),
        child_pane=PaneState(
            directory_path=TEST_PROJECT_ROOT + '/docs',
            entries=(
                DirectoryEntryState(
                    TEST_PROJECT_ROOT + '/docs/spec.md',
                    "spec.md",
                    "file",
                ),
            ),
        ),
        pending_child_pane_request_id=7,
    )

    assert select_child_entries(state) == ()

def test_select_child_entries_is_empty_when_cursor_is_file() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, SetCursorPath(TEST_PROJECT_ROOT + '/README.md'))

    assert select_child_entries(state) == ()

def test_select_child_syntax_theme_prefers_explicit_preview_style() -> None:
    assert selectors_module._select_child_syntax_theme("solarized-light", "xcode") == "xcode"
    assert selectors_module._select_child_syntax_theme("dracula", "one-dark") == "one-dark"

def test_select_child_syntax_theme_tracks_builtin_theme_brightness() -> None:
    assert selectors_module._select_child_syntax_theme("solarized-light", "auto") == "friendly"
    assert selectors_module._select_child_syntax_theme("dracula", "auto") == "monokai"

def test_select_current_entries_applies_filter_and_sort() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, SetFilterQuery("t"))
    state = _reduce_state(
        state,
        SetSort(field="name", descending=True, directories_first=False),
    )

    entries = select_current_entries(state)

    assert [entry.name for entry in entries] == ["tests", "pyproject.toml"]

def test_select_current_entries_hides_hidden_by_default() -> None:
    state = replace(
        build_initial_app_state(),
        current_pane=PaneState(
            directory_path=TEST_PROJECT_ROOT,
            entries=(
                DirectoryEntryState(
                    TEST_PROJECT_ROOT + '/.env',
                    ".env",
                    "file",
                    hidden=True,
                ),
                DirectoryEntryState(TEST_PROJECT_ROOT + '/docs', "docs", "dir"),
            ),
            cursor_path=TEST_PROJECT_ROOT + '/docs',
        ),
    )

    entries = select_current_entries(state)

    assert [entry.name for entry in entries] == ["docs"]

def test_select_current_entries_marks_cut_rows() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, CutTargets((TEST_PROJECT_ROOT + '/docs',)))

    entries = select_current_entries(state)

    assert entries[0].name == "docs"
    assert entries[0].cut is True
    assert entries[1].cut is False

def test_select_current_entries_marks_selected_rows() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, ToggleSelection(TEST_PROJECT_ROOT + '/README.md'))

    entries = select_current_entries(state)

    assert entries[0].selected is False
    assert entries[4].name == "README.md"
    assert entries[4].selected is True
    assert entries[4].selection_marker == "*"

def test_select_current_entry_for_path_returns_none_for_filtered_entry() -> None:
    hidden_path = TEST_PROJECT_ROOT + '/README.md'
    visible_path = TEST_PROJECT_ROOT + '/docs'
    state = replace(
        build_initial_app_state(),
        current_pane=PaneState(
            directory_path=TEST_PROJECT_ROOT,
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

def test_select_current_summary_counts_selected_absolute_paths() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, ToggleSelection(TEST_PROJECT_ROOT + '/README.md'))
    state = _reduce_state(state, ToggleSelection(TEST_PROJECT_ROOT + '/tests'))

    summary = select_current_summary_state(state)

    assert summary.selected_count == 2
    assert summary.item_count == 5

def test_select_current_summary_state_keeps_summary_format() -> None:
    state = build_initial_app_state()

    summary = select_current_summary_state(state)

    assert (
        f"{summary.item_count} items | {summary.selected_count} selected | "
        f"sort: {summary.sort_label}"
    ) == "5 items | 0 selected | sort: name asc"

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
            directory_path=TEST_PROJECT_ROOT,
            entries=(
                DirectoryEntryState(TEST_PROJECT_ROOT + '/docs', "docs", "dir"),
                DirectoryEntryState(
                    TEST_PROJECT_ROOT + '/README.md',
                    "README.md",
                    "file",
                    size_bytes=2_150,
                ),
            ),
            cursor_path=TEST_PROJECT_ROOT + '/docs',
        ),
        child_pane=PaneState(
            directory_path=TEST_PROJECT_ROOT + '/docs',
            entries=(DirectoryEntryState(TEST_PROJECT_ROOT + '/docs/api', "api", "dir"),),
        ),
        directory_size_cache=(
            DirectorySizeCacheEntry(
                "/tmp/zivo",
                "ready",
                size_bytes=3_400_000,
            ),
            DirectorySizeCacheEntry(
                TEST_PROJECT_ROOT + '/docs',
                "pending",
            ),
            DirectorySizeCacheEntry(
                TEST_PROJECT_ROOT + '/docs/api',
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
            directory_path=TEST_PROJECT_ROOT,
            entries=(DirectoryEntryState(TEST_PROJECT_ROOT + '/docs', "docs", "dir"),),
            cursor_path=TEST_PROJECT_ROOT + '/docs',
        ),
        child_pane=PaneState(
            directory_path=TEST_PROJECT_ROOT + '/docs',
            entries=(
                DirectoryEntryState(
                    TEST_PROJECT_ROOT + '/docs/.draft.md',
                    ".draft.md",
                    "file",
                    hidden=True,
                ),
                DirectoryEntryState(
                    TEST_PROJECT_ROOT + '/docs/spec.md',
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
            directory_path=TEST_PROJECT_ROOT,
            entries=state.current_pane.entries,
            cursor_path=TEST_PROJECT_ROOT + '/docs',
        ),
        child_pane=PaneState(
            directory_path=TEST_PROJECT_ROOT + '/docs',
            entries=(
                DirectoryEntryState(
                    TEST_PROJECT_ROOT + '/docs/readme.txt',
                    "readme.txt",
                    "file",
                ),
                DirectoryEntryState(
                    TEST_PROJECT_ROOT + '/docs/archive',
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

def test_select_shell_data_builds_child_preview_for_permission_denied_directory() -> None:
    from zivo.services import PREVIEW_PERMISSION_DENIED_MESSAGE

    initial_state = build_initial_app_state()
    path = TEST_PROJECT_ROOT + '/.Trash'
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

def test_select_shell_data_builds_child_preview_for_text_file() -> None:
    initial_state = build_initial_app_state()
    path = TEST_PROJECT_ROOT + '/README.md'
    state = replace(
        initial_state,
        current_pane=replace(initial_state.current_pane, cursor_path=path),
        child_pane=PaneState(
            directory_path=TEST_PROJECT_ROOT,
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
    path = TEST_PROJECT_ROOT + '/archive.bin'
    state = replace(
        initial_state,
        current_pane=replace(
            initial_state.current_pane,
            entries=initial_state.current_pane.entries
            + (DirectoryEntryState(path, "archive.bin", "file"),),
            cursor_path=path,
        ),
        child_pane=PaneState(
            directory_path=TEST_PROJECT_ROOT,
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

def test_select_shell_data_builds_grep_preview_for_palette_selection() -> None:
    initial_state = build_initial_app_state()
    path = TEST_PROJECT_ROOT + '/README.md'
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
            directory_path=TEST_PROJECT_ROOT,
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

def test_select_shell_data_emits_row_delta_updates_for_cut_changes() -> None:
    path = TEST_PROJECT_ROOT + '/docs'
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

def test_select_shell_data_emits_row_delta_updates_for_selection_changes() -> None:
    path = TEST_PROJECT_ROOT + '/README.md'
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
                TEST_PROJECT_ROOT + '/docs',
                "ready",
                size_bytes=4_200,
            ),
        ),
        directory_size_delta=DirectorySizeDeltaState(
            changed_paths=(TEST_PROJECT_ROOT + '/docs',),
            revision=3,
        ),
    )

    shell = select_shell_data(state)
    row_index = next(
        index
        for index, entry in enumerate(select_current_entries(state))
        if entry.path == TEST_PROJECT_ROOT + '/docs'
    )

    assert shell.current_entries is None
    assert shell.current_pane_update.mode == "size_delta"
    assert shell.current_pane_update.revision == 3
    assert [
        (update.path, update.size_label, update.row_index)
        for update in shell.current_pane_update.size_updates
    ] == [
        (TEST_PROJECT_ROOT + '/docs', "4.1KiB", row_index)
    ]

def test_select_shell_data_exposes_visible_cursor_index() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, SetCursorPath(TEST_PROJECT_ROOT + '/tests'))

    shell = select_shell_data(state)

    assert shell.current_path == TEST_PROJECT_ROOT
    assert shell.current_cursor_index == 2
    assert shell.current_heading.status_label == "3/5"
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

def test_select_shell_data_hides_cursor_while_filtering() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFilterInput())

    shell = select_shell_data(state)

    assert shell.current_cursor_visible is False

def test_select_shell_data_hides_stale_preview_while_request_is_pending() -> None:
    current_path = TEST_PROJECT_ROOT
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

def test_select_shell_data_includes_selected_cut_and_contextual_models() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        ToggleSelection(TEST_PROJECT_ROOT + '/README.md'),
    )
    state = _reduce_state(state, CutTargets((TEST_PROJECT_ROOT + '/docs',)))
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

def test_select_shell_data_keeps_cursor_visible_in_palette_mode() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())

    shell = select_shell_data(state)

    assert shell.current_cursor_visible is True

def test_select_shell_data_keeps_full_refresh_when_sorting_by_size() -> None:
    state = replace(
        build_initial_app_state(),
        sort=replace(build_initial_app_state().sort, field="size"),
        current_pane_delta=CurrentPaneDeltaState(
            changed_paths=(TEST_PROJECT_ROOT + '/docs',),
            revision=7,
        ),
        directory_size_cache=(
            DirectorySizeCacheEntry(
                TEST_PROJECT_ROOT + '/docs',
                "ready",
                size_bytes=4_200,
            ),
        ),
        directory_size_delta=DirectorySizeDeltaState(
            changed_paths=(TEST_PROJECT_ROOT + '/docs',),
            revision=2,
        ),
    )

    shell = select_shell_data(state)

    assert shell.current_pane_update.mode == "full"
    assert shell.current_entries is not None

def test_select_shell_data_rebuilds_only_current_entries_when_selection_changes() -> None:
    state = build_initial_app_state()

    initial_shell = select_shell_data(state)
    updated_shell = select_shell_data(
        _reduce_state(
            state,
            ToggleSelection(TEST_PROJECT_ROOT + '/README.md'),
        )
    )

    assert updated_shell.parent_entries is initial_shell.parent_entries
    assert updated_shell.child_pane == initial_shell.child_pane
    assert updated_shell.current_entries is not initial_shell.current_entries

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
            SetCursorPath(TEST_PROJECT_ROOT + '/tests'),
        )
    )

    assert moved_shell.current_entries is initial_shell.current_entries
    assert moved_shell.current_cursor_index == 2
    assert moved_shell.child_pane.entries == ()

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
    assert updated_shell.child_pane == initial_shell.child_pane

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

def test_select_shell_data_limits_parent_and_child_panes_to_visible_window() -> None:
    root = "/tmp/zivo-side-viewport"
    parent_entries = tuple(
        entry(f"/tmp/sibling_{index:02d}", name=f"sibling_{index:02d}", kind="dir")
        for index in range(12)
    )
    current_directory = parent_entries[10]
    child_entries = tuple(
        entry(f"{root}/child_{index:02d}", name=f"child_{index:02d}")
        for index in range(12)
    )
    state = replace(
        build_initial_app_state(current_pane_projection_mode="viewport"),
        terminal_width=120,
        terminal_height=12,
        parent_pane=pane(
            "/tmp",
            parent_entries,
            cursor_path=current_directory.path,
        ),
        current_pane=pane(
            root,
            (entry(f"{root}/selected", name="selected", kind="dir"),),
            cursor_path=f"{root}/selected",
        ),
        child_pane=pane(f"{root}/selected", child_entries),
    )

    shell = select_shell_data(state)

    visible_window = compute_current_pane_visible_window(state.terminal_height)
    assert len(shell.parent_entries) == visible_window
    assert current_directory.path in {item.path for item in shell.parent_entries}
    assert len(shell.child_pane.entries) == visible_window
    assert shell.child_pane.display_title == "Contents · selected · 12 items"

def test_select_shell_data_skips_hidden_side_pane_projection(monkeypatch) -> None:
    state = replace(
        build_initial_app_state(current_pane_projection_mode="viewport"),
        terminal_width=79,
        narrow_pane_view="current",
    )

    monkeypatch.setattr(
        selectors_module,
        "select_parent_entries",
        lambda _state: pytest.fail("hidden parent pane must not be projected"),
    )
    monkeypatch.setattr(
        selectors_module,
        "_select_child_pane_for_cursor",
        lambda _state, _entry: pytest.fail("hidden child pane must not be projected"),
    )

    shell = select_shell_data(state)

    assert shell.parent_entries == ()
    assert shell.child_pane.entries == ()

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

def test_select_tab_bar_state_marks_active_tab() -> None:
    state = _reduce_state(build_initial_app_state(), OpenNewTab())

    tab_bar = select_tab_bar_state(state)

    assert [tab.label for tab in tab_bar.tabs] == ["zivo", "zivo"]
    assert [tab.active for tab in tab_bar.tabs] == [False, True]

def test_select_target_file_paths_ignores_hidden_selected_entries_when_hidden_files_are_off(
) -> None:
    hidden_path = TEST_PROJECT_ROOT + '/.env'
    visible_path = TEST_PROJECT_ROOT + '/README.md'
    state = replace(
        build_initial_app_state(),
        current_pane=PaneState(
            directory_path=TEST_PROJECT_ROOT,
            entries=(
                DirectoryEntryState(hidden_path, ".env", "file", hidden=True),
                DirectoryEntryState(visible_path, "README.md", "file"),
            ),
            cursor_path=visible_path,
            selected_paths=frozenset({hidden_path}),
        ),
    )

    assert selectors_module.select_target_file_paths(state) == ()

def test_select_target_paths_falls_back_to_cursor() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, SetCursorPath(TEST_PROJECT_ROOT + '/tests'))

    assert select_target_paths(state) == (TEST_PROJECT_ROOT + '/tests',)

def test_select_target_paths_ignores_hidden_selected_entries_when_hidden_files_are_off() -> None:
    hidden_path = TEST_PROJECT_ROOT + '/.env'
    visible_path = TEST_PROJECT_ROOT + '/docs'
    state = replace(
        build_initial_app_state(),
        current_pane=pane(
            TEST_PROJECT_ROOT,
            (
                entry(hidden_path, hidden=True),
                entry(visible_path, kind="dir"),
            ),
            cursor_path=visible_path,
            selected_paths=(hidden_path, visible_path),
        ),
    )

    assert select_target_paths(state) == (visible_path,)

def test_select_target_paths_prefers_selection_in_entry_order() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, ToggleSelection(TEST_PROJECT_ROOT + '/README.md'))
    state = _reduce_state(state, ToggleSelection(TEST_PROJECT_ROOT + '/docs'))

    assert select_target_paths(state) == (
        TEST_PROJECT_ROOT + '/docs',
        TEST_PROJECT_ROOT + '/README.md',
    )

def test_select_target_paths_returns_empty_tuple_for_empty_directory() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        current_pane=PaneState(directory_path=state.current_path, entries=(), cursor_path=None),
    )

    assert select_target_paths(state) == ()

def test_select_visible_current_entries_skip_size_overlay_when_not_sorting_by_size() -> None:
    state = replace(
        build_initial_app_state(),
        directory_size_cache=(
            DirectorySizeCacheEntry(
                TEST_PROJECT_ROOT + '/docs',
                "ready",
                size_bytes=4_200,
            ),
        ),
    )

    visible_entries = select_visible_current_entry_states(state)

    assert visible_entries[0].path == TEST_PROJECT_ROOT + '/docs'
    assert visible_entries[0].size_bytes is None

def test_select_visible_current_entries_sorts_by_modified_with_missing_values_last() -> None:
    state = replace(
        build_initial_app_state(),
        current_pane=pane(
            TEST_PROJECT_ROOT,
            (
                entry(
                    TEST_PROJECT_ROOT + '/alpha.txt',
                    modified_at=None,
                ),
                entry(
                    TEST_PROJECT_ROOT + '/beta.txt',
                    modified_at=build_initial_app_state().current_pane.entries[3].modified_at,
                ),
                entry(
                    TEST_PROJECT_ROOT + '/gamma.txt',
                    modified_at=build_initial_app_state().current_pane.entries[4].modified_at,
                ),
            ),
            cursor_path=TEST_PROJECT_ROOT + '/alpha.txt',
        ),
        sort=replace(build_initial_app_state().sort, field="modified", descending=True),
    )

    entries = select_visible_current_entry_states(state)

    assert [entry.name for entry in entries] == ["alpha.txt", "beta.txt", "gamma.txt"]

def test_select_visible_current_entries_sorts_by_size_without_directories_first() -> None:
    state = replace(
        build_initial_app_state(),
        current_pane=pane(
            TEST_PROJECT_ROOT,
            (
                entry(TEST_PROJECT_ROOT + '/docs', kind="dir"),
                entry(TEST_PROJECT_ROOT + '/alpha.txt', size_bytes=500),
                entry(TEST_PROJECT_ROOT + '/beta.txt', size_bytes=2_000),
            ),
            cursor_path=TEST_PROJECT_ROOT + '/docs',
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

def test_detect_preview_disabled_message_returns_none_for_directory() -> None:
    """Test that preview disabled message is None for directories."""
    from zivo.state.selectors_panes import _detect_preview_disabled_message

    entry = DirectoryEntryState(TEST_HOME + '/docs', "docs", "dir")
    message = _detect_preview_disabled_message(
        entry,
        enable_text_preview=False,
        enable_image_preview=False,
        enable_pdf_preview=False,
        enable_office_preview=False,
    )
    assert message is None

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

    entry = DirectoryEntryState(TEST_HOME + '/docs/test.pdf', "test.pdf", "file")
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
        TEST_HOME + '/docs/test.docx', "test.docx", "file"
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
        TEST_HOME + '/docs/test.xlsx', "test.xlsx", "file"
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
        TEST_HOME + '/docs/test.pptx', "test.pptx", "file"
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

    entry = DirectoryEntryState(TEST_HOME + '/docs/test.txt', "test.txt", "file")
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

    entry = DirectoryEntryState(TEST_HOME + '/docs/test.png', "test.png", "file")
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

    entry = DirectoryEntryState(TEST_HOME + '/docs/test.txt', "test.txt", "file")
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

    entry = DirectoryEntryState(TEST_HOME + '/docs/test.txt', "test.txt", "file")
    message = _detect_preview_disabled_message(
        entry,
        enable_text_preview=True,
        enable_image_preview=True,
        enable_pdf_preview=True,
        enable_office_preview=True,
    )
    assert message is None

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
    assert fallback.status.actions[0].action_id == "open_preview_default_app"
    assert fallback.status.actions[0].label == "Open with default app"
    assert fallback.status.actions[0].target_path == target
    assert [(item.label, item.value) for item in fallback.metadata] == [
        ("Name", "data.bin"),
        ("Type", "BIN"),
        ("Size", "2.0KiB"),
        ("Owner/group", "alice/staff"),
    ]
