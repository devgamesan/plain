"""Command palette reducer handlers."""

import re
from dataclasses import replace
from pathlib import Path
from typing import Callable

from zivo.archive_utils import is_supported_archive_path
from zivo.models import TextReplaceRequest
from zivo.models.external_launch import ExternalLaunchRequest

from .actions import (
    Action,
    ActivateNextTab,
    ActivatePreviousTab,
    AddBookmark,
    BeginBookmarkSearch,
    BeginCommandPalette,
    BeginCreateInput,
    BeginDeleteTargets,
    BeginEmptyTrash,
    BeginExtractArchiveInput,
    BeginFileSearch,
    BeginGoToPath,
    BeginGrepSearch,
    BeginHistorySearch,
    BeginRenameInput,
    BeginShellCommandInput,
    BeginTextReplace,
    BeginZipCompressInput,
    CancelCommandPalette,
    CloseCurrentTab,
    CopyPathsToClipboard,
    CycleGrepSearchField,
    CycleReplaceField,
    DismissAttributeDialog,
    FileSearchCompleted,
    FileSearchFailed,
    GoBack,
    GoForward,
    GoToHomeDirectory,
    GrepSearchCompleted,
    GrepSearchFailed,
    MoveCommandPaletteCursor,
    OpenFindResultInEditor,
    OpenGrepResultInEditor,
    OpenNewTab,
    OpenPathInEditor,
    OpenPathWithDefaultApp,
    OpenTerminalAtPath,
    ReloadDirectory,
    RemoveBookmark,
    RequestBrowserSnapshot,
    SelectAllVisibleEntries,
    SetCommandPaletteQuery,
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
    UndoLastOperation,
)
from .command_palette import get_command_palette_items, normalize_command_palette_cursor
from .effects import (
    LoadChildPaneSnapshotEffect,
    ReduceResult,
    RunFileSearchEffect,
    RunGrepSearchEffect,
    RunTextReplaceApplyEffect,
    RunTextReplacePreviewEffect,
)
from .models import (
    AppState,
    AttributeInspectionState,
    CommandPaletteState,
    ConfigEditorState,
    FileSearchResultState,
    GrepSearchFieldId,
    GrepSearchResultState,
    NotificationState,
    PaneState,
    ReplaceFieldId,
    ReplacePreviewResultState,
)
from .reducer_common import (
    ReducerFn,
    browser_snapshot_invalidation_paths,
    expand_and_validate_path,
    filter_file_search_results,
    finalize,
    is_regex_file_search_query,
    list_matching_directory_paths,
    run_external_launch_request,
    single_target_entry,
    single_target_path,
    sync_child_pane,
)
from .selectors import select_target_paths, select_visible_current_entry_states

_GREP_SEARCH_FIELDS: tuple[GrepSearchFieldId, ...] = ("keyword", "include", "exclude")
_REPLACE_FIELDS: tuple[ReplaceFieldId, ...] = ("find", "replace")
_EXTENSION_SEPARATOR_RE = re.compile(r"[\s,]+")
_VALID_EXTENSION_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]*")


def _grep_field_value(
    palette: CommandPaletteState,
    field: GrepSearchFieldId,
) -> str:
    if field == "keyword":
        return palette.grep_search_keyword
    if field == "include":
        return palette.grep_search_include_extensions
    return palette.grep_search_exclude_extensions


def _replace_grep_field(
    palette: CommandPaletteState,
    *,
    field: GrepSearchFieldId,
    value: str,
) -> CommandPaletteState:
    if field == "keyword":
        return replace(palette, query=value, grep_search_keyword=value)
    if field == "include":
        return replace(palette, grep_search_include_extensions=value)
    return replace(palette, grep_search_exclude_extensions=value)


def _replace_field_value(
    palette: CommandPaletteState,
    field: ReplaceFieldId,
) -> str:
    if field == "find":
        return palette.replace_find_text
    return palette.replace_replacement_text


def _replace_replace_field(
    palette: CommandPaletteState,
    *,
    field: ReplaceFieldId,
    value: str,
) -> CommandPaletteState:
    if field == "find":
        return replace(palette, replace_find_text=value)
    return replace(palette, replace_replacement_text=value)


def _normalize_grep_extension_filters(
    raw_value: str,
    *,
    label: str,
) -> tuple[str, ...]:
    normalized_globs: list[str] = []
    seen: set[str] = set()
    for token in _EXTENSION_SEPARATOR_RE.split(raw_value.strip()):
        if not token:
            continue
        normalized_token = token.strip().lstrip(".").casefold()
        if not normalized_token or not _VALID_EXTENSION_RE.fullmatch(normalized_token):
            raise ValueError(f"Invalid {label} extension: {token}")
        glob = f"*.{normalized_token}"
        if glob not in seen:
            seen.add(glob)
            normalized_globs.append(glob)
    return tuple(normalized_globs)


