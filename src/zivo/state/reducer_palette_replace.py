"""Replace-related command palette reducers."""

from dataclasses import replace

from zivo.models import TextReplaceRequest

from .actions import (
    CycleFindReplaceField,
    CycleGrepReplaceField,
    CycleGrepReplaceSelectedField,
    CycleReplaceField,
    FileSearchCompleted,
    GrepSearchCompleted,
    TextReplaceApplied,
    TextReplaceApplyFailed,
    TextReplacePreviewCompleted,
    TextReplacePreviewFailed,
)
from .command_palette import normalize_command_palette_cursor
from .effects import (
    ReduceResult,
    RunGrepSearchEffect,
    RunTextReplaceApplyEffect,
    RunTextReplacePreviewEffect,
)
from .models import (
    AppState,
    GrepSearchResultState,
    NotificationState,
    PaneState,
    ReplacePreviewResultState,
)
from .reducer_common import browser_snapshot_invalidation_paths, finalize
from .reducer_palette_shared import (
    FIND_REPLACE_FIELDS,
    GREP_REPLACE_FIELDS,
    GREP_REPLACE_SELECTED_FIELDS,
    REPLACE_FIELDS,
    build_replace_preview_results,
    filter_grep_results_by_filename,
    matches_replace_preview,
    normalize_grep_extension_filters,
    notify,
    replace_grf_field,
    replace_replace_field,
    restore_browsing_from_palette,
)


