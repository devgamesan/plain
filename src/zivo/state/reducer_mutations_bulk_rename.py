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
    ApplyBulkRenameFindReplace,
    BeginBulkRename,
    BulkRenameCompleted,
    BulkRenameFailed,
    BulkRenameProgress,
    CancelBulkRename,
    CycleBulkRenameField,
    DeleteBulkRenameTextBackward,
    DeleteBulkRenameTextForward,
    MoveBulkRenameCursor,
    MoveBulkRenameTextCursor,
    PasteIntoBulkRename,
    SetBulkRenameEditing,
    SetBulkRenameFindReplace,
    SetBulkRenameName,
    SetBulkRenameTextCursor,
)
from .effects import ReduceResult, RunBulkRenameEffect
from .models import AppState, BulkRenameEditorState, NotificationState
from .reducer_common import ReducerFn, finalize, request_snapshot_refresh
from .reducer_mutations_common import push_undo_entry
from .reducer_transfer import request_all_transfer_pane_snapshots
from .selectors import select_target_paths

_FIELDS = ("table", "find", "replace", "replace_action", "apply", "cancel")


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
            active_field="find",
            text_cursor_pos=len(action.targets[0].new_name) if action.targets else 0,
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


def _handle_set_bulk_rename_name(
    state, action: SetBulkRenameName, reduce_state
) -> ReduceResult:
    del reduce_state
    editor = state.bulk_rename
    if editor is None or not 0 <= action.row_index < len(editor.items):
        return finalize(state)
    items = list(editor.items)
    item = items[action.row_index]
    items[action.row_index] = replace(item, new_name=action.value, status="ready", message=None)
    next_editor = _refresh_validation(
        replace(
            editor,
            items=tuple(items),
            cursor_index=action.row_index,
            result_message=None,
        )
    )
    return finalize(replace(state, bulk_rename=next_editor, notification=None))


def _handle_set_bulk_rename_editing(
    state, action: SetBulkRenameEditing, reduce_state
) -> ReduceResult:
    del reduce_state
    editor = state.bulk_rename
    if editor is None or not editor.items:
        return finalize(state)
    item = editor.items[editor.cursor_index]
    return finalize(
        replace(
            state,
            bulk_rename=replace(
                editor,
                editing=action.editing,
                text_cursor_pos=min(editor.text_cursor_pos, len(item.new_name)),
            ),
        )
    )


def _handle_move_bulk_rename_text_cursor(
    state, action: MoveBulkRenameTextCursor, reduce_state
) -> ReduceResult:
    del reduce_state
    editor = state.bulk_rename
    if editor is None or not editor.items:
        return finalize(state)
    item = editor.items[editor.cursor_index]
    position = max(0, min(len(item.new_name), editor.text_cursor_pos + action.delta))
    return finalize(replace(state, bulk_rename=replace(editor, text_cursor_pos=position)))


def _handle_set_bulk_rename_text_cursor(
    state, action: SetBulkRenameTextCursor, reduce_state
) -> ReduceResult:
    del reduce_state
    editor = state.bulk_rename
    if editor is None or not editor.items:
        return finalize(state)
    item = editor.items[editor.cursor_index]
    position = max(0, min(len(item.new_name), action.cursor_pos))
    return finalize(replace(state, bulk_rename=replace(editor, text_cursor_pos=position)))


def _handle_delete_bulk_rename_text(
    state, action, *, forward: bool
) -> ReduceResult:
    del action
    editor = state.bulk_rename
    if editor is None or not editor.items:
        return finalize(state)
    item = editor.items[editor.cursor_index]
    position = editor.text_cursor_pos
    if forward:
        if position >= len(item.new_name):
            return finalize(state)
        new_value = item.new_name[:position] + item.new_name[position + 1 :]
    else:
        if position <= 0:
            return finalize(state)
        new_value = item.new_name[: position - 1] + item.new_name[position:]
        position -= 1
    items = list(editor.items)
    items[editor.cursor_index] = replace(
        items[editor.cursor_index], new_name=new_value, status="ready"
    )
    next_editor = _refresh_validation(
        replace(editor, items=tuple(items), text_cursor_pos=position)
    )
    return finalize(replace(state, bulk_rename=next_editor))


