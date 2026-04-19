from dataclasses import replace
from pathlib import Path

from tests.state_test_helpers import reduce_state
from zivo.models import (
    AppConfig,
    BookmarkConfig,
    CreatePathRequest,
    CreateZipArchiveRequest,
    CreateZipArchiveResult,
    DeleteRequest,
    ExternalLaunchRequest,
    ExtractArchiveRequest,
    ExtractArchiveResult,
    FileMutationResult,
    PasteAppliedChange,
    PasteConflict,
    PasteRequest,
    PasteSummary,
    RenameRequest,
    TextReplacePreviewEntry,
    TextReplacePreviewResult,
    TextReplaceRequest,
    TextReplaceResult,
    TrashRestoreRecord,
    UndoDeletePathStep,
    UndoEntry,
    UndoMovePathStep,
    UndoRestoreTrashStep,
    UndoResult,
)
from zivo.state import (
    ActivateNextTab,
    ActivatePreviousTab,
    AddBookmark,
    ArchiveExtractCompleted,
    ArchiveExtractConfirmationState,
    ArchiveExtractFailed,
    ArchiveExtractProgress,
    ArchiveExtractProgressState,
    ArchivePreparationCompleted,
    ArchivePreparationFailed,
    AttributeInspectionState,
    BeginBookmarkSearch,
    BeginCommandPalette,
    BeginCreateInput,
    BeginDeleteTargets,
    BeginEmptyTrash,
    BeginExtractArchiveInput,
    BeginFileSearch,
    BeginFilterInput,
    BeginFindAndReplace,
    BeginGoToPath,
    BeginGrepReplace,
    BeginGrepReplaceSelected,
    BeginGrepSearch,
    BeginHistorySearch,
    BeginRenameInput,
    BeginTextReplace,
    BeginZipCompressInput,
    BrowserSnapshot,
    BrowserSnapshotFailed,
    BrowserSnapshotLoaded,
    CancelArchiveExtractConfirmation,
    CancelCommandPalette,
    CancelDeleteConfirmation,
    CancelEmptyTrashConfirmation,
    CancelFilterInput,
    CancelPasteConflict,
    CancelPendingInput,
    CancelZipCompressConfirmation,
    ChildPaneSnapshotFailed,
    ChildPaneSnapshotLoaded,
    ClearSelection,
    ClipboardPasteCompleted,
    ClipboardPasteFailed,
    ClipboardPasteNeedsResolution,
    CloseCurrentTab,
    CloseSplitTerminalEffect,
    CommandPaletteState,
    ConfigEditorState,
    ConfigSaveCompleted,
    ConfigSaveFailed,
    ConfirmArchiveExtract,
    ConfirmDeleteTargets,
    ConfirmEmptyTrash,
    ConfirmFilterInput,
    ConfirmZipCompress,
    CopyPathsToClipboard,
    CopyTargets,
    CurrentPaneDeltaState,
    CutTargets,
    CycleConfigEditorValue,
    CycleFindReplaceField,
    CycleReplaceField,
    DeleteConfirmationState,
    DirectoryEntryState,
    DirectorySizeCacheEntry,
    DirectorySizeDeltaState,
    DirectorySizesFailed,
    DirectorySizesLoaded,
    DismissAttributeDialog,
    DismissConfigEditor,
    DismissNameConflict,
    EmptyTrashConfirmationState,
    EnterCursorDirectory,
    ExternalLaunchCompleted,
    ExternalLaunchFailed,
    FileMutationCompleted,
    FileMutationFailed,
    FileSearchCompleted,
    FileSearchFailed,
    FileSearchResultState,
    FocusSplitTerminal,
    GoBack,
    GoForward,
    GoToHomeDirectory,
    GoToParentDirectory,
    GrepSearchCompleted,
    GrepSearchFailed,
    GrepSearchResultState,
    HistoryState,
    JumpCursor,
    LoadBrowserSnapshotEffect,
    LoadChildPaneSnapshotEffect,
    MoveCommandPaletteCursor,
    MoveConfigEditorCursor,
    MoveCursor,
    MoveCursorAndSelectRange,
    MoveCursorByPage,
    NameConflictState,
    NotificationState,
    OpenFindResultInEditor,
    OpenGrepResultInEditor,
    OpenNewTab,
    OpenPathInEditor,
    OpenPathWithDefaultApp,
    OpenTerminalAtPath,
    PaneState,
    PasteClipboard,
    PasteConflictState,
    PendingInputState,
    PendingKeySequenceState,
    ReloadDirectory,
    RemoveBookmark,
    ReplacePreviewResultState,
    RequestBrowserSnapshot,
    RequestDirectorySizes,
    ResolvePasteConflict,
    RunArchiveExtractEffect,
    RunArchivePreparationEffect,
    RunClipboardPasteEffect,
    RunConfigSaveEffect,
    RunDirectorySizeEffect,
    RunExternalLaunchEffect,
    RunFileMutationEffect,
    RunFileSearchEffect,
    RunGrepSearchEffect,
    RunTextReplaceApplyEffect,
    RunTextReplacePreviewEffect,
    RunUndoEffect,
    RunZipCompressEffect,
    RunZipCompressPreparationEffect,
    SaveConfigEditor,
    SelectAllVisibleEntries,
    SendSplitTerminalInput,
    SetCommandPaletteQuery,
    SetCursorPath,
    SetFilterQuery,
    SetFindReplaceField,
    SetGrepReplaceField,
    SetGrepReplaceSelectedField,
    SetGrepSearchField,
    SetNotification,
    SetPendingInputValue,
    SetPendingKeySequence,
    SetReplaceField,
    SetSort,
    SetTerminalHeight,
    SetUiMode,
    ShowAttributes,
    SplitTerminalExited,
    SplitTerminalOutputReceived,
    SplitTerminalStarted,
    StartSplitTerminalEffect,
    SubmitCommandPalette,
    SubmitPendingInput,
    TextReplaceApplied,
    TextReplaceApplyFailed,
    TextReplacePreviewCompleted,
    TextReplacePreviewFailed,
    ToggleHiddenFiles,
    ToggleSelection,
    ToggleSelectionAndAdvance,
    ToggleSplitTerminal,
    UndoCompleted,
    UndoFailed,
    UndoLastOperation,
    WriteSplitTerminalInputEffect,
    ZipCompressCompleted,
    ZipCompressConfirmationState,
    ZipCompressFailed,
    ZipCompressPreparationCompleted,
    ZipCompressProgress,
    ZipCompressProgressState,
    build_initial_app_state,
    reduce_app_state,
    select_browser_tabs,
)
from zivo.state.reducer_common import browser_snapshot_invalidation_paths


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
    assert result.effects[0].path == "/home/tadashi/develop"
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
    assert result.effects[0].path == "/tmp/work"
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


def test_open_terminal_at_path_emits_external_launch_effect() -> None:
    state = build_initial_app_state()

    result = reduce_app_state(
        state,
        OpenTerminalAtPath("/home/tadashi/develop/zivo"),
    )

    assert result.state.next_request_id == 2
    assert result.effects == (
        RunExternalLaunchEffect(
            request_id=1,
            request=ExternalLaunchRequest(
                kind="open_terminal",
                path="/home/tadashi/develop/zivo",
            ),
        ),
    )


def test_begin_filter_input_switches_mode_without_mutating_query() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(state, BeginFilterInput())

    assert next_state.ui_mode == "FILTER"
    assert next_state.filter == state.filter


def test_begin_rename_input_sets_initial_value_from_target_name() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(state, BeginRenameInput("/home/tadashi/develop/zivo/docs"))

    assert next_state.ui_mode == "RENAME"
    assert next_state.pending_input == PendingInputState(
        prompt="Rename: ",
        value="docs",
        cursor_pos=4,
        target_path="/home/tadashi/develop/zivo/docs",
    )


def test_begin_rename_input_ignores_unknown_path() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(state, BeginRenameInput("/tmp/missing"))

    assert next_state == state


def test_begin_create_input_sets_mode_and_kind() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(state, BeginCreateInput("dir"))

    assert next_state.ui_mode == "CREATE"
    assert next_state.pending_input == PendingInputState(
        prompt="New directory: ",
        value="",
        create_kind="dir",
    )


def test_begin_command_palette_sets_mode_and_empty_query() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(state, BeginCommandPalette())

    assert next_state.ui_mode == "PALETTE"
    assert next_state.command_palette is not None
    assert next_state.command_palette.query == ""
    assert next_state.command_palette.cursor_index == 0


def test_begin_command_palette_keeps_current_cursor_path() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        SetCursorPath("/home/tadashi/develop/zivo/tests"),
    )

    next_state = _reduce_state(state, BeginCommandPalette())

    assert next_state.current_pane.cursor_path == "/home/tadashi/develop/zivo/tests"


def test_move_command_palette_cursor_clamps_to_visible_commands() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())

    next_state = _reduce_state(state, MoveCommandPaletteCursor(delta=20))

    assert next_state.command_palette is not None
    assert next_state.command_palette.cursor_index == 20


def test_set_command_palette_query_resets_cursor() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, MoveCommandPaletteCursor(delta=3))

    next_state = _reduce_state(state, SetCommandPaletteQuery("dir"))

    assert next_state.command_palette is not None
    assert next_state.command_palette.query == "dir"
    assert next_state.command_palette.cursor_index == 0


def test_submit_command_palette_runs_create_file_flow() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("create file"))

    next_state = _reduce_state(state, SubmitCommandPalette())

    assert next_state.ui_mode == "CREATE"
    assert next_state.command_palette is None
    assert next_state.pending_input == PendingInputState(
        prompt="New file: ",
        value="",
        create_kind="file",
    )


def test_begin_extract_archive_input_sets_default_destination() -> None:
    archive_path = "/home/tadashi/develop/zivo/archive.tar.gz"
    expected_value = str(Path("/home/tadashi/develop/zivo/archive").resolve())
    next_state = _reduce_state(
        build_initial_app_state(),
        BeginExtractArchiveInput(archive_path),
    )

    assert next_state.ui_mode == "EXTRACT"
    assert next_state.pending_input == PendingInputState(
        prompt="Extract to: ",
        value=expected_value,
        cursor_pos=len(expected_value),
        extract_source_path=archive_path,
    )


def test_begin_zip_compress_input_sets_default_destination() -> None:
    source_path = "/home/tadashi/develop/zivo/README.md"
    expected_value = str(Path("/home/tadashi/develop/zivo/README.zip").resolve())
    next_state = _reduce_state(
        build_initial_app_state(),
        BeginZipCompressInput((source_path,)),
    )

    assert next_state.ui_mode == "ZIP"
    assert next_state.pending_input == PendingInputState(
        prompt="Compress to: ",
        value=expected_value,
        cursor_pos=len(expected_value),
        zip_source_paths=(source_path,),
    )


def test_submit_command_palette_begins_extract_archive_flow() -> None:
    archive_path = "/home/tadashi/develop/zivo/archive.zip"
    state = replace(
        build_initial_app_state(),
        current_pane=replace(
            build_initial_app_state().current_pane,
            entries=(
                DirectoryEntryState(archive_path, "archive.zip", "file"),
                *build_initial_app_state().current_pane.entries[1:],
            ),
            cursor_path=archive_path,
        ),
    )
    state = _reduce_state(state, BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("extract"))

    next_state = _reduce_state(state, SubmitCommandPalette())

    assert next_state.ui_mode == "EXTRACT"
    assert next_state.pending_input is not None
    expected_dest = str(Path("/home/tadashi/develop/zivo/archive").resolve())
    assert next_state.pending_input.value == expected_dest
    assert next_state.pending_input.extract_source_path == archive_path


def test_submit_command_palette_begins_zip_compress_flow() -> None:
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
    state = _reduce_state(state, BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("compress"))

    next_state = _reduce_state(state, SubmitCommandPalette())

    assert next_state.ui_mode == "ZIP"
    assert next_state.pending_input is not None
    expected_zip = str(Path("/home/tadashi/develop/zivo/zivo.zip").resolve())
    assert next_state.pending_input.value == expected_zip
    assert next_state.pending_input.zip_source_paths == (
        "/home/tadashi/develop/zivo/docs",
        "/home/tadashi/develop/zivo/src",
    )


def test_begin_file_search_enters_find_file_mode() -> None:
    next_state = _reduce_state(build_initial_app_state(), BeginFileSearch())

    assert next_state.ui_mode == "PALETTE"
    assert next_state.command_palette == CommandPaletteState(source="file_search")


def test_begin_grep_search_enters_grep_mode() -> None:
    next_state = _reduce_state(build_initial_app_state(), BeginGrepSearch())

    assert next_state.ui_mode == "PALETTE"
    assert next_state.command_palette == CommandPaletteState(source="grep_search")


def test_begin_history_search_enters_history_mode() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        history=HistoryState(
            back=("/tmp/a", "/tmp/b"),
            forward=("/tmp/c",),
            visited_all=("/home/tadashi/develop/zivo", "/tmp/a", "/tmp/b", "/tmp/c"),
        ),
    )
    next_state = _reduce_state(state, BeginHistorySearch())

    assert next_state.ui_mode == "PALETTE"
    assert next_state.command_palette is not None
    assert next_state.command_palette.source == "history"
    assert next_state.command_palette.history_results == (
        "/home/tadashi/develop/zivo",
        "/tmp/a",
        "/tmp/b",
        "/tmp/c",
    )


def test_begin_history_search_with_empty_history() -> None:
    next_state = _reduce_state(build_initial_app_state(), BeginHistorySearch())

    assert next_state.ui_mode == "PALETTE"
    assert next_state.command_palette is not None
    assert next_state.command_palette.source == "history"
    assert next_state.command_palette.history_results == ()


def test_begin_bookmark_search_enters_bookmarks_mode() -> None:
    next_state = _reduce_state(build_initial_app_state(), BeginBookmarkSearch())

    assert next_state.ui_mode == "PALETTE"
    assert next_state.command_palette == CommandPaletteState(source="bookmarks")


def test_begin_go_to_path_enters_palette_mode() -> None:
    next_state = _reduce_state(build_initial_app_state(), BeginGoToPath())

    assert next_state.ui_mode == "PALETTE"
    assert next_state.command_palette == CommandPaletteState(source="go_to_path")


