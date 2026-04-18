"""Command palette definitions and filtering helpers."""

import os
import platform
from dataclasses import dataclass

from zivo.archive_utils import is_supported_archive_path

from .models import AppState, DirectoryEntryState


@dataclass(frozen=True)
class CommandPaletteItem:
    """Runtime command entry exposed to reducer and selectors."""

    id: str
    label: str
    shortcut: str | None
    enabled: bool
    path: str | None = None


def get_command_palette_items(state: AppState) -> tuple[CommandPaletteItem, ...]:
    """Return visible command palette items for the active palette source."""

    if state.command_palette is None:
        return ()

    if state.command_palette.source == "file_search":
        return tuple(
            CommandPaletteItem(
                id=f"file_search_result:{index}",
                label=result.display_path,
                shortcut=None,
                enabled=True,
                path=result.path,
            )
            for index, result in enumerate(state.command_palette.file_search_results)
        )

    if state.command_palette.source == "grep_search":
        return tuple(
            CommandPaletteItem(
                id=f"grep_search_result:{index}",
                label=result.display_label,
                shortcut=None,
                enabled=True,
                path=result.path,
            )
            for index, result in enumerate(state.command_palette.grep_search_results)
        )

    if state.command_palette.source == "history":
        query = state.command_palette.query
        return tuple(
            item
            for item in (
                CommandPaletteItem(
                    id=f"history_result:{index}",
                    label=_display_path(path),
                    shortcut=None,
                    enabled=True,
                    path=path,
                )
                for index, path in enumerate(state.command_palette.history_results)
            )
            if _matches_query(item, query)
        )

    if state.command_palette.source == "bookmarks":
        query = state.command_palette.query
        return tuple(
            item
            for item in (
                CommandPaletteItem(
                    id=f"bookmark_result:{index}",
                    label=_display_path(path),
                    shortcut=None,
                    enabled=True,
                    path=path,
                )
                for index, path in enumerate(state.config.bookmarks.paths)
            )
            if _matches_query(item, query)
        )

    if state.command_palette.source == "go_to_path":
        return tuple(
            CommandPaletteItem(
                id=f"go_to_path_candidate:{index}",
                label=_display_path(path),
                shortcut=None,
                enabled=True,
                path=path,
            )
            for index, path in enumerate(state.command_palette.go_to_path_candidates)
        )

    query = state.command_palette.query

    return tuple(
        item for item in _build_command_palette_items(state) if _matches_query(item, query)
    )


def normalize_command_palette_cursor(state: AppState, cursor_index: int) -> int:
    """Clamp the palette cursor to the current filtered item list."""

    if state.command_palette is None:
        return 0
    if state.command_palette.source == "file_search":
        item_count = len(state.command_palette.file_search_results)
    elif state.command_palette.source == "grep_search":
        item_count = len(state.command_palette.grep_search_results)
    elif state.command_palette.source == "replace_text":
        item_count = len(state.command_palette.replace_preview_results)
    elif state.command_palette.source == "replace_in_found_files":
        item_count = len(state.command_palette.rff_preview_results)
    elif state.command_palette.source == "history":
        item_count = len(get_command_palette_items(state))
    else:
        item_count = len(get_command_palette_items(state))
    if item_count == 0:
        return 0
    return max(0, min(item_count - 1, cursor_index))


