from dataclasses import replace

from tests.state_test_helpers import reduce_state
from zivo.models import (
    ExternalLaunchRequest,
)
from zivo.state import (
    CommandPaletteState,
    DirectoryEntryState,
    FileSearchResultState,
    GrepSearchResultState,
    LoadBrowserSnapshotEffect,
    LoadChildPaneSnapshotEffect,
    NotificationState,
    PaneState,
    RunDirectorySizeEffect,
    RunExternalLaunchEffect,
    RunFileSearchEffect,
    RunGrepSearchEffect,
    build_initial_app_state,
    reduce_app_state,
)
from zivo.state.actions import (
    BeginCommandPalette,
    BeginFileSearch,
    BeginGrepSearch,
    BeginSelectedFilesGrep,
    CancelCommandPalette,
    CycleSelectedFilesGrepField,
    FileSearchCompleted,
    FileSearchFailed,
    GrepSearchCompleted,
    GrepSearchFailed,
    OpenFindResultInEditor,
    OpenGrepResultInEditor,
    SelectedFilesGrepKeywordChanged,
    SetCommandPaletteQuery,
    SetGrepSearchField,
    SubmitCommandPalette,
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


def test_open_find_result_in_editor_emits_external_launch_effect() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFileSearch())
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            query="readme",
            file_search_results=(
                FileSearchResultState(
                    path="/home/tadashi/develop/zivo/README.md",
                    display_path="README.md",
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
                path="/home/tadashi/develop/zivo/README.md",
                line_number=None,
            ),
        ),
    )

def test_open_grep_result_in_editor_keeps_palette_state() -> None:
    state = _reduce_state(build_initial_app_state(), BeginGrepSearch())
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            query="reduce_app_state",
            grep_search_results=(
                GrepSearchResultState(
                    path="/home/tadashi/develop/zivo/src/zivo/state/reducer.py",
                    display_path="src/zivo/state/reducer.py",
                    line_number=15,
                    line_text=(
                        "def reduce_app_state("
                        "state: AppState, action: Action"
                        ") -> ReduceResult:"
                    ),
                ),
            ),
            cursor_index=0,
        ),
    )

    result = reduce_app_state(state, OpenGrepResultInEditor())

    assert result.state.ui_mode == "PALETTE"
    assert result.state.next_request_id == 2
    assert result.state.command_palette == state.command_palette
    assert result.effects == (
        RunExternalLaunchEffect(
            request_id=1,
            request=ExternalLaunchRequest(
                kind="open_editor",
                path="/home/tadashi/develop/zivo/src/zivo/state/reducer.py",
                line_number=15,
            ),
        ),
    )

def test_begin_file_search_enters_find_file_mode() -> None:
    next_state = _reduce_state(build_initial_app_state(), BeginFileSearch())

    assert next_state.ui_mode == "PALETTE"
    assert next_state.command_palette == CommandPaletteState(source="file_search")

def test_begin_grep_search_enters_grep_mode() -> None:
    next_state = _reduce_state(build_initial_app_state(), BeginGrepSearch())

    assert next_state.ui_mode == "PALETTE"
    assert next_state.command_palette == CommandPaletteState(source="grep_search")

def test_submit_command_palette_begins_file_search() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("find files"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.ui_mode == "PALETTE"
    assert result.state.command_palette is not None
    assert result.state.command_palette.source == "file_search"

def test_submit_command_palette_begins_grep_search() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("grep search"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.ui_mode == "PALETTE"
    assert result.state.command_palette is not None
    assert result.state.command_palette.source == "grep_search"

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
            root_path="/home/tadashi/develop/zivo",
            query="read",
            show_hidden=False,
        ),
    )