def test_submit_history_palette_navigates_to_selected_directory() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="history",
            history_results=("/tmp/a", "/tmp/b", "/tmp/c"),
            cursor_index=1,
        ),
    )

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.command_palette is None
    assert any(
        isinstance(e, LoadBrowserSnapshotEffect) and e.path == "/tmp/b"
        for e in result.effects
    )


def test_submit_history_palette_with_empty_history_shows_warning() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="history",
            history_results=(),
        ),
    )

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.notification is not None
    assert result.state.notification.message == "No directory history"


def test_submit_bookmarks_palette_navigates_to_selected_directory(tmp_path) -> None:
    bookmarked_path = tmp_path / "project"
    bookmarked_path.mkdir()
    state = build_initial_app_state(
        config=AppConfig(bookmarks=BookmarkConfig(paths=(str(bookmarked_path),)))
    )
    state = replace(
        state,
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(source="bookmarks"),
    )

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.command_palette is None
    assert result.effects == (
        LoadBrowserSnapshotEffect(
            request_id=1,
            path=str(bookmarked_path),
            cursor_path=None,
            blocking=True,
        ),
    )


def test_submit_bookmarks_palette_with_invalid_path_shows_error() -> None:
    state = build_initial_app_state(
        config=AppConfig(bookmarks=BookmarkConfig(paths=("/tmp/does-not-exist",)))
    )
    state = replace(
        state,
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(source="bookmarks"),
    )

    next_state = _reduce_state(state, SubmitCommandPalette())

    assert next_state.notification == NotificationState(
        level="error",
        message="Bookmarked path does not exist or is not a directory",
    )


def test_set_command_palette_query_updates_go_to_path_candidates(tmp_path) -> None:
    state = _reduce_state(
        replace(build_initial_app_state(), current_path=str(tmp_path)),
        BeginGoToPath(),
    )
    (tmp_path / "docs").mkdir()
    (tmp_path / "downloads").mkdir()

    next_state = _reduce_state(
        state,
        SetCommandPaletteQuery("do"),
    )

    assert next_state.command_palette is not None
    assert next_state.command_palette.go_to_path_candidates == (
        str(tmp_path / "docs"),
        str(tmp_path / "downloads"),
    )


def test_set_command_palette_query_resolves_relative_go_to_path_candidates(tmp_path) -> None:
    state = _reduce_state(
        replace(build_initial_app_state(), current_path=str(tmp_path)),
        BeginGoToPath(),
    )
    (tmp_path / "projects").mkdir()
    (tmp_path / "projects" / "zivo").mkdir()

    next_state = _reduce_state(state, SetCommandPaletteQuery("projects/z"))

    assert next_state.command_palette is not None
    assert next_state.command_palette.go_to_path_candidates == (
        str(tmp_path / "projects" / "zivo"),
    )


def test_submit_go_to_path_palette_requests_snapshot(tmp_path) -> None:
    state = _reduce_state(
        replace(build_initial_app_state(), current_path=str(tmp_path)),
        BeginGoToPath(),
    )
    target_path = tmp_path / "docs"
    target_path.mkdir()
    state = _reduce_state(
        state,
        SetCommandPaletteQuery("do"),
    )

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.ui_mode == "BUSY"
    assert result.state.command_palette is None
    assert result.effects == (
        LoadBrowserSnapshotEffect(
            request_id=1,
            path=str(target_path),
            cursor_path=None,
            blocking=True,
        ),
    )


def test_submit_go_to_path_palette_uses_selected_candidate(tmp_path) -> None:
    state = _reduce_state(
        replace(build_initial_app_state(), current_path=str(tmp_path)),
        BeginGoToPath(),
    )
    (tmp_path / "alpha").mkdir()
    (tmp_path / "beta").mkdir()
    state = _reduce_state(state, SetCommandPaletteQuery(""))
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            query=str(tmp_path),
            go_to_path_candidates=(str(tmp_path / "alpha"), str(tmp_path / "beta")),
            cursor_index=1,
        ),
    )

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.effects == (
        LoadBrowserSnapshotEffect(
            request_id=1,
            path=str(tmp_path / "beta"),
            cursor_path=None,
            blocking=True,
        ),
    )


def test_submit_go_to_path_palette_with_trailing_separator_uses_query_directory(tmp_path) -> None:
    state = _reduce_state(
        replace(build_initial_app_state(), current_path=str(tmp_path)),
        BeginGoToPath(),
    )
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "api").mkdir()
    state = _reduce_state(state, SetCommandPaletteQuery("docs/"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.effects == (
        LoadBrowserSnapshotEffect(
            request_id=1,
            path=str(tmp_path / "docs"),
            cursor_path=None,
            blocking=True,
        ),
    )

def test_submit_go_to_path_palette_with_invalid_directory_shows_error() -> None:
    state = _reduce_state(build_initial_app_state(), BeginGoToPath())
    state = _reduce_state(
        state,
        SetCommandPaletteQuery("/path/that/does/not/exist"),
    )

    next_state = _reduce_state(state, SubmitCommandPalette())

    assert next_state.ui_mode == "PALETTE"
    assert next_state.notification == NotificationState(
        level="error",
        message="Path does not exist or is not a directory",
    )
    state = _reduce_state(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        BeginCommandPalette(),
    )
    state = _reduce_state(state, SetCommandPaletteQuery("config"))

    next_state = _reduce_state(state, SubmitCommandPalette())

    assert next_state.ui_mode == "CONFIG"
    assert next_state.command_palette is None
    assert next_state.config_editor == ConfigEditorState(
        path="/tmp/zivo/config.toml",
        draft=next_state.config,
    )


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
    assert next_state.config_editor.cursor_index == 15


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


def test_cycle_config_editor_split_terminal_position_updates_draft() -> None:
    original_state = build_initial_app_state(config_path="/tmp/zivo/config.toml")
    state = replace(
        original_state,
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=original_state.config,
            cursor_index=12,
        ),
    )

    next_state = _reduce_state(state, CycleConfigEditorValue(delta=1))

    assert next_state.config_editor is not None
    assert next_state.config_editor.draft.display.split_terminal_position == "right"
    assert next_state.config_editor.dirty is True


def test_cycle_config_editor_split_terminal_position_reaches_overlay() -> None:
    original_state = build_initial_app_state(config_path="/tmp/zivo/config.toml")
    state = replace(
        original_state,
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=replace(
                original_state.config,
                display=replace(
                    original_state.config.display,
                    split_terminal_position="right",
                ),
            ),
            cursor_index=12,
        ),
    )

    next_state = _reduce_state(state, CycleConfigEditorValue(delta=1))

    assert next_state.config_editor is not None
    assert next_state.config_editor.draft.display.split_terminal_position == "overlay"
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


def test_cycle_config_editor_preview_visibility_updates_draft_and_dirty_state() -> None:
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
    assert next_state.config_editor.draft.display.show_preview is False
    assert next_state.config_editor.dirty is True


def test_cycle_config_editor_preview_syntax_theme_updates_draft_and_dirty_state() -> None:
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
    assert next_state.config_editor.draft.display.preview_syntax_theme == "abap"
    assert next_state.config_editor.dirty is True


def test_cycle_config_editor_preview_max_kib_updates_draft_and_dirty_state() -> None:
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
                display=replace(build_initial_app_state().config.display, show_preview=False),
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

    assert next_state.config.display.show_preview is False
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
            display=replace(base_state.config.display, show_preview=False),
        ),
        current_pane=replace(base_state.current_pane, cursor_path=path),
        child_pane=PaneState(directory_path="/home/tadashi/develop/zivo", entries=()),
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=replace(
                base_state.config,
                display=replace(base_state.config.display, show_preview=True),
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

    assert result.state.config.display.show_preview is True
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


def test_submit_command_palette_runs_copy_path_flow() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("copy"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.ui_mode == "BROWSING"
    assert result.state.command_palette is None
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


def test_submit_command_palette_opens_attribute_dialog_for_single_target() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("attr"))

    next_state = _reduce_state(state, SubmitCommandPalette())

    assert next_state.ui_mode == "DETAIL"
    assert next_state.command_palette is None
    assert next_state.attribute_inspection is not None
    assert next_state.attribute_inspection.name == "docs"
    assert next_state.attribute_inspection.kind == "dir"
    assert next_state.attribute_inspection.path == "/home/tadashi/develop/zivo/docs"
    assert next_state.attribute_inspection.permissions_mode is None


def test_dismiss_attribute_dialog_returns_to_browsing() -> None:
    initial_state = build_initial_app_state()
    state = replace(
        initial_state,
        ui_mode="DETAIL",
        attribute_inspection=AttributeInspectionState(
            name="docs",
            kind="dir",
            path="/home/tadashi/develop/zivo/docs",
        ),
    )

    next_state = _reduce_state(state, DismissAttributeDialog())

    assert next_state.ui_mode == "BROWSING"
    assert next_state.attribute_inspection is None


def test_submit_command_palette_opens_current_directory_in_file_manager() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("manager"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.ui_mode == "BROWSING"
    assert result.state.command_palette is None
    assert result.state.next_request_id == 2
    assert result.effects == (
        RunExternalLaunchEffect(
            request_id=1,
            request=ExternalLaunchRequest(
                kind="open_file",
                path="/home/tadashi/develop/zivo",
            ),
        ),
    )


def test_submit_command_palette_warns_when_query_has_no_match() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("zzz"))

    next_state = _reduce_state(state, SubmitCommandPalette())

    assert next_state.ui_mode == "PALETTE"
    assert next_state.notification == NotificationState(
        level="warning",
        message="No matching command",
    )


def test_submit_command_palette_toggles_hidden_files() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("hidden"))

    next_state = _reduce_state(state, SubmitCommandPalette())

    assert next_state.ui_mode == "BROWSING"
    assert next_state.command_palette is None
    assert next_state.show_hidden is True
    assert next_state.notification == NotificationState(
        level="info",
        message="Hidden files shown",
    )


