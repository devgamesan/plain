from dataclasses import replace
from pathlib import Path

from tests.state_test_helpers import reduce_state
from zivo.models import (
    AppConfig,
    BookmarkConfig,
    ExternalLaunchRequest,
)
from zivo.state import (
    BrowserSnapshot,
    ConfigEditorState,
    CurrentPaneDeltaState,
    DirectoryEntryState,
    DirectorySizeCacheEntry,
    DirectorySizeDeltaState,
    HistoryState,
    LoadBrowserSnapshotEffect,
    LoadChildPaneSnapshotEffect,
    NameConflictState,
    NotificationState,
    PaneState,
    PendingInputState,
    PendingKeySequenceState,
    RunConfigSaveEffect,
    RunDirectorySizeEffect,
    RunExternalLaunchEffect,
    build_initial_app_state,
    reduce_app_state,
    select_browser_tabs,
)
from zivo.state.actions import (
    ActivateNextTab,
    ActivatePreviousTab,
    ActivateTabByIndex,
    AddBookmark,
    BeginFilterInput,
    BeginHistorySearch,
    BrowserSnapshotFailed,
    BrowserSnapshotLoaded,
    CancelFilterInput,
    ChildPaneSnapshotFailed,
    ChildPaneSnapshotLoaded,
    ClearSelection,
    CloseCurrentTab,
    ConfigSaveCompleted,
    ConfigSaveFailed,
    ConfirmFilterInput,
    CopyPathsToClipboard,
    CutTargets,
    CycleConfigEditorValue,
    DirectorySizesFailed,
    DirectorySizesLoaded,
    DismissConfigEditor,
    DismissNameConflict,
    EnterCursorDirectory,
    ExternalLaunchCompleted,
    ExternalLaunchFailed,
    GoBack,
    GoForward,
    GoToHomeDirectory,
    GoToParentDirectory,
    JumpCursor,
    MoveConfigEditorCursor,
    MoveCursor,
    MoveCursorAndSelectRange,
    MoveCursorByPage,
    OpenNewTab,
    OpenPathInEditor,
    OpenPathWithDefaultApp,
    OpenTerminalAtPath,
    ReloadDirectory,
    RemoveBookmark,
    RequestBrowserSnapshot,
    RequestDirectorySizes,
    SaveConfigEditor,
    SetCursorPath,
    SetFilterQuery,
    SetNotification,
    SetPendingKeySequence,
    SetSort,
    SetTerminalHeight,
    SetUiMode,
    ToggleHiddenFiles,
    ToggleSelection,
)
from zivo.windows_paths import WINDOWS_DRIVES_ROOT


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
                DirectoryEntryState("/tmp/project/docs/api", "api", "dir"),
                DirectoryEntryState("/tmp/project/docs/guide.md", "guide.md", "file"),
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

def test_begin_filter_input_switches_mode_without_mutating_query() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(state, BeginFilterInput())

    assert next_state.ui_mode == "FILTER"
    assert next_state.filter == state.filter

def test_move_config_editor_cursor_clamps_to_visible_settings() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
        ),
    )

    next_state = _reduce_state(state, MoveConfigEditorCursor(delta=99))

    assert next_state.config_editor is not None
    assert next_state.config_editor.cursor_index == 17

def test_cycle_config_editor_editor_command_updates_draft_and_dirty_state() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
            cursor_index=0,
        ),
    )

    next_state = _reduce_state(state, CycleConfigEditorValue(delta=1))

    assert next_state.config_editor is not None
    assert next_state.config_editor.draft.editor.command == "nvim"
    assert next_state.config_editor.dirty is True

def test_cycle_config_editor_value_updates_draft_and_dirty_state() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
            cursor_index=1,
        ),
    )

    next_state = _reduce_state(state, CycleConfigEditorValue(delta=1))

    assert next_state.config_editor is not None
    assert next_state.config_editor.draft.display.show_hidden_files is True
    assert next_state.config_editor.dirty is True

def test_cycle_config_editor_theme_updates_draft_and_dirty_state() -> None:
    original_state = build_initial_app_state(config_path="/tmp/zivo/config.toml")
    state = replace(
        original_state,
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=original_state.config,
            cursor_index=2,
        ),
    )

    next_state = _reduce_state(state, CycleConfigEditorValue(delta=1))

    assert next_state.config_editor is not None
    assert next_state.config_editor.draft.display.theme == "textual-light"
    assert next_state.config.display.theme == "textual-dark"
    assert next_state.config_editor.dirty is True

