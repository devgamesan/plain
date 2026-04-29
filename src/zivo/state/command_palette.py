"""Command palette definitions and filtering helpers."""

import os
import platform
from dataclasses import dataclass

from zivo.archive_utils import is_supported_archive_path
from zivo.platform_support import is_split_terminal_supported
from zivo.windows_paths import display_path

from .entry_state_helpers import select_visible_entry_states
from .models import AppState
from .selectors import (
    select_current_entry_for_path,
    select_has_visible_current_entries,
    select_single_target_entry,
    select_target_file_paths,
    select_target_paths,
)


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

    if state.command_palette.source == "replace_in_grep_files":
        return tuple(
            CommandPaletteItem(
                id=f"grf_preview_result:{index}",
                label=result.display_label,
                shortcut=None,
                enabled=True,
                path=result.path,
            )
            for index, result in enumerate(state.command_palette.grf_preview_results)
        )

    if state.command_palette.source == "grep_replace_selected":
        return tuple(
            CommandPaletteItem(
                id=f"grs_preview_result:{index}",
                label=result.display_label,
                shortcut=None,
                enabled=True,
                path=result.path,
            )
            for index, result in enumerate(state.command_palette.grs_preview_results)
        )

    query = state.command_palette.query

    if state.layout_mode == "transfer":
        return tuple(
            item
            for item in _build_transfer_command_palette_items(state)
            if _matches_query(item, query)
        )

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
    elif state.command_palette.source == "replace_in_grep_files":
        item_count = len(state.command_palette.grf_preview_results)
    elif state.command_palette.source == "grep_replace_selected":
        item_count = len(state.command_palette.grs_preview_results)
    elif state.command_palette.source == "history":
        item_count = len(get_command_palette_items(state))
    else:
        item_count = len(get_command_palette_items(state))
    if item_count == 0:
        return 0
    return max(0, min(item_count - 1, cursor_index))