def test_submit_command_palette_runs_open_terminal_flow() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("open terminal"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.ui_mode == "BROWSING"
    assert result.state.command_palette is None
    assert result.state.next_request_id == 2
    assert result.effects == (
        RunExternalLaunchEffect(
            request_id=1,
            request=ExternalLaunchRequest(
                kind="open_terminal",
                path="/home/tadashi/develop/zivo",
            ),
        ),
    )


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


def test_submit_command_palette_begins_history_search() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("history search"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.ui_mode == "PALETTE"
    assert result.state.command_palette is not None
    assert result.state.command_palette.source == "history"


def test_submit_command_palette_begins_bookmark_search() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("show bookmarks"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.ui_mode == "PALETTE"
    assert result.state.command_palette is not None
    assert result.state.command_palette.source == "bookmarks"


def test_submit_command_palette_adds_current_directory_bookmark() -> None:
    state = _reduce_state(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        BeginCommandPalette(),
    )
    state = _reduce_state(state, SetCommandPaletteQuery("bookmark this directory"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.command_palette is None
    assert result.effects == (
        RunConfigSaveEffect(
            request_id=1,
            path="/tmp/zivo/config.toml",
            config=AppConfig(
                bookmarks=BookmarkConfig(paths=("/home/tadashi/develop/zivo",))
            ),
        ),
    )


def test_show_attributes_enters_detail_mode_for_single_target() -> None:
    state = build_initial_app_state()

    result = reduce_app_state(state, ShowAttributes())

    assert result.state.ui_mode == "DETAIL"
    assert result.state.attribute_inspection == AttributeInspectionState(
        name="docs",
        kind="dir",
        path="/home/tadashi/develop/zivo/docs",
        size_bytes=None,
        modified_at=state.current_pane.entries[0].modified_at,
        hidden=False,
        permissions_mode=state.current_pane.entries[0].permissions_mode,
    )


def test_show_attributes_warns_without_single_target() -> None:
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

    next_state = _reduce_state(state, ShowAttributes())

    assert next_state.notification == NotificationState(
        level="warning",
        message="Show attributes requires a single target",
    )


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


def test_submit_command_palette_removes_current_directory_bookmark() -> None:
    state = _reduce_state(
        build_initial_app_state(
            config_path="/tmp/zivo/config.toml",
            config=AppConfig(
                bookmarks=BookmarkConfig(paths=("/home/tadashi/develop/zivo", "/home/tadashi/src"))
            ),
        ),
        BeginCommandPalette(),
    )
    state = _reduce_state(state, SetCommandPaletteQuery("remove bookmark"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.command_palette is None
    assert result.effects == (
        RunConfigSaveEffect(
            request_id=1,
            path="/tmp/zivo/config.toml",
            config=AppConfig(
                bookmarks=BookmarkConfig(paths=("/home/tadashi/src",))
            ),
        ),
    )


def test_submit_command_palette_goes_back() -> None:
    state = replace(
        _reduce_state(build_initial_app_state(), BeginCommandPalette()),
        history=HistoryState(
            back=("/home/tadashi/downloads",),
            forward=(),
        ),
    )
    state = _reduce_state(state, SetCommandPaletteQuery("go back"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.ui_mode == "BUSY"
    assert result.state.command_palette is None
    assert len(result.effects) == 1
    assert isinstance(result.effects[0], LoadBrowserSnapshotEffect)
    assert result.effects[0].path == "/home/tadashi/downloads"


def test_submit_command_palette_go_forward_is_unavailable_without_history() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("go forward"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.ui_mode == "PALETTE"
    assert result.state.command_palette is not None
    assert result.state.notification == NotificationState(
        level="warning",
        message="Go forward is not available yet",
    )


def test_submit_command_palette_reloads_directory() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("reload directory"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.command_palette is None
    assert len(result.effects) == 1
    assert isinstance(result.effects[0], LoadBrowserSnapshotEffect)


def test_submit_command_palette_goes_to_home_directory() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("go to home directory"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.ui_mode == "BUSY"
    assert result.state.command_palette is None
    assert len(result.effects) == 1
    assert isinstance(result.effects[0], LoadBrowserSnapshotEffect)


def test_submit_command_palette_toggles_split_terminal() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("split terminal"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.ui_mode == "BROWSING"
    assert result.state.command_palette is None
    assert result.state.split_terminal.visible is True
    assert len(result.effects) == 1
    assert isinstance(result.effects[0], StartSplitTerminalEffect)


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


def test_toggle_split_terminal_starts_embedded_session() -> None:
    result = reduce_app_state(build_initial_app_state(), ToggleSplitTerminal())

    assert result.state.split_terminal.visible is True
    assert result.state.split_terminal.status == "starting"
    assert result.state.split_terminal.cwd == "/home/tadashi/develop/zivo"
    assert result.state.split_terminal.session_id == 1
    assert result.effects == (
        StartSplitTerminalEffect(
            session_id=1,
            cwd="/home/tadashi/develop/zivo",
        ),
    )


def test_submit_command_palette_begins_rename_with_single_target() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("rename"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.ui_mode == "RENAME"
    assert result.state.command_palette is None
    assert result.state.pending_input is not None
    assert result.state.pending_input.prompt == "Rename: "


def test_submit_command_palette_deletes_targets() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("trash"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.ui_mode == "CONFIRM"
    assert result.state.command_palette is None
    assert result.state.delete_confirmation is not None


def test_toggle_split_terminal_closes_active_session() -> None:
    state = replace(
        build_initial_app_state(),
        split_terminal=replace(
            build_initial_app_state().split_terminal,
            visible=True,
            status="running",
            session_id=7,
            output="prompt> ",
        ),
    )

    result = reduce_app_state(state, ToggleSplitTerminal())

    assert result.state.split_terminal.visible is False
    assert result.effects == (CloseSplitTerminalEffect(session_id=7),)


def test_focus_split_terminal_switches_focus_target() -> None:
    state = replace(
        build_initial_app_state(),
        split_terminal=replace(
            build_initial_app_state().split_terminal,
            visible=True,
            status="running",
            session_id=3,
        ),
    )

    next_state = _reduce_state(state, FocusSplitTerminal("terminal"))

    assert next_state.split_terminal.focus_target == "terminal"


def test_toggle_split_terminal_opens_with_terminal_focus() -> None:
    result = reduce_app_state(build_initial_app_state(), ToggleSplitTerminal())

    assert result.state.split_terminal.visible is True
    assert result.state.split_terminal.focus_target == "terminal"


def test_send_split_terminal_input_emits_write_effect() -> None:
    state = replace(
        build_initial_app_state(),
        split_terminal=replace(
            build_initial_app_state().split_terminal,
            visible=True,
            status="running",
            session_id=5,
        ),
    )

    result = reduce_app_state(state, SendSplitTerminalInput("ls\n"))

    assert result.effects == (
        WriteSplitTerminalInputEffect(session_id=5, data="ls\n"),
    )


def test_split_terminal_started_marks_session_running() -> None:
    state = replace(
        build_initial_app_state(),
        split_terminal=replace(
            build_initial_app_state().split_terminal,
            visible=True,
            status="starting",
            session_id=5,
        ),
    )

    next_state = _reduce_state(
        state,
        SplitTerminalStarted(session_id=5, cwd="/home/tadashi/develop/zivo"),
    )

    assert next_state.split_terminal.status == "running"
    assert next_state.notification == NotificationState(
        level="info",
        message="Split terminal opened",
    )


def test_split_terminal_output_received_does_not_mutate_reducer_state() -> None:
    state = replace(
        build_initial_app_state(),
        split_terminal=replace(
            build_initial_app_state().split_terminal,
            visible=True,
            status="running",
            session_id=5,
            output="hello",
        ),
    )

    next_state = _reduce_state(state, SplitTerminalOutputReceived(session_id=5, data=" world"))

    assert next_state == state


def test_split_terminal_exited_resets_state_and_notifies() -> None:
    state = replace(
        build_initial_app_state(),
        split_terminal=replace(
            build_initial_app_state().split_terminal,
            visible=True,
            status="running",
            focus_target="terminal",
            session_id=5,
            output="prompt",
        ),
    )

    next_state = _reduce_state(state, SplitTerminalExited(session_id=5, exit_code=0))

    assert next_state.split_terminal.visible is False
    assert next_state.notification == NotificationState(
        level="info",
        message="Split terminal closed (exit 0)",
    )


def test_submit_command_palette_uses_selected_paths_for_copy_path() -> None:
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
    state = _reduce_state(state, SetCommandPaletteQuery("copy"))

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.effects == (
        RunExternalLaunchEffect(
            request_id=1,
            request=ExternalLaunchRequest(
                kind="copy_paths",
                paths=(
                    "/home/tadashi/develop/zivo/docs",
                    "/home/tadashi/develop/zivo/src",
                ),
            ),
        ),
    )


def test_submit_command_palette_select_all_uses_visible_entries() -> None:
    initial_state = build_initial_app_state()
    state = replace(
        initial_state,
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
                DirectoryEntryState("/home/tadashi/develop/zivo/src", "src", "dir"),
            ),
            cursor_path="/home/tadashi/develop/zivo/docs",
        ),
        filter=replace(initial_state.filter, query="s", active=True),
    )
    state = _reduce_state(state, BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("select all"))

    next_state = _reduce_state(state, SubmitCommandPalette())

    assert next_state.current_pane.selected_paths == frozenset(
        {
            "/home/tadashi/develop/zivo/docs",
            "/home/tadashi/develop/zivo/src",
        }
    )


def test_select_all_visible_entries_replaces_selection_with_visible_paths() -> None:
    initial_state = build_initial_app_state()
    state = replace(
        initial_state,
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
                DirectoryEntryState("/home/tadashi/develop/zivo/src", "src", "dir"),
            ),
            cursor_path="/home/tadashi/develop/zivo/docs",
            selected_paths=frozenset(
                {
                    "/home/tadashi/develop/zivo/.env",
                    "/home/tadashi/develop/zivo/docs",
                }
            ),
        ),
    )

    next_state = _reduce_state(
        state,
        SelectAllVisibleEntries(
            (
                "/home/tadashi/develop/zivo/docs",
                "/home/tadashi/develop/zivo/src",
            )
        ),
    )

    assert next_state.current_pane.selected_paths == frozenset(
        {
            "/home/tadashi/develop/zivo/docs",
            "/home/tadashi/develop/zivo/src",
        }
    )


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


def test_begin_text_replace_enters_replace_mode() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginTextReplace(target_paths=("/home/tadashi/develop/zivo/README.md",)),
    )

    assert state.ui_mode == "PALETTE"
    assert state.command_palette is not None
    assert state.command_palette.source == "replace_text"
    assert state.command_palette.replace_target_paths == (
        "/home/tadashi/develop/zivo/README.md",
    )


def test_set_replace_field_starts_preview_effect() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginTextReplace(target_paths=("/home/tadashi/develop/zivo/README.md",)),
    )

    result = reduce_app_state(state, SetReplaceField(field="find", value="todo"))

    assert result.state.command_palette is not None
    assert result.state.pending_replace_preview_request_id == 1
    assert result.effects == (
        RunTextReplacePreviewEffect(
            request_id=1,
            request=TextReplaceRequest(
                paths=("/home/tadashi/develop/zivo/README.md",),
                find_text="todo",
                replace_text="",
            ),
        ),
    )


def test_cycle_replace_field_switches_active_input() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginTextReplace(target_paths=("/home/tadashi/develop/zivo/README.md",)),
    )

    next_state = _reduce_state(state, CycleReplaceField(delta=1))

    assert next_state.command_palette is not None
    assert next_state.command_palette.replace_active_field == "replace"


def test_text_replace_preview_completed_updates_palette_results() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginTextReplace(target_paths=("/home/tadashi/develop/zivo/README.md",)),
    )
    state = replace(
        state,
        pending_replace_preview_request_id=4,
        command_palette=replace(
            state.command_palette,
            replace_find_text="todo",
        ),
    )

    next_state = _reduce_state(
        state,
        TextReplacePreviewCompleted(
            request_id=4,
            result=TextReplacePreviewResult(
                request=TextReplaceRequest(
                    paths=("/home/tadashi/develop/zivo/README.md",),
                    find_text="todo",
                    replace_text="done",
                ),
                changed_entries=(
                    TextReplacePreviewEntry(
                        path="/home/tadashi/develop/zivo/README.md",
                        diff_text="--- before\n+++ after\n@@\n-todo item\n+done item\n",
                        match_count=2,
                        first_match_line_number=12,
                        first_match_before="todo item",
                        first_match_after="done item",
                    ),
                ),
                total_match_count=2,
                diff_text="--- before\n+++ after\n@@\n-todo item\n+done item\n",
            ),
        ),
    )

    assert next_state.command_palette is not None
    assert next_state.command_palette.replace_total_match_count == 2
    assert next_state.command_palette.replace_preview_results[0].display_path == "README.md"
    assert next_state.command_palette.replace_preview_results[0].diff_text == (
        "--- before\n+++ after\n@@\n-todo item\n+done item\n"
    )
    assert next_state.child_pane.preview_title == "Replace Preview"
    assert next_state.child_pane.preview_content == (
        "--- before\n+++ after\n@@\n-todo item\n+done item\n"
    )
    assert next_state.child_pane.preview_path == "/home/tadashi/develop/zivo/README.md"
    assert next_state.pending_replace_preview_request_id is None


def test_move_palette_cursor_updates_replace_preview_diff() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginTextReplace(
            target_paths=(
                "/home/tadashi/develop/zivo/README.md",
                "/home/tadashi/develop/zivo/docs/notes.md",
            )
        ),
    )
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            replace_preview_results=(
                ReplacePreviewResultState(
                    path="/home/tadashi/develop/zivo/README.md",
                    display_path="README.md",
                    diff_text="--- README\n+++ README\n@@\n-todo\n+done\n",
                    match_count=1,
                    first_match_line_number=1,
                    first_match_before="todo",
                    first_match_after="done",
                ),
                ReplacePreviewResultState(
                    path="/home/tadashi/develop/zivo/docs/notes.md",
                    display_path="docs/notes.md",
                    diff_text="--- notes\n+++ notes\n@@\n-todo\n+done\n",
                    match_count=1,
                    first_match_line_number=2,
                    first_match_before="todo",
                    first_match_after="done",
                ),
            ),
            replace_total_match_count=2,
        ),
        child_pane=PaneState(
            directory_path=state.current_path,
            entries=(),
            mode="preview",
            preview_path="/home/tadashi/develop/zivo/README.md",
            preview_title="Replace Preview",
            preview_content="--- README\n+++ README\n@@\n-todo\n+done\n",
        ),
    )

    result = reduce_app_state(state, MoveCommandPaletteCursor(delta=1))

    assert result.state.command_palette is not None
    assert result.state.command_palette.cursor_index == 1
    assert result.state.child_pane.preview_path == "/home/tadashi/develop/zivo/docs/notes.md"
    assert result.state.child_pane.preview_content == (
        "--- notes\n+++ notes\n@@\n-todo\n+done\n"
    )


def test_text_replace_preview_failed_sets_inline_error_for_invalid_regex() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginTextReplace(target_paths=("/home/tadashi/develop/zivo/README.md",)),
    )
    state = replace(state, pending_replace_preview_request_id=4)

    next_state = _reduce_state(
        state,
        TextReplacePreviewFailed(
            request_id=4,
            message="missing )",
            invalid_query=True,
        ),
    )

    assert next_state.command_palette is not None
    assert next_state.command_palette.replace_error_message == "missing )"
    assert next_state.pending_replace_preview_request_id is None


def test_submit_command_palette_applies_replace_when_preview_exists() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginTextReplace(target_paths=("/home/tadashi/develop/zivo/README.md",)),
    )
    state = replace(
        state,
        next_request_id=8,
        command_palette=replace(
            state.command_palette,
            replace_find_text="todo",
            replace_replacement_text="done",
            replace_preview_results=(
                ReplacePreviewResultState(
                    path="/home/tadashi/develop/zivo/README.md",
                    display_path="README.md",
                    diff_text="--- before\n+++ after\n@@\n-todo item\n+done item\n",
                    match_count=2,
                    first_match_line_number=12,
                    first_match_before="todo item",
                    first_match_after="done item",
                ),
            ),
        ),
    )

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.pending_replace_apply_request_id == 8
    assert result.state.ui_mode == "BROWSING"
    assert result.effects == (
        RunTextReplaceApplyEffect(
            request_id=8,
            request=TextReplaceRequest(
                paths=("/home/tadashi/develop/zivo/README.md",),
                find_text="todo",
                replace_text="done",
            ),
        ),
    )


def test_text_replace_applied_refreshes_current_directory() -> None:
    state = replace(
        build_initial_app_state(),
        pending_replace_apply_request_id=6,
        current_path="/home/tadashi/develop/zivo",
        current_pane=replace(
            build_initial_app_state().current_pane,
            cursor_path="/home/tadashi/develop/zivo/README.md",
        ),
    )

    result = reduce_app_state(
        state,
        TextReplaceApplied(
            request_id=6,
            result=TextReplaceResult(
                request=TextReplaceRequest(
                    paths=("/home/tadashi/develop/zivo/README.md",),
                    find_text="todo",
                    replace_text="done",
                ),
                changed_paths=("/home/tadashi/develop/zivo/README.md",),
                total_match_count=3,
                message="Replaced 3 match(es) in 1 file(s)",
            ),
        ),
    )

    assert result.state.post_reload_notification == NotificationState(
        level="info",
        message="Replaced 3 match(es) in 1 file(s)",
    )
    assert result.effects == (
        LoadBrowserSnapshotEffect(
            request_id=1,
            path="/home/tadashi/develop/zivo",
            cursor_path="/home/tadashi/develop/zivo/README.md",
            blocking=True,
            invalidate_paths=browser_snapshot_invalidation_paths(
                "/home/tadashi/develop/zivo",
                "/home/tadashi/develop/zivo/README.md",
            ),
        ),
    )


def test_text_replace_apply_failed_sets_error_notification() -> None:
    state = replace(
        build_initial_app_state(),
        pending_replace_apply_request_id=3,
    )

    next_state = _reduce_state(
        state,
        TextReplaceApplyFailed(request_id=3, message="permission denied"),
    )

    assert next_state.pending_replace_apply_request_id is None
    assert next_state.notification == NotificationState(
        level="error",
        message="permission denied",
    )


def test_run_replace_text_command_uses_cursor_file_when_nothing_is_selected() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = replace(
        state,
        command_palette=replace(state.command_palette, query="replace text"),
        current_pane=replace(
            state.current_pane,
            selected_paths=frozenset(),
            cursor_path="/home/tadashi/develop/zivo/README.md",
        ),
    )

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.command_palette is not None
    assert result.state.command_palette.source == "replace_text"
    assert result.state.command_palette.replace_target_paths == (
        "/home/tadashi/develop/zivo/README.md",
    )


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
            display=replace(build_initial_app_state().config.display, show_preview=False),
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

    assert result.state.config.display.show_preview is False
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


def test_cancel_command_palette_returns_to_browsing() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())

    next_state = _reduce_state(state, CancelCommandPalette())

    assert next_state.ui_mode == "BROWSING"
    assert next_state.command_palette is None


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


def test_begin_delete_targets_single_runs_file_mutation() -> None:
    state = build_initial_app_state(confirm_delete=False)

    result = reduce_app_state(
        state,
        BeginDeleteTargets(("/home/tadashi/develop/zivo/docs",)),
    )

    assert result.state.ui_mode == "BUSY"
    assert result.effects == (
        RunFileMutationEffect(
            request_id=1,
            request=DeleteRequest(paths=("/home/tadashi/develop/zivo/docs",), mode="trash"),
        ),
    )


def test_begin_delete_targets_single_enters_confirm_mode_when_enabled() -> None:
    state = build_initial_app_state(confirm_delete=True)

    next_state = _reduce_state(
        state,
        BeginDeleteTargets(("/home/tadashi/develop/zivo/docs",)),
    )

    assert next_state.ui_mode == "CONFIRM"
    assert next_state.delete_confirmation == DeleteConfirmationState(
        paths=("/home/tadashi/develop/zivo/docs",)
    )


def test_begin_delete_targets_with_empty_paths_keeps_state() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(state, BeginDeleteTargets(()))

    assert next_state == state


def test_begin_delete_targets_multiple_enters_confirm_mode() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(
        state,
        BeginDeleteTargets(
            (
                "/home/tadashi/develop/zivo/docs",
                "/home/tadashi/develop/zivo/src",
            )
        ),
    )

    assert next_state.ui_mode == "CONFIRM"
    assert next_state.delete_confirmation == DeleteConfirmationState(
        paths=(
            "/home/tadashi/develop/zivo/docs",
            "/home/tadashi/develop/zivo/src",
        )
    )


def test_cancel_pending_input_returns_to_browsing() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="RENAME",
        pending_input=PendingInputState(prompt="Rename: ", value="docs"),
    )

    next_state = _reduce_state(state, CancelPendingInput())

    assert next_state.ui_mode == "BROWSING"
    assert next_state.pending_input is None


