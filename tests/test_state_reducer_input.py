"""Test State Reducer Input tests."""
from tests.support.paths import TEST_PROJECT_ROOT
from tests.support.reducer import (
    CancelFilterInput,
    ConfirmFilterInput,
    CopyPathsToClipboard,
    CopyTextToClipboard,
    DirectoryEntryState,
    DismissNameConflict,
    ExternalLaunchCompleted,
    ExternalLaunchFailed,
    ExternalLaunchRequest,
    LoadChildPaneSnapshotEffect,
    MoveCursor,
    MoveCursorAndSelectRange,
    NameConflictState,
    NotificationState,
    OpenPathInEditor,
    PaneState,
    PendingInputState,
    RunDirectorySizeEffect,
    RunExternalLaunchEffect,
    SetFilterQuery,
    SetUiMode,
    ToggleHiddenFiles,
    _reduce_state,
    build_initial_app_state,
    reduce_app_state,
    replace,
)


def test_copy_paths_to_clipboard_emits_external_launch_effect() -> None:
    result = reduce_app_state(build_initial_app_state(), CopyPathsToClipboard())

    assert result.state.next_request_id == 2
    assert result.effects == (
        RunExternalLaunchEffect(
            request_id=1,
            request=ExternalLaunchRequest(
                kind="copy_paths",
                paths=(TEST_PROJECT_ROOT + '/docs',),
            ),
        ),
    )

def test_copy_text_to_clipboard_emits_external_launch_effect() -> None:
    result = reduce_app_state(
        build_initial_app_state(),
        CopyTextToClipboard("selected preview text"),
    )

    assert result.state.next_request_id == 2
    assert result.effects == (
        RunExternalLaunchEffect(
            request_id=1,
            request=ExternalLaunchRequest(
                kind="copy_text",
                text="selected preview text",
            ),
        ),
    )

def test_copy_text_to_clipboard_ignores_whitespace_only_text() -> None:
    result = reduce_app_state(build_initial_app_state(), CopyTextToClipboard(" \n\t"))

    assert result.effects == ()
    assert result.state.notification == NotificationState(
        level="warning",
        message="Nothing to copy",
    )

def test_open_path_in_editor_allows_non_browser_file_path() -> None:
    result = reduce_app_state(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        OpenPathInEditor("/tmp/zivo/config.toml"),
    )

    assert result.state.next_request_id == 2
    assert result.effects == (
        RunExternalLaunchEffect(
            request_id=1,
            request=ExternalLaunchRequest(
                kind="open_editor",
                path="/tmp/zivo/config.toml",
            ),
        ),
    )

def test_toggle_hidden_files_normalizes_cursor_and_selection() -> None:
    hidden_path = TEST_PROJECT_ROOT + '/.env'
    visible_path = TEST_PROJECT_ROOT + '/docs'
    state = replace(
        build_initial_app_state(),
        show_hidden=True,
        current_pane=PaneState(
            directory_path=TEST_PROJECT_ROOT,
            entries=(
                DirectoryEntryState(hidden_path, ".env", "file", hidden=True),
                DirectoryEntryState(visible_path, "docs", "dir"),
            ),
            cursor_path=hidden_path,
            selected_paths=frozenset({hidden_path, visible_path}),
            selection_anchor_path=hidden_path,
        ),
    )

    next_state = _reduce_state(state, ToggleHiddenFiles())

    assert next_state.show_hidden is False
    assert next_state.current_pane.cursor_path == visible_path
    assert next_state.current_pane.selected_paths == frozenset({visible_path})
    assert next_state.current_pane.selection_anchor_path is None
    assert next_state.notification == NotificationState(
        level="info",
        message="Hidden files hidden",
    )

def test_confirm_filter_input_returns_to_browsing() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, SetUiMode("FILTER"))

    next_state = _reduce_state(state, ConfirmFilterInput())

    assert next_state.ui_mode == "BROWSING"

def test_confirm_filter_input_normalizes_cursor_path() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, SetUiMode("FILTER"))
    state = _reduce_state(state, SetFilterQuery("src"))

    next_state = _reduce_state(state, ConfirmFilterInput())

    assert next_state.ui_mode == "BROWSING"
    assert next_state.current_pane.cursor_path == TEST_PROJECT_ROOT + '/src'

def test_cancel_filter_input_clears_query() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, SetUiMode("FILTER"))
    state = _reduce_state(state, SetFilterQuery("readme"))

    next_state = _reduce_state(state, CancelFilterInput())

    assert next_state.ui_mode == "BROWSING"
    assert next_state.filter.query == ""
    assert next_state.filter.active is False

def test_cancel_filter_input_clears_query_from_browsing() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, SetFilterQuery("readme"))

    next_state = _reduce_state(state, CancelFilterInput())

    assert next_state.ui_mode == "BROWSING"
    assert next_state.filter.query == ""
    assert next_state.filter.active is False

def test_external_launch_failed_sets_error_notification() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(
        state,
        ExternalLaunchFailed(
            request_id=5,
            request=ExternalLaunchRequest(kind="open_file", path="/tmp/zivo/README.md"),
            message="Failed to open /tmp/zivo/README.md: permission denied",
        ),
    )

    assert next_state.notification == NotificationState(
        level="error",
        message="Failed to open /tmp/zivo/README.md: permission denied",
    )

