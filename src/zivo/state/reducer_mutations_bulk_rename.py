"""Reducer handlers for the bulk rename editor and execution."""

from dataclasses import replace
from pathlib import Path

from zivo.models import (
    BulkRenamePlanItem,
    BulkRenameRequest,
    BulkRenameTarget,
    UndoEntry,
    UndoMovePathStep,
)

from .actions import (
    ApplyBulkRename,
    BeginBulkRename,
    BulkRenameCompleted,
    BulkRenameFailed,
    BulkRenameProgress,
    CancelBulkRename,
    PasteIntoBulkRenameBaseName,
    SetBulkRenameBaseName,
)
from .effects import ReduceResult, RunBulkRenameEffect
from .models import (
    AppState,
    BulkRenameEditorState,
    NotificationAction,
    NotificationState,
)
from .reducer_common import ReducerFn, finalize, request_snapshot_refresh
from .reducer_mutations_common import push_undo_entry
from .reducer_transfer import request_all_transfer_pane_snapshots
from .selectors import select_target_paths


def _active_entries(state: AppState):
    if state.layout_mode == "transfer":
        active = (
            state.transfer_left
            if state.active_transfer_pane == "left"
            else state.transfer_right
        )
        return active.pane.entries if active is not None else ()
    return state.current_pane.entries


def _targets_for_state(state: AppState) -> tuple[str, ...]:
    if state.layout_mode == "transfer":
        active = (
            state.transfer_left
            if state.active_transfer_pane == "left"
            else state.transfer_right
        )
        if active is None:
            return ()
        selected = tuple(
            entry.path for entry in active.pane.entries if entry.path in active.pane.selected_paths
        )
        return selected or ((active.pane.cursor_path,) if active.pane.cursor_path else ())
    return select_target_paths(state)


def _parent_dir_for_state(state: AppState) -> str:
    if state.layout_mode == "transfer":
        active = (
            state.transfer_left
            if state.active_transfer_pane == "left"
            else state.transfer_right
        )
        if active is not None:
            return active.current_path
    return state.current_pane.directory_path


def _initial_items(
    state: AppState, targets: tuple[BulkRenameTarget, ...]
) -> tuple[BulkRenamePlanItem, ...]:
    entry_names = {entry.path: entry.name for entry in _active_entries(state)}
    return tuple(
        BulkRenamePlanItem(
            source_path=target.source_path,
            old_name=entry_names.get(target.source_path, Path(target.source_path).name),
            new_name=target.new_name,
            status="ready",
        )
        for target in targets
    )


def _request_from_editor(editor: BulkRenameEditorState) -> BulkRenameRequest:
    return BulkRenameRequest(
        parent_dir=editor.parent_dir,
        targets=tuple(
            BulkRenameTarget(source_path=item.source_path, new_name=item.new_name)
            for item in editor.items
        ),
    )


def _refresh_validation(editor: BulkRenameEditorState) -> BulkRenameEditorState:
    from zivo.services.bulk_rename import LiveBulkRenameService

    request = _request_from_editor(editor)
    validation = LiveBulkRenameService().validate(request)
    return replace(editor, items=validation.items)


def _handle_begin_bulk_rename(
    state, action: BeginBulkRename, reduce_state: ReducerFn
) -> ReduceResult:
    del reduce_state
    if len(action.targets) < 2:
        return finalize(
            replace(
                state,
                notification=NotificationState(
                    level="warning",
                    message="Bulk rename requires at least two selected items",
                ),
            )
        )
    editor = _refresh_validation(
        BulkRenameEditorState(
            parent_dir=action.parent_dir,
            targets=action.targets,
            items=_initial_items(state, action.targets),
            active_field="base_name",
        )
    )
    return finalize(
        replace(
            state,
            ui_mode="BULK_RENAME",
            bulk_rename=editor,
            notification=None,
            command_palette=None,
            pending_input=None,
            pending_bulk_rename_request_id=None,
        )
    )