def test_confirm_delete_targets_runs_file_mutation() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        delete_confirmation=DeleteConfirmationState(
            paths=(
                "/home/tadashi/develop/zivo/docs",
                "/home/tadashi/develop/zivo/src",
            )
        ),
        next_request_id=4,
    )

    result = reduce_app_state(state, ConfirmDeleteTargets())

    assert result.state.ui_mode == "BUSY"
    assert result.effects == (
        RunFileMutationEffect(
            request_id=4,
            request=DeleteRequest(
                paths=(
                    "/home/tadashi/develop/zivo/docs",
                    "/home/tadashi/develop/zivo/src",
                ),
                mode="trash",
            ),
        ),
    )


def test_cancel_delete_confirmation_returns_to_browsing_with_warning() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        delete_confirmation=DeleteConfirmationState(
            paths=("/home/tadashi/develop/zivo/docs",),
        ),
    )

    next_state = _reduce_state(state, CancelDeleteConfirmation())

    assert next_state.ui_mode == "BROWSING"
    assert next_state.notification == NotificationState(level="warning", message="Delete cancelled")


def test_begin_permanent_delete_targets_enters_confirm_mode_when_delete_confirmation_disabled(
) -> None:
    state = build_initial_app_state(confirm_delete=False)

    next_state = _reduce_state(
        state,
        BeginDeleteTargets(("/home/tadashi/develop/zivo/docs",), mode="permanent"),
    )

    assert next_state.ui_mode == "CONFIRM"
    assert next_state.delete_confirmation == DeleteConfirmationState(
        paths=("/home/tadashi/develop/zivo/docs",),
        mode="permanent",
    )


def test_confirm_permanent_delete_targets_runs_file_mutation() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        delete_confirmation=DeleteConfirmationState(
            paths=("/home/tadashi/develop/zivo/docs",),
            mode="permanent",
        ),
        next_request_id=4,
    )

    result = reduce_app_state(state, ConfirmDeleteTargets())

    assert result.state.ui_mode == "BUSY"
    assert result.effects == (
        RunFileMutationEffect(
            request_id=4,
            request=DeleteRequest(
                paths=("/home/tadashi/develop/zivo/docs",),
                mode="permanent",
            ),
        ),
    )


def test_cancel_permanent_delete_confirmation_returns_to_browsing_with_warning() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        delete_confirmation=DeleteConfirmationState(
            paths=("/home/tadashi/develop/zivo/docs",),
            mode="permanent",
        ),
    )

    next_state = _reduce_state(state, CancelDeleteConfirmation())

    assert next_state.ui_mode == "BROWSING"
    assert next_state.notification == NotificationState(
        level="warning",
        message="Permanent delete cancelled",
    )


def test_submit_pending_extract_starts_archive_preparation() -> None:
    source_path = "/home/tadashi/develop/zivo/archive.zip"
    dest_path = "/tmp/output/archive"
    state = replace(
        build_initial_app_state(),
        ui_mode="EXTRACT",
        pending_input=PendingInputState(
            prompt="Extract to: ",
            value=dest_path,
            extract_source_path=source_path,
        ),
    )

    result = reduce_app_state(state, SubmitPendingInput())

    assert result.state.pending_archive_prepare_request_id == 1
    assert result.state.ui_mode == "BUSY"
    assert result.effects == (
        RunArchivePreparationEffect(
            request_id=1,
            request=ExtractArchiveRequest(
                source_path=str(Path(source_path).resolve()),
                destination_path=str(Path(dest_path).resolve()),
            ),
        ),
    )


def test_submit_pending_zip_compress_starts_preparation() -> None:
    dest_path = "/tmp/output.zip"
    state = replace(
        build_initial_app_state(),
        ui_mode="ZIP",
        pending_input=PendingInputState(
            prompt="Compress to: ",
            value=dest_path,
            zip_source_paths=(
                "/home/tadashi/develop/zivo/docs",
                "/home/tadashi/develop/zivo/src",
            ),
        ),
    )

    result = reduce_app_state(state, SubmitPendingInput())

    assert result.state.pending_zip_compress_prepare_request_id == 1
    assert result.state.ui_mode == "BUSY"
    assert result.effects == (
        RunZipCompressPreparationEffect(
            request_id=1,
            request=CreateZipArchiveRequest(
                source_paths=(
                    "/home/tadashi/develop/zivo/docs",
                    "/home/tadashi/develop/zivo/src",
                ),
                destination_path=str(Path(dest_path).resolve()),
                root_dir="/home/tadashi/develop/zivo",
            ),
        ),
    )


def test_submit_pending_extract_resolves_relative_destination_from_archive_parent() -> None:
    source_path = "/home/tadashi/develop/zivo/docs/archive.tar.bz2"
    state = replace(
        build_initial_app_state(),
        ui_mode="EXTRACT",
        pending_input=PendingInputState(
            prompt="Extract to: ",
            value="../exports/archive",
            extract_source_path=source_path,
        ),
    )

    result = reduce_app_state(state, SubmitPendingInput())

    assert result.effects == (
        RunArchivePreparationEffect(
            request_id=1,
            request=ExtractArchiveRequest(
                source_path=str(Path(source_path).resolve()),
                destination_path=str(Path("/home/tadashi/develop/zivo/exports/archive").resolve()),
            ),
        ),
    )


def test_archive_preparation_with_conflicts_enters_confirm_mode() -> None:
    request = ExtractArchiveRequest(
        source_path="/home/tadashi/develop/zivo/archive.zip",
        destination_path="/tmp/output/archive",
    )
    state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        pending_input=PendingInputState(
            prompt="Extract to: ",
            value="/tmp/output/archive",
            extract_source_path=request.source_path,
        ),
        pending_archive_prepare_request_id=4,
    )

    next_state = _reduce_state(
        state,
        ArchivePreparationCompleted(
            request_id=4,
            request=request,
            total_entries=7,
            conflict_count=2,
            first_conflict_path="/tmp/output/archive/notes.txt",
        ),
    )

    assert next_state.ui_mode == "CONFIRM"
    assert next_state.pending_archive_prepare_request_id is None
    assert next_state.archive_extract_confirmation == ArchiveExtractConfirmationState(
        request=request,
        conflict_count=2,
        first_conflict_path="/tmp/output/archive/notes.txt",
        total_entries=7,
    )


def test_zip_compress_preparation_with_existing_destination_enters_confirm_mode() -> None:
    request = CreateZipArchiveRequest(
        source_paths=("/home/tadashi/develop/zivo/docs",),
        destination_path="/home/tadashi/develop/zivo/docs.zip",
        root_dir="/home/tadashi/develop/zivo",
    )
    state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        pending_input=PendingInputState(
            prompt="Compress to: ",
            value="/home/tadashi/develop/zivo/docs.zip",
            zip_source_paths=request.source_paths,
        ),
        pending_zip_compress_prepare_request_id=4,
    )

    next_state = _reduce_state(
        state,
        ZipCompressPreparationCompleted(
            request_id=4,
            request=request,
            total_entries=7,
            destination_exists=True,
        ),
    )

    assert next_state.ui_mode == "CONFIRM"
    assert next_state.pending_zip_compress_prepare_request_id is None
    assert next_state.zip_compress_confirmation == ZipCompressConfirmationState(
        request=request,
        total_entries=7,
    )


def test_confirm_archive_extract_runs_extract_effect() -> None:
    request = ExtractArchiveRequest(
        source_path="/home/tadashi/develop/zivo/archive.zip",
        destination_path="/tmp/output/archive",
    )
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        pending_input=PendingInputState(
            prompt="Extract to: ",
            value="/tmp/output/archive",
            extract_source_path=request.source_path,
        ),
        archive_extract_confirmation=ArchiveExtractConfirmationState(
            request=request,
            conflict_count=1,
            first_conflict_path="/tmp/output/archive/notes.txt",
            total_entries=3,
        ),
    )

    result = reduce_app_state(state, ConfirmArchiveExtract())

    assert result.state.pending_archive_extract_request_id == 1
    assert result.effects == (
        RunArchiveExtractEffect(
            request_id=1,
            request=request,
        ),
    )


def test_confirm_zip_compress_runs_effect() -> None:
    request = CreateZipArchiveRequest(
        source_paths=("/home/tadashi/develop/zivo/docs",),
        destination_path="/home/tadashi/develop/zivo/docs.zip",
        root_dir="/home/tadashi/develop/zivo",
    )
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        pending_input=PendingInputState(
            prompt="Compress to: ",
            value="/home/tadashi/develop/zivo/docs.zip",
            zip_source_paths=request.source_paths,
        ),
        zip_compress_confirmation=ZipCompressConfirmationState(
            request=request,
            total_entries=3,
        ),
    )

    result = reduce_app_state(state, ConfirmZipCompress())

    assert result.state.pending_zip_compress_request_id == 1
    assert result.effects == (
        RunZipCompressEffect(
            request_id=1,
            request=request,
        ),
    )


def test_cancel_archive_extract_confirmation_returns_to_extract_mode() -> None:
    request = ExtractArchiveRequest(
        source_path="/home/tadashi/develop/zivo/archive.zip",
        destination_path="/tmp/output/archive",
    )
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        pending_input=PendingInputState(
            prompt="Extract to: ",
            value="/tmp/output/archive",
            extract_source_path=request.source_path,
        ),
        archive_extract_confirmation=ArchiveExtractConfirmationState(
            request=request,
            conflict_count=1,
            first_conflict_path="/tmp/output/archive/notes.txt",
            total_entries=3,
        ),
    )

    next_state = _reduce_state(state, CancelArchiveExtractConfirmation())

    assert next_state.ui_mode == "EXTRACT"
    assert next_state.archive_extract_confirmation is None
    assert next_state.notification == NotificationState(
        level="warning",
        message="Extraction cancelled",
    )


def test_cancel_zip_compress_confirmation_returns_to_zip_mode() -> None:
    request = CreateZipArchiveRequest(
        source_paths=("/home/tadashi/develop/zivo/docs",),
        destination_path="/home/tadashi/develop/zivo/docs.zip",
        root_dir="/home/tadashi/develop/zivo",
    )
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        pending_input=PendingInputState(
            prompt="Compress to: ",
            value="/home/tadashi/develop/zivo/docs.zip",
            zip_source_paths=request.source_paths,
        ),
        zip_compress_confirmation=ZipCompressConfirmationState(
            request=request,
            total_entries=3,
        ),
    )

    next_state = _reduce_state(state, CancelZipCompressConfirmation())

    assert next_state.ui_mode == "ZIP"
    assert next_state.zip_compress_confirmation is None
    assert next_state.notification == NotificationState(
        level="warning",
        message="Zip compression cancelled",
    )


def test_archive_extract_progress_updates_notification() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        pending_archive_extract_request_id=6,
    )

    next_state = _reduce_state(
        state,
        ArchiveExtractProgress(
            request_id=6,
            completed_entries=2,
            total_entries=5,
            current_path="/tmp/output/archive/notes.txt",
        ),
    )

    assert next_state.archive_extract_progress == ArchiveExtractProgressState(
        completed_entries=2,
        total_entries=5,
        current_path="/tmp/output/archive/notes.txt",
    )
    assert next_state.notification == NotificationState(
        level="info",
        message="Extracting archive 2/5: notes.txt",
    )