def test_set_command_palette_query_starts_grep_search_effect() -> None:
    state = _reduce_state(build_initial_app_state(), BeginGrepSearch())

    result = reduce_app_state(state, SetCommandPaletteQuery("todo"))

    assert result.state.command_palette is not None
    assert result.state.command_palette.source == "grep_search"
    assert result.state.command_palette.query == "todo"
    assert result.state.pending_grep_search_request_id == 1
    assert result.effects == (
        RunGrepSearchEffect(
            request_id=1,
            root_path="/home/tadashi/develop/zivo",
            query="todo",
            show_hidden=False,
            include_globs=(),
            exclude_globs=(),
        ),
    )

def test_set_grep_search_field_builds_include_and_exclude_globs() -> None:
    state = _reduce_state(build_initial_app_state(), BeginGrepSearch())
    state = _reduce_state(state, SetCommandPaletteQuery("todo"))

    result = reduce_app_state(state, SetGrepSearchField(field="include", value="py, ts"))
    result = reduce_app_state(result.state, SetGrepSearchField(field="exclude", value=".log"))

    assert result.state.command_palette is not None
    assert result.state.command_palette.grep_search_include_extensions == "py, ts"
    assert result.state.command_palette.grep_search_exclude_extensions == ".log"
    assert result.effects == (
        RunGrepSearchEffect(
            request_id=3,
            root_path="/home/tadashi/develop/zivo",
            query="todo",
            show_hidden=False,
            include_globs=("*.py", "*.ts"),
            exclude_globs=("*.log",),
        ),
    )

def test_set_grep_search_filename_filter_updates_palette_and_requests_search() -> None:
    state = _reduce_state(build_initial_app_state(), BeginGrepSearch())
    state = _reduce_state(state, SetCommandPaletteQuery("todo"))

    result = reduce_app_state(state, SetGrepSearchField(field="filename", value="readme"))

    assert result.state.command_palette is not None
    assert result.state.command_palette.grep_search_filename_filter == "readme"
    assert result.effects == (
        RunGrepSearchEffect(
            request_id=2,
            root_path="/home/tadashi/develop/zivo",
            query="todo",
            show_hidden=False,
            include_globs=(),
            exclude_globs=(),
        ),
    )

def test_grep_search_completed_filters_results_by_filename() -> None:
    state = _reduce_state(build_initial_app_state(), BeginGrepSearch())
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            grep_search_keyword="todo",
            grep_search_filename_filter="readme",
        ),
        pending_grep_search_request_id=4,
    )
    results = (
        GrepSearchResultState(
            path="/home/tadashi/develop/zivo/README.md",
            display_path="README.md",
            line_number=1,
            line_text="TODO",
        ),
        GrepSearchResultState(
            path="/home/tadashi/develop/zivo/docs/guide.md",
            display_path="docs/guide.md",
            line_number=2,
            line_text="TODO",
        ),
    )

    result = reduce_app_state(
        state,
        GrepSearchCompleted(request_id=4, query="todo", results=results),
    )

    assert result.state.command_palette is not None
    assert result.state.command_palette.grep_search_results == (results[0],)
    assert result.state.pending_grep_search_request_id is None

def test_grep_search_completed_filters_results_by_filename_regex() -> None:
    state = _reduce_state(build_initial_app_state(), BeginGrepSearch())
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            grep_search_keyword="todo",
            grep_search_filename_filter="re:^docs/.+\\.md$",
        ),
        pending_grep_search_request_id=4,
    )
    results = (
        GrepSearchResultState(
            path="/home/tadashi/develop/zivo/README.md",
            display_path="README.md",
            line_number=1,
            line_text="TODO",
        ),
        GrepSearchResultState(
            path="/home/tadashi/develop/zivo/docs/guide.md",
            display_path="docs/guide.md",
            line_number=2,
            line_text="TODO",
        ),
    )

    result = reduce_app_state(
        state,
        GrepSearchCompleted(request_id=4, query="todo", results=results),
    )

    assert result.state.command_palette is not None
    assert result.state.command_palette.grep_search_results == (results[1],)

