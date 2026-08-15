"""Test State Reducer Core tests."""

from tests.support.reducer import (
    WINDOWS_DRIVES_ROOT,
    BrowserSnapshot,
    BrowserSnapshotLoaded,
    ClearSelection,
    CurrentPaneDeltaState,
    CutTargets,
    DirectoryEntryState,
    DirectorySizeCacheEntry,
    DirectorySizeDeltaState,
    DirectorySizesFailed,
    DirectorySizesLoaded,
    EnterCursorDirectory,
    ExternalLaunchCompleted,
    ExternalLaunchRequest,
    FilterState,
    ForegroundOperationState,
    GoToHomeDirectory,
    GoToParentDirectory,
    LoadBrowserSnapshotEffect,
    LoadChildPaneSnapshotEffect,
    LoadCurrentPaneEffect,
    MoveCursorAndSelectRange,
    NotificationState,
    OpenPathInEditor,
    OpenPathInGuiEditor,
    OpenPathWithDefaultApp,
    OpenTerminalAtPath,
    PaneState,
    Path,
    ReloadDirectory,
    RequestBrowserSnapshot,
    RequestDirectorySizes,
    RunDirectorySizeEffect,
    RunExternalLaunchEffect,
    SetCursorPath,
    SetFilterQuery,
    SetNotification,
    SetSort,
    SetUiMode,
    SortState,
    ToggleSelection,
    _reduce_state,
    build_initial_app_state,
    datetime,
    reduce_app_state,
    replace,
)


def test_set_ui_mode_updates_only_mode() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(state, SetUiMode("FILTER"))

    assert next_state.ui_mode == "FILTER"
    assert next_state.current_pane == state.current_pane
    assert next_state.filter == state.filter

def test_request_directory_sizes_marks_paths_pending_and_emits_effect() -> None:
    state = build_initial_app_state()

    result = reduce_app_state(
        state,
        RequestDirectorySizes(("/home/tadashi/develop/zivo/docs",)),
    )

    assert result.state.pending_directory_size_request_id == 1
    assert result.state.directory_size_cache == (
        DirectorySizeCacheEntry("/home/tadashi/develop/zivo/docs", "pending"),
    )
    assert result.effects == (
        RunDirectorySizeEffect(
            request_id=1,
            paths=("/home/tadashi/develop/zivo/docs",),
        ),
    )

def test_request_browser_snapshot_clears_directory_size_cache() -> None:
    state = replace(
        build_initial_app_state(),
        directory_size_cache=(
            DirectorySizeCacheEntry("/home/tadashi/develop/zivo/docs", "ready", size_bytes=123),
        ),
        pending_directory_size_request_id=7,
    )

    next_state = reduce_app_state(
        state,
        RequestBrowserSnapshot("/home/tadashi/develop/zivo", blocking=True),
    ).state

    assert next_state.directory_size_cache == ()
    assert next_state.pending_directory_size_request_id is None

def test_directory_sizes_loaded_updates_cache_when_request_matches() -> None:
    state = replace(
        build_initial_app_state(),
        directory_size_cache=(
            DirectorySizeCacheEntry("/home/tadashi/develop/zivo/docs", "pending"),
        ),
        pending_directory_size_request_id=9,
    )

    next_state = _reduce_state(
        state,
        DirectorySizesLoaded(
            request_id=9,
            sizes=(("/home/tadashi/develop/zivo/docs", 4321),),
        ),
    )

    assert next_state.directory_size_cache == (
        DirectorySizeCacheEntry("/home/tadashi/develop/zivo/docs", "ready", size_bytes=4321),
    )
    assert next_state.directory_size_delta == DirectorySizeDeltaState(
        changed_paths=("/home/tadashi/develop/zivo/docs",),
        revision=1,
    )
    assert next_state.pending_directory_size_request_id is None