def test_cycle_config_editor_theme_supports_all_builtin_themes() -> None:
    base_state = build_initial_app_state()
    themed_config = replace(
        base_state.config,
        display=replace(base_state.config.display, theme="solarized-light"),
    )
    state = replace(
        base_state,
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=themed_config,
            cursor_index=2,
        ),
    )

    next_state = _reduce_state(state, CycleConfigEditorValue(delta=1))

    assert next_state.config_editor is not None
    assert next_state.config_editor.draft.display.theme == "textual-ansi"
    assert next_state.config_editor.dirty is True

def test_cycle_config_editor_directory_size_visibility_updates_draft_and_dirty_state() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
            cursor_index=3,
        ),
    )

    next_state = _reduce_state(state, CycleConfigEditorValue(delta=1))

    assert next_state.config_editor is not None
    assert next_state.config_editor.draft.display.show_directory_sizes is False
    assert next_state.config_editor.dirty is True

def test_cycle_config_editor_text_preview_updates_draft_and_dirty_state() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
            cursor_index=4,
        ),
    )

    next_state = _reduce_state(state, CycleConfigEditorValue(delta=1))

    assert next_state.config_editor is not None
    assert next_state.config_editor.draft.display.enable_text_preview is False
    assert next_state.config_editor.dirty is True

def test_cycle_config_editor_image_preview_updates_draft_and_dirty_state() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
            cursor_index=5,
        ),
    )

    next_state = _reduce_state(state, CycleConfigEditorValue(delta=1))

    assert next_state.config_editor is not None
    assert next_state.config_editor.draft.display.enable_image_preview is False
    assert next_state.config_editor.dirty is True

def test_cycle_config_editor_pdf_preview_updates_draft_and_dirty_state() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
            cursor_index=6,
        ),
    )

    next_state = _reduce_state(state, CycleConfigEditorValue(delta=1))

    assert next_state.config_editor is not None
    assert next_state.config_editor.draft.display.enable_pdf_preview is False
    assert next_state.config_editor.dirty is True

def test_cycle_config_editor_office_preview_updates_draft_and_dirty_state() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
            cursor_index=7,
        ),
    )

    next_state = _reduce_state(state, CycleConfigEditorValue(delta=1))

    assert next_state.config_editor is not None
    assert next_state.config_editor.draft.display.enable_office_preview is False
    assert next_state.config_editor.dirty is True

def test_cycle_config_editor_preview_syntax_theme_updates_draft_and_dirty_state() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
            cursor_index=8,
        ),
    )

    next_state = _reduce_state(state, CycleConfigEditorValue(delta=1))

    assert next_state.config_editor is not None
    assert next_state.config_editor.draft.display.preview_syntax_theme == "abap"
    assert next_state.config_editor.dirty is True

def test_cycle_config_editor_preview_max_kib_updates_draft_and_dirty_state() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
            cursor_index=9,
        ),
    )

    next_state = _reduce_state(state, CycleConfigEditorValue(delta=1))

    assert next_state.config_editor is not None
    assert next_state.config_editor.draft.display.preview_max_kib == 128
    assert next_state.config_editor.dirty is True

def test_save_config_editor_emits_config_save_effect() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=replace(
                build_initial_app_state().config,
                behavior=replace(build_initial_app_state().config.behavior, confirm_delete=False),
            ),
            dirty=True,
        ),
    )

    result = reduce_app_state(state, SaveConfigEditor())

    assert result.state.pending_config_save_request_id == 1
    assert result.state.next_request_id == 2
    assert result.effects == (
        RunConfigSaveEffect(
            request_id=1,
            path="/tmp/zivo/config.toml",
            config=result.state.config_editor.draft,
        ),
    )

def test_add_bookmark_emits_config_save_effect() -> None:
    state = build_initial_app_state(config_path="/tmp/zivo/config.toml")

    result = reduce_app_state(state, AddBookmark(path="/home/tadashi/develop/zivo"))

    assert result.state.pending_config_save_request_id == 1
    assert result.effects == (
        RunConfigSaveEffect(
            request_id=1,
            path="/tmp/zivo/config.toml",
            config=AppConfig(
                bookmarks=BookmarkConfig(paths=("/home/tadashi/develop/zivo",))
            ),
        ),
    )

