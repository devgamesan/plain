"""Shared helpers for command palette reducers."""

import re
from dataclasses import replace
from pathlib import Path

from .actions import RequestBrowserSnapshot
from .effects import ReduceResult
from .models import (
    AppState,
    CommandPaletteState,
    FindReplaceFieldId,
    GrepReplaceFieldId,
    GrepReplaceSelectedFieldId,
    GrepSearchFieldId,
    GrepSearchResultState,
    HistoryAndNavigationPaletteState,
    NotificationState,
    ReplaceFieldId,
    ReplacePreviewResultState,
)
from .reducer_common import ReducerFn, finalize, is_regex_file_search_query
from .selectors import select_visible_current_entry_states

GREP_SEARCH_FIELDS: tuple[GrepSearchFieldId, ...] = ("keyword", "filename", "include", "exclude")
REPLACE_FIELDS: tuple[ReplaceFieldId, ...] = ("find", "replace")
FIND_REPLACE_FIELDS: tuple[FindReplaceFieldId, ...] = ("filename", "find", "replace")
GREP_REPLACE_FIELDS: tuple[GrepReplaceFieldId, ...] = (
    "keyword",
    "replace",
    "filename",
    "include",
    "exclude",
)
GREP_REPLACE_SELECTED_FIELDS: tuple[GrepReplaceSelectedFieldId, ...] = ("keyword", "replace")

_EXTENSION_SEPARATOR_RE = re.compile(r"[\s,]+")
_VALID_EXTENSION_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]*")


def grep_field_value(
    palette: CommandPaletteState,
    field: GrepSearchFieldId,
) -> str:
    if field == "keyword":
        return palette.grep_search.keyword
    if field == "filename":
        return palette.grep_search.filename_filter
    if field == "include":
        return palette.grep_search.include_extensions
    return palette.grep_search.exclude_extensions


def replace_grep_field(
    palette: CommandPaletteState,
    *,
    field: GrepSearchFieldId,
    value: str,
) -> CommandPaletteState:
    if field == "keyword":
        return replace(
            palette,
            query=value,
            grep_search=replace(palette.grep_search, keyword=value),
        )
    if field == "filename":
        return replace(
            palette,
            grep_search=replace(palette.grep_search, filename_filter=value),
        )
    if field == "include":
        return replace(
            palette,
            grep_search=replace(palette.grep_search, include_extensions=value),
        )
    return replace(
        palette,
        grep_search=replace(palette.grep_search, exclude_extensions=value),
    )


def replace_field_value(
    palette: CommandPaletteState,
    field: ReplaceFieldId,
) -> str:
    if field == "find":
        return palette.replace_find_text
    return palette.replace_replacement_text


def replace_replace_field(
    palette: CommandPaletteState,
    *,
    field: ReplaceFieldId,
    value: str,
) -> CommandPaletteState:
    if field == "find":
        return replace(palette, replace_find_text=value)
    return replace(palette, replace_replacement_text=value)


def grf_field_value(
    palette: CommandPaletteState,
    field: GrepReplaceFieldId,
) -> str:
    if field == "keyword":
        return palette.grf_keyword
    if field == "replace":
        return palette.grf_replacement_text
    if field == "filename":
        return palette.grf_filename_filter
    if field == "include":
        return palette.grf_include_extensions
    return palette.grf_exclude_extensions


def replace_grf_field(
    palette: CommandPaletteState,
    *,
    field: GrepReplaceFieldId,
    value: str,
) -> CommandPaletteState:
    if field == "keyword":
        return replace(palette, query=value, grf_keyword=value)
    if field == "replace":
        return replace(palette, grf_replacement_text=value)
    if field == "filename":
        return replace(palette, grf_filename_filter=value)
    if field == "include":
        return replace(palette, grf_include_extensions=value)
    return replace(palette, grf_exclude_extensions=value)


def grs_field_value(
    palette: CommandPaletteState,
    field: GrepReplaceSelectedFieldId,
) -> str:
    if field == "keyword":
        return palette.grs_keyword or palette.query
    return palette.grs_replacement_text


def replace_grs_field(
    palette: CommandPaletteState,
    *,
    field: GrepReplaceSelectedFieldId,
    value: str,
) -> CommandPaletteState:
    if field == "keyword":
        return replace(palette, grs_keyword=value)
    return replace(palette, grs_replacement_text=value)


def normalize_grep_extension_filters(
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


def validate_filename_filter(filename_query: str) -> str | None:
    """ファイル名フィルタの正規表現をバリデーションし、エラーメッセージを返す

    無効な正規表現の場合はエラーメッセージを返し、
    有効な場合は None を返す。
    """
    if not is_regex_file_search_query(filename_query):
        return None
    try:
        re.compile(filename_query[3:], re.IGNORECASE)
        return None
    except re.error as e:
        return f"Invalid regex pattern: {e}"


def filter_grep_results_by_filename(
    results: tuple[GrepSearchResultState, ...],
    filename_query: str,
) -> tuple[GrepSearchResultState, ...]:
    if not filename_query.strip():
        return results
    if is_regex_file_search_query(filename_query):
        try:
            pattern = re.compile(filename_query[3:], re.IGNORECASE)
            return tuple(result for result in results if pattern.search(result.display_path))
        except re.error:
            # バリデーション済みのため通常は到達しないが、安全性のため空を返す
            return ()
    lowered = filename_query.casefold()
    return tuple(result for result in results if lowered in result.display_path.casefold())


def notify(
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


def enter_palette(
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
            history_and_navigation=HistoryAndNavigationPaletteState(
                history_results=history_results,
            ),
        ),
        pending_file_search_request_id=None,
        pending_grep_search_request_id=None,
        pending_replace_preview_request_id=None,
        pending_replace_apply_request_id=None,
        delete_confirmation=None,
        name_conflict=None,
        attribute_inspection=None,
    )


def restore_browsing_from_palette(
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


def request_palette_snapshot(
    state: AppState,
    reduce_state: ReducerFn,
    *,
    path: str,
    cursor_path: str | None = None,
) -> ReduceResult:
    return reduce_state(
        restore_browsing_from_palette(state),
        RequestBrowserSnapshot(path, cursor_path=cursor_path, blocking=True),
    )


def matches_search_completion(
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


def selected_current_file_paths(state: AppState) -> tuple[str, ...]:
    selected_paths = tuple(
        entry.path
        for entry in select_visible_current_entry_states(state)
        if entry.path in state.current_pane.selected_paths and entry.kind == "file"
    )
    if state.current_pane.selected_paths:
        return selected_paths

    entry = next(
        (
            candidate
            for candidate in select_visible_current_entry_states(state)
            if candidate.path == state.current_pane.cursor_path
        ),
        None,
    )
    if entry is None or entry.kind != "file":
        return ()
    return (entry.path,)


def build_replace_preview_results(
    state: AppState,
    changed_entries,
) -> tuple[ReplacePreviewResultState, ...]:
    return tuple(
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
        for entry in changed_entries
    )


def matches_replace_preview(
    state: AppState,
    result: ReplacePreviewResultState,
) -> bool:
    return (
        state.child_pane.mode == "preview"
        and state.child_pane.preview_title == "Replace Preview"
        and state.child_pane.preview_path == result.path
        and state.child_pane.preview_content == result.diff_text
    )