def test_set_grep_search_field_rejects_conflicting_extensions() -> None:
    state = _reduce_state(build_initial_app_state(), BeginGrepSearch())
    state = _reduce_state(state, SetCommandPaletteQuery("todo"))
    state = _reduce_state(state, SetGrepSearchField(field="include", value="py"))

    result = reduce_app_state(state, SetGrepSearchField(field="exclude", value=".py"))

    assert result.state.command_palette is not None
    assert result.state.command_palette.grep_search_results == ()
    assert (
        result.state.command_palette.grep_search_error_message
        == "Extensions cannot be included and excluded at the same time: py"
    )
    assert result.state.pending_grep_search_request_id is None
    assert result.effects == ()

def test_set_grep_search_field_rejects_invalid_extension_input() -> None:
    state = _reduce_state(build_initial_app_state(), BeginGrepSearch())
    state = _reduce_state(state, SetCommandPaletteQuery("todo"))

    result = reduce_app_state(state, SetGrepSearchField(field="include", value="*.py"))

    assert result.state.command_palette is not None
    assert (
        result.state.command_palette.grep_search_error_message
        == "Invalid include extension: *.py"
    )
    assert result.effects == ()

def test_set_grep_search_field_clears_results_when_keyword_becomes_empty() -> None:
    state = _reduce_state(build_initial_app_state(), BeginGrepSearch())
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            query="todo",
            grep_search_keyword="todo",
            grep_search_results=(
                GrepSearchResultState(
                    path="/home/tadashi/develop/zivo/README.md",
                    display_path="README.md",
                    line_number=1,
                    line_text="TODO",
                ),
            ),
        ),
        pending_grep_search_request_id=4,
        pending_child_pane_request_id=7,
    )

    result = reduce_app_state(state, SetGrepSearchField(field="keyword", value=""))

    assert result.state.command_palette is not None
    assert result.state.command_palette.grep_search_results == ()
    assert result.state.command_palette.grep_search_error_message is None
    assert result.state.pending_grep_search_request_id is None
    assert result.state.pending_child_pane_request_id is None
    assert result.effects == ()

