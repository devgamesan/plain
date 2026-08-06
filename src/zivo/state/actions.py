"""Reducer actions for app state transitions."""

from .actions_input import (
    BeginChmodInput,
    BeginChownInput,
    BeginCreateInput,
    BeginExtractArchiveInput,
    BeginFilterInput,
    BeginRecursiveChmodInput,
    BeginRecursiveChownInput,
    BeginRenameInput,
    BeginShellCommandInput,
    BeginSymlinkInput,
    BeginZipCompressInput,
    CancelFilterInput,
    CancelPendingInput,
    CancelShellCommandInput,
    ConfirmFilterInput,
    CycleConfigEditorValue,
    DeletePendingInputForward,
    DismissAboutDialog,
    DismissAttributeDialog,
    DismissConfigEditor,
    DismissNameConflict,
    MoveConfigEditorCursor,
    MovePendingInputCursor,
    MoveShellCommandCursor,
    PasteIntoPendingInput,
    PasteIntoShellCommand,
    ResetHelpBarConfig,
    SaveConfigEditor,
    SetFilterQuery,
    SetPendingInputCursor,
    SetPendingInputValue,
    SetShellCommandCursor,
    SetShellCommandValue,
    SubmitPendingInput,
    SubmitShellCommand,
)
from .actions_mutations import (
    BeginCustomActionConfirmation,
    BeginDeleteTargets,
    BeginExitCurrentPath,
    CancelArchiveExtractConfirmation,
    CancelCustomActionConfirmation,
    CancelDeleteConfirmation,
    CancelExitConfirmation,
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
    "BeginExtractArchiveInput",
    "BeginFilterInput",
    "BeginRecursiveChmodInput",
    "BeginRecursiveChownInput",
    "BeginRenameInput",
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
    "PasteIntoShellCommand",
    "ResetHelpBarConfig",
    "SaveConfigEditor",
    "SetFilterQuery",
    "SetPendingInputCursor",
    "SetPendingInputValue",
    "SetShellCommandCursor",
    "SetShellCommandValue",
    "SubmitPendingInput",
    "SubmitShellCommand",
    # Mutation actions
    "BeginDeleteTargets",
    "BeginExitCurrentPath",
    "BeginCustomActionConfirmation",
    "CancelArchiveExtractConfirmation",
    "CancelCustomActionConfirmation",
    "CancelDeleteConfirmation",
    "CancelExitConfirmation",
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
    BeginGoToPath,
    BeginGrepExport,
    BeginGrepReplace,
    BeginGrepReplaceSelected,
    BeginGrepSearch,
    BeginHistorySearch,
    BeginSelectedFilesGrep,
    BeginTextReplace,
    CancelCommandPalette,
    CancelGrepExport,
    CycleFileSearchField,
    CycleFindReplaceField,
    CycleGrepReplaceField,
    CycleGrepReplaceSelectedField,
    CycleGrepSearchField,
    CycleReplaceField,
    CycleSelectedFilesGrepField,
    FileSearchCompleted,
    FileSearchFailed,
    GrepExportCompleted,
    GrepExportFailed,
    GrepSearchCompleted,
    GrepSearchFailed,
    MoveCommandPaletteCursor,
    OpenFindResultInEditor,
    OpenFindResultInGuiEditor,
    OpenGrepResultInEditor,
    OpenGrepResultInGuiEditor,
    OpenSearchWorkspace,
    SelectedFilesGrepKeywordChanged,
    SetCommandPaletteQuery,
    SetFileSearchTarget,
    SetFindReplaceField,
    SetGrepExportFilename,
    SetGrepExportFormat,
    SetGrepReplaceField,
    SetGrepReplaceSelectedField,
    SetGrepSearchField,
    SetReplaceField,
    SubmitCommandPalette,
    SubmitGrepExport,
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
    ChildPaneSnapshotFailed,
    ChildPaneSnapshotLoaded,
    ClipboardPasteCompleted,
    ClipboardPasteFailed,
    ClipboardPasteNeedsResolution,
    ConfigSaveCompleted,
    ConfigSaveFailed,
    CurrentPaneSnapshotLoaded,
    CustomActionCompleted,
    CustomActionFailed,
    DirectorySizesFailed,
    DirectorySizesLoaded,
    ExternalLaunchCompleted,
    ExternalLaunchFailed,
    FileMutationCompleted,
    FileMutationFailed,
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
    ClearPendingKeySequence,
    InitializeState,
    SetNotification,
    SetPendingKeySequence,
    SetTerminalHeight,
    SetUiMode,
)

Action = (
    InitializeState
    | SetUiMode
    | SetPendingKeySequence
    | ClearPendingKeySequence
    | SetNotification
    | SetTerminalHeight
    | BeginFileSearch
    | BeginGrepSearch
    | BeginGrepExport
    | CancelGrepExport
    | SetGrepExportFormat
    | SetGrepExportFilename
    | SubmitGrepExport
    | GrepExportCompleted
    | GrepExportFailed
    | BeginHistorySearch
    | BeginBookmarkSearch
    | BeginGoToPath
    | BeginTextReplace
    | BeginFindAndReplace
    | BeginGrepReplace
    | BeginGrepReplaceSelected
    | BeginSelectedFilesGrep
    | SelectedFilesGrepKeywordChanged
    | CycleFileSearchField
    | SetFileSearchTarget
    | CycleSelectedFilesGrepField
    | BeginCommandPalette
    | CancelCommandPalette
    | MoveCommandPaletteCursor
    | SetCommandPaletteQuery
    | SetGrepSearchField
    | CycleGrepSearchField
    | SetReplaceField
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
    | GrepSearchCompleted
    | GrepSearchFailed
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
    | BeginRecursiveChmodInput
    | BeginChownInput
    | BeginRecursiveChownInput
    | BeginRenameInput
    | BeginCreateInput
    | BeginSymlinkInput
    | BeginExtractArchiveInput
    | BeginZipCompressInput
    | BeginShellCommandInput
    | DismissConfigEditor
    | MoveConfigEditorCursor
    | CycleConfigEditorValue
    | SaveConfigEditor
    | ResetHelpBarConfig
    | SetPendingInputValue
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
    | BeginCustomActionConfirmation
    | ToggleSelection
    | ToggleSelectionAndAdvance
    | ClearSelection
    | SelectAllVisibleEntries
    | CopyTargets
    | CutTargets
    | PasteClipboard
    | UndoLastOperation
    | ResolvePasteConflict
    | CancelPasteConflict
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
    | ClipboardPasteNeedsResolution
    | ClipboardPasteCompleted
    | ClipboardPasteFailed
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
    | CustomActionCompleted
    | CustomActionFailed
)