def _generated_name(base_name: str, old_name: str, index: int) -> str:
    """Build a numbered destination name while preserving the full suffix."""

    if not base_name:
        return old_name
    suffix = "".join(Path(old_name).suffixes)
    return f"{base_name}_{index + 1}{suffix}"


def _handle_set_bulk_rename_base_name(
    state, action: SetBulkRenameBaseName, reduce_state
) -> ReduceResult:
    del reduce_state
    editor = state.bulk_rename
    if editor is None:
        return finalize(state)
    items = tuple(
        replace(
            item,
            new_name=_generated_name(action.value, item.old_name, index),
            status="ready",
            message=None,
        )
        for index, item in enumerate(editor.items)
    )
    next_editor = _refresh_validation(
        replace(editor, base_name=action.value, items=items, result_message=None)
    )
    return finalize(replace(state, bulk_rename=next_editor, notification=None))


def _handle_paste_into_bulk_rename_base_name(
    state, action: PasteIntoBulkRenameBaseName, reduce_state
) -> ReduceResult:
    editor = state.bulk_rename
    if editor is None:
        return finalize(state)
    return _handle_set_bulk_rename_base_name(
        state,
        SetBulkRenameBaseName(editor.base_name + action.text),
        reduce_state,
    )


def _handle_apply_bulk_rename(
    state, action: ApplyBulkRename, reduce_state: ReducerFn
) -> ReduceResult:
    del action, reduce_state
    editor = state.bulk_rename
    if editor is None:
        return finalize(state)
    editor = _refresh_validation(editor)
    request = _request_from_editor(editor)
    from zivo.services.bulk_rename import LiveBulkRenameService

    validation = LiveBulkRenameService().validate(request)
    if not validation.executable:
        message = (
            f"Bulk rename has {validation.error_count} validation error(s)"
            if validation.error_count
            else "No names have changed"
        )
        return finalize(
            replace(
                state,
                bulk_rename=replace(editor, items=validation.items, result_message=message),
                notification=NotificationState(level="warning", message=message),
            )
        )
    request_id = state.next_request_id
    changed_count = validation.changed_count
    return ReduceResult(
        state=replace(
            state,
            ui_mode="BUSY",
            bulk_rename=replace(
                editor,
                items=validation.items,
                result_message=None,
                progress_completed=0,
                progress_total=changed_count,
            ),
            notification=NotificationState(
                level="info",
                message=f"Renaming {changed_count} item(s)...",
            ),
            pending_bulk_rename_request_id=request_id,
            next_request_id=request_id + 1,
        ),
        effects=(RunBulkRenameEffect(request_id=request_id, request=request),),
    )


def _handle_bulk_rename_progress(
    state, action: BulkRenameProgress, reduce_state
) -> ReduceResult:
    del reduce_state
    if action.request_id != state.pending_bulk_rename_request_id or state.bulk_rename is None:
        return finalize(state)
    current = Path(action.current_path).name if action.current_path else ""
    suffix = f": {current}" if current else ""
    return finalize(
        replace(
            state,
            bulk_rename=replace(
                state.bulk_rename,
                progress_completed=action.completed_entries,
                progress_total=action.total_entries,
                progress_path=action.current_path,
            ),
            notification=NotificationState(
                level="info",
                message=(
                    f"Renaming {action.completed_entries}/{action.total_entries} item(s)"
                    f"{suffix}"
                ),
            ),
        )
    )


def _bulk_rename_undo_entry(result) -> UndoEntry | None:
    if not result.applied_changes or result.failure_count:
        return None
    return UndoEntry(
        kind="bulk_rename",
        steps=tuple(
            UndoMovePathStep(
                source_path=change.destination_path,
                destination_path=change.source_path,
            )
            for change in result.applied_changes
        ),
    )