def _build_command_palette_items(state: AppState) -> tuple[CommandPaletteItem, ...]:
    target_paths = select_target_paths(state)
    replace_target_paths = select_target_file_paths(state)
    selected_files_grep_target_paths = _selected_files_grep_target_paths(state)
    single_target_entry = select_single_target_entry(state)
    has_target = bool(target_paths)
    has_single_target = single_target_entry is not None
    current_path_is_bookmarked = state.current_path in state.config.bookmarks.paths
    has_visible_entries = select_has_visible_current_entries(state)
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
            shortcut="{",
            enabled=bool(state.history.back),
        ),
        CommandPaletteItem(
            id="go_forward",
            label="Go forward",
            shortcut="}",
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
            id="toggle_transfer_mode",
            label=(
                "Close transfer mode"
                if state.layout_mode == "transfer"
                else "Toggle transfer mode"
            ),
            shortcut="p",
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
        CommandPaletteItem(
            id="replace_in_grep_files",
            label="Replace text in grep results",
            shortcut=None,
            enabled=True,
        ),
        CommandPaletteItem(
            id="selected_files_grep",
            label="Grep in selected files",
            shortcut=None,
            enabled=bool(selected_files_grep_target_paths),
        ),
        CommandPaletteItem(
            id="grep_replace_selected",
            label="Grep and replace in selected files",
            shortcut=None,
            enabled=bool(replace_target_paths),
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
                id="create_symlink",
                label="Make symlink",
                shortcut=None,
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
                shortcut="M",
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


def _build_transfer_command_palette_items(state: AppState) -> tuple[CommandPaletteItem, ...]:
    target_paths = _transfer_target_paths(state)
    has_target = bool(target_paths)
    has_single_target = _transfer_single_target_entry(state) is not None
    has_visible_entries = bool(_transfer_visible_entries(state))
    can_paste = state.clipboard.mode != "none" and bool(state.clipboard.paths)
    tab_count = len(state.browser_tabs) or 1

    return (
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
            enabled=_active_transfer_pane_state(state) is not None,
        ),
        CommandPaletteItem(
            id="toggle_transfer_mode",
            label="Close transfer mode",
            shortcut="p",
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
            id="copy_targets",
            label="Copy selection",
            shortcut="c",
            enabled=has_target,
        ),
        CommandPaletteItem(
            id="cut_targets",
            label="Cut selection",
            shortcut="x",
            enabled=has_target,
        ),
        CommandPaletteItem(
            id="paste_clipboard",
            label="Paste clipboard",
            shortcut="v",
            enabled=can_paste,
        ),
        CommandPaletteItem(
            id="transfer_copy_to_opposite_pane",
            label="Copy to opposite pane",
            shortcut="y",
            enabled=has_target,
        ),
        CommandPaletteItem(
            id="transfer_move_to_opposite_pane",
            label="Move to opposite pane",
            shortcut="m",
            enabled=has_target,
        ),
        CommandPaletteItem(
            id="select_all",
            label="Select all",
            shortcut="a",
            enabled=has_visible_entries,
        ),
        CommandPaletteItem(
            id="rename",
            label="Rename",
            shortcut="r",
            enabled=has_single_target,
        ),
        CommandPaletteItem(
            id="create_symlink",
            label="Make symlink",
            shortcut=None,
            enabled=has_single_target,
        ),
        CommandPaletteItem(
            id="delete_targets",
            label="Move to trash",
            shortcut="d",
            enabled=has_target,
        ),
        CommandPaletteItem(
            id="toggle_hidden",
            label=_hidden_files_label(state),
            shortcut=".",
            enabled=True,
        ),
    )


def _matches_query(item: CommandPaletteItem, query: str) -> bool:
    if not query:
        return True
    lowered_query = query.casefold()
    return lowered_query in item.label.casefold()


def _display_path(path: str) -> str:
    """Replace home directory prefix with ~ for display."""

    rendered = display_path(path)
    if rendered != path:
        return rendered
    home = os.path.expanduser("~")
    if path.startswith(home + "/"):
        return "~" + path[len(home):]
    if path == home:
        return "~"
    return path


def _hidden_files_label(state: AppState) -> str:
    return "Hide hidden files" if state.show_hidden else "Show hidden files"


def _replace_target_file_paths(state: AppState) -> tuple[str, ...]:
    return select_target_file_paths(state)


def _selected_files_grep_target_paths(state: AppState) -> tuple[str, ...]:
    """Return target file paths for selected-files-grep."""
    target_paths = select_target_paths(state)
    if state.current_pane.selected_paths:
        return tuple(
            path
            for path in target_paths
            if (entry := select_current_entry_for_path(state, path)) is not None
            and entry.kind == "file"
        )

    cursor_entry = select_current_entry_for_path(state, state.current_pane.cursor_path)
    if cursor_entry is None or cursor_entry.kind != "file":
        return ()
    return (cursor_entry.path,)


def _active_transfer_pane_state(state: AppState):
    if state.layout_mode != "transfer":
        return None
    if state.active_transfer_pane == "left":
        return state.transfer_left
    return state.transfer_right


def _transfer_visible_entries(state: AppState):
    transfer = _active_transfer_pane_state(state)
    if transfer is None:
        return ()
    return select_visible_entry_states(
        transfer.pane.entries,
        state.directory_size_cache,
        state.show_hidden,
        "",
        False,
        state.sort,
    )


def _transfer_target_paths(state: AppState) -> tuple[str, ...]:
    transfer = _active_transfer_pane_state(state)
    if transfer is None:
        return ()
    visible_entries = _transfer_visible_entries(state)
    selected_paths = tuple(
        entry.path
        for entry in visible_entries
        if entry.path in transfer.pane.selected_paths
    )
    if selected_paths:
        return selected_paths
    if any(entry.path == transfer.pane.cursor_path for entry in visible_entries):
        return (transfer.pane.cursor_path,)
    return ()


def _transfer_single_target_entry(state: AppState):
    target_paths = _transfer_target_paths(state)
    if len(target_paths) != 1:
        return None
    target_path = target_paths[0]
    for entry in _transfer_visible_entries(state):
        if entry.path == target_path:
            return entry
    return None


def _is_empty_trash_supported() -> bool:
    """Check if empty trash is supported on current platform."""
    return platform.system() in ("Linux", "Darwin", "Windows")


def _is_split_terminal_supported() -> bool:
    """Check if the embedded split terminal is available on this platform."""
    return is_split_terminal_supported()
