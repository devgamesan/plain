"""Search-related command palette reducers."""

from dataclasses import replace
from pathlib import Path

from zivo.models.external_launch import ExternalLaunchRequest

from .actions import (
    CycleSelectedFilesGrepField,
    FileSearchCompleted,
    FileSearchFailed,
    GrepSearchCompleted,
    GrepSearchFailed,
    SelectedFilesGrepKeywordChanged,
)
from .command_palette import normalize_command_palette_cursor
from .effects import (
    LoadChildPaneSnapshotEffect,
    ReduceResult,
    RunFileSearchEffect,
    RunGrepSearchEffect,
)
from .models import AppState, FileSearchResultState, GrepSearchResultState, NotificationState
from .reducer_common import (
    filter_file_search_results,
    finalize,
    is_regex_file_search_query,
    run_external_launch_request,
)
from .reducer_palette_replace import (
    handle_grf_grep_search_completed,
    handle_grs_grep_search_completed,
    handle_rff_file_search_completed,
    sync_find_replace_preview,
    sync_grep_replace_preview,
    sync_grep_replace_selected_preview,
)
from .reducer_palette_shared import (
    filter_grep_results_by_filename,
    matches_search_completion,
    notify,
    replace_grep_field,
    request_palette_snapshot,
)


def validate_grep_search_filters(
    include_extensions: str,
    exclude_extensions: str,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    from .reducer_palette_shared import normalize_grep_extension_filters

    include_globs = normalize_grep_extension_filters(include_extensions, label="include")
    exclude_globs = normalize_grep_extension_filters(exclude_extensions, label="exclude")
    conflicts = tuple(sorted(set(include_globs) & set(exclude_globs)))
    if conflicts:
        formatted = ", ".join(glob.removeprefix("*.") for glob in conflicts)
        raise ValueError(
            f"Extensions cannot be included and excluded at the same time: {formatted}"
        )
    return include_globs, exclude_globs


def handle_set_file_search_query(
    state: AppState,
    next_palette,
    query: str,
) -> ReduceResult:
    stripped_query = query.strip()
    if not stripped_query:
        return sync_file_search_preview(
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
        return sync_file_search_preview(
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


def handle_set_grep_search_field(
    state: AppState,
    field,
    value: str,
) -> ReduceResult:
    next_palette = replace(
        replace_grep_field(state.command_palette, field=field, value=value),
        grep_search_error_message=None,
        cursor_index=0,
    )
    stripped_query = next_palette.grep_search_keyword.strip()
    if not stripped_query:
        return sync_grep_preview(
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
        include_globs, exclude_globs = validate_grep_search_filters(
            next_palette.grep_search_include_extensions,
            next_palette.grep_search_exclude_extensions,
        )
    except ValueError as error:
        return sync_grep_preview(
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


def handle_submit_file_search_palette(
    state: AppState,
    reduce_state,
) -> ReduceResult:
    results = state.command_palette.file_search_results
    message = state.command_palette.file_search_error_message or "No matching files"
    if not results:
        return notify(state, level="warning", message=message)

    selected_result = results[
        normalize_command_palette_cursor(state, state.command_palette.cursor_index)
    ]
    return request_palette_snapshot(
        state,
        reduce_state,
        path=str(Path(selected_result.path).parent),
        cursor_path=selected_result.path,
    )


def handle_submit_grep_search_palette(
    state: AppState,
    reduce_state,
) -> ReduceResult:
    results = state.command_palette.grep_search_results
    message = state.command_palette.grep_search_error_message or "No matching lines"
    if not results:
        return notify(state, level="warning", message=message)

    selected_result = results[
        normalize_command_palette_cursor(state, state.command_palette.cursor_index)
    ]
    return request_palette_snapshot(
        state,
        reduce_state,
        path=str(Path(selected_result.path).parent),
        cursor_path=selected_result.path,
    )


def handle_open_grep_result_in_editor(
    state: AppState,
    reduce_state,
) -> ReduceResult:
    del reduce_state
    results = state.command_palette.grep_search_results
    message = state.command_palette.grep_search_error_message or "No matching lines"
    if not results:
        return notify(state, level="warning", message=message)

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


def handle_open_find_result_in_editor(
    state: AppState,
    reduce_state,
) -> ReduceResult:
    del reduce_state
    results = state.command_palette.file_search_results
    message = state.command_palette.file_search_error_message or "No matching files"
    if not results:
        return notify(state, level="warning", message=message)

    selected_result = results[
        normalize_command_palette_cursor(state, state.command_palette.cursor_index)
    ]
    return run_external_launch_request(
        replace(state, notification=None),
        ExternalLaunchRequest(kind="open_editor", path=selected_result.path, line_number=None),
    )


def handle_file_search_completed(
    state: AppState,
    action: FileSearchCompleted,
) -> ReduceResult:
    if (
        state.command_palette is not None
        and state.command_palette.source == "replace_in_found_files"
    ):
        return handle_rff_file_search_completed(state, action)

    if not matches_search_completion(
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

    return sync_file_search_preview(
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


def handle_file_search_failed(
    state: AppState,
    action: FileSearchFailed,
) -> ReduceResult:
    if action.request_id != state.pending_file_search_request_id:
        return finalize(state)

    if (
        state.command_palette is not None
        and state.command_palette.source == "replace_in_found_files"
    ):
        if action.invalid_query:
            return sync_find_replace_preview(
                replace(
                    state,
                    command_palette=replace(
                        state.command_palette,
                        rff_file_results=(),
                        rff_file_error_message=action.message,
                        rff_preview_results=(),
                        rff_total_match_count=0,
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

    if state.command_palette is not None and action.invalid_query:
        return sync_file_search_preview(
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


def handle_grep_search_completed(
    state: AppState,
    action: GrepSearchCompleted,
) -> ReduceResult:
    if action.request_id != state.pending_grep_search_request_id:
        return finalize(state)

    if (
        state.command_palette is not None
        and state.command_palette.source == "replace_in_grep_files"
    ):
        return handle_grf_grep_search_completed(state, action)

    if (
        state.command_palette is not None
        and state.command_palette.source == "grep_replace_selected"
    ):
        return handle_grs_grep_search_completed(state, action)

    if (
        state.command_palette is not None
        and state.command_palette.source == "selected_files_grep"
    ):
        return handle_sfg_grep_search_completed(state, action)

    if state.command_palette is None or state.command_palette.source != "grep_search":
        return finalize(state)

    return sync_grep_preview(
        replace(
            state,
            command_palette=replace(
                state.command_palette,
                grep_search_results=filter_grep_results_by_filename(
                    action.results,
                    state.command_palette.grep_search_filename_filter,
                ),
                grep_search_error_message=None,
                cursor_index=0,
            ),
            pending_grep_search_request_id=None,
        )
    )


def handle_grep_search_failed(
    state: AppState,
    action: GrepSearchFailed,
) -> ReduceResult:
    if action.request_id != state.pending_grep_search_request_id:
        return finalize(state)

    if (
        state.command_palette is not None
        and state.command_palette.source == "replace_in_grep_files"
    ):
        if action.invalid_query:
            return sync_grep_replace_preview(
                replace(
                    state,
                    command_palette=replace(
                        state.command_palette,
                        grf_grep_results=(),
                        grf_grep_error_message=action.message,
                        grf_preview_results=(),
                        grf_total_match_count=0,
                        cursor_index=0,
                    ),
                    pending_grep_search_request_id=None,
                )
            )
        return notify(
            replace(state, pending_grep_search_request_id=None),
            level="error",
            message=action.message,
        )

    if (
        state.command_palette is not None
        and state.command_palette.source == "grep_replace_selected"
    ):
        if action.invalid_query:
            return sync_grep_replace_selected_preview(
                replace(
                    state,
                    command_palette=replace(
                        state.command_palette,
                        grs_grep_results=(),
                        grs_grep_error_message=action.message,
                        grs_preview_results=(),
                        grs_total_match_count=0,
                        cursor_index=0,
                    ),
                    pending_grep_search_request_id=None,
                )
            )
        return notify(
            replace(state, pending_grep_search_request_id=None),
            level="error",
            message=action.message,
        )

    if (
        state.command_palette is not None
        and state.command_palette.source == "selected_files_grep"
    ):
        return handle_sfg_grep_search_failed(state, action)

    if state.command_palette is not None and action.invalid_query:
        return sync_grep_preview(
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

    return notify(
        replace(state, pending_grep_search_request_id=None),
        level="error",
        message=action.message,
    )


def selected_file_search_result(state: AppState) -> FileSearchResultState | None:
    if state.command_palette is None or state.command_palette.source != "file_search":
        return None
    results = state.command_palette.file_search_results
    if not results:
        return None
    cursor_index = normalize_command_palette_cursor(state, state.command_palette.cursor_index)
    if cursor_index >= len(results):
        return None
    return results[cursor_index]


def selected_grep_result(state: AppState) -> GrepSearchResultState | None:
    if state.command_palette is None or state.command_palette.source != "grep_search":
        return None
    results = state.command_palette.grep_search_results
    if not results:
        return None
    cursor_index = normalize_command_palette_cursor(state, state.command_palette.cursor_index)
    if cursor_index >= len(results):
        return None
    return results[cursor_index]


def matches_file_search_preview(
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


def sync_file_search_preview(state: AppState) -> ReduceResult:
    selected_result = selected_file_search_result(state)
    if selected_result is None or not state.config.display.show_preview:
        return finalize(replace(state, pending_child_pane_request_id=None))

    if state.pending_child_pane_request_id is None and matches_file_search_preview(
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
            preview_max_bytes=state.config.display.preview_max_kib * 1024,
        ),
    )


def matches_grep_preview(
    state: AppState,
    result: GrepSearchResultState,
) -> bool:
    return (
        state.child_pane.mode == "preview"
        and state.child_pane.preview_path == result.path
        and state.child_pane.preview_highlight_line == result.line_number
    )


def sync_grep_preview(state: AppState) -> ReduceResult:
    selected_result = selected_grep_result(state)
    if selected_result is None or not state.config.display.show_preview:
        return finalize(replace(state, pending_child_pane_request_id=None))

    if state.pending_child_pane_request_id is None and matches_grep_preview(state, selected_result):
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
            preview_max_bytes=state.config.display.preview_max_kib * 1024,
            grep_result=selected_result,
            grep_context_lines=state.config.display.grep_preview_context_lines,
        ),
    )


def handle_sfg_keyword_changed(
    state: AppState,
    action: SelectedFilesGrepKeywordChanged,
) -> ReduceResult:
    """Handle keyword changes for selected-files-grep."""
    if state.command_palette is None or state.command_palette.source != "selected_files_grep":
        return finalize(state)

    next_palette = replace(
        state.command_palette,
        sfg_keyword=action.keyword,
        sfg_error_message=None,
        cursor_index=0,
    )
    stripped_query = action.keyword.strip()

    if not stripped_query:
        return sync_sfg_preview(
            replace(
                state,
                command_palette=replace(
                    next_palette,
                    sfg_results=(),
                    sfg_error_message=None,
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
            include_globs=(),  # No extension filtering for selected-files-grep
            exclude_globs=(),  # No extension filtering for selected-files-grep
        ),
    )


def handle_sfg_grep_search_completed(
    state: AppState,
    action: GrepSearchCompleted,
) -> ReduceResult:
    """Handle grep search completion for selected-files-grep."""
    if action.request_id != state.pending_grep_search_request_id:
        return finalize(state)

    if state.command_palette is None or state.command_palette.source != "selected_files_grep":
        return finalize(state)

    target_set = frozenset(state.command_palette.sfg_target_paths)
    filtered_results = tuple(
        r for r in action.results
        if r.path in target_set
    )

    return sync_sfg_preview(
        replace(
            state,
            command_palette=replace(
                state.command_palette,
                sfg_results=filtered_results,
                sfg_error_message=None,
                cursor_index=0,
            ),
            pending_grep_search_request_id=None,
        )
    )


def handle_sfg_grep_search_failed(
    state: AppState,
    action: GrepSearchFailed,
) -> ReduceResult:
    """Handle grep search failure for selected-files-grep."""
    if action.request_id != state.pending_grep_search_request_id:
        return finalize(state)

    if state.command_palette is None or state.command_palette.source != "selected_files_grep":
        return finalize(state)

    if action.invalid_query:
        return sync_sfg_preview(
            replace(
                state,
                command_palette=replace(
                    state.command_palette,
                    sfg_results=(),
                    sfg_error_message=action.message,
                    cursor_index=0,
                ),
                pending_grep_search_request_id=None,
                pending_child_pane_request_id=None,
            )
        )

    return notify(
        replace(state, pending_grep_search_request_id=None),
        level="error",
        message=action.message,
    )


def handle_cycle_sfg_field(
    state: AppState,
    action: CycleSelectedFilesGrepField,
) -> ReduceResult:
    """Handle field cycling for selected-files-grep (no-op since only keyword field exists)."""
    if state.command_palette is None or state.command_palette.source != "selected_files_grep":
        return finalize(state)

    # Only one field (keyword), so cycling is a no-op
    return finalize(state)


def selected_sfg_result(state: AppState) -> GrepSearchResultState | None:
    """Return the selected result for selected-files-grep."""
    if state.command_palette is None or state.command_palette.source != "selected_files_grep":
        return None
    results = state.command_palette.sfg_results
    if not results:
        return None
    cursor_index = normalize_command_palette_cursor(state, state.command_palette.cursor_index)
    if cursor_index >= len(results):
        return None
    return results[cursor_index]


def matches_sfg_preview(
    state: AppState,
    result: GrepSearchResultState,
) -> bool:
    """Check if the current preview matches the selected result for selected-files-grep."""
    return (
        state.child_pane.mode == "preview"
        and state.child_pane.preview_path == result.path
        and state.child_pane.preview_highlight_line == result.line_number
    )


def sync_sfg_preview(state: AppState) -> ReduceResult:
    """Sync the preview pane for selected-files-grep."""
    selected_result = selected_sfg_result(state)
    if selected_result is None or not state.config.display.show_preview:
        return finalize(replace(state, pending_child_pane_request_id=None))

    if state.pending_child_pane_request_id is None and matches_sfg_preview(state, selected_result):
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
            preview_max_bytes=state.config.display.preview_max_kib * 1024,
            grep_result=selected_result,
            grep_context_lines=state.config.display.grep_preview_context_lines,
        ),
    )
