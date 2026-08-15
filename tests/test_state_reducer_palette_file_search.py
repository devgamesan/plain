"""Test State Reducer Palette File Search tests."""
from tests.support.paths import TEST_PROJECT_ROOT
from tests.support.reducer_palette_search import (
    BeginCommandPalette,
    BeginFileSearch,
    BeginGrepSearch,
    CommandPaletteState,
    DirectoryEntryState,
    ExternalLaunchRequest,
    FileSearchCompleted,
    FileSearchFailed,
    FileSearchResultState,
    FileSearchResultsUpdated,
    GrepSearchCompleted,
    GrepSearchResultState,
    LoadBrowserSnapshotEffect,
    LoadChildPaneSnapshotEffect,
    NotificationState,
    OpenFindResultInEditor,
    OpenFindResultInGuiEditor,
    OpenSearchWorkspace,
    PaneState,
    RunExternalLaunchEffect,
    RunFileSearchEffect,
    RunGrepSearchEffect,
    SetCommandPaletteQuery,
    SetFileSearchField,
    SetFileSearchTarget,
    SetGrepSearchScope,
    SubmitCommandPalette,
    _reduce_state,
    build_initial_app_state,
    reduce_app_state,
    replace,
)


def test_open_find_result_in_editor_emits_external_launch_effect() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFileSearch())
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            query="readme",
            file_search=replace(
                state.command_palette.file_search,
                results=(
                    FileSearchResultState(
                        path=TEST_PROJECT_ROOT + '/README.md',
                        display_path="README.md",
                    ),
                ),
            ),
            cursor_index=0,
        ),
    )

    result = reduce_app_state(state, OpenFindResultInEditor())

    assert result.state.ui_mode == "PALETTE"
    assert result.state.next_request_id == 2
    assert result.state.command_palette == state.command_palette
    assert result.effects == (
        RunExternalLaunchEffect(
            request_id=1,
            request=ExternalLaunchRequest(
                kind="open_editor",
                path=TEST_PROJECT_ROOT + '/README.md',
                line_number=None,
            ),
        ),
    )

def test_open_find_result_in_gui_editor_emits_external_launch_effect() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFileSearch())
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            query="readme",
            file_search=replace(
                state.command_palette.file_search,
                results=(
                    FileSearchResultState(
                        path=TEST_PROJECT_ROOT + '/README.md',
                        display_path="README.md",
                    ),
                ),
            ),
            cursor_index=0,
        ),
    )

    result = reduce_app_state(state, OpenFindResultInGuiEditor())

    assert result.effects == (
        RunExternalLaunchEffect(
            request_id=1,
            request=ExternalLaunchRequest(
                kind="open_gui_editor",
                path=TEST_PROJECT_ROOT + '/README.md',
            ),
        ),
    )

def test_begin_file_search_enters_find_file_mode() -> None:
    next_state = _reduce_state(build_initial_app_state(), BeginFileSearch())

    assert next_state.ui_mode == "PALETTE"
    assert next_state.command_palette == CommandPaletteState(source="file_search")

def test_selected_entries_scope_keeps_matches_under_selected_directories() -> None:
    directory_path = TEST_PROJECT_ROOT + '/docs'
    state = _reduce_state(
        build_initial_app_state(),
        BeginGrepSearch(scope="selected_entries", target_paths=(directory_path,)),
    )
    state = replace(state, pending_grep_search_request_id=1)

    result = reduce_app_state(
        state,
        GrepSearchCompleted(
            query="todo",
            request_id=1,
            results=(
                GrepSearchResultState(
                    path=f"{directory_path}/guide.md",
                    display_path="docs/guide.md",
                    line_number=1,
                    line_text="TODO: keep",
                ),
                GrepSearchResultState(
                    path=TEST_PROJECT_ROOT + '/README.md',
                    display_path="README.md",
                    line_number=1,
                    line_text="TODO: exclude",
                ),
            ),
        ),
    )

    assert [item.path for item in result.state.command_palette.grep_search.results] == [
        f"{directory_path}/guide.md"
    ]

