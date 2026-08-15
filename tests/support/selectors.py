"""Shared setup for selector tests."""

# ruff: noqa: F401

import os
from dataclasses import replace
from stat import S_IFREG

import pytest

import zivo.state.selectors as selectors_module
from tests.support.state import entry, pane, reduce_state
from zivo.models import (
    ActionsConfig,
    AppConfig,
    BookmarkConfig,
    CreateZipArchiveRequest,
    CustomActionConfig,
    DisplayConfig,
    EditorConfig,
    ExtractArchiveRequest,
    GuiEditorConfig,
    PasteConflict,
    PasteRequest,
    StatusBarActionState,
    UndoDeletePathStep,
    UndoEntry,
)
from zivo.state import (
    ArchiveExtractConfirmationState,
    AttributeInspectionState,
    CommandPaletteState,
    ConfigEditorState,
    CurrentPaneDeltaState,
    DeleteConfirmationState,
    DirectoryEntryState,
    DirectorySizeCacheEntry,
    DirectorySizeDeltaState,
    FileSearchPaletteState,
    FileSearchResultState,
    ForegroundOperationState,
    GrepSearchPaletteState,
    GrepSearchResultState,
    GrfPaletteState,
    GrsPaletteState,
    HistoryState,
    NameConflictState,
    NotificationState,
    PaneState,
    PasteConflictState,
    PendingInputState,
    PendingKeySequenceState,
    PreviewMetadataState,
    ReplacePreviewPaletteState,
    ReplacePreviewResultState,
    RffPaletteState,
    ZipCompressConfirmationState,
    build_initial_app_state,
    build_placeholder_app_state,
    select_attribute_dialog_state,
    select_child_entries,
    select_command_palette_state,
    select_config_dialog_state,
    select_conflict_dialog_state,
    select_current_entries,
    select_current_summary_state,
    select_help_bar_state,
    select_input_bar_state,
    select_parent_entries,
    select_responsive_pane_layout,
    select_shell_data,
    select_status_bar_state,
    select_tab_bar_state,
    select_target_paths,
    select_visible_current_entry_states,
)
from zivo.state import command_palette as command_palette_module
from zivo.state.actions import (
    BeginCommandPalette,
    BeginCreateInput,
    BeginFilterInput,
    ConfirmFilterInput,
    CutTargets,
    OpenNewTab,
    SetCursorPath,
    SetFilterQuery,
    SetNotification,
    SetSort,
    ToggleSelection,
    ToggleTransferMode,
)
from zivo.state.command_palette import CommandPaletteItem
from zivo.state.reducer_common import directory_size_target_paths
from zivo.state.selectors import (
    _has_execute_permission,
    _select_command_palette_window,
    compute_current_pane_visible_window,
    select_input_dialog_state,
)

SEARCH_WORKSPACE_PATH = (
    "search://readme?target=files&hidden=false&root=%2Fhome%2Ftadashi%2Fdevelop%2Fzivo"
)


def build_search_workspace_state():
    result_path = "/home/tadashi/develop/zivo/README.md"
    state = build_initial_app_state()
    return replace(
        state,
        current_path=SEARCH_WORKSPACE_PATH,
        current_pane=pane(
            SEARCH_WORKSPACE_PATH,
            (entry(result_path, "file"),),
            cursor_path=result_path,
        ),
    )


def _reduce_state(state, action):
    return reduce_state(state, action)


def _display_path_for_test(path: str) -> str:
    return command_palette_module._display_path(path)