def handle_set_replace_field(state: AppState, field, value: str) -> ReduceResult:
    next_palette = replace(
        replace_replace_field(state.command_palette, field=field, value=value),
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


def handle_set_find_replace_field(state: AppState, field, value: str) -> ReduceResult:
    if state.command_palette is None:
        return finalize(state)

    if field == "filename":
        return handle_set_rff_filename(state, value)
    return handle_set_rff_text_field(state, field, value)


def handle_set_rff_filename(state: AppState, value: str) -> ReduceResult:
    next_palette = replace(
        state.command_palette,
        rff_filename_query=value,
        rff_file_error_message=None,
        cursor_index=0,
    )
    query = value.strip()
    if not query:
        return finalize(
            replace(
                state,
                command_palette=replace(
                    next_palette,
                    rff_file_results=(),
                    rff_preview_results=(),
                    rff_error_message=None,
                    rff_status_message=None,
                    rff_total_match_count=0,
                ),
                child_pane=PaneState(directory_path=state.current_path, entries=()),
                pending_file_search_request_id=None,
            )
        )

    request_id = state.next_request_id
    from .effects import RunFileSearchEffect

    return finalize(
        replace(
            state,
            command_palette=next_palette,
            pending_file_search_request_id=request_id,
            next_request_id=request_id + 1,
        ),
        RunFileSearchEffect(
            request_id=request_id,
            root_path=state.current_path,
            query=query,
            show_hidden=state.show_hidden,
        ),
    )


def handle_set_rff_text_field(state: AppState, field: str, value: str) -> ReduceResult:
    if field == "find":
        next_palette = replace(
            state.command_palette,
            rff_find_text=value,
            rff_error_message=None,
            rff_status_message=None,
            cursor_index=0,
        )
    else:
        next_palette = replace(
            state.command_palette,
            rff_replacement_text=value,
            rff_error_message=None,
            rff_status_message=None,
            cursor_index=0,
        )

    find_text = next_palette.rff_find_text.strip()
    file_paths = tuple(r.path for r in next_palette.rff_file_results)
    if not find_text or not file_paths:
        return finalize(
            replace(
                state,
                command_palette=replace(
                    next_palette,
                    rff_preview_results=(),
                    rff_total_match_count=0,
                ),
                child_pane=PaneState(directory_path=state.current_path, entries=()),
                pending_replace_preview_request_id=None,
            )
        )

    request_id = state.next_request_id
    request = TextReplaceRequest(
        paths=file_paths,
        find_text=next_palette.rff_find_text,
        replace_text=next_palette.rff_replacement_text,
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


def handle_cycle_replace_field(state: AppState, action: CycleReplaceField) -> ReduceResult:
    if state.command_palette is None or state.command_palette.source != "replace_text":
        return finalize(state)
    current_index = REPLACE_FIELDS.index(state.command_palette.replace_active_field)
    next_index = (current_index + action.delta) % len(REPLACE_FIELDS)
    return finalize(
        replace(
            state,
            command_palette=replace(
                state.command_palette,
                replace_active_field=REPLACE_FIELDS[next_index],
            ),
        )
    )


def handle_cycle_find_replace_field(
    state: AppState,
    action: CycleFindReplaceField,
) -> ReduceResult:
    if state.command_palette is None or state.command_palette.source != "replace_in_found_files":
        return finalize(state)
    current_index = FIND_REPLACE_FIELDS.index(state.command_palette.rff_active_field)
    next_index = (current_index + action.delta) % len(FIND_REPLACE_FIELDS)
    return finalize(
        replace(
            state,
            command_palette=replace(
                state.command_palette,
                rff_active_field=FIND_REPLACE_FIELDS[next_index],
            ),
        )
    )


def handle_cycle_grep_replace_field(
    state: AppState,
    action: CycleGrepReplaceField,
) -> ReduceResult:
    if state.command_palette is None or state.command_palette.source != "replace_in_grep_files":
        return finalize(state)
    current_index = GREP_REPLACE_FIELDS.index(state.command_palette.grf_active_field)
    next_index = (current_index + action.delta) % len(GREP_REPLACE_FIELDS)
    return finalize(
        replace(
            state,
            command_palette=replace(
                state.command_palette,
                grf_active_field=GREP_REPLACE_FIELDS[next_index],
            ),
        )
    )


def handle_cycle_grep_replace_selected_field(
    state: AppState,
    action: CycleGrepReplaceSelectedField,
) -> ReduceResult:
    if state.command_palette is None or state.command_palette.source != "grep_replace_selected":
        return finalize(state)
    current_index = GREP_REPLACE_SELECTED_FIELDS.index(state.command_palette.grs_active_field)
    next_index = (current_index + action.delta) % len(GREP_REPLACE_SELECTED_FIELDS)
    return finalize(
        replace(
            state,
            command_palette=replace(
                state.command_palette,
                grs_active_field=GREP_REPLACE_SELECTED_FIELDS[next_index],
            ),
        )
    )


def handle_set_grep_replace_field(state: AppState, field, value: str) -> ReduceResult:
    if state.command_palette is None:
        return finalize(state)
    if field in ("keyword", "include", "exclude"):
        return handle_set_grf_keyword(state, field, value)
    if field == "replace":
        return handle_set_grf_replace(state, value)
    return handle_set_grf_filename(state, value)


def validate_grf_filters(palette) -> tuple[tuple[str, ...], tuple[str, ...]]:
    include_globs = normalize_grep_extension_filters(
        palette.grf_include_extensions,
        label="include",
    )
    exclude_globs = normalize_grep_extension_filters(
        palette.grf_exclude_extensions,
        label="exclude",
    )
    conflicts = tuple(sorted(set(include_globs) & set(exclude_globs)))
    if conflicts:
        formatted = ", ".join(glob.removeprefix("*.") for glob in conflicts)
        raise ValueError(
            f"Extensions cannot be included and excluded at the same time: {formatted}"
        )
    return include_globs, exclude_globs


def handle_set_grf_keyword(state: AppState, field, value: str) -> ReduceResult:
    next_palette = replace_grf_field(state.command_palette, field=field, value=value)
    next_palette = replace(next_palette, grf_grep_error_message=None, cursor_index=0)
    keyword = next_palette.grf_keyword.strip()
    if not keyword:
        return sync_grep_replace_preview(
            replace(
                state,
                command_palette=replace(
                    next_palette,
                    grf_grep_results=(),
                    grf_grep_error_message=None,
                    grf_preview_results=(),
                    grf_total_match_count=0,
                ),
                pending_grep_search_request_id=None,
            )
        )
    try:
        include_globs, exclude_globs = validate_grf_filters(next_palette)
    except ValueError as error:
        return sync_grep_replace_preview(
            replace(
                state,
                command_palette=replace(
                    next_palette,
                    grf_grep_results=(),
                    grf_grep_error_message=str(error),
                    grf_preview_results=(),
                    grf_total_match_count=0,
                ),
                pending_grep_search_request_id=None,
            )
        )

    request_id = state.next_request_id
    return finalize(
        replace(
            state,
            command_palette=next_palette,
            pending_grep_search_request_id=request_id,
            next_request_id=request_id + 1,
        ),
        RunGrepSearchEffect(
            request_id=request_id,
            root_path=state.current_path,
            query=keyword,
            show_hidden=state.show_hidden,
            include_globs=include_globs,
            exclude_globs=exclude_globs,
        ),
    )


def handle_set_grf_replace(state: AppState, value: str) -> ReduceResult:
    next_palette = replace(
        state.command_palette,
        grf_replacement_text=value,
        grf_error_message=None,
        grf_status_message=None,
        cursor_index=0,
    )
    return trigger_grf_preview(state, next_palette)


def handle_set_grf_filename(state: AppState, value: str) -> ReduceResult:
    next_palette = replace(
        state.command_palette,
        grf_filename_filter=value,
        grf_error_message=None,
        grf_status_message=None,
        cursor_index=0,
    )
    return trigger_grf_preview(state, next_palette)


def grf_unique_file_paths(grep_results: tuple[GrepSearchResultState, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(r.path for r in grep_results))


def trigger_grf_preview(state: AppState, next_palette) -> ReduceResult:
    keyword = next_palette.grf_keyword.strip()
    filtered_results = filter_grep_results_by_filename(
        next_palette.grf_grep_results,
        next_palette.grf_filename_filter,
    )
    file_paths = grf_unique_file_paths(filtered_results)
    if not keyword or not file_paths:
        return sync_grep_replace_preview(
            replace(
                state,
                command_palette=replace(
                    next_palette,
                    grf_preview_results=(),
                    grf_total_match_count=0,
                ),
                child_pane=PaneState(directory_path=state.current_path, entries=()),
                pending_replace_preview_request_id=None,
            )
        )
    request_id = state.next_request_id
    request = TextReplaceRequest(
        paths=file_paths,
        find_text=keyword,
        replace_text=next_palette.grf_replacement_text,
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


def handle_set_grep_replace_selected_field(state: AppState, field, value: str) -> ReduceResult:
    if state.command_palette is None:
        return finalize(state)
    if field == "keyword":
        return handle_set_grs_keyword(state, value)
    return handle_set_grs_replace(state, value)


def grs_unique_file_paths(grep_results: tuple[GrepSearchResultState, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(r.path for r in grep_results))


def handle_set_grs_keyword(state: AppState, value: str) -> ReduceResult:
    next_palette = replace(
        state.command_palette,
        grs_keyword=value,
        grs_grep_error_message=None,
        cursor_index=0,
    )
    keyword = next_palette.grs_keyword.strip()
    if not keyword:
        return sync_grep_replace_selected_preview(
            replace(
                state,
                command_palette=replace(
                    next_palette,
                    grs_grep_results=(),
                    grs_grep_error_message=None,
                    grs_preview_results=(),
                    grs_total_match_count=0,
                ),
                pending_grep_search_request_id=None,
            )
        )
    request_id = state.next_request_id
    return finalize(
        replace(
            state,
            command_palette=next_palette,
            pending_grep_search_request_id=request_id,
            next_request_id=request_id + 1,
        ),
        RunGrepSearchEffect(
            request_id=request_id,
            root_path=state.current_path,
            query=keyword,
            show_hidden=state.show_hidden,
        ),
    )


def handle_set_grs_replace(state: AppState, value: str) -> ReduceResult:
    next_palette = replace(
        state.command_palette,
        grs_replacement_text=value,
        grs_error_message=None,
        grs_status_message=None,
        cursor_index=0,
    )
    return trigger_grs_preview(state, next_palette)


def trigger_grs_preview(state: AppState, next_palette) -> ReduceResult:
    keyword = next_palette.grs_keyword.strip()
    file_paths = grs_unique_file_paths(next_palette.grs_grep_results)
    if not keyword or not file_paths:
        return sync_grep_replace_selected_preview(
            replace(
                state,
                command_palette=replace(
                    next_palette,
                    grs_preview_results=(),
                    grs_total_match_count=0,
                ),
                child_pane=PaneState(directory_path=state.current_path, entries=()),
                pending_replace_preview_request_id=None,
            )
        )
    request_id = state.next_request_id
    request = TextReplaceRequest(
        paths=file_paths,
        find_text=keyword,
        replace_text=next_palette.grs_replacement_text,
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


def handle_submit_replace_palette(state: AppState) -> ReduceResult:
    if state.pending_replace_preview_request_id is not None:
        return notify(state, level="warning", message="Replacement preview is still running")
    if state.command_palette is None:
        return finalize(state)
    if not state.command_palette.replace_find_text.strip():
        return notify(state, level="warning", message="Find text is required")
    if state.command_palette.replace_error_message is not None:
        return notify(state, level="warning", message=state.command_palette.replace_error_message)
    if not state.command_palette.replace_preview_results:
        message = state.command_palette.replace_status_message or "No matching files"
        return notify(state, level="warning", message=message)

    request_id = state.next_request_id
    request = TextReplaceRequest(
        paths=state.command_palette.replace_target_paths,
        find_text=state.command_palette.replace_find_text,
        replace_text=state.command_palette.replace_replacement_text,
    )
    next_state = restore_browsing_from_palette(state)
    return finalize(
        replace(
            next_state,
            pending_replace_apply_request_id=request_id,
            next_request_id=request_id + 1,
            notification=NotificationState(level="info", message="Applying replacement..."),
        ),
        RunTextReplaceApplyEffect(request_id=request_id, request=request),
    )


def handle_submit_find_and_replace_palette(state: AppState) -> ReduceResult:
    if state.pending_replace_preview_request_id is not None:
        return notify(state, level="warning", message="Replacement preview is still running")
    if state.pending_file_search_request_id is not None:
        return notify(state, level="warning", message="File search is still running")
    if state.command_palette is None:
        return finalize(state)
    if not state.command_palette.rff_find_text.strip():
        return notify(state, level="warning", message="Find text is required")
    if state.command_palette.rff_error_message is not None:
        return notify(state, level="warning", message=state.command_palette.rff_error_message)
    if not state.command_palette.rff_preview_results:
        message = state.command_palette.rff_status_message or "No matching files"
        return notify(state, level="warning", message=message)

    file_paths = tuple(r.path for r in state.command_palette.rff_file_results)
    request_id = state.next_request_id
    request = TextReplaceRequest(
        paths=file_paths,
        find_text=state.command_palette.rff_find_text,
        replace_text=state.command_palette.rff_replacement_text,
    )
    next_state = restore_browsing_from_palette(state)
    return finalize(
        replace(
            next_state,
            pending_replace_apply_request_id=request_id,
            next_request_id=request_id + 1,
            notification=NotificationState(level="info", message="Applying replacement..."),
        ),
        RunTextReplaceApplyEffect(request_id=request_id, request=request),
    )


def handle_submit_grep_replace_palette(state: AppState) -> ReduceResult:
    if state.pending_replace_preview_request_id is not None:
        return notify(state, level="warning", message="Replacement preview is still running")
    if state.pending_grep_search_request_id is not None:
        return notify(state, level="warning", message="Grep search is still running")
    if state.command_palette is None:
        return finalize(state)
    if not state.command_palette.grf_keyword.strip():
        return notify(state, level="warning", message="Keyword is required")
    if state.command_palette.grf_error_message is not None:
        return notify(state, level="warning", message=state.command_palette.grf_error_message)
    if not state.command_palette.grf_preview_results:
        message = state.command_palette.grf_status_message or "No matching files"
        return notify(state, level="warning", message=message)

    filtered_results = filter_grep_results_by_filename(
        state.command_palette.grf_grep_results,
        state.command_palette.grf_filename_filter,
    )
    file_paths = grf_unique_file_paths(filtered_results)
    request_id = state.next_request_id
    request = TextReplaceRequest(
        paths=file_paths,
        find_text=state.command_palette.grf_keyword,
        replace_text=state.command_palette.grf_replacement_text,
    )
    next_state = restore_browsing_from_palette(state)
    return finalize(
        replace(
            next_state,
            pending_replace_apply_request_id=request_id,
            next_request_id=request_id + 1,
            notification=NotificationState(level="info", message="Applying replacement..."),
        ),
        RunTextReplaceApplyEffect(request_id=request_id, request=request),
    )


def handle_submit_grep_replace_selected_palette(state: AppState) -> ReduceResult:
    if state.pending_replace_preview_request_id is not None:
        return notify(state, level="warning", message="Replacement preview is still running")
    if state.pending_grep_search_request_id is not None:
        return notify(state, level="warning", message="Grep search is still running")
    if state.command_palette is None:
        return finalize(state)
    if not state.command_palette.grs_keyword.strip():
        return notify(state, level="warning", message="Keyword is required")
    if state.command_palette.grs_error_message is not None:
        return notify(state, level="warning", message=state.command_palette.grs_error_message)
    if not state.command_palette.grs_preview_results:
        message = state.command_palette.grs_status_message or "No matching files"
        return notify(state, level="warning", message=message)

    file_paths = grs_unique_file_paths(state.command_palette.grs_grep_results)
    request_id = state.next_request_id
    request = TextReplaceRequest(
        paths=file_paths,
        find_text=state.command_palette.grs_keyword,
        replace_text=state.command_palette.grs_replacement_text,
    )
    next_state = restore_browsing_from_palette(state)
    return finalize(
        replace(
            next_state,
            pending_replace_apply_request_id=request_id,
            next_request_id=request_id + 1,
            notification=NotificationState(level="info", message="Applying replacement..."),
        ),
        RunTextReplaceApplyEffect(request_id=request_id, request=request),
    )


def handle_rff_file_search_completed(state: AppState, action: FileSearchCompleted) -> ReduceResult:
    if action.request_id != state.pending_file_search_request_id:
        return finalize(state)
    next_state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            rff_file_results=action.results,
            rff_file_error_message=None,
            cursor_index=0,
        ),
        pending_file_search_request_id=None,
    )
    find_text = next_state.command_palette.rff_find_text.strip()
    if not find_text or not action.results:
        return sync_find_replace_preview(
            replace(
                next_state,
                command_palette=replace(
                    next_state.command_palette,
                    rff_preview_results=(),
                    rff_total_match_count=0,
                ),
            )
        )
    file_paths = tuple(r.path for r in action.results)
    request_id = next_state.next_request_id
    request = TextReplaceRequest(
        paths=file_paths,
        find_text=next_state.command_palette.rff_find_text,
        replace_text=next_state.command_palette.rff_replacement_text,
    )
    return finalize(
        replace(
            next_state,
            pending_replace_preview_request_id=request_id,
            next_request_id=request_id + 1,
        ),
        RunTextReplacePreviewEffect(request_id=request_id, request=request),
    )


def handle_grf_grep_search_completed(state: AppState, action: GrepSearchCompleted) -> ReduceResult:
    next_state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            grf_grep_results=action.results,
            grf_grep_error_message=None,
            cursor_index=0,
        ),
        pending_grep_search_request_id=None,
    )
    keyword = next_state.command_palette.grf_keyword.strip()
    if not keyword or not action.results:
        return sync_grep_replace_preview(
            replace(
                next_state,
                command_palette=replace(
                    next_state.command_palette,
                    grf_preview_results=(),
                    grf_total_match_count=0,
                ),
            )
        )
    filtered_results = filter_grep_results_by_filename(
        action.results,
        next_state.command_palette.grf_filename_filter,
    )
    file_paths = grf_unique_file_paths(filtered_results)
    if not file_paths:
        return sync_grep_replace_preview(
            replace(
                next_state,
                command_palette=replace(
                    next_state.command_palette,
                    grf_preview_results=(),
                    grf_total_match_count=0,
                ),
            )
        )
    request_id = next_state.next_request_id
    request = TextReplaceRequest(
        paths=file_paths,
        find_text=keyword,
        replace_text=next_state.command_palette.grf_replacement_text,
    )
    return finalize(
        replace(
            next_state,
            pending_replace_preview_request_id=request_id,
            next_request_id=request_id + 1,
        ),
        RunTextReplacePreviewEffect(request_id=request_id, request=request),
    )


def handle_grs_grep_search_completed(state: AppState, action: GrepSearchCompleted) -> ReduceResult:
    target_set = frozenset(state.command_palette.grs_target_paths)
    filtered_results = tuple(r for r in action.results if r.path in target_set)
    next_state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            grs_grep_results=filtered_results,
            grs_grep_error_message=None,
            cursor_index=0,
        ),
        pending_grep_search_request_id=None,
    )
    keyword = next_state.command_palette.grs_keyword.strip()
    if not keyword or not filtered_results:
        return sync_grep_replace_selected_preview(
            replace(
                next_state,
                command_palette=replace(
                    next_state.command_palette,
                    grs_preview_results=(),
                    grs_total_match_count=0,
                ),
            )
        )
    file_paths = grs_unique_file_paths(filtered_results)
    request_id = next_state.next_request_id
    request = TextReplaceRequest(
        paths=file_paths,
        find_text=keyword,
        replace_text=next_state.command_palette.grs_replacement_text,
    )
    return finalize(
        replace(
            next_state,
            pending_replace_preview_request_id=request_id,
            next_request_id=request_id + 1,
        ),
        RunTextReplacePreviewEffect(request_id=request_id, request=request),
    )