def test_selected_entries_scope_passes_target_paths_to_search_effect() -> None:
    file_path = TEST_PROJECT_ROOT + '/README.md'
    directory_path = TEST_PROJECT_ROOT + '/docs'
    state = replace(
        build_initial_app_state(),
        current_pane=PaneState(
            directory_path=TEST_PROJECT_ROOT,
            entries=(
                DirectoryEntryState(file_path, "README.md", "file"),
                DirectoryEntryState(directory_path, "docs", "dir"),
            ),
            selected_paths=frozenset({file_path, directory_path}),
        ),
    )
    state = _reduce_state(state, BeginGrepSearch(scope="selected_entries"))

    result = reduce_app_state(state, SetCommandPaletteQuery("todo"))

    assert result.effects == (
        RunGrepSearchEffect(
            request_id=1,
            root_path=TEST_PROJECT_ROOT,
            query="todo",
            show_hidden=False,
            target_paths=(file_path, directory_path),
        ),
    )

def test_search_workspace_scope_is_rejected_outside_a_workspace() -> None:
    state = _reduce_state(build_initial_app_state(), BeginGrepSearch())

    result = reduce_app_state(state, SetGrepSearchScope(scope="search_workspace"))

    assert result.state.command_palette.grep_search.scope == "current_directory"
    assert result.state.notification is not None
    assert "Search Workspace" in result.state.notification.message

def test_submit_command_palette_begins_file_search() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("find files"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.ui_mode == "PALETTE"
    assert result.state.command_palette is not None
    assert result.state.command_palette.source == "file_search"

def test_set_command_palette_query_starts_file_search_effect() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFileSearch())

    result = reduce_app_state(state, SetCommandPaletteQuery("read"))

    assert result.state.command_palette is not None
    assert result.state.command_palette.source == "file_search"
    assert result.state.command_palette.query == "read"
    assert result.state.pending_file_search_request_id == 1
    assert result.effects == (
        RunFileSearchEffect(
            request_id=1,
            root_path=TEST_PROJECT_ROOT,
            query="read",
            show_hidden=False,
        ),
    )

def test_set_file_search_extension_field_starts_filtered_effect() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFileSearch())
    state = _reduce_state(state, SetCommandPaletteQuery("read"))

    result = reduce_app_state(
        state,
        SetFileSearchField(field="include", value="py, .JS"),
    )

    assert result.state.command_palette is not None
    assert result.state.command_palette.file_search.include_extensions == "py, .JS"
    assert result.effects == (
        RunFileSearchEffect(
            request_id=2,
            root_path=TEST_PROJECT_ROOT,
            query="read",
            show_hidden=False,
            include_extensions=("*.py", "*.js"),
        ),
    )

def test_file_search_extension_filter_allows_empty_keyword() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFileSearch())

    result = reduce_app_state(
        state,
        SetFileSearchField(field="include", value="py"),
    )

    assert result.state.command_palette is not None
    assert result.state.command_palette.query == ""
    assert result.effects == (
        RunFileSearchEffect(
            request_id=1,
            root_path=TEST_PROJECT_ROOT,
            query="",
            show_hidden=False,
            include_extensions=("*.py",),
        ),
    )

def test_file_search_extension_conflict_keeps_input_and_reports_error() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFileSearch())
    state = _reduce_state(state, SetFileSearchField(field="include", value="py"))

    result = reduce_app_state(
        state,
        SetFileSearchField(field="exclude", value=".PY"),
    )

    assert result.state.command_palette is not None
    assert result.state.command_palette.file_search.exclude_extensions == ".PY"
    assert result.state.command_palette.file_search.results == ()
    assert result.state.command_palette.file_search.error_message == (
        "Extensions cannot be included and excluded at the same time: py"
    )
    assert result.effects == ()

