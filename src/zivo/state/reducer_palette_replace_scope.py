"""Unified scope-aware reducers for the text replacement palette."""

from dataclasses import replace

from zivo.models import TextReplaceRequest
from zivo.windows_paths import is_search_workspace_path, parse_search_workspace_path

from .actions import FileSearchCompleted, GrepSearchCompleted
from .actions_palette import SetReplaceScope
from .effects import (
    ReduceResult,
    RunFileSearchEffect,
    RunGrepSearchEffect,
    RunTextReplacePreviewEffect,
)
from .models import AppState, PaneState, ReplaceScope
from .reducer_common import finalize
from .reducer_palette_shared import (
    filter_grep_results_by_filename,
    normalize_grep_extension_filters,
    notify,
)


def _selected_file_paths(state: AppState) -> tuple[str, ...]:
    return tuple(
        entry.path
        for entry in state.current_pane.entries
        if entry.path in state.current_pane.selected_paths and entry.kind == "file"
    )


def _current_file_path(state: AppState) -> str | None:
    return next(
        (
            entry.path
            for entry in state.current_pane.entries
            if entry.path == state.current_pane.cursor_path and entry.kind == "file"
        ),
        None,
    )


def replace_scope_target_paths(state: AppState, scope: ReplaceScope) -> tuple[str, ...]:
    if scope == "current_file":
        return (_current_file_path(state),) if _current_file_path(state) else ()
    if scope == "selected_files":
        return _selected_file_paths(state)
    return ()


def replace_scope_available(state: AppState, scope: ReplaceScope) -> bool:
    if scope == "current_file":
        return _current_file_path(state) is not None
    if scope == "selected_files":
        return bool(_selected_file_paths(state))
    return True


def replace_scope_message(state: AppState, scope: ReplaceScope) -> str | None:
    if scope == "current_file" and _current_file_path(state) is None:
        return "Current file requires a file to be focused"
    if scope == "selected_files" and not _selected_file_paths(state):
        return "Selected files requires one or more selected files"
    return None


def default_replace_scope(state: AppState) -> ReplaceScope:
    if _selected_file_paths(state):
        return "selected_files"
    if _current_file_path(state) is not None:
        return "current_file"
    return "current_directory"


def replace_scope_root_path(state: AppState) -> str:
    if is_search_workspace_path(state.current_path):
        return parse_search_workspace_path(state.current_path)["root"] or state.current_path
    return state.current_path


def replace_scope_fields(scope: ReplaceScope) -> tuple[str, ...]:
    if scope == "found_files":
        return ("scope", "filename", "find", "replace")
    if scope in {"current_directory", "grep_result_files"}:
        return ("scope", "find", "replace", "filename", "include", "exclude")
    return ("scope", "find", "replace")


def handle_set_replace_scope(state: AppState, action: SetReplaceScope) -> ReduceResult:
    if state.command_palette is None or state.command_palette.source != "replace_text":
        return finalize(state)
    if not replace_scope_available(state, action.scope):
        return notify(
            state,
            level="warning",
            message=replace_scope_message(state, action.scope) or "Scope is unavailable",
        )
    palette = state.command_palette.replace_preview
    scope = action.scope
    next_palette = replace(
        palette,
        scope=scope,
        active_field="find" if scope != "found_files" else "filename",
        target_paths=replace_scope_target_paths(state, scope),
        file_results=(),
        grep_results=(),
        preview_results=(),
        total_match_count=0,
        error_message=None,
        status_message=None,
        scope_message=replace_scope_message(state, scope),
    )
    return finalize(
        replace(
            state,
            command_palette=replace(
                state.command_palette,
                replace_preview=next_palette,
                cursor_index=0,
            ),
            pending_file_search_request_id=None,
            pending_grep_search_request_id=None,
            pending_replace_preview_request_id=None,
        )
    )


def handle_cycle_replace_field(state: AppState, delta: int) -> ReduceResult:
    if state.command_palette is None or state.command_palette.source != "replace_text":
        return finalize(state)
    palette = state.command_palette.replace_preview
    fields = replace_scope_fields(palette.scope)
    active = fields[(fields.index(palette.active_field) + delta) % len(fields)]
    return finalize(
        replace(
            state,
            command_palette=replace(
                state.command_palette,
                replace_preview=replace(palette, active_field=active),
            ),
        )
    )


