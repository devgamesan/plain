"""Selection and clipboard mutation handlers."""

from dataclasses import replace

from zivo.models import PasteRequest

from .actions import (
    CancelPasteConflict,
    ClearSelection,
    ClipboardPasteCompleted,
    ClipboardPasteFailed,
    ClipboardPasteNeedsResolution,
    CopyTargets,
    CutTargets,
    PasteClipboard,
    ResolvePasteConflict,
    SelectAllVisibleEntries,
    ToggleSelection,
    ToggleSelectionAndAdvance,
)
from .models import ClipboardState, NotificationState, PasteConflictState
from .reducer_common import (
    active_current_entries,
    current_entry_paths,
    finalize,
    format_clipboard_message,
    move_cursor,
    normalize_selected_paths,
    notification_for_paste_summary,
    request_snapshot_refresh,
    run_paste_request,
    sync_child_pane,
)
from .reducer_mutations_common import MutationHandler, push_undo_entry, undo_entry_for_paste


def _handle_toggle_selection(state, action, reduce_state):
    if action.path not in current_entry_paths(state):
        return finalize(state)
    active_entries = active_current_entries(state)
    selected_paths = set(
        normalize_selected_paths(
            state.current_pane.selected_paths,
            active_entries,
        )
    )
    if action.path in selected_paths:
        selected_paths.remove(action.path)
    else:
        selected_paths.add(action.path)
    return finalize(
        replace(
            state,
            current_pane=replace(
                state.current_pane,
                selected_paths=frozenset(selected_paths),
                selection_anchor_path=None,
            ),
        )
    )


def _handle_toggle_selection_and_advance(state, action, reduce_state):
    if action.path not in current_entry_paths(state):
        return finalize(state)
    active_entries = active_current_entries(state)
    selected_paths = set(
        normalize_selected_paths(
            state.current_pane.selected_paths,
            active_entries,
        )
    )
    if action.path in selected_paths:
        selected_paths.remove(action.path)
    else:
        selected_paths.add(action.path)
    cursor_path = move_cursor(action.path, action.visible_paths, 1)
    next_state = replace(
        state,
        current_pane=replace(
            state.current_pane,
            cursor_path=cursor_path,
            selected_paths=frozenset(selected_paths),
            selection_anchor_path=None,
        ),
        notification=None,
    )
    return sync_child_pane(next_state, cursor_path, reduce_state)


def _handle_clear_selection(state, action, reduce_state):
    return finalize(
        replace(
            state,
            current_pane=replace(
                state.current_pane,
                selected_paths=frozenset(),
                selection_anchor_path=None,
            ),
        )
    )


def _handle_select_all_visible_entries(state, action, reduce_state):
    active_entries = active_current_entries(state)
    selected_paths = normalize_selected_paths(
        frozenset(action.paths),
        active_entries,
    )
    return finalize(
        replace(
            state,
            current_pane=replace(
                state.current_pane,
                selected_paths=selected_paths,
                selection_anchor_path=None,
            ),
            notification=None,
        )
    )


def _handle_copy_targets(state, action, reduce_state):
    if not action.paths:
        return finalize(
            replace(
                state,
                notification=NotificationState(level="warning", message="Nothing to copy"),
            )
        )
    return finalize(
        replace(
            state,
            clipboard=ClipboardState(mode="copy", paths=action.paths),
            notification=NotificationState(
                level="info",
                message=format_clipboard_message("Copied", action.paths),
            ),
        )
    )


def _handle_cut_targets(state, action, reduce_state):
    if not action.paths:
        return finalize(
            replace(
                state,
                notification=NotificationState(level="warning", message="Nothing to cut"),
            )
        )
    return finalize(
        replace(
            state,
            clipboard=ClipboardState(mode="cut", paths=action.paths),
            notification=NotificationState(
                level="info",
                message=format_clipboard_message("Cut", action.paths),
            ),
        )
    )


