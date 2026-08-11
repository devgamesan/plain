"""Command palette reducer handlers."""

from dataclasses import replace
from typing import Callable

from .actions import (
    Action,
    AttributeInspectionFailed,
    AttributeInspectionLoaded,
    BeginBookmarkSearch,
    BeginCommandPalette,
    BeginFileSearch,
    BeginFindAndReplace,
    BeginGo,
    BeginGrepReplace,
    BeginGrepReplaceSelected,
    BeginGrepSearch,
    BeginTextReplace,
    CancelCommandPalette,
    CycleFileSearchField,
    CycleFindReplaceField,
    CycleGrepReplaceField,
    CycleGrepReplaceSelectedField,
    CycleGrepSearchField,
    CycleReplaceField,
    DismissAboutDialog,
    DismissAttributeDialog,
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
    ShowAbout,
    ShowAttributes,
    SubmitCommandPalette,
    TextReplaceApplied,
    TextReplaceApplyFailed,
    TextReplacePreviewCompleted,
    TextReplacePreviewFailed,
)
from .actions_palette import OpenSearchWorkspace
from .command_palette import normalize_command_palette_cursor
from .effects import ReduceResult
from .models import AppState, NotificationState
from .reducer_common import (
    ReducerFn,
    finalize,
    sync_child_pane,
)
from .reducer_palette_commands import (
    handle_show_attributes_command,
    handle_submit_commands_palette,
)
from .reducer_palette_export import (
    handle_grep_export_completed,
    handle_grep_export_failed,
    handle_save_grep_results,
)
from .reducer_palette_navigation import (
    handle_begin_bookmark_search,
    handle_begin_go,
    handle_submit_go_palette,
)
from .reducer_palette_replace import (
    handle_cycle_find_replace_field,
    handle_cycle_grep_replace_field,
    handle_cycle_grep_replace_selected_field,
    handle_set_find_replace_field,
    handle_set_grep_replace_field,
    handle_set_grep_replace_selected_field,
    handle_submit_find_and_replace_palette,
    handle_submit_grep_replace_palette,
    handle_submit_grep_replace_selected_palette,
    handle_submit_replace_palette,
    handle_text_replace_applied,
    handle_text_replace_apply_failed,
    handle_text_replace_preview_completed,
    handle_text_replace_preview_failed,
    sync_find_replace_preview,
    sync_grep_replace_preview,
    sync_grep_replace_selected_preview,
    sync_replace_preview,
)
from .reducer_palette_replace_scope import (
    default_replace_scope,
    handle_set_replace_scope,
    replace_scope_target_paths,
)
from .reducer_palette_replace_scope import (
    handle_cycle_replace_field as handle_cycle_unified_replace_field,
)
from .reducer_palette_replace_scope import (
    handle_set_replace_field as handle_set_unified_replace_field,
)
from .reducer_palette_search import (
    handle_cycle_file_search_field,
    handle_file_search_completed,
    handle_file_search_failed,
    handle_file_search_results_updated,
    handle_grep_search_completed,
    handle_grep_search_failed,
    handle_grep_search_results_updated,
    handle_open_find_result_in_editor,
    handle_open_find_result_in_gui_editor,
    handle_open_grep_result_in_editor,
    handle_open_grep_result_in_gui_editor,
    handle_open_search_workspace,
    handle_set_file_search_query,
    handle_set_file_search_target,
    handle_set_grep_search_field,
    handle_set_grep_search_scope,
    handle_submit_file_search_palette,
    handle_submit_grep_search_palette,
    sync_file_search_preview,
    sync_grep_preview,
)
from .reducer_palette_shared import (
    GREP_SEARCH_FIELDS,
    enter_palette,
    restore_browsing_from_palette,
)


def _handle_move_palette_cursor(state: AppState, action: MoveCommandPaletteCursor) -> ReduceResult:
    if state.command_palette is None:
        return finalize(state)
    next_palette = replace(
        state.command_palette,
        cursor_index=normalize_command_palette_cursor(
            state,
            state.command_palette.cursor_index + action.delta,
        ),
    )
    next_state = replace(state, command_palette=next_palette)
    if state.command_palette.source == "file_search":
        return sync_file_search_preview(next_state)
    if state.command_palette.source == "grep_search":
        return sync_grep_preview(next_state)
    if state.command_palette.source == "replace_text":
        return sync_replace_preview(next_state)
    if state.command_palette.source == "replace_in_found_files":
        return sync_find_replace_preview(next_state)
    if state.command_palette.source == "replace_in_grep_files":
        return sync_grep_replace_preview(next_state)
    if state.command_palette.source == "grep_replace_selected":
        return sync_grep_replace_selected_preview(next_state)
    return finalize(next_state)


