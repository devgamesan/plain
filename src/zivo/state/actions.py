"""Reducer actions for app state transitions."""

from .actions_input import (
    ApplyBulkRename,
    BeginBulkRename,
    BeginChmodInput,
    BeginChownInput,
    BeginConfigEditor,
    BeginCreateInput,
    BeginExtractArchiveInput,
    BeginFilterInput,
    BeginRenameInput,
    BeginShellCommandInput,
    BeginSymlinkInput,
    BeginZipCompressInput,
    CancelBulkRename,
    CancelFilterInput,
    CancelPendingInput,
    CancelShellCommandInput,
    ConfirmFilterInput,
    CycleConfigEditorValue,
    CycleCreateKind,
    DeletePendingInputForward,
    DismissAboutDialog,
    DismissAttributeDialog,
    DismissConfigEditor,
    DismissNameConflict,
    MoveConfigEditorCursor,
    MovePendingInputCursor,
    MoveShellCommandCursor,
    PasteIntoBulkRenameBaseName,
    PasteIntoPendingInput,
    PasteIntoShellCommand,
    SaveConfigEditor,
    SetBulkRenameBaseName,
    SetFilterQuery,
    SetPendingInputCursor,
    SetPendingInputValue,
    SetShellCommandCursor,
    SetShellCommandValue,
    SubmitPendingInput,
    SubmitShellCommand,
    TogglePendingInputRecursive,
)
from .actions_mutations import (
    AdvancePermanentDeleteConfirmation,
    BeginCustomActionConfirmation,
    BeginDeleteTargets,
    BeginExitCurrentPath,
    CancelArchiveExtractConfirmation,
    CancelCustomActionConfirmation,
    CancelDeleteConfirmation,
    CancelExitConfirmation,
    CancelForegroundOperation,
    CancelPasteConflict,
    CancelReplaceConfirmation,
    CancelSymlinkOverwriteConfirmation,
    CancelZipCompressConfirmation,
    ClearSelection,
    ConfirmArchiveExtract,
    ConfirmCustomAction,
    ConfirmDeleteTargets,
    ConfirmExitCurrentPath,
    ConfirmReplaceTargets,
    ConfirmSymlinkOverwrite,
    ConfirmZipCompress,
    CopyTargets,
    CutTargets,
    DuplicateTargets,
    ForegroundOperationAborted,
    PasteClipboard,
    ResolvePasteConflict,
    SelectAllVisibleEntries,
    ToggleSelection,
    ToggleSelectionAndAdvance,
    UndoLastOperation,
)

__all__ = [
    # Input actions
    "BeginChmodInput",
    "BeginChownInput",
    "BeginCreateInput",
    "CycleCreateKind",
    "BeginConfigEditor",
    "BeginExtractArchiveInput",
    "BeginFilterInput",
    "BeginRenameInput",
    "BeginBulkRename",
    "ApplyBulkRename",
    "CancelBulkRename",
    "BeginShellCommandInput",
    "BeginSymlinkInput",
    "BeginZipCompressInput",
    "CancelFilterInput",
    "CancelPendingInput",
    "CancelShellCommandInput",
    "ConfirmFilterInput",
    "CycleConfigEditorValue",
    "DeletePendingInputForward",
    "DismissAboutDialog",
    "DismissAttributeDialog",
    "DismissConfigEditor",
    "DismissNameConflict",
    "MoveConfigEditorCursor",
    "MovePendingInputCursor",
    "MoveShellCommandCursor",
    "PasteIntoPendingInput",
    "PasteIntoBulkRenameBaseName",
    "PasteIntoShellCommand",
    "SaveConfigEditor",
    "SetFilterQuery",
    "SetBulkRenameBaseName",
    "SetPendingInputCursor",
    "SetPendingInputValue",
    "TogglePendingInputRecursive",
    "SetShellCommandCursor",
    "SetShellCommandValue",
    "SubmitPendingInput",
    "SubmitShellCommand",
    # Mutation actions
    "AdvancePermanentDeleteConfirmation",
    "BeginDeleteTargets",
    "BeginExitCurrentPath",
    "BeginCustomActionConfirmation",
    "CancelArchiveExtractConfirmation",
    "CancelCustomActionConfirmation",
    "CancelDeleteConfirmation",
    "CancelExitConfirmation",
    "CancelForegroundOperation",
    "ForegroundOperationAborted",
    "CancelPasteConflict",
    "CancelReplaceConfirmation",
    "CancelSymlinkOverwriteConfirmation",
    "CancelZipCompressConfirmation",
    "ClearSelection",
    "ConfirmArchiveExtract",
    "ConfirmCustomAction",
    "ConfirmDeleteTargets",
    "ConfirmExitCurrentPath",
    "ConfirmReplaceTargets",
    "ConfirmSymlinkOverwrite",
    "ConfirmZipCompress",
    "CopyTargets",
    "CutTargets",
    "DuplicateTargets",
    "PasteClipboard",
    "ResolvePasteConflict",
    "SelectAllVisibleEntries",
    "ToggleSelection",
    "ToggleSelectionAndAdvance",
    "UndoLastOperation",
]

