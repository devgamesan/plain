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
    BeginEmptyTrash,
    CancelArchiveExtractConfirmation,
    CancelCustomActionConfirmation,
    CancelDeleteConfirmation,
    CancelEmptyTrashConfirmation,
    CancelPasteConflict,
    CancelReplaceConfirmation,
    CancelSymlinkOverwriteConfirmation,
    CancelZipCompressConfirmation,
    ClearSelection,
    ConfirmArchiveExtract,
    ConfirmCustomAction,
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
    "BeginEmptyTrash",
    "BeginCustomActionConfirmation",
    "CancelArchiveExtractConfirmation",
    "CancelCustomActionConfirmation",
    "CancelDeleteConfirmation",
    "CancelEmptyTrashConfirmation",
    "CancelPasteConflict",
    "CancelReplaceConfirmation",
    "CancelSymlinkOverwriteConfirmation",
    "CancelZipCompressConfirmation",
    "ClearSelection",
    "ConfirmArchiveExtract",
    "ConfirmCustomAction",
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
    OpenFileSearchWorkspace,
    OpenFindResultInEditor,
    OpenFindResultInGuiEditor,
    OpenGrepResultInEditor,
    OpenGrepResultInGuiEditor,
    OpenGrepSearchWorkspace,
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
    | OpenFileSearchWorkspace
    | OpenGrepResultInGuiEditor
    | OpenFindResultInGuiEditor
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
    | MoveShellCommandCursor
    | SetShellCommandCursor
    | SetShellCommandValue
    | SubmitPendingInput
    | CancelPendingInput
    | SubmitShellCommand
    | CancelShellCommandInput
    | DismissNameConflict
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
    | OpenGrepSearchWorkspace
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
    | BeginEmptyTrash
    | ConfirmEmptyTrash
    | CancelEmptyTrashConfirmation
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
