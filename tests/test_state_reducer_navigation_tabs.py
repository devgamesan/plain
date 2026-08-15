"""Test State Reducer Navigation Tabs tests."""
from tests.support.paths import TEST_DEVELOP_ROOT, TEST_HOME, TEST_PROJECT_ROOT
from tests.support.reducer import (
    DIRECTORY_HISTORY_LIMIT,
    ActivateNextTab,
    ActivatePreviousTab,
    ActivateTabByIndex,
    BeginFilterInput,
    BrowserSnapshot,
    BrowserSnapshotLoaded,
    CloseCurrentTab,
    CloseTabByIndex,
    DirectoryEntryState,
    GoBack,
    GoForward,
    HistoryState,
    JumpCursor,
    LoadChildPaneSnapshotEffect,
    MoveCursor,
    MoveCursorByPage,
    NotificationState,
    OpenNewTab,
    PaneState,
    PendingKeySequenceState,
    RequestBrowserSnapshot,
    RunDirectorySizeEffect,
    SetCursorPath,
    SetFilterQuery,
    SetPendingKeySequence,
    SetSort,
    ToggleHiddenFiles,
    _reduce_state,
    _viewport_test_entries,
    build_history_after_snapshot_load,
    build_initial_app_state,
    reduce_app_state,
    replace,
    select_browser_tabs,
)


def test_jump_cursor_start() -> None:
    state = build_initial_app_state()
    visible_paths = (
        TEST_PROJECT_ROOT + '/docs',
        TEST_PROJECT_ROOT + '/src',
        TEST_PROJECT_ROOT + '/tests',
    )
    state = _reduce_state(state, SetCursorPath(TEST_PROJECT_ROOT + '/tests'))

    result = reduce_app_state(state, JumpCursor(position="start", visible_paths=visible_paths))

    assert result.state.current_pane.cursor_path == TEST_PROJECT_ROOT + '/docs'
    assert result.effects == (
        LoadChildPaneSnapshotEffect(
            request_id=3,
            current_path=TEST_PROJECT_ROOT,
            cursor_path=TEST_PROJECT_ROOT + '/docs',
        ),
    )