def handle_set_replace_field(state: AppState, field: str, value: str) -> ReduceResult:
    if state.command_palette is None or state.command_palette.source != "replace_text":
        return finalize(state)
    palette = state.command_palette.replace_preview
    if field == "scope":
        return finalize(state)
    field_names = {
        "find": "find_text",
        "replace": "replacement_text",
        "filename": "filename_filter",
        "include": "include_extensions",
        "exclude": "exclude_extensions",
    }
    next_palette = replace(
        palette,
        **{field_names[field]: value},
        error_message=None,
        status_message=None,
        scope_message=None,
        preview_results=(),
        total_match_count=0,
    )
    next_state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            replace_preview=next_palette,
            cursor_index=0,
        ),
    )
    return _refresh(next_state)


def _clear_preview(state: AppState) -> ReduceResult:
    return finalize(
        replace(
            state,
            child_pane=PaneState(directory_path=state.current_path, entries=()),
            pending_replace_preview_request_id=None,
        )
    )


def _refresh(state: AppState) -> ReduceResult:
    palette = state.command_palette.replace_preview
    if not palette.find_text.strip():
        return _clear_preview(state)
    if palette.scope in {"current_file", "selected_files"}:
        return _request_preview(state, palette.target_paths)
    if palette.scope == "found_files":
        if not palette.filename_filter.strip():
            return _clear_preview(state)
        request_id = state.next_request_id
        return finalize(
            replace(
                state,
                pending_file_search_request_id=request_id,
                next_request_id=request_id + 1,
            ),
            RunFileSearchEffect(
                request_id=request_id,
                root_path=replace_scope_root_path(state),
                query=palette.filename_filter.strip(),
                show_hidden=state.show_hidden,
            ),
        )
    try:
        include = normalize_grep_extension_filters(palette.include_extensions, label="include")
        exclude = normalize_grep_extension_filters(palette.exclude_extensions, label="exclude")
    except ValueError as error:
        return _clear_preview(
            replace(
                state,
                command_palette=replace(
                    state.command_palette,
                    replace_preview=replace(palette, error_message=str(error)),
                ),
            )
        )
    if set(include) & set(exclude):
        return _clear_preview(
            replace(
                state,
                command_palette=replace(
                    state.command_palette,
                    replace_preview=replace(
                        palette,
                        error_message="Extensions cannot be included and excluded at the same time",
                    ),
                ),
            )
        )
    request_id = state.next_request_id
    return finalize(
        replace(
            state,
            pending_grep_search_request_id=request_id,
            next_request_id=request_id + 1,
        ),
        RunGrepSearchEffect(
            request_id=request_id,
            root_path=replace_scope_root_path(state),
            query=palette.find_text.strip(),
            show_hidden=state.show_hidden,
            include_globs=include,
            exclude_globs=exclude,
        ),
    )


def _request_preview(state: AppState, paths: tuple[str, ...]) -> ReduceResult:
    if not paths:
        return _clear_preview(state)
    palette = state.command_palette.replace_preview
    request_id = state.next_request_id
    request = TextReplaceRequest(
        paths=paths,
        find_text=palette.find_text,
        replace_text=palette.replacement_text,
    )
    return finalize(
        replace(
            state,
            command_palette=replace(
                state.command_palette,
                replace_preview=replace(palette, target_paths=paths),
            ),
            pending_replace_preview_request_id=request_id,
            next_request_id=request_id + 1,
        ),
        RunTextReplacePreviewEffect(request_id=request_id, request=request),
    )


def handle_file_search_completed(
    state: AppState, action: FileSearchCompleted
) -> ReduceResult | None:
    if (
        state.command_palette is None
        or state.command_palette.source != "replace_text"
        or state.command_palette.replace_preview.scope != "found_files"
    ):
        return None
    if action.request_id != state.pending_file_search_request_id:
        return finalize(state)
    palette = state.command_palette.replace_preview
    next_state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            replace_preview=replace(palette, file_results=action.results),
        ),
        pending_file_search_request_id=None,
    )
    return _request_preview(next_state, tuple(result.path for result in action.results))


def handle_grep_search_completed(
    state: AppState, action: GrepSearchCompleted
) -> ReduceResult | None:
    if (
        state.command_palette is None
        or state.command_palette.source != "replace_text"
        or state.command_palette.replace_preview.scope
        not in {"current_directory", "grep_result_files"}
    ):
        return None
    if action.request_id != state.pending_grep_search_request_id:
        return finalize(state)
    palette = state.command_palette.replace_preview
    results = filter_grep_results_by_filename(action.results, palette.filename_filter)
    next_state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            replace_preview=replace(palette, grep_results=results),
        ),
        pending_grep_search_request_id=None,
    )
    return _request_preview(next_state, tuple(dict.fromkeys(result.path for result in results)))