def test_add_bookmark_ignores_duplicate_path() -> None:
    state = build_initial_app_state(
        config=AppConfig(bookmarks=BookmarkConfig(paths=("/home/tadashi/develop/zivo",)))
    )

    next_state = _reduce_state(state, AddBookmark(path="/home/tadashi/develop/zivo"))

    assert next_state.notification == NotificationState(
        level="info",
        message="Directory is already bookmarked",
    )

def test_remove_bookmark_emits_config_save_effect() -> None:
    state = build_initial_app_state(
        config_path="/tmp/zivo/config.toml",
        config=AppConfig(
            bookmarks=BookmarkConfig(
                paths=("/home/tadashi/develop/zivo", "/home/tadashi/src")
            )
        ),
    )

    result = reduce_app_state(state, RemoveBookmark(path="/home/tadashi/develop/zivo"))

    assert result.state.pending_config_save_request_id == 1
    assert result.effects == (
        RunConfigSaveEffect(
            request_id=1,
            path="/tmp/zivo/config.toml",
            config=AppConfig(
                bookmarks=BookmarkConfig(paths=("/home/tadashi/src",))
            ),
        ),
    )

def test_config_save_completed_updates_runtime_state_and_clears_dirty_flag() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=replace(
                build_initial_app_state().config,
                behavior=replace(build_initial_app_state().config.behavior, confirm_delete=False),
            ),
            dirty=True,
        ),
        pending_config_save_request_id=3,
    )

    saved_config = state.config_editor.draft
    next_state = _reduce_state(
        state,
        ConfigSaveCompleted(
            request_id=3,
            path="/tmp/zivo/config.toml",
            config=saved_config,
        ),
    )

    assert next_state.pending_config_save_request_id is None
    assert next_state.config == saved_config
    assert next_state.confirm_delete is False
    assert next_state.config_editor is not None
    assert next_state.config_editor.dirty is False

def test_config_save_completed_clears_preview_when_disabled() -> None:
    path = "/home/tadashi/develop/zivo/README.md"
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        current_pane=replace(
            build_initial_app_state().current_pane,
            cursor_path=path,
        ),
        child_pane=PaneState(
            directory_path="/home/tadashi/develop/zivo",
            entries=(),
            mode="preview",
            preview_path=path,
            preview_content="# Preview\n",
        ),
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=replace(
                build_initial_app_state().config,
                display=replace(
                    build_initial_app_state().config.display,
                    enable_text_preview=False,
                ),
            ),
            dirty=True,
        ),
        pending_config_save_request_id=3,
    )

    saved_config = state.config_editor.draft
    next_state = _reduce_state(
        state,
        ConfigSaveCompleted(
            request_id=3,
            path="/tmp/zivo/config.toml",
            config=saved_config,
        ),
    )

    assert next_state.config.display.enable_text_preview is False
    assert next_state.child_pane == PaneState(
        directory_path="/home/tadashi/develop/zivo",
        entries=(),
    )
    assert next_state.pending_child_pane_request_id is None

def test_config_save_completed_requests_preview_when_enabled() -> None:
    path = "/home/tadashi/develop/zivo/README.md"
    base_state = build_initial_app_state(config_path="/tmp/zivo/config.toml")
    state = replace(
        base_state,
        ui_mode="CONFIG",
        config=replace(
            base_state.config,
            display=replace(base_state.config.display, enable_text_preview=False),
        ),
        current_pane=replace(base_state.current_pane, cursor_path=path),
        child_pane=PaneState(directory_path="/home/tadashi/develop/zivo", entries=()),
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=replace(
                base_state.config,
                display=replace(base_state.config.display, enable_text_preview=True),
            ),
            dirty=True,
        ),
        pending_config_save_request_id=3,
    )

    saved_config = state.config_editor.draft
    result = reduce_app_state(
        state,
        ConfigSaveCompleted(
            request_id=3,
            path="/tmp/zivo/config.toml",
            config=saved_config,
        ),
    )

    assert result.state.config.display.enable_text_preview is True
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