def test_directory_sizes_loaded_marks_partial_failures() -> None:
    state = replace(
        build_initial_app_state(),
        directory_size_cache=(
            DirectorySizeCacheEntry("/home/tadashi/develop/zivo/docs", "pending"),
            DirectorySizeCacheEntry("/home/tadashi/develop/zivo/private", "pending"),
        ),
        pending_directory_size_request_id=9,
    )

    next_state = _reduce_state(
        state,
        DirectorySizesLoaded(
            request_id=9,
            sizes=(("/home/tadashi/develop/zivo/docs", 4321),),
            failures=(("/home/tadashi/develop/zivo/private", "Permission denied"),),
        ),
    )

    assert next_state.directory_size_cache == (
        DirectorySizeCacheEntry("/home/tadashi/develop/zivo/docs", "ready", size_bytes=4321),
        DirectorySizeCacheEntry(
            "/home/tadashi/develop/zivo/private",
            "failed",
            error_message="Permission denied",
        ),
    )
    assert next_state.directory_size_delta == DirectorySizeDeltaState(
        changed_paths=(
            "/home/tadashi/develop/zivo/docs",
            "/home/tadashi/develop/zivo/private",
        ),
        revision=1,
    )
    assert next_state.pending_directory_size_request_id is None

def test_directory_sizes_failed_marks_requested_paths_failed() -> None:
    state = replace(
        build_initial_app_state(),
        directory_size_cache=(
            DirectorySizeCacheEntry("/home/tadashi/develop/zivo/docs", "pending"),
        ),
        pending_directory_size_request_id=4,
    )

    next_state = _reduce_state(
        state,
        DirectorySizesFailed(
            request_id=4,
            paths=("/home/tadashi/develop/zivo/docs",),
            message="Permission denied",
        ),
    )

    assert next_state.directory_size_cache == (
        DirectorySizeCacheEntry(
            "/home/tadashi/develop/zivo/docs",
            "failed",
            error_message="Permission denied",
        ),
    )
    assert next_state.directory_size_delta == DirectorySizeDeltaState(
        changed_paths=("/home/tadashi/develop/zivo/docs",),
        revision=1,
    )
    assert next_state.pending_directory_size_request_id is None

def test_non_directory_size_action_clears_transient_directory_size_delta() -> None:
    state = replace(
        build_initial_app_state(),
        directory_size_delta=DirectorySizeDeltaState(
            changed_paths=("/home/tadashi/develop/zivo/docs",),
            revision=4,
        ),
    )

    result = reduce_app_state(
        state,
        SetNotification(NotificationState(level="info", message="Ready")),
    )

    assert result.state.notification == NotificationState(level="info", message="Ready")
    assert result.state.directory_size_delta == DirectorySizeDeltaState(revision=4)

def test_toggle_selection_sets_transient_current_pane_delta() -> None:
    state = build_initial_app_state()
    path = "/home/tadashi/develop/zivo/README.md"

    next_state = _reduce_state(state, ToggleSelection(path))

    assert next_state.current_pane.selected_paths == frozenset({path})
    assert next_state.current_pane_delta == CurrentPaneDeltaState(
        changed_paths=(path,),
        revision=1,
    )

def test_cut_targets_sets_transient_current_pane_delta() -> None:
    state = build_initial_app_state()
    path = "/home/tadashi/develop/zivo/docs"

    next_state = _reduce_state(state, CutTargets((path,)))

    assert next_state.clipboard.mode == "cut"
    assert next_state.current_pane_delta == CurrentPaneDeltaState(
        changed_paths=(path,),
        revision=1,
    )

def test_move_cursor_and_select_range_sets_transient_current_pane_delta() -> None:
    state = build_initial_app_state()
    visible_paths = tuple(entry.path for entry in state.current_pane.entries)

    next_state = _reduce_state(
        state,
        MoveCursorAndSelectRange(delta=1, visible_paths=visible_paths),
    )

    assert next_state.current_pane.selected_paths == frozenset(
        {
            "/home/tadashi/develop/zivo/docs",
            "/home/tadashi/develop/zivo/src",
        }
    )
    assert next_state.current_pane_delta == CurrentPaneDeltaState(
        changed_paths=(
            "/home/tadashi/develop/zivo/docs",
            "/home/tadashi/develop/zivo/src",
        ),
        revision=1,
    )

def test_non_selection_action_clears_transient_current_pane_delta() -> None:
    state = replace(
        build_initial_app_state(),
        current_pane_delta=CurrentPaneDeltaState(
            changed_paths=("/home/tadashi/develop/zivo/docs",),
            revision=4,
        ),
    )

    result = reduce_app_state(
        state,
        SetNotification(NotificationState(level="info", message="Ready")),
    )

    assert result.state.notification == NotificationState(level="info", message="Ready")
    assert result.state.current_pane_delta == CurrentPaneDeltaState(revision=4)