def _handle_paste_clipboard(state, action, reduce_state):
    if state.clipboard.mode == "none" or not state.clipboard.paths:
        return finalize(
            replace(
                state,
                notification=NotificationState(level="warning", message="Clipboard is empty"),
            )
        )

    request = PasteRequest(
        mode=state.clipboard.mode,
        source_paths=state.clipboard.paths,
        destination_dir=state.current_pane.directory_path,
    )
    return run_paste_request(state, request)


def _handle_resolve_paste_conflict(state, action, reduce_state):
    if state.paste_conflict is None:
        return finalize(state)
    request = replace(
        state.paste_conflict.request,
        conflict_resolution=action.resolution,
    )
    return run_paste_request(
        replace(
            state,
            paste_conflict=None,
            delete_confirmation=None,
            command_palette=None,
            ui_mode="BROWSING",
            notification=None,
        ),
        request,
    )


def _handle_cancel_paste_conflict(state, action, reduce_state):
    return finalize(
        replace(
            state,
            paste_conflict=None,
            delete_confirmation=None,
            ui_mode="BROWSING",
            notification=NotificationState(level="warning", message="Paste cancelled"),
        )
    )


def _handle_clipboard_paste_needs_resolution(state, action, reduce_state):
    if action.request_id != state.pending_paste_request_id or not action.conflicts:
        return finalize(state)
    if state.paste_conflict_action != "prompt":
        request = replace(
            action.request,
            conflict_resolution=state.paste_conflict_action,
        )
        return run_paste_request(
            replace(
                state,
                paste_conflict=None,
                delete_confirmation=None,
                name_conflict=None,
                notification=None,
                pending_paste_request_id=None,
                ui_mode="BROWSING",
            ),
            request,
        )
    return finalize(
        replace(
            state,
            paste_conflict=PasteConflictState(
                request=action.request,
                conflicts=action.conflicts,
                first_conflict=action.conflicts[0],
            ),
            delete_confirmation=None,
            name_conflict=None,
            pending_paste_request_id=None,
            ui_mode="CONFIRM",
        )
    )


def _handle_clipboard_paste_completed(state, action, reduce_state):
    if action.request_id != state.pending_paste_request_id:
        return finalize(state)

    next_clipboard = state.clipboard
    if state.clipboard.mode == "cut" and action.summary.success_count > 0:
        next_clipboard = ClipboardState()

    next_state = replace(
        state,
        clipboard=next_clipboard,
        undo_stack=push_undo_entry(
            state,
            undo_entry_for_paste(action.summary, action.applied_changes),
        ),
        notification=None,
        paste_conflict=None,
        delete_confirmation=None,
        name_conflict=None,
        post_reload_notification=notification_for_paste_summary(action.summary),
        pending_paste_request_id=None,
        ui_mode="BROWSING",
    )
    return request_snapshot_refresh(next_state)


def _handle_clipboard_paste_failed(state, action, reduce_state):
    if action.request_id != state.pending_paste_request_id:
        return finalize(state)
    return finalize(
        replace(
            state,
            notification=NotificationState(level="error", message=action.message),
            paste_conflict=None,
            delete_confirmation=None,
            name_conflict=None,
            pending_paste_request_id=None,
            ui_mode="BROWSING",
        )
    )


SELECTION_MUTATION_HANDLERS: dict[type, MutationHandler] = {
    ToggleSelection: _handle_toggle_selection,
    ToggleSelectionAndAdvance: _handle_toggle_selection_and_advance,
    ClearSelection: _handle_clear_selection,
    SelectAllVisibleEntries: _handle_select_all_visible_entries,
    CopyTargets: _handle_copy_targets,
    CutTargets: _handle_cut_targets,
    PasteClipboard: _handle_paste_clipboard,
    ResolvePasteConflict: _handle_resolve_paste_conflict,
    CancelPasteConflict: _handle_cancel_paste_conflict,
    ClipboardPasteNeedsResolution: _handle_clipboard_paste_needs_resolution,
    ClipboardPasteCompleted: _handle_clipboard_paste_completed,
    ClipboardPasteFailed: _handle_clipboard_paste_failed,
}
