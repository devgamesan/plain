"""Runtime action mapping for worker completion and failure."""

from collections.abc import Callable
from typing import Any

from zivo.app_runtime_core import CompleteActionHandler, FailureActionHandler, find_handler
from zivo.models import (
    CreateZipArchivePreparationResult,
    CreateZipArchiveResult,
    ExtractArchivePreparationResult,
    ExtractArchiveResult,
    FileMutationResult,
    PasteConflictPrompt,
    PasteExecutionResult,
    ShellCommandResult,
    TextReplacePreviewResult,
    TextReplaceResult,
    UndoResult,
)
from zivo.services import (
    InvalidFileSearchQueryError,
    InvalidGrepSearchQueryError,
    InvalidTextReplaceQueryError,
)
from zivo.state import (
    Effect,
    LoadBrowserSnapshotEffect,
    LoadChildPaneSnapshotEffect,
    LoadCurrentPaneEffect,
    LoadParentChildEffect,
    RunArchiveExtractEffect,
    RunArchivePreparationEffect,
    RunAttributeInspectionEffect,
    RunClipboardPasteEffect,
    RunConfigSaveEffect,
    RunDirectorySizeEffect,
    RunExternalLaunchEffect,
    RunFileMutationEffect,
    RunFileSearchEffect,
    RunGrepSearchEffect,
    RunShellCommandEffect,
    RunTextReplaceApplyEffect,
    RunTextReplacePreviewEffect,
    RunUndoEffect,
    RunZipCompressEffect,
    RunZipCompressPreparationEffect,
)
from zivo.state.actions import (
    ArchiveExtractCompleted,
    ArchiveExtractFailed,
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
    FileSearchCompleted,
    FileSearchFailed,
    GrepSearchCompleted,
    GrepSearchFailed,
    ParentChildSnapshotFailed,
    ParentChildSnapshotLoaded,
    ShellCommandCompleted,
    ShellCommandFailed,
    TextReplaceApplied,
    TextReplaceApplyFailed,
    TextReplacePreviewCompleted,
    TextReplacePreviewFailed,
    UndoCompleted,
    UndoFailed,
    ZipCompressCompleted,
    ZipCompressFailed,
    ZipCompressPreparationCompleted,
    ZipCompressPreparationFailed,
)


def complete_browser_snapshot(
    effect: LoadBrowserSnapshotEffect,
    result: object,
) -> tuple[Any, ...]:
    return (
        BrowserSnapshotLoaded(
            request_id=effect.request_id,
            snapshot=result,
            blocking=effect.blocking,
        ),
    )


def complete_child_pane_snapshot(
    effect: LoadChildPaneSnapshotEffect,
    result: object,
) -> tuple[Any, ...]:
    return (
        ChildPaneSnapshotLoaded(
            request_id=effect.request_id,
            pane=result,
        ),
    )


def complete_current_pane_snapshot(
    effect: LoadCurrentPaneEffect,
    result: object,
) -> tuple[Any, ...]:
    current_path, current_pane, parent_pane = result
    return (
        CurrentPaneSnapshotLoaded(
            request_id=effect.request_id,
            current_path=current_path,
            current_pane=current_pane,
            parent_pane=parent_pane,
        ),
    )


def complete_parent_child_snapshot(
    effect: LoadParentChildEffect,
    result: object,
) -> tuple[Any, ...]:
    parent_pane, child_pane = result
    return (
        ParentChildSnapshotLoaded(
            request_id=effect.request_id,
            parent_pane=parent_pane,
            child_pane=child_pane,
        ),
    )


def complete_clipboard_paste_conflicts(
    effect: Effect,
    result: PasteConflictPrompt,
) -> tuple[Any, ...]:
    return (
        ClipboardPasteNeedsResolution(
            request_id=effect.request_id,
            request=result.request,
            conflicts=result.conflicts,
        ),
    )


def complete_clipboard_paste(
    effect: Effect,
    result: PasteExecutionResult,
) -> tuple[Any, ...]:
    return (
        ClipboardPasteCompleted(
            request_id=effect.request_id,
            summary=result.summary,
            applied_changes=result.applied_changes,
        ),
    )


def complete_file_mutation(effect: Effect, result: FileMutationResult) -> tuple[Any, ...]:
    return (
        FileMutationCompleted(
            request_id=effect.request_id,
            result=result,
        ),
    )


def complete_undo(effect: RunUndoEffect, result: UndoResult) -> tuple[Any, ...]:
    return (
        UndoCompleted(
            request_id=effect.request_id,
            entry=effect.entry,
            result=result,
        ),
    )


def complete_archive_preparation(
    effect: RunArchivePreparationEffect,
    result: ExtractArchivePreparationResult,
) -> tuple[Any, ...]:
    first_conflict_path = None
    if result.conflicts:
        first_conflict_path = result.conflicts[0].destination_path
    return (
        ArchivePreparationCompleted(
            request_id=effect.request_id,
            request=result.request,
            total_entries=result.total_entries,
            conflict_count=len(result.conflicts),
            first_conflict_path=first_conflict_path,
        ),
    )