def test_toggle_selection_uses_absolute_paths() -> None:
    state = build_initial_app_state()
    path = "/home/tadashi/develop/zivo/README.md"

    selected_state = _reduce_state(state, ToggleSelection(path))
    cleared_state = _reduce_state(selected_state, ToggleSelection(path))

    assert selected_state.current_pane.selected_paths == frozenset({path})
    assert cleared_state.current_pane.selected_paths == frozenset()

def test_clear_selection_empties_selection() -> None:
    state = build_initial_app_state()
    selected_state = _reduce_state(
        state,
        ToggleSelection("/home/tadashi/develop/zivo/README.md"),
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

def test_set_sort_keeps_cursor_on_same_visible_path() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, SetCursorPath("/home/tadashi/develop/zivo/README.md"))

    next_state = _reduce_state(
        state,
        SetSort(field="modified", descending=True, directories_first=False),
    )

    assert next_state.current_pane.cursor_path == "/home/tadashi/develop/zivo/README.md"

def test_set_sort_normalizes_cursor_to_first_visible_path_when_hidden() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, SetFilterQuery("py"))

    next_state = _reduce_state(
        state,
        SetSort(field="name", descending=False, directories_first=True),
    )

    assert next_state.current_pane.cursor_path == "/home/tadashi/develop/zivo/pyproject.toml"

def test_set_cursor_path_ignores_unknown_path() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(state, SetCursorPath("/missing"))

    assert next_state == state

def test_enter_cursor_directory_requests_blocking_snapshot_when_child_pane_is_stale() -> None:
    state = replace(
        build_initial_app_state(),
        child_pane=PaneState(
            directory_path="/home/tadashi/develop/zivo/src",
            entries=(),
        ),
    )

    result = reduce_app_state(state, EnterCursorDirectory())

    assert result.state.pending_browser_snapshot_request_id == 1
    assert result.state.ui_mode == "BUSY"
    assert result.effects == (
        LoadBrowserSnapshotEffect(
            request_id=1,
            path="/home/tadashi/develop/zivo/docs",
            cursor_path=None,
            blocking=True,
        ),
    )

def test_blocking_navigation_snapshot_is_nonblocking_during_long_running_operation() -> None:
    state = replace(
        build_initial_app_state(),
        foreground_operation=ForegroundOperationState(operation_id=4, kind="copy"),
    )

    result = reduce_app_state(
        state,
        RequestBrowserSnapshot("/tmp/next", blocking=True),
    )

    assert result.state.ui_mode == "BROWSING"
    assert result.effects == (
        LoadCurrentPaneEffect(
            request_id=1,
            path="/tmp/next",
            cursor_path=None,
            invalidate_paths=(),
        ),
    )

def test_enter_cursor_directory_promotes_matching_child_pane() -> None:
    state = replace(
        build_initial_app_state(),
        current_path="/tmp/project",
        current_pane=PaneState(
            directory_path="/tmp/project",
            entries=(
                DirectoryEntryState("/tmp/project/docs", "docs", "dir"),
                DirectoryEntryState("/tmp/project/README.md", "README.md", "file"),
            ),
            cursor_path="/tmp/project/docs",
        ),
        child_pane=PaneState(
            directory_path="/tmp/project/docs",
            entries=(
                DirectoryEntryState(
                    "/tmp/project/docs/api",
                    "api",
                    "dir",
                    modified_at=datetime(2026, 1, 1),
                    permissions_mode=0o40755,
                ),
                DirectoryEntryState(
                    "/tmp/project/docs/guide.md",
                    "guide.md",
                    "file",
                    size_bytes=42,
                    modified_at=datetime(2026, 1, 1),
                    permissions_mode=0o100644,
                ),
            ),
        ),
        directory_size_cache=(
            DirectorySizeCacheEntry(
                path="/tmp/project/docs/api",
                status="ready",
                size_bytes=128,
            ),
        ),
        pending_directory_size_request_id=99,
    )

    result = reduce_app_state(state, EnterCursorDirectory())

    assert result.state.current_path == "/tmp/project/docs"
    assert result.state.parent_pane == PaneState(
        directory_path="/tmp/project",
        entries=state.current_pane.entries,
        cursor_path="/tmp/project/docs",
    )
    assert result.state.current_pane == PaneState(
        directory_path="/tmp/project/docs",
        entries=state.child_pane.entries,
        cursor_path="/tmp/project/docs/api",
    )
    assert result.state.child_pane == PaneState(
        directory_path="/tmp/project/docs",
        entries=(),
    )
    assert result.state.directory_size_cache == (
        DirectorySizeCacheEntry("/tmp/project/docs/api", "pending"),
    )
    assert result.state.pending_browser_snapshot_request_id is None
    assert result.state.pending_child_pane_request_id == 1
    assert result.state.pending_directory_size_request_id == 2
    assert result.state.history.back == ("/tmp/project",)
    assert result.state.history.forward == ()
    assert result.effects == (
        LoadChildPaneSnapshotEffect(
            request_id=1,
            current_path="/tmp/project/docs",
            cursor_path="/tmp/project/docs/api",
        ),
        RunDirectorySizeEffect(
            request_id=2,
            paths=("/tmp/project/docs/api",),
        ),
    )

