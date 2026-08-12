"""Search-related command palette reducers."""

from dataclasses import replace
from pathlib import Path

from zivo.models.external_launch import ExternalLaunchRequest
from zivo.windows_paths import (
    is_search_workspace_path,
    parse_search_workspace_path,
    resolve_parent_directory_path,
)

from .actions import (
    CycleFileSearchField,
    FileSearchCompleted,
    FileSearchFailed,
    FileSearchResultsUpdated,
    GrepSearchCompleted,
    GrepSearchFailed,
    GrepSearchResultsUpdated,
    RequestBrowserSnapshot,
    SetFileSearchField,
    SetFileSearchTarget,
    SetGrepSearchScope,
)
from .actions_palette import OpenSearchWorkspace
from .command_palette import normalize_command_palette_cursor
from .effects import (
    LoadChildPaneSnapshotEffect,
    ReduceResult,
    RunFileSearchEffect,
    RunGrepSearchEffect,
)
from .models import AppState, FileSearchResultState, GrepSearchResultState, NotificationState
from .natural_sort import natural_sort_key
from .reducer_common import (
    ReducerFn,
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
    FILE_SEARCH_FIELDS,
    filter_grep_results_by_filename,
    matches_search_completion,
    normalize_extension_filters,
    notify,
    replace_grep_field,
    request_palette_snapshot,
    validate_filename_filter,
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


def validate_file_search_filters(
    include_extensions: str,
    exclude_extensions: str,
    *,
    target: str,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Normalize file-search extension filters and validate their scope."""

    include_globs = normalize_extension_filters(include_extensions, label="include")
    exclude_globs = normalize_extension_filters(exclude_extensions, label="exclude")
    conflicts = tuple(sorted(set(include_globs) & set(exclude_globs)))
    if conflicts:
        formatted = ", ".join(glob.removeprefix("*.") for glob in conflicts)
        raise ValueError(
            f"Extensions cannot be included and excluded at the same time: {formatted}"
        )
    if target == "directories" and (include_globs or exclude_globs):
        raise ValueError(
            "Extension filters require Target=files or all; clear the filters or change Target"
        )
    return include_globs, exclude_globs


def grep_scope_target_paths(state: AppState, scope: str) -> tuple[str, ...]:
    """Resolve explicitly selected file and directory targets for a content-search scope."""
    if scope == "selected_entries":
        return tuple(
            entry.path
            for entry in state.current_pane.entries
            if entry.path in state.current_pane.selected_paths
        )
    return ()


def is_grep_search_scope_available(state: AppState, scope: str) -> bool:
    """Return whether a scope can be chosen in the current browser context."""
    if scope == "current_directory":
        return not is_search_workspace_path(state.current_path)
    if scope == "selected_entries":
        return bool(grep_scope_target_paths(state, scope))
    return is_search_workspace_path(state.current_path)


def grep_scope_unavailable_message(state: AppState, scope: str) -> str | None:
    if scope == "selected_entries" and not grep_scope_target_paths(state, scope):
        return "Select one or more files or directories to search selected entries"
    if scope == "search_workspace" and not is_search_workspace_path(state.current_path):
        return "Search Workspace is only available while browsing a Search Workspace"
    return None


def default_grep_search_scope(state: AppState) -> str:
    if is_search_workspace_path(state.current_path):
        return "search_workspace"
    if grep_scope_target_paths(state, "selected_entries"):
        return "selected_entries"
    return "current_directory"


def grep_scope_root_path(state: AppState) -> str:
    if is_search_workspace_path(state.current_path):
        return parse_search_workspace_path(state.current_path)["root"] or state.current_path
    return state.current_path


def _matches_grep_scope_target(result_path: str, target_paths: tuple[str, ...]) -> bool:
    """Include a result when it belongs to an explicitly selected entry."""
    if not target_paths:
        return True
    result = Path(result_path)
    return any(
        result == Path(target) or result.is_relative_to(Path(target))
        for target in target_paths
    )


def handle_set_file_search_query(
    state: AppState,
    next_palette,
    query: str,
) -> ReduceResult:
    next_palette = replace(
        next_palette,
        cursor_index=0,
        cursor_navigation_active=False,
    )
    stripped_query = query.strip()
    search_target = next_palette.file_search.target
    try:
        include_globs, exclude_globs = validate_file_search_filters(
            next_palette.file_search.include_extensions,
            next_palette.file_search.exclude_extensions,
            target=search_target,
        )
    except ValueError as error:
        return sync_file_search_preview(
            replace(
                state,
                command_palette=replace(
                    next_palette,
                    file_search=replace(
                        next_palette.file_search,
                        results=(),
                        error_message=str(error),
                        results_truncated=False,
                    ),
                ),
                pending_file_search_request_id=None,
                pending_child_pane_request_id=None,
            )
        )

    if not stripped_query and not (include_globs or exclude_globs):
        return sync_file_search_preview(
            replace(
                state,
                command_palette=replace(
                    next_palette,
                    file_search=replace(
                        next_palette.file_search,
                        results=(),
                        error_message=None,
                        results_truncated=False,
                    ),
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
        and state.command_palette.file_search.cache_query
        and normalized_query.startswith(state.command_palette.file_search.cache_query)
        and state.command_palette.file_search.cache_root_path == state.current_path
        and state.command_palette.file_search.cache_show_hidden == state.show_hidden
        and state.command_palette.file_search.cache_target == search_target
        and state.command_palette.file_search.cache_include_extensions == include_globs
        and state.command_palette.file_search.cache_exclude_extensions == exclude_globs
    ):
        return sync_file_search_preview(
            replace(
                state,
                command_palette=replace(
                    next_palette,
                    file_search=replace(
                        next_palette.file_search,
                        results=filter_file_search_results(
                            state.command_palette.file_search.cache_results,
                            normalized_query,
                        ),
                    ),
                ),
                pending_file_search_request_id=None,
                pending_grep_search_request_id=None,
            )
        )

    request_id = state.next_request_id
    next_state = replace(
        state,
        command_palette=replace(
            next_palette,
            file_search=replace(
                next_palette.file_search,
                results=(),
                error_message=None,
                results_truncated=False,
            ),
        ),
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
            search_target=search_target,
            include_extensions=include_globs,
            exclude_extensions=exclude_globs,
        ),
    )


def handle_set_file_search_field(
    state: AppState,
    action: SetFileSearchField,
) -> ReduceResult:
    if state.command_palette is None or state.command_palette.source != "file_search":
        return finalize(state)
    if action.field == "keyword":
        next_palette = replace(state.command_palette, query=action.value)
    elif action.field == "include":
        next_palette = replace(
            state.command_palette,
            file_search=replace(
                state.command_palette.file_search,
                include_extensions=action.value,
            ),
        )
    elif action.field == "exclude":
        next_palette = replace(
            state.command_palette,
            file_search=replace(
                state.command_palette.file_search,
                exclude_extensions=action.value,
            ),
        )
    else:
        return finalize(state)
    return handle_set_file_search_query(state, next_palette, next_palette.query)


def handle_set_grep_search_field(
    state: AppState,
    field,
    value: str,
) -> ReduceResult:
    next_palette = replace_grep_field(state.command_palette, field=field, value=value)
    next_palette = replace(
        next_palette,
        grep_search=replace(next_palette.grep_search, error_message=None),
        cursor_index=0,
        cursor_navigation_active=False,
    )
    stripped_query = next_palette.grep_search.keyword.strip()
    if not stripped_query:
        return sync_grep_preview(
            replace(
                state,
                command_palette=replace(
                    next_palette,
                    grep_search=replace(
                        next_palette.grep_search,
                        results=(),
                        error_message=None,
                        results_truncated=False,
                    ),
                ),
                pending_grep_search_request_id=None,
                pending_child_pane_request_id=None,
            )
        )

    # If filename filter is changed and we have existing results, re-apply filtering
    if field == "filename":
        # Validate filename filter to prevent regex crashes
        validation_error = validate_filename_filter(value)
        if validation_error:
            return sync_grep_preview(
                replace(
                    state,
                    command_palette=replace(
                        next_palette,
                        grep_search=replace(
                            next_palette.grep_search,
                            results=(),
                            error_message=validation_error,
                            results_truncated=False,
                        ),
                    ),
                    pending_grep_search_request_id=None,
                    pending_child_pane_request_id=None,
                )
            )
        if state.command_palette.grep_search.results:
            return sync_grep_preview(
                replace(
                    state,
                    command_palette=replace(
                        next_palette,
                        grep_search=replace(
                            next_palette.grep_search,
                            results=filter_grep_results_by_filename(
                                state.command_palette.grep_search.results,
                                value,
                            ),
                        ),
                    ),
                )
            )

    try:
        include_globs, exclude_globs = validate_grep_search_filters(
            next_palette.grep_search.include_extensions,
            next_palette.grep_search.exclude_extensions,
        )
    except ValueError as error:
        return sync_grep_preview(
            replace(
                state,
                command_palette=replace(
                    next_palette,
                    grep_search=replace(
                        next_palette.grep_search,
                        results=(),
                        error_message=str(error),
                    ),
                ),
                pending_grep_search_request_id=None,
                pending_child_pane_request_id=None,
            )
        )

    request_id = state.next_request_id
    next_state = replace(
        state,
        command_palette=replace(
            next_palette,
            grep_search=replace(
                next_palette.grep_search,
                results=(),
                error_message=None,
                results_truncated=False,
            ),
        ),
        pending_grep_search_request_id=request_id,
        next_request_id=request_id + 1,
    )
    return finalize(
        next_state,
        RunGrepSearchEffect(
            request_id=request_id,
            root_path=grep_scope_root_path(state),
            query=stripped_query,
            show_hidden=state.show_hidden,
            include_globs=include_globs,
            exclude_globs=exclude_globs,
            target_paths=next_palette.grep_search.target_paths,
            filename_filter=next_palette.grep_search.filename_filter,
        ),
    )


def handle_set_grep_search_scope(
    state: AppState,
    action: SetGrepSearchScope,
) -> ReduceResult:
    if state.command_palette is None or state.command_palette.source != "grep_search":
        return finalize(state)
    if not is_grep_search_scope_available(state, action.scope):
        return notify(
            state,
            level="warning",
            message=grep_scope_unavailable_message(state, action.scope) or "Scope is unavailable",
        )
    target_paths = grep_scope_target_paths(state, action.scope)
    scope_message = grep_scope_unavailable_message(state, action.scope)
    next_palette = replace(
        state.command_palette,
        grep_search=replace(
            state.command_palette.grep_search,
            scope=action.scope,
            target_paths=target_paths,
            scope_message=scope_message,
            results=(),
            error_message=None,
        ),
        cursor_index=0,
    )
    return handle_set_grep_search_field(
        replace(state, command_palette=next_palette), "keyword", next_palette.grep_search.keyword
    ) if target_paths or action.scope == "current_directory" else finalize(
        replace(state, command_palette=next_palette, pending_grep_search_request_id=None)
    )


def handle_submit_file_search_palette(
    state: AppState,
    reduce_state,
) -> ReduceResult:
    results = state.command_palette.file_search.results
    message = state.command_palette.file_search.error_message or "No matching files"
    if not results:
        return notify(state, level="warning", message=message)

    selected_result = results[
        normalize_command_palette_cursor(state, state.command_palette.cursor_index)
    ]
    return request_palette_snapshot(
        state,
        reduce_state,
        path=resolve_parent_directory_path(selected_result.path)[1] or selected_result.path,
        cursor_path=selected_result.path,
    )


def handle_submit_grep_search_palette(
    state: AppState,
    reduce_state,
) -> ReduceResult:
    results = state.command_palette.grep_search.results
    message = state.command_palette.grep_search.error_message or "No matching lines"

    if not results:
        return notify(state, level="warning", message=message)

    selected_result = results[
        normalize_command_palette_cursor(state, state.command_palette.cursor_index)
    ]
    return request_palette_snapshot(
        state,
        reduce_state,
        path=resolve_parent_directory_path(selected_result.path)[1] or selected_result.path,
        cursor_path=selected_result.path,
    )


def handle_open_grep_result_in_editor(
    state: AppState,
    reduce_state,
) -> ReduceResult:
    del reduce_state
    results = state.command_palette.grep_search.results
    message = state.command_palette.grep_search.error_message or "No matching lines"

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


def handle_open_grep_result_in_gui_editor(
    state: AppState,
    reduce_state,
) -> ReduceResult:
    del reduce_state
    results = state.command_palette.grep_search.results
    message = state.command_palette.grep_search.error_message or "No matching lines"

    if not results:
        return notify(state, level="warning", message=message)

    selected_result = results[
        normalize_command_palette_cursor(state, state.command_palette.cursor_index)
    ]
    return run_external_launch_request(
        replace(state, notification=None),
        ExternalLaunchRequest(
            kind="open_gui_editor",
            path=selected_result.path,
            line_number=selected_result.line_number,
            column_number=selected_result.column_number,
        ),
    )


def handle_open_find_result_in_editor(
    state: AppState,
    reduce_state,
) -> ReduceResult:
    del reduce_state
    results = state.command_palette.file_search.results
    message = state.command_palette.file_search.error_message or "No matching files"
    if not results:
        return notify(state, level="warning", message=message)

    selected_result = results[
        normalize_command_palette_cursor(state, state.command_palette.cursor_index)
    ]
    return run_external_launch_request(
        replace(state, notification=None),
        ExternalLaunchRequest(kind="open_editor", path=selected_result.path, line_number=None),
    )


def handle_open_find_result_in_gui_editor(
    state: AppState,
    reduce_state,
) -> ReduceResult:
    del reduce_state
    results = state.command_palette.file_search.results
    message = state.command_palette.file_search.error_message or "No matching files"
    if not results:
        return notify(state, level="warning", message=message)

    selected_result = results[
        normalize_command_palette_cursor(state, state.command_palette.cursor_index)
    ]
    return run_external_launch_request(
        replace(state, notification=None),
        ExternalLaunchRequest(kind="open_gui_editor", path=selected_result.path),
    )


def handle_file_search_completed(
    state: AppState,
    action: FileSearchCompleted,
) -> ReduceResult:
    from .reducer_palette_replace_scope import (
        handle_file_search_completed as handle_replace_file_search_completed,
    )

    replace_result = handle_replace_file_search_completed(state, action)
    if replace_result is not None:
        return replace_result
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
    if not action.truncated and not is_regex_file_search_query(action.query):
        cache_query = action.query.casefold()
        cache_results = action.results

    current_results = state.command_palette.file_search.results
    next_results = action.results
    cursor_index = _preserve_search_cursor(state, current_results, next_results)
    include_globs, exclude_globs = validate_file_search_filters(
        state.command_palette.file_search.include_extensions,
        state.command_palette.file_search.exclude_extensions,
        target=state.command_palette.file_search.target,
    )

    return sync_file_search_preview(
        replace(
            state,
            command_palette=replace(
                state.command_palette,
                file_search=replace(
                    state.command_palette.file_search,
                    results=action.results,
                    error_message=None,
                    results_truncated=action.truncated,
                    cache_query=cache_query,
                    cache_results=cache_results,
                    cache_root_path=state.current_path,
                    cache_show_hidden=state.show_hidden,
                    cache_target=state.command_palette.file_search.target,
                    cache_include_extensions=include_globs,
                    cache_exclude_extensions=exclude_globs,
                ),
                cursor_index=cursor_index,
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
                        rff=replace(
                            state.command_palette.rff,
                            file_results=(),
                            file_error_message=action.message,
                            preview_results=(),
                            total_match_count=0,
                        ),
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
                    file_search=replace(
                        state.command_palette.file_search,
                        results=(),
                        error_message=action.message,
                        results_truncated=False,
                    ),
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


def _merge_file_search_results(
    current: tuple[FileSearchResultState, ...],
    incoming: tuple[FileSearchResultState, ...],
) -> tuple[FileSearchResultState, ...]:
    by_path = {result.path: result for result in current}
    by_path.update({result.path: result for result in incoming})
    return tuple(sorted(by_path.values(), key=lambda result: natural_sort_key(result.display_path)))


def _merge_grep_search_results(
    current: tuple[GrepSearchResultState, ...],
    incoming: tuple[GrepSearchResultState, ...],
) -> tuple[GrepSearchResultState, ...]:
    by_match = {(result.path, result.line_number): result for result in current}
    by_match.update({(result.path, result.line_number): result for result in incoming})
    return tuple(
        sorted(
            by_match.values(),
            key=lambda result: (result.display_path.casefold(), result.line_number),
        )
    )


def _preserve_search_cursor(
    state: AppState,
    current: tuple[FileSearchResultState | GrepSearchResultState, ...],
    merged: tuple[FileSearchResultState | GrepSearchResultState, ...],
) -> int:
    if (
        not current
        or not merged
        or state.command_palette is None
        or not state.command_palette.cursor_navigation_active
    ):
        return 0
    old_index = normalize_command_palette_cursor(state, state.command_palette.cursor_index)
    if old_index >= len(current):
        return 0
    selected_path = current[old_index].path
    for index, result in enumerate(merged):
        if result.path == selected_path:
            return index
    return min(old_index, len(merged) - 1)


def handle_file_search_results_updated(
    state: AppState,
    action: FileSearchResultsUpdated,
) -> ReduceResult:
    if not matches_search_completion(
        state,
        request_id=action.request_id,
        pending_request_id=state.pending_file_search_request_id,
        source="file_search",
        query=action.query,
    ):
        return finalize(state)
    palette = state.command_palette
    assert palette is not None
    current = palette.file_search.results
    merged = _merge_file_search_results(current, action.results)
    cursor_index = _preserve_search_cursor(state, current, merged)
    return sync_file_search_preview(
        replace(
            state,
            command_palette=replace(
                palette,
                file_search=replace(
                    palette.file_search,
                    results=merged,
                    error_message=None,
                    results_truncated=palette.file_search.results_truncated or action.truncated,
                ),
                cursor_index=cursor_index,
            ),
        )
    )


def handle_grep_search_completed(
    state: AppState,
    action: GrepSearchCompleted,
) -> ReduceResult:
    if action.request_id != state.pending_grep_search_request_id:
        return finalize(state)

    from .reducer_palette_replace_scope import (
        handle_grep_search_completed as handle_replace_grep_search_completed,
    )

    replace_result = handle_replace_grep_search_completed(state, action)
    if replace_result is not None:
        return replace_result

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


    if state.command_palette is None or state.command_palette.source != "grep_search":
        return finalize(state)

    current_results = state.command_palette.grep_search.results
    next_results = filter_grep_results_by_filename(
        tuple(
            result for result in action.results
            if _matches_grep_scope_target(
                result.path,
                state.command_palette.grep_search.target_paths,
            )
        ),
        state.command_palette.grep_search.filename_filter,
    )
    cursor_index = _preserve_search_cursor(state, current_results, next_results)

    return sync_grep_preview(
        replace(
            state,
            command_palette=replace(
                state.command_palette,
                grep_search=replace(
                    state.command_palette.grep_search,
                    results=next_results,
                    error_message=None,
                    results_truncated=action.truncated,
                ),
                cursor_index=cursor_index,
            ),
            pending_grep_search_request_id=None,
        )
    )


def handle_grep_search_results_updated(
    state: AppState,
    action: GrepSearchResultsUpdated,
) -> ReduceResult:
    if not matches_search_completion(
        state,
        request_id=action.request_id,
        pending_request_id=state.pending_grep_search_request_id,
        source="grep_search",
        query=action.query,
    ):
        return finalize(state)
    palette = state.command_palette
    assert palette is not None
    incoming = filter_grep_results_by_filename(
        tuple(
            result for result in action.results
            if _matches_grep_scope_target(
                result.path,
                palette.grep_search.target_paths,
            )
        ),
        palette.grep_search.filename_filter,
    )
    current = palette.grep_search.results
    merged = _merge_grep_search_results(current, incoming)
    cursor_index = _preserve_search_cursor(state, current, merged)
    return sync_grep_preview(
        replace(
            state,
            command_palette=replace(
                palette,
                grep_search=replace(
                    palette.grep_search,
                    results=merged,
                    error_message=None,
                    results_truncated=palette.grep_search.results_truncated or action.truncated,
                ),
                cursor_index=cursor_index,
            ),
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
                        grs=replace(
                            state.command_palette.grs,
                            grep_results=(),
                            grep_error_message=action.message,
                            preview_results=(),
                            total_match_count=0,
                        ),
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


    if state.command_palette is not None and action.invalid_query:
        return sync_grep_preview(
            replace(
                state,
                command_palette=replace(
                    state.command_palette,
                    grep_search=replace(
                        state.command_palette.grep_search,
                        results=(),
                        error_message=action.message,
                        results_truncated=False,
                    ),
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


FILE_SEARCH_TARGET_CYCLE: tuple[str, ...] = ("files", "directories", "all")


def _next_file_search_target(current: str, delta: int) -> str:
    index = FILE_SEARCH_TARGET_CYCLE.index(current)
    return FILE_SEARCH_TARGET_CYCLE[(index + delta) % len(FILE_SEARCH_TARGET_CYCLE)]


def handle_set_file_search_target(
    state: AppState,
    action: SetFileSearchTarget,
) -> ReduceResult:
    if state.command_palette is None or state.command_palette.source != "file_search":
        return finalize(state)
    if action.target == state.command_palette.file_search.target:
        return finalize(state)
    next_palette = replace(
        state.command_palette,
        file_search=replace(
            state.command_palette.file_search,
            target=action.target,
            results=(),
            error_message=None,
        ),
        cursor_index=0,
    )
    return handle_set_file_search_query(
        state, next_palette, state.command_palette.query,
    )


def handle_cycle_file_search_field(
    state: AppState,
    action: CycleFileSearchField,
) -> ReduceResult:
    if state.command_palette is None or state.command_palette.source != "file_search":
        return finalize(state)
    current = state.command_palette.file_search.active_field
    index = FILE_SEARCH_FIELDS.index(current)
    next_index = (index + action.delta) % len(FILE_SEARCH_FIELDS)
    next_palette = replace(
        state.command_palette,
        file_search=replace(
            state.command_palette.file_search,
            active_field=FILE_SEARCH_FIELDS[next_index],
        ),
    )
    return finalize(replace(state, command_palette=next_palette))


def selected_file_search_result(state: AppState) -> FileSearchResultState | None:
    if state.command_palette is None or state.command_palette.source != "file_search":
        return None
    results = state.command_palette.file_search.results
    if not results:
        return None
    cursor_index = normalize_command_palette_cursor(state, state.command_palette.cursor_index)
    if cursor_index >= len(results):
        return None
    return results[cursor_index]


def selected_grep_result(state: AppState) -> GrepSearchResultState | None:
    if state.command_palette is None or state.command_palette.source != "grep_search":
        return None
    results = state.command_palette.grep_search.results
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
    if selected_result is None:
        return finalize(replace(state, pending_child_pane_request_id=None))

    if selected_result.entry_type == "directory":
        if state.pending_child_pane_request_id is None and (
            state.child_pane.mode == "entries"
            and state.child_pane.directory_path == selected_result.path
        ):
            return finalize(state)
    else:
        if not (
            state.config.display.enable_text_preview
            or state.config.display.enable_pdf_preview
            or state.config.display.enable_office_preview
        ):
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
            enable_text_preview=state.config.display.enable_text_preview,
            enable_image_preview=state.config.display.enable_image_preview,
            image_preview_mode=state.config.display.image_preview_mode,
            enable_pdf_preview=state.config.display.enable_pdf_preview,
            enable_office_preview=state.config.display.enable_office_preview,
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
    if selected_result is None or not state.config.display.enable_text_preview:
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
            enable_text_preview=state.config.display.enable_text_preview,
            enable_image_preview=state.config.display.enable_image_preview,
            image_preview_mode=state.config.display.image_preview_mode,
            enable_pdf_preview=state.config.display.enable_pdf_preview,
            enable_office_preview=state.config.display.enable_office_preview,
            grep_result=selected_result,
            grep_context_lines=state.config.display.grep_preview_context_lines,
        ),
    )


def handle_sfg_keyword_changed(
    state: AppState,
    action: object,
) -> ReduceResult:
    """Handle keyword changes for selected-files-grep."""
    if state.command_palette is None or state.command_palette.source != "selected_files_grep":
        return finalize(state)

    next_palette = replace(
        state.command_palette,
        sfg=replace(
            state.command_palette.sfg,
            keyword=action.keyword,
            error_message=None,
        ),
        cursor_index=0,
    )
    stripped_query = action.keyword.strip()

    if not stripped_query:
        return sync_sfg_preview(
            replace(
                state,
                command_palette=replace(
                    next_palette,
                    sfg=replace(
                        next_palette.sfg,
                        results=(),
                        error_message=None,
                    ),
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

    target_set = frozenset(state.command_palette.sfg.target_paths)
    filtered_results = tuple(
        r for r in action.results
        if r.path in target_set
    )

    return sync_sfg_preview(
        replace(
            state,
            command_palette=replace(
                state.command_palette,
                sfg=replace(
                    state.command_palette.sfg,
                    results=filtered_results,
                    error_message=None,
                ),
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
                    sfg=replace(
                        state.command_palette.sfg,
                        results=(),
                        error_message=action.message,
                    ),
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
    action: object,
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
    results = state.command_palette.sfg.results
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
    if selected_result is None or not state.config.display.enable_text_preview:
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
            enable_text_preview=state.config.display.enable_text_preview,
            enable_image_preview=state.config.display.enable_image_preview,
            image_preview_mode=state.config.display.image_preview_mode,
            enable_pdf_preview=state.config.display.enable_pdf_preview,
            enable_office_preview=state.config.display.enable_office_preview,
            grep_result=selected_result,
            grep_context_lines=state.config.display.grep_preview_context_lines,
        ),
    )


def handle_open_search_workspace(
    state: AppState,
    action: OpenSearchWorkspace,
    reduce_state: ReducerFn,
) -> ReduceResult:
    """Open search results as a virtual workspace."""
    from urllib.parse import quote, urlencode


    # Get search results
    results = state.command_palette.file_search.results
    if not results:
        message = state.command_palette.file_search.error_message or "No matching files"
        return notify(state, level="warning", message=message)

    # Build virtual path
    query = state.command_palette.file_search.cache_query or ""
    target = state.command_palette.file_search.target
    hidden = state.show_hidden
    root = state.command_palette.file_search.cache_root_path or state.current_path
    include_globs, exclude_globs = validate_file_search_filters(
        state.command_palette.file_search.include_extensions,
        state.command_palette.file_search.exclude_extensions,
        target=target,
    )

    params = {
        "target": target,
        "hidden": "true" if hidden else "false",
        "root": root,
    }
    if include_globs:
        params["include"] = ",".join(include_globs)
    if exclude_globs:
        params["exclude"] = ",".join(exclude_globs)
    virtual_path = f"search://{quote(query)}?{urlencode(params, doseq=True)}"

    # Cache search results in search_workspaces (keep as FileSearchResultState)
    next_state = replace(
        state,
        search_workspaces={
            **state.search_workspaces,
            virtual_path: results,
        },
    )

    # Switch to browser mode if in transfer mode
    if state.layout_mode == "transfer":
        next_state = replace(next_state, layout_mode="browser")

    # Navigate to virtual path
    return reduce_state(
        next_state,
        RequestBrowserSnapshot(
            virtual_path,
            cursor_path=None,
            blocking=True,
        ),
    )