def handle_text_replace_preview_completed(
    state: AppState,
    action: TextReplacePreviewCompleted,
) -> ReduceResult:
    if action.request_id != state.pending_replace_preview_request_id:
        return finalize(state)
    if state.command_palette is None:
        return finalize(state)
    if state.command_palette.source == "replace_in_found_files":
        return handle_rff_preview_completed(state, action)
    if state.command_palette.source == "replace_in_grep_files":
        return handle_grf_preview_completed(state, action)
    if state.command_palette.source == "grep_replace_selected":
        return handle_grs_preview_completed(state, action)
    if state.command_palette.source != "replace_text":
        return finalize(state)

    preview_results = build_replace_preview_results(state, action.result.changed_entries)
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
    return sync_replace_preview(next_state)


def handle_rff_preview_completed(
    state: AppState,
    action: TextReplacePreviewCompleted,
) -> ReduceResult:
    preview_results = build_replace_preview_results(state, action.result.changed_entries)
    status_message = None
    if action.result.skipped_paths:
        status_message = f"Skipped {len(action.result.skipped_paths)} unreadable file(s)"
    next_state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            rff_preview_results=preview_results,
            rff_error_message=None,
            rff_status_message=status_message,
            rff_total_match_count=action.result.total_match_count,
            cursor_index=0,
        ),
        pending_replace_preview_request_id=None,
    )
    return sync_find_replace_preview(next_state)