def _next_palette_query_state(state: AppState, query: str):
    return replace(
        state.command_palette,
        query=query,
        cursor_index=0,
        file_search=replace(
            state.command_palette.file_search,
            error_message=None,
        ),
        grep_search=replace(
            state.command_palette.grep_search,
            error_message=None,
        ),
    )

def _handle_set_palette_query(state: AppState, action: SetCommandPaletteQuery) -> ReduceResult:
    if state.command_palette is None:
        return finalize(state)
    next_palette = _next_palette_query_state(state, action.query)
    if state.command_palette.source == "file_search":
        return handle_set_file_search_query(state, next_palette, action.query)
    if state.command_palette.source == "grep_search":
        return handle_set_grep_search_field(state, "keyword", action.query)
    return finalize(replace(state, command_palette=next_palette))


def _handle_cycle_grep_search_field(state: AppState, action: CycleGrepSearchField) -> ReduceResult:
    if state.command_palette is None or state.command_palette.source != "grep_search":
        return finalize(state)
    current_index = GREP_SEARCH_FIELDS.index(state.command_palette.grep_search.active_field)
    next_index = (current_index + action.delta) % len(GREP_SEARCH_FIELDS)
    return finalize(
        replace(
            state,
            command_palette=replace(
                state.command_palette,
                grep_search=replace(
                    state.command_palette.grep_search,
                    active_field=GREP_SEARCH_FIELDS[next_index],
                ),
            ),
        )
    )

def _handle_submit_palette(state: AppState, reduce_state: ReducerFn) -> ReduceResult:
    if state.command_palette is None:
        return finalize(state)
    if state.command_palette.source == "file_search":
        return handle_submit_file_search_palette(state, reduce_state)
    if state.command_palette.source == "grep_search":
        return handle_submit_grep_search_palette(state, reduce_state)
    if state.command_palette.source == "replace_text":
        return handle_submit_replace_palette(state)
    if state.command_palette.source == "replace_in_found_files":
        return handle_submit_find_and_replace_palette(state)
    if state.command_palette.source == "replace_in_grep_files":
        return handle_submit_grep_replace_palette(state)
    if state.command_palette.source == "grep_replace_selected":
        return handle_submit_grep_replace_selected_palette(state)
    if state.command_palette.source == "go":
        return handle_submit_go_palette(state, reduce_state)
    return handle_submit_commands_palette(state, reduce_state)