def test_set_command_palette_query_reuses_completed_file_search_results_for_prefix_extension(
) -> None:
    state = _reduce_state(build_initial_app_state(), BeginFileSearch())
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            query="read",
            file_search_results=(
                FileSearchResultState(
                    path="/home/tadashi/develop/zivo/README.md",
                    display_path="README.md",
                ),
                FileSearchResultState(
                    path="/home/tadashi/develop/zivo/docs/readings.txt",
                    display_path="docs/readings.txt",
                ),
            ),
            file_search_cache_query="read",
            file_search_cache_results=(
                FileSearchResultState(
                    path="/home/tadashi/develop/zivo/README.md",
                    display_path="README.md",
                ),
                FileSearchResultState(
                    path="/home/tadashi/develop/zivo/docs/readings.txt",
                    display_path="docs/readings.txt",
                ),
            ),
            file_search_cache_root_path="/home/tadashi/develop/zivo",
            file_search_cache_show_hidden=False,
        ),
        pending_file_search_request_id=4,
        next_request_id=5,
    )

    result = reduce_app_state(state, SetCommandPaletteQuery("readm"))

    assert result.effects == (
        LoadChildPaneSnapshotEffect(
            request_id=5,
            current_path="/home/tadashi/develop/zivo",
            cursor_path="/home/tadashi/develop/zivo/README.md",
        ),
    )
    assert result.state.pending_file_search_request_id is None
    assert result.state.pending_child_pane_request_id == 5
    assert result.state.command_palette is not None
    assert result.state.command_palette.file_search_results == (
        FileSearchResultState(
            path="/home/tadashi/develop/zivo/README.md",
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
            file_search_results=(
                FileSearchResultState(
                    path="/home/tadashi/develop/zivo/README.md",
                    display_path="README.md",
                ),
            ),
            file_search_cache_query="read",
            file_search_cache_results=(
                FileSearchResultState(
                    path="/home/tadashi/develop/zivo/README.md",
                    display_path="README.md",
                ),
            ),
            file_search_cache_root_path="/home/tadashi/develop/zivo",
            file_search_cache_show_hidden=False,
        ),
        next_request_id=4,
    )

    result = reduce_app_state(state, SetCommandPaletteQuery("rea"))

    assert result.state.pending_file_search_request_id == 4
    assert result.effects == (
        RunFileSearchEffect(
            request_id=4,
            root_path="/home/tadashi/develop/zivo",
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
            file_search_cache_query="read",
            file_search_cache_results=(
                FileSearchResultState(
                    path="/home/tadashi/develop/zivo/README.md",
                    display_path="README.md",
                ),
            ),
            file_search_cache_root_path="/home/tadashi/develop/zivo",
            file_search_cache_show_hidden=False,
        ),
        next_request_id=4,
    )

    result = reduce_app_state(state, SetCommandPaletteQuery(r"re:^README\.md$"))

    assert result.state.pending_file_search_request_id == 4
    assert result.effects == (
        RunFileSearchEffect(
            request_id=4,
            root_path="/home/tadashi/develop/zivo",
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
                    path="/home/tadashi/develop/zivo/README.md",
                    display_path="README.md",
                ),
            ),
        ),
    )

    assert next_state.command_palette is not None
    assert next_state.command_palette.file_search_results == (
        FileSearchResultState(
            path="/home/tadashi/develop/zivo/README.md",
            display_path="README.md",
        ),
    )
    assert next_state.command_palette.file_search_cache_query == "read"
    assert next_state.command_palette.file_search_cache_root_path == "/home/tadashi/develop/zivo"
    assert next_state.command_palette.file_search_cache_show_hidden is False
    assert next_state.pending_file_search_request_id is None

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
                    path="/home/tadashi/develop/zivo/README.md",
                    display_path="README.md",
                ),
            ),
        ),
    )

    assert next_state.command_palette is not None
    assert next_state.command_palette.file_search_results == (
        FileSearchResultState(
            path="/home/tadashi/develop/zivo/README.md",
            display_path="README.md",
        ),
    )
    assert next_state.command_palette.file_search_cache_query == ""
    assert next_state.command_palette.file_search_cache_results == ()