def test_enter_cursor_directory_does_not_promote_lightweight_child_entries() -> None:
    state = replace(
        build_initial_app_state(),
        current_path="/tmp/project",
        current_pane=PaneState(
            directory_path="/tmp/project",
            entries=(DirectoryEntryState("/tmp/project/docs", "docs", "dir"),),
            cursor_path="/tmp/project/docs",
        ),
        child_pane=PaneState(
            directory_path="/tmp/project/docs",
            entries=(
                DirectoryEntryState("/tmp/project/docs/guide.md", "guide.md", "file"),
            ),
        ),
    )

    result = reduce_app_state(state, EnterCursorDirectory())

    assert result.state.pending_browser_snapshot_request_id == 1
    assert result.effects == (
        LoadBrowserSnapshotEffect(
            request_id=1,
            path="/tmp/project/docs",
            cursor_path=None,
            blocking=True,
        ),
    )

def test_enter_cursor_directory_with_active_filter_falls_back_to_snapshot() -> None:
    state = replace(
        build_initial_app_state(),
        current_path="/tmp/project",
        current_pane=PaneState(
            directory_path="/tmp/project",
            entries=(DirectoryEntryState("/tmp/project/docs", "docs", "dir"),),
            cursor_path="/tmp/project/docs",
        ),
        child_pane=PaneState(
            directory_path="/tmp/project/docs",
            entries=(DirectoryEntryState("/tmp/project/docs/api", "api", "dir"),),
        ),
        filter=replace(build_initial_app_state().filter, query="do", active=True),
    )

    result = reduce_app_state(state, EnterCursorDirectory())

    assert result.state.pending_browser_snapshot_request_id == 1
    assert result.state.ui_mode == "BUSY"
    assert result.effects == (
        LoadBrowserSnapshotEffect(
            request_id=1,
            path="/tmp/project/docs",
            cursor_path=None,
            blocking=True,
        ),
    )

def test_enter_cursor_directory_with_stale_child_pane_falls_back_to_snapshot() -> None:
    state = replace(
        build_initial_app_state(),
        current_path="/tmp/project",
        current_pane=PaneState(
            directory_path="/tmp/project",
            entries=(DirectoryEntryState("/tmp/project/docs", "docs", "dir"),),
            cursor_path="/tmp/project/docs",
        ),
        child_pane=PaneState(
            directory_path="/tmp/project/src",
            entries=(DirectoryEntryState("/tmp/project/src/main.py", "main.py", "file"),),
        ),
    )

    result = reduce_app_state(state, EnterCursorDirectory())

    assert result.state.pending_browser_snapshot_request_id == 1
    assert result.state.ui_mode == "BUSY"
    assert result.effects == (
        LoadBrowserSnapshotEffect(
            request_id=1,
            path="/tmp/project/docs",
            cursor_path=None,
            blocking=True,
        ),
    )

def test_go_to_parent_directory_restores_cursor_to_previous_child() -> None:
    state = build_initial_app_state()

    result = reduce_app_state(state, GoToParentDirectory())

    assert result.state.pending_browser_snapshot_request_id == 1
    assert result.state.ui_mode == "BUSY"
    assert len(result.effects) == 1
    assert result.effects[0].path == str(Path("/home/tadashi/develop/zivo").parent)
    assert result.effects[0].cursor_path == "/home/tadashi/develop/zivo"
    assert result.effects[0].blocking is True