def _build_command_palette_items(state: AppState) -> tuple[CommandPaletteItem, ...]:
    target_paths = _select_target_paths(state)
    replace_target_paths = _replace_target_file_paths(state)
    single_target_entry = _single_target_entry(state, target_paths)
    has_target = bool(target_paths)
    has_single_target = single_target_entry is not None
    current_path_is_bookmarked = state.current_path in state.config.bookmarks.paths
    has_visible_entries = _has_visible_current_entries(state)
    tab_count = len(state.browser_tabs) or 1

    items = [
        CommandPaletteItem(
            id="file_search",
            label="Find files",
            shortcut="f",
            enabled=True,
        ),
        CommandPaletteItem(
            id="grep_search",
            label="Grep search",
            shortcut="g",
            enabled=True,
        ),
        CommandPaletteItem(
            id="history_search",
            label="History search",
            shortcut="H",
            enabled=True,
        ),
        CommandPaletteItem(
            id="bookmark_search",
            label="Show bookmarks",
            shortcut="b",
            enabled=True,
        ),
        CommandPaletteItem(
            id="go_back",
            label="Go back",
            shortcut="[",
            enabled=bool(state.history.back),
        ),
        CommandPaletteItem(
            id="go_forward",
            label="Go forward",
            shortcut="]",
            enabled=bool(state.history.forward),
        ),
        CommandPaletteItem(
            id="go_to_path",
            label="Go to path",
            shortcut="G",
            enabled=True,
        ),
        CommandPaletteItem(
            id="go_to_home_directory",
            label="Go to home directory",
            shortcut="~",
            enabled=True,
        ),
        CommandPaletteItem(
            id="reload_directory",
            label="Reload directory",
            shortcut="R",
            enabled=True,
        ),
        CommandPaletteItem(
            id="undo_last_operation",
            label="Undo last file operation",
            shortcut="z",
            enabled=bool(state.undo_stack),
        ),
        CommandPaletteItem(
            id="new_tab",
            label="New tab",
            shortcut="o",
            enabled=True,
        ),
        CommandPaletteItem(
            id="next_tab",
            label="Next tab",
            shortcut="tab",
            enabled=tab_count > 1,
        ),
        CommandPaletteItem(
            id="previous_tab",
            label="Previous tab",
            shortcut="shift+tab",
            enabled=tab_count > 1,
        ),
        CommandPaletteItem(
            id="close_current_tab",
            label="Close current tab",
            shortcut="w",
            enabled=tab_count > 1,
        ),
        CommandPaletteItem(
            id="toggle_split_terminal",
            label="Toggle split terminal",
            shortcut="t",
            enabled=True,
        ),
        CommandPaletteItem(
            id="select_all",
            label="Select all",
            shortcut="a",
            enabled=has_visible_entries,
        ),
        CommandPaletteItem(
            id="replace_text",
            label="Replace text in selected files",
            shortcut=None,
            enabled=bool(replace_target_paths),
        ),
        CommandPaletteItem(
            id="replace_in_found_files",
            label="Replace text in found files",
            shortcut=None,
            enabled=True,
        ),
    ]

    if has_single_target:
        items.append(
            CommandPaletteItem(
                id="show_attributes",
                label="Show attributes",
                shortcut="i",
                enabled=True,
            )
        )
        items.append(
            CommandPaletteItem(
                id="rename",
                label="Rename",
                shortcut="r",
                enabled=True,
            )
        )
        items.append(
            CommandPaletteItem(
                id="compress_as_zip",
                label="Compress as zip",
                shortcut=None,
                enabled=True,
            )
        )
        items.append(
            CommandPaletteItem(
                id="extract_archive",
                label="Extract archive",
                shortcut=None,
                enabled=single_target_entry.kind == "file"
                and is_supported_archive_path(single_target_entry.path),
            )
        )
        items.append(
            CommandPaletteItem(
                id="open_in_editor",
                label="Open in editor",
                shortcut="e",
                enabled=single_target_entry.kind == "file",
            )
        )
    elif has_target:
        items.append(
            CommandPaletteItem(
                id="compress_as_zip",
                label="Compress as zip",
                shortcut=None,
                enabled=True,
            )
        )

    if has_target:
        items.append(
            CommandPaletteItem(
                id="copy_path",
                label="Copy path",
                shortcut="C",
                enabled=True,
            )
        )
        items.append(
            CommandPaletteItem(
                id="delete_targets",
                label="Move to trash",
                shortcut="d",
                enabled=True,
            )
        )

    items.append(
        CommandPaletteItem(
            id="empty_trash",
            label="Empty trash",
            shortcut=None,
            enabled=_is_empty_trash_supported(),
        )
    )

    items.extend(
        [
            CommandPaletteItem(
                id="open_file_manager",
                label="Open in file manager",
                shortcut="m",
                enabled=True,
            ),
            CommandPaletteItem(
                id="open_terminal",
                label="Open terminal here",
                shortcut="T",
                enabled=True,
            ),
            CommandPaletteItem(
                id="run_shell_command",
                label="Run shell command",
                shortcut="!",
                enabled=True,
            ),
            CommandPaletteItem(
                id="remove_bookmark" if current_path_is_bookmarked else "add_bookmark",
                label=(
                    "Remove bookmark"
                    if current_path_is_bookmarked
                    else "Bookmark this directory"
                ),
                shortcut="B",
                enabled=True,
            ),
            CommandPaletteItem(
                id="toggle_hidden",
                label=_hidden_files_label(state),
                shortcut=".",
                enabled=True,
            ),
            CommandPaletteItem(
                id="edit_config",
                label="Edit config",
                shortcut=None,
                enabled=True,
            ),
            CommandPaletteItem(
                id="create_file",
                label="Create file",
                shortcut="n",
                enabled=True,
            ),
            CommandPaletteItem(
                id="create_dir",
                label="Create directory",
                shortcut="N",
                enabled=True,
            )
        ]
    )

    return tuple(items)