def test_zip_compress_progress_updates_notification() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        pending_zip_compress_request_id=6,
    )

    next_state = _reduce_state(
        state,
        ZipCompressProgress(
            request_id=6,
            completed_entries=2,
            total_entries=5,
            current_path="/home/tadashi/develop/zivo/docs/readme.txt",
        ),
    )

    assert next_state.zip_compress_progress == ZipCompressProgressState(
        completed_entries=2,
        total_entries=5,
        current_path="/home/tadashi/develop/zivo/docs/readme.txt",
    )
    assert next_state.notification == NotificationState(
        level="info",
        message="Compressing as zip 2/5: readme.txt",
    )


def test_archive_extract_completed_requests_snapshot_for_destination_parent() -> None:
    dest_parent = str(Path("/tmp/output").resolve())
    dest_path = str(Path("/tmp/output/archive").resolve())
    state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        pending_input=PendingInputState(
            prompt="Extract to: ",
            value=dest_path,
            extract_source_path="/home/tadashi/develop/zivo/archive.zip",
        ),
        pending_archive_extract_request_id=9,
    )

    result = reduce_app_state(
        state,
        ArchiveExtractCompleted(
            request_id=9,
            result=ExtractArchiveResult(
                destination_path=dest_path,
                extracted_entries=2,
                total_entries=2,
                message="Extracted 2 entries to archive",
            ),
        ),
    )

    assert result.state.post_reload_notification == NotificationState(
        level="info",
        message="Extracted 2 entries to archive",
    )
    assert result.effects == (
        LoadBrowserSnapshotEffect(
            request_id=1,
            path=dest_parent,
            cursor_path=dest_path,
            blocking=True,
            invalidate_paths=browser_snapshot_invalidation_paths(
                dest_parent, dest_path
            ),
        ),
    )


def test_zip_compress_completed_requests_snapshot_for_destination_parent() -> None:
    dest_parent = str(Path("/tmp").resolve())
    dest_path = str(Path("/tmp/output.zip").resolve())
    state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        pending_input=PendingInputState(
            prompt="Compress to: ",
            value=dest_path,
            zip_source_paths=("/home/tadashi/develop/zivo/docs",),
        ),
        pending_zip_compress_request_id=9,
    )

    result = reduce_app_state(
        state,
        ZipCompressCompleted(
            request_id=9,
            result=CreateZipArchiveResult(
                destination_path=dest_path,
                archived_entries=2,
                total_entries=2,
                message="Created output.zip with 2 entries",
            ),
        ),
    )

    assert result.state.post_reload_notification == NotificationState(
        level="info",
        message="Created output.zip with 2 entries",
    )
    assert result.effects == (
        LoadBrowserSnapshotEffect(
            request_id=1,
            path=dest_parent,
            cursor_path=dest_path,
            blocking=True,
            invalidate_paths=browser_snapshot_invalidation_paths(
                dest_parent, dest_path
            ),
        ),
    )


def test_archive_extract_failed_returns_to_extract_mode() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        pending_input=PendingInputState(
            prompt="Extract to: ",
            value="/tmp/output/archive",
            extract_source_path="/home/tadashi/develop/zivo/archive.zip",
        ),
        pending_archive_extract_request_id=12,
    )

    next_state = _reduce_state(
        state,
        ArchiveExtractFailed(request_id=12, message="Unsupported archive member type: link"),
    )

    assert next_state.ui_mode == "EXTRACT"
    assert next_state.pending_archive_extract_request_id is None
    assert next_state.notification == NotificationState(
        level="error",
        message="Unsupported archive member type: link",
    )


def test_zip_compress_failed_returns_to_zip_mode() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        pending_input=PendingInputState(
            prompt="Compress to: ",
            value="/tmp/output.zip",
            zip_source_paths=("/home/tadashi/develop/zivo/docs",),
        ),
        pending_zip_compress_request_id=12,
    )

    next_state = _reduce_state(
        state,
        ZipCompressFailed(request_id=12, message="Destination path already exists as a directory"),
    )

    assert next_state.ui_mode == "ZIP"
    assert next_state.pending_zip_compress_request_id is None
    assert next_state.notification == NotificationState(
        level="error",
        message="Destination path already exists as a directory",
    )


def test_archive_preparation_failed_returns_to_extract_mode() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        pending_input=PendingInputState(
            prompt="Extract to: ",
            value="/tmp/output/archive",
            extract_source_path="/home/tadashi/develop/zivo/archive.zip",
        ),
        pending_archive_prepare_request_id=7,
    )

    next_state = _reduce_state(
        state,
        ArchivePreparationFailed(request_id=7, message="Unsupported archive format: archive.rar"),
    )

    assert next_state.ui_mode == "EXTRACT"
    assert next_state.pending_archive_prepare_request_id is None
    assert next_state.notification == NotificationState(
        level="error",
        message="Unsupported archive format: archive.rar",
    )


def test_set_pending_input_value_updates_current_value() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CREATE",
        pending_input=PendingInputState(prompt="New file: ", value="", create_kind="file"),
    )

    next_state = _reduce_state(state, SetPendingInputValue("notes.txt", cursor_pos=8))

    assert next_state.pending_input is not None
    assert next_state.pending_input.value == "notes.txt"


def test_submit_pending_input_rejects_duplicate_name() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CREATE",
        pending_input=PendingInputState(
            prompt="New file: ",
            value="README.md",
            create_kind="file",
        ),
    )

    next_state = _reduce_state(state, SubmitPendingInput())

    assert next_state.ui_mode == "CONFIRM"
    assert next_state.pending_input is not None
    assert next_state.notification is None
    assert next_state.name_conflict == NameConflictState(
        kind="create_file",
        name="README.md",
    )


def test_submit_pending_input_treats_unchanged_rename_as_noop() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="RENAME",
        pending_input=PendingInputState(
            prompt="Rename: ",
            value="docs",
            target_path="/home/tadashi/develop/zivo/docs",
        ),
    )

    next_state = _reduce_state(state, SubmitPendingInput())

    assert next_state.ui_mode == "BROWSING"
    assert next_state.pending_input is None
    assert next_state.notification == NotificationState(level="info", message="Name unchanged")


def test_submit_pending_input_emits_file_mutation_effect() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="RENAME",
        pending_input=PendingInputState(
            prompt="Rename: ",
            value="manuals",
            target_path="/home/tadashi/develop/zivo/docs",
        ),
    )

    result = reduce_app_state(state, SubmitPendingInput())

    assert result.state.ui_mode == "BUSY"
    assert result.state.pending_file_mutation_request_id == 1
    assert result.effects == (
        RunFileMutationEffect(
            request_id=1,
            request=RenameRequest(
                source_path="/home/tadashi/develop/zivo/docs",
                new_name="manuals",
            ),
        ),
    )


def test_submit_pending_input_emits_create_effect() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CREATE",
        pending_input=PendingInputState(
            prompt="New file: ",
            value="notes.txt",
            create_kind="file",
        ),
    )

    result = reduce_app_state(state, SubmitPendingInput())

    assert result.effects == (
        RunFileMutationEffect(
            request_id=1,
            request=CreatePathRequest(
                parent_dir="/home/tadashi/develop/zivo",
                name="notes.txt",
                kind="file",
            ),
        ),
    )


def test_submit_pending_input_name_conflict_enters_confirm_mode_for_rename() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="RENAME",
        pending_input=PendingInputState(
            prompt="Rename: ",
            value="src",
            target_path="/home/tadashi/develop/zivo/docs",
        ),
    )

    result = reduce_app_state(state, SubmitPendingInput())

    assert result.state.ui_mode == "CONFIRM"
    assert result.state.notification is None
    assert result.state.name_conflict == NameConflictState(kind="rename", name="src")
    assert result.effects == ()


def test_submit_pending_input_name_conflict_enters_confirm_mode_for_create_dir() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CREATE",
        pending_input=PendingInputState(
            prompt="New directory: ",
            value="docs",
            create_kind="dir",
        ),
    )

    result = reduce_app_state(state, SubmitPendingInput())

    assert result.state.ui_mode == "CONFIRM"
    assert result.state.name_conflict == NameConflictState(kind="create_dir", name="docs")
    assert result.effects == ()


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


def test_copy_targets_updates_clipboard_state() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(state, CopyTargets(("/home/tadashi/develop/zivo/docs",)))

    assert next_state.clipboard.mode == "copy"
    assert next_state.clipboard.paths == ("/home/tadashi/develop/zivo/docs",)


def test_copy_targets_warns_when_empty() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(state, CopyTargets(()))

    assert next_state.notification == NotificationState(level="warning", message="Nothing to copy")
    assert next_state.clipboard.mode == "none"


def test_cut_targets_warns_when_empty() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(state, CutTargets(()))

    assert next_state.notification == NotificationState(level="warning", message="Nothing to cut")
    assert next_state.clipboard.mode == "none"


def test_paste_clipboard_emits_paste_effect_and_sets_busy() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        CopyTargets(("/home/tadashi/develop/zivo/docs",)),
    )

    result = reduce_app_state(state, PasteClipboard())

    assert result.state.ui_mode == "BUSY"
    assert result.state.pending_paste_request_id == 1
    assert result.effects == (
        RunClipboardPasteEffect(
            request_id=1,
            request=result.effects[0].request,
        ),
    )
    assert result.effects[0].request.destination_dir == "/home/tadashi/develop/zivo"


def test_paste_clipboard_warns_when_empty() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(state, PasteClipboard())

    assert next_state.notification == NotificationState(
        level="warning",
        message="Clipboard is empty",
    )
    assert next_state.ui_mode == "BROWSING"


def test_undo_last_operation_warns_when_stack_is_empty() -> None:
    next_state = _reduce_state(build_initial_app_state(), UndoLastOperation())

    assert next_state.notification == NotificationState(level="warning", message="Nothing to undo")


def test_paste_needs_resolution_enters_confirm_mode() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        CopyTargets(("/home/tadashi/develop/zivo/docs",)),
    )
    requested = reduce_app_state(state, PasteClipboard()).state

    conflict = PasteConflict(
        source_path="/home/tadashi/develop/zivo/docs",
        destination_path="/home/tadashi/develop/zivo/docs",
    )
    next_state = _reduce_state(
        requested,
        ClipboardPasteNeedsResolution(
            request_id=1,
            request=PasteRequest(
                mode="copy",
                source_paths=("/home/tadashi/develop/zivo/docs",),
                destination_dir="/home/tadashi/develop/zivo",
            ),
            conflicts=(conflict,),
        ),
    )

    assert next_state.ui_mode == "CONFIRM"
    assert isinstance(next_state.paste_conflict, PasteConflictState)
    assert next_state.paste_conflict.first_conflict == conflict


def test_paste_needs_resolution_uses_configured_default_resolution() -> None:
    state = _reduce_state(
        build_initial_app_state(paste_conflict_action="rename"),
        CopyTargets(("/home/tadashi/develop/zivo/docs",)),
    )
    requested = reduce_app_state(state, PasteClipboard()).state

    conflict = PasteConflict(
        source_path="/home/tadashi/develop/zivo/docs",
        destination_path="/home/tadashi/develop/zivo/docs",
    )
    result = reduce_app_state(
        requested,
        ClipboardPasteNeedsResolution(
            request_id=1,
            request=PasteRequest(
                mode="copy",
                source_paths=("/home/tadashi/develop/zivo/docs",),
                destination_dir="/home/tadashi/develop/zivo",
            ),
            conflicts=(conflict,),
        ),
    )

    assert result.state.ui_mode == "BUSY"
    assert result.effects == (
        RunClipboardPasteEffect(
            request_id=2,
            request=PasteRequest(
                mode="copy",
                source_paths=("/home/tadashi/develop/zivo/docs",),
                destination_dir="/home/tadashi/develop/zivo",
                conflict_resolution="rename",
            ),
        ),
    )


def test_paste_needs_resolution_ignores_stale_request() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        CopyTargets(("/home/tadashi/develop/zivo/docs",)),
    )
    requested = reduce_app_state(state, PasteClipboard()).state

    conflict = PasteConflict(
        source_path="/home/tadashi/develop/zivo/docs",
        destination_path="/home/tadashi/develop/zivo/docs",
    )
    next_state = _reduce_state(
        requested,
        ClipboardPasteNeedsResolution(
            request_id=99,
            request=PasteRequest(
                mode="copy",
                source_paths=("/home/tadashi/develop/zivo/docs",),
                destination_dir="/home/tadashi/develop/zivo",
            ),
            conflicts=(conflict,),
        ),
    )

    assert next_state == requested


def test_resolve_paste_conflict_restarts_paste_with_resolution() -> None:
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
        next_request_id=2,
    )
    state = replace(
        state,
        notification=None,
    )

    result = reduce_app_state(state, ResolvePasteConflict("rename"))

    assert result.state.ui_mode == "BUSY"
    assert result.effects == (
        RunClipboardPasteEffect(
            request_id=2,
            request=PasteRequest(
                mode="copy",
                source_paths=("/home/tadashi/develop/zivo/docs",),
                destination_dir="/home/tadashi/develop/zivo",
                conflict_resolution="rename",
            ),
        ),
    )


def test_clipboard_paste_completed_for_cut_clears_clipboard_and_requests_reload() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        CutTargets(("/home/tadashi/develop/zivo/docs",)),
    )
    state = replace(state, pending_paste_request_id=4)

    result = reduce_app_state(
        state,
        ClipboardPasteCompleted(
            request_id=4,
            summary=PasteSummary(
                mode="cut",
                destination_dir="/home/tadashi/develop/zivo",
                total_count=1,
                success_count=1,
                skipped_count=0,
            ),
            applied_changes=(
                PasteAppliedChange(
                    source_path="/tmp/staging/docs",
                    destination_path="/home/tadashi/develop/zivo/docs",
                ),
            ),
        ),
    )

    assert result.state.clipboard.mode == "none"
    assert result.state.undo_stack == (
        UndoEntry(
            kind="paste_cut",
            steps=(
                UndoMovePathStep(
                    source_path="/home/tadashi/develop/zivo/docs",
                    destination_path="/tmp/staging/docs",
                ),
            ),
        ),
    )
    assert result.state.pending_browser_snapshot_request_id == 1
    assert result.effects == (
        LoadBrowserSnapshotEffect(
            request_id=1,
            path="/home/tadashi/develop/zivo",
            cursor_path="/home/tadashi/develop/zivo/docs",
            blocking=False,
            invalidate_paths=tuple(
                str(Path(p).resolve())
                for p in (
                    "/home/tadashi/develop/zivo",
                    "/home/tadashi/develop",
                    "/home/tadashi/develop/zivo/docs",
                )
            ),
        ),
    )