def handle_grf_preview_completed(
    state: AppState,
    action: TextReplacePreviewCompleted,
) -> ReduceResult:
    preview_results = build_replace_preview_results(state, action.result.changed_entries)
    status_message = None
    if action.result.skipped_paths:
        status_message = f"Skipped {len(action.result.skipped_paths)} unreadable file(s)"
    next_state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            grf_preview_results=preview_results,
            grf_error_message=None,
            grf_status_message=status_message,
            grf_total_match_count=action.result.total_match_count,
            cursor_index=0,
        ),
        pending_replace_preview_request_id=None,
    )
    return sync_grep_replace_preview(next_state)


def handle_grs_preview_completed(
    state: AppState,
    action: TextReplacePreviewCompleted,
) -> ReduceResult:
    preview_results = build_replace_preview_results(state, action.result.changed_entries)
    status_message = None
    if action.result.skipped_paths:
        status_message = f"Skipped {len(action.result.skipped_paths)} unreadable file(s)"
    next_state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            grs_preview_results=preview_results,
            grs_error_message=None,
            grs_status_message=status_message,
            grs_total_match_count=action.result.total_match_count,
            cursor_index=0,
        ),
        pending_replace_preview_request_id=None,
    )
    return sync_grep_replace_selected_preview(next_state)


