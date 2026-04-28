"""Reducer actions for app state transitions."""

from .actions_input import (
    BeginCreateInput,
    BeginExtractArchiveInput,
    BeginFilterInput,
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
    DismissAttributeDialog,
    DismissConfigEditor,
    DismissNameConflict,
    MoveConfigEditorCursor,
    MovePendingInputCursor,
    PasteIntoPendingInput,
    ResetHelpBarConfig,
    SaveConfigEditor,
    SetFilterQuery,
    SetPendingInputCursor,
    SetPendingInputValue,
    SetShellCommandValue,
    SubmitPendingInput,
    SubmitShellCommand,
)
from .actions_mutations import (
    BeginDeleteTargets,
    BeginEmptyTrash,
    CancelArchiveExtractConfirmation,
    CancelDeleteConfirmation,
    CancelEmptyTrashConfirmation,
    CancelPasteConflict,
    CancelReplaceConfirmation,
    CancelSymlinkOverwriteConfirmation,
    CancelZipCompressConfirmation,
    ClearSelection,
    ConfirmArchiveExtract,
    ConfirmDeleteTargets,
    ConfirmEmptyTrash,
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
    "BeginCreateInput",
    "BeginExtractArchiveInput",
    "BeginFilterInput",
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
    "DismissAttributeDialog",
    "DismissConfigEditor",
    "DismissNameConflict",
    "MoveConfigEditorCursor",
    "MovePendingInputCursor",
    "PasteIntoPendingInput",
    "ResetHelpBarConfig",
    "SaveConfigEditor",
    "SetFilterQuery",
    "SetPendingInputCursor",
    "SetPendingInputValue",
    "SetShellCommandValue",
    "SubmitPendingInput",
    "SubmitShellCommand",
    # Mutation actions
    "BeginDeleteTargets",
    "BeginEmptyTrash",
    "CancelArchiveExtractConfirmation",
    "CancelDeleteConfirmation",
    "CancelEmptyTrashConfirmation",
    "CancelPasteConflict",
    "CancelReplaceConfirmation",
    "CancelSymlinkOverwriteConfirmation",
    "CancelZipCompressConfirmation",
    "ClearSelection",
    "ConfirmArchiveExtract",
    "ConfirmDeleteTargets",
    "ConfirmEmptyTrash",
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
    OpenNewTab,
    OpenPathInEditor,
    OpenPathWithDefaultApp,
    OpenTerminalAtPath,
    PasteClipboardToTransferPane,
    ReloadDirectory,
    RemoveBookmark,
    SelectAllVisibleTransferEntries,
    SetCursorPath,
    SetSort,
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
    BeginGrepReplace,
    BeginGrepReplaceSelected,
    BeginGrepSearch,
    BeginHistorySearch,
    BeginSelectedFilesGrep,
    BeginTextReplace,
    CancelCommandPalette,
    CycleFindReplaceField,
    CycleGrepReplaceField,
    CycleGrepReplaceSelectedField,
    CycleGrepSearchField,
    CycleReplaceField,
    CycleSelectedFilesGrepField,
    FileSearchCompleted,
    FileSearchFailed,
    GrepSearchCompleted,
    GrepSearchFailed,
    MoveCommandPaletteCursor,
    OpenFindResultInEditor,
    OpenGrepResultInEditor,
    SelectedFilesGrepKeywordChanged,
    SetCommandPaletteQuery,
    SetFindReplaceField,
    SetGrepReplaceField,
    SetGrepReplaceSelectedField,
    SetGrepSearchField,
    SetReplaceField,
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
    ChildPaneSnapshotFailed,
    ChildPaneSnapshotLoaded,
    ClipboardPasteCompleted,
    ClipboardPasteFailed,
    ClipboardPasteNeedsResolution,
    ConfigSaveCompleted,
    ConfigSaveFailed,
    CurrentPaneSnapshotLoaded,
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
    | BeginHistorySearch
    | BeginBookmarkSearch
    | BeginGoToPath
    | BeginTextReplace
    | BeginFindAndReplace
    | BeginGrepReplace
    | BeginGrepReplaceSelected
    | BeginSelectedFilesGrep
    | SelectedFilesGrepKeywordChanged
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
    | BeginFilterInput
    | ConfirmFilterInput
    | CancelFilterInput
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
    | SetShellCommandValue
    | SubmitPendingInput
    | CancelPendingInput
    | SubmitShellCommand
    | CancelShellCommandInput
    | DismissNameConflict
    | DismissAttributeDialog
    | SetFilterQuery
    | PasteIntoPendingInput
    | OpenNewTab
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
    | OpenTerminalAtPath
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
    | MoveTransferCursorAndSelectRange
    | ToggleTransferSelectionAndAdvance
    | ClearTransferSelection
    | SelectAllVisibleTransferEntries
    | EnterTransferDirectory
    | GoToTransferParent
    | GoToTransferHome
    | TransferCopyToOppositePane
    | TransferMoveToOppositePane
    | PasteClipboardToTransferPane
    | BeginDeleteTargets
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
    | BeginEmptyTrash
    | ConfirmEmptyTrash
    | CancelEmptyTrashConfirmation
    | ConfirmArchiveExtract
    | CancelArchiveExtractConfirmation
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
)