def test_clipboard_paste_completed_pushes_copy_undo_entry() -> None:
    state = replace(build_initial_app_state(), pending_paste_request_id=4)

    next_state = _reduce_state(
        state,
        ClipboardPasteCompleted(
            request_id=4,
            summary=PasteSummary(
                mode="copy",
                destination_dir="/home/tadashi/develop/zivo",
                total_count=1,
                success_count=1,
                skipped_count=0,
            ),
            applied_changes=(
                PasteAppliedChange(
                    source_path="/tmp/source/docs",
                    destination_path="/home/tadashi/develop/zivo/docs copy",
                ),
            ),
        ),
    )

    assert next_state.undo_stack == (
        UndoEntry(
            kind="paste_copy",
            steps=(UndoDeletePathStep(path="/home/tadashi/develop/zivo/docs copy"),),
        ),
    )


def test_clipboard_paste_completed_skips_undo_for_overwrite() -> None:
    state = replace(build_initial_app_state(), pending_paste_request_id=4)

    next_state = _reduce_state(
        state,
        ClipboardPasteCompleted(
            request_id=4,
            summary=PasteSummary(
                mode="copy",
                destination_dir="/home/tadashi/develop/zivo",
                total_count=1,
                success_count=1,
                skipped_count=0,
                overwrote_count=1,
            ),
            applied_changes=(
                PasteAppliedChange(
                    source_path="/tmp/source/docs",
                    destination_path="/home/tadashi/develop/zivo/docs",
                ),
            ),
        ),
    )

    assert next_state.undo_stack == ()
    assert next_state.post_reload_notification == NotificationState(
        level="info",
        message="Copied 1 item(s), undo unavailable for overwritten items",
    )


def test_file_mutation_completed_requests_reload_with_result_cursor() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        pending_file_mutation_request_id=4,
        pending_input=PendingInputState(
            prompt="New file: ",
            value="notes.txt",
            create_kind="file",
        ),
    )

    result = reduce_app_state(
        state,
        FileMutationCompleted(
            request_id=4,
            result=FileMutationResult(
                path="/home/tadashi/develop/zivo/notes.txt",
                message="Created file notes.txt",
            ),
        ),
    )

    assert result.state.ui_mode == "BROWSING"
    assert result.state.pending_input is None
    assert result.state.undo_stack == ()
    assert result.state.pending_browser_snapshot_request_id == 1
    assert result.effects == (
        LoadBrowserSnapshotEffect(
            request_id=1,
            path="/home/tadashi/develop/zivo",
            cursor_path="/home/tadashi/develop/zivo/notes.txt",
            blocking=False,
            invalidate_paths=tuple(
                str(Path(p).resolve())
                for p in (
                    "/home/tadashi/develop/zivo",
                    "/home/tadashi/develop",
                    "/home/tadashi/develop/zivo/notes.txt",
                )
            ),
        ),
    )
    state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        pending_file_mutation_request_id=4,
        pending_input=PendingInputState(
            prompt="Rename: ",
            value="manuals",
            target_path="/home/tadashi/develop/zivo/docs",
        ),
    )

    next_state = _reduce_state(
        state,
        FileMutationCompleted(
            request_id=4,
            result=FileMutationResult(
                path="/home/tadashi/develop/zivo/manuals",
                message="Renamed to manuals",
                operation="rename",
                source_path="/home/tadashi/develop/zivo/docs",
            ),
        ),
    )

    assert next_state.undo_stack == (
        UndoEntry(
            kind="rename",
            steps=(
                UndoMovePathStep(
                    source_path="/home/tadashi/develop/zivo/manuals",
                    destination_path="/home/tadashi/develop/zivo/docs",
                ),
            ),
        ),
    )


def test_delete_file_mutation_completed_requests_reload_without_deleted_cursor() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        pending_file_mutation_request_id=7,
        current_pane=replace(
            build_initial_app_state().current_pane,
            cursor_path="/home/tadashi/develop/zivo/docs",
        ),
    )

    result = reduce_app_state(
        state,
        FileMutationCompleted(
            request_id=7,
            result=FileMutationResult(
                path=None,
                message="Trashed 1 item",
                removed_paths=("/home/tadashi/develop/zivo/docs",),
            ),
        ),
    )

    assert result.state.ui_mode == "BROWSING"
    assert result.state.undo_stack == ()
    assert result.effects == (
        LoadBrowserSnapshotEffect(
            request_id=1,
            path="/home/tadashi/develop/zivo",
            cursor_path="/home/tadashi/develop/zivo/src",
            blocking=False,
            invalidate_paths=tuple(
                str(Path(p).resolve())
                for p in (
                    "/home/tadashi/develop/zivo",
                    "/home/tadashi/develop",
                    "/home/tadashi/develop/zivo/src",
                )
            ),
        ),
    )
    state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        pending_file_mutation_request_id=7,
    )

    next_state = _reduce_state(
        state,
        FileMutationCompleted(
            request_id=7,
            result=FileMutationResult(
                path=None,
                message="Trashed 1 item",
                removed_paths=("/home/tadashi/develop/zivo/docs",),
                operation="delete",
                delete_mode="trash",
                trash_records=(
                    TrashRestoreRecord(
                        original_path="/home/tadashi/develop/zivo/docs",
                        trashed_path="/home/tadashi/.local/share/Trash/files/docs",
                        metadata_path="/home/tadashi/.local/share/Trash/info/docs.trashinfo",
                    ),
                ),
            ),
        ),
    )

    assert next_state.undo_stack == (
        UndoEntry(
            kind="trash_delete",
            steps=(
                UndoRestoreTrashStep(
                    record=TrashRestoreRecord(
                        original_path="/home/tadashi/develop/zivo/docs",
                        trashed_path="/home/tadashi/.local/share/Trash/files/docs",
                        metadata_path="/home/tadashi/.local/share/Trash/info/docs.trashinfo",
                    )
                ),
            ),
        ),
    )


def test_undo_last_operation_runs_effect() -> None:
    entry = UndoEntry(kind="paste_copy", steps=(UndoDeletePathStep(path="/tmp/copied"),))
    state = replace(build_initial_app_state(), undo_stack=(entry,), next_request_id=6)

    result = reduce_app_state(state, UndoLastOperation())

    assert result.state.pending_undo_entry == entry
    assert result.state.pending_undo_request_id == 6
    assert result.state.ui_mode == "BUSY"
    assert result.effects == (RunUndoEffect(request_id=6, entry=entry),)


def test_undo_completed_pops_stack_and_requests_reload() -> None:
    entry = UndoEntry(kind="paste_copy", steps=(UndoDeletePathStep(path="/tmp/copied"),))
    state = replace(
        build_initial_app_state(),
        undo_stack=(entry,),
        pending_undo_entry=entry,
        pending_undo_request_id=9,
        next_request_id=4,
    )

    result = reduce_app_state(
        state,
        UndoCompleted(
            request_id=9,
            entry=entry,
            result=UndoResult(
                path=None,
                message="Undid copied item",
                removed_paths=("/tmp/copied",),
            ),
        ),
    )

    assert result.state.undo_stack == ()
    assert result.state.pending_undo_request_id is None
    assert result.state.post_reload_notification == NotificationState(
        level="info",
        message="Undid copied item",
    )
    assert result.effects == (
        LoadBrowserSnapshotEffect(
            request_id=4,
            path="/home/tadashi/develop/zivo",
            cursor_path="/home/tadashi/develop/zivo/docs",
            blocking=False,
            invalidate_paths=tuple(
                str(Path(p).resolve())
                for p in (
                    "/home/tadashi/develop/zivo",
                    "/home/tadashi/develop",
                    "/home/tadashi/develop/zivo/docs",
                )
            ),
        ),
    )
    entry = UndoEntry(kind="paste_copy", steps=(UndoDeletePathStep(path="/tmp/copied"),))
    state = replace(
        build_initial_app_state(),
        undo_stack=(entry,),
        pending_undo_entry=entry,
        pending_undo_request_id=9,
        ui_mode="BUSY",
    )

    next_state = _reduce_state(state, UndoFailed(request_id=9, message="permission denied"))

    assert next_state.pending_undo_request_id is None
    assert next_state.undo_stack == (entry,)
    assert next_state.notification == NotificationState(
        level="error",
        message="permission denied",
    )


def test_file_mutation_failed_keeps_input_value_and_returns_error() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        pending_file_mutation_request_id=3,
        pending_input=PendingInputState(
            prompt="Rename: ",
            value="docs copy",
            target_path="/home/tadashi/develop/zivo/docs",
        ),
    )

    next_state = _reduce_state(state, FileMutationFailed(request_id=3, message="permission denied"))

    assert next_state.ui_mode == "RENAME"
    assert next_state.pending_input is not None
    assert next_state.pending_input.value == "docs copy"
    assert next_state.notification == NotificationState(
        level="error",
        message="permission denied",
    )


def test_delete_file_mutation_failed_returns_to_browsing() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        pending_file_mutation_request_id=5,
    )

    next_state = _reduce_state(state, FileMutationFailed(request_id=5, message="trash failed"))

    assert next_state.ui_mode == "BROWSING"
    assert next_state.notification == NotificationState(
        level="error",
        message="trash failed",
    )


def test_clipboard_paste_failed_returns_to_browsing_and_clears_dialog_state() -> None:
    conflict = PasteConflict(
        source_path="/home/tadashi/develop/zivo/docs",
        destination_path="/home/tadashi/develop/zivo/docs",
    )
    state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        pending_paste_request_id=4,
        paste_conflict=PasteConflictState(
            request=PasteRequest(
                mode="copy",
                source_paths=("/home/tadashi/develop/zivo/docs",),
                destination_dir="/home/tadashi/develop/zivo",
            ),
            conflicts=(conflict,),
            first_conflict=conflict,
        ),
        delete_confirmation=DeleteConfirmationState(paths=("/home/tadashi/develop/zivo/docs",)),
        name_conflict=NameConflictState(kind="rename", name="docs"),
    )

    next_state = _reduce_state(
        state,
        ClipboardPasteFailed(request_id=4, message="paste failed"),
    )

    assert next_state.ui_mode == "BROWSING"
    assert next_state.paste_conflict is None
    assert next_state.delete_confirmation is None
    assert next_state.name_conflict is None
    assert next_state.notification == NotificationState(level="error", message="paste failed")


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


def test_cancel_paste_conflict_returns_to_browsing_with_warning() -> None:
    state = replace(build_initial_app_state(), ui_mode="CONFIRM")

    next_state = _reduce_state(state, CancelPasteConflict())

    assert next_state.ui_mode == "BROWSING"
    assert next_state.notification == NotificationState(level="warning", message="Paste cancelled")


def test_toggle_selection_and_advance_moves_cursor_to_next_visible_entry() -> None:
    state = build_initial_app_state()
    current_path = "/home/tadashi/develop/zivo/docs"
    visible_paths = (
        "/home/tadashi/develop/zivo/docs",
        "/home/tadashi/develop/zivo/src",
        "/home/tadashi/develop/zivo/tests",
        "/home/tadashi/develop/zivo/README.md",
        "/home/tadashi/develop/zivo/pyproject.toml",
    )

    result = reduce_app_state(
        state,
        ToggleSelectionAndAdvance(path=current_path, visible_paths=visible_paths),
    )

    assert result.state.current_pane.selected_paths == frozenset({current_path})
    assert result.state.current_pane.cursor_path == "/home/tadashi/develop/zivo/src"
    assert result.state.pending_child_pane_request_id == 1
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
            display=replace(build_initial_app_state().config.display, show_preview=False),
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
            display=replace(build_initial_app_state().config.display, show_preview=False),
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
    assert result.state.current_pane_window_start == 1


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


def test_begin_empty_trash_enters_confirm_mode(monkeypatch) -> None:
    monkeypatch.setattr("platform.system", lambda: "Darwin")

    state = build_initial_app_state()

    next_state = _reduce_state(state, BeginEmptyTrash())

    assert next_state.ui_mode == "CONFIRM"
    assert next_state.empty_trash_confirmation is not None
    assert next_state.empty_trash_confirmation.platform == "darwin"
    assert next_state.command_palette is None
    assert next_state.pending_input is None


def test_cancel_empty_trash_confirmation_returns_to_browsing() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        empty_trash_confirmation=EmptyTrashConfirmationState(platform="darwin"),
    )

    next_state = _reduce_state(state, CancelEmptyTrashConfirmation())

    assert next_state.ui_mode == "BROWSING"
    assert next_state.empty_trash_confirmation is None
    assert next_state.notification is None


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


def test_begin_command_palette_clears_pending_key_sequence() -> None:
    state = replace(
        build_initial_app_state(),
        pending_key_sequence=PendingKeySequenceState(
            keys=("y",),
            possible_next_keys=("y",),
        ),
    )

    next_state = _reduce_state(state, BeginCommandPalette())

    assert next_state.ui_mode == "PALETTE"
    assert next_state.pending_key_sequence is None


def test_confirm_empty_trash_shows_notification_on_success(monkeypatch) -> None:
    from unittest.mock import MagicMock

    from zivo.services.trash_operations import MacOsTrashService

    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        empty_trash_confirmation=EmptyTrashConfirmationState(platform="darwin"),
    )

    fake_service = MacOsTrashService()
    monkeypatch.setattr(
        "zivo.services.resolve_trash_service",
        lambda: fake_service,
    )
    monkeypatch.setattr(
        "zivo.services.trash_operations.subprocess.run",
        lambda *a, **kw: MagicMock(returncode=0, stderr=""),
    )

    class FakeHome:
        def __truediv__(self, other):
            return FakePath()

    class FakePath:
        def exists(self):
            return False

    monkeypatch.setattr("pathlib.Path.home", lambda: FakeHome())

    next_state = _reduce_state(state, ConfirmEmptyTrash())

    assert next_state.ui_mode == "BROWSING"
    assert next_state.empty_trash_confirmation is None
    assert next_state.notification is not None
    assert next_state.notification.level == "info"