def complete_archive_extract(
    effect: RunArchiveExtractEffect,
    result: ExtractArchiveResult,
) -> tuple[Any, ...]:
    return (
        ArchiveExtractCompleted(
            request_id=effect.request_id,
            result=result,
        ),
    )


def complete_zip_compress_preparation(
    effect: RunZipCompressPreparationEffect,
    result: CreateZipArchivePreparationResult,
) -> tuple[Any, ...]:
    return (
        ZipCompressPreparationCompleted(
            request_id=effect.request_id,
            request=result.request,
            total_entries=result.total_entries,
            destination_exists=result.destination_exists,
        ),
    )


def complete_zip_compress(
    effect: RunZipCompressEffect,
    result: CreateZipArchiveResult,
) -> tuple[Any, ...]:
    return (
        ZipCompressCompleted(
            request_id=effect.request_id,
            result=result,
        ),
    )


def complete_config_save(effect: RunConfigSaveEffect, result: object) -> tuple[Any, ...]:
    return (
        ConfigSaveCompleted(
            request_id=effect.request_id,
            path=result,
            config=effect.config,
        ),
    )


def complete_directory_sizes(
    effect: RunDirectorySizeEffect,
    result: object,
) -> tuple[Any, ...]:
    sizes, failures = result
    return (
        DirectorySizesLoaded(
            request_id=effect.request_id,
            sizes=sizes,
            failures=failures,
        ),
    )


def complete_attribute_inspection(
    effect: RunAttributeInspectionEffect,
    result: object,
) -> tuple[Any, ...]:
    return (
        AttributeInspectionLoaded(
            request_id=effect.request_id,
            inspection=result,
        ),
    )


def complete_external_launch(
    effect: RunExternalLaunchEffect,
    result: object,
) -> tuple[Any, ...]:
    return (
        ExternalLaunchCompleted(
            request_id=effect.request_id,
            request=effect.request,
        ),
    )


def complete_shell_command(
    effect: RunShellCommandEffect,
    result: ShellCommandResult,
) -> tuple[Any, ...]:
    return (
        ShellCommandCompleted(
            request_id=effect.request_id,
            result=result,
        ),
    )


def complete_file_search(effect: RunFileSearchEffect, result: object) -> tuple[Any, ...]:
    return (
        FileSearchCompleted(
            request_id=effect.request_id,
            query=effect.query,
            results=result,
        ),
    )


def complete_grep_search(effect: RunGrepSearchEffect, result: object) -> tuple[Any, ...]:
    return (
        GrepSearchCompleted(
            request_id=effect.request_id,
            query=effect.query,
            results=result,
        ),
    )


def complete_text_replace_preview(
    effect: RunTextReplacePreviewEffect,
    result: TextReplacePreviewResult,
) -> tuple[Any, ...]:
    return (
        TextReplacePreviewCompleted(
            request_id=effect.request_id,
            result=result,
        ),
    )


def complete_text_replace_apply(
    effect: RunTextReplaceApplyEffect,
    result: TextReplaceResult,
) -> tuple[Any, ...]:
    return (
        TextReplaceApplied(
            request_id=effect.request_id,
            result=result,
        ),
    )


ExtraFieldBuilder = Callable[[Effect, BaseException | None, str], Any]


def make_failed_handler(
    event_cls: type,
    *,
    extra_field_builders: dict[str, ExtraFieldBuilder] | None = None,
) -> FailureActionHandler:
    builders = extra_field_builders or {}

    def handler(effect: Effect, error: BaseException | None, message: str) -> tuple[Any, ...]:
        kwargs: dict[str, Any] = {"request_id": effect.request_id, "message": message}
        for name, builder in builders.items():
            kwargs[name] = builder(effect, error, message)
        return (event_cls(**kwargs),)

    return handler