def _handle_paste_into_bulk_rename(
    state, action: PasteIntoBulkRename, reduce_state
) -> ReduceResult:
    del reduce_state
    editor = state.bulk_rename
    if editor is None or not editor.items:
        return finalize(state)
    item = editor.items[editor.cursor_index]
    position = editor.text_cursor_pos
    new_value = item.new_name[:position] + action.text + item.new_name[position:]
    items = list(editor.items)
    items[editor.cursor_index] = replace(
        items[editor.cursor_index], new_name=new_value, status="ready"
    )
    next_editor = _refresh_validation(
        replace(editor, items=tuple(items), text_cursor_pos=position + len(action.text))
    )
    return finalize(replace(state, bulk_rename=next_editor))


def _handle_set_bulk_rename_find_replace(
    state, action: SetBulkRenameFindReplace, reduce_state
) -> ReduceResult:
    del reduce_state
    if state.bulk_rename is None:
        return finalize(state)
    return finalize(
        replace(
            state,
            bulk_rename=replace(
                state.bulk_rename,
                find_text=action.find_text,
                replace_text=action.replace_text,
                result_message=None,
            ),
        )
    )


def _handle_apply_bulk_rename_find_replace(state, action, reduce_state) -> ReduceResult:
    del action, reduce_state
    editor = state.bulk_rename
    if editor is None or not editor.find_text:
        return finalize(state)
    items = tuple(
        replace(
            item,
            new_name=item.new_name.replace(editor.find_text, editor.replace_text),
            status="ready",
            message=None,
        )
        for item in editor.items
    )
    return finalize(replace(state, bulk_rename=_refresh_validation(replace(editor, items=items))))


def _handle_move_bulk_rename_cursor(
    state, action: MoveBulkRenameCursor, reduce_state
) -> ReduceResult:
    del reduce_state
    editor = state.bulk_rename
    if editor is None or not editor.items:
        return finalize(state)
    index = max(0, min(len(editor.items) - 1, editor.cursor_index + action.delta))
    item = editor.items[index]
    return finalize(
        replace(
            state,
            bulk_rename=replace(
                editor,
                cursor_index=index,
                editing=False,
                text_cursor_pos=len(item.new_name),
            ),
        )
    )


def _handle_cycle_bulk_rename_field(
    state, action: CycleBulkRenameField, reduce_state
) -> ReduceResult:
    del reduce_state
    editor = state.bulk_rename
    if editor is None:
        return finalize(state)
    current = _FIELDS.index(editor.active_field)
    next_field = _FIELDS[(current + action.delta) % len(_FIELDS)]
    return finalize(replace(state, bulk_rename=replace(editor, active_field=next_field)))


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
        next_state = replace(
            next_state,
            bulk_rename=None,
            pending_bulk_rename_request_id=None,
            notification=None,
            post_reload_notification=NotificationState(
                level="info",
                message=f"Renamed {result.success_count} item(s)",
            ),
            undo_stack=push_undo_entry(state, _bulk_rename_undo_entry(result)),
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
    SetBulkRenameName: _handle_set_bulk_rename_name,
    SetBulkRenameEditing: _handle_set_bulk_rename_editing,
    MoveBulkRenameTextCursor: _handle_move_bulk_rename_text_cursor,
    SetBulkRenameTextCursor: _handle_set_bulk_rename_text_cursor,
    DeleteBulkRenameTextBackward: lambda state, action, _reduce: _handle_delete_bulk_rename_text(
        state, action, forward=False
    ),
    DeleteBulkRenameTextForward: lambda state, action, _reduce: _handle_delete_bulk_rename_text(
        state, action, forward=True
    ),
    PasteIntoBulkRename: _handle_paste_into_bulk_rename,
    SetBulkRenameFindReplace: _handle_set_bulk_rename_find_replace,
    ApplyBulkRenameFindReplace: _handle_apply_bulk_rename_find_replace,
    MoveBulkRenameCursor: _handle_move_bulk_rename_cursor,
    CycleBulkRenameField: _handle_cycle_bulk_rename_field,
    ApplyBulkRename: _handle_apply_bulk_rename,
    BulkRenameProgress: _handle_bulk_rename_progress,
    BulkRenameCompleted: _handle_bulk_rename_completed,
    BulkRenameFailed: _handle_bulk_rename_failed,
    CancelBulkRename: _handle_cancel_bulk_rename,
}