def test_file_search_failed_sets_inline_error_for_invalid_regex() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFileSearch())
    search_state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            query="re:[",
            file_search_results=(
                FileSearchResultState(
                    path="/home/tadashi/develop/zivo/README.md",
                    display_path="README.md",
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
    assert next_state.command_palette.file_search_results == ()
    assert (
        next_state.command_palette.file_search_error_message
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
            file_search_error_message="Invalid regex: unterminated character set",
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
            file_search_results=(
                FileSearchResultState(
                    path="/home/tadashi/develop/zivo/docs/README.md",
                    display_path="docs/README.md",
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
            path="/home/tadashi/develop/zivo/docs",
            cursor_path="/home/tadashi/develop/zivo/docs/README.md",
            blocking=True,
        ),
    )

def test_grep_search_completed_updates_palette_results() -> None:
    state = _reduce_state(build_initial_app_state(), BeginGrepSearch())
    search_state = replace(
        state,
        command_palette=replace(state.command_palette, query="todo"),
        pending_grep_search_request_id=4,
    )

    next_state = _reduce_state(
        search_state,
        GrepSearchCompleted(
            request_id=4,
            query="todo",
            results=(
                GrepSearchResultState(
                    path="/home/tadashi/develop/zivo/src/zivo/app.py",
                    display_path="src/zivo/app.py",
                    line_number=42,
                    line_text="TODO: update palette",
                ),
            ),
        ),
    )

    assert next_state.command_palette is not None
    assert next_state.command_palette.grep_search_results == (
        GrepSearchResultState(
            path="/home/tadashi/develop/zivo/src/zivo/app.py",
            display_path="src/zivo/app.py",
            line_number=42,
            line_text="TODO: update palette",
        ),
    )
    assert next_state.pending_grep_search_request_id is None

def test_grep_search_completed_requests_context_preview() -> None:
    state = _reduce_state(build_initial_app_state(), BeginGrepSearch())
    search_state = replace(
        state,
        command_palette=replace(state.command_palette, query="todo"),
        pending_grep_search_request_id=4,
    )
    grep_result = GrepSearchResultState(
        path="/home/tadashi/develop/zivo/src/zivo/app.py",
        display_path="src/zivo/app.py",
        line_number=42,
        line_text="TODO: update palette",
    )

    result = reduce_app_state(
        search_state,
        GrepSearchCompleted(
            request_id=4,
            query="todo",
            results=(grep_result,),
        ),
    )

    assert result.state.pending_child_pane_request_id == 1
    assert result.effects == (
        LoadChildPaneSnapshotEffect(
            request_id=1,
            current_path="/home/tadashi/develop/zivo",
            cursor_path="/home/tadashi/develop/zivo/src/zivo/app.py",
            grep_result=grep_result,
            grep_context_lines=3,
        ),
    )

def test_grep_search_completed_skips_context_preview_when_preview_disabled() -> None:
    grep_result = GrepSearchResultState(
        path="/home/tadashi/develop/zivo/src/zivo/app.py",
        display_path="src/zivo/app.py",
        line_number=42,
        line_text="TODO: update palette",
    )
    search_state = replace(
        _reduce_state(build_initial_app_state(), BeginGrepSearch()),
        config=replace(
            build_initial_app_state().config,
            display=replace(build_initial_app_state().config.display, enable_text_preview=False),
        ),
        command_palette=replace(
            _reduce_state(build_initial_app_state(), BeginGrepSearch()).command_palette,
            query="todo",
        ),
        pending_grep_search_request_id=4,
    )

    result = reduce_app_state(
        search_state,
        GrepSearchCompleted(
            request_id=4,
            query="todo",
            results=(grep_result,),
        ),
    )

    assert result.state.config.display.enable_text_preview is False
    assert result.state.pending_child_pane_request_id is None
    assert result.effects == ()

def test_grep_search_failed_sets_inline_error_for_invalid_regex() -> None:
    state = _reduce_state(build_initial_app_state(), BeginGrepSearch())
    search_state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            query="re:[",
            grep_search_results=(
                GrepSearchResultState(
                    path="/home/tadashi/develop/zivo/src/zivo/app.py",
                    display_path="src/zivo/app.py",
                    line_number=42,
                    line_text="TODO: update palette",
                ),
            ),
        ),
        pending_grep_search_request_id=4,
    )

    next_state = _reduce_state(
        search_state,
        GrepSearchFailed(
            request_id=4,
            query="re:[",
            message="regex parse error",
            invalid_query=True,
        ),
    )

    assert next_state.command_palette is not None
    assert next_state.command_palette.grep_search_results == ()
    assert next_state.command_palette.grep_search_error_message == "regex parse error"
    assert next_state.pending_grep_search_request_id is None

def test_submit_command_palette_grep_result_requests_snapshot() -> None:
    state = _reduce_state(build_initial_app_state(), BeginGrepSearch())
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            query="todo",
            grep_search_results=(
                GrepSearchResultState(
                    path="/home/tadashi/develop/zivo/src/zivo/app.py",
                    display_path="src/zivo/app.py",
                    line_number=42,
                    line_text="TODO: update palette",
                ),
            ),
            cursor_index=0,
        ),
    )

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.ui_mode == "BUSY"
    assert result.effects == (
        LoadBrowserSnapshotEffect(
            request_id=1,
            path="/home/tadashi/develop/zivo/src/zivo",
            cursor_path="/home/tadashi/develop/zivo/src/zivo/app.py",
            blocking=True,
        ),
    )

