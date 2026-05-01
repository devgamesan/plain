"""Helpers for deriving visible search workspace entries."""

from collections import OrderedDict

from .models import AppState, DirectoryEntryState, GrepSearchResultState

_GREP_PATH_SEP = "\x00"


def encode_grep_result_path(real_path: str, line_number: int) -> str:
    return f"{real_path}{_GREP_PATH_SEP}{line_number}"


def decode_grep_result_path(encoded_path: str) -> tuple[str, int] | None:
    try:
        real_path, line_str = encoded_path.rsplit(_GREP_PATH_SEP, 1)
    except ValueError:
        return None
    try:
        return real_path, int(line_str)
    except ValueError:
        return None


def select_active_current_entries(state: AppState) -> tuple[DirectoryEntryState, ...]:
    workspace = state.search_workspace
    if workspace is None:
        return state.current_pane.entries
    if workspace.kind != "grep" or workspace.grep_display_mode == "match":
        return state.current_pane.entries
    return build_grep_file_entries(workspace.grep_results)


def build_grep_file_entries(
    grep_results: tuple[GrepSearchResultState, ...],
) -> tuple[DirectoryEntryState, ...]:
    file_entries: "OrderedDict[str, DirectoryEntryState]" = OrderedDict()
    for result in grep_results:
        if result.path in file_entries:
            continue
        file_entries[result.path] = DirectoryEntryState(
            path=result.path,
            name=result.display_path,
            kind="file",
            size_bytes=result.size_bytes,
            modified_at=result.modified_at,
        )
    return tuple(file_entries.values())


def normalize_grep_workspace_path(
    state: AppState,
    path: str | None,
) -> str | None:
    if path is None:
        return None
    workspace = state.search_workspace
    if workspace is None or workspace.kind != "grep":
        return path
    if workspace.grep_display_mode == "match":
        return path
    if decode_grep_result_path(path) is None:
        return path
    result = first_grep_result_for_encoded_path(workspace.grep_results, path)
    if result is None:
        return None
    return result.path


def normalize_grep_workspace_path_for_mode(
    grep_results: tuple[GrepSearchResultState, ...],
    path: str | None,
    mode: str,
) -> str | None:
    if path is None:
        return None
    if mode == "file":
        result = first_grep_result_for_encoded_path(grep_results, path)
        if result is not None:
            return result.path
        return path
    result = first_grep_result_for_file_path(grep_results, path)
    if result is not None:
        return encode_grep_result_path(result.path, result.line_number)
    return path


def normalize_selected_grep_workspace_paths(
    state: AppState,
    selected_paths: frozenset[str],
) -> frozenset[str]:
    workspace = state.search_workspace
    if workspace is None or workspace.kind != "grep" or workspace.grep_display_mode == "match":
        return selected_paths
    normalized = {
        result.path
        for path in selected_paths
        for result in _matching_grep_results(workspace.grep_results, path)
    }
    return frozenset(normalized)


def normalize_grep_workspace_selected_paths_for_mode(
    grep_results: tuple[GrepSearchResultState, ...],
    selected_paths: frozenset[str],
    mode: str,
) -> frozenset[str]:
    if mode == "file":
        normalized = {
            result.path
            for path in selected_paths
            for result in _matching_grep_results(grep_results, path)
        }
        return frozenset(normalized)
    normalized = {
        encode_grep_result_path(result.path, result.line_number)
        for path in selected_paths
        for result in _matching_grep_results(grep_results, path)
    }
    return frozenset(normalized)


def expand_grep_workspace_paths_for_match_mode(
    grep_results: tuple[GrepSearchResultState, ...],
    file_paths: frozenset[str],
) -> frozenset[str]:
    expanded = {
        encode_grep_result_path(result.path, result.line_number)
        for result in grep_results
        if result.path in file_paths
    }
    return frozenset(expanded)


def first_grep_result_for_encoded_path(
    grep_results: tuple[GrepSearchResultState, ...],
    encoded_path: str,
) -> GrepSearchResultState | None:
    decoded = decode_grep_result_path(encoded_path)
    if decoded is not None:
        real_path, line_number = decoded
        for result in grep_results:
            if result.path == real_path and result.line_number == line_number:
                return result
        return None
    for result in grep_results:
        if result.path == encoded_path:
            return result
    return None


def first_grep_result_for_file_path(
    grep_results: tuple[GrepSearchResultState, ...],
    file_path: str,
) -> GrepSearchResultState | None:
    for result in grep_results:
        if result.path == file_path:
            return result
    return None


def _matching_grep_results(
    grep_results: tuple[GrepSearchResultState, ...],
    path: str,
) -> tuple[GrepSearchResultState, ...]:
    if decode_grep_result_path(path) is not None:
        result = first_grep_result_for_encoded_path(grep_results, path)
        return () if result is None else (result,)
    return tuple(result for result in grep_results if result.path == path)