from .actions_navigation import (
    ActivateNextTab,
    ActivatePreviousTab,
    ActivateTabByIndex,
    AddBookmark,
    ClearTransferSelection,
    CloseCurrentTab,
    CloseTabByIndex,
    CopyPathsToClipboard,
    EnterCursorDirectory,
    EnterTransferDirectory,
    ExitCurrentPath,
    FocusTransferPane,
    GoBack,
    GoForward,
    GoToHomeDirectory,
    GoToParentDirectory,
    GoToTransferHome,
    GoToTransferParent,
    JumpCursor,
    JumpTransferCursor,
    MoveCursor,
    MoveCursorAndSelectRange,
    MoveCursorByPage,
    MoveTransferCursor,
    MoveTransferCursorAndSelectRange,
    MoveTransferCursorByPage,
    NavigateTransferToPath,
    OpenNewTab,
    OpenPathInEditor,
    OpenPathInGuiEditor,
    OpenPathWithDefaultApp,
    OpenTerminalAtPath,
    PasteClipboardToTransferPane,
    ReloadDirectory,
    RemoveBookmark,
    SelectAllVisibleTransferEntries,
    SetCursorPath,
    SetSort,
    SetTransferCursorPath,
    ShowAbout,
    ShowAttributes,
    ToggleHiddenFiles,
    ToggleTransferMode,
    ToggleTransferSelectionAndAdvance,
    TransferCopyToOppositePane,
    TransferMoveToOppositePane,
)
from .actions_palette import (
    BeginBookmarkSearch,
    BeginCommandPalette,
    BeginFileSearch,
    BeginFindAndReplace,
    BeginGo,
    BeginGoToPath,
    BeginGrepReplace,
    BeginGrepReplaceSelected,
    BeginGrepSearch,
    BeginHistorySearch,
    BeginTextReplace,
    CancelCommandPalette,
    CycleFileSearchField,
    CycleFindReplaceField,
    CycleGrepReplaceField,
    CycleGrepReplaceSelectedField,
    CycleGrepSearchField,
    CycleReplaceField,
    FileSearchCompleted,
    FileSearchFailed,
    FileSearchResultsUpdated,
    GrepExportCompleted,
    GrepExportFailed,
    GrepSearchCompleted,
    GrepSearchFailed,
    GrepSearchResultsUpdated,
    MoveCommandPaletteCursor,
    OpenFindResultInEditor,
    OpenFindResultInGuiEditor,
    OpenGrepResultInEditor,
    OpenGrepResultInGuiEditor,
    OpenSearchWorkspace,
    SaveGrepResults,
    SetCommandPaletteQuery,
    SetFileSearchTarget,
    SetFindReplaceField,
    SetGrepReplaceField,
    SetGrepReplaceSelectedField,
    SetGrepSearchField,
    SetGrepSearchScope,
    SetReplaceField,
    SetReplaceScope,
    SubmitCommandPalette,
    TextReplaceApplied,
    TextReplaceApplyFailed,
    TextReplacePreviewCompleted,
    TextReplacePreviewFailed,
)
from .actions_runtime import (
    ArchiveExtractCompleted,
    ArchiveExtractFailed,
    ArchiveExtractProgress,
    ArchivePreparationCompleted,
    ArchivePreparationFailed,
    AttributeInspectionFailed,
    AttributeInspectionLoaded,
    BrowserSnapshotFailed,
    BrowserSnapshotLoaded,
    BulkRenameCompleted,
    BulkRenameFailed,
    BulkRenameProgress,
    ChildPaneSnapshotFailed,
    ChildPaneSnapshotLoaded,
    ClipboardPasteCompleted,
    ClipboardPasteFailed,
    ClipboardPasteNeedsResolution,
    ConfigReloadCompleted,
    ConfigReloadFailed,
    ConfigSaveCompleted,
    ConfigSaveFailed,
    CurrentPaneSnapshotLoaded,
    CustomActionCompleted,
    CustomActionFailed,
    DeletePreparationCompleted,
    DeletePreparationFailed,
    DirectorySizesFailed,
    DirectorySizesLoaded,
    DuplicateCompleted,
    DuplicateFailed,
    DuplicateProgress,
    ExternalLaunchCompleted,
    ExternalLaunchFailed,
    FileMutationCompleted,
    FileMutationFailed,
    ForegroundOperationProgress,
    ParentChildSnapshotFailed,
    ParentChildSnapshotLoaded,
    RequestBrowserSnapshot,
    RequestDirectorySizes,
    ShellCommandCompleted,
    ShellCommandFailed,
    TransferPaneSnapshotFailed,
    TransferPaneSnapshotLoaded,
    UndoCompleted,
    UndoFailed,
    ZipCompressCompleted,
    ZipCompressFailed,
    ZipCompressPreparationCompleted,
    ZipCompressPreparationFailed,
    ZipCompressProgress,
)
from .actions_ui import (
    ActivateNotificationAction,
    ClearPendingKeySequence,
    DismissNotification,
    InitializeState,
    SetNotification,
    SetPendingKeySequence,
    SetTerminalHeight,
    SetTerminalSize,
    SetTerminalWidth,
    SetUiMode,
    ToggleNarrowPaneView,
)

