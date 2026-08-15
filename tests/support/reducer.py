"""Shared setup for reducer tests."""

# Test support re-exports the state and action types used by split modules.
# ruff: noqa: F401

from dataclasses import replace
from datetime import datetime
from pathlib import Path

from tests.support.state import reduce_state
from zivo.models import (
    AppConfig,
    BookmarkConfig,
    ConfigLoadResult,
    ExternalLaunchRequest,
    GuiEditorConfig,
)
from zivo.state import (
    BrowserSnapshot,
    ConfigEditorState,
    CurrentPaneDeltaState,
    DirectoryEntryState,
    DirectorySizeCacheEntry,
    DirectorySizeDeltaState,
    FilterState,
    ForegroundOperationState,
    HistoryState,
    LoadBrowserSnapshotEffect,
    LoadChildPaneSnapshotEffect,
    LoadCurrentPaneEffect,
    NameConflictState,
    NotificationState,
    PaneState,
    PendingInputState,
    PendingKeySequenceState,
    RunConfigReloadEffect,
    RunConfigSaveEffect,
    RunDirectorySizeEffect,
    RunExternalLaunchEffect,
    SortState,
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
    BrowserSnapshotFailed,
    BrowserSnapshotLoaded,
    CancelFilterInput,
    ChildPaneSnapshotFailed,
    ChildPaneSnapshotLoaded,
    ClearSelection,
    CloseCurrentTab,
    CloseTabByIndex,
    ConfigReloadCompleted,
    ConfigReloadFailed,
    ConfigSaveCompleted,
    ConfigSaveFailed,
    ConfirmFilterInput,
    CopyPathsToClipboard,
    CopyTextToClipboard,
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
    OpenPathInGuiEditor,
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
    SetTerminalSize,
    SetTerminalWidth,
    SetUiMode,
    ToggleHiddenFiles,
    ToggleNarrowPaneView,
    ToggleSelection,
)
from zivo.state.models import DIRECTORY_HISTORY_LIMIT
from zivo.state.reducer_requests import build_history_after_snapshot_load
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

