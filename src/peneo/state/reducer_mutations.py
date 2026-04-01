"""Mutation and clipboard reducer handlers."""

from dataclasses import replace
from pathlib import Path

from peneo.models import PasteRequest, RenameRequest, TrashDeleteRequest

from .actions import (
    Action,
    BeginCreateInput,
    BeginDeleteTargets,
    BeginRenameInput,
    CancelDeleteConfirmation,
    CancelPasteConflict,
    CancelPendingInput,
    ClearSelection,
    ClipboardPasteCompleted,
    ClipboardPasteFailed,
    ClipboardPasteNeedsResolution,
    ConfirmDeleteTargets,
    CopyTargets,
    CutTargets,
    DismissNameConflict,
    FileMutationCompleted,
    FileMutationFailed,
    PasteClipboard,
    ResolvePasteConflict,
    SetPendingInputValue,
    SubmitPendingInput,
    ToggleSelection,
    ToggleSelectionAndAdvance,
)
from .effects import ReduceResult
from .models import (
    AppState,
    ClipboardState,
    DeleteConfirmationState,
    NameConflictState,
    NotificationState,
    PasteConflictState,
    PendingInputState,
)
from .reducer_common import (
    ReducerFn,
    active_current_entries,
    build_file_mutation_request,
    current_entry_for_path,
    current_entry_paths,
    cursor_path_after_file_mutation,
    done,
    format_clipboard_message,
    is_name_conflict_validation_error,
    move_cursor,
    name_conflict_kind,
    normalize_selected_paths,
    notification_for_paste_summary,
    request_snapshot_refresh,
    restore_ui_mode_after_pending_input,
    run_file_mutation_request,
    run_paste_request,
    sync_child_pane,
    validate_pending_input,
)