def test_cancel_grep_command_palette_restores_current_cursor_preview() -> None:
    path = "/home/tadashi/develop/zivo/README.md"
    grep_result = GrepSearchResultState(
        path=path,
        display_path="README.md",
        line_number=3,
        line_text="TODO: update docs",
    )
    state = replace(
        _reduce_state(build_initial_app_state(), BeginGrepSearch()),
        current_pane=replace(build_initial_app_state().current_pane, cursor_path=path),
        command_palette=CommandPaletteState(
            source="grep_search",
            query="todo",
            grep_search_results=(grep_result,),
        ),
        child_pane=PaneState(
            directory_path="/home/tadashi/develop/zivo",
            entries=(),
            mode="preview",
            preview_path=path,
            preview_title="Preview: README.md:3",
            preview_content="TODO: update docs\n",
            preview_start_line=3,
            preview_highlight_line=3,
        ),
    )

    result = reduce_app_state(state, CancelCommandPalette())

    assert result.state.ui_mode == "BROWSING"
    assert result.state.pending_child_pane_request_id == 1
    assert result.effects == (
        LoadChildPaneSnapshotEffect(
            request_id=1,
            current_path="/home/tadashi/develop/zivo",
            cursor_path=path,
        ),
        RunDirectorySizeEffect(
            request_id=2,
            paths=(
                "/home/tadashi/develop/zivo/docs",
                "/home/tadashi/develop/zivo/src",
                "/home/tadashi/develop/zivo/tests",
            ),
        ),
    )



def test_begin_selected_files_grep_with_multiple_selection() -> None:
    """Test opening selected-files-grep with multiple files selected."""
    state = _reduce_state(
        build_initial_app_state(),
        BeginSelectedFilesGrep(
            target_paths=(
                "/home/tadashi/develop/zivo/src/main.py",
                "/home/tadashi/develop/zivo/src/utils.py",
            )
        ),
    )

    assert state.ui_mode == "PALETTE"
    assert state.command_palette is not None
    assert state.command_palette.source == "selected_files_grep"
    assert state.command_palette.sfg_target_paths == (
        "/home/tadashi/develop/zivo/src/main.py",
        "/home/tadashi/develop/zivo/src/utils.py",
    )
    assert state.command_palette.sfg_keyword == ""
    assert state.command_palette.sfg_results == ()


def test_begin_selected_files_grep_with_single_file() -> None:
    """Test opening selected-files-grep with a single file selected."""
    state = _reduce_state(
        build_initial_app_state(),
        BeginSelectedFilesGrep(
            target_paths=("/home/tadashi/develop/zivo/README.md",)
        ),
    )

    assert state.ui_mode == "PALETTE"
    assert state.command_palette is not None
    assert state.command_palette.source == "selected_files_grep"
    assert state.command_palette.sfg_target_paths == ("/home/tadashi/develop/zivo/README.md",)


def test_begin_selected_files_grep_with_empty_selection() -> None:
    """Test opening selected-files-grep with no files selected."""
    state = _reduce_state(
        build_initial_app_state(),
        BeginSelectedFilesGrep(target_paths=()),
    )

    assert state.ui_mode == "PALETTE"
    assert state.command_palette is not None
    assert state.command_palette.source == "selected_files_grep"
    assert state.command_palette.sfg_target_paths == ()


def test_sfg_keyword_triggers_search() -> None:
    """Test that keyword change triggers grep search."""
    target_paths = ("/path/to/file.py",)
    state = _reduce_state(
        build_initial_app_state(),
        BeginSelectedFilesGrep(target_paths=target_paths)
    )
    state = replace(
        state,
        current_pane=replace(
            state.current_pane,
            entries=(
                DirectoryEntryState(
                    "/path/to/file.py",
                    "file.py",
                    "file",
                ),
            ),
        ),
    )

    result = reduce_app_state(
        state,
        SelectedFilesGrepKeywordChanged(keyword="test"),
    )

    assert result.state.command_palette is not None
    assert result.state.command_palette.sfg_keyword == "test"
    assert result.state.pending_grep_search_request_id == 1
    assert len(result.effects) == 1
    effect = result.effects[0]
    assert isinstance(effect, RunGrepSearchEffect)
    assert effect.query == "test"
    assert effect.root_path == state.current_path


