from plain.state import (
    BeginFilterInput,
    BrowserSnapshot,
    BrowserSnapshotFailed,
    BrowserSnapshotLoaded,
    CancelFilterInput,
    ChildPaneSnapshotFailed,
    ChildPaneSnapshotLoaded,
    ClearSelection,
    ConfirmFilterInput,
    LoadChildPaneSnapshotEffect,
    MoveCursor,
    NotificationState,
    RequestBrowserSnapshot,
    SetCursorPath,
    SetFilterQuery,
    SetSort,
    SetUiMode,
    ToggleSelection,
    ToggleSelectionAndAdvance,
    build_initial_app_state,
    reduce_app_state,
)


def _reduce_state(state, action):
    return reduce_app_state(state, action).state


def test_set_ui_mode_updates_only_mode() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(state, SetUiMode("FILTER"))

    assert next_state.ui_mode == "FILTER"
    assert next_state.current_pane == state.current_pane
    assert next_state.filter == state.filter


def test_toggle_selection_uses_absolute_paths() -> None:
    state = build_initial_app_state()
    path = "/home/tadashi/develop/plain/README.md"

    selected_state = _reduce_state(state, ToggleSelection(path))
    cleared_state = _reduce_state(selected_state, ToggleSelection(path))

    assert selected_state.current_pane.selected_paths == frozenset({path})
    assert cleared_state.current_pane.selected_paths == frozenset()


def test_clear_selection_empties_selection() -> None:
    state = build_initial_app_state()
    selected_state = _reduce_state(
        state,
        ToggleSelection("/home/tadashi/develop/plain/README.md"),
    )

    next_state = _reduce_state(selected_state, ClearSelection())

    assert next_state.current_pane.selected_paths == frozenset()


def test_set_filter_query_returns_new_state_without_mutating_input() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(state, SetFilterQuery("readme"))

    assert next_state.filter.query == "readme"
    assert next_state.filter.active is True
    assert state.filter.query == ""
    assert state.filter.active is False


def test_set_sort_returns_new_state_without_mutating_input() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(
        state,
        SetSort(field="modified", descending=True, directories_first=False),
    )

    assert next_state.sort.field == "modified"
    assert next_state.sort.descending is True
    assert next_state.sort.directories_first is False
    assert state.sort.field == "name"
    assert state.sort.descending is False
    assert state.sort.directories_first is True


def test_set_cursor_path_ignores_unknown_path() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(state, SetCursorPath("/missing"))

    assert next_state == state


def test_begin_filter_input_switches_mode_without_mutating_query() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(state, BeginFilterInput())

    assert next_state.ui_mode == "FILTER"
    assert next_state.filter == state.filter


def test_confirm_filter_input_returns_to_browsing() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, SetUiMode("FILTER"))

    next_state = _reduce_state(state, ConfirmFilterInput())

    assert next_state.ui_mode == "BROWSING"


def test_cancel_filter_input_clears_query_and_recursive_flag() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, SetUiMode("FILTER"))
    state = _reduce_state(state, SetFilterQuery("readme"))

    next_state = _reduce_state(state, CancelFilterInput())

    assert next_state.ui_mode == "BROWSING"
    assert next_state.filter.query == ""
    assert next_state.filter.active is False
    assert next_state.filter.recursive is False


def test_toggle_selection_and_advance_moves_cursor_to_next_visible_entry() -> None:
    state = build_initial_app_state()
    current_path = "/home/tadashi/develop/plain/docs"
    visible_paths = (
        "/home/tadashi/develop/plain/docs",
        "/home/tadashi/develop/plain/src",
        "/home/tadashi/develop/plain/tests",
        "/home/tadashi/develop/plain/README.md",
        "/home/tadashi/develop/plain/pyproject.toml",
    )

    result = reduce_app_state(
        state,
        ToggleSelectionAndAdvance(path=current_path, visible_paths=visible_paths),
    )

    assert result.state.current_pane.selected_paths == frozenset({current_path})
    assert result.state.current_pane.cursor_path == "/home/tadashi/develop/plain/src"
    assert result.state.pending_child_pane_request_id == 1
    assert result.effects == (
        LoadChildPaneSnapshotEffect(
            request_id=1,
            current_path="/home/tadashi/develop/plain",
            cursor_path="/home/tadashi/develop/plain/src",
        ),
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
        "/home/tadashi/develop/plain/docs",
        "/home/tadashi/develop/plain/src",
        "/home/tadashi/develop/plain/tests",
    )

    result = reduce_app_state(state, SetCursorPath("/home/tadashi/develop/plain/docs"))
    assert result.effects == ()

    moved = reduce_app_state(state, SetCursorPath("/home/tadashi/develop/plain/src"))

    assert moved.state.pending_child_pane_request_id == 1
    assert moved.effects == (
        LoadChildPaneSnapshotEffect(
            request_id=1,
            current_path="/home/tadashi/develop/plain",
            cursor_path="/home/tadashi/develop/plain/src",
        ),
    )

    down = reduce_app_state(state, MoveCursor(delta=1, visible_paths=visible_paths))

    assert down.state.current_pane.cursor_path == "/home/tadashi/develop/plain/src"
    assert down.effects == (
        LoadChildPaneSnapshotEffect(
            request_id=1,
            current_path="/home/tadashi/develop/plain",
            cursor_path="/home/tadashi/develop/plain/src",
        ),
    )


def test_set_cursor_path_to_file_clears_child_pane_without_effect() -> None:
    state = build_initial_app_state()

    result = reduce_app_state(state, SetCursorPath("/home/tadashi/develop/plain/README.md"))

    assert result.state.child_pane.directory_path == "/home/tadashi/develop/plain"
    assert result.state.child_pane.entries == ()
    assert result.effects == ()


def test_child_pane_snapshot_loaded_ignores_stale_request() -> None:
    state = build_initial_app_state()
    requested = reduce_app_state(state, SetCursorPath("/home/tadashi/develop/plain/src")).state

    next_state = _reduce_state(
        requested,
        ChildPaneSnapshotLoaded(
            request_id=99,
            pane=requested.child_pane,
        ),
    )

    assert next_state == requested


def test_child_pane_snapshot_failure_sets_error_and_clears_entries() -> None:
    state = build_initial_app_state()
    requested = reduce_app_state(state, SetCursorPath("/home/tadashi/develop/plain/src")).state

    next_state = _reduce_state(
        requested,
        ChildPaneSnapshotFailed(request_id=1, message="permission denied"),
    )

    assert next_state.child_pane.directory_path == "/home/tadashi/develop/plain"
    assert next_state.child_pane.entries == ()
    assert next_state.notification == NotificationState(
        level="error",
        message="permission denied",
    )
