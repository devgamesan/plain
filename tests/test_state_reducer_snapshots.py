"""Test State Reducer Snapshots tests."""
from tests.support.paths import TEST_PROJECT_ROOT
from tests.support.reducer import (
    BrowserSnapshot,
    BrowserSnapshotFailed,
    BrowserSnapshotLoaded,
    ChildPaneSnapshotFailed,
    ChildPaneSnapshotLoaded,
    DirectoryEntryState,
    LoadChildPaneSnapshotEffect,
    MoveCursor,
    NotificationState,
    PaneState,
    RequestBrowserSnapshot,
    RunDirectorySizeEffect,
    SetCursorPath,
    SetTerminalHeight,
    SetTerminalSize,
    SetTerminalWidth,
    ToggleNarrowPaneView,
    ToggleSelection,
    _reduce_state,
    _viewport_test_entries,
    build_initial_app_state,
    reduce_app_state,
    replace,
)


def test_request_browser_snapshot_returns_effect_and_updates_pending_request() -> None:
    state = build_initial_app_state()

    result = reduce_app_state(state, RequestBrowserSnapshot("/tmp/example"))

    assert result.state.pending_browser_snapshot_request_id == 1
    assert result.state.pending_child_pane_request_id is None
    assert result.state.next_request_id == 2
    assert len(result.effects) == 1
    assert result.effects[0].path == "/tmp/example"
    assert result.effects[0].request_id == 1

def test_browser_snapshot_failed_ignores_stale_request() -> None:
    state = build_initial_app_state()
    requested = reduce_app_state(state, RequestBrowserSnapshot("/tmp/example")).state

    next_state = _reduce_state(
        requested,
        BrowserSnapshotFailed(request_id=99, message="load failed"),
    )

    assert next_state == requested

def test_browser_snapshot_loaded_ignores_stale_request() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, RequestBrowserSnapshot("/tmp/example"))
    snapshot = BrowserSnapshot(
        current_path="/tmp/new",
        parent_pane=state.parent_pane,
        current_pane=state.current_pane,
        child_pane=state.child_pane,
    )

    next_state = _reduce_state(
        state,
        BrowserSnapshotLoaded(request_id=99, snapshot=snapshot),
    )

    assert next_state == state

def test_browser_snapshot_loaded_applies_snapshot_and_clears_error() -> None:
    state = build_initial_app_state()
    requested = reduce_app_state(state, RequestBrowserSnapshot("/tmp/example")).state
    requested = _reduce_state(
        requested,
        BrowserSnapshotFailed(request_id=1, message="boom"),
    )
    snapshot = BrowserSnapshot(
        current_path="/tmp/example",
        parent_pane=requested.parent_pane,
        current_pane=requested.current_pane,
        child_pane=requested.child_pane,
    )
    requested = _reduce_state(requested, RequestBrowserSnapshot("/tmp/example"))

    next_state = _reduce_state(
        requested,
        BrowserSnapshotLoaded(request_id=2, snapshot=snapshot),
    )

    assert next_state.current_path == "/tmp/example"
    assert next_state.notification is None
    assert next_state.pending_browser_snapshot_request_id is None

def test_browser_snapshot_loaded_preserves_remaining_selection_on_reload() -> None:
    state = build_initial_app_state()
    state = _reduce_state(
        state,
        ToggleSelection(TEST_PROJECT_ROOT + '/docs'),
    )
    state = _reduce_state(
        state,
        ToggleSelection(TEST_PROJECT_ROOT + '/README.md'),
    )
    requested = reduce_app_state(
        state,
        RequestBrowserSnapshot(TEST_PROJECT_ROOT, blocking=True),
    ).state

    snapshot = BrowserSnapshot(
        current_path=TEST_PROJECT_ROOT,
        parent_pane=requested.parent_pane,
        current_pane=PaneState(
            directory_path=TEST_PROJECT_ROOT,
            entries=(
                DirectoryEntryState(TEST_PROJECT_ROOT + '/docs', "docs", "dir"),
                DirectoryEntryState(TEST_PROJECT_ROOT + '/src', "src", "dir"),
            ),
            cursor_path=TEST_PROJECT_ROOT + '/src',
        ),
        child_pane=PaneState(directory_path=TEST_PROJECT_ROOT + '/src', entries=()),
    )

    next_state = _reduce_state(
        requested,
        BrowserSnapshotLoaded(request_id=1, snapshot=snapshot, blocking=True),
    )

    assert next_state.current_pane.selected_paths == frozenset(
        {TEST_PROJECT_ROOT + '/docs'}
    )