failed_browser_snapshot = make_failed_handler(
    BrowserSnapshotFailed,
    extra_field_builders={"blocking": lambda e, _err, _msg: e.blocking},
)
failed_child_pane_snapshot = make_failed_handler(ChildPaneSnapshotFailed)
failed_current_pane_snapshot = make_failed_handler(CurrentPaneSnapshotLoaded)
failed_parent_child_snapshot = make_failed_handler(ParentChildSnapshotFailed)
failed_clipboard_paste = make_failed_handler(ClipboardPasteFailed)
failed_file_mutation = make_failed_handler(FileMutationFailed)
failed_archive_preparation = make_failed_handler(ArchivePreparationFailed)
failed_archive_extract = make_failed_handler(ArchiveExtractFailed)
failed_zip_compress_preparation = make_failed_handler(ZipCompressPreparationFailed)
failed_zip_compress = make_failed_handler(ZipCompressFailed)
failed_config_save = make_failed_handler(ConfigSaveFailed)
failed_directory_sizes = make_failed_handler(
    DirectorySizesFailed,
    extra_field_builders={"paths": lambda e, _err, _msg: e.paths},
)
failed_attribute_inspection = make_failed_handler(AttributeInspectionFailed)
failed_external_launch = make_failed_handler(
    ExternalLaunchFailed,
    extra_field_builders={"request": lambda e, _err, _msg: e.request},
)
failed_shell_command = make_failed_handler(ShellCommandFailed)
failed_undo = make_failed_handler(UndoFailed)
failed_file_search = make_failed_handler(
    FileSearchFailed,
    extra_field_builders={
        "query": lambda e, _err, _msg: e.query,
        "invalid_query": lambda _e, err, _msg: isinstance(err, InvalidFileSearchQueryError),
    },
)
failed_grep_search = make_failed_handler(
    GrepSearchFailed,
    extra_field_builders={
        "query": lambda e, _err, _msg: e.query,
        "invalid_query": lambda _e, err, _msg: isinstance(err, InvalidGrepSearchQueryError),
    },
)
failed_text_replace_preview = make_failed_handler(
    TextReplacePreviewFailed,
    extra_field_builders={
        "invalid_query": lambda _e, err, _msg: isinstance(err, InvalidTextReplaceQueryError),
    },
)
failed_text_replace_apply = make_failed_handler(TextReplaceApplyFailed)

RESULT_COMPLETE_HANDLERS: tuple[tuple[type[Any], CompleteActionHandler], ...] = (
    (PasteConflictPrompt, complete_clipboard_paste_conflicts),
    (PasteExecutionResult, complete_clipboard_paste),
    (ExtractArchivePreparationResult, complete_archive_preparation),
    (ExtractArchiveResult, complete_archive_extract),
    (CreateZipArchivePreparationResult, complete_zip_compress_preparation),
    (CreateZipArchiveResult, complete_zip_compress),
    (FileMutationResult, complete_file_mutation),
    (UndoResult, complete_undo),
)

COMPLETE_ACTION_HANDLERS: tuple[tuple[type[Any], CompleteActionHandler], ...] = (
    (LoadBrowserSnapshotEffect, complete_browser_snapshot),
    (LoadChildPaneSnapshotEffect, complete_child_pane_snapshot),
    (LoadCurrentPaneEffect, complete_current_pane_snapshot),
    (LoadParentChildEffect, complete_parent_child_snapshot),
    (RunConfigSaveEffect, complete_config_save),
    (RunDirectorySizeEffect, complete_directory_sizes),
    (RunAttributeInspectionEffect, complete_attribute_inspection),
    (RunExternalLaunchEffect, complete_external_launch),
    (RunShellCommandEffect, complete_shell_command),
    (RunFileSearchEffect, complete_file_search),
    (RunGrepSearchEffect, complete_grep_search),
    (RunTextReplacePreviewEffect, complete_text_replace_preview),
    (RunTextReplaceApplyEffect, complete_text_replace_apply),
)

FAILED_ACTION_HANDLERS: tuple[tuple[type[Any], FailureActionHandler], ...] = (
    (LoadBrowserSnapshotEffect, failed_browser_snapshot),
    (LoadChildPaneSnapshotEffect, failed_child_pane_snapshot),
    (LoadCurrentPaneEffect, failed_current_pane_snapshot),
    (LoadParentChildEffect, failed_parent_child_snapshot),
    (RunArchivePreparationEffect, failed_archive_preparation),
    (RunArchiveExtractEffect, failed_archive_extract),
    (RunZipCompressPreparationEffect, failed_zip_compress_preparation),
    (RunZipCompressEffect, failed_zip_compress),
    (RunClipboardPasteEffect, failed_clipboard_paste),
    (RunFileMutationEffect, failed_file_mutation),
    (RunConfigSaveEffect, failed_config_save),
    (RunDirectorySizeEffect, failed_directory_sizes),
    (RunAttributeInspectionEffect, failed_attribute_inspection),
    (RunExternalLaunchEffect, failed_external_launch),
    (RunShellCommandEffect, failed_shell_command),
    (RunUndoEffect, failed_undo),
    (RunFileSearchEffect, failed_file_search),
    (RunGrepSearchEffect, failed_grep_search),
    (RunTextReplacePreviewEffect, failed_text_replace_preview),
    (RunTextReplaceApplyEffect, failed_text_replace_apply),
)


def complete_worker_actions(effect: Effect, result: object) -> tuple[Any, ...]:
    handler = find_handler(result, RESULT_COMPLETE_HANDLERS)
    if handler is not None:
        return handler(effect, result)
    handler = find_handler(effect, COMPLETE_ACTION_HANDLERS)
    if handler is None:
        return ()
    return handler(effect, result)


def failed_worker_actions(effect: Effect, error: BaseException | None) -> tuple[Any, ...]:
    message = str(error) or "Operation failed"
    handler = find_handler(effect, FAILED_ACTION_HANDLERS)
    if handler is None:
        return ()
    return handler(effect, error, message)