def test_cycle_config_editor_file_search_max_results_updates_draft() -> None:
    """file_search.max_results をサイクルさせて設定を変更できることを確認."""
    original_state = build_initial_app_state(config_path="/tmp/zivo/config.toml")
    state = replace(
        original_state,
        ui_mode="CONFIG",
            config_editor=ConfigEditorState(
                path="/tmp/zivo/config.toml",
                draft=original_state.config,
                cursor_index=18,  # file_search.max_results
            ),
        )

    # None → 100
    next_state = _reduce_state(state, CycleConfigEditorValue(delta=1))

    assert next_state.config_editor is not None
    assert next_state.config_editor.draft.file_search.max_results == 100
    assert next_state.config_editor.dirty is True

    # 100 → 500
    next_state = _reduce_state(next_state, CycleConfigEditorValue(delta=1))

    assert next_state.config_editor is not None
    assert next_state.config_editor.draft.file_search.max_results == 500

    # 500 → 1000
    next_state = _reduce_state(next_state, CycleConfigEditorValue(delta=1))

    assert next_state.config_editor is not None
    assert next_state.config_editor.draft.file_search.max_results == 1000

    # 1000 → 5000
    next_state = _reduce_state(next_state, CycleConfigEditorValue(delta=1))

    assert next_state.config_editor is not None
    assert next_state.config_editor.draft.file_search.max_results == 5000

    # 5000 → 10000
    next_state = _reduce_state(next_state, CycleConfigEditorValue(delta=1))

    assert next_state.config_editor is not None
    assert next_state.config_editor.draft.file_search.max_results == 10000

    # 10000 → None (制限なしに戻る)
    next_state = _reduce_state(next_state, CycleConfigEditorValue(delta=1))

    assert next_state.config_editor is not None
    assert next_state.config_editor.draft.file_search.max_results is None


def test_config_save_failed_sets_error_notification() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        pending_config_save_request_id=4,
    )

    next_state = _reduce_state(state, ConfigSaveFailed(request_id=4, message="disk full"))

    assert next_state.pending_config_save_request_id is None
    assert next_state.notification == NotificationState(
        level="error",
        message="Failed to save config: disk full",
    )

def test_dismiss_config_editor_returns_to_browsing() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
        ),
    )

    next_state = _reduce_state(state, DismissConfigEditor())

    assert next_state.ui_mode == "BROWSING"
    assert next_state.config_editor is None