def test_go_to_parent_directory_uses_current_path_parent() -> None:
    state = build_initial_app_state()
    state = _reduce_state(
        state,
        BrowserSnapshotLoaded(
            request_id=99,
            snapshot=BrowserSnapshot(
                current_path="/tmp/work/project",
                parent_pane=state.parent_pane,
                current_pane=state.current_pane,
                child_pane=state.child_pane,
            ),
        ),
    )
    state = _reduce_state(state, RequestBrowserSnapshot("/tmp/work/project"))
    state = _reduce_state(
        state,
        BrowserSnapshotLoaded(
            request_id=1,
            snapshot=BrowserSnapshot(
                current_path="/tmp/work/project",
                parent_pane=state.parent_pane,
                current_pane=state.current_pane,
                child_pane=state.child_pane,
            ),
            blocking=True,
        ),
    )

    result = reduce_app_state(state, GoToParentDirectory())

    assert len(result.effects) == 1
    assert result.effects[0].path == str(Path("/tmp/work/project").parent)
    assert result.effects[0].cursor_path == "/tmp/work/project"

def test_go_to_home_directory_navigates_to_home() -> None:
    state = build_initial_app_state()

    result = reduce_app_state(state, GoToHomeDirectory())

    assert result.state.pending_browser_snapshot_request_id == 1
    assert result.state.ui_mode == "BUSY"
    assert len(result.effects) == 1
    # Home directory path will be expanded and resolved
    assert result.effects[0].blocking is True
    assert str(Path.home()) in result.effects[0].path

def test_go_to_parent_directory_from_windows_drive_root_requests_drive_list(
    monkeypatch,
) -> None:
    monkeypatch.setattr("zivo.windows_paths.platform.system", lambda: "Windows")
    state = replace(
        build_initial_app_state(),
        current_path="C:\\",
        parent_pane=PaneState(
            directory_path=WINDOWS_DRIVES_ROOT,
            entries=(
                DirectoryEntryState("C:\\", "C:\\", "dir"),
                DirectoryEntryState("D:\\", "D:\\", "dir"),
            ),
            cursor_path="C:\\",
        ),
        current_pane=PaneState(
            directory_path="C:\\",
            entries=(DirectoryEntryState("C:\\Users", "Users", "dir"),),
            cursor_path="C:\\Users",
        ),
        child_pane=PaneState(directory_path="C:\\Users", entries=()),
    )

    result = reduce_app_state(state, GoToParentDirectory())

    assert len(result.effects) == 1
    assert result.effects[0].path == WINDOWS_DRIVES_ROOT
    assert result.effects[0].cursor_path == "C:\\"

def test_reload_directory_requests_snapshot_with_current_cursor() -> None:
    state = build_initial_app_state()
    cursor = f"{state.current_path}/src"
    state = _reduce_state(state, SetCursorPath(cursor))

    result = reduce_app_state(state, ReloadDirectory())

    assert result.state.pending_browser_snapshot_request_id == 3
    assert result.state.ui_mode == "BUSY"
    assert len(result.effects) == 1
    assert result.effects[0].path == state.current_path
    assert result.effects[0].cursor_path == cursor
    assert result.effects[0].blocking is True
    assert result.effects[0].invalidate_paths == tuple(
        str(Path(p).resolve())
        for p in (
            state.current_path,
            str(Path(state.current_path).parent),
            cursor,
        )
    )

def test_open_path_with_default_app_emits_external_launch_effect() -> None:
    state = replace(
        build_initial_app_state(),
        current_pane=replace(
            build_initial_app_state().current_pane,
            cursor_path="/home/tadashi/develop/zivo/README.md",
        ),
    )

    result = reduce_app_state(
        state,
        OpenPathWithDefaultApp("/home/tadashi/develop/zivo/README.md"),
    )

    assert result.state.ui_mode == "BROWSING"
    assert result.state.next_request_id == 2
    assert result.effects == (
        RunExternalLaunchEffect(
            request_id=1,
            request=ExternalLaunchRequest(
                kind="open_file",
                path="/home/tadashi/develop/zivo/README.md",
            ),
        ),
    )

def test_open_path_in_editor_emits_external_launch_effect() -> None:
    state = replace(
        build_initial_app_state(),
        current_pane=replace(
            build_initial_app_state().current_pane,
            cursor_path="/home/tadashi/develop/zivo/README.md",
        ),
    )

    result = reduce_app_state(
        state,
        OpenPathInEditor("/home/tadashi/develop/zivo/README.md"),
    )

    assert result.state.ui_mode == "BROWSING"
    assert result.state.next_request_id == 2
    assert result.effects == (
        RunExternalLaunchEffect(
            request_id=1,
            request=ExternalLaunchRequest(
                kind="open_editor",
                path="/home/tadashi/develop/zivo/README.md",
            ),
        ),
    )