def _matches_query(item: CommandPaletteItem, query: str) -> bool:
    if not query:
        return True
    lowered_query = query.casefold()
    return lowered_query in item.label.casefold()


def _display_path(path: str) -> str:
    """Replace home directory prefix with ~ for display."""
    home = os.path.expanduser("~")
    if path.startswith(home + "/"):
        return "~" + path[len(home):]
    if path == home:
        return "~"
    return path


def _hidden_files_label(state: AppState) -> str:
    return "Hide hidden files" if state.show_hidden else "Show hidden files"


def _select_target_paths(state: AppState) -> tuple[str, ...]:
    selected_paths = tuple(
        entry.path
        for entry in _active_current_entries(state)
        if entry.path in state.current_pane.selected_paths
    )
    if selected_paths:
        return selected_paths

    cursor_entry = _current_entry(state)
    if cursor_entry is None:
        return ()
    return (cursor_entry.path,)


def _single_target_entry(
    state: AppState,
    target_paths: tuple[str, ...],
) -> DirectoryEntryState | None:
    if len(target_paths) != 1:
        return None
    return _entry_for_path(state, target_paths[0])


def _current_entry(state: AppState) -> DirectoryEntryState | None:
    return _entry_for_path(state, state.current_pane.cursor_path)


def _entry_for_path(state: AppState, path: str | None) -> DirectoryEntryState | None:
    if path is None:
        return None
    for entry in _active_current_entries(state):
        if entry.path == path:
            return entry
    return None


def _active_current_entries(state: AppState) -> tuple[DirectoryEntryState, ...]:
    return state.current_pane.entries


def _has_visible_current_entries(state: AppState) -> bool:
    query = state.filter.query.casefold()
    filter_is_active = state.filter.active and bool(state.filter.query)
    for entry in _active_current_entries(state):
        if entry.hidden and not state.show_hidden:
            continue
        if filter_is_active and query not in entry.name.casefold():
            continue
        return True
    return False


def _replace_target_file_paths(state: AppState) -> tuple[str, ...]:
    selected_paths = tuple(
        entry.path
        for entry in _active_current_entries(state)
        if entry.path in state.current_pane.selected_paths and entry.kind == "file"
    )
    if state.current_pane.selected_paths:
        return selected_paths

    cursor_entry = _current_entry(state)
    if cursor_entry is None or cursor_entry.kind != "file":
        return ()
    return (cursor_entry.path,)


def _is_empty_trash_supported() -> bool:
    """Check if empty trash is supported on current platform."""
    return platform.system() in ("Linux", "Darwin")
