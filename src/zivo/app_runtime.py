"""Runtime helpers for effect scheduling and worker result handling."""

from collections.abc import Sequence
from typing import Any

from textual.worker import Worker, WorkerState

from zivo.app_runtime_actions import complete_worker_actions, failed_worker_actions
from zivo.app_runtime_core import TrackingConfig, clear_tracking_for_request
from zivo.app_runtime_execution import (
    report_archive_extract_progress,
    report_zip_compress_progress,
    run_copy_paths,
    run_foreground_external_launch,
    schedule_archive_extract,
    schedule_archive_preparation,
    schedule_attribute_inspection,
    schedule_clipboard_paste,
    schedule_config_save,
    schedule_external_launch_effect,
    schedule_file_mutation,
    schedule_shell_command,
    schedule_undo,
    schedule_zip_compress,
    schedule_zip_compress_preparation,
)
from zivo.app_runtime_search import (
    CHILD_PANE_TRACKING,
    DIRECTORY_SIZE_TRACKING,
    FILE_SEARCH_RUNTIME,
    GREP_SEARCH_RUNTIME,
    cancel_active_file_search,
    cancel_active_grep_search,
    cancel_file_search_timer,
    cancel_grep_search_timer,
    cancel_pending_child_pane,
    cancel_pending_directory_size,
    cancel_pending_file_search,
    cancel_pending_grep_search,
    schedule_browser_snapshot,
    schedule_child_pane_snapshot,
    schedule_directory_sizes,
    schedule_file_search,
    schedule_grep_search,
    schedule_parent_child_update,
    schedule_progressive_browser_snapshot,
    schedule_text_replace_apply,
    schedule_text_replace_preview,
    schedule_transfer_pane_snapshot,
    start_child_pane_snapshot,
    start_file_search_worker,
    start_grep_search_worker,
)
from zivo.state import (
    Effect,
    LoadBrowserSnapshotEffect,
    LoadChildPaneSnapshotEffect,
    LoadCurrentPaneEffect,
    LoadParentChildEffect,
    LoadTransferPaneEffect,
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

TRACKING_CONFIGS: tuple[TrackingConfig, ...] = (
    CHILD_PANE_TRACKING,
    FILE_SEARCH_RUNTIME.tracking,
    GREP_SEARCH_RUNTIME.tracking,
    DIRECTORY_SIZE_TRACKING,
)

__all__ = [
    "cancel_active_file_search",
    "cancel_active_grep_search",
    "cancel_file_search_timer",
    "cancel_grep_search_timer",
    "cancel_pending_child_pane",
    "cancel_pending_directory_size",
    "cancel_pending_file_search",
    "cancel_pending_grep_search",
    "cancel_pending_runtime_work",
    "clear_effect_tracking",
    "complete_worker_actions",
    "failed_worker_actions",
    "handle_worker_state_changed",
    "report_archive_extract_progress",
    "report_zip_compress_progress",
    "run_copy_paths",
    "run_foreground_external_launch",
    "schedule_browser_snapshot",
    "schedule_child_pane_snapshot",
    "schedule_effects",
    "schedule_parent_child_update",
    "schedule_progressive_browser_snapshot",
    "schedule_file_search",
    "schedule_undo",
    "start_child_pane_snapshot",
    "start_file_search_worker",
    "start_grep_search_worker",
    "sync_runtime_state",
]


def sync_runtime_state(app: Any, previous_state: Any, next_state: Any) -> None:
    if previous_state.pending_child_pane_request_id != next_state.pending_child_pane_request_id:
        cancel_pending_child_pane(app)
    if previous_state.pending_file_search_request_id != next_state.pending_file_search_request_id:
        cancel_pending_file_search(app)
    if previous_state.pending_grep_search_request_id != next_state.pending_grep_search_request_id:
        cancel_pending_grep_search(app)
    if (
        previous_state.pending_directory_size_request_id
        != next_state.pending_directory_size_request_id
    ):
        cancel_pending_directory_size(app)


def cancel_pending_runtime_work(app: Any) -> None:
    cancel_pending_child_pane(app)
    cancel_pending_file_search(app)
    cancel_pending_grep_search(app)
    cancel_pending_directory_size(app)


def schedule_effects(app: Any, effects: Sequence[Effect]) -> None:
    for effect in effects:
        _schedule_effect(app, effect)


def _schedule_effect(app: Any, effect: Effect) -> None:
    for effect_type, scheduler in EFFECT_SCHEDULERS:
        if isinstance(effect, effect_type):
            scheduler(app, effect)
            return


EFFECT_SCHEDULERS = (
    (LoadBrowserSnapshotEffect, schedule_browser_snapshot),
    (LoadChildPaneSnapshotEffect, schedule_child_pane_snapshot),
    (LoadCurrentPaneEffect, schedule_progressive_browser_snapshot),
    (LoadParentChildEffect, schedule_parent_child_update),
    (LoadTransferPaneEffect, schedule_transfer_pane_snapshot),
    (RunArchivePreparationEffect, schedule_archive_preparation),
    (RunArchiveExtractEffect, schedule_archive_extract),
    (RunZipCompressPreparationEffect, schedule_zip_compress_preparation),
    (RunZipCompressEffect, schedule_zip_compress),
    (RunClipboardPasteEffect, schedule_clipboard_paste),
    (RunConfigSaveEffect, schedule_config_save),
    (RunDirectorySizeEffect, schedule_directory_sizes),
    (RunAttributeInspectionEffect, schedule_attribute_inspection),
    (RunFileMutationEffect, schedule_file_mutation),
    (RunUndoEffect, schedule_undo),
    (RunExternalLaunchEffect, schedule_external_launch_effect),
    (RunShellCommandEffect, schedule_shell_command),
    (RunFileSearchEffect, schedule_file_search),
    (RunGrepSearchEffect, schedule_grep_search),
    (RunTextReplacePreviewEffect, schedule_text_replace_preview),
    (RunTextReplaceApplyEffect, schedule_text_replace_apply),
)


def clear_effect_tracking(app: Any, effect: Effect) -> None:
    for tracking in TRACKING_CONFIGS:
        if isinstance(effect, tracking.effect_type):
            clear_tracking_for_request(app, tracking, effect.request_id)
            return


async def handle_worker_state_changed(app: Any, event: Worker.StateChanged) -> None:
    effect = app._pending_workers.get(event.worker.name)
    if effect is None:
        return

    if event.state in {WorkerState.PENDING, WorkerState.RUNNING}:
        return

    app._pending_workers.pop(event.worker.name, None)
    clear_effect_tracking(app, effect)

    if event.state == WorkerState.CANCELLED:
        return

    if event.state == WorkerState.SUCCESS:
        actions = complete_worker_actions(effect, event.worker.result)
        if actions:
            await app.dispatch_actions(actions)
        return

    await app.dispatch_actions(failed_worker_actions(effect, event.worker.error))