def handle_text_replace_preview_failed(
    state: AppState,
    action: TextReplacePreviewFailed,
) -> ReduceResult:
    if action.request_id != state.pending_replace_preview_request_id:
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
                        rff_preview_results=(),
                        rff_error_message=action.message,
                        rff_status_message=None,
                        rff_total_match_count=0,
                        cursor_index=0,
                    ),
                    child_pane=PaneState(directory_path=state.current_path, entries=()),
                    pending_replace_preview_request_id=None,
                )
            )
        return notify(
            replace(state, pending_replace_preview_request_id=None),
            level="error",
            message=action.message,
        )

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
                        grf_preview_results=(),
                        grf_error_message=action.message,
                        grf_status_message=None,
                        grf_total_match_count=0,
                        cursor_index=0,
                    ),
                    child_pane=PaneState(directory_path=state.current_path, entries=()),
                    pending_replace_preview_request_id=None,
                )
            )
        return notify(
            replace(state, pending_replace_preview_request_id=None),
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
                        grs_preview_results=(),
                        grs_error_message=action.message,
                        grs_status_message=None,
                        grs_total_match_count=0,
                        cursor_index=0,
                    ),
                    child_pane=PaneState(directory_path=state.current_path, entries=()),
                    pending_replace_preview_request_id=None,
                )
            )
        return notify(
            replace(state, pending_replace_preview_request_id=None),
            level="error",
            message=action.message,
        )

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
    return notify(
        replace(state, pending_replace_preview_request_id=None),
        level="error",
        message=action.message,
    )