def handle_mutation_action(
    state: AppState,
    action: Action,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    if isinstance(action, BeginRenameInput):
        entry = current_entry_for_path(state, action.path)
        if entry is None:
            return done(state)
        return done(
            replace(
                state,
                ui_mode="RENAME",
                notification=None,
                pending_input=PendingInputState(
                    prompt="Rename: ",
                    value=entry.name,
                    target_path=entry.path,
                ),
                command_palette=None,
                pending_file_search_request_id=None,
                pending_grep_search_request_id=None,
                delete_confirmation=None,
                name_conflict=None,
                attribute_inspection=None,
            )
        )

    if isinstance(action, BeginDeleteTargets):
        if not action.paths:
            return done(state)
        if state.confirm_delete:
            return done(
                replace(
                    state,
                    ui_mode="CONFIRM",
                    notification=None,
                    pending_input=None,
                    command_palette=None,
                    pending_file_search_request_id=None,
                    pending_grep_search_request_id=None,
                    paste_conflict=None,
                    delete_confirmation=DeleteConfirmationState(paths=action.paths),
                    name_conflict=None,
                    attribute_inspection=None,
                )
            )
        return run_file_mutation_request(
            replace(
                state,
                notification=None,
                paste_conflict=None,
                delete_confirmation=None,
                name_conflict=None,
                attribute_inspection=None,
            ),
            TrashDeleteRequest(paths=action.paths),
        )

    if isinstance(action, BeginCreateInput):
        prompt = "New file: " if action.kind == "file" else "New directory: "
        return done(
            replace(
                state,
                ui_mode="CREATE",
                notification=None,
                pending_input=PendingInputState(
                    prompt=prompt,
                    create_kind=action.kind,
                ),
                command_palette=None,
                pending_file_search_request_id=None,
                pending_grep_search_request_id=None,
                delete_confirmation=None,
                name_conflict=None,
                attribute_inspection=None,
            )
        )

    if isinstance(action, SetPendingInputValue):
        if state.pending_input is None:
            return done(state)
        return done(
            replace(
                state,
                pending_input=replace(state.pending_input, value=action.value),
            )
        )

    if isinstance(action, CancelPendingInput):
        return done(
            replace(
                state,
                ui_mode="BROWSING",
                notification=None,
                pending_input=None,
                command_palette=None,
                pending_file_search_request_id=None,
                pending_grep_search_request_id=None,
                delete_confirmation=None,
                name_conflict=None,
                attribute_inspection=None,
            )
        )

    if isinstance(action, SubmitPendingInput):
        if state.pending_input is None:
            return done(state)
        validation_error = validate_pending_input(state)
        if validation_error is not None:
            if is_name_conflict_validation_error(state, validation_error):
                return done(
                    replace(
                        state,
                        ui_mode="CONFIRM",
                        notification=None,
                        paste_conflict=None,
                        delete_confirmation=None,
                        name_conflict=NameConflictState(
                            kind=name_conflict_kind(state),
                            name=state.pending_input.value,
                        ),
                    )
                )
            return done(
                replace(
                    state,
                    notification=NotificationState(level="error", message=validation_error),
                    name_conflict=None,
                )
            )
        request = build_file_mutation_request(state)
        if request is None:
            return done(state)
        if isinstance(request, RenameRequest):
            current_name = Path(request.source_path).name
            if current_name == request.new_name:
                return done(
                    replace(
                        state,
                        ui_mode="BROWSING",
                        pending_input=None,
                        notification=NotificationState(level="info", message="Name unchanged"),
                    )
                )
        return run_file_mutation_request(state, request)

    if isinstance(action, ToggleSelection):
        if action.path not in current_entry_paths(state):
            return done(state)
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
        return done(
            replace(
                state,
                current_pane=replace(
                    state.current_pane,
                    selected_paths=frozenset(selected_paths),
                ),
            )
        )

    if isinstance(action, ToggleSelectionAndAdvance):
        if action.path not in current_entry_paths(state):
            return done(state)
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
            ),
            notification=None,
        )
        return sync_child_pane(next_state, cursor_path, reduce_state)

    if isinstance(action, ClearSelection):
        return done(
            replace(
                state,
                current_pane=replace(state.current_pane, selected_paths=frozenset()),
            )
        )

    if isinstance(action, CopyTargets):
        if not action.paths:
            return done(
                replace(
                    state,
                    notification=NotificationState(level="warning", message="Nothing to copy"),
                )
            )
        return done(
            replace(
                state,
                clipboard=ClipboardState(mode="copy", paths=action.paths),
                notification=NotificationState(
                    level="info",
                    message=format_clipboard_message("Copied", action.paths),
                ),
            )
        )

    if isinstance(action, CutTargets):
        if not action.paths:
            return done(
                replace(
                    state,
                    notification=NotificationState(level="warning", message="Nothing to cut"),
                )
            )
        return done(
            replace(
                state,
                clipboard=ClipboardState(mode="cut", paths=action.paths),
                notification=NotificationState(
                    level="info",
                    message=format_clipboard_message("Cut", action.paths),
                ),
            )
        )

    if isinstance(action, PasteClipboard):
        if state.clipboard.mode == "none" or not state.clipboard.paths:
            return done(
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

    if isinstance(action, ResolvePasteConflict):
        if state.paste_conflict is None:
            return done(state)
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

    if isinstance(action, CancelPasteConflict):
        return done(
            replace(
                state,
                paste_conflict=None,
                delete_confirmation=None,
                ui_mode="BROWSING",
                notification=NotificationState(level="warning", message="Paste cancelled"),
            )
        )

    if isinstance(action, ConfirmDeleteTargets):
        if state.delete_confirmation is None:
            return done(state)
        return run_file_mutation_request(
            replace(
                state,
                delete_confirmation=None,
                paste_conflict=None,
                notification=None,
            ),
            TrashDeleteRequest(paths=state.delete_confirmation.paths),
        )

    if isinstance(action, CancelDeleteConfirmation):
        return done(
            replace(
                state,
                delete_confirmation=None,
                ui_mode="BROWSING",
                notification=NotificationState(level="warning", message="Delete cancelled"),
            )
        )

    if isinstance(action, ClipboardPasteNeedsResolution):
        if action.request_id != state.pending_paste_request_id or not action.conflicts:
            return done(state)
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
        return done(
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

    if isinstance(action, ClipboardPasteCompleted):
        if action.request_id != state.pending_paste_request_id:
            return done(state)

        next_clipboard = state.clipboard
        if state.clipboard.mode == "cut" and action.summary.success_count > 0:
            next_clipboard = ClipboardState()

        next_state = replace(
            state,
            clipboard=next_clipboard,
            notification=None,
            paste_conflict=None,
            delete_confirmation=None,
            name_conflict=None,
            post_reload_notification=notification_for_paste_summary(action.summary),
            pending_paste_request_id=None,
            ui_mode="BROWSING",
        )
        return request_snapshot_refresh(next_state)

    if isinstance(action, ClipboardPasteFailed):
        if action.request_id != state.pending_paste_request_id:
            return done(state)
        return done(
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

    if isinstance(action, FileMutationCompleted):
        if action.request_id != state.pending_file_mutation_request_id:
            return done(state)
        selected_paths = state.current_pane.selected_paths
        if action.result.removed_paths:
            selected_paths = frozenset(
                path for path in selected_paths if path not in action.result.removed_paths
            )
        next_state = replace(
            state,
            notification=None,
            current_pane=replace(state.current_pane, selected_paths=selected_paths),
            pending_input=None,
            delete_confirmation=None,
            name_conflict=None,
            pending_file_mutation_request_id=None,
            post_reload_notification=NotificationState(
                level=action.result.level,
                message=action.result.message,
            ),
            ui_mode="BROWSING",
        )
        return request_snapshot_refresh(
            next_state,
            cursor_path=cursor_path_after_file_mutation(state, action.result),
            keep_current_cursor=not bool(action.result.removed_paths),
        )

    if isinstance(action, FileMutationFailed):
        if action.request_id != state.pending_file_mutation_request_id:
            return done(state)
        return done(
            replace(
                state,
                notification=NotificationState(level="error", message=action.message),
                pending_file_mutation_request_id=None,
                delete_confirmation=None,
                name_conflict=None,
                ui_mode=restore_ui_mode_after_pending_input(state),
            )
        )

    if isinstance(action, DismissNameConflict):
        if state.name_conflict is None:
            return done(state)
        return done(
            replace(
                state,
                notification=None,
                name_conflict=None,
                ui_mode=restore_ui_mode_after_pending_input(state),
            )
        )

    return None