def _handle_begin_command_palette(
    state: AppState,
    action: BeginCommandPalette,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del reduce_state
    return finalize(enter_palette(state, preserve_notification=True))


def _handle_begin_file_search(
    state: AppState,
    action: BeginFileSearch,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del action, reduce_state
    return finalize(enter_palette(state, source="file_search"))


def _handle_begin_go(
    state: AppState,
    action: BeginGo,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del reduce_state
    return handle_begin_go(state, action.source_filter)


def _handle_begin_grep_search(
    state: AppState,
    action: BeginGrepSearch,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del reduce_state
    from .reducer_palette_search import default_grep_search_scope, grep_scope_target_paths

    scope = action.scope or default_grep_search_scope(state)
    next_state = enter_palette(state, source="grep_search")
    return finalize(replace(
        next_state,
        command_palette=replace(
            next_state.command_palette,
            grep_search=replace(
                next_state.command_palette.grep_search,
                scope=scope,
                target_paths=action.target_paths or grep_scope_target_paths(state, scope),
            ),
        ),
    ))


def _handle_begin_text_replace(
    state: AppState,
    action: BeginTextReplace,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del reduce_state
    scope = "selected_files" if action.target_paths else default_replace_scope(state)
    next_state = enter_palette(state, source="replace_text")
    return finalize(
        replace(
            next_state,
            command_palette=replace(
                next_state.command_palette,
                replace_preview=replace(
                    next_state.command_palette.replace_preview,
                    scope=scope,
                    target_paths=action.target_paths or replace_scope_target_paths(state, scope),
                ),
            ),
        )
    )


def _handle_begin_legacy_replace(state: AppState, source: str) -> ReduceResult:
    return finalize(enter_palette(state, source=source))


def _handle_begin_grep_replace_selected(
    state: AppState, action: BeginGrepReplaceSelected, reduce_state: ReducerFn
) -> ReduceResult:
    del reduce_state
    next_state = enter_palette(state, source="grep_replace_selected")
    return finalize(
        replace(
            next_state,
            command_palette=replace(
                next_state.command_palette,
                grs=replace(next_state.command_palette.grs, target_paths=action.target_paths),
            ),
        )
    )


def _dispatch_begin_bookmark_search(
    state: AppState,
    action: BeginBookmarkSearch,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del action, reduce_state
    return handle_begin_bookmark_search(state)


def _handle_cancel_command_palette(
    state: AppState,
    action: CancelCommandPalette,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del action
    preserve_notification = (
        state.command_palette is not None
        and state.command_palette.source == "commands"
        and state.notification is not None
        and state.notification.action is not None
    )
    next_state = restore_browsing_from_palette(
        state,
        clear_name_conflict=True,
        preserve_notification=preserve_notification,
    )
    if state.command_palette is not None and state.command_palette.source in {
        "file_search",
        "grep_search",
        "replace_text",
        "replace_in_found_files",
        "replace_in_grep_files",
        "grep_replace_selected",
    }:
        return sync_child_pane(next_state, next_state.current_pane.cursor_path, reduce_state)
    return finalize(next_state)


def _handle_dismiss_about_dialog(
    state: AppState,
    action: DismissAboutDialog,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del action, reduce_state
    return finalize(
        replace(
            state,
            ui_mode="BROWSING",
        )
    )


def _handle_show_about(
    state: AppState,
    action: ShowAbout,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del action, reduce_state
    return finalize(
        replace(
            state,
            ui_mode="ABOUT",
            notification=None,
            command_palette=None,
        )
    )


def _handle_dismiss_attribute_dialog(
    state: AppState,
    action: DismissAttributeDialog,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del action, reduce_state
    return finalize(
        replace(
            state,
            ui_mode="BROWSING",
            notification=None,
            notification_details=None,
            attribute_inspection=None,
            pending_attribute_inspection_request_id=None,
        )
    )


def _handle_show_attributes(
    state: AppState,
    action: ShowAttributes,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del action, reduce_state
    return handle_show_attributes_command(state)


def _handle_attribute_inspection_loaded(
    state: AppState,
    action: AttributeInspectionLoaded,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del reduce_state
    if action.request_id != state.pending_attribute_inspection_request_id:
        return finalize(state)
    return finalize(
        replace(
            state,
            notification=None,
            attribute_inspection=(
                action.inspection
                if state.attribute_inspection is not None
                else None
            ),
            pending_attribute_inspection_request_id=None,
        )
    )


def _handle_attribute_inspection_failed(
    state: AppState,
    action: AttributeInspectionFailed,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del reduce_state
    if action.request_id != state.pending_attribute_inspection_request_id:
        return finalize(state)
    return finalize(
        replace(
            state,
            notification=NotificationState(level="error", message=action.message),
            pending_attribute_inspection_request_id=None,
        )
    )


_PaletteHandler = Callable[[AppState, Action, ReducerFn], ReduceResult]

_PALETTE_HANDLERS: dict[type[Action], _PaletteHandler] = {
    AttributeInspectionLoaded: _handle_attribute_inspection_loaded,
    AttributeInspectionFailed: _handle_attribute_inspection_failed,
    BeginCommandPalette: _handle_begin_command_palette,
    BeginFileSearch: _handle_begin_file_search,
    BeginGrepSearch: _handle_begin_grep_search,
    BeginTextReplace: _handle_begin_text_replace,
    BeginFindAndReplace: lambda s, a, r: _handle_begin_legacy_replace(s, "replace_in_found_files"),
    BeginGrepReplace: lambda s, a, r: _handle_begin_legacy_replace(s, "replace_in_grep_files"),
    BeginGrepReplaceSelected: _handle_begin_grep_replace_selected,
    BeginBookmarkSearch: _dispatch_begin_bookmark_search,
    BeginGo: _handle_begin_go,
    CancelCommandPalette: _handle_cancel_command_palette,
    DismissAboutDialog: _handle_dismiss_about_dialog,
    DismissAttributeDialog: _handle_dismiss_attribute_dialog,
    ShowAbout: _handle_show_about,
    ShowAttributes: _handle_show_attributes,
    MoveCommandPaletteCursor: lambda s, a, r: _handle_move_palette_cursor(s, a),
    SetCommandPaletteQuery: lambda s, a, r: _handle_set_palette_query(s, a),
    SetGrepSearchField: lambda s, a, r: handle_set_grep_search_field(s, a.field, a.value),
    SetGrepSearchScope: lambda s, a, r: handle_set_grep_search_scope(s, a),
    SetReplaceField: lambda s, a, r: handle_set_unified_replace_field(s, a.field, a.value),
    SetReplaceScope: lambda s, a, r: handle_set_replace_scope(s, a),
    CycleGrepSearchField: lambda s, a, r: _handle_cycle_grep_search_field(s, a),
    CycleReplaceField: lambda s, a, r: handle_cycle_unified_replace_field(s, a.delta),
    SetFindReplaceField: lambda s, a, r: handle_set_find_replace_field(s, a.field, a.value),
    CycleFindReplaceField: lambda s, a, r: handle_cycle_find_replace_field(s, a),
    SetGrepReplaceField: lambda s, a, r: handle_set_grep_replace_field(s, a.field, a.value),
    CycleGrepReplaceField: lambda s, a, r: handle_cycle_grep_replace_field(s, a),
    SetGrepReplaceSelectedField: lambda s, a, r: handle_set_grep_replace_selected_field(
        s, a.field, a.value
    ),
    CycleGrepReplaceSelectedField: lambda s, a, r: handle_cycle_grep_replace_selected_field(s, a),
    SetFileSearchTarget: lambda s, a, r: handle_set_file_search_target(s, a),
    CycleFileSearchField: lambda s, a, r: handle_cycle_file_search_field(s, a),
    SubmitCommandPalette: lambda s, a, r: _handle_submit_palette(s, r),
    FileSearchCompleted: lambda s, a, r: handle_file_search_completed(s, a),
    FileSearchFailed: lambda s, a, r: handle_file_search_failed(s, a),
    FileSearchResultsUpdated: lambda s, a, r: handle_file_search_results_updated(s, a),
    GrepSearchCompleted: lambda s, a, r: handle_grep_search_completed(s, a),
    GrepSearchFailed: lambda s, a, r: handle_grep_search_failed(s, a),
    GrepSearchResultsUpdated: lambda s, a, r: handle_grep_search_results_updated(s, a),
    TextReplacePreviewCompleted: lambda s, a, r: handle_text_replace_preview_completed(s, a),
    TextReplacePreviewFailed: lambda s, a, r: handle_text_replace_preview_failed(s, a),
    TextReplaceApplied: lambda s, a, r: handle_text_replace_applied(s, a, r),
    TextReplaceApplyFailed: lambda s, a, r: handle_text_replace_apply_failed(s, a),
    OpenGrepResultInEditor: lambda s, a, r: handle_open_grep_result_in_editor(s, r),
    OpenFindResultInEditor: lambda s, a, r: handle_open_find_result_in_editor(s, r),
    OpenGrepResultInGuiEditor: lambda s, a, r: handle_open_grep_result_in_gui_editor(s, r),
    OpenFindResultInGuiEditor: lambda s, a, r: handle_open_find_result_in_gui_editor(s, r),
    OpenSearchWorkspace: lambda s, a, r: handle_open_search_workspace(s, a, r),
    SaveGrepResults: lambda s, a, r: handle_save_grep_results(s, a),
    GrepExportCompleted: lambda s, a, r: handle_grep_export_completed(s, a),
    GrepExportFailed: lambda s, a, r: handle_grep_export_failed(s, a),
}


def handle_palette_action(
    state: AppState,
    action: Action,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    handler = _PALETTE_HANDLERS.get(type(action))
    if handler is not None:
        return handler(state, action, reduce_state)  # type: ignore[arg-type]
    return None
