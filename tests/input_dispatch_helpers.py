# ruff: noqa: F401

from dataclasses import replace

import zivo.state.input as input_module
from zivo.models import AppConfig, BookmarkConfig, CreateZipArchiveRequest
from zivo.state import (
    ActivateNextTab,
    ActivatePreviousTab,
    AddBookmark,
    BeginBookmarkSearch,
    BeginCommandPalette,
    BeginCreateInput,
    BeginDeleteTargets,
    BeginFileSearch,
    BeginFilterInput,
    BeginGoToPath,
    BeginGrepSearch,
    BeginHistorySearch,
    BeginRenameInput,
    CancelCommandPalette,
    CancelDeleteConfirmation,
    CancelFilterInput,
    CancelPasteConflict,
    CancelPendingInput,
    CancelZipCompressConfirmation,
    ClearPendingKeySequence,
    ClearSelection,
    CloseCurrentTab,
    CommandPaletteState,
    ConfigEditorState,
    ConfirmDeleteTargets,
    ConfirmFilterInput,
    ConfirmZipCompress,
    CopyPathsToClipboard,
    CopyTargets,
    CutTargets,
    CycleConfigEditorValue,
    CycleFindReplaceField,
    CycleGrepSearchField,
    DeleteConfirmationState,
    DismissAttributeDialog,
    DismissConfigEditor,
    DismissNameConflict,
    EnterCursorDirectory,
    ExitCurrentPath,
    GoBack,
    GoForward,
    GoToHomeDirectory,
    GoToParentDirectory,
    MoveCommandPaletteCursor,
    MoveConfigEditorCursor,
    MoveCursor,
    MoveCursorAndSelectRange,
    MovePendingInputCursor,
    NameConflictState,
    NotificationState,
    OpenFindResultInEditor,
    OpenGrepResultInEditor,
    OpenNewTab,
    OpenPathInEditor,
    OpenPathWithDefaultApp,
    PasteClipboard,
    PendingInputState,
    PendingKeySequenceState,
    ReloadDirectory,
    RemoveBookmark,
    ResolvePasteConflict,
    SaveConfigEditor,
    SelectAllVisibleEntries,
    SendSplitTerminalInput,
    SetCommandPaletteQuery,
    SetFilterQuery,
    SetFindReplaceField,
    SetGrepSearchField,
    SetNotification,
    SetPendingInputValue,
    SetPendingKeySequence,
    SetSort,
    ShowAttributes,
    SubmitCommandPalette,
    SubmitPendingInput,
    ToggleHiddenFiles,
    ToggleSelectionAndAdvance,
    ToggleSplitTerminal,
    UndoLastOperation,
    ZipCompressConfirmationState,
    build_initial_app_state,
    dispatch_key_input,
    iter_bound_keys,
)


def _focused_split_terminal_state():
    state = build_initial_app_state()
    return replace(
        state,
        split_terminal=replace(
            state.split_terminal,
            visible=True,
            status="running",
            focus_target="terminal",
        ),
    )


def _reduce_go_to_path_state(
    *,
    query: str,
    candidates: tuple[str, ...],
    current_path: str,
    cursor_index: int = 0,
):
    state = replace(
        build_initial_app_state(),
        current_path=current_path,
    )
    state = replace(
        state,
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="go_to_path",
            query=query,
            cursor_index=cursor_index,
            go_to_path_candidates=candidates,
        ),
    )
    return state


__all__ = [name for name in globals() if not name.startswith("__")]