def test_open_path_in_editor_with_line_number_emits_external_launch_effect() -> None:
    state = replace(
        build_initial_app_state(),
        current_pane=replace(
            build_initial_app_state().current_pane,
            cursor_path="/home/tadashi/develop/zivo/README.md",
        ),
    )

    result = reduce_app_state(
        state,
        OpenPathInEditor("/home/tadashi/develop/zivo/README.md", line_number=42),
    )

    assert result.state.ui_mode == "BROWSING"
    assert result.state.next_request_id == 2
    assert result.effects == (
        RunExternalLaunchEffect(
            request_id=1,
            request=ExternalLaunchRequest(
                kind="open_editor",
                path="/home/tadashi/develop/zivo/README.md",
                line_number=42,
            ),
        ),
    )

def test_completed_foreground_editor_refreshes_matching_current_directory() -> None:
    state = replace(
        build_initial_app_state(),
        current_path="/tmp/project",
        current_pane=PaneState(
            directory_path="/tmp/project",
            entries=(DirectoryEntryState("/tmp/project/README.md", "README.md", "file"),),
            cursor_path="/tmp/project/README.md",
        ),
    )

    result = reduce_app_state(
        state,
        ExternalLaunchCompleted(
            request_id=4,
            request=ExternalLaunchRequest(
                kind="open_editor",
                path="/tmp/project/README.md",
            ),
        ),
    )

    assert result.state.pending_browser_snapshot_request_id == 1
    assert result.state.ui_mode == "BROWSING"
    assert result.effects == (
        LoadBrowserSnapshotEffect(
            request_id=1,
            path="/tmp/project",
            cursor_path="/tmp/project/README.md",
            blocking=False,
            invalidate_paths=tuple(
                str(Path(path).resolve())
                for path in ("/tmp/project", "/tmp", "/tmp/project/README.md")
            ),
            enable_image_preview=True,
            enable_pdf_preview=True,
            enable_office_preview=True,
        ),
    )

def test_completed_external_launch_excludes_gui_editor_and_terminal_window() -> None:
    state = replace(build_initial_app_state(), current_path="/tmp/project")

    gui_result = reduce_app_state(
        state,
        ExternalLaunchCompleted(
            request_id=1,
            request=ExternalLaunchRequest(
                kind="open_gui_editor",
                path="/tmp/project/README.md",
            ),
        ),
    )
    window_result = reduce_app_state(
        state,
        ExternalLaunchCompleted(
            request_id=2,
            request=ExternalLaunchRequest(
                kind="open_terminal",
                path="/tmp/project",
                terminal_launch_mode="window",
            ),
        ),
    )

    assert gui_result.effects == ()
    assert window_result.effects == ()

def test_completed_foreground_terminal_refreshes_matching_current_directory() -> None:
    state = replace(build_initial_app_state(), current_path="/tmp/project")

    result = reduce_app_state(
        state,
        ExternalLaunchCompleted(
            request_id=1,
            request=ExternalLaunchRequest(
                kind="open_terminal",
                path="/tmp/project",
                terminal_launch_mode="foreground",
            ),
        ),
    )

    assert result.state.pending_browser_snapshot_request_id == 1
    assert result.effects[0].path == "/tmp/project"

def test_external_refresh_skips_virtual_search_workspace() -> None:
    state = replace(
        build_initial_app_state(),
        current_path="search://query?root=%2Ftmp%2Fproject",
    )

    result = reduce_app_state(
        state,
        ExternalLaunchCompleted(
            request_id=1,
            request=ExternalLaunchRequest(
                kind="open_editor",
                path="/tmp/project/README.md",
            ),
        ),
    )

    assert result.effects == ()

def test_external_refresh_skips_archive_virtual_path() -> None:
    state = replace(
        build_initial_app_state(),
        current_path="/tmp/project/archive.zip/src",
    )

    result = reduce_app_state(
        state,
        ExternalLaunchCompleted(
            request_id=1,
            request=ExternalLaunchRequest(
                kind="open_editor",
                path="/tmp/project/archive.zip/src/README.md",
            ),
        ),
    )

    assert result.effects == ()