def _preserve_renamed_selection(state: AppState, result) -> AppState:
    """Carry selected and focused paths across the post-rename refresh."""

    path_map = {
        change.source_path: change.destination_path
        for change in result.applied_changes
    }

    def map_pane(pane):
        return replace(
            pane,
            selected_paths=frozenset(
                path_map.get(path, path) for path in pane.selected_paths
            ),
            selection_anchor_path=(
                path_map.get(pane.selection_anchor_path, pane.selection_anchor_path)
                if pane.selection_anchor_path
                else None
            ),
            cursor_path=(
                path_map.get(pane.cursor_path, pane.cursor_path)
                if pane.cursor_path
                else None
            ),
        )

    if state.layout_mode != "transfer":
        return replace(state, current_pane=map_pane(state.current_pane))
    active = state.transfer_left if state.active_transfer_pane == "left" else state.transfer_right
    if active is None:
        return state
    next_transfer = replace(active, pane=map_pane(active.pane))
    if state.active_transfer_pane == "left":
        return replace(state, transfer_left=next_transfer)
    return replace(state, transfer_right=next_transfer)


def _handle_bulk_rename_completed(
    state, action: BulkRenameCompleted, reduce_state
) -> ReduceResult:
    del reduce_state
    if action.request_id != state.pending_bulk_rename_request_id or state.bulk_rename is None:
        return finalize(state)
    result = action.result
    if result.failure_count == 0 and result.success_count == result.validation.changed_count:
        next_state = _preserve_renamed_selection(state, result)
        undo_entry = _bulk_rename_undo_entry(result)
        next_state = replace(
            next_state,
            bulk_rename=None,
            pending_bulk_rename_request_id=None,
            notification=None,
            post_reload_notification=NotificationState(
                level="info",
                message=f"Renamed {result.success_count} item(s)",
                action=(
                    NotificationAction(
                        action_id="notification.undo",
                        label="Undo",
                        payload=undo_entry,
                    )
                    if undo_entry is not None
                    else None
                ),
                auto_dismiss=True,
            ),
            undo_stack=push_undo_entry(state, undo_entry),
            ui_mode="BROWSING",
        )
        if state.layout_mode == "transfer":
            return request_all_transfer_pane_snapshots(next_state)
        return request_snapshot_refresh(next_state)

    message = result.message or "Bulk rename failed"
    level = "warning" if result.rolled_back else "error"
    return finalize(
        replace(
            state,
            ui_mode="BULK_RENAME",
            pending_bulk_rename_request_id=None,
            bulk_rename=replace(
                state.bulk_rename,
                items=result.validation.items,
                result_message=message,
                progress_completed=0,
                progress_total=0,
            ),
            notification=NotificationState(level=level, message=message),
        )
    )


def _handle_bulk_rename_failed(state, action: BulkRenameFailed, reduce_state) -> ReduceResult:
    del reduce_state
    if action.request_id != state.pending_bulk_rename_request_id or state.bulk_rename is None:
        return finalize(state)
    return finalize(
        replace(
            state,
            ui_mode="BULK_RENAME",
            pending_bulk_rename_request_id=None,
            bulk_rename=replace(state.bulk_rename, result_message=action.message),
            notification=NotificationState(level="error", message=action.message),
        )
    )


def _handle_cancel_bulk_rename(state, action, reduce_state) -> ReduceResult:
    del action, reduce_state
    if state.bulk_rename is None:
        return finalize(state)
    return finalize(
        replace(
            state,
            ui_mode="BROWSING",
            bulk_rename=None,
            pending_bulk_rename_request_id=None,
            notification=None,
        )
    )


BULK_RENAME_MUTATION_HANDLERS = {
    BeginBulkRename: _handle_begin_bulk_rename,
    SetBulkRenameBaseName: _handle_set_bulk_rename_base_name,
    PasteIntoBulkRenameBaseName: _handle_paste_into_bulk_rename_base_name,
    ApplyBulkRename: _handle_apply_bulk_rename,
    BulkRenameProgress: _handle_bulk_rename_progress,
    BulkRenameCompleted: _handle_bulk_rename_completed,
    BulkRenameFailed: _handle_bulk_rename_failed,
    CancelBulkRename: _handle_cancel_bulk_rename,
}