def handle_text_replace_applied(
    state: AppState,
    action: TextReplaceApplied,
    reduce_state,
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
    from .actions import RequestBrowserSnapshot

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


def handle_text_replace_apply_failed(
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


def selected_replace_preview_result(state: AppState) -> ReplacePreviewResultState | None:
    if state.command_palette is None or state.command_palette.source != "replace_text":
        return None
    results = state.command_palette.replace_preview_results
    if not results:
        return None
    return results[normalize_command_palette_cursor(state, state.command_palette.cursor_index)]


def sync_replace_preview(state: AppState) -> ReduceResult:
    selected_result = selected_replace_preview_result(state)
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
    if matches_replace_preview(state, selected_result):
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


def selected_find_replace_preview_result(state: AppState) -> ReplacePreviewResultState | None:
    if state.command_palette is None or state.command_palette.source != "replace_in_found_files":
        return None
    results = state.command_palette.rff_preview_results
    if not results:
        return None
    return results[normalize_command_palette_cursor(state, state.command_palette.cursor_index)]


def sync_find_replace_preview(state: AppState) -> ReduceResult:
    selected_result = selected_find_replace_preview_result(state)
    if selected_result is None:
        preview_message = "No matching files"
        if (
            state.command_palette is not None
            and state.command_palette.source == "replace_in_found_files"
        ):
            preview_message = state.command_palette.rff_status_message or preview_message
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
    if matches_replace_preview(state, selected_result):
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
                    state.command_palette.rff_status_message
                    if state.command_palette is not None
                    else None
                ),
            ),
        )
    )


