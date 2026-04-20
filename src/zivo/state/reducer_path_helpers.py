"""Path, selection, and lightweight search helpers for reducers."""

import os
from pathlib import Path

from .models import DirectoryEntryState, FileSearchResultState

REGEX_FILE_SEARCH_PREFIX = "re:"
REGEX_GREP_SEARCH_PREFIX = "re:"


def current_entry_paths(state) -> set[str]:
    return {entry.path for entry in active_current_entries(state)}


def active_current_entries(state) -> tuple[DirectoryEntryState, ...]:
    return state.current_pane.entries


def list_matching_directory_paths(query: str, base_path: str) -> tuple[str, ...]:
    """Return matching directory candidates for go-to-path completion."""

    raw_query = query.strip()
    if not raw_query:
        return ()

    resolved = _resolve_input_path(raw_query, base_path)
    if resolved is None:
        return ()

    has_trailing_separator = raw_query.endswith(os.sep)
    if os.altsep is not None and raw_query.endswith(os.altsep):
        has_trailing_separator = True

    parent = resolved if has_trailing_separator else resolved.parent
    prefix = "" if has_trailing_separator else resolved.name.casefold()
    if not parent.exists() or not parent.is_dir():
        return ()

    matches: list[str] = []
    try:
        for child in parent.iterdir():
            try:
                if not child.is_dir():
                    continue
            except OSError:
                continue

            if prefix and not child.name.casefold().startswith(prefix):
                continue
            matches.append(str(child.resolve()))
    except (OSError, PermissionError):
        return ()

    matches.sort(key=lambda path: (Path(path).name.casefold(), path))
    return tuple(matches)


def format_go_to_path_completion(
    path: str,
    query: str,
    base_path: str,
    *,
    append_separator: bool,
) -> str:
    """Render a selected go-to-path completion in the user's current path style."""

    raw_query = query.strip()
    normalized_path = str(Path(path).resolve())
    if raw_query.startswith("~"):
        home = os.path.expanduser("~")
        if normalized_path.startswith(home + os.sep):
            rendered = "~" + normalized_path[len(home) :]
        elif normalized_path == home:
            rendered = "~"
        else:
            rendered = normalized_path
    elif raw_query.startswith(os.sep) or (
        os.altsep is not None and raw_query.startswith(os.altsep)
    ):
        rendered = normalized_path
    else:
        rendered = os.path.relpath(normalized_path, str(Path(base_path).resolve()))

    if append_separator and rendered != os.sep:
        rendered = rendered.rstrip(os.sep)
        if not rendered.endswith(os.sep):
            rendered = f"{rendered}{os.sep}"
    return rendered


def expand_and_validate_path(query: str, base_path: str) -> str | None:
    """Expand ~, ., .. and validate path exists and is a directory."""

    expanded = _resolve_input_path(query, base_path)
    if expanded is None:
        return None
    try:
        if not expanded.exists() or not expanded.is_dir():
            return None
        return str(expanded)
    except (OSError, ValueError, RuntimeError):
        return None


def normalize_selected_paths(
    selected_paths: frozenset[str],
    entries: tuple[DirectoryEntryState, ...],
) -> frozenset[str]:
    entry_paths = {entry.path for entry in entries}
    return frozenset(path for path in selected_paths if path in entry_paths)


def normalize_selection_anchor_path(
    anchor_path: str | None,
    visible_paths: tuple[str, ...],
) -> str | None:
    if anchor_path in visible_paths:
        return anchor_path
    return None


def move_cursor(
    current_path: str | None,
    visible_paths: tuple[str, ...],
    delta: int,
) -> str | None:
    if not visible_paths:
        return None

    if current_path in visible_paths:
        current_index = visible_paths.index(current_path)
    else:
        current_index = 0

    next_index = max(0, min(len(visible_paths) - 1, current_index + delta))
    return visible_paths[next_index]


def select_range_paths(
    anchor_path: str,
    cursor_path: str,
    visible_paths: tuple[str, ...],
) -> frozenset[str]:
    anchor_index = visible_paths.index(anchor_path)
    cursor_index = visible_paths.index(cursor_path)
    start = min(anchor_index, cursor_index)
    end = max(anchor_index, cursor_index)
    return frozenset(visible_paths[start : end + 1])


def normalize_cursor_path(
    entries: tuple[DirectoryEntryState, ...],
    current_cursor: str | None,
) -> str | None:
    entry_paths = {entry.path for entry in entries}
    if current_cursor in entry_paths:
        return current_cursor
    if not entries:
        return None
    return entries[0].path


def filter_file_search_results(
    results: tuple[FileSearchResultState, ...],
    normalized_query: str,
) -> tuple[FileSearchResultState, ...]:
    return tuple(
        result
        for result in results
        if normalized_query in Path(result.path).name.casefold()
    )


def is_regex_file_search_query(query: str) -> bool:
    return query.strip().startswith(REGEX_FILE_SEARCH_PREFIX)


def _resolve_input_path(query: str, base_path: str) -> Path | None:
    raw_query = query.strip()
    if not raw_query:
        return None

    candidate = Path(os.path.expanduser(raw_query))
    if not candidate.is_absolute():
        candidate = Path(base_path) / candidate

    try:
        return candidate.resolve(strict=False)
    except (OSError, ValueError, RuntimeError):
        return None