def test_sfg_empty_keyword_clears_results() -> None:
    """Test that empty keyword clears results."""
    target_paths = ("/path/to/file.py",)
    state = _reduce_state(
        build_initial_app_state(),
        BeginSelectedFilesGrep(target_paths=target_paths)
    )
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            sfg_keyword="test",
            sfg_results=(
                GrepSearchResultState(
                    path="/path/to/file.py",
                    display_path="file.py",
                    line_number=1,
                    line_text="test line",
                ),
            ),
        ),
        pending_grep_search_request_id=1,
    )

    result = reduce_app_state(
        state,
        SelectedFilesGrepKeywordChanged(keyword=""),
    )

    assert result.state.command_palette is not None
    assert result.state.command_palette.sfg_keyword == ""
    assert result.state.command_palette.sfg_results == ()
    assert result.state.pending_grep_search_request_id is None


def test_sfg_filters_results_by_target_paths() -> None:
    """Test that search results are filtered by target paths."""
    target_paths = (
        "/home/tadashi/develop/zivo/src/main.py",
        "/home/tadashi/develop/zivo/src/utils.py",
    )
    state = _reduce_state(
        build_initial_app_state(),
        BeginSelectedFilesGrep(target_paths=target_paths),
    )
    state = replace(state, pending_grep_search_request_id=1)

    result = reduce_app_state(
        state,
        GrepSearchCompleted(
            query="test",
            request_id=1,
            results=(
                GrepSearchResultState(
                    path="/home/tadashi/develop/zivo/src/main.py",
                    display_path="src/main.py",
                    line_number=10,
                    line_text="def main():",
                ),
                GrepSearchResultState(
                    path="/home/tadashi/develop/zivo/src/other.py",
                    display_path="src/other.py",
                    line_number=5,
                    line_text="def other():",
                ),
                GrepSearchResultState(
                    path="/home/tadashi/develop/zivo/src/utils.py",
                    display_path="src/utils.py",
                    line_number=20,
                    line_text="def utils():",
                ),
            ),
        ),
    )

    assert result.state.command_palette is not None
    assert result.state.command_palette.sfg_results == (
        GrepSearchResultState(
            path="/home/tadashi/develop/zivo/src/main.py",
            display_path="src/main.py",
            line_number=10,
            line_text="def main():",
        ),
        GrepSearchResultState(
            path="/home/tadashi/develop/zivo/src/utils.py",
            display_path="src/utils.py",
            line_number=20,
            line_text="def utils():",
        ),
    )
    # other.py should be filtered out as it's not in target_paths
    assert len(result.state.command_palette.sfg_results) == 2


def test_sfg_grep_search_failed_with_invalid_query() -> None:
    """Test that invalid query shows error message."""
    target_paths = ("/path/to/file.py",)
    state = _reduce_state(
        build_initial_app_state(),
        BeginSelectedFilesGrep(target_paths=target_paths)
    )
    state = replace(state, pending_grep_search_request_id=1)

    result = reduce_app_state(
        state,
        GrepSearchFailed(
            query="test",
            request_id=1,
            message="Invalid regex pattern",
            invalid_query=True,
        ),
    )

    assert result.state.command_palette is not None
    assert result.state.command_palette.sfg_error_message == "Invalid regex pattern"
    assert result.state.command_palette.sfg_results == ()