def test_browser_snapshot_loaded_clears_selection_when_directory_changes() -> None:
    state = build_initial_app_state()
    state = _reduce_state(
        state,
        ToggleSelection(TEST_PROJECT_ROOT + '/docs'),
    )
    requested = reduce_app_state(
        state,
        RequestBrowserSnapshot(TEST_PROJECT_ROOT + '/docs', blocking=True),
    ).state

    snapshot = BrowserSnapshot(
        current_path=TEST_PROJECT_ROOT + '/docs',
        parent_pane=PaneState(
            directory_path=TEST_PROJECT_ROOT,
            entries=state.current_pane.entries,
            cursor_path=TEST_PROJECT_ROOT + '/docs',
        ),
        current_pane=PaneState(
            directory_path=TEST_PROJECT_ROOT + '/docs',
            entries=(
                DirectoryEntryState(
                    TEST_PROJECT_ROOT + '/docs/spec.md',
                    "spec.md",
                    "file",
                ),
            ),
            cursor_path=TEST_PROJECT_ROOT + '/docs/spec.md',
        ),
        child_pane=PaneState(directory_path=TEST_PROJECT_ROOT + '/docs', entries=()),
    )

    next_state = _reduce_state(
        requested,
        BrowserSnapshotLoaded(request_id=1, snapshot=snapshot, blocking=True),
    )

    assert next_state.current_pane.selected_paths == frozenset()

def test_browser_snapshot_failed_sets_error_notification() -> None:
    state = build_initial_app_state()
    requested = reduce_app_state(state, RequestBrowserSnapshot("/tmp/example")).state

    next_state = _reduce_state(
        requested,
        BrowserSnapshotFailed(request_id=1, message="load failed"),
    )

    assert next_state.notification == NotificationState(
        level="error",
        message="load failed",
    )
    assert next_state.pending_browser_snapshot_request_id is None

