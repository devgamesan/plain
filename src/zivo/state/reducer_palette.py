"""Command palette reducer handlers."""

from dataclasses import replace
from pathlib import Path
from typing import Callable

from zivo.archive_utils import is_supported_archive_path

from .actions import (
    Action,
    ActivateNextTab,
    ActivatePreviousTab,
    AddBookmark,
    AttributeInspectionFailed,
    AttributeInspectionLoaded,
    BeginBookmarkSearch,
    BeginCommandPalette,
    BeginCreateInput,
    BeginDeleteTargets,
    BeginEmptyTrash,
    BeginExtractArchiveInput,
    BeginFileSearch,
    BeginFindAndReplace,
    BeginGoToPath,
    BeginGrepReplace,
    BeginGrepReplaceSelected,
    BeginGrepSearch,
    BeginHistorySearch,
    BeginRenameInput,
    BeginSelectedFilesGrep,
    BeginShellCommandInput,
    BeginSymlinkInput,
    BeginTextReplace,
    BeginZipCompressInput,
    CancelCommandPalette,
    CloseCurrentTab,
    CopyPathsToClipboard,
    CopyTargets,
    CutTargets,
    CycleFindReplaceField,
    CycleGrepReplaceField,
    CycleGrepReplaceSelectedField,
    CycleGrepSearchField,
    CycleReplaceField,
    CycleSelectedFilesGrepField,
    DismissAttributeDialog,
    FileSearchCompleted,
    FileSearchFailed,
    GoBack,
    GoForward,
    GoToHomeDirectory,
    GoToTransferHome,
    GrepSearchCompleted,
    GrepSearchFailed,
    MoveCommandPaletteCursor,
    OpenFindResultInEditor,
    OpenGrepResultInEditor,
    OpenNewTab,
    OpenPathInEditor,
    OpenPathWithDefaultApp,
    OpenTerminalAtPath,
    PasteClipboard,
    PasteClipboardToTransferPane,
    ReloadDirectory,
    RemoveBookmark,
    SelectAllVisibleEntries,
    SelectAllVisibleTransferEntries,
    SelectedFilesGrepKeywordChanged,
    SetCommandPaletteQuery,
    SetFindReplaceField,
    SetGrepReplaceField,
    SetGrepReplaceSelectedField,
    SetGrepSearchField,
    SetReplaceField,
    ShowAttributes,
    SubmitCommandPalette,
    TextReplaceApplied,
    TextReplaceApplyFailed,
    TextReplacePreviewCompleted,
    TextReplacePreviewFailed,
    ToggleHiddenFiles,
    ToggleSplitTerminal,
    ToggleTransferMode,
    TransferCopyToOppositePane,
    TransferMoveToOppositePane,
    UndoLastOperation,
)
from .command_palette import get_command_palette_items, normalize_command_palette_cursor
from .effects import ReduceResult, RunAttributeInspectionEffect
from .models import AppState, AttributeInspectionState, ConfigEditorState, NotificationState
from .reducer_common import (
    ReducerFn,
    browser_snapshot_invalidation_paths,
    expand_and_validate_path,
    finalize,
    list_matching_directory_paths,
    single_target_entry,
    single_target_path,
    sync_child_pane,
)
from .reducer_palette_replace import (
    handle_cycle_find_replace_field,
    handle_cycle_grep_replace_field,
    handle_cycle_grep_replace_selected_field,
    handle_cycle_replace_field,
    handle_set_find_replace_field,
    handle_set_grep_replace_field,
    handle_set_grep_replace_selected_field,
    handle_set_replace_field,
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
from .reducer_palette_search import (
    handle_cycle_sfg_field,
    handle_file_search_completed,
    handle_file_search_failed,
    handle_grep_search_completed,
    handle_grep_search_failed,
    handle_open_find_result_in_editor,
    handle_open_grep_result_in_editor,
    handle_set_file_search_query,
    handle_set_grep_search_field,
    handle_sfg_keyword_changed,
    handle_submit_file_search_palette,
    handle_submit_grep_search_palette,
    sync_file_search_preview,
    sync_grep_preview,
    sync_sfg_preview,
)
from .reducer_palette_shared import (
    GREP_SEARCH_FIELDS,
    enter_palette,
    notify,
    request_palette_snapshot,
    restore_browsing_from_palette,
    selected_current_file_paths,
)
from .reducer_transfer import request_transfer_pane_snapshot
from .selectors import select_target_paths, select_visible_current_entry_states


def _handle_begin_history_search(state: AppState) -> ReduceResult:
    if state.layout_mode == "transfer":
        transfer = (
            state.transfer_left
            if state.active_transfer_pane == "left"
            else state.transfer_right
        )
        if transfer is None:
            return finalize(state)
        history_items = tuple(dict.fromkeys(transfer.history.visited_all))
    else:
        history_items = tuple(dict.fromkeys(state.history.visited_all))
    return finalize(enter_palette(state, source="history", history_results=history_items))


def _handle_begin_bookmark_search(state: AppState) -> ReduceResult:
    return finalize(enter_palette(state, source="bookmarks"))


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
    if state.command_palette.source == "go_to_path":
        next_palette = replace(next_palette, go_to_path_selection_active=True)
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
    if state.command_palette.source == "selected_files_grep":
        return sync_sfg_preview(next_state)
    return finalize(next_state)


def _next_palette_query_state(state: AppState, query: str):
    return replace(
        state.command_palette,
        query=query,
        cursor_index=0,
        file_search_error_message=None,
        grep_search_error_message=None,
    )


def _handle_set_go_to_path_query(state: AppState, next_palette, query: str) -> ReduceResult:
    # Transferモード: アクティブペインのパスを基準に補完
    if state.layout_mode == "transfer":
        active_pane = (
            state.transfer_left
            if state.active_transfer_pane == "left"
            else state.transfer_right
        )
        base_path = active_pane.current_path
    else:
        base_path = state.current_path
    matches = list_matching_directory_paths(query, base_path)
    has_trailing_separator = query.endswith("/")
    return finalize(
        replace(
            state,
            command_palette=replace(
                next_palette,
                go_to_path_candidates=matches,
                go_to_path_selection_active=not has_trailing_separator,
            ),
        )
    )


def _handle_set_palette_query(state: AppState, action: SetCommandPaletteQuery) -> ReduceResult:
    if state.command_palette is None:
        return finalize(state)
    next_palette = _next_palette_query_state(state, action.query)
    if state.command_palette.source == "file_search":
        return handle_set_file_search_query(state, next_palette, action.query)
    if state.command_palette.source == "grep_search":
        return handle_set_grep_search_field(state, "keyword", action.query)
    if state.command_palette.source == "go_to_path":
        return _handle_set_go_to_path_query(state, next_palette, action.query)
    if state.command_palette.source == "replace_in_grep_files":
        return handle_set_grep_replace_field(state, "keyword", action.query)
    if state.command_palette.source == "grep_replace_selected":
        return handle_set_grep_replace_selected_field(state, "keyword", action.query)
    if state.command_palette.source == "selected_files_grep":
        return handle_sfg_keyword_changed(
            state,
            SelectedFilesGrepKeywordChanged(keyword=action.query),
        )
    return finalize(replace(state, command_palette=next_palette))


def _handle_cycle_grep_search_field(state: AppState, action: CycleGrepSearchField) -> ReduceResult:
    if state.command_palette is None or state.command_palette.source != "grep_search":
        return finalize(state)
    current_index = GREP_SEARCH_FIELDS.index(state.command_palette.grep_search_active_field)
    next_index = (current_index + action.delta) % len(GREP_SEARCH_FIELDS)
    return finalize(
        replace(
            state,
            command_palette=replace(
                state.command_palette,
                grep_search_active_field=GREP_SEARCH_FIELDS[next_index],
            ),
        )
    )


def _handle_submit_history_palette(state: AppState, reduce_state: ReducerFn) -> ReduceResult:
    items = get_command_palette_items(state)
    if not items:
        return notify(state, level="warning", message="No directory history")
    selected_item = items[
        normalize_command_palette_cursor(state, state.command_palette.cursor_index)
    ]
    if state.layout_mode == "transfer":
        next_state = restore_browsing_from_palette(state)
        return request_transfer_pane_snapshot(
            next_state,
            next_state.active_transfer_pane,
            selected_item.path,
            invalidate_paths=(),
        )
    return request_palette_snapshot(state, reduce_state, path=selected_item.path)


def _handle_submit_bookmarks_palette(state: AppState, reduce_state: ReducerFn) -> ReduceResult:
    items = get_command_palette_items(state)
    if not items:
        return notify(state, level="warning", message="No bookmarks")
    selected_item = items[
        normalize_command_palette_cursor(state, state.command_palette.cursor_index)
    ]
    if selected_item.path is None or not Path(selected_item.path).is_dir():
        return notify(
            state,
            level="error",
            message="Bookmarked path does not exist or is not a directory",
        )
    if state.layout_mode == "transfer":
        return request_transfer_pane_snapshot(
            state,
            state.active_transfer_pane,
            selected_item.path,
            invalidate_paths=(),
        )
    return request_palette_snapshot(state, reduce_state, path=selected_item.path)


def _handle_submit_go_to_path_palette(state: AppState, reduce_state: ReducerFn) -> ReduceResult:
    items = get_command_palette_items(state)
    expanded_path = None
    if items and state.command_palette.go_to_path_selection_active:
        expanded_path = items[
            normalize_command_palette_cursor(state, state.command_palette.cursor_index)
        ].path
    if state.layout_mode == "transfer":
        # Transferモード: アクティブペインのパスを基準に展開
        active_pane = (
            state.transfer_left
            if state.active_transfer_pane == "left"
            else state.transfer_right
        )
        if expanded_path is None:
            expanded_path = expand_and_validate_path(
                state.command_palette.query, active_pane.current_path
            )
        if expanded_path is None:
            return notify(state, level="error", message="Path does not exist or is not a directory")
        next_state = restore_browsing_from_palette(state)
        return request_transfer_pane_snapshot(
            next_state,
            state.active_transfer_pane,
            expanded_path,
            invalidate_paths=(),
        )
    # メイン画面
    if expanded_path is None:
        expanded_path = expand_and_validate_path(state.command_palette.query, state.current_path)
    if expanded_path is None:
        return notify(state, level="error", message="Path does not exist or is not a directory")
    return request_palette_snapshot(state, reduce_state, path=expanded_path)


def _run_new_tab_command(state: AppState, reduce_state: ReducerFn) -> ReduceResult:
    return reduce_state(state, OpenNewTab())


def _run_next_tab_command(state: AppState, reduce_state: ReducerFn) -> ReduceResult:
    return reduce_state(state, ActivateNextTab())


def _run_previous_tab_command(state: AppState, reduce_state: ReducerFn) -> ReduceResult:
    return reduce_state(state, ActivatePreviousTab())


def _run_close_current_tab_command(state: AppState, reduce_state: ReducerFn) -> ReduceResult:
    return reduce_state(state, CloseCurrentTab())


def _run_file_search_command(state: AppState, reduce_state: ReducerFn) -> ReduceResult:
    return reduce_state(state, BeginFileSearch())


def _run_grep_search_command(state: AppState, reduce_state: ReducerFn) -> ReduceResult:
    return reduce_state(state, BeginGrepSearch())


def _run_history_search_command(state: AppState, reduce_state: ReducerFn) -> ReduceResult:
    return reduce_state(state, BeginHistorySearch())


def _run_bookmark_search_command(state: AppState, reduce_state: ReducerFn) -> ReduceResult:
    return reduce_state(state, BeginBookmarkSearch())


def _run_go_back_command(state: AppState, reduce_state: ReducerFn) -> ReduceResult:
    return reduce_state(state, GoBack())


def _run_go_forward_command(state: AppState, reduce_state: ReducerFn) -> ReduceResult:
    return reduce_state(state, GoForward())


def _run_go_to_path_command(state: AppState, reduce_state: ReducerFn) -> ReduceResult:
    return reduce_state(state, BeginGoToPath())


def _run_go_to_home_directory_command(state: AppState, reduce_state: ReducerFn) -> ReduceResult:
    if state.layout_mode == "transfer":
        return reduce_state(state, GoToTransferHome())
    return reduce_state(state, GoToHomeDirectory())


def _run_reload_directory_command(state: AppState, reduce_state: ReducerFn) -> ReduceResult:
    if state.layout_mode == "transfer":
        transfer = _active_transfer_pane(state)
        if transfer is None:
            return finalize(state)
        return request_transfer_pane_snapshot(
            state,
            state.active_transfer_pane,
            transfer.current_path,
            cursor_path=transfer.pane.cursor_path,
            invalidate_paths=browser_snapshot_invalidation_paths(
                transfer.current_path,
                transfer.pane.cursor_path,
            ),
        )
    return reduce_state(state, ReloadDirectory())


def _run_toggle_split_terminal_command(state: AppState, reduce_state: ReducerFn) -> ReduceResult:
    return reduce_state(state, ToggleSplitTerminal())


def _run_select_all_command(state: AppState, reduce_state: ReducerFn) -> ReduceResult:
    if state.layout_mode == "transfer":
        return reduce_state(
            state,
            SelectAllVisibleTransferEntries(paths=_transfer_visible_paths(state)),
        )
    visible_paths = tuple(entry.path for entry in select_visible_current_entry_states(state))
    return reduce_state(state, SelectAllVisibleEntries(visible_paths))


def _run_replace_text_command(
    state: AppState,
    next_state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    target_paths = selected_current_file_paths(state)
    if not target_paths:
        return notify(
            next_state,
            level="warning",
            message=(
                "Replace text requires a selected file or file selection "
                "in the current directory"
            ),
        )
    return reduce_state(next_state, BeginTextReplace(target_paths=target_paths))


def _run_find_and_replace_command(state: AppState, reduce_state: ReducerFn) -> ReduceResult:
    return reduce_state(state, BeginFindAndReplace())


def _run_grep_replace_command(state: AppState, reduce_state: ReducerFn) -> ReduceResult:
    return reduce_state(state, BeginGrepReplace())


def _run_show_attributes_command(state: AppState) -> ReduceResult:
    entry = single_target_entry(state)
    if entry is None:
        return notify(state, level="warning", message="Show attributes requires a single target")
    request_id = state.next_request_id
    return finalize(
        replace(
            state,
            ui_mode="DETAIL",
            notification=None,
            command_palette=None,
            pending_file_search_request_id=None,
            pending_grep_search_request_id=None,
            pending_attribute_inspection_request_id=request_id,
            next_request_id=request_id + 1,
            attribute_inspection=AttributeInspectionState(
                name=entry.name,
                kind=entry.kind,
                path=entry.path,
                symlink=entry.symlink,
                size_bytes=entry.size_bytes,
                modified_at=entry.modified_at,
                hidden=entry.hidden,
                permissions_mode=entry.permissions_mode,
                owner=entry.owner,
                group=entry.group,
            ),
        ),
        RunAttributeInspectionEffect(request_id=request_id, path=entry.path),
    )


def _run_copy_path_command(next_state: AppState, reduce_state: ReducerFn) -> ReduceResult:
    return reduce_state(next_state, CopyPathsToClipboard())


def _run_rename_command(
    state: AppState,
    next_state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    target_path = (
        _transfer_single_target_path(state)
        if state.layout_mode == "transfer"
        else single_target_path(state)
    )
    if target_path is None:
        return notify(next_state, level="warning", message="Rename requires a single target")
    return reduce_state(next_state, BeginRenameInput(path=target_path))


def _run_open_in_editor_command(
    state: AppState,
    next_state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    entry = single_target_entry(state)
    if entry is None:
        return notify(
            next_state,
            level="warning",
            message="Open in editor requires a single target",
        )
    if entry.kind != "file":
        return notify(next_state, level="warning", message="Can only open files in editor")
    return reduce_state(next_state, OpenPathInEditor(path=entry.path))


def _run_extract_archive_command(
    state: AppState,
    next_state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    entry = single_target_entry(state)
    if entry is None:
        return notify(
            next_state,
            level="warning",
            message="Extract archive requires a single target",
        )
    if entry.kind != "file" or not is_supported_archive_path(entry.path):
        return notify(
            next_state,
            level="warning",
            message="Extract archive requires a supported archive file",
        )
    return reduce_state(next_state, BeginExtractArchiveInput(source_path=entry.path))


def _run_compress_as_zip_command(
    state: AppState,
    next_state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    target_paths = select_target_paths(state)
    if not target_paths:
        return notify(
            next_state,
            level="warning",
            message="Compress as zip requires at least one target",
        )
    return reduce_state(next_state, BeginZipCompressInput(source_paths=target_paths))


def _run_delete_targets_command(
    state: AppState,
    next_state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    target_paths = (
        _transfer_target_paths(state)
        if state.layout_mode == "transfer"
        else select_target_paths(state)
    )
    if not target_paths:
        return notify(state, level="warning", message="Nothing to delete")
    return reduce_state(next_state, BeginDeleteTargets(paths=target_paths))


def _run_copy_targets_command(
    state: AppState,
    next_state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    target_paths = (
        _transfer_target_paths(state)
        if state.layout_mode == "transfer"
        else select_target_paths(state)
    )
    if not target_paths:
        return notify(next_state, level="warning", message="Nothing to copy")
    return reduce_state(next_state, CopyTargets(target_paths))


def _run_cut_targets_command(
    state: AppState,
    next_state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    target_paths = (
        _transfer_target_paths(state)
        if state.layout_mode == "transfer"
        else select_target_paths(state)
    )
    if not target_paths:
        return notify(next_state, level="warning", message="Nothing to cut")
    return reduce_state(next_state, CutTargets(target_paths))


def _run_paste_clipboard_command(
    state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    if state.layout_mode == "transfer":
        return reduce_state(state, PasteClipboardToTransferPane())
    return reduce_state(state, PasteClipboard())


def _run_empty_trash_command(state: AppState, reduce_state: ReducerFn) -> ReduceResult:
    return reduce_state(state, BeginEmptyTrash())


def _run_open_file_manager_command(state: AppState, reduce_state: ReducerFn) -> ReduceResult:
    return reduce_state(state, OpenPathWithDefaultApp(state.current_path))


def _run_open_terminal_command(state: AppState, reduce_state: ReducerFn) -> ReduceResult:
    return reduce_state(state, OpenTerminalAtPath(state.current_path))


def _run_shell_command_command(state: AppState, reduce_state: ReducerFn) -> ReduceResult:
    return reduce_state(state, BeginShellCommandInput())


def _run_add_bookmark_command(state: AppState, reduce_state: ReducerFn) -> ReduceResult:
    return reduce_state(state, AddBookmark(path=state.current_path))


def _run_remove_bookmark_command(state: AppState, reduce_state: ReducerFn) -> ReduceResult:
    return reduce_state(state, RemoveBookmark(path=state.current_path))


def _run_toggle_hidden_command(state: AppState, reduce_state: ReducerFn) -> ReduceResult:
    return reduce_state(state, ToggleHiddenFiles())


def _run_edit_config_command(state: AppState) -> ReduceResult:
    return finalize(
        replace(
            state,
            ui_mode="CONFIG",
            notification=None,
            command_palette=None,
            pending_file_search_request_id=None,
            pending_grep_search_request_id=None,
            attribute_inspection=None,
            config_editor=ConfigEditorState(path=state.config_path, draft=state.config),
        )
    )


def _run_create_file_command(state: AppState, reduce_state: ReducerFn) -> ReduceResult:
    return reduce_state(state, BeginCreateInput("file"))


def _run_create_dir_command(state: AppState, reduce_state: ReducerFn) -> ReduceResult:
    return reduce_state(state, BeginCreateInput("dir"))


def _run_create_symlink_command(
    state: AppState,
    next_state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    target_path = single_target_path(state)
    if target_path is None:
        return notify(next_state, level="warning", message="Select one item to create a symlink")
    return reduce_state(next_state, BeginSymlinkInput(source_path=target_path))


def _run_grep_replace_selected_command(
    state: AppState,
    next_state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    target_paths = selected_current_file_paths(state)
    if not target_paths:
        return notify(
            next_state,
            level="warning",
            message=(
                "Grep replace requires a selected file or file selection "
                "in the current directory"
            ),
        )
    return reduce_state(next_state, BeginGrepReplaceSelected(target_paths=target_paths))


def _run_selected_files_grep_command(
    state: AppState,
    next_state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    target_paths = selected_current_file_paths(state)
    if not target_paths:
        return notify(
            next_state,
            level="warning",
            message=(
                "Grep in selected files requires a selected file or file selection "
                "in the current directory"
            ),
        )
    return reduce_state(next_state, BeginSelectedFilesGrep(target_paths=target_paths))


def _run_palette_command_item(
    state: AppState,
    next_state: AppState,
    item_id: str,
    reduce_state: ReducerFn,
) -> ReduceResult:
    if item_id == "new_tab":
        return _run_new_tab_command(next_state, reduce_state)
    if item_id == "next_tab":
        return _run_next_tab_command(next_state, reduce_state)
    if item_id == "previous_tab":
        return _run_previous_tab_command(next_state, reduce_state)
    if item_id == "close_current_tab":
        return _run_close_current_tab_command(next_state, reduce_state)
    if item_id == "file_search":
        return _run_file_search_command(next_state, reduce_state)
    if item_id == "grep_search":
        return _run_grep_search_command(next_state, reduce_state)
    if item_id == "history_search":
        return _run_history_search_command(next_state, reduce_state)
    if item_id == "bookmark_search":
        return _run_bookmark_search_command(next_state, reduce_state)
    if item_id == "go_back":
        return _run_go_back_command(next_state, reduce_state)
    if item_id == "go_forward":
        return _run_go_forward_command(next_state, reduce_state)
    if item_id == "go_to_path":
        return _run_go_to_path_command(next_state, reduce_state)
    if item_id == "go_to_home_directory":
        return _run_go_to_home_directory_command(next_state, reduce_state)
    if item_id == "reload_directory":
        return _run_reload_directory_command(next_state, reduce_state)
    if item_id == "toggle_transfer_mode":
        return reduce_state(next_state, ToggleTransferMode())
    if item_id == "undo_last_operation":
        return reduce_state(next_state, UndoLastOperation())
    if item_id == "copy_targets":
        return _run_copy_targets_command(state, next_state, reduce_state)
    if item_id == "cut_targets":
        return _run_cut_targets_command(state, next_state, reduce_state)
    if item_id == "paste_clipboard":
        return _run_paste_clipboard_command(next_state, reduce_state)
    if item_id == "transfer_copy_to_opposite_pane":
        return reduce_state(next_state, TransferCopyToOppositePane())
    if item_id == "transfer_move_to_opposite_pane":
        return reduce_state(next_state, TransferMoveToOppositePane())
    if item_id == "toggle_split_terminal":
        return _run_toggle_split_terminal_command(next_state, reduce_state)
    if item_id == "select_all":
        return _run_select_all_command(next_state, reduce_state)
    if item_id == "replace_text":
        return _run_replace_text_command(state, next_state, reduce_state)
    if item_id == "replace_in_found_files":
        return _run_find_and_replace_command(next_state, reduce_state)
    if item_id == "replace_in_grep_files":
        return _run_grep_replace_command(next_state, reduce_state)
    if item_id == "grep_replace_selected":
        return _run_grep_replace_selected_command(state, next_state, reduce_state)
    if item_id == "selected_files_grep":
        return _run_selected_files_grep_command(state, next_state, reduce_state)
    if item_id == "show_attributes":
        return reduce_state(next_state, ShowAttributes())
    if item_id == "copy_path":
        return _run_copy_path_command(next_state, reduce_state)
    if item_id == "rename":
        return _run_rename_command(state, next_state, reduce_state)
    if item_id == "create_symlink":
        return _run_create_symlink_command(state, next_state, reduce_state)
    if item_id == "compress_as_zip":
        return _run_compress_as_zip_command(state, next_state, reduce_state)
    if item_id == "extract_archive":
        return _run_extract_archive_command(state, next_state, reduce_state)
    if item_id == "open_in_editor":
        return _run_open_in_editor_command(state, next_state, reduce_state)
    if item_id == "delete_targets":
        return _run_delete_targets_command(state, next_state, reduce_state)
    if item_id == "empty_trash":
        return _run_empty_trash_command(next_state, reduce_state)
    if item_id == "open_file_manager":
        return _run_open_file_manager_command(next_state, reduce_state)
    if item_id == "open_terminal":
        return _run_open_terminal_command(next_state, reduce_state)
    if item_id == "run_shell_command":
        return _run_shell_command_command(next_state, reduce_state)
    if item_id == "add_bookmark":
        return _run_add_bookmark_command(next_state, reduce_state)
    if item_id == "remove_bookmark":
        return _run_remove_bookmark_command(next_state, reduce_state)
    if item_id == "toggle_hidden":
        return _run_toggle_hidden_command(next_state, reduce_state)
    if item_id == "edit_config":
        return _run_edit_config_command(state)
    if item_id == "create_file":
        return _run_create_file_command(next_state, reduce_state)
    if item_id == "create_dir":
        return _run_create_dir_command(next_state, reduce_state)
    return finalize(next_state)


def _handle_submit_commands_palette(state: AppState, reduce_state: ReducerFn) -> ReduceResult:
    items = get_command_palette_items(state)
    if not items:
        return notify(state, level="warning", message="No matching command")
    selected_item = items[
        normalize_command_palette_cursor(state, state.command_palette.cursor_index)
    ]
    if not selected_item.enabled:
        return notify(
            state,
            level="warning",
            message=f"{selected_item.label} is not available yet",
        )
    next_state = restore_browsing_from_palette(state)
    return _run_palette_command_item(state, next_state, selected_item.id, reduce_state)


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
    if state.command_palette.source == "selected_files_grep":
        return handle_submit_grep_search_palette(state, reduce_state)
    if state.command_palette.source == "history":
        return _handle_submit_history_palette(state, reduce_state)
    if state.command_palette.source == "bookmarks":
        return _handle_submit_bookmarks_palette(state, reduce_state)
    if state.command_palette.source == "go_to_path":
        return _handle_submit_go_to_path_palette(state, reduce_state)
    return _handle_submit_commands_palette(state, reduce_state)


def _handle_begin_command_palette(
    state: AppState,
    action: BeginCommandPalette,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del action, reduce_state
    return finalize(enter_palette(state))


def _active_transfer_pane(state: AppState):
    if state.layout_mode != "transfer":
        return None
    if state.active_transfer_pane == "left":
        return state.transfer_left
    return state.transfer_right


def _transfer_visible_paths(state: AppState) -> tuple[str, ...]:
    transfer = _active_transfer_pane(state)
    if transfer is None:
        return ()
    transfer_state = replace(
        state,
        current_pane=transfer.pane,
        filter=replace(state.filter, query="", active=False),
    )
    return tuple(entry.path for entry in select_visible_current_entry_states(transfer_state))


def _transfer_target_paths(state: AppState) -> tuple[str, ...]:
    transfer = _active_transfer_pane(state)
    if transfer is None:
        return ()
    visible_paths = _transfer_visible_paths(state)
    selected_paths = tuple(
        path for path in visible_paths if path in transfer.pane.selected_paths
    )
    if selected_paths:
        return selected_paths
    if transfer.pane.cursor_path in visible_paths:
        return (transfer.pane.cursor_path,)
    return ()


def _transfer_single_target_path(state: AppState) -> str | None:
    target_paths = _transfer_target_paths(state)
    if len(target_paths) != 1:
        return None
    return target_paths[0]


def _handle_begin_file_search(
    state: AppState,
    action: BeginFileSearch,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del action, reduce_state
    return finalize(enter_palette(state, source="file_search"))


def _handle_begin_grep_search(
    state: AppState,
    action: BeginGrepSearch,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del action, reduce_state
    return finalize(enter_palette(state, source="grep_search"))


def _handle_begin_text_replace(
    state: AppState,
    action: BeginTextReplace,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del reduce_state
    next_state = enter_palette(state, source="replace_text")
    return finalize(
        replace(
            next_state,
            command_palette=replace(
                next_state.command_palette,
                replace_target_paths=action.target_paths,
            ),
        )
    )


def _handle_begin_find_and_replace(
    state: AppState,
    action: BeginFindAndReplace,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del action, reduce_state
    return finalize(enter_palette(state, source="replace_in_found_files"))


def _handle_begin_grep_replace(
    state: AppState,
    action: BeginGrepReplace,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del action, reduce_state
    return finalize(enter_palette(state, source="replace_in_grep_files"))


def _handle_begin_grep_replace_selected(
    state: AppState,
    action: BeginGrepReplaceSelected,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del reduce_state
    next_state = enter_palette(state, source="grep_replace_selected")
    return finalize(
        replace(
            next_state,
            command_palette=replace(
                next_state.command_palette,
                grs_target_paths=action.target_paths,
            ),
        )
    )


def _handle_begin_selected_files_grep(
    state: AppState,
    action: BeginSelectedFilesGrep,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del reduce_state
    next_state = enter_palette(state, source="selected_files_grep")
    return finalize(
        replace(
            next_state,
            command_palette=replace(
                next_state.command_palette,
                sfg_target_paths=action.target_paths,
            ),
        )
    )


def _dispatch_begin_history_search(
    state: AppState,
    action: BeginHistorySearch,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del action, reduce_state
    return _handle_begin_history_search(state)


def _dispatch_begin_bookmark_search(
    state: AppState,
    action: BeginBookmarkSearch,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del action, reduce_state
    return _handle_begin_bookmark_search(state)


def _handle_begin_go_to_path(
    state: AppState,
    action: BeginGoToPath,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del action, reduce_state
    return finalize(enter_palette(state, source="go_to_path"))


def _handle_cancel_command_palette(
    state: AppState,
    action: CancelCommandPalette,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del action
    next_state = restore_browsing_from_palette(state, clear_name_conflict=True)
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
    return _run_show_attributes_command(state)


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
    BeginFindAndReplace: _handle_begin_find_and_replace,
    BeginGrepReplace: _handle_begin_grep_replace,
    BeginGrepReplaceSelected: _handle_begin_grep_replace_selected,
    BeginSelectedFilesGrep: _handle_begin_selected_files_grep,
    BeginHistorySearch: _dispatch_begin_history_search,
    BeginBookmarkSearch: _dispatch_begin_bookmark_search,
    BeginGoToPath: _handle_begin_go_to_path,
    CancelCommandPalette: _handle_cancel_command_palette,
    DismissAttributeDialog: _handle_dismiss_attribute_dialog,
    ShowAttributes: _handle_show_attributes,
    MoveCommandPaletteCursor: lambda s, a, r: _handle_move_palette_cursor(s, a),
    SetCommandPaletteQuery: lambda s, a, r: _handle_set_palette_query(s, a),
    SetGrepSearchField: lambda s, a, r: handle_set_grep_search_field(s, a.field, a.value),
    SetReplaceField: lambda s, a, r: handle_set_replace_field(s, a.field, a.value),
    CycleGrepSearchField: lambda s, a, r: _handle_cycle_grep_search_field(s, a),
    CycleReplaceField: lambda s, a, r: handle_cycle_replace_field(s, a),
    SetFindReplaceField: lambda s, a, r: handle_set_find_replace_field(s, a.field, a.value),
    CycleFindReplaceField: lambda s, a, r: handle_cycle_find_replace_field(s, a),
    SetGrepReplaceField: lambda s, a, r: handle_set_grep_replace_field(s, a.field, a.value),
    SetGrepReplaceSelectedField: lambda s, a, r: handle_set_grep_replace_selected_field(
        s,
        a.field,
        a.value,
    ),
    SelectedFilesGrepKeywordChanged: lambda s, a, r: handle_sfg_keyword_changed(s, a),
    CycleGrepReplaceField: lambda s, a, r: handle_cycle_grep_replace_field(s, a),
    CycleGrepReplaceSelectedField: lambda s, a, r: handle_cycle_grep_replace_selected_field(s, a),
    CycleSelectedFilesGrepField: lambda s, a, r: handle_cycle_sfg_field(s, a),
    SubmitCommandPalette: lambda s, a, r: _handle_submit_palette(s, r),
    FileSearchCompleted: lambda s, a, r: handle_file_search_completed(s, a),
    FileSearchFailed: lambda s, a, r: handle_file_search_failed(s, a),
    GrepSearchCompleted: lambda s, a, r: handle_grep_search_completed(s, a),
    GrepSearchFailed: lambda s, a, r: handle_grep_search_failed(s, a),
    TextReplacePreviewCompleted: lambda s, a, r: handle_text_replace_preview_completed(s, a),
    TextReplacePreviewFailed: lambda s, a, r: handle_text_replace_preview_failed(s, a),
    TextReplaceApplied: lambda s, a, r: handle_text_replace_applied(s, a, r),
    TextReplaceApplyFailed: lambda s, a, r: handle_text_replace_apply_failed(s, a),
    OpenGrepResultInEditor: lambda s, a, r: handle_open_grep_result_in_editor(s, r),
    OpenFindResultInEditor: lambda s, a, r: handle_open_find_result_in_editor(s, r),
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