def test_external_launch_completed_sets_copy_notification() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(
        state,
        ExternalLaunchCompleted(
            request_id=5,
            request=ExternalLaunchRequest(
                kind="copy_paths",
                paths=("/tmp/zivo/docs", "/tmp/zivo/README.md"),
            ),
        ),
    )

    assert next_state.notification == NotificationState(
        level="info",
        message="Copied 2 paths to system clipboard",
        auto_dismiss=True,
    )

def test_dismiss_name_conflict_restores_rename_mode_and_keeps_input() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        pending_input=PendingInputState(
            prompt="Rename: ",
            value="src",
            target_path=TEST_PROJECT_ROOT + '/docs',
        ),
        name_conflict=NameConflictState(kind="rename", name="src"),
    )

    next_state = _reduce_state(state, DismissNameConflict())

    assert next_state.ui_mode == "RENAME"
    assert next_state.pending_input == state.pending_input
    assert next_state.name_conflict is None

def test_dismiss_name_conflict_restores_create_mode_and_keeps_input() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        pending_input=PendingInputState(
            prompt="Name or path: ",
            value="docs",
            create_kind="file",
        ),
        name_conflict=NameConflictState(kind="create_file", name="docs"),
    )

    next_state = _reduce_state(state, DismissNameConflict())

    assert next_state.ui_mode == "CREATE"
    assert next_state.pending_input == state.pending_input
    assert next_state.name_conflict is None

def test_move_cursor_and_select_range_sets_anchor_and_selects_contiguous_entries() -> None:
    state = build_initial_app_state()
    visible_paths = (
        TEST_PROJECT_ROOT + '/docs',
        TEST_PROJECT_ROOT + '/src',
        TEST_PROJECT_ROOT + '/tests',
        TEST_PROJECT_ROOT + '/README.md',
        TEST_PROJECT_ROOT + '/pyproject.toml',
    )

    result = reduce_app_state(
        state,
        MoveCursorAndSelectRange(delta=1, visible_paths=visible_paths),
    )

    assert result.state.current_pane.cursor_path == TEST_PROJECT_ROOT + '/src'
    assert result.state.current_pane.selected_paths == frozenset(
        {
            TEST_PROJECT_ROOT + '/docs',
            TEST_PROJECT_ROOT + '/src',
        }
    )
    assert result.state.current_pane.selection_anchor_path == TEST_PROJECT_ROOT + '/docs'
    assert result.effects == (
        LoadChildPaneSnapshotEffect(
            request_id=1,
            current_path=TEST_PROJECT_ROOT,
            cursor_path=TEST_PROJECT_ROOT + '/src',
        ),
        RunDirectorySizeEffect(
            request_id=2,
            paths=(
                TEST_PROJECT_ROOT + '/docs',
                TEST_PROJECT_ROOT + '/src',
                TEST_PROJECT_ROOT + '/tests',
            ),
        ),
    )

def test_move_cursor_and_select_range_reuses_anchor_when_shrinking_selection() -> None:
    visible_paths = (
        TEST_PROJECT_ROOT + '/docs',
        TEST_PROJECT_ROOT + '/src',
        TEST_PROJECT_ROOT + '/tests',
        TEST_PROJECT_ROOT + '/README.md',
        TEST_PROJECT_ROOT + '/pyproject.toml',
    )
    state = reduce_app_state(
        build_initial_app_state(),
        MoveCursorAndSelectRange(delta=1, visible_paths=visible_paths),
    ).state
    state = reduce_app_state(
        state,
        MoveCursorAndSelectRange(delta=1, visible_paths=visible_paths),
    ).state

    result = reduce_app_state(
        state,
        MoveCursorAndSelectRange(delta=-1, visible_paths=visible_paths),
    )

    assert result.state.current_pane.cursor_path == TEST_PROJECT_ROOT + '/src'
    assert result.state.current_pane.selected_paths == frozenset(
        {
            TEST_PROJECT_ROOT + '/docs',
            TEST_PROJECT_ROOT + '/src',
        }
    )
    assert result.state.current_pane.selection_anchor_path == TEST_PROJECT_ROOT + '/docs'

def test_move_cursor_clears_range_selection_anchor() -> None:
    visible_paths = (
        TEST_PROJECT_ROOT + '/docs',
        TEST_PROJECT_ROOT + '/src',
        TEST_PROJECT_ROOT + '/tests',
    )
    initial_state = build_initial_app_state()
    state = replace(
        initial_state,
        current_pane=replace(
            initial_state.current_pane,
            selected_paths=frozenset(
                {
                    TEST_PROJECT_ROOT + '/docs',
                    TEST_PROJECT_ROOT + '/src',
                }
            ),
            selection_anchor_path=TEST_PROJECT_ROOT + '/docs',
        ),
    )

    result = reduce_app_state(state, MoveCursor(delta=1, visible_paths=visible_paths))

    assert result.state.current_pane.cursor_path == TEST_PROJECT_ROOT + '/src'
    assert result.state.current_pane.selected_paths == frozenset(
        {
            TEST_PROJECT_ROOT + '/docs',
            TEST_PROJECT_ROOT + '/src',
        }
    )
    assert result.state.current_pane.selection_anchor_path is None