def selected_grep_replace_preview_result(state: AppState) -> ReplacePreviewResultState | None:
    if state.command_palette is None or state.command_palette.source != "replace_in_grep_files":
        return None
    results = state.command_palette.grf_preview_results
    if not results:
        return None
    return results[normalize_command_palette_cursor(state, state.command_palette.cursor_index)]


def sync_grep_replace_preview(state: AppState) -> ReduceResult:
    selected_result = selected_grep_replace_preview_result(state)
    if selected_result is None:
        preview_message = "No matching files"
        if (
            state.command_palette is not None
            and state.command_palette.source == "replace_in_grep_files"
        ):
            preview_message = state.command_palette.grf_status_message or preview_message
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
    if matches_replace_preview(state, selected_result):
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
                    state.command_palette.grf_status_message
                    if state.command_palette is not None
                    else None
                ),
            ),
        )
    )


def selected_grep_replace_selected_preview_result(
    state: AppState,
) -> ReplacePreviewResultState | None:
    if state.command_palette is None or state.command_palette.source != "grep_replace_selected":
        return None
    results = state.command_palette.grs_preview_results
    if not results:
        return None
    cursor = normalize_command_palette_cursor(state, state.command_palette.cursor_index)
    return results[cursor]


def sync_grep_replace_selected_preview(state: AppState) -> ReduceResult:
    selected_result = selected_grep_replace_selected_preview_result(state)
    if selected_result is None:
        preview_message = "No matching files"
        if (
            state.command_palette is not None
            and state.command_palette.source == "grep_replace_selected"
        ):
            preview_message = state.command_palette.grs_status_message or preview_message
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
    if matches_replace_preview(state, selected_result):
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
                    state.command_palette.grs_status_message
                    if state.command_palette is not None
                    else None
                ),
            ),
        )
    )