def test_submit_pending_input_case_only_rename_emits_mutation() -> None:
    """Case-only rename (docs -> Docs) should proceed, not show 'Name unchanged'."""
    state = replace(
        build_initial_app_state(),
        ui_mode="RENAME",
        pending_input=PendingInputState(
            prompt="Rename: ",
            value="Docs",
            target_path="/home/tadashi/develop/zivo/docs",
        ),
    )

    result = reduce_app_state(state, SubmitPendingInput())

    assert result.state.ui_mode == "BUSY"
    assert result.effects == (
        RunFileMutationEffect(
            request_id=1,
            request=RenameRequest(
                source_path="/home/tadashi/develop/zivo/docs",
                new_name="Docs",
            ),
        ),
    )


def test_submit_pending_input_case_insensitive_conflict_on_macos(monkeypatch) -> None:
    """On macOS, renaming to a case-different existing name should conflict."""
    import zivo.state.reducer_common as rc

    monkeypatch.setattr(rc, "_is_macos", True)
    state = replace(
        build_initial_app_state(),
        ui_mode="RENAME",
        pending_input=PendingInputState(
            prompt="Rename: ",
            value="Src",
            target_path="/home/tadashi/develop/zivo/docs",
        ),
    )

    result = reduce_app_state(state, SubmitPendingInput())

    assert result.state.ui_mode == "CONFIRM"
    assert result.state.name_conflict == NameConflictState(kind="rename", name="Src")


def test_submit_pending_input_case_sensitive_no_conflict_on_linux(monkeypatch) -> None:
    """On Linux, renaming to a case-different existing name should NOT conflict."""
    import zivo.state.reducer_common as rc

    monkeypatch.setattr(rc, "_is_macos", False)
    state = replace(
        build_initial_app_state(),
        ui_mode="RENAME",
        pending_input=PendingInputState(
            prompt="Rename: ",
            value="Src",
            target_path="/home/tadashi/develop/zivo/docs",
        ),
    )

    result = reduce_app_state(state, SubmitPendingInput())

    assert result.state.ui_mode == "BUSY"
    assert result.effects != ()


def test_submit_pending_input_rejects_colon_in_name_on_macos(monkeypatch) -> None:
    """On macOS, names containing ':' should be rejected."""
    import zivo.state.reducer_common as rc

    monkeypatch.setattr(rc, "_is_macos", True)
    state = replace(
        build_initial_app_state(),
        ui_mode="CREATE",
        pending_input=PendingInputState(
            prompt="New file: ",
            value="file:name.txt",
            create_kind="file",
        ),
    )

    next_state = _reduce_state(state, SubmitPendingInput())

    assert next_state.notification is not None
    assert next_state.notification.level == "error"
    assert "colons" in next_state.notification.message


def test_submit_pending_input_allows_colon_in_name_on_linux(monkeypatch) -> None:
    """On Linux, names containing ':' should not be rejected."""
    import zivo.state.reducer_common as rc

    monkeypatch.setattr(rc, "_is_macos", False)
    state = replace(
        build_initial_app_state(),
        ui_mode="CREATE",
        pending_input=PendingInputState(
            prompt="New file: ",
            value="file:name.txt",
            create_kind="file",
        ),
    )

    result = reduce_app_state(state, SubmitPendingInput())

    # Should proceed to emit a create effect (not blocked by colon validation)
    assert result.state.ui_mode == "BUSY"
    assert result.effects != ()


# ---------------------------------------------------------------------------
# Find-and-replace (replace_in_found_files) tests
# ---------------------------------------------------------------------------


def test_begin_find_and_replace_enters_rff_mode() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFindAndReplace())

    assert state.ui_mode == "PALETTE"
    assert state.command_palette is not None
    assert state.command_palette.source == "replace_in_found_files"
    assert state.command_palette.rff_active_field == "filename"


def test_set_rff_filename_field_starts_file_search() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFindAndReplace())

    result = reduce_app_state(state, SetFindReplaceField(field="filename", value="readme"))

    assert result.state.command_palette is not None
    assert result.state.command_palette.rff_filename_query == "readme"
    assert result.state.pending_file_search_request_id == 1
    assert result.effects == (
        RunFileSearchEffect(
            request_id=1,
            root_path="/home/tadashi/develop/zivo",
            query="readme",
            show_hidden=False,
        ),
    )


def test_set_rff_filename_clear_triggers_no_search() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFindAndReplace())

    result = reduce_app_state(
        state,
        SetFindReplaceField(field="filename", value=""),
    )

    assert result.state.command_palette is not None
    assert result.state.pending_file_search_request_id is None
    assert result.effects == ()


def test_set_rff_find_field_with_file_results_starts_preview() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFindAndReplace())
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            rff_filename_query="readme",
            rff_file_results=(
                FileSearchResultState(
                    path="/home/tadashi/develop/zivo/README.md",
                    display_path="README.md",
                ),
            ),
        ),
    )

    result = reduce_app_state(state, SetFindReplaceField(field="find", value="todo"))

    assert result.state.command_palette is not None
    assert result.state.command_palette.rff_find_text == "todo"
    assert result.state.pending_replace_preview_request_id == 1
    assert result.effects == (
        RunTextReplacePreviewEffect(
            request_id=1,
            request=TextReplaceRequest(
                paths=("/home/tadashi/develop/zivo/README.md",),
                find_text="todo",
                replace_text="",
            ),
        ),
    )


def test_set_rff_find_field_without_file_results_no_preview() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFindAndReplace())

    result = reduce_app_state(state, SetFindReplaceField(field="find", value="todo"))

    assert result.state.command_palette is not None
    assert result.state.pending_replace_preview_request_id is None
    assert result.effects == ()


def test_cycle_find_replace_field_cycles_through_three_fields() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFindAndReplace())

    assert state.command_palette is not None
    assert state.command_palette.rff_active_field == "filename"

    state = _reduce_state(state, CycleFindReplaceField(delta=1))
    assert state.command_palette is not None
    assert state.command_palette.rff_active_field == "find"

    state = _reduce_state(state, CycleFindReplaceField(delta=1))
    assert state.command_palette is not None
    assert state.command_palette.rff_active_field == "replace"

    state = _reduce_state(state, CycleFindReplaceField(delta=1))
    assert state.command_palette is not None
    assert state.command_palette.rff_active_field == "filename"


def test_cycle_find_replace_field_reverse() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFindAndReplace())

    state = _reduce_state(state, CycleFindReplaceField(delta=-1))
    assert state.command_palette is not None
    assert state.command_palette.rff_active_field == "replace"


def test_rff_file_search_completed_stores_results() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFindAndReplace())
    state = replace(
        state,
        pending_file_search_request_id=3,
        command_palette=replace(
            state.command_palette,
            rff_filename_query="readme",
        ),
    )

    next_state = _reduce_state(
        state,
        FileSearchCompleted(
            request_id=3,
            query="readme",
            results=(
                FileSearchResultState(
                    path="/home/tadashi/develop/zivo/README.md",
                    display_path="README.md",
                ),
            ),
        ),
    )

    assert next_state.command_palette is not None
    assert next_state.command_palette.rff_file_results == (
        FileSearchResultState(
            path="/home/tadashi/develop/zivo/README.md",
            display_path="README.md",
        ),
    )
    assert next_state.pending_file_search_request_id is None


def test_rff_file_search_completed_auto_triggers_preview_when_find_text_present() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFindAndReplace())
    state = replace(
        state,
        pending_file_search_request_id=3,
        command_palette=replace(
            state.command_palette,
            rff_filename_query="readme",
            rff_find_text="todo",
        ),
    )

    result = reduce_app_state(
        state,
        FileSearchCompleted(
            request_id=3,
            query="readme",
            results=(
                FileSearchResultState(
                    path="/home/tadashi/develop/zivo/README.md",
                    display_path="README.md",
                ),
            ),
        ),
    )

    assert result.state.pending_replace_preview_request_id is not None
    assert len(result.effects) == 1
    assert isinstance(result.effects[0], RunTextReplacePreviewEffect)


def test_rff_preview_completed_stores_results() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFindAndReplace())
    state = replace(
        state,
        pending_replace_preview_request_id=4,
        command_palette=replace(
            state.command_palette,
            rff_find_text="todo",
            rff_replacement_text="done",
            rff_file_results=(
                FileSearchResultState(
                    path="/home/tadashi/develop/zivo/README.md",
                    display_path="README.md",
                ),
            ),
        ),
    )

    next_state = _reduce_state(
        state,
        TextReplacePreviewCompleted(
            request_id=4,
            result=TextReplacePreviewResult(
                request=TextReplaceRequest(
                    paths=("/home/tadashi/develop/zivo/README.md",),
                    find_text="todo",
                    replace_text="done",
                ),
                changed_entries=(
                    TextReplacePreviewEntry(
                        path="/home/tadashi/develop/zivo/README.md",
                        diff_text="-todo\n+done",
                        match_count=1,
                        first_match_line_number=5,
                        first_match_before="todo",
                        first_match_after="done",
                    ),
                ),
                total_match_count=1,
                diff_text="-todo\n+done",
            ),
        ),
    )

    assert next_state.command_palette is not None
    assert next_state.command_palette.rff_total_match_count == 1
    assert len(next_state.command_palette.rff_preview_results) == 1
    assert next_state.command_palette.rff_preview_results[0].display_path == "README.md"
    assert next_state.child_pane.preview_title == "Replace Preview"
    assert next_state.pending_replace_preview_request_id is None


def test_submit_rff_palette_warns_when_no_find_text() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFindAndReplace())

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.notification == NotificationState(
        level="warning",
        message="Find text is required",
    )


def test_submit_rff_palette_warns_when_no_preview_results() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFindAndReplace())
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            rff_find_text="todo",
            rff_file_results=(
                FileSearchResultState(
                    path="/home/tadashi/develop/zivo/README.md",
                    display_path="README.md",
                ),
            ),
        ),
    )

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.notification is not None
    assert result.state.notification.level == "warning"


def test_cancel_rff_returns_to_browsing() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFindAndReplace())
    assert state.ui_mode == "PALETTE"

    state = _reduce_state(state, CancelCommandPalette())
    assert state.ui_mode == "BROWSING"
    assert state.command_palette is None


# ---------------------------------------------------------------------------
# Grep replace (grf) tests
# ---------------------------------------------------------------------------


def test_begin_grep_replace_enters_grf_mode() -> None:
    state = _reduce_state(build_initial_app_state(), BeginGrepReplace())
    assert state.ui_mode == "PALETTE"
    assert state.command_palette is not None
    assert state.command_palette.source == "replace_in_grep_files"
    assert state.command_palette.grf_active_field == "keyword"


def test_set_grf_keyword_field_starts_grep_search() -> None:
    state = _reduce_state(build_initial_app_state(), BeginGrepReplace())
    result = reduce_app_state(state, SetGrepReplaceField(field="keyword", value="todo"))

    assert result.state.pending_grep_search_request_id is not None
    assert result.state.command_palette.grf_keyword == "todo"
    effects = [e for e in result.effects if isinstance(e, RunGrepSearchEffect)]
    assert len(effects) == 1
    assert effects[0].query == "todo"


def test_set_grf_keyword_clear_triggers_no_search() -> None:
    state = _reduce_state(build_initial_app_state(), BeginGrepReplace())
    state = _reduce_state(state, SetGrepReplaceField(field="keyword", value="todo"))
    result = reduce_app_state(state, SetGrepReplaceField(field="keyword", value=""))

    assert result.state.pending_grep_search_request_id is None
    assert result.state.command_palette.grf_grep_results == ()


def test_set_grf_replace_field_with_grep_results_starts_preview() -> None:
    state = _reduce_state(build_initial_app_state(), BeginGrepReplace())
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            grf_keyword="todo",
            grf_grep_results=(
                GrepSearchResultState(
                    path="/home/tadashi/develop/zivo/README.md",
                    display_path="README.md",
                    line_number=1,
                    line_text="todo item",
                ),
            ),
        ),
    )
    result = reduce_app_state(state, SetGrepReplaceField(field="replace", value="done"))

    assert result.state.pending_replace_preview_request_id is not None
    effects = [e for e in result.effects if isinstance(e, RunTextReplacePreviewEffect)]
    assert len(effects) == 1
    assert effects[0].request.paths == ("/home/tadashi/develop/zivo/README.md",)
    assert effects[0].request.find_text == "todo"


def test_set_grf_replace_field_without_grep_results_no_preview() -> None:
    state = _reduce_state(build_initial_app_state(), BeginGrepReplace())
    result = reduce_app_state(state, SetGrepReplaceField(field="replace", value="done"))

    assert result.state.pending_replace_preview_request_id is None
    assert result.state.command_palette.grf_preview_results == ()


def test_grf_grep_search_completed_stores_results() -> None:
    state = _reduce_state(build_initial_app_state(), BeginGrepReplace())
    state = replace(
        state,
        command_palette=replace(state.command_palette, grf_keyword="todo"),
        pending_grep_search_request_id=10,
        next_request_id=11,
    )
    results = (
        GrepSearchResultState(
            path="/home/tadashi/develop/zivo/README.md",
            display_path="README.md",
            line_number=1,
            line_text="todo item",
        ),
    )
    result = reduce_app_state(
        state, GrepSearchCompleted(request_id=10, query="todo", results=results)
    )

    assert result.state.command_palette.grf_grep_results == results
    assert result.state.pending_grep_search_request_id is None


def test_grf_grep_search_completed_auto_triggers_preview_when_replace_text_present() -> None:
    state = _reduce_state(build_initial_app_state(), BeginGrepReplace())
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            grf_keyword="todo",
            grf_replacement_text="done",
        ),
        pending_grep_search_request_id=10,
        next_request_id=11,
    )
    results = (
        GrepSearchResultState(
            path="/home/tadashi/develop/zivo/README.md",
            display_path="README.md",
            line_number=1,
            line_text="todo item",
        ),
    )
    result = reduce_app_state(
        state, GrepSearchCompleted(request_id=10, query="todo", results=results)
    )

    assert result.state.command_palette.grf_grep_results == results
    assert result.state.pending_replace_preview_request_id is not None
    effects = [e for e in result.effects if isinstance(e, RunTextReplacePreviewEffect)]
    assert len(effects) == 1