def _validate_grep_search_filters(
    palette: CommandPaletteState,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    include_globs = _normalize_grep_extension_filters(
        palette.grep_search_include_extensions,
        label="include",
    )
    exclude_globs = _normalize_grep_extension_filters(
        palette.grep_search_exclude_extensions,
        label="exclude",
    )
    conflicts = tuple(sorted(set(include_globs) & set(exclude_globs)))
    if conflicts:
        formatted = ", ".join(glob.removeprefix("*.") for glob in conflicts)
        raise ValueError(
            f"Extensions cannot be included and excluded at the same time: {formatted}"
        )
    return include_globs, exclude_globs


def _notify(
    state: AppState,
    *,
    level: str,
    message: str,
) -> ReduceResult:
    return finalize(
        replace(
            state,
            notification=NotificationState(level=level, message=message),
        )
    )


def _enter_palette(
    state: AppState,
    *,
    source: str = "commands",
    history_results: tuple[str, ...] = (),
) -> AppState:
    return replace(
        state,
        ui_mode="PALETTE",
        notification=None,
        pending_input=None,
        command_palette=CommandPaletteState(
            source=source,
            history_results=history_results,
        ),
        pending_file_search_request_id=None,
        pending_grep_search_request_id=None,
        pending_replace_preview_request_id=None,
        pending_replace_apply_request_id=None,
        delete_confirmation=None,
        name_conflict=None,
        attribute_inspection=None,
    )


def _restore_browsing_from_palette(
    state: AppState,
    *,
    clear_name_conflict: bool = False,
) -> AppState:
    next_state = replace(
        state,
        ui_mode="BROWSING",
        notification=None,
        command_palette=None,
        pending_file_search_request_id=None,
        pending_grep_search_request_id=None,
        pending_replace_preview_request_id=None,
        pending_replace_apply_request_id=None,
        attribute_inspection=None,
    )
    if clear_name_conflict:
        next_state = replace(next_state, name_conflict=None)
    return next_state


def _request_palette_snapshot(
    state: AppState,
    reduce_state: ReducerFn,
    *,
    path: str,
    cursor_path: str | None = None,
) -> ReduceResult:
    return reduce_state(
        _restore_browsing_from_palette(state),
        RequestBrowserSnapshot(path, cursor_path=cursor_path, blocking=True),
    )


def _handle_begin_history_search(state: AppState) -> ReduceResult:
    history_items = tuple(dict.fromkeys(state.history.visited_all))
    return finalize(_enter_palette(state, source="history", history_results=history_items))


def _handle_begin_bookmark_search(state: AppState) -> ReduceResult:
    return finalize(_enter_palette(state, source="bookmarks"))


def _handle_move_palette_cursor(
    state: AppState,
    action: MoveCommandPaletteCursor,
) -> ReduceResult:
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
    next_state = replace(
        state,
        command_palette=next_palette,
    )
    if state.command_palette.source == "file_search":
        return _sync_file_search_preview(next_state)
    if state.command_palette.source == "grep_search":
        return _sync_grep_preview(next_state)
    if state.command_palette.source == "replace_text":
        return _sync_replace_preview(next_state)
    return finalize(next_state)


def _next_palette_query_state(state: AppState, query: str) -> CommandPaletteState:
    return replace(
        state.command_palette,
        query=query,
        cursor_index=0,
        file_search_error_message=None,
        grep_search_error_message=None,
    )


def _handle_set_palette_query(
    state: AppState,
    action: SetCommandPaletteQuery,
) -> ReduceResult:
    if state.command_palette is None:
        return finalize(state)

    next_palette = _next_palette_query_state(state, action.query)

    if state.command_palette.source == "file_search":
        return _handle_set_file_search_query(state, next_palette, action.query)
    if state.command_palette.source == "grep_search":
        return _handle_set_grep_search_field(state, "keyword", action.query)
    if state.command_palette.source == "go_to_path":
        return _handle_set_go_to_path_query(state, next_palette, action.query)
    return finalize(replace(state, command_palette=next_palette))


def _handle_set_file_search_query(
    state: AppState,
    next_palette: CommandPaletteState,
    query: str,
) -> ReduceResult:
    stripped_query = query.strip()
    if not stripped_query:
        return _sync_file_search_preview(
            replace(
                state,
                command_palette=replace(
                    next_palette,
                    file_search_results=(),
                    file_search_error_message=None,
                ),
                pending_file_search_request_id=None,
                pending_grep_search_request_id=None,
                pending_child_pane_request_id=None,
            )
        )

    is_regex_query = is_regex_file_search_query(stripped_query)
    normalized_query = stripped_query.casefold()
    if (
        not is_regex_query
        and state.command_palette.file_search_cache_query
        and normalized_query.startswith(state.command_palette.file_search_cache_query)
        and state.command_palette.file_search_cache_root_path == state.current_path
        and state.command_palette.file_search_cache_show_hidden == state.show_hidden
    ):
        return _sync_file_search_preview(
            replace(
                state,
                command_palette=replace(
                    next_palette,
                    file_search_results=filter_file_search_results(
                        state.command_palette.file_search_cache_results,
                        normalized_query,
                    ),
                ),
                pending_file_search_request_id=None,
                pending_grep_search_request_id=None,
            )
        )

    request_id = state.next_request_id
    next_state = replace(
        state,
        command_palette=next_palette,
        pending_file_search_request_id=request_id,
        pending_grep_search_request_id=None,
        next_request_id=request_id + 1,
    )
    return finalize(
        next_state,
        RunFileSearchEffect(
            request_id=request_id,
            root_path=state.current_path,
            query=stripped_query,
            show_hidden=state.show_hidden,
        ),
    )


def _handle_set_grep_search_field(
    state: AppState,
    field: GrepSearchFieldId,
    value: str,
) -> ReduceResult:
    next_palette = replace(
        _replace_grep_field(state.command_palette, field=field, value=value),
        grep_search_error_message=None,
        cursor_index=0,
    )
    stripped_query = next_palette.grep_search_keyword.strip()
    if not stripped_query:
        return _sync_grep_preview(
            replace(
                state,
                command_palette=replace(
                    next_palette,
                    grep_search_results=(),
                    grep_search_error_message=None,
                ),
                pending_grep_search_request_id=None,
                pending_child_pane_request_id=None,
            )
        )

    try:
        include_globs, exclude_globs = _validate_grep_search_filters(next_palette)
    except ValueError as error:
        return _sync_grep_preview(
            replace(
                state,
                command_palette=replace(
                    next_palette,
                    grep_search_results=(),
                    grep_search_error_message=str(error),
                ),
                pending_grep_search_request_id=None,
                pending_child_pane_request_id=None,
            )
        )

    request_id = state.next_request_id
    next_state = replace(
        state,
        command_palette=next_palette,
        pending_grep_search_request_id=request_id,
        next_request_id=request_id + 1,
    )
    return finalize(
        next_state,
        RunGrepSearchEffect(
            request_id=request_id,
            root_path=state.current_path,
            query=stripped_query,
            show_hidden=state.show_hidden,
            include_globs=include_globs,
            exclude_globs=exclude_globs,
        ),
    )


def _handle_set_replace_field(
    state: AppState,
    field: ReplaceFieldId,
    value: str,
) -> ReduceResult:
    next_palette = replace(
        _replace_replace_field(state.command_palette, field=field, value=value),
        replace_error_message=None,
        replace_status_message=None,
        cursor_index=0,
    )
    find_text = next_palette.replace_find_text.strip()
    if not find_text:
        return finalize(
            replace(
                state,
                command_palette=replace(
                    next_palette,
                    replace_preview_results=(),
                    replace_total_match_count=0,
                ),
                child_pane=PaneState(directory_path=state.current_path, entries=()),
                pending_replace_preview_request_id=None,
            )
        )

    request_id = state.next_request_id
    request = TextReplaceRequest(
        paths=next_palette.replace_target_paths,
        find_text=next_palette.replace_find_text,
        replace_text=next_palette.replace_replacement_text,
    )
    return finalize(
        replace(
            state,
            command_palette=next_palette,
            pending_replace_preview_request_id=request_id,
            next_request_id=request_id + 1,
        ),
        RunTextReplacePreviewEffect(request_id=request_id, request=request),
    )


def _handle_cycle_replace_field(
    state: AppState,
    action: CycleReplaceField,
) -> ReduceResult:
    if state.command_palette is None or state.command_palette.source != "replace_text":
        return finalize(state)
    current_index = _REPLACE_FIELDS.index(state.command_palette.replace_active_field)
    next_index = (current_index + action.delta) % len(_REPLACE_FIELDS)
    return finalize(
        replace(
            state,
            command_palette=replace(
                state.command_palette,
                replace_active_field=_REPLACE_FIELDS[next_index],
            ),
        )
    )


def _handle_cycle_grep_search_field(
    state: AppState,
    action: CycleGrepSearchField,
) -> ReduceResult:
    if state.command_palette is None or state.command_palette.source != "grep_search":
        return finalize(state)
    current_index = _GREP_SEARCH_FIELDS.index(state.command_palette.grep_search_active_field)
    next_index = (current_index + action.delta) % len(_GREP_SEARCH_FIELDS)
    return finalize(
        replace(
            state,
            command_palette=replace(
                state.command_palette,
                grep_search_active_field=_GREP_SEARCH_FIELDS[next_index],
            ),
        )
    )


def _handle_set_go_to_path_query(
    state: AppState,
    next_palette: CommandPaletteState,
    query: str,
) -> ReduceResult:
    matches = list_matching_directory_paths(query, state.current_path)
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


def _handle_submit_palette(
    state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    if state.command_palette is None:
        return finalize(state)

    if state.command_palette.source == "file_search":
        return _handle_submit_file_search_palette(state, reduce_state)
    if state.command_palette.source == "grep_search":
        return _handle_submit_grep_search_palette(state, reduce_state)
    if state.command_palette.source == "replace_text":
        return _handle_submit_replace_palette(state)
    if state.command_palette.source == "history":
        return _handle_submit_history_palette(state, reduce_state)
    if state.command_palette.source == "bookmarks":
        return _handle_submit_bookmarks_palette(state, reduce_state)
    if state.command_palette.source == "go_to_path":
        return _handle_submit_go_to_path_palette(state, reduce_state)
    return _handle_submit_commands_palette(state, reduce_state)


def _handle_submit_file_search_palette(
    state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    results = state.command_palette.file_search_results
    message = state.command_palette.file_search_error_message or "No matching files"
    if not results:
        return _notify(state, level="warning", message=message)

    selected_result = results[
        normalize_command_palette_cursor(state, state.command_palette.cursor_index)
    ]
    return _request_palette_snapshot(
        state,
        reduce_state,
        path=str(Path(selected_result.path).parent),
        cursor_path=selected_result.path,
    )


def _handle_submit_grep_search_palette(
    state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    results = state.command_palette.grep_search_results
    message = state.command_palette.grep_search_error_message or "No matching lines"
    if not results:
        return _notify(state, level="warning", message=message)

    selected_result = results[
        normalize_command_palette_cursor(state, state.command_palette.cursor_index)
    ]
    return _request_palette_snapshot(
        state,
        reduce_state,
        path=str(Path(selected_result.path).parent),
        cursor_path=selected_result.path,
    )


def _handle_open_grep_result_in_editor(
    state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    results = state.command_palette.grep_search_results
    message = state.command_palette.grep_search_error_message or "No matching lines"
    if not results:
        return _notify(state, level="warning", message=message)

    selected_result = results[
        normalize_command_palette_cursor(state, state.command_palette.cursor_index)
    ]
    return run_external_launch_request(
        replace(state, notification=None),
        ExternalLaunchRequest(
            kind="open_editor",
            path=selected_result.path,
            line_number=selected_result.line_number,
        ),
    )


def _handle_open_find_result_in_editor(
    state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    results = state.command_palette.file_search_results
    message = state.command_palette.file_search_error_message or "No matching files"
    if not results:
        return _notify(state, level="warning", message=message)

    selected_result = results[
        normalize_command_palette_cursor(state, state.command_palette.cursor_index)
    ]
    return run_external_launch_request(
        replace(state, notification=None),
        ExternalLaunchRequest(
            kind="open_editor",
            path=selected_result.path,
            line_number=None,  # File search doesn't have line numbers
        ),
    )


def _handle_submit_replace_palette(state: AppState) -> ReduceResult:
    if state.pending_replace_preview_request_id is not None:
        return _notify(state, level="warning", message="Replacement preview is still running")
    if state.command_palette is None:
        return finalize(state)
    if not state.command_palette.replace_find_text.strip():
        return _notify(state, level="warning", message="Find text is required")
    if state.command_palette.replace_error_message is not None:
        return _notify(state, level="warning", message=state.command_palette.replace_error_message)
    if not state.command_palette.replace_preview_results:
        message = state.command_palette.replace_status_message or "No matching files"
        return _notify(state, level="warning", message=message)

    request_id = state.next_request_id
    request = TextReplaceRequest(
        paths=state.command_palette.replace_target_paths,
        find_text=state.command_palette.replace_find_text,
        replace_text=state.command_palette.replace_replacement_text,
    )
    next_state = _restore_browsing_from_palette(state)
    return finalize(
        replace(
            next_state,
            pending_replace_apply_request_id=request_id,
            next_request_id=request_id + 1,
            notification=NotificationState(level="info", message="Applying replacement..."),
        ),
        RunTextReplaceApplyEffect(request_id=request_id, request=request),
    )


def _handle_submit_history_palette(
    state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    items = get_command_palette_items(state)
    if not items:
        return _notify(state, level="warning", message="No directory history")

    selected_item = items[
        normalize_command_palette_cursor(state, state.command_palette.cursor_index)
    ]
    return _request_palette_snapshot(
        state,
        reduce_state,
        path=selected_item.path,
    )


def _handle_submit_bookmarks_palette(
    state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    items = get_command_palette_items(state)
    if not items:
        return _notify(state, level="warning", message="No bookmarks")

    selected_item = items[
        normalize_command_palette_cursor(state, state.command_palette.cursor_index)
    ]
    if selected_item.path is None or not Path(selected_item.path).is_dir():
        return _notify(
            state,
            level="error",
            message="Bookmarked path does not exist or is not a directory",
        )
    return _request_palette_snapshot(
        state,
        reduce_state,
        path=selected_item.path,
    )


def _handle_submit_go_to_path_palette(
    state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    items = get_command_palette_items(state)
    expanded_path = None
    if items and state.command_palette.go_to_path_selection_active:
        expanded_path = items[
            normalize_command_palette_cursor(state, state.command_palette.cursor_index)
        ].path
    if expanded_path is None:
        expanded_path = expand_and_validate_path(
            state.command_palette.query,
            state.current_path,
        )
    if expanded_path is None:
        return _notify(
            state,
            level="error",
            message="Path does not exist or is not a directory",
        )
    return _request_palette_snapshot(
        state,
        reduce_state,
        path=expanded_path,
    )


def _handle_submit_commands_palette(
    state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    items = get_command_palette_items(state)
    if not items:
        return _notify(state, level="warning", message="No matching command")

    selected_item = items[
        normalize_command_palette_cursor(state, state.command_palette.cursor_index)
    ]
    if not selected_item.enabled:
        return _notify(
            state,
            level="warning",
            message=f"{selected_item.label} is not available yet",
        )

    next_state = _restore_browsing_from_palette(state)
    return _run_palette_command_item(state, next_state, selected_item.id, reduce_state)


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
    if item_id == "undo_last_operation":
        return reduce_state(next_state, UndoLastOperation())
    if item_id == "toggle_split_terminal":
        return _run_toggle_split_terminal_command(next_state, reduce_state)
    if item_id == "select_all":
        return _run_select_all_command(next_state, reduce_state)
    if item_id == "replace_text":
        return _run_replace_text_command(state, next_state, reduce_state)
    if item_id == "show_attributes":
        return reduce_state(next_state, ShowAttributes())
    if item_id == "copy_path":
        return _run_copy_path_command(next_state, reduce_state)
    if item_id == "rename":
        return _run_rename_command(state, next_state, reduce_state)
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


def _run_new_tab_command(
    state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return reduce_state(state, OpenNewTab())


def _run_next_tab_command(
    state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return reduce_state(state, ActivateNextTab())


def _run_previous_tab_command(
    state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return reduce_state(state, ActivatePreviousTab())


def _run_close_current_tab_command(
    state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return reduce_state(state, CloseCurrentTab())


def _run_file_search_command(
    state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return reduce_state(state, BeginFileSearch())


def _run_grep_search_command(
    state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return reduce_state(state, BeginGrepSearch())


def _run_history_search_command(
    state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return reduce_state(state, BeginHistorySearch())


def _run_bookmark_search_command(
    state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return reduce_state(state, BeginBookmarkSearch())


def _run_go_back_command(
    state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return reduce_state(state, GoBack())


def _run_go_forward_command(
    state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return reduce_state(state, GoForward())


def _run_go_to_path_command(
    state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return reduce_state(state, BeginGoToPath())


def _run_go_to_home_directory_command(
    state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return reduce_state(state, GoToHomeDirectory())


def _run_reload_directory_command(
    state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return reduce_state(state, ReloadDirectory())


def _run_toggle_split_terminal_command(
    state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return reduce_state(state, ToggleSplitTerminal())


def _run_select_all_command(
    state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    visible_paths = tuple(entry.path for entry in select_visible_current_entry_states(state))
    return reduce_state(state, SelectAllVisibleEntries(visible_paths))


def _selected_current_file_paths(state: AppState) -> tuple[str, ...]:
    selected_paths = tuple(
        entry.path
        for entry in select_visible_current_entry_states(state)
        if entry.path in state.current_pane.selected_paths and entry.kind == "file"
    )
    if state.current_pane.selected_paths:
        return selected_paths

    entry = single_target_entry(state)
    if entry is None or entry.kind != "file":
        return ()
    return (entry.path,)


def _run_replace_text_command(
    state: AppState,
    next_state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    target_paths = _selected_current_file_paths(state)
    if not target_paths:
        return _notify(
            next_state,
            level="warning",
            message=(
                "Replace text requires a selected file or file selection "
                "in the current directory"
            ),
        )
    return reduce_state(next_state, BeginTextReplace(target_paths=target_paths))


def _run_show_attributes_command(state: AppState) -> ReduceResult:
    entry = single_target_entry(state)
    if entry is None:
        return _notify(
            state,
            level="warning",
            message="Show attributes requires a single target",
        )

    return finalize(
        replace(
            state,
            ui_mode="DETAIL",
            notification=None,
            command_palette=None,
            pending_file_search_request_id=None,
            pending_grep_search_request_id=None,
            attribute_inspection=AttributeInspectionState(
                name=entry.name,
                kind=entry.kind,
                path=entry.path,
                size_bytes=entry.size_bytes,
                modified_at=entry.modified_at,
                hidden=entry.hidden,
                permissions_mode=entry.permissions_mode,
            ),
        )
    )


def _run_copy_path_command(
    next_state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return reduce_state(next_state, CopyPathsToClipboard())


def _run_rename_command(
    state: AppState,
    next_state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    target_path = single_target_path(state)
    if target_path is None:
        return _notify(
            next_state,
            level="warning",
            message="Rename requires a single target",
        )
    return reduce_state(next_state, BeginRenameInput(path=target_path))


def _run_open_in_editor_command(
    state: AppState,
    next_state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    entry = single_target_entry(state)
    if entry is None:
        return _notify(
            next_state,
            level="warning",
            message="Open in editor requires a single target",
        )
    if entry.kind != "file":
        return _notify(
            next_state,
            level="warning",
            message="Can only open files in editor",
        )
    return reduce_state(next_state, OpenPathInEditor(path=entry.path))


def _run_extract_archive_command(
    state: AppState,
    next_state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    entry = single_target_entry(state)
    if entry is None:
        return _notify(
            next_state,
            level="warning",
            message="Extract archive requires a single target",
        )
    if entry.kind != "file" or not is_supported_archive_path(entry.path):
        return _notify(
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
        return _notify(
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
    target_paths = select_target_paths(state)
    if not target_paths:
        return _notify(state, level="warning", message="Nothing to delete")
    return reduce_state(next_state, BeginDeleteTargets(paths=target_paths))


def _run_empty_trash_command(
    state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return reduce_state(state, BeginEmptyTrash())


def _run_open_file_manager_command(
    state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return reduce_state(state, OpenPathWithDefaultApp(state.current_path))


def _run_open_terminal_command(
    state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return reduce_state(state, OpenTerminalAtPath(state.current_path))


def _run_shell_command_command(
    state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return reduce_state(state, BeginShellCommandInput())


def _run_add_bookmark_command(
    state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return reduce_state(state, AddBookmark(path=state.current_path))


def _run_remove_bookmark_command(
    state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return reduce_state(state, RemoveBookmark(path=state.current_path))


def _run_toggle_hidden_command(
    state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
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
            config_editor=ConfigEditorState(
                path=state.config_path,
                draft=state.config,
            ),
        )
    )


def _run_create_file_command(
    state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return reduce_state(state, BeginCreateInput("file"))


def _run_create_dir_command(
    state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return reduce_state(state, BeginCreateInput("dir"))


def _matches_search_completion(
    state: AppState,
    *,
    request_id: int,
    pending_request_id: int | None,
    source: str,
    query: str,
) -> bool:
    return (
        request_id == pending_request_id
        and state.command_palette is not None
        and state.command_palette.source == source
        and state.command_palette.query.strip() == query
    )


def _handle_file_search_completed(
    state: AppState,
    action: FileSearchCompleted,
) -> ReduceResult:
    if not _matches_search_completion(
        state,
        request_id=action.request_id,
        pending_request_id=state.pending_file_search_request_id,
        source="file_search",
        query=action.query,
    ):
        return finalize(state)

    cache_query = ""
    cache_results = ()
    if not is_regex_file_search_query(action.query):
        cache_query = action.query.casefold()
        cache_results = action.results

    return _sync_file_search_preview(
        replace(
            state,
            command_palette=replace(
                state.command_palette,
                file_search_results=action.results,
                file_search_error_message=None,
                cursor_index=0,
                file_search_cache_query=cache_query,
                file_search_cache_results=cache_results,
                file_search_cache_root_path=state.current_path,
                file_search_cache_show_hidden=state.show_hidden,
            ),
            pending_file_search_request_id=None,
        )
    )


def _handle_file_search_failed(
    state: AppState,
    action: FileSearchFailed,
) -> ReduceResult:
    if action.request_id != state.pending_file_search_request_id:
        return finalize(state)

    if state.command_palette is not None and action.invalid_query:
        return _sync_file_search_preview(
            replace(
                state,
                command_palette=replace(
                    state.command_palette,
                    file_search_results=(),
                    file_search_error_message=action.message,
                ),
                pending_file_search_request_id=None,
            )
        )

    return finalize(
        replace(
            state,
            notification=NotificationState(level="error", message=action.message),
            pending_file_search_request_id=None,
        )
    )


def _handle_grep_search_completed(
    state: AppState,
    action: GrepSearchCompleted,
) -> ReduceResult:
    if (
        action.request_id != state.pending_grep_search_request_id
        or state.command_palette is None
        or state.command_palette.source != "grep_search"
    ):
        return finalize(state)

    return _sync_grep_preview(
        replace(
            state,
            command_palette=replace(
                state.command_palette,
                grep_search_results=action.results,
                grep_search_error_message=None,
                cursor_index=0,
            ),
            pending_grep_search_request_id=None,
        )
    )


def _handle_grep_search_failed(
    state: AppState,
    action: GrepSearchFailed,
) -> ReduceResult:
    if action.request_id != state.pending_grep_search_request_id:
        return finalize(state)

    if state.command_palette is not None and action.invalid_query:
        return _sync_grep_preview(
            replace(
                state,
                command_palette=replace(
                    state.command_palette,
                    grep_search_results=(),
                    grep_search_error_message=action.message,
                    cursor_index=0,
                ),
                pending_grep_search_request_id=None,
                pending_child_pane_request_id=None,
            )
        )

    return finalize(
        replace(
            state,
            notification=NotificationState(level="error", message=action.message),
            pending_grep_search_request_id=None,
        )
    )


def _handle_text_replace_preview_completed(
    state: AppState,
    action: TextReplacePreviewCompleted,
) -> ReduceResult:
    if (
        action.request_id != state.pending_replace_preview_request_id
        or state.command_palette is None
        or state.command_palette.source != "replace_text"
    ):
        return finalize(state)

    preview_results = tuple(
        ReplacePreviewResultState(
            path=entry.path,
            display_path=str(Path(entry.path).name)
            if Path(entry.path).parent == Path(state.current_path)
            else str(Path(entry.path).relative_to(state.current_path)),
            diff_text=entry.diff_text,
            match_count=entry.match_count,
            first_match_line_number=entry.first_match_line_number,
            first_match_before=entry.first_match_before,
            first_match_after=entry.first_match_after,
        )
        for entry in action.result.changed_entries
    )
    status_message = None
    if action.result.skipped_paths:
        status_message = f"Skipped {len(action.result.skipped_paths)} unreadable file(s)"
    next_state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            replace_preview_results=preview_results,
            replace_error_message=None,
            replace_status_message=status_message,
            replace_total_match_count=action.result.total_match_count,
            cursor_index=0,
        ),
        pending_replace_preview_request_id=None,
    )
    return _sync_replace_preview(next_state)


def _handle_text_replace_preview_failed(
    state: AppState,
    action: TextReplacePreviewFailed,
) -> ReduceResult:
    if action.request_id != state.pending_replace_preview_request_id:
        return finalize(state)

    if state.command_palette is not None and action.invalid_query:
        return finalize(
            replace(
                state,
                command_palette=replace(
                    state.command_palette,
                    replace_preview_results=(),
                    replace_error_message=action.message,
                    replace_status_message=None,
                    replace_total_match_count=0,
                    cursor_index=0,
                ),
                child_pane=PaneState(directory_path=state.current_path, entries=()),
                pending_replace_preview_request_id=None,
            )
        )

    return finalize(
        replace(
            state,
            notification=NotificationState(level="error", message=action.message),
            pending_replace_preview_request_id=None,
        )
    )


def _handle_text_replace_applied(
    state: AppState,
    action: TextReplaceApplied,
    reduce_state: ReducerFn,
) -> ReduceResult:
    if action.request_id != state.pending_replace_apply_request_id:
        return finalize(state)

    next_state = replace(
        state,
        pending_replace_apply_request_id=None,
        post_reload_notification=NotificationState(
            level=action.result.level,
            message=action.result.message,
        ),
        notification=None,
    )
    return reduce_state(
        next_state,
        RequestBrowserSnapshot(
            path=state.current_path,
            cursor_path=state.current_pane.cursor_path,
            blocking=True,
            invalidate_paths=browser_snapshot_invalidation_paths(
                state.current_path,
                *action.result.changed_paths,
            ),
        ),
    )


def _handle_text_replace_apply_failed(
    state: AppState,
    action: TextReplaceApplyFailed,
) -> ReduceResult:
    if action.request_id != state.pending_replace_apply_request_id:
        return finalize(state)
    return finalize(
        replace(
            state,
            pending_replace_apply_request_id=None,
            notification=NotificationState(level="error", message=action.message),
        )
    )


def _selected_grep_result(state: AppState) -> GrepSearchResultState | None:
    if state.command_palette is None or state.command_palette.source != "grep_search":
        return None
    results = state.command_palette.grep_search_results
    if not results:
        return None
    return results[normalize_command_palette_cursor(state, state.command_palette.cursor_index)]


def _selected_file_search_result(state: AppState) -> FileSearchResultState | None:
    if state.command_palette is None or state.command_palette.source != "file_search":
        return None
    results = state.command_palette.file_search_results
    if not results:
        return None
    return results[normalize_command_palette_cursor(state, state.command_palette.cursor_index)]


def _matches_file_search_preview(
    state: AppState,
    result: FileSearchResultState,
) -> bool:
    return (
        state.child_pane.mode == "preview"
        and state.child_pane.preview_path == result.path
        and state.child_pane.preview_title is None
        and state.child_pane.preview_start_line is None
        and state.child_pane.preview_highlight_line is None
    )


def _sync_file_search_preview(state: AppState) -> ReduceResult:
    selected_result = _selected_file_search_result(state)
    if selected_result is None or not state.config.display.show_preview:
        return finalize(replace(state, pending_child_pane_request_id=None))

    if state.pending_child_pane_request_id is None and _matches_file_search_preview(
        state,
        selected_result,
    ):
        return finalize(state)

    request_id = state.next_request_id
    return finalize(
        replace(
            state,
            pending_child_pane_request_id=request_id,
            next_request_id=request_id + 1,
        ),
        LoadChildPaneSnapshotEffect(
            request_id=request_id,
            current_path=state.current_path,
            cursor_path=selected_result.path,
        ),
    )


def _matches_grep_preview(
    state: AppState,
    result: GrepSearchResultState,
) -> bool:
    return (
        state.child_pane.mode == "preview"
        and state.child_pane.preview_path == result.path
        and state.child_pane.preview_highlight_line == result.line_number
    )


def _sync_grep_preview(state: AppState) -> ReduceResult:
    selected_result = _selected_grep_result(state)
    if selected_result is None or not state.config.display.show_preview:
        return finalize(replace(state, pending_child_pane_request_id=None))

    if state.pending_child_pane_request_id is None and _matches_grep_preview(
        state,
        selected_result,
    ):
        return finalize(state)

    request_id = state.next_request_id
    return finalize(
        replace(
            state,
            pending_child_pane_request_id=request_id,
            next_request_id=request_id + 1,
        ),
        LoadChildPaneSnapshotEffect(
            request_id=request_id,
            current_path=state.current_path,
            cursor_path=selected_result.path,
            grep_result=selected_result,
            grep_context_lines=state.config.display.grep_preview_context_lines,
        ),
    )


def _matches_replace_preview(
    state: AppState,
    result: ReplacePreviewResultState,
) -> bool:
    return (
        state.child_pane.mode == "preview"
        and state.child_pane.preview_title == "Replace Preview"
        and state.child_pane.preview_path == result.path
        and state.child_pane.preview_content == result.diff_text
    )


def _selected_replace_preview_result(state: AppState) -> ReplacePreviewResultState | None:
    if state.command_palette is None or state.command_palette.source != "replace_text":
        return None
    results = state.command_palette.replace_preview_results
    if not results:
        return None
    return results[normalize_command_palette_cursor(state, state.command_palette.cursor_index)]


def _sync_replace_preview(state: AppState) -> ReduceResult:
    selected_result = _selected_replace_preview_result(state)
    if selected_result is None:
        preview_message = "No matching files"
        if state.command_palette is not None and state.command_palette.source == "replace_text":
            preview_message = state.command_palette.replace_status_message or preview_message
        return finalize(
            replace(
                state,
                child_pane=PaneState(
                    directory_path=state.current_path,
                    entries=(),
                    mode="preview",
                    preview_path=state.current_path,
                    preview_title="Replace Preview",
                    preview_content="",
                    preview_message=preview_message,
                ),
            )
        )

    if _matches_replace_preview(state, selected_result):
        return finalize(state)

    return finalize(
        replace(
            state,
            child_pane=PaneState(
                directory_path=state.current_path,
                entries=(),
                mode="preview",
                preview_path=selected_result.path,
                preview_title="Replace Preview",
                preview_content=selected_result.diff_text,
                preview_message=(
                    state.command_palette.replace_status_message
                    if state.command_palette is not None
                    else None
                ),
            ),
        )
    )


# ---------------------------------------------------------------------------
# Individual handler functions
# ---------------------------------------------------------------------------


def _handle_begin_command_palette(
    state: AppState,
    action: BeginCommandPalette,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return finalize(_enter_palette(state))


def _handle_begin_file_search(
    state: AppState,
    action: BeginFileSearch,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return finalize(_enter_palette(state, source="file_search"))


def _handle_begin_grep_search(
    state: AppState,
    action: BeginGrepSearch,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return finalize(_enter_palette(state, source="grep_search"))


def _handle_begin_text_replace(
    state: AppState,
    action: BeginTextReplace,
    reduce_state: ReducerFn,
) -> ReduceResult:
    next_state = _enter_palette(state, source="replace_text")
    return finalize(
        replace(
            next_state,
            command_palette=replace(
                next_state.command_palette,
                replace_target_paths=action.target_paths,
            ),
        )
    )


def _dispatch_begin_history_search(
    state: AppState,
    action: BeginHistorySearch,
    reduce_state: ReducerFn,
) -> ReduceResult:
    # Call the original helper function (note: different signature)
    return _handle_begin_history_search(state)


def _dispatch_begin_bookmark_search(
    state: AppState,
    action: BeginBookmarkSearch,
    reduce_state: ReducerFn,
) -> ReduceResult:
    # Call the original helper function (note: different signature)
    return _handle_begin_bookmark_search(state)


def _handle_begin_go_to_path(
    state: AppState,
    action: BeginGoToPath,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return finalize(_enter_palette(state, source="go_to_path"))


def _handle_cancel_command_palette(
    state: AppState,
    action: CancelCommandPalette,
    reduce_state: ReducerFn,
) -> ReduceResult:
    next_state = _restore_browsing_from_palette(state, clear_name_conflict=True)
    if state.command_palette is not None and state.command_palette.source in {
        "file_search",
        "grep_search",
        "replace_text",
    }:
        return sync_child_pane(next_state, next_state.current_pane.cursor_path, reduce_state)
    return finalize(next_state)


def _handle_dismiss_attribute_dialog(
    state: AppState,
    action: DismissAttributeDialog,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return finalize(
        replace(
            state,
            ui_mode="BROWSING",
            notification=None,
            attribute_inspection=None,
        )
    )


def _handle_show_attributes(
    state: AppState,
    action: ShowAttributes,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return _run_show_attributes_command(state)


def _dispatch_move_palette_cursor(
    state: AppState,
    action: MoveCommandPaletteCursor,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return _handle_move_palette_cursor(state, action)


def _dispatch_set_command_palette_query(
    state: AppState,
    action: SetCommandPaletteQuery,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return _handle_set_palette_query(state, action)


def _dispatch_set_grep_search_field(
    state: AppState,
    action: SetGrepSearchField,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return _handle_set_grep_search_field(state, action.field, action.value)


def _dispatch_set_replace_field(
    state: AppState,
    action: SetReplaceField,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return _handle_set_replace_field(state, action.field, action.value)


def _dispatch_cycle_grep_search_field(
    state: AppState,
    action: CycleGrepSearchField,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return _handle_cycle_grep_search_field(state, action)


def _dispatch_cycle_replace_field(
    state: AppState,
    action: CycleReplaceField,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return _handle_cycle_replace_field(state, action)


def _dispatch_submit_command_palette(
    state: AppState,
    action: SubmitCommandPalette,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return _handle_submit_palette(state, reduce_state)


def _dispatch_file_search_completed(
    state: AppState,
    action: FileSearchCompleted,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return _handle_file_search_completed(state, action)


def _dispatch_file_search_failed(
    state: AppState,
    action: FileSearchFailed,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return _handle_file_search_failed(state, action)


def _dispatch_grep_search_completed(
    state: AppState,
    action: GrepSearchCompleted,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return _handle_grep_search_completed(state, action)


def _dispatch_grep_search_failed(
    state: AppState,
    action: GrepSearchFailed,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return _handle_grep_search_failed(state, action)


def _dispatch_text_replace_preview_completed(
    state: AppState,
    action: TextReplacePreviewCompleted,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return _handle_text_replace_preview_completed(state, action)


def _dispatch_text_replace_preview_failed(
    state: AppState,
    action: TextReplacePreviewFailed,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return _handle_text_replace_preview_failed(state, action)


def _dispatch_text_replace_applied(
    state: AppState,
    action: TextReplaceApplied,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return _handle_text_replace_applied(state, action, reduce_state)


def _dispatch_text_replace_apply_failed(
    state: AppState,
    action: TextReplaceApplyFailed,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return _handle_text_replace_apply_failed(state, action)


def _dispatch_open_grep_result_in_editor(
    state: AppState,
    action: OpenGrepResultInEditor,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return _handle_open_grep_result_in_editor(state, reduce_state)


def _dispatch_open_find_result_in_editor(
    state: AppState,
    action: OpenFindResultInEditor,
    reduce_state: ReducerFn,
) -> ReduceResult:
    return _handle_open_find_result_in_editor(state, reduce_state)


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_PaletteHandler = Callable[[AppState, Action, ReducerFn], ReduceResult]

_PALETTE_HANDLERS: dict[type[Action], _PaletteHandler] = {
    BeginCommandPalette: _handle_begin_command_palette,
    BeginFileSearch: _handle_begin_file_search,
    BeginGrepSearch: _handle_begin_grep_search,
    BeginTextReplace: _handle_begin_text_replace,
    BeginHistorySearch: _dispatch_begin_history_search,
    BeginBookmarkSearch: _dispatch_begin_bookmark_search,
    BeginGoToPath: _handle_begin_go_to_path,
    CancelCommandPalette: _handle_cancel_command_palette,
    DismissAttributeDialog: _handle_dismiss_attribute_dialog,
    ShowAttributes: _handle_show_attributes,
    MoveCommandPaletteCursor: _dispatch_move_palette_cursor,
    SetCommandPaletteQuery: _dispatch_set_command_palette_query,
    SetGrepSearchField: _dispatch_set_grep_search_field,
    SetReplaceField: _dispatch_set_replace_field,
    CycleGrepSearchField: _dispatch_cycle_grep_search_field,
    CycleReplaceField: _dispatch_cycle_replace_field,
    SubmitCommandPalette: _dispatch_submit_command_palette,
    FileSearchCompleted: _dispatch_file_search_completed,
    FileSearchFailed: _dispatch_file_search_failed,
    GrepSearchCompleted: _dispatch_grep_search_completed,
    GrepSearchFailed: _dispatch_grep_search_failed,
    TextReplacePreviewCompleted: _dispatch_text_replace_preview_completed,
    TextReplacePreviewFailed: _dispatch_text_replace_preview_failed,
    TextReplaceApplied: _dispatch_text_replace_applied,
    TextReplaceApplyFailed: _dispatch_text_replace_apply_failed,
    OpenGrepResultInEditor: _dispatch_open_grep_result_in_editor,
    OpenFindResultInEditor: _dispatch_open_find_result_in_editor,
}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def handle_palette_action(
    state: AppState,
    action: Action,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    handler = _PALETTE_HANDLERS.get(type(action))
    if handler is not None:
        return handler(state, action, reduce_state)  # type: ignore[arg-type]
    return None