def test_jump_cursor_end() -> None:
    state = build_initial_app_state()
    visible_paths = (
        TEST_PROJECT_ROOT + '/docs',
        TEST_PROJECT_ROOT + '/src',
        TEST_PROJECT_ROOT + '/tests',
    )

    result = reduce_app_state(state, JumpCursor(position="end", visible_paths=visible_paths))

    assert result.state.current_pane.cursor_path == TEST_PROJECT_ROOT + '/tests'
    assert result.effects == (
        LoadChildPaneSnapshotEffect(
            request_id=1,
            current_path=TEST_PROJECT_ROOT,
            cursor_path=TEST_PROJECT_ROOT + '/tests',
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

def test_jump_cursor_end_repositions_viewport_window() -> None:
    path = "/tmp/zivo-viewport-jump"
    entries = _viewport_test_entries(path, 20)
    visible_paths = tuple(entry.path for entry in entries)
    state = replace(
        build_initial_app_state(current_pane_projection_mode="viewport"),
        terminal_height=12,
        current_pane=PaneState(
            directory_path=path,
            entries=entries,
            cursor_path=entries[0].path,
        ),
        child_pane=PaneState(directory_path=path, entries=()),
    )

    result = reduce_app_state(state, JumpCursor(position="end", visible_paths=visible_paths))

    assert result.state.current_pane.cursor_path == entries[-1].path
    assert result.state.current_pane_window_start == 15

def test_jump_cursor_empty_paths() -> None:
    state = build_initial_app_state()

    result = reduce_app_state(state, JumpCursor(position="start", visible_paths=()))

    assert result.state is state

def test_jump_cursor_with_filter() -> None:
    state = build_initial_app_state()
    filtered_paths = (
        TEST_PROJECT_ROOT + '/src',
        TEST_PROJECT_ROOT + '/tests',
    )
    state = _reduce_state(state, SetCursorPath(TEST_PROJECT_ROOT + '/tests'))

    result = reduce_app_state(
        state,
        JumpCursor(position="start", visible_paths=filtered_paths),
    )

    assert result.state.current_pane.cursor_path == TEST_PROJECT_ROOT + '/src'

def test_move_cursor_page_down_repositions_viewport_window() -> None:
    path = "/tmp/zivo-viewport-page"
    entries = _viewport_test_entries(path, 20)
    visible_paths = tuple(entry.path for entry in entries)
    state = replace(
        build_initial_app_state(current_pane_projection_mode="viewport"),
        terminal_height=12,
        current_pane=PaneState(
            directory_path=path,
            entries=entries,
            cursor_path=entries[0].path,
        ),
        child_pane=PaneState(directory_path=path, entries=()),
    )

    result = reduce_app_state(state, MoveCursor(delta=5, visible_paths=visible_paths))

    assert result.state.current_pane.cursor_path == entries[5].path
    assert result.state.current_pane_window_start == 2

def test_set_filter_query_resets_viewport_window_when_cursor_leaves_visible_entries() -> None:
    path = "/tmp/zivo-viewport-filter"
    entries = _viewport_test_entries(path, 20)
    state = replace(
        build_initial_app_state(current_pane_projection_mode="viewport"),
        terminal_height=12,
        current_pane=PaneState(
            directory_path=path,
            entries=entries,
            cursor_path=entries[-1].path,
        ),
        child_pane=PaneState(directory_path=path, entries=()),
        current_pane_window_start=15,
    )

    next_state = _reduce_state(state, SetFilterQuery("item_0", active=True))

    assert next_state.filter.query == "item_0"
    assert next_state.current_pane_window_start == 0

def test_toggle_hidden_files_clamps_viewport_window_start() -> None:
    path = "/tmp/zivo-viewport-hidden"
    entries = _viewport_test_entries(path, 10, hidden_indexes=frozenset({7, 8, 9}))
    state = replace(
        build_initial_app_state(current_pane_projection_mode="viewport"),
        terminal_height=12,
        show_hidden=True,
        current_pane=PaneState(
            directory_path=path,
            entries=entries,
            cursor_path=entries[-1].path,
        ),
        child_pane=PaneState(directory_path=path, entries=()),
        current_pane_window_start=5,
    )

    next_state = _reduce_state(state, ToggleHiddenFiles())

    assert next_state.show_hidden is False
    assert next_state.current_pane.cursor_path == entries[0].path
    assert next_state.current_pane_window_start == 0

def test_set_sort_keeps_cursor_visible_when_viewport_order_changes() -> None:
    path = "/tmp/zivo-viewport-sort"
    entries = _viewport_test_entries(path, 20)
    state = replace(
        build_initial_app_state(current_pane_projection_mode="viewport"),
        terminal_height=12,
        current_pane=PaneState(
            directory_path=path,
            entries=entries,
            cursor_path=entries[0].path,
        ),
        child_pane=PaneState(directory_path=path, entries=()),
    )

    next_state = _reduce_state(
        state,
        SetSort(field="name", descending=True, directories_first=False),
    )

    assert next_state.sort.descending is True
    assert next_state.current_pane.cursor_path == entries[0].path
    assert next_state.current_pane_window_start == 15

def test_go_back_does_nothing_when_back_stack_is_empty() -> None:
    state = build_initial_app_state()

    result = reduce_app_state(state, GoBack())

    assert result.state == state

def test_go_back_requests_snapshot_from_back_stack() -> None:
    state = replace(
        build_initial_app_state(),
        history=HistoryState(
            back=(TEST_HOME, TEST_HOME + '/downloads'),
            forward=(),
        ),
    )

    result = reduce_app_state(state, GoBack())

    assert result.state.pending_browser_snapshot_request_id is not None
    assert result.state.ui_mode == "BUSY"
    assert len(result.effects) == 1
    assert result.effects[0].path == TEST_HOME + '/downloads'

def test_go_forward_does_nothing_when_forward_stack_is_empty() -> None:
    state = build_initial_app_state()

    result = reduce_app_state(state, GoForward())

    assert result.state == state

def test_go_forward_requests_snapshot_from_forward_stack() -> None:
    state = replace(
        build_initial_app_state(),
        history=HistoryState(
            back=(),
            forward=(TEST_HOME + '/downloads',),
        ),
    )

    result = reduce_app_state(state, GoForward())

    assert result.state.pending_browser_snapshot_request_id is not None
    assert result.state.ui_mode == "BUSY"
    assert len(result.effects) == 1
    assert result.effects[0].path == TEST_HOME + '/downloads'

def test_browser_snapshot_loaded_records_history_on_path_change() -> None:
    state = build_initial_app_state()
    initial_path = state.current_path
    state = _reduce_state(state, RequestBrowserSnapshot("/tmp/example"))

    snapshot = BrowserSnapshot(
        current_path="/tmp/example",
        parent_pane=state.parent_pane,
        current_pane=state.current_pane,
        child_pane=state.child_pane,
    )

    next_state = _reduce_state(
        state,
        BrowserSnapshotLoaded(
            request_id=state.pending_browser_snapshot_request_id,
            snapshot=snapshot,
            blocking=True,
        ),
    )

    assert next_state.current_path == "/tmp/example"
    assert next_state.history.back == (initial_path,)
    assert next_state.history.forward == ()
    assert next_state.history.visited_all == (initial_path, "/tmp/example")

def test_browser_snapshot_loaded_clears_forward_on_new_navigation() -> None:
    initial_path = build_initial_app_state().current_path
    state = replace(
        build_initial_app_state(),
        history=HistoryState(
            back=(TEST_HOME,),
            forward=(TEST_HOME + '/downloads', TEST_HOME + '/documents'),
        ),
    )
    state = _reduce_state(state, RequestBrowserSnapshot("/tmp/new_place"))

    snapshot = BrowserSnapshot(
        current_path="/tmp/new_place",
        parent_pane=state.parent_pane,
        current_pane=state.current_pane,
        child_pane=state.child_pane,
    )

    next_state = _reduce_state(
        state,
        BrowserSnapshotLoaded(
            request_id=state.pending_browser_snapshot_request_id,
            snapshot=snapshot,
            blocking=True,
        ),
    )

    assert next_state.history.forward == ()
    assert next_state.history.back == (TEST_HOME, initial_path)

def test_browser_snapshot_loaded_does_not_record_history_on_reload() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, RequestBrowserSnapshot(state.current_path))

    snapshot = BrowserSnapshot(
        current_path=state.current_path,
        parent_pane=state.parent_pane,
        current_pane=state.current_pane,
        child_pane=state.child_pane,
    )

    next_state = _reduce_state(
        state,
        BrowserSnapshotLoaded(
            request_id=state.pending_browser_snapshot_request_id,
            snapshot=snapshot,
            blocking=True,
        ),
    )

    assert next_state.history.back == ()
    assert next_state.history.forward == ()

def test_directory_history_is_bounded_when_navigating_to_a_new_path() -> None:
    state = replace(
        build_initial_app_state(),
        current_path="/current",
        history=HistoryState(
            back=tuple(f"/back/{index}" for index in range(DIRECTORY_HISTORY_LIMIT)),
            forward=tuple(
                f"/forward/{index}" for index in range(DIRECTORY_HISTORY_LIMIT)
            ),
            visited_all=tuple(
                f"/visited/{index}" for index in range(DIRECTORY_HISTORY_LIMIT)
            ),
        ),
    )

    next_history = build_history_after_snapshot_load(state, "/new")

    assert len(next_history.back) == DIRECTORY_HISTORY_LIMIT
    assert next_history.back == (
        *(f"/back/{index}" for index in range(1, DIRECTORY_HISTORY_LIMIT)),
        "/current",
    )
    assert next_history.forward == ()
    assert len(next_history.visited_all) == DIRECTORY_HISTORY_LIMIT
    assert next_history.visited_all[-2:] == ("/current", "/new")

def test_back_and_forward_stacks_are_trimmed_when_history_is_already_oversized() -> None:
    state = replace(
        build_initial_app_state(),
        current_path="/current",
        history=HistoryState(
            back=tuple(f"/back/{index}" for index in range(120)),
            forward=tuple(f"/forward/{index}" for index in range(120)),
        ),
    )

    next_history = build_history_after_snapshot_load(state, "/forward/0")

    assert len(next_history.back) == DIRECTORY_HISTORY_LIMIT
    assert next_history.back == (
        *(f"/back/{index}" for index in range(21, 120)),
        "/current",
    )
    assert next_history.forward == tuple(
        f"/forward/{index}" for index in range(1, DIRECTORY_HISTORY_LIMIT + 1)
    )

def test_revisiting_a_directory_moves_it_to_the_newest_history_position() -> None:
    state = replace(
        build_initial_app_state(),
        current_path="/current",
        history=HistoryState(visited_all=("/old", "/current", "/other")),
    )

    next_history = build_history_after_snapshot_load(state, "/old")

    assert next_history.visited_all == ("/other", "/current", "/old")

def test_go_back_then_snapshot_loaded_updates_history_correctly() -> None:
    initial_path = TEST_HOME
    second_path = TEST_DEVELOP_ROOT

    state = replace(
        build_initial_app_state(),
        current_path=second_path,
        history=HistoryState(
            back=(initial_path,),
            forward=(),
            visited_all=(initial_path, second_path),
        ),
    )

    result = reduce_app_state(state, GoBack())
    assert result.effects[0].path == initial_path

    snapshot = BrowserSnapshot(
        current_path=initial_path,
        parent_pane=state.parent_pane,
        current_pane=state.current_pane,
        child_pane=state.child_pane,
    )
    loaded_result = _reduce_state(
        result.state,
        BrowserSnapshotLoaded(
            request_id=result.state.pending_browser_snapshot_request_id,
            snapshot=snapshot,
            blocking=True,
        ),
    )

    assert loaded_result.current_path == initial_path
    assert loaded_result.history.back == ()
    assert loaded_result.history.forward == (second_path,)

def test_go_forward_then_snapshot_loaded_updates_history_correctly() -> None:
    initial_path = TEST_HOME
    forward_path = TEST_DEVELOP_ROOT

    state = replace(
        build_initial_app_state(),
        current_path=initial_path,
        history=HistoryState(
            back=(),
            forward=(forward_path,),
            visited_all=(initial_path, forward_path),
        ),
    )

    result = reduce_app_state(state, GoForward())
    assert result.effects[0].path == forward_path

    snapshot = BrowserSnapshot(
        current_path=forward_path,
        parent_pane=state.parent_pane,
        current_pane=state.current_pane,
        child_pane=state.child_pane,
    )
    loaded_result = _reduce_state(
        result.state,
        BrowserSnapshotLoaded(
            request_id=result.state.pending_browser_snapshot_request_id,
            snapshot=snapshot,
            blocking=True,
        ),
    )

    assert loaded_result.current_path == forward_path
    assert loaded_result.history.back == (initial_path,)
    assert loaded_result.history.forward == ()

def test_browser_snapshot_loaded_clears_filter_when_directory_changes() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, SetFilterQuery("readme"))

    requested = reduce_app_state(
        state,
        RequestBrowserSnapshot("/tmp/example", blocking=True),
    ).state
    snapshot = BrowserSnapshot(
        current_path="/tmp/example",
        parent_pane=requested.parent_pane,
        current_pane=requested.current_pane,
        child_pane=requested.child_pane,
    )
    next_state = _reduce_state(
        requested,
        BrowserSnapshotLoaded(request_id=1, snapshot=snapshot, blocking=True),
    )

    assert next_state.filter.query == ""
    assert next_state.filter.active is False

