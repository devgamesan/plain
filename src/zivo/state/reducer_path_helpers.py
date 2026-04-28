"""Path, selection, and lightweight search helpers for reducers."""

import ntpath
import os
from pathlib import Path

from zivo.windows_paths import (
    comparable_path,
    expand_windows_path,
    is_windows_drive_root,
    is_windows_drives_root,
    is_windows_path,
    list_windows_drive_paths,
    normalize_windows_path,
    paths_equal,
    split_windows_completion_query,
)

from .models import DirectoryEntryState, FileSearchResultState

REGEX_FILE_SEARCH_PREFIX = "re:"
REGEX_GREP_SEARCH_PREFIX = "re:"


def current_entry_paths(state) -> set[str]:
    return {entry.path for entry in active_current_entries(state)}


def active_current_entries(state) -> tuple[DirectoryEntryState, ...]:
    return state.current_pane.entries


def list_matching_directory_paths(query: str, base_path: str) -> tuple[str, ...]:
    """Return matching directory candidates for go-to-path completion."""

    return _list_matching_entry_paths(query, base_path, directories_only=True)


def list_matching_path_entries(query: str, base_path: str) -> tuple[str, ...]:
    """Return matching file or directory candidates for general path completion."""

    return _list_matching_entry_paths(query, base_path, directories_only=False)


def longest_common_completion_prefix(candidates: tuple[str, ...]) -> str:
    """Return the longest shared completion prefix across rendered candidates."""

    if not candidates:
        return ""
    prefix = os.path.commonprefix(candidates)
    if not prefix:
        return ""
    separator_index = prefix.rfind(os.sep)
    if os.altsep is not None:
        separator_index = max(separator_index, prefix.rfind(os.altsep))
    if separator_index <= 0:
        return prefix
    return prefix[: separator_index + 1]


def _list_matching_entry_paths(
    query: str,
    base_path: str,
    *,
    directories_only: bool,
) -> tuple[str, ...]:
    """Return matching completion candidates for a partially typed path."""

    raw_query = query.strip()
    windows_mode = _uses_windows_path_rules(base_path, raw_query)
    if windows_mode:
        windows_shortcut = split_windows_completion_query(raw_query)
        if windows_shortcut is not None:
            _, prefix = windows_shortcut
            return _list_windows_drive_candidates(prefix)
    elif not raw_query:
        return ()

    if not raw_query:
        return ()

    if windows_mode:
        resolved = expand_windows_path(raw_query, base_path)
        if resolved is None:
            return ()
        has_trailing_separator = raw_query.endswith(("\\", "/"))
        parent = resolved if has_trailing_separator else ntpath.dirname(resolved)
        prefix = "" if has_trailing_separator else ntpath.basename(resolved).casefold()
        if is_windows_drives_root(parent):
            return _list_windows_drive_candidates(prefix)
        if not os.path.isdir(parent):
            return ()
        matches: list[str] = []
        try:
            for child in os.scandir(parent):
                try:
                    if directories_only and not child.is_dir():
                        continue
                except OSError:
                    continue
                if prefix and not child.name.casefold().startswith(prefix):
                    continue
                matches.append(normalize_windows_path(child.path))
        except (OSError, PermissionError):
            return ()
        matches.sort(key=lambda path: (ntpath.basename(path).casefold(), path.casefold()))
        return tuple(matches)

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
                if directories_only and not child.is_dir():
                    continue
            except OSError:
                continue

            if prefix and not child.name.casefold().startswith(prefix):
                continue
            matches.append(normalize_windows_path(str(child.resolve())))
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
    if _uses_windows_path_rules(base_path, raw_query):
        normalized_path = normalize_windows_path(path)
        if raw_query.startswith("~"):
            rendered = normalized_path
        elif raw_query.startswith(("\\", "/")) or ":" in raw_query[:3]:
            rendered = normalized_path
        elif is_windows_drives_root(base_path) or is_windows_drive_root(normalized_path):
            rendered = normalized_path
        else:
            rendered = ntpath.relpath(normalized_path, normalize_windows_path(base_path))
        if append_separator and not rendered.endswith("\\"):
            rendered = f"{rendered.rstrip('\\')}\\"
        return rendered

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

    if _uses_windows_path_rules(base_path, query):
        expanded = expand_windows_path(query, base_path)
        if expanded is None:
            return None
        try:
            if not os.path.isdir(expanded):
                return None
            return normalize_windows_path(expanded)
        except (OSError, ValueError, RuntimeError):
            return None

    expanded = _resolve_input_path(query, base_path)
    if expanded is None:
        return None
    try:
        if not expanded.exists() or not expanded.is_dir():
            return None
        return normalize_windows_path(str(expanded))
    except (OSError, ValueError, RuntimeError):
        return None


def normalize_selected_paths(
    selected_paths: frozenset[str],
    entries: tuple[DirectoryEntryState, ...],
) -> frozenset[str]:
    return frozenset(
        path
        for path in selected_paths
        if any(paths_equal(path, entry.path) for entry in entries)
    )


def normalize_selection_anchor_path(
    anchor_path: str | None,
    visible_paths: tuple[str, ...],
) -> str | None:
    return _find_visible_path(anchor_path, visible_paths)


def move_cursor(
    current_path: str | None,
    visible_paths: tuple[str, ...],
    delta: int,
) -> str | None:
    if not visible_paths:
        return None

    current_index = _find_visible_path_index(current_path, visible_paths)
    if current_index is None:
        current_index = 0

    next_index = max(0, min(len(visible_paths) - 1, current_index + delta))
    return comparable_path(visible_paths[next_index])


def select_range_paths(
    anchor_path: str,
    cursor_path: str,
    visible_paths: tuple[str, ...],
) -> frozenset[str]:
    anchor_index = _find_visible_path_index(anchor_path, visible_paths)
    cursor_index = _find_visible_path_index(cursor_path, visible_paths)
    if anchor_index is None or cursor_index is None:
        return frozenset()
    start = min(anchor_index, cursor_index)
    end = max(anchor_index, cursor_index)
    return frozenset(visible_paths[start : end + 1])


def normalize_cursor_path(
    entries: tuple[DirectoryEntryState, ...],
    current_cursor: str | None,
) -> str | None:
    for entry in entries:
        if paths_equal(current_cursor, entry.path):
            return comparable_path(entry.path)
    if not entries:
        return None
    return comparable_path(entries[0].path)


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


def _list_windows_drive_candidates(prefix: str) -> tuple[str, ...]:
    matches = tuple(
        drive
        for drive in list_windows_drive_paths()
        if not prefix or drive[0].casefold().startswith(prefix)
    )
    return tuple(sorted(matches, key=lambda drive: drive.casefold()))


def _uses_windows_path_rules(base_path: str, query: str) -> bool:
    if is_windows_drives_root(base_path) or is_windows_path(base_path):
        return True
    normalized_query = query.strip().replace("/", "\\")
    if not normalized_query:
        return False
    if normalized_query.startswith("\\"):
        return True
    return bool(ntpath.splitdrive(normalized_query)[0])


def _find_visible_path(path: str | None, visible_paths: tuple[str, ...]) -> str | None:
    index = _find_visible_path_index(path, visible_paths)
    if index is None:
        return None
    return comparable_path(visible_paths[index])


def _find_visible_path_index(path: str | None, visible_paths: tuple[str, ...]) -> int | None:
    if path is None:
        return None
    for index, visible_path in enumerate(visible_paths):
        if paths_equal(path, visible_path):
            return index
    return None