def test_sfg_cycle_field_is_noop() -> None:
    """Test that cycling fields is a no-op since only keyword field exists."""
    target_paths = ("/path/to/file.py",)
    state = _reduce_state(
        build_initial_app_state(),
        BeginSelectedFilesGrep(target_paths=target_paths)
    )

    result = reduce_app_state(state, CycleSelectedFilesGrepField(delta=1))

    assert result.state.command_palette is not None
    assert result.state.command_palette.sfg_active_field == "keyword"
    assert result.state == state  # No changes expected


def test_grep_filename_filter_with_invalid_regex_single_backslash() -> None:
    """Test that single backslash in regex mode shows error and clears results."""
    state = _reduce_state(build_initial_app_state(), BeginGrepSearch())
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            grep_search_keyword="test",
            grep_search_results=(
                GrepSearchResultState(
                    path="/home/test/file.py",
                    display_path="file.py",
                    line_number=1,
                    line_text="test content",
                ),
            ),
        ),
    )

    result = reduce_app_state(state, SetGrepSearchField(field="filename", value="re:\\"))

    assert result.state.command_palette is not None
    assert result.state.command_palette.grep_search_filename_filter == "re:\\"
    assert result.state.command_palette.grep_search_error_message is not None
    assert "Invalid regex pattern" in result.state.command_palette.grep_search_error_message
    assert result.state.command_palette.grep_search_results == ()


def test_grep_filename_filter_with_invalid_regex_unclosed_char_class() -> None:
    """Test that invalid regex (unclosed character class) shows error and clears results."""
    state = _reduce_state(build_initial_app_state(), BeginGrepSearch())
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            grep_search_keyword="test",
            grep_search_results=(
                GrepSearchResultState(
                    path="/home/test/file.py",
                    display_path="file.py",
                    line_number=1,
                    line_text="test content",
                ),
            ),
        ),
    )

    result = reduce_app_state(state, SetGrepSearchField(field="filename", value="re:["))

    assert result.state.command_palette is not None
    assert result.state.command_palette.grep_search_filename_filter == "re:["
    assert result.state.command_palette.grep_search_error_message is not None
    assert "Invalid regex pattern" in result.state.command_palette.grep_search_error_message
    assert result.state.command_palette.grep_search_results == ()


def test_grep_filename_filter_with_valid_regex_backslash() -> None:
    """Test that valid regex with backslash works correctly."""
    state = _reduce_state(build_initial_app_state(), BeginGrepSearch())
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            grep_search_keyword="test",
            grep_search_results=(
                GrepSearchResultState(
                    path="/home/test/file.py",
                    display_path="file.py",
                    line_number=1,
                    line_text="test content",
                ),
                GrepSearchResultState(
                    path="/home/test/file.txt",
                    display_path="file.txt",
                    line_number=1,
                    line_text="test content",
                ),
            ),
        ),
    )

    result = reduce_app_state(state, SetGrepSearchField(field="filename", value="re:\\.py$"))

    assert result.state.command_palette is not None
    assert result.state.command_palette.grep_search_filename_filter == "re:\\.py$"
    assert result.state.command_palette.grep_search_error_message is None
    assert len(result.state.command_palette.grep_search_results) == 1
    assert result.state.command_palette.grep_search_results[0].display_path == "file.py"


def test_grep_filename_filter_with_non_regex_backslash() -> None:
    """Test that backslash in non-regex mode works correctly."""
    state = _reduce_state(build_initial_app_state(), BeginGrepSearch())
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            grep_search_keyword="test",
            grep_search_results=(
                GrepSearchResultState(
                    path="/home/test/file.py",
                    display_path="file.py",
                    line_number=1,
                    line_text="test content",
                ),
            ),
        ),
    )

    result = reduce_app_state(state, SetGrepSearchField(field="filename", value="\\"))

    assert result.state.command_palette is not None
    assert result.state.command_palette.grep_search_filename_filter == "\\"
    assert result.state.command_palette.grep_search_error_message is None
    # Non-regex mode should not crash, results may be empty or filtered
    assert isinstance(result.state.command_palette.grep_search_results, tuple)