def test_file_search_extension_filter_rejects_directory_target() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFileSearch())
    state = _reduce_state(state, SetFileSearchField(field="include", value="py"))

    result = reduce_app_state(state, SetFileSearchTarget(target="directories"))

    assert result.state.command_palette is not None
    assert result.state.command_palette.file_search.target == "directories"
    assert result.state.command_palette.file_search.include_extensions == "py"
    assert result.state.command_palette.file_search.error_message == (
        "Extension filters require Target=files or all; clear the filters or change Target"
    )
    assert result.effects == ()

def test_open_file_search_workspace_keeps_extension_filter_identity() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFileSearch())
    state = _reduce_state(state, SetFileSearchField(field="include", value="py, js"))
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            file_search=replace(
                state.command_palette.file_search,
                results=(
                    FileSearchResultState(
                        path=TEST_PROJECT_ROOT + '/main.py',
                        display_path="main.py",
                    ),
                ),
            ),
        ),
    )

    result = reduce_app_state(state, OpenSearchWorkspace())

    assert len(result.state.search_workspaces) == 1
    workspace_path = next(iter(result.state.search_workspaces))
    assert "include=%2A.py%2C%2A.js" in workspace_path

def test_set_command_palette_query_reuses_completed_file_search_results_for_prefix_extension(
    ) -> None:
    state = _reduce_state(build_initial_app_state(), BeginFileSearch())
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            query="read",
            file_search=replace(
                state.command_palette.file_search,
                results=(
                    FileSearchResultState(
                        path=TEST_PROJECT_ROOT + '/README.md',
                        display_path="README.md",
                    ),
                    FileSearchResultState(
                        path=TEST_PROJECT_ROOT + '/docs/readings.txt',
                        display_path="docs/readings.txt",
                    ),
                ),
                cache_query="read",
                cache_results=(
                    FileSearchResultState(
                        path=TEST_PROJECT_ROOT + '/README.md',
                        display_path="README.md",
                    ),
                    FileSearchResultState(
                        path=TEST_PROJECT_ROOT + '/docs/readings.txt',
                        display_path="docs/readings.txt",
                    ),
                ),
                cache_root_path=TEST_PROJECT_ROOT,
                cache_show_hidden=False,
                cache_target="all",
            ),
        ),
        pending_file_search_request_id=4,
        next_request_id=5,
    )

    result = reduce_app_state(state, SetCommandPaletteQuery("readm"))

    assert result.effects == (
        LoadChildPaneSnapshotEffect(
            request_id=5,
            current_path=TEST_PROJECT_ROOT,
            cursor_path=TEST_PROJECT_ROOT + '/README.md',
        ),
    )
    assert result.state.pending_file_search_request_id is None
    assert result.state.pending_child_pane_request_id == 5
    assert result.state.command_palette is not None
    assert result.state.command_palette.file_search.results == (
        FileSearchResultState(
            path=TEST_PROJECT_ROOT + '/README.md',
            display_path="README.md",
        ),
    )
    assert result.state.next_request_id == 6

def test_set_command_palette_query_runs_new_search_when_query_is_not_prefix_extension() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFileSearch())
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            query="read",
            file_search=replace(
                state.command_palette.file_search,
                results=(
                    FileSearchResultState(
                        path=TEST_PROJECT_ROOT + '/README.md',
                        display_path="README.md",
                    ),
                ),
                cache_query="read",
                cache_results=(
                    FileSearchResultState(
                        path=TEST_PROJECT_ROOT + '/README.md',
                        display_path="README.md",
                    ),
                ),
                cache_root_path=TEST_PROJECT_ROOT,
                cache_show_hidden=False,
            ),
        ),
        next_request_id=4,
    )

    result = reduce_app_state(state, SetCommandPaletteQuery("rea"))

    assert result.state.pending_file_search_request_id == 4
    assert result.effects == (
        RunFileSearchEffect(
            request_id=4,
            root_path=TEST_PROJECT_ROOT,
            query="rea",
            show_hidden=False,
        ),
    )