def test_external_refresh_completion_wins_over_manual_reload_without_busy_mode() -> None:
    state = replace(
        build_initial_app_state(),
        current_path="/tmp/project",
        ui_mode="BUSY",
        pending_browser_snapshot_request_id=9,
        next_request_id=10,
    )

    result = reduce_app_state(
        state,
        ExternalLaunchCompleted(
            request_id=8,
            request=ExternalLaunchRequest(
                kind="open_editor",
                path="/tmp/project/README.md",
            ),
        ),
    )

    assert result.state.pending_browser_snapshot_request_id == 10
    assert result.state.ui_mode == "BROWSING"
    assert result.effects[0].request_id == 10

    stale = reduce_app_state(
        result.state,
        BrowserSnapshotLoaded(
            request_id=9,
            snapshot=BrowserSnapshot(
                current_path="/tmp/project",
                parent_pane=PaneState(directory_path="/tmp", entries=()),
                current_pane=PaneState(directory_path="/tmp/project", entries=()),
                child_pane=PaneState(directory_path="/tmp/project", entries=()),
            ),
        ),
    )
    assert stale.state.pending_browser_snapshot_request_id == 10

def test_external_refresh_applies_new_entries_while_preserving_view_state() -> None:
    state = replace(
        build_initial_app_state(),
        current_path="/tmp/project",
        filter=FilterState(query="read", active=True),
        sort=SortState(field="modified", descending=True, directories_first=False),
        current_pane=PaneState(
            directory_path="/tmp/project",
            entries=(DirectoryEntryState("/tmp/project/README.md", "README.md", "file"),),
            cursor_path="/tmp/project/README.md",
            selected_paths=frozenset({"/tmp/project/README.md"}),
            selection_anchor_path="/tmp/project/README.md",
        ),
    )
    started = reduce_app_state(
        state,
        ExternalLaunchCompleted(
            request_id=1,
            request=ExternalLaunchRequest(
                kind="open_editor",
                path="/tmp/project/README.md",
            ),
        ),
    )
    loaded = reduce_app_state(
        started.state,
        BrowserSnapshotLoaded(
            request_id=started.state.pending_browser_snapshot_request_id or 0,
            snapshot=BrowserSnapshot(
                current_path="/tmp/project",
                parent_pane=PaneState(directory_path="/tmp", entries=()),
                current_pane=PaneState(
                    directory_path="/tmp/project",
                    entries=(
                        DirectoryEntryState(
                            "/tmp/project/README.md",
                            "README.md",
                            "file",
                        ),
                        DirectoryEntryState("/tmp/project/new.txt", "new.txt", "file"),
                    ),
                    cursor_path="/tmp/project/README.md",
                ),
                child_pane=PaneState(directory_path="/tmp/project", entries=()),
            ),
        ),
    )

    assert loaded.state.current_pane.cursor_path == "/tmp/project/README.md"
    assert loaded.state.current_pane.selected_paths == frozenset({"/tmp/project/README.md"})
    assert loaded.state.filter == FilterState(query="read", active=True)
    assert loaded.state.sort == SortState(
        field="modified",
        descending=True,
        directories_first=False,
    )

def test_open_path_in_gui_editor_emits_external_launch_effect() -> None:
    state = build_initial_app_state()

    result = reduce_app_state(
        state,
        OpenPathInGuiEditor(
            "/home/tadashi/develop/zivo/README.md",
            line_number=42,
            column_number=7,
        ),
    )

    assert result.state.ui_mode == "BROWSING"
    assert result.state.next_request_id == 2
    assert result.effects == (
        RunExternalLaunchEffect(
            request_id=1,
            request=ExternalLaunchRequest(
                kind="open_gui_editor",
                path="/home/tadashi/develop/zivo/README.md",
                line_number=42,
                column_number=7,
            ),
        ),
    )

def test_open_terminal_at_path_emits_external_launch_effect() -> None:
    state = build_initial_app_state()

    result = reduce_app_state(
        state,
        OpenTerminalAtPath("/home/tadashi/develop/zivo", launch_mode="foreground"),
    )

    assert result.state.next_request_id == 2
    assert result.effects == (
        RunExternalLaunchEffect(
            request_id=1,
            request=ExternalLaunchRequest(
                kind="open_terminal",
                path="/home/tadashi/develop/zivo",
                terminal_launch_mode="foreground",
            ),
        ),
    )