def test_browser_snapshot_loaded_preserves_filter_on_reload() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, SetFilterQuery("readme"))
    initial_path = state.current_path

    requested = reduce_app_state(
        state,
        RequestBrowserSnapshot(initial_path, blocking=True),
    ).state
    snapshot = BrowserSnapshot(
        current_path=initial_path,
        parent_pane=requested.parent_pane,
        current_pane=requested.current_pane,
        child_pane=requested.child_pane,
    )
    next_state = _reduce_state(
        requested,
        BrowserSnapshotLoaded(request_id=1, snapshot=snapshot, blocking=True),
    )

    assert next_state.filter.query == "readme"
    assert next_state.filter.active is True

def test_browser_snapshot_loaded_exits_filter_mode_on_directory_change() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, BeginFilterInput())
    state = _reduce_state(state, SetFilterQuery("test"))

    requested = reduce_app_state(
        state,
        RequestBrowserSnapshot("/tmp/example", blocking=True),
    ).state
    snapshot = BrowserSnapshot(
        current_path="/tmp/example",
        parent_pane=requested.parent_pane,
        current_pane=requested.current_pane,
        child_pane=requested.child_pane,
    )
    next_state = _reduce_state(
        requested,
        BrowserSnapshotLoaded(request_id=1, snapshot=snapshot, blocking=True),
    )

    assert next_state.ui_mode == "BROWSING"
    assert next_state.filter.query == ""
    assert next_state.filter.active is False

