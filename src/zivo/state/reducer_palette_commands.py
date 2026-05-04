"""Command execution helpers for the command palette reducer."""

from dataclasses import replace

from zivo.archive_utils import is_supported_archive_path
from zivo.models import (
    CustomActionContext,
    CustomActionExpansionError,
    expand_custom_action,
)

from .actions import (
    ActivateNextTab,
    ActivatePreviousTab,
    AddBookmark,
    BeginBookmarkSearch,
    BeginCreateInput,
    BeginCustomActionConfirmation,
    BeginDeleteTargets,
    BeginEmptyTrash,
    BeginExitCurrentPath,
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
    CloseCurrentTab,
    CopyPathsToClipboard,
    CopyTargets,
    CutTargets,
    GoBack,
    GoForward,
    GoToHomeDirectory,
    GoToTransferHome,
    OpenNewTab,
    OpenPathInEditor,
    OpenPathInGuiEditor,
    OpenPathWithDefaultApp,
    OpenTerminalAtPath,
    PasteClipboard,
    PasteClipboardToTransferPane,
    ReloadDirectory,
    RemoveBookmark,
    SelectAllVisibleEntries,
    SelectAllVisibleTransferEntries,
    ShowAbout,
    ShowAttributes,
    ToggleHiddenFiles,
    ToggleTransferMode,
    TransferCopyToOppositePane,
    TransferMoveToOppositePane,
    UndoLastOperation,
)
from .command_palette import get_command_palette_items, normalize_command_palette_cursor
from .effects import ReduceResult, RunAttributeInspectionEffect
from .models import AppState, AttributeInspectionState, ConfigEditorState
from .reducer_common import (
    ReducerFn,
    browser_snapshot_invalidation_paths,
    finalize,
    single_target_entry,
    single_target_path,
)
from .reducer_palette_shared import (
    notify,
    restore_browsing_from_palette,
    selected_current_file_paths,
)
from .reducer_transfer import request_transfer_pane_snapshot
from .selectors import select_target_paths, select_visible_current_entry_states


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


def handle_show_attributes_command(state: AppState) -> ReduceResult:
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


def _run_open_in_gui_editor_command(
    state: AppState,
    next_state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    entry = single_target_entry(state)
    if entry is None:
        return notify(
            next_state,
            level="warning",
            message="Open in GUI editor requires a single target",
        )
    if entry.kind != "file":
        return notify(next_state, level="warning", message="Can only open files in GUI editor")
    return reduce_state(next_state, OpenPathInGuiEditor(path=entry.path))


def _run_open_current_directory_in_gui_editor_command(
    state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return reduce_state(state, OpenPathInGuiEditor(path=state.current_path))


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


def _run_exit_command(state: AppState, reduce_state: ReducerFn) -> ReduceResult:
    return reduce_state(state, BeginExitCurrentPath())


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


def _run_custom_action_command(
    state: AppState,
    next_state: AppState,
    item_id: str,
    reduce_state: ReducerFn,
) -> ReduceResult:
    try:
        action_index = int(item_id.split(":", 1)[1])
        action = state.config.actions.custom[action_index]
    except (IndexError, ValueError):
        return notify(next_state, level="warning", message="Custom action is no longer available")

    target_files = selected_current_file_paths(state)
    focused_file = target_files[0] if len(target_files) == 1 else None
    context = CustomActionContext(
        cwd=state.current_path,
        focused_file=focused_file,
        selection=select_target_paths(state),
    )
    try:
        request = expand_custom_action(action, context)
    except CustomActionExpansionError as error:
        return notify(next_state, level="error", message=str(error))
    return reduce_state(next_state, BeginCustomActionConfirmation(request))


def _run_palette_command_item(
    state: AppState,
    next_state: AppState,
    item_id: str,
    reduce_state: ReducerFn,
) -> ReduceResult:
    if item_id.startswith("custom_action:"):
        return _run_custom_action_command(state, next_state, item_id, reduce_state)
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
    if item_id == "exit":
        return _run_exit_command(next_state, reduce_state)
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
    if item_id == "show_about":
        return reduce_state(next_state, ShowAbout())
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
    if item_id == "open_in_gui_editor":
        return _run_open_in_gui_editor_command(state, next_state, reduce_state)
    if item_id == "delete_targets":
        return _run_delete_targets_command(state, next_state, reduce_state)
    if item_id == "empty_trash":
        return _run_empty_trash_command(next_state, reduce_state)
    if item_id == "open_file_manager":
        return _run_open_file_manager_command(next_state, reduce_state)
    if item_id == "open_current_directory_in_gui_editor":
        return _run_open_current_directory_in_gui_editor_command(next_state, reduce_state)
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


def handle_submit_commands_palette(state: AppState, reduce_state: ReducerFn) -> ReduceResult:
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