def test_copy_paths_to_clipboard_emits_external_launch_effect() -> None:
    result = reduce_app_state(build_initial_app_state(), CopyPathsToClipboard())

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
    hidden_path = "/home/tadashi/develop/zivo/.env"
    visible_path = "/home/tadashi/develop/zivo/docs"
    state = replace(
        build_initial_app_state(),
        show_hidden=True,
        current_pane=PaneState(
            directory_path="/home/tadashi/develop/zivo",
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
    )

def test_dismiss_name_conflict_restores_rename_mode_and_keeps_input() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        pending_input=PendingInputState(
            prompt="Rename: ",
            value="src",
            target_path="/home/tadashi/develop/zivo/docs",
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
            prompt="New file: ",
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
        "/home/tadashi/develop/zivo/docs",
        "/home/tadashi/develop/zivo/src",
        "/home/tadashi/develop/zivo/tests",
        "/home/tadashi/develop/zivo/README.md",
        "/home/tadashi/develop/zivo/pyproject.toml",
    )

    result = reduce_app_state(
        state,
        MoveCursorAndSelectRange(delta=1, visible_paths=visible_paths),
    )

    assert result.state.current_pane.cursor_path == "/home/tadashi/develop/zivo/src"
    assert result.state.current_pane.selected_paths == frozenset(
        {
            "/home/tadashi/develop/zivo/docs",
            "/home/tadashi/develop/zivo/src",
        }
    )
    assert result.state.current_pane.selection_anchor_path == "/home/tadashi/develop/zivo/docs"
    assert result.effects == (
        LoadChildPaneSnapshotEffect(
            request_id=1,
            current_path="/home/tadashi/develop/zivo",
            cursor_path="/home/tadashi/develop/zivo/src",
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

def test_move_cursor_and_select_range_reuses_anchor_when_shrinking_selection() -> None:
    visible_paths = (
        "/home/tadashi/develop/zivo/docs",
        "/home/tadashi/develop/zivo/src",
        "/home/tadashi/develop/zivo/tests",
        "/home/tadashi/develop/zivo/README.md",
        "/home/tadashi/develop/zivo/pyproject.toml",
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

    assert result.state.current_pane.cursor_path == "/home/tadashi/develop/zivo/src"
    assert result.state.current_pane.selected_paths == frozenset(
        {
            "/home/tadashi/develop/zivo/docs",
            "/home/tadashi/develop/zivo/src",
        }
    )
    assert result.state.current_pane.selection_anchor_path == "/home/tadashi/develop/zivo/docs"

def test_move_cursor_clears_range_selection_anchor() -> None:
    visible_paths = (
        "/home/tadashi/develop/zivo/docs",
        "/home/tadashi/develop/zivo/src",
        "/home/tadashi/develop/zivo/tests",
    )
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
            selection_anchor_path="/home/tadashi/develop/zivo/docs",
        ),
    )

    result = reduce_app_state(state, MoveCursor(delta=1, visible_paths=visible_paths))

    assert result.state.current_pane.cursor_path == "/home/tadashi/develop/zivo/src"
    assert result.state.current_pane.selected_paths == frozenset(
        {
            "/home/tadashi/develop/zivo/docs",
            "/home/tadashi/develop/zivo/src",
        }
    )
    assert result.state.current_pane.selection_anchor_path is None

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
        ToggleSelection("/home/tadashi/develop/zivo/docs"),
    )
    state = _reduce_state(
        state,
        ToggleSelection("/home/tadashi/develop/zivo/README.md"),
    )
    requested = reduce_app_state(
        state,
        RequestBrowserSnapshot("/home/tadashi/develop/zivo", blocking=True),
    ).state

    snapshot = BrowserSnapshot(
        current_path="/home/tadashi/develop/zivo",
        parent_pane=requested.parent_pane,
        current_pane=PaneState(
            directory_path="/home/tadashi/develop/zivo",
            entries=(
                DirectoryEntryState("/home/tadashi/develop/zivo/docs", "docs", "dir"),
                DirectoryEntryState("/home/tadashi/develop/zivo/src", "src", "dir"),
            ),
            cursor_path="/home/tadashi/develop/zivo/src",
        ),
        child_pane=PaneState(directory_path="/home/tadashi/develop/zivo/src", entries=()),
    )

    next_state = _reduce_state(
        requested,
        BrowserSnapshotLoaded(request_id=1, snapshot=snapshot, blocking=True),
    )

    assert next_state.current_pane.selected_paths == frozenset(
        {"/home/tadashi/develop/zivo/docs"}
    )

def test_browser_snapshot_loaded_clears_selection_when_directory_changes() -> None:
    state = build_initial_app_state()
    state = _reduce_state(
        state,
        ToggleSelection("/home/tadashi/develop/zivo/docs"),
    )
    requested = reduce_app_state(
        state,
        RequestBrowserSnapshot("/home/tadashi/develop/zivo/docs", blocking=True),
    ).state

    snapshot = BrowserSnapshot(
        current_path="/home/tadashi/develop/zivo/docs",
        parent_pane=PaneState(
            directory_path="/home/tadashi/develop/zivo",
            entries=state.current_pane.entries,
            cursor_path="/home/tadashi/develop/zivo/docs",
        ),
        current_pane=PaneState(
            directory_path="/home/tadashi/develop/zivo/docs",
            entries=(
                DirectoryEntryState(
                    "/home/tadashi/develop/zivo/docs/spec.md",
                    "spec.md",
                    "file",
                ),
            ),
            cursor_path="/home/tadashi/develop/zivo/docs/spec.md",
        ),
        child_pane=PaneState(directory_path="/home/tadashi/develop/zivo/docs", entries=()),
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
        "/home/tadashi/develop/zivo/docs",
        "/home/tadashi/develop/zivo/src",
        "/home/tadashi/develop/zivo/tests",
    )

    result = reduce_app_state(state, SetCursorPath("/home/tadashi/develop/zivo/docs"))
    assert result.effects == (
        RunDirectorySizeEffect(
            request_id=1,
            paths=(
                "/home/tadashi/develop/zivo/docs",
                "/home/tadashi/develop/zivo/src",
                "/home/tadashi/develop/zivo/tests",
            ),
        ),
    )

    moved = reduce_app_state(state, SetCursorPath("/home/tadashi/develop/zivo/src"))

    assert moved.state.pending_child_pane_request_id == 1
    assert moved.state.child_pane == state.child_pane
    assert moved.effects == (
        LoadChildPaneSnapshotEffect(
            request_id=1,
            current_path="/home/tadashi/develop/zivo",
            cursor_path="/home/tadashi/develop/zivo/src",
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

    down = reduce_app_state(state, MoveCursor(delta=1, visible_paths=visible_paths))

    assert down.state.current_pane.cursor_path == "/home/tadashi/develop/zivo/src"
    assert down.effects == (
        LoadChildPaneSnapshotEffect(
            request_id=1,
            current_path="/home/tadashi/develop/zivo",
            cursor_path="/home/tadashi/develop/zivo/src",
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

def test_set_cursor_path_to_file_requests_child_pane_preview() -> None:
    state = build_initial_app_state()

    result = reduce_app_state(state, SetCursorPath("/home/tadashi/develop/zivo/README.md"))

    assert result.state.child_pane == state.child_pane
    assert result.state.pending_child_pane_request_id == 1
    assert result.effects == (
        LoadChildPaneSnapshotEffect(
            request_id=1,
            current_path="/home/tadashi/develop/zivo",
            cursor_path="/home/tadashi/develop/zivo/README.md",
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

def test_set_cursor_path_to_file_clears_child_pane_when_preview_disabled() -> None:
    state = replace(
        build_initial_app_state(),
        config=replace(
            build_initial_app_state().config,
            display=replace(build_initial_app_state().config.display, enable_text_preview=False),
        ),
        child_pane=PaneState(
            directory_path="/home/tadashi/develop/zivo",
            entries=(),
            mode="preview",
            preview_path="/home/tadashi/develop/zivo/pyproject.toml",
            preview_content="[project]\n",
        ),
    )

    result = reduce_app_state(state, SetCursorPath("/home/tadashi/develop/zivo/README.md"))

    assert result.state.child_pane == PaneState(
        directory_path="/home/tadashi/develop/zivo",
        entries=(),
    )
    assert result.state.pending_child_pane_request_id is None
    assert result.effects == (
        RunDirectorySizeEffect(
            request_id=1,
            paths=(
                "/home/tadashi/develop/zivo/docs",
                "/home/tadashi/develop/zivo/src",
                "/home/tadashi/develop/zivo/tests",
            ),
        ),
    )

def test_child_pane_snapshot_loaded_ignores_stale_request() -> None:
    state = build_initial_app_state()
    requested = reduce_app_state(state, SetCursorPath("/home/tadashi/develop/zivo/src")).state

    next_state = _reduce_state(
        requested,
        ChildPaneSnapshotLoaded(
            request_id=99,
            pane=requested.child_pane,
        ),
    )

    assert next_state == requested

def test_child_pane_snapshot_loaded_clears_grep_preview_when_file_preview_disabled() -> None:
    path = "/home/tadashi/develop/zivo/README.md"
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
                directory_path="/home/tadashi/develop/zivo",
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
        directory_path="/home/tadashi/develop/zivo",
        entries=(),
    )
    assert next_state.pending_child_pane_request_id is None

def test_child_pane_snapshot_failed_ignores_stale_request() -> None:
    state = build_initial_app_state()
    requested = reduce_app_state(state, SetCursorPath("/home/tadashi/develop/zivo/src")).state

    next_state = _reduce_state(
        requested,
        ChildPaneSnapshotFailed(request_id=99, message="permission denied"),
    )

    assert next_state == requested

def test_child_pane_snapshot_failure_sets_error_and_clears_entries() -> None:
    state = build_initial_app_state()
    requested = reduce_app_state(state, SetCursorPath("/home/tadashi/develop/zivo/src")).state

    next_state = _reduce_state(
        requested,
        ChildPaneSnapshotFailed(request_id=1, message="permission denied"),
    )

    assert next_state.child_pane.directory_path == "/home/tadashi/develop/zivo"
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

def test_jump_cursor_start() -> None:
    state = build_initial_app_state()
    visible_paths = (
        "/home/tadashi/develop/zivo/docs",
        "/home/tadashi/develop/zivo/src",
        "/home/tadashi/develop/zivo/tests",
    )
    state = _reduce_state(state, SetCursorPath("/home/tadashi/develop/zivo/tests"))

    result = reduce_app_state(state, JumpCursor(position="start", visible_paths=visible_paths))

    assert result.state.current_pane.cursor_path == "/home/tadashi/develop/zivo/docs"
    assert result.effects == (
        LoadChildPaneSnapshotEffect(
            request_id=3,
            current_path="/home/tadashi/develop/zivo",
            cursor_path="/home/tadashi/develop/zivo/docs",
        ),
    )

def test_jump_cursor_end() -> None:
    state = build_initial_app_state()
    visible_paths = (
        "/home/tadashi/develop/zivo/docs",
        "/home/tadashi/develop/zivo/src",
        "/home/tadashi/develop/zivo/tests",
    )

    result = reduce_app_state(state, JumpCursor(position="end", visible_paths=visible_paths))

    assert result.state.current_pane.cursor_path == "/home/tadashi/develop/zivo/tests"
    assert result.effects == (
        LoadChildPaneSnapshotEffect(
            request_id=1,
            current_path="/home/tadashi/develop/zivo",
            cursor_path="/home/tadashi/develop/zivo/tests",
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
        "/home/tadashi/develop/zivo/src",
        "/home/tadashi/develop/zivo/tests",
    )
    state = _reduce_state(state, SetCursorPath("/home/tadashi/develop/zivo/tests"))

    result = reduce_app_state(
        state,
        JumpCursor(position="start", visible_paths=filtered_paths),
    )

    assert result.state.current_pane.cursor_path == "/home/tadashi/develop/zivo/src"

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
            back=("/home/tadashi", "/home/tadashi/downloads"),
            forward=(),
        ),
    )

    result = reduce_app_state(state, GoBack())

    assert result.state.pending_browser_snapshot_request_id is not None
    assert result.state.ui_mode == "BUSY"
    assert len(result.effects) == 1
    assert result.effects[0].path == "/home/tadashi/downloads"

def test_go_forward_does_nothing_when_forward_stack_is_empty() -> None:
    state = build_initial_app_state()

    result = reduce_app_state(state, GoForward())

    assert result.state == state

def test_go_forward_requests_snapshot_from_forward_stack() -> None:
    state = replace(
        build_initial_app_state(),
        history=HistoryState(
            back=(),
            forward=("/home/tadashi/downloads",),
        ),
    )

    result = reduce_app_state(state, GoForward())

    assert result.state.pending_browser_snapshot_request_id is not None
    assert result.state.ui_mode == "BUSY"
    assert len(result.effects) == 1
    assert result.effects[0].path == "/home/tadashi/downloads"

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
            back=("/home/tadashi",),
            forward=("/home/tadashi/downloads", "/home/tadashi/documents"),
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
    assert next_state.history.back == ("/home/tadashi", initial_path)

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

def test_go_back_then_snapshot_loaded_updates_history_correctly() -> None:
    initial_path = "/home/tadashi"
    second_path = "/home/tadashi/develop"

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
    initial_path = "/home/tadashi"
    forward_path = "/home/tadashi/develop"

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

def test_all_visited_directories_enumerable() -> None:
    state = build_initial_app_state()
    initial_path = state.current_path

    state = _reduce_state(state, RequestBrowserSnapshot("/tmp/first"))
    snapshot1 = BrowserSnapshot(
        current_path="/tmp/first",
        parent_pane=state.parent_pane,
        current_pane=state.current_pane,
        child_pane=state.child_pane,
    )
    state = _reduce_state(
        state,
        BrowserSnapshotLoaded(
            request_id=state.pending_browser_snapshot_request_id,
            snapshot=snapshot1,
            blocking=True,
        ),
    )

    state = _reduce_state(state, RequestBrowserSnapshot("/tmp/second"))
    snapshot2 = BrowserSnapshot(
        current_path="/tmp/second",
        parent_pane=state.parent_pane,
        current_pane=state.current_pane,
        child_pane=state.child_pane,
    )
    state = _reduce_state(
        state,
        BrowserSnapshotLoaded(
            request_id=state.pending_browser_snapshot_request_id,
            snapshot=snapshot2,
            blocking=True,
        ),
    )

    next_state = _reduce_state(state, BeginHistorySearch())

    assert next_state.command_palette is not None
    assert next_state.command_palette.source == "history"
    assert next_state.command_palette.history_results == (
        initial_path,
        "/tmp/first",
        "/tmp/second",
    )

def test_history_search_deduplicates_duplicates() -> None:
    state = build_initial_app_state()
    initial_path = state.current_path

    state = _reduce_state(state, RequestBrowserSnapshot("/tmp/first"))
    snapshot1 = BrowserSnapshot(
        current_path="/tmp/first",
        parent_pane=state.parent_pane,
        current_pane=state.current_pane,
        child_pane=state.child_pane,
    )
    state = _reduce_state(
        state,
        BrowserSnapshotLoaded(
            request_id=state.pending_browser_snapshot_request_id,
            snapshot=snapshot1,
            blocking=True,
        ),
    )

    state = _reduce_state(state, RequestBrowserSnapshot(initial_path))
    snapshot2 = BrowserSnapshot(
        current_path=initial_path,
        parent_pane=state.parent_pane,
        current_pane=state.current_pane,
        child_pane=state.child_pane,
    )
    state = _reduce_state(
        state,
        BrowserSnapshotLoaded(
            request_id=state.pending_browser_snapshot_request_id,
            snapshot=snapshot2,
            blocking=True,
        ),
    )

    state = _reduce_state(state, RequestBrowserSnapshot("/tmp/second"))
    snapshot3 = BrowserSnapshot(
        current_path="/tmp/second",
        parent_pane=state.parent_pane,
        current_pane=state.current_pane,
        child_pane=state.child_pane,
    )
    state = _reduce_state(
        state,
        BrowserSnapshotLoaded(
            request_id=state.pending_browser_snapshot_request_id,
            snapshot=snapshot3,
            blocking=True,
        ),
    )

    next_state = _reduce_state(state, BeginHistorySearch())

    assert next_state.command_palette is not None
    assert next_state.command_palette.source == "history"
    assert next_state.command_palette.history_results == (
        initial_path,
        "/tmp/first",
        "/tmp/second",
    )

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
        "/home/tadashi/develop/zivo/docs",
        "/home/tadashi/develop/zivo/src",
        "/home/tadashi/develop/zivo/tests",
        "/home/tadashi/develop/zivo/README.md",
        "/home/tadashi/develop/zivo/pyproject.toml",
    )
    state = _reduce_state(state, SetCursorPath("/home/tadashi/develop/zivo/docs"))

    result = reduce_app_state(
        state, MoveCursorByPage(direction="down", page_size=3, visible_paths=visible_paths)
    )

    assert result.state.current_pane.cursor_path == "/home/tadashi/develop/zivo/README.md"
    assert result.effects == (
        LoadChildPaneSnapshotEffect(
            request_id=2,
            current_path="/home/tadashi/develop/zivo",
            cursor_path="/home/tadashi/develop/zivo/README.md",
        ),
    )

def test_move_cursor_by_page_up() -> None:
    state = build_initial_app_state()
    visible_paths = (
        "/home/tadashi/develop/zivo/docs",
        "/home/tadashi/develop/zivo/src",
        "/home/tadashi/develop/zivo/tests",
        "/home/tadashi/develop/zivo/README.md",
        "/home/tadashi/develop/zivo/pyproject.toml",
    )
    state = _reduce_state(state, SetCursorPath("/home/tadashi/develop/zivo/pyproject.toml"))

    result = reduce_app_state(
        state, MoveCursorByPage(direction="up", page_size=3, visible_paths=visible_paths)
    )

    assert result.state.current_pane.cursor_path == "/home/tadashi/develop/zivo/src"
    assert result.effects == (
        LoadChildPaneSnapshotEffect(
            request_id=3,
            current_path="/home/tadashi/develop/zivo",
            cursor_path="/home/tadashi/develop/zivo/src",
        ),
    )

def test_move_cursor_by_page_down_clamps_to_last_entry() -> None:
    state = build_initial_app_state()
    visible_paths = (
        "/home/tadashi/develop/zivo/docs",
        "/home/tadashi/develop/zivo/src",
        "/home/tadashi/develop/zivo/tests",
    )
    state = _reduce_state(state, SetCursorPath("/home/tadashi/develop/zivo/src"))

    result = reduce_app_state(
        state, MoveCursorByPage(direction="down", page_size=10, visible_paths=visible_paths)
    )

    assert result.state.current_pane.cursor_path == "/home/tadashi/develop/zivo/tests"

def test_move_cursor_by_page_up_clamps_to_first_entry() -> None:
    state = build_initial_app_state()
    visible_paths = (
        "/home/tadashi/develop/zivo/docs",
        "/home/tadashi/develop/zivo/src",
        "/home/tadashi/develop/zivo/tests",
    )
    state = _reduce_state(state, SetCursorPath("/home/tadashi/develop/zivo/src"))

    result = reduce_app_state(
        state, MoveCursorByPage(direction="up", page_size=10, visible_paths=visible_paths)
    )

    assert result.state.current_pane.cursor_path == "/home/tadashi/develop/zivo/docs"

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
            selected_paths=frozenset({"/home/tadashi/develop/zivo/docs"}),
            selection_anchor_path="/home/tadashi/develop/zivo/docs",
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
        {"/home/tadashi/develop/zivo/docs"}
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

# ---------------------------------------------------------------------------
# Find-and-replace (replace_in_found_files) tests
# ---------------------------------------------------------------------------