def test_move_cursor_by_page_down() -> None:
    state = build_initial_app_state()
    visible_paths = (
        TEST_PROJECT_ROOT + '/docs',
        TEST_PROJECT_ROOT + '/src',
        TEST_PROJECT_ROOT + '/tests',
        TEST_PROJECT_ROOT + '/README.md',
        TEST_PROJECT_ROOT + '/pyproject.toml',
    )
    state = _reduce_state(state, SetCursorPath(TEST_PROJECT_ROOT + '/docs'))

    result = reduce_app_state(
        state, MoveCursorByPage(direction="down", page_size=3, visible_paths=visible_paths)
    )

    assert result.state.current_pane.cursor_path == TEST_PROJECT_ROOT + '/README.md'
    assert result.effects == (
        LoadChildPaneSnapshotEffect(
            request_id=2,
            current_path=TEST_PROJECT_ROOT,
            cursor_path=TEST_PROJECT_ROOT + '/README.md',
        ),
    )

def test_move_cursor_by_page_up() -> None:
    state = build_initial_app_state()
    visible_paths = (
        TEST_PROJECT_ROOT + '/docs',
        TEST_PROJECT_ROOT + '/src',
        TEST_PROJECT_ROOT + '/tests',
        TEST_PROJECT_ROOT + '/README.md',
        TEST_PROJECT_ROOT + '/pyproject.toml',
    )
    state = _reduce_state(state, SetCursorPath(TEST_PROJECT_ROOT + '/pyproject.toml'))

    result = reduce_app_state(
        state, MoveCursorByPage(direction="up", page_size=3, visible_paths=visible_paths)
    )

    assert result.state.current_pane.cursor_path == TEST_PROJECT_ROOT + '/src'
    assert result.effects == (
        LoadChildPaneSnapshotEffect(
            request_id=3,
            current_path=TEST_PROJECT_ROOT,
            cursor_path=TEST_PROJECT_ROOT + '/src',
        ),
    )