def test_set_command_palette_query_runs_new_search_for_regex_queries() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFileSearch())
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            query="read",
            file_search=replace(
                state.command_palette.file_search,
                cache_query="read",
                cache_results=(
                    FileSearchResultState(
                        path=TEST_PROJECT_ROOT + '/README.md',
                        display_path="README.md",
                    ),
                ),
                cache_root_path=TEST_PROJECT_ROOT,
                cache_show_hidden=False,
            ),
        ),
        next_request_id=4,
    )

    result = reduce_app_state(state, SetCommandPaletteQuery(r"re:^README\.md$"))

    assert result.state.pending_file_search_request_id == 4
    assert result.effects == (
        RunFileSearchEffect(
            request_id=4,
            root_path=TEST_PROJECT_ROOT,
            query=r"re:^README\.md$",
            show_hidden=False,
        ),
    )

def test_file_search_completed_updates_palette_results() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFileSearch())
    search_state = replace(
        state,
        command_palette=replace(state.command_palette, query="read"),
        pending_file_search_request_id=4,
    )

    next_state = _reduce_state(
        search_state,
        FileSearchCompleted(
            request_id=4,
            query="read",
            results=(
                FileSearchResultState(
                    path=TEST_PROJECT_ROOT + '/README.md',
                    display_path="README.md",
                ),
            ),
        ),
    )

    assert next_state.command_palette is not None
    assert next_state.command_palette.file_search.results == (
        FileSearchResultState(
            path=TEST_PROJECT_ROOT + '/README.md',
            display_path="README.md",
        ),
    )
    assert next_state.command_palette.file_search.cache_query == "read"
    assert next_state.command_palette.file_search.cache_root_path == TEST_PROJECT_ROOT
    assert next_state.command_palette.file_search.cache_show_hidden is False
    assert next_state.pending_file_search_request_id is None

def test_file_search_partial_results_are_applied_and_keep_request_pending() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFileSearch())
    state = _reduce_state(state, SetCommandPaletteQuery("read"))

    result = reduce_app_state(
        state,
        FileSearchResultsUpdated(
            request_id=1,
            query="read",
            results=(
                FileSearchResultState(
                    path=TEST_PROJECT_ROOT + '/README.md',
                    display_path="README.md",
                ),
            ),
        ),
    )

    assert result.state.command_palette.file_search.results[0].display_path == "README.md"
    assert result.state.pending_file_search_request_id == 1
    assert result.state.command_palette.file_search.results_truncated is False

def test_file_search_streaming_results_keep_first_result_selected_without_navigation() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFileSearch())
    state = _reduce_state(state, SetCommandPaletteQuery("read"))
    state = _reduce_state(
        state,
        FileSearchResultsUpdated(
            request_id=1,
            query="read",
            results=(FileSearchResultState(path="/tmp/b.txt", display_path="b.txt"),),
        ),
    )

    result = reduce_app_state(
        state,
        FileSearchResultsUpdated(
            request_id=1,
            query="read",
            results=(FileSearchResultState(path="/tmp/a.txt", display_path="a.txt"),),
        ),
    )

    assert [item.display_path for item in result.state.command_palette.file_search.results] == [
        "a.txt",
        "b.txt",
    ]
    assert result.state.command_palette.cursor_index == 0

def test_file_search_partial_results_preserve_selected_path_when_sorted_order_changes() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFileSearch())
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            query="read",
            cursor_index=0,
            file_search=replace(
                state.command_palette.file_search,
                results=(
                    FileSearchResultState(path="/tmp/b.txt", display_path="b.txt"),
                ),
            ),
            cursor_navigation_active=True,
        ),
        pending_file_search_request_id=1,
    )

    result = reduce_app_state(
        state,
        FileSearchResultsUpdated(
            request_id=1,
            query="read",
            results=(FileSearchResultState(path="/tmp/a.txt", display_path="a.txt"),),
        ),
    )

    assert [item.display_path for item in result.state.command_palette.file_search.results] == [
        "a.txt",
        "b.txt",
    ]
    assert result.state.command_palette.cursor_index == 1