def test_move_cursor_emits_child_snapshot_effect_only_when_target_changes() -> None:
    state = build_initial_app_state()
    visible_paths = (
        TEST_PROJECT_ROOT + '/docs',
        TEST_PROJECT_ROOT + '/src',
        TEST_PROJECT_ROOT + '/tests',
    )

    result = reduce_app_state(state, SetCursorPath(TEST_PROJECT_ROOT + '/docs'))
    assert result.effects == (
        RunDirectorySizeEffect(
            request_id=1,
            paths=(
                TEST_PROJECT_ROOT + '/docs',
                TEST_PROJECT_ROOT + '/src',
                TEST_PROJECT_ROOT + '/tests',
            ),
        ),
    )

    moved = reduce_app_state(state, SetCursorPath(TEST_PROJECT_ROOT + '/src'))

    assert moved.state.pending_child_pane_request_id == 1
    assert moved.state.child_pane == state.child_pane
    assert moved.effects == (
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

    down = reduce_app_state(state, MoveCursor(delta=1, visible_paths=visible_paths))

    assert down.state.current_pane.cursor_path == TEST_PROJECT_ROOT + '/src'
    assert down.effects == (
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

def test_set_cursor_path_to_file_requests_child_pane_preview() -> None:
    state = build_initial_app_state()

    result = reduce_app_state(state, SetCursorPath(TEST_PROJECT_ROOT + '/README.md'))

    assert result.state.child_pane == state.child_pane
    assert result.state.pending_child_pane_request_id == 1
    assert result.effects == (
        LoadChildPaneSnapshotEffect(
            request_id=1,
            current_path=TEST_PROJECT_ROOT,
            cursor_path=TEST_PROJECT_ROOT + '/README.md',
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

def test_set_cursor_path_to_file_clears_child_pane_when_preview_disabled() -> None:
    state = replace(
        build_initial_app_state(),
        config=replace(
            build_initial_app_state().config,
            display=replace(build_initial_app_state().config.display, enable_text_preview=False),
        ),
        child_pane=PaneState(
            directory_path=TEST_PROJECT_ROOT,
            entries=(),
            mode="preview",
            preview_path=TEST_PROJECT_ROOT + '/pyproject.toml',
            preview_content="[project]\n",
        ),
    )

    result = reduce_app_state(state, SetCursorPath(TEST_PROJECT_ROOT + '/README.md'))

    assert result.state.child_pane == PaneState(
        directory_path=TEST_PROJECT_ROOT,
        entries=(),
    )
    assert result.state.pending_child_pane_request_id is None
    assert result.effects == (
        RunDirectorySizeEffect(
            request_id=1,
            paths=(
                TEST_PROJECT_ROOT + '/docs',
                TEST_PROJECT_ROOT + '/src',
                TEST_PROJECT_ROOT + '/tests',
            ),
        ),
    )

def test_child_pane_snapshot_loaded_ignores_stale_request() -> None:
    state = build_initial_app_state()
    requested = reduce_app_state(state, SetCursorPath(TEST_PROJECT_ROOT + '/src')).state

    next_state = _reduce_state(
        requested,
        ChildPaneSnapshotLoaded(
            request_id=99,
            pane=requested.child_pane,
        ),
    )

    assert next_state == requested

def test_child_pane_snapshot_loaded_clears_grep_preview_when_file_preview_disabled() -> None:
    path = TEST_PROJECT_ROOT + '/README.md'
    state = replace(
        build_initial_app_state(),
        config=replace(
            build_initial_app_state().config,
            display=replace(build_initial_app_state().config.display, enable_text_preview=False),
        ),
        pending_child_pane_request_id=7,
    )

    next_state = _reduce_state(
        state,
        ChildPaneSnapshotLoaded(
            request_id=7,
            pane=PaneState(
                directory_path=TEST_PROJECT_ROOT,
                entries=(),
                mode="preview",
                preview_path=path,
                preview_title="Preview: README.md:3",
                preview_content="one\ntwo\nTODO: update docs\n",
                preview_start_line=1,
                preview_highlight_line=3,
            ),
        ),
    )

    assert next_state.child_pane == PaneState(
        directory_path=TEST_PROJECT_ROOT,
        entries=(),
    )
    assert next_state.pending_child_pane_request_id is None

def test_child_pane_snapshot_failed_ignores_stale_request() -> None:
    state = build_initial_app_state()
    requested = reduce_app_state(state, SetCursorPath(TEST_PROJECT_ROOT + '/src')).state

    next_state = _reduce_state(
        requested,
        ChildPaneSnapshotFailed(request_id=99, message="permission denied"),
    )

    assert next_state == requested

def test_child_pane_snapshot_failure_sets_error_and_clears_entries() -> None:
    state = build_initial_app_state()
    requested = reduce_app_state(state, SetCursorPath(TEST_PROJECT_ROOT + '/src')).state

    next_state = _reduce_state(
        requested,
        ChildPaneSnapshotFailed(request_id=1, message="permission denied"),
    )

    assert next_state.child_pane.directory_path == TEST_PROJECT_ROOT
    assert next_state.child_pane.entries == ()
    assert next_state.notification == NotificationState(
        level="error",
        message="permission denied",
    )

class TestSetTerminalHeight:
    def test_updates_terminal_height(self) -> None:
        state = build_initial_app_state()
        assert state.terminal_height == 24

        next_state = _reduce_state(state, SetTerminalHeight(height=48))

        assert next_state.terminal_height == 48

    def test_repositions_viewport_window_to_keep_cursor_visible(self) -> None:
        path = "/tmp/zivo-viewport-terminal-height"
        entries = _viewport_test_entries(path, 20)
        state = replace(
            build_initial_app_state(current_pane_projection_mode="viewport"),
            terminal_height=16,
            current_pane=PaneState(
                directory_path=path,
                entries=entries,
                cursor_path=entries[16].path,
            ),
            child_pane=PaneState(directory_path=path, entries=()),
            current_pane_window_start=9,
        )

        next_state = _reduce_state(state, SetTerminalHeight(height=12))

        assert next_state.terminal_height == 12
        assert next_state.current_pane_window_start == 12

    def test_no_change_when_same_height(self) -> None:
        state = build_initial_app_state()
        next_state = _reduce_state(state, SetTerminalHeight(height=24))

        assert next_state is state

class TestResponsivePaneState:
    def test_set_terminal_size_updates_both_dimensions_once(self) -> None:
        state = replace(
            build_initial_app_state(),
            terminal_height=24,
            terminal_width=72,
            narrow_pane_view="details",
        )

        next_state = _reduce_state(state, SetTerminalSize(height=30, width=80))

        assert next_state.terminal_height == 30
        assert next_state.terminal_width == 80
        assert next_state.narrow_pane_view == "current"

    def test_set_terminal_size_no_change_returns_same_state(self) -> None:
        state = build_initial_app_state()

        assert _reduce_state(
            state,
            SetTerminalSize(height=state.terminal_height, width=state.terminal_width),
        ) is state

    def test_updates_terminal_width_and_resets_narrow_view_at_breakpoint(self) -> None:
        state = replace(
            build_initial_app_state(),
            terminal_width=72,
            narrow_pane_view="details",
        )

        next_state = _reduce_state(state, SetTerminalWidth(width=80))

        assert next_state.terminal_width == 80
        assert next_state.narrow_pane_view == "current"

    def test_toggle_narrow_view(self) -> None:
        state = replace(build_initial_app_state(), terminal_width=72)

        details = _reduce_state(state, ToggleNarrowPaneView())
        current = _reduce_state(details, ToggleNarrowPaneView())

        assert details.narrow_pane_view == "details"
        assert current.narrow_pane_view == "current"

    def test_toggle_narrow_view_is_ignored_outside_narrow_browser(self) -> None:
        state = replace(build_initial_app_state(), terminal_width=80)

        assert _reduce_state(state, ToggleNarrowPaneView()) is state