def test_move_cursor_by_page_down_clamps_to_last_entry() -> None:
    state = build_initial_app_state()
    visible_paths = (
        TEST_PROJECT_ROOT + '/docs',
        TEST_PROJECT_ROOT + '/src',
        TEST_PROJECT_ROOT + '/tests',
    )
    state = _reduce_state(state, SetCursorPath(TEST_PROJECT_ROOT + '/src'))

    result = reduce_app_state(
        state, MoveCursorByPage(direction="down", page_size=10, visible_paths=visible_paths)
    )

    assert result.state.current_pane.cursor_path == TEST_PROJECT_ROOT + '/tests'

def test_move_cursor_by_page_up_clamps_to_first_entry() -> None:
    state = build_initial_app_state()
    visible_paths = (
        TEST_PROJECT_ROOT + '/docs',
        TEST_PROJECT_ROOT + '/src',
        TEST_PROJECT_ROOT + '/tests',
    )
    state = _reduce_state(state, SetCursorPath(TEST_PROJECT_ROOT + '/src'))

    result = reduce_app_state(
        state, MoveCursorByPage(direction="up", page_size=10, visible_paths=visible_paths)
    )

    assert result.state.current_pane.cursor_path == TEST_PROJECT_ROOT + '/docs'

def test_move_cursor_by_page_empty_paths() -> None:
    state = build_initial_app_state()

    result = reduce_app_state(
        state, MoveCursorByPage(direction="down", page_size=3, visible_paths=())
    )

    assert result.state is state
    assert result.effects == ()