def test_file_search_truncation_is_visible_and_not_cached() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFileSearch())
    state = replace(
        state,
        command_palette=replace(state.command_palette, query="read"),
        pending_file_search_request_id=1,
    )

    next_state = _reduce_state(
        state,
        FileSearchCompleted(
            request_id=1,
            query="read",
            results=(FileSearchResultState(path="/tmp/README.md", display_path="README.md"),),
            truncated=True,
        ),
    )

    assert next_state.command_palette.file_search.results_truncated is True
    assert next_state.command_palette.file_search.cache_query == ""
    assert next_state.command_palette.file_search.cache_results == ()

def test_file_search_completed_does_not_cache_regex_queries() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFileSearch())
    search_state = replace(
        state,
        command_palette=replace(state.command_palette, query=r"re:^README\.md$"),
        pending_file_search_request_id=4,
    )

    next_state = _reduce_state(
        search_state,
        FileSearchCompleted(
            request_id=4,
            query=r"re:^README\.md$",
            results=(
                FileSearchResultState(
                    path=TEST_PROJECT_ROOT + '/README.md',
                    display_path="README.md",
                ),
            ),
        ),
    )

    assert next_state.command_palette is not None
    assert next_state.command_palette.file_search.results == (
        FileSearchResultState(
            path=TEST_PROJECT_ROOT + '/README.md',
            display_path="README.md",
        ),
    )
    assert next_state.command_palette.file_search.cache_query == ""
    assert next_state.command_palette.file_search.cache_results == ()

def test_file_search_failed_sets_inline_error_for_invalid_regex() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFileSearch())
    search_state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            query="re:[",
            file_search=replace(
                state.command_palette.file_search,
                results=(
                    FileSearchResultState(
                        path=TEST_PROJECT_ROOT + '/README.md',
                        display_path="README.md",
                    ),
                ),
            ),
        ),
        pending_file_search_request_id=4,
    )

    next_state = _reduce_state(
        search_state,
        FileSearchFailed(
            request_id=4,
            query="re:[",
            message="Invalid regex: unterminated character set",
            invalid_query=True,
        ),
    )

    assert next_state.command_palette is not None
    assert next_state.command_palette.file_search.results == ()
    assert (
        next_state.command_palette.file_search.error_message
        == "Invalid regex: unterminated character set"
    )
    assert next_state.notification is None
    assert next_state.pending_file_search_request_id is None

def test_submit_command_palette_uses_inline_error_message_when_present() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFileSearch())
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            query="re:[",
            file_search=replace(
                state.command_palette.file_search,
                error_message="Invalid regex: unterminated character set",
            ),
        ),
    )

    next_state = _reduce_state(state, SubmitCommandPalette())

    assert next_state.notification == NotificationState(
        level="warning",
        message="Invalid regex: unterminated character set",
    )

def test_submit_command_palette_file_search_result_requests_snapshot() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFileSearch())
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            query="read",
            file_search=replace(
                state.command_palette.file_search,
                results=(
                    FileSearchResultState(
                        path=TEST_PROJECT_ROOT + '/docs/README.md',
                        display_path="docs/README.md",
                    ),
                ),
            ),
            cursor_index=0,
        ),
    )

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.ui_mode == "BUSY"
    assert result.state.command_palette is None
    assert result.effects == (
        LoadBrowserSnapshotEffect(
            request_id=1,
            path=TEST_PROJECT_ROOT + '/docs',
            cursor_path=TEST_PROJECT_ROOT + '/docs/README.md',
            blocking=True,
        ),
    )