Action = (
    InitializeState
    | SetUiMode
    | SetPendingKeySequence
    | ClearPendingKeySequence
    | SetNotification
    | ActivateNotificationAction
    | DismissNotification
    | SetTerminalHeight
    | SetTerminalSize
    | SetTerminalWidth
    | ToggleNarrowPaneView
    | BeginFileSearch
    | BeginGrepSearch
    | SaveGrepResults
    | GrepExportCompleted
    | GrepExportFailed
    | BeginHistorySearch
    | BeginBookmarkSearch
    | BeginGoToPath
    | BeginGo
    | BeginTextReplace
    | BeginFindAndReplace
    | BeginGrepReplace
    | BeginGrepReplaceSelected
    | CycleFileSearchField
    | SetFileSearchTarget
    | BeginCommandPalette
    | CancelCommandPalette
    | MoveCommandPaletteCursor
    | SetCommandPaletteQuery
    | SetGrepSearchField
    | SetGrepSearchScope
    | CycleGrepSearchField
    | SetReplaceField
    | SetReplaceScope
    | CycleReplaceField
    | SetFindReplaceField
    | CycleFindReplaceField
    | SetGrepReplaceField
    | CycleGrepReplaceField
    | SetGrepReplaceSelectedField
    | CycleGrepReplaceSelectedField
    | SubmitCommandPalette
    | FileSearchCompleted
    | FileSearchFailed
    | FileSearchResultsUpdated
    | GrepSearchCompleted
    | GrepSearchFailed
    | GrepSearchResultsUpdated
    | TextReplacePreviewCompleted
    | TextReplacePreviewFailed
    | TextReplaceApplied
    | TextReplaceApplyFailed
    | OpenGrepResultInEditor
    | OpenFindResultInEditor
    | OpenGrepResultInGuiEditor
    | OpenFindResultInGuiEditor
    | OpenSearchWorkspace
    | BeginFilterInput
    | ConfirmFilterInput
    | CancelFilterInput
    | BeginChmodInput
    | BeginChownInput
    | BeginBulkRename
    | BeginRenameInput
    | SetBulkRenameBaseName
    | PasteIntoBulkRenameBaseName
    | ApplyBulkRename
    | CancelBulkRename
    | BeginCreateInput
    | CycleCreateKind
    | BeginConfigEditor
    | BeginSymlinkInput
    | BeginExtractArchiveInput
    | BeginZipCompressInput
    | BeginShellCommandInput
    | DismissConfigEditor
    | MoveConfigEditorCursor
    | CycleConfigEditorValue
    | SaveConfigEditor
    | SetPendingInputValue
    | TogglePendingInputRecursive
    | MovePendingInputCursor
    | SetPendingInputCursor
    | DeletePendingInputForward
    | MoveShellCommandCursor
    | SetShellCommandCursor
    | SetShellCommandValue
    | SubmitPendingInput
    | CancelPendingInput
    | SubmitShellCommand
    | CancelShellCommandInput
    | DismissNameConflict
    | DismissAboutDialog
    | DismissAttributeDialog
    | SetFilterQuery
    | PasteIntoPendingInput
    | PasteIntoShellCommand
    | OpenNewTab
    | ActivateTabByIndex
    | ActivateNextTab
    | ActivatePreviousTab
    | CloseCurrentTab
    | CloseTabByIndex
    | MoveCursor
    | JumpCursor
    | MoveCursorByPage
    | MoveCursorAndSelectRange
    | SetCursorPath
    | EnterCursorDirectory
    | GoToParentDirectory
    | GoToHomeDirectory
    | ReloadDirectory
    | GoBack
    | GoForward
    | ExitCurrentPath
    | OpenPathWithDefaultApp
    | OpenPathInEditor
    | OpenPathInGuiEditor
    | OpenTerminalAtPath
    | ShowAbout
    | ShowAttributes
    | CopyPathsToClipboard
    | AddBookmark
    | RemoveBookmark
    | ToggleHiddenFiles
    | SetSort
    | ToggleTransferMode
    | FocusTransferPane
    | MoveTransferCursor
    | JumpTransferCursor
    | MoveTransferCursorByPage
    | SetTransferCursorPath
    | MoveTransferCursorAndSelectRange
    | ToggleTransferSelectionAndAdvance
    | ClearTransferSelection
    | SelectAllVisibleTransferEntries
    | EnterTransferDirectory
    | GoToTransferParent
    | GoToTransferHome
    | NavigateTransferToPath
    | TransferCopyToOppositePane
    | TransferMoveToOppositePane
    | PasteClipboardToTransferPane
    | BeginDeleteTargets
    | AdvancePermanentDeleteConfirmation
    | BeginCustomActionConfirmation
    | ToggleSelection
    | ToggleSelectionAndAdvance
    | ClearSelection
    | SelectAllVisibleEntries
    | CopyTargets
    | CutTargets
    | DuplicateTargets
    | PasteClipboard
    | UndoLastOperation
    | ResolvePasteConflict
    | CancelPasteConflict
    | CancelForegroundOperation
    | ForegroundOperationAborted
    | ConfirmDeleteTargets
    | CancelDeleteConfirmation
    | BeginExitCurrentPath
    | ConfirmExitCurrentPath
    | CancelExitConfirmation
    | ConfirmArchiveExtract
    | ConfirmCustomAction
    | CancelArchiveExtractConfirmation
    | CancelCustomActionConfirmation
    | ConfirmZipCompress
    | CancelZipCompressConfirmation
    | ConfirmSymlinkOverwrite
    | CancelSymlinkOverwriteConfirmation
    | RequestBrowserSnapshot
    | RequestDirectorySizes
    | AttributeInspectionLoaded
    | AttributeInspectionFailed
    | BrowserSnapshotLoaded
    | BrowserSnapshotFailed
    | ChildPaneSnapshotLoaded
    | ChildPaneSnapshotFailed
    | CurrentPaneSnapshotLoaded
    | ParentChildSnapshotLoaded
    | ParentChildSnapshotFailed
    | TransferPaneSnapshotLoaded
    | TransferPaneSnapshotFailed
    | DirectorySizesLoaded
    | DirectorySizesFailed
    | DeletePreparationCompleted
    | DeletePreparationFailed
    | ClipboardPasteNeedsResolution
    | ClipboardPasteCompleted
    | ClipboardPasteFailed
    | ForegroundOperationProgress
    | DuplicateProgress
    | DuplicateCompleted
    | DuplicateFailed
    | BulkRenameProgress
    | BulkRenameCompleted
    | BulkRenameFailed
    | ArchivePreparationCompleted
    | ArchivePreparationFailed
    | ArchiveExtractProgress
    | ArchiveExtractCompleted
    | ArchiveExtractFailed
    | ZipCompressPreparationCompleted
    | ZipCompressPreparationFailed
    | ZipCompressProgress
    | ZipCompressCompleted
    | ZipCompressFailed
    | FileMutationCompleted
    | FileMutationFailed
    | UndoCompleted
    | UndoFailed
    | ExternalLaunchCompleted
    | ExternalLaunchFailed
    | ShellCommandCompleted
    | ShellCommandFailed
    | ConfigSaveCompleted
    | ConfigSaveFailed
    | ConfigReloadCompleted
    | ConfigReloadFailed
    | CustomActionCompleted
    | CustomActionFailed
)