def test_grf_preview_completed_stores_results() -> None:
    state = _reduce_state(build_initial_app_state(), BeginGrepReplace())
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            grf_keyword="todo",
            grf_replacement_text="done",
            grf_grep_results=(
                GrepSearchResultState(
                    path="/home/tadashi/develop/zivo/README.md",
                    display_path="README.md",
                    line_number=1,
                    line_text="todo item",
                ),
            ),
        ),
        pending_replace_preview_request_id=10,
        next_request_id=11,
    )
    preview_result = TextReplacePreviewResult(
        request=TextReplaceRequest(
            paths=("/home/tadashi/develop/zivo/README.md",),
            find_text="todo",
            replace_text="done",
        ),
        changed_entries=(
            TextReplacePreviewEntry(
                path="/home/tadashi/develop/zivo/README.md",
                diff_text="- todo + done",
                match_count=1,
                first_match_line_number=1,
                first_match_before="todo",
                first_match_after="done",
            ),
        ),
        total_match_count=1,
        skipped_paths=(),
    )
    result = reduce_app_state(
        state, TextReplacePreviewCompleted(request_id=10, result=preview_result)
    )

    assert len(result.state.command_palette.grf_preview_results) == 1
    assert result.state.command_palette.grf_total_match_count == 1
    assert result.state.pending_replace_preview_request_id is None


def test_submit_grf_palette_warns_when_no_replace_text() -> None:
    state = _reduce_state(build_initial_app_state(), BeginGrepReplace())
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            grf_keyword="todo",
            grf_grep_results=(
                GrepSearchResultState(
                    path="/home/tadashi/develop/zivo/README.md",
                    display_path="README.md",
                    line_number=1,
                    line_text="todo item",
                ),
            ),
        ),
    )
    result = reduce_app_state(state, SubmitCommandPalette())
    assert result.state.notification is not None
    assert result.state.notification.level == "warning"


def test_submit_grf_palette_warns_when_no_preview_results() -> None:
    state = _reduce_state(build_initial_app_state(), BeginGrepReplace())
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            grf_keyword="todo",
            grf_replacement_text="done",
            grf_grep_results=(
                GrepSearchResultState(
                    path="/home/tadashi/develop/zivo/README.md",
                    display_path="README.md",
                    line_number=1,
                    line_text="todo item",
                ),
            ),
        ),
    )
    result = reduce_app_state(state, SubmitCommandPalette())
    assert result.state.notification is not None
    assert result.state.notification.level == "warning"


def test_cancel_grf_returns_to_browsing() -> None:
    state = _reduce_state(build_initial_app_state(), BeginGrepReplace())
    assert state.ui_mode == "PALETTE"

    state = _reduce_state(state, CancelCommandPalette())
    assert state.ui_mode == "BROWSING"
    assert state.command_palette is None


def test_submit_command_palette_begins_grep_replace() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery(query="replace text in grep"))

    result = reduce_app_state(state, SubmitCommandPalette())
    assert result.state.command_palette is not None
    assert result.state.command_palette.source == "replace_in_grep_files"


def test_grf_grep_search_completed_deduplicates_file_paths() -> None:
    state = _reduce_state(build_initial_app_state(), BeginGrepReplace())
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            grf_keyword="todo",
            grf_replacement_text="done",
        ),
        pending_grep_search_request_id=10,
        next_request_id=11,
    )
    results = (
        GrepSearchResultState(
            path="/home/tadashi/develop/zivo/README.md",
            display_path="README.md",
            line_number=1,
            line_text="todo item 1",
        ),
        GrepSearchResultState(
            path="/home/tadashi/develop/zivo/README.md",
            display_path="README.md",
            line_number=5,
            line_text="todo item 2",
        ),
    )
    result = reduce_app_state(
        state, GrepSearchCompleted(request_id=10, query="todo", results=results)
    )

    effects = [e for e in result.effects if isinstance(e, RunTextReplacePreviewEffect)]
    assert len(effects) == 1
    assert effects[0].request.paths == ("/home/tadashi/develop/zivo/README.md",)


# ---------------------------------------------------------------------------
# Grep replace selected (grs) tests
# ---------------------------------------------------------------------------


def test_begin_grep_replace_selected_enters_grs_mode() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginGrepReplaceSelected(
            target_paths=("/home/tadashi/develop/zivo/a.py", "/home/tadashi/develop/zivo/b.py")
        ),
    )
    assert state.ui_mode == "PALETTE"
    assert state.command_palette is not None
    assert state.command_palette.source == "grep_replace_selected"
    assert state.command_palette.grs_active_field == "keyword"
    assert state.command_palette.grs_target_paths == (
        "/home/tadashi/develop/zivo/a.py",
        "/home/tadashi/develop/zivo/b.py",
    )


def test_set_grs_keyword_field_starts_grep_search() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginGrepReplaceSelected(target_paths=("/home/tadashi/develop/zivo/a.py",)),
    )
    result = reduce_app_state(
        state, SetGrepReplaceSelectedField(field="keyword", value="todo")
    )

    assert result.state.pending_grep_search_request_id is not None
    assert result.state.command_palette.grs_keyword == "todo"
    effects = [e for e in result.effects if isinstance(e, RunGrepSearchEffect)]
    assert len(effects) == 1
    assert effects[0].query == "todo"


def test_set_grs_keyword_clear_triggers_no_search() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginGrepReplaceSelected(target_paths=("/home/tadashi/develop/zivo/a.py",)),
    )
    state = _reduce_state(state, SetGrepReplaceSelectedField(field="keyword", value="todo"))
    result = reduce_app_state(state, SetGrepReplaceSelectedField(field="keyword", value=""))

    assert result.state.pending_grep_search_request_id is None
    assert result.state.command_palette.grs_grep_results == ()


def test_grs_grep_search_completed_filters_to_target_paths() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginGrepReplaceSelected(
            target_paths=("/home/tadashi/develop/zivo/a.py", "/home/tadashi/develop/zivo/c.py")
        ),
    )
    state = replace(
        state,
        command_palette=replace(state.command_palette, grs_keyword="todo"),
        pending_grep_search_request_id=10,
        next_request_id=11,
    )
    all_results = (
        GrepSearchResultState(
            path="/home/tadashi/develop/zivo/a.py",
            display_path="a.py",
            line_number=1,
            line_text="todo in a",
        ),
        GrepSearchResultState(
            path="/home/tadashi/develop/zivo/b.py",
            display_path="b.py",
            line_number=3,
            line_text="todo in b",
        ),
        GrepSearchResultState(
            path="/home/tadashi/develop/zivo/c.py",
            display_path="c.py",
            line_number=5,
            line_text="todo in c",
        ),
    )
    result = reduce_app_state(
        state, GrepSearchCompleted(request_id=10, query="todo", results=all_results)
    )

    assert len(result.state.command_palette.grs_grep_results) == 2
    assert result.state.command_palette.grs_grep_results[0].path == "/home/tadashi/develop/zivo/a.py"
    assert result.state.command_palette.grs_grep_results[1].path == "/home/tadashi/develop/zivo/c.py"
    assert result.state.pending_grep_search_request_id is None


def test_grs_grep_search_completed_auto_triggers_preview_when_replace_text_present() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginGrepReplaceSelected(target_paths=("/home/tadashi/develop/zivo/a.py",)),
    )
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            grs_keyword="todo",
            grs_replacement_text="done",
        ),
        pending_grep_search_request_id=10,
        next_request_id=11,
    )
    results = (
        GrepSearchResultState(
            path="/home/tadashi/develop/zivo/a.py",
            display_path="a.py",
            line_number=1,
            line_text="todo item",
        ),
    )
    result = reduce_app_state(
        state, GrepSearchCompleted(request_id=10, query="todo", results=results)
    )

    assert result.state.command_palette.grs_grep_results == results
    assert result.state.pending_replace_preview_request_id is not None
    effects = [e for e in result.effects if isinstance(e, RunTextReplacePreviewEffect)]
    assert len(effects) == 1
    assert effects[0].request.paths == ("/home/tadashi/develop/zivo/a.py",)


def test_set_grs_replace_field_with_grep_results_starts_preview() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginGrepReplaceSelected(target_paths=("/home/tadashi/develop/zivo/a.py",)),
    )
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            grs_keyword="todo",
            grs_grep_results=(
                GrepSearchResultState(
                    path="/home/tadashi/develop/zivo/a.py",
                    display_path="a.py",
                    line_number=1,
                    line_text="todo item",
                ),
            ),
        ),
    )
    result = reduce_app_state(
        state, SetGrepReplaceSelectedField(field="replace", value="done")
    )

    assert result.state.pending_replace_preview_request_id is not None
    effects = [e for e in result.effects if isinstance(e, RunTextReplacePreviewEffect)]
    assert len(effects) == 1
    assert effects[0].request.paths == ("/home/tadashi/develop/zivo/a.py",)
    assert effects[0].request.find_text == "todo"


def test_set_grs_replace_field_without_grep_results_no_preview() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginGrepReplaceSelected(target_paths=("/home/tadashi/develop/zivo/a.py",)),
    )
    result = reduce_app_state(
        state, SetGrepReplaceSelectedField(field="replace", value="done")
    )

    assert result.state.pending_replace_preview_request_id is None
    assert result.state.command_palette.grs_preview_results == ()


def test_grs_preview_completed_stores_results() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginGrepReplaceSelected(target_paths=("/home/tadashi/develop/zivo/a.py",)),
    )
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            grs_keyword="todo",
            grs_replacement_text="done",
            grs_grep_results=(
                GrepSearchResultState(
                    path="/home/tadashi/develop/zivo/a.py",
                    display_path="a.py",
                    line_number=1,
                    line_text="todo item",
                ),
            ),
        ),
        pending_replace_preview_request_id=10,
        next_request_id=11,
    )
    preview_result = TextReplacePreviewResult(
        request=TextReplaceRequest(
            paths=("/home/tadashi/develop/zivo/a.py",),
            find_text="todo",
            replace_text="done",
        ),
        changed_entries=(
            TextReplacePreviewEntry(
                path="/home/tadashi/develop/zivo/a.py",
                diff_text="- todo + done",
                match_count=1,
                first_match_line_number=1,
                first_match_before="todo",
                first_match_after="done",
            ),
        ),
        total_match_count=1,
        skipped_paths=(),
    )
    result = reduce_app_state(
        state, TextReplacePreviewCompleted(request_id=10, result=preview_result)
    )

    assert len(result.state.command_palette.grs_preview_results) == 1
    assert result.state.command_palette.grs_total_match_count == 1
    assert result.state.pending_replace_preview_request_id is None


def test_submit_grs_palette_applies_replacement() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginGrepReplaceSelected(target_paths=("/home/tadashi/develop/zivo/a.py",)),
    )
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            grs_keyword="todo",
            grs_replacement_text="done",
            grs_grep_results=(
                GrepSearchResultState(
                    path="/home/tadashi/develop/zivo/a.py",
                    display_path="a.py",
                    line_number=1,
                    line_text="todo item",
                ),
            ),
            grs_preview_results=(
                ReplacePreviewResultState(
                    path="/home/tadashi/develop/zivo/a.py",
                    display_path="a.py",
                    diff_text="- todo + done",
                    match_count=1,
                    first_match_line_number=1,
                    first_match_before="todo",
                    first_match_after="done",
                ),
            ),
            grs_total_match_count=1,
        ),
    )
    result = reduce_app_state(state, SubmitCommandPalette())

    effects = [e for e in result.effects if isinstance(e, RunTextReplaceApplyEffect)]
    assert len(effects) == 1
    assert effects[0].request.paths == ("/home/tadashi/develop/zivo/a.py",)
    assert effects[0].request.find_text == "todo"
    assert effects[0].request.replace_text == "done"
    assert result.state.command_palette is None


def test_submit_grs_palette_warns_when_no_keyword() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginGrepReplaceSelected(target_paths=("/home/tadashi/develop/zivo/a.py",)),
    )
    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.notification is not None
    assert result.state.notification.level == "warning"


def test_submit_grs_palette_warns_when_no_preview_results() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginGrepReplaceSelected(target_paths=("/home/tadashi/develop/zivo/a.py",)),
    )
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            grs_keyword="todo",
            grs_replacement_text="done",
            grs_grep_results=(
                GrepSearchResultState(
                    path="/home/tadashi/develop/zivo/a.py",
                    display_path="a.py",
                    line_number=1,
                    line_text="todo item",
                ),
            ),
        ),
    )
    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.notification is not None
    assert result.state.notification.level == "warning"


def test_cancel_grs_returns_to_browsing() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginGrepReplaceSelected(target_paths=("/home/tadashi/develop/zivo/a.py",)),
    )
    assert state.ui_mode == "PALETTE"

    state = _reduce_state(state, CancelCommandPalette())
    assert state.ui_mode == "BROWSING"
    assert state.command_palette is None


def test_grs_grep_search_completed_filters_non_target_results() -> None:
    """Verify that grep results not in target_paths are excluded."""
    state = _reduce_state(
        build_initial_app_state(),
        BeginGrepReplaceSelected(target_paths=("/home/tadashi/develop/zivo/a.py",)),
    )
    state = replace(
        state,
        command_palette=replace(state.command_palette, grs_keyword="todo"),
        pending_grep_search_request_id=10,
        next_request_id=11,
    )
    all_results = (
        GrepSearchResultState(
            path="/home/tadashi/develop/zivo/a.py",
            display_path="a.py",
            line_number=1,
            line_text="todo in a",
        ),
        GrepSearchResultState(
            path="/home/tadashi/develop/zivo/b.py",
            display_path="b.py",
            line_number=3,
            line_text="todo in b",
        ),
    )
    result = reduce_app_state(
        state, GrepSearchCompleted(request_id=10, query="todo", results=all_results)
    )

    assert len(result.state.command_palette.grs_grep_results) == 1
    assert result.state.command_palette.grs_grep_results[0].path == "/home/tadashi/develop/zivo/a.py"
    # Preview is triggered even with empty replace text to show find matches
    assert result.state.pending_replace_preview_request_id is not None