def test_open_new_tab_clones_path_but_resets_filter_and_selection() -> None:
    state = replace(
        build_initial_app_state(),
        filter=replace(build_initial_app_state().filter, query="read", active=True),
        current_pane=replace(
            build_initial_app_state().current_pane,
            selected_paths=frozenset({TEST_PROJECT_ROOT + '/docs'}),
            selection_anchor_path=TEST_PROJECT_ROOT + '/docs',
        ),
    )

    next_state = _reduce_state(state, OpenNewTab())

    assert next_state.active_tab_index == 1
    assert next_state.current_path == state.current_path
    assert next_state.filter.query == ""
    assert next_state.filter.active is False
    assert next_state.current_pane.selected_paths == frozenset()
    assert len(select_browser_tabs(next_state)) == 2
    assert select_browser_tabs(next_state)[0].filter.query == "read"
    assert select_browser_tabs(next_state)[0].current_pane.selected_paths == frozenset(
        {TEST_PROJECT_ROOT + '/docs'}
    )

def test_activate_tabs_restores_per_tab_filter_state() -> None:
    state = _reduce_state(build_initial_app_state(), OpenNewTab())
    state = _reduce_state(state, SetFilterQuery("read"))

    state = _reduce_state(state, ActivatePreviousTab())
    assert state.active_tab_index == 0
    assert state.filter.query == ""

    state = _reduce_state(state, ActivateNextTab())
    assert state.active_tab_index == 1
    assert state.filter.query == "read"

def test_activate_tab_by_index_selects_requested_tab() -> None:
    state = _reduce_state(build_initial_app_state(), OpenNewTab())
    state = _reduce_state(state, SetFilterQuery("read"))

    state = _reduce_state(state, ActivateTabByIndex(0))

    assert state.active_tab_index == 0
    assert state.filter.query == ""

def test_activate_tab_by_index_ignores_out_of_range_index() -> None:
    state = _reduce_state(build_initial_app_state(), OpenNewTab())

    next_state = _reduce_state(state, ActivateTabByIndex(9))

    assert next_state == state

def test_close_current_tab_warns_when_only_one_tab_remains() -> None:
    next_state = _reduce_state(build_initial_app_state(), CloseCurrentTab())

    assert next_state.notification == NotificationState(
        level="warning",
        message="Cannot close the last tab",
    )

def test_close_tab_by_index_preserves_active_tab_when_closing_another_tab() -> None:
    state = _reduce_state(build_initial_app_state(), OpenNewTab())
    state = _reduce_state(state, OpenNewTab())
    active_path = state.current_path

    next_state = _reduce_state(state, CloseTabByIndex(0))

    assert next_state.active_tab_index == 1
    assert next_state.current_path == active_path
    assert len(select_browser_tabs(next_state)) == 2

def test_close_tab_by_index_warns_when_only_one_tab_remains() -> None:
    next_state = _reduce_state(build_initial_app_state(), CloseTabByIndex(0))

    assert next_state.notification == NotificationState(
        level="warning",
        message="Cannot close the last tab",
    )

def test_browser_snapshot_loaded_updates_inactive_tab_only() -> None:
    state = _reduce_state(build_initial_app_state(), OpenNewTab())
    result = reduce_app_state(state, RequestBrowserSnapshot("/tmp/project", blocking=True))
    state = result.state
    request_id = state.pending_browser_snapshot_request_id

    state = _reduce_state(state, ActivatePreviousTab())
    base_path = state.current_path

    loaded = reduce_app_state(
        state,
        BrowserSnapshotLoaded(
            request_id=request_id,
            blocking=True,
            snapshot=BrowserSnapshot(
                current_path="/tmp/project",
                parent_pane=PaneState(
                    directory_path="/tmp",
                    entries=(DirectoryEntryState("/tmp/project", "project", "dir"),),
                    cursor_path="/tmp/project",
                ),
                current_pane=PaneState(
                    directory_path="/tmp/project",
                    entries=(DirectoryEntryState("/tmp/project/file.txt", "file.txt", "file"),),
                    cursor_path="/tmp/project/file.txt",
                ),
                child_pane=PaneState(directory_path="/tmp/project", entries=()),
            ),
        ),
    ).state

    assert loaded.current_path == base_path
    assert select_browser_tabs(loaded)[1].current_path == "/tmp/project"

    loaded = _reduce_state(loaded, ActivateNextTab())
    assert loaded.current_path == "/tmp/project"

def test_set_pending_key_sequence_updates_state() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(
        state,
        SetPendingKeySequence(keys=("y",), possible_next_keys=("y",)),
    )

    assert next_state.pending_key_sequence == PendingKeySequenceState(
        keys=("y",),
        possible_next_keys=("y",),
    )
