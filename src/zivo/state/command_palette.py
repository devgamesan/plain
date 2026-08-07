"""Command palette definitions and filtering helpers."""

import os
import platform
from dataclasses import dataclass, replace

from zivo.archive_utils import is_supported_archive_path
from zivo.models import CustomActionContext, custom_action_matches
from zivo.platform_support import is_split_terminal_supported
from zivo.windows_paths import display_path, is_search_workspace_path

from .entry_state_helpers import select_visible_entry_states
from .models import AppState
from .selectors import (
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
    category: str = "System"
    keywords: tuple[str, ...] = ()
    context_priority: int = 100
    disabled_reason: str | None = None


@dataclass(frozen=True)
class CommandPaletteMetadata:
    """Stable discovery metadata shared by palette evaluation and rendering."""

    category: str
    keywords: tuple[str, ...] = ()
    context_priority: int = 100


_COMMAND_METADATA: dict[str, CommandPaletteMetadata] = {
    "file_search": CommandPaletteMetadata("Search", ("find", "files", "filename"), 20),
    "grep_search": CommandPaletteMetadata(
        "Search", ("grep", "search", "search contents", "text", "content", "contents"), 21
    ),
    "history_search": CommandPaletteMetadata("Navigate", ("history", "recent"), 30),
    "bookmark_search": CommandPaletteMetadata("Navigate", ("bookmark", "saved"), 31),
    "go_back": CommandPaletteMetadata("Navigate", ("back", "previous"), 32),
    "go_forward": CommandPaletteMetadata("Navigate", ("forward", "next"), 33),
    "go_to_path": CommandPaletteMetadata("Navigate", ("go", "path", "directory"), 34),
    "go_to_home_directory": CommandPaletteMetadata("Navigate", ("home", "~"), 35),
    "reload_directory": CommandPaletteMetadata("View", ("reload", "refresh"), 70),
    "undo_last_operation": CommandPaletteMetadata("System", ("undo", "revert"), 50),
    "new_tab": CommandPaletteMetadata("Navigate", ("tab", "open"), 60),
    "next_tab": CommandPaletteMetadata("Navigate", ("tab", "forward"), 61),
    "previous_tab": CommandPaletteMetadata("Navigate", ("tab", "back"), 62),
    "close_current_tab": CommandPaletteMetadata("Navigate", ("tab", "close"), 63),
    "exit": CommandPaletteMetadata("System", ("quit", "close", "exit"), 95),
    "toggle_transfer_mode": CommandPaletteMetadata(
        "Navigate", ("transfer", "two pane", "dual pane"), 80
    ),
    "select_all": CommandPaletteMetadata("File", ("select", "all", "mark"), 40),
    "replace_text": CommandPaletteMetadata(
        "File", ("replace", "substitute", "edit text"), 45
    ),
    "show_attributes": CommandPaletteMetadata(
        "View", ("attributes", "properties", "info", "stat"), 42
    ),
    "rename": CommandPaletteMetadata("File", ("rename", "move", "name"), 12),
    "change_permissions": CommandPaletteMetadata(
        "File", ("permissions", "chmod", "mode"), 75
    ),
    "change_owner": CommandPaletteMetadata("File", ("owner", "group", "chown"), 76),
    "create_symlink": CommandPaletteMetadata(
        "File", ("symlink", "link", "symbolic"), 77
    ),
    "compress_as_zip": CommandPaletteMetadata(
        "File", ("compress", "zip", "archive"), 78
    ),
    "extract_archive": CommandPaletteMetadata(
        "File", ("extract", "unzip", "archive", "expand"), 79
    ),
    "open": CommandPaletteMetadata("File", ("open", "launch", "view"), 10),
    "edit_with_terminal_editor": CommandPaletteMetadata(
        "File", ("edit", "editor", "terminal", "vim", "nano"), 11
    ),
    "edit_with_gui_editor": CommandPaletteMetadata(
        "File", ("edit", "editor", "gui", "code"), 13
    ),
    "copy_path": CommandPaletteMetadata("File", ("path", "clipboard"), 8),
    "copy_targets": CommandPaletteMetadata(
        "File", ("copy", "duplicate", "yank"), 14
    ),
    "cut_targets": CommandPaletteMetadata("File", ("cut", "move"), 15),
    "paste_clipboard": CommandPaletteMetadata(
        "File", ("paste", "clipboard", "insert"), 16
    ),
    "delete_targets": CommandPaletteMetadata(
        "File", ("delete", "trash", "remove"), 17
    ),
    "open_current_directory_with_file_manager": CommandPaletteMetadata(
        "System", ("open", "folder", "file manager", "explorer"), 82
    ),
    "open_current_directory_with_terminal": CommandPaletteMetadata(
        "System", ("terminal", "shell", "console"), 81
    ),
    "run_shell_command": CommandPaletteMetadata(
        "System", ("shell", "command", "terminal", "console"), 83
    ),
    "add_bookmark": CommandPaletteMetadata("Navigate", ("bookmark", "save"), 55),
    "remove_bookmark": CommandPaletteMetadata("Navigate", ("bookmark", "remove"), 55),
    "toggle_hidden": CommandPaletteMetadata(
        "View", ("hidden", "dotfiles", "show", "hide"), 71
    ),
    "show_about": CommandPaletteMetadata("System", ("about", "version", "help"), 98),
    "edit_config": CommandPaletteMetadata(
        "System", ("config", "settings", "preferences"), 90
    ),
    "create_file": CommandPaletteMetadata("File", ("new", "file", "create", "touch"), 18),
    "create_dir": CommandPaletteMetadata(
        "File", ("new", "directory", "folder", "create", "mkdir"), 19
    ),
    "transfer_copy_to_opposite_pane": CommandPaletteMetadata(
        "File", ("copy", "transfer", "other pane"), 20
    ),
    "transfer_move_to_opposite_pane": CommandPaletteMetadata(
        "File", ("move", "transfer", "other pane"), 21
    ),
}

_CATEGORY_ORDER = ("Navigate", "File", "Search", "View", "System", "Custom actions")


SEARCH_WORKSPACE_COMMAND_IDS = frozenset(
    {
        "history_search",
        "bookmark_search",
        "go_back",
        "go_forward",
        "go_to_path",
        "go_to_home_directory",
        "undo_last_operation",
        "new_tab",
        "next_tab",
        "previous_tab",
        "close_current_tab",
        "exit",
        "select_all",
        "show_attributes",
        "edit_with_terminal_editor",
        "edit_with_gui_editor",
        "copy_path",
        "toggle_hidden",
        "show_about",
        "edit_config",
    }
)


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
            for index, result in enumerate(state.command_palette.file_search.results)
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
            for index, result in enumerate(state.command_palette.grep_search.results)
        )

    if state.command_palette.source == "history":
        query = state.command_palette.query
        history_results = state.command_palette.history_and_navigation.history_results
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
                for index, path in enumerate(history_results)
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
        go_to_path_candidates = state.command_palette.history_and_navigation.go_to_path_candidates
        return tuple(
            CommandPaletteItem(
                id=f"go_to_path_candidate:{index}",
                label=_display_path(path),
                shortcut=None,
                enabled=True,
                path=path,
            )
            for index, path in enumerate(go_to_path_candidates)
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
            for index, result in enumerate(state.command_palette.grf.preview_results)
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
            for index, result in enumerate(state.command_palette.grs.preview_results)
        )

    query = state.command_palette.query

    items = (
        _build_transfer_command_palette_items(state)
        if state.layout_mode == "transfer"
        else _build_command_palette_items(state)
    )
    return _prepare_command_palette_items(state, items, query)


def normalize_command_palette_cursor(state: AppState, cursor_index: int) -> int:
    """Clamp the palette cursor to the current filtered item list."""

    if state.command_palette is None:
        return 0
    if state.command_palette.source == "file_search":
        item_count = len(state.command_palette.file_search.results)
    elif state.command_palette.source == "grep_search":
        item_count = len(state.command_palette.grep_search.results)
    elif state.command_palette.source == "replace_text":
        item_count = len(state.command_palette.replace_preview.preview_results)
    elif state.command_palette.source == "replace_in_found_files":
        item_count = len(state.command_palette.rff.preview_results)
    elif state.command_palette.source == "replace_in_grep_files":
        item_count = len(state.command_palette.grf.preview_results)
    elif state.command_palette.source == "grep_replace_selected":
        item_count = len(state.command_palette.grs.preview_results)
    elif state.command_palette.source == "history":
        item_count = len(get_command_palette_items(state))
    else:
        item_count = len(get_command_palette_items(state))
    if item_count == 0:
        return 0
    return max(0, min(item_count - 1, cursor_index))


def _build_command_palette_items(state: AppState) -> tuple[CommandPaletteItem, ...]:
    target_paths = select_target_paths(state)
    single_target_entry = select_single_target_entry(state)
    has_target = bool(target_paths)
    has_single_target = single_target_entry is not None
    current_path_is_bookmarked = state.current_path in state.config.bookmarks.paths
    has_visible_entries = select_has_visible_current_entries(state)
    tab_count = len(state.browser_tabs) or 1
    chmod_supported = _is_chmod_supported()

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
            shortcut=None,
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
            shortcut=None,
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
            shortcut=None,
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
            id="exit",
            label="Exit",
            shortcut="q",
            enabled=True,
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
            label="Replace text",
            shortcut=None,
            enabled=True,
        ),
    ]

    is_search_workspace = is_search_workspace_path(state.current_path)

    items.extend(_build_custom_action_items(state))

    if has_single_target:
        items.append(
            CommandPaletteItem(
                id="show_attributes",
                label="Show attributes",
                shortcut=None,
                enabled=True,
            )
        )
        if not is_search_workspace:
            items.append(
                CommandPaletteItem(
                    id="rename",
                    label="Rename",
                    shortcut="r",
                    enabled=True,
                )
            )
            if chmod_supported:
                items.append(
                    CommandPaletteItem(
                        id="change_permissions",
                        label="Change permissions",
                        shortcut=None,
                        enabled=True,
                    )
                )
                items.append(
                    CommandPaletteItem(
                        id="change_owner",
                        label="Change owner",
                        shortcut=None,
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
                id="open",
                label="Open",
                shortcut="enter",
                enabled=single_target_entry.kind == "file",
            )
        )
        items.append(
            CommandPaletteItem(
                id="edit_with_terminal_editor",
                label="Edit with terminal editor",
                shortcut="e",
                enabled=single_target_entry.kind == "file",
            )
        )
        items.append(
            CommandPaletteItem(
                id="edit_with_gui_editor",
                label="Edit with GUI editor",
                shortcut=None,
                enabled=single_target_entry.kind == "file",
            )
        )
    elif has_target and not is_search_workspace:
        if chmod_supported:
            items.append(
                CommandPaletteItem(
                    id="change_permissions",
                    label="Change permissions",
                    shortcut=None,
                    enabled=True,
                )
            )
            items.append(
                CommandPaletteItem(
                    id="change_owner",
                    label="Change owner",
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

    if has_target:
        items.append(
            CommandPaletteItem(
                id="copy_path",
                label="Copy path",
                shortcut=None,
                enabled=True,
            )
        )
        if not is_search_workspace:
            items.append(
                CommandPaletteItem(
                    id="delete_targets",
                    label="Move to trash",
                    shortcut="d",
                    enabled=True,
                )
            )

    items.extend(
        [
            CommandPaletteItem(
                id="open_current_directory_with_file_manager",
                label="Open current directory with file manager",
                shortcut=None,
                enabled=not is_search_workspace,
            ),
            CommandPaletteItem(
                id="open_current_directory_with_terminal",
                label="Open current directory with terminal",
                shortcut=None,
                enabled=not is_search_workspace,
            ),
            CommandPaletteItem(
                id="run_shell_command",
                label="Run shell command",
                shortcut="!",
                enabled=not is_search_workspace,
            ),
            CommandPaletteItem(
                id="remove_bookmark" if current_path_is_bookmarked else "add_bookmark",
                label=(
                    "Remove bookmark"
                    if current_path_is_bookmarked
                    else "Bookmark this directory"
                ),
                shortcut=None,
                enabled=not is_search_workspace,
            ),
            CommandPaletteItem(
                id="toggle_hidden",
                label=_hidden_files_label(state),
                shortcut=".",
                enabled=True,
            ),
            CommandPaletteItem(
                id="show_about",
                label="About zivo",
                shortcut=None,
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
                enabled=not is_search_workspace,
            ),
            CommandPaletteItem(
                id="create_dir",
                label="Create directory",
                shortcut="N",
                enabled=not is_search_workspace,
            )
        ]
    )

    existing_ids = {item.id for item in items}
    items.extend(
        item for item in _build_contextual_command_items(state) if item.id not in existing_ids
    )
    return tuple(items)


def _build_contextual_command_items(state: AppState) -> tuple[CommandPaletteItem, ...]:
    """Build target-dependent commands even when they are currently unavailable."""

    target_paths = select_target_paths(state)
    single_target = select_single_target_entry(state)
    has_target = bool(target_paths)
    has_single_target = single_target is not None
    search_workspace = is_search_workspace_path(state.current_path)
    chmod_supported = _is_chmod_supported()
    items = (
        CommandPaletteItem("show_attributes", "Show attributes", None, has_single_target),
        CommandPaletteItem("rename", "Rename", "r", has_single_target and not search_workspace),
        CommandPaletteItem(
            "change_permissions",
            "Change permissions",
            None,
            has_target and chmod_supported and not search_workspace,
        ),
        CommandPaletteItem(
            "change_owner",
            "Change owner",
            None,
            has_target and chmod_supported and not search_workspace,
        ),
        CommandPaletteItem(
            "create_symlink", "Make symlink", None, has_single_target and not search_workspace
        ),
        CommandPaletteItem(
            "compress_as_zip", "Compress as zip", None, has_target and not search_workspace
        ),
        CommandPaletteItem(
            "extract_archive",
            "Extract archive",
            None,
            bool(
                has_single_target
                and single_target is not None
                and single_target.kind == "file"
                and is_supported_archive_path(single_target.path)
                and not search_workspace
            ),
        ),
        CommandPaletteItem(
            "open",
            "Open",
            "enter",
            bool(has_single_target and single_target and single_target.kind == "file"),
        ),
        CommandPaletteItem(
            "edit_with_terminal_editor",
            "Edit with terminal editor",
            "e",
            bool(has_single_target and single_target and single_target.kind == "file"),
        ),
        CommandPaletteItem(
            "edit_with_gui_editor",
            "Edit with GUI editor",
            None,
            bool(has_single_target and single_target and single_target.kind == "file"),
        ),
        CommandPaletteItem("copy_path", "Copy path", None, has_target),
        CommandPaletteItem("copy_targets", "Copy selection or cursor target", "c", has_target),
        CommandPaletteItem(
            "cut_targets",
            "Cut selection or cursor target",
            "x",
            has_target and not search_workspace,
        ),
        CommandPaletteItem(
            "paste_clipboard",
            "Paste clipboard",
            "v",
            bool(state.clipboard.paths) and not search_workspace,
        ),
        CommandPaletteItem(
            "delete_targets", "Move to trash", "d", has_target and not search_workspace
        ),
    )
    return items


def _prepare_command_palette_items(
    state: AppState,
    items: tuple[CommandPaletteItem, ...],
    query: str,
) -> tuple[CommandPaletteItem, ...]:
    """Apply shared metadata, availability reasons, and deterministic ranking."""

    search_workspace = is_search_workspace_path(state.current_path)
    decorated: list[CommandPaletteItem] = []
    for item in items:
        metadata = _COMMAND_METADATA.get(
            item.id,
            CommandPaletteMetadata(
                "Custom actions" if item.id.startswith("custom_action:") else item.category
            ),
        )
        enabled = item.enabled
        reason = item.disabled_reason
        if search_workspace and item.id not in SEARCH_WORKSPACE_COMMAND_IDS:
            enabled = False
            reason = "Unavailable in Search Workspace"
        elif not enabled and reason is None:
            reason = _disabled_reason(state, item.id)
        decorated.append(
            replace(
                item,
                enabled=enabled,
                category=metadata.category,
                keywords=metadata.keywords,
                context_priority=metadata.context_priority,
                disabled_reason=reason,
            )
        )

    if query.strip():
        ranked = [
            (score, index, item)
            for index, item in enumerate(decorated)
            if (score := _command_match_score(item, query)) is not None
        ]
        ranked.sort(
            key=lambda row: (
                row[0],
                not row[2].enabled,
                row[2].context_priority,
                _category_index(row[2].category),
                row[1],
            )
        )
        return tuple(item for _score, _index, item in ranked)

    indexed = list(enumerate(decorated))
    indexed.sort(
        key=lambda row: (
            _category_index(row[1].category),
            row[1].context_priority,
            row[0],
        )
    )
    return tuple(item for _index, item in indexed)


def _category_index(category: str) -> int:
    try:
        return _CATEGORY_ORDER.index(category)
    except ValueError:
        return len(_CATEGORY_ORDER)


def _disabled_reason(state: AppState, item_id: str) -> str:
    """Explain why a command cannot run in the current state."""

    target = select_single_target_entry(state)
    has_target = bool(select_target_paths(state))
    if item_id in {"go_back", "go_forward"}:
        return "No directory history in this direction"
    if item_id == "undo_last_operation":
        return "No operation to undo"
    if item_id in {"next_tab", "previous_tab", "close_current_tab"}:
        return "Requires at least two tabs"
    if item_id == "select_all":
        return "No visible entries to select"
    if item_id in {"show_attributes"}:
        return "Select one target to inspect"
    if item_id in {"rename", "create_symlink"}:
        return "Select one target to use this command"
    if item_id in {"change_permissions", "change_owner"} and not _is_chmod_supported():
        return "Unavailable on Windows"
    if item_id in {
        "change_permissions",
        "change_owner",
        "compress_as_zip",
        "copy_path",
        "copy_targets",
        "cut_targets",
        "delete_targets",
    }:
        return "Select at least one target to use this command"
    if item_id in {"open", "edit_with_terminal_editor", "edit_with_gui_editor"}:
        if target is None:
            return "Select one file to use this command"
        return "Select one file to use this command"
    if item_id == "extract_archive":
        return "Select one supported archive file"
    if item_id == "paste_clipboard":
        return "Clipboard is empty"
    if item_id in {
        "open_current_directory_with_file_manager",
        "open_current_directory_with_terminal",
        "run_shell_command",
    }:
        return "Unavailable in Search Workspace"
    if item_id in {
        "add_bookmark",
        "remove_bookmark",
        "create_file",
        "create_dir",
        "toggle_transfer_mode",
    }:
        return "Unavailable in Search Workspace"
    if not has_target:
        return "Requires a selected or focused target"
    return "Unavailable in the current context"


def _build_custom_action_items(state: AppState) -> list[CommandPaletteItem]:
    context = _custom_action_context(state)
    items: list[CommandPaletteItem] = []
    for index, action in enumerate(state.config.actions.custom):
        enabled = custom_action_matches(action, context)
        disabled_reason = None
        if not enabled:
            if action.when == "single_file":
                disabled_reason = "Select one matching file for this custom action"
            elif action.when == "selection":
                disabled_reason = "Select at least one entry for this custom action"
            else:
                disabled_reason = "Custom action is unavailable in the current context"
        items.append(
            CommandPaletteItem(
                id=f"custom_action:{index}",
                label=action.name,
                shortcut=None,
                enabled=enabled,
                disabled_reason=disabled_reason,
            )
        )
    return items


def _custom_action_context(state: AppState) -> CustomActionContext:
    single_file_paths = select_target_file_paths(state)
    focused_file = single_file_paths[0] if len(single_file_paths) == 1 else None
    return CustomActionContext(
        cwd=state.current_path,
        focused_file=focused_file,
        selection=select_target_paths(state),
    )


def _build_transfer_command_palette_items(state: AppState) -> tuple[CommandPaletteItem, ...]:
    target_paths = _transfer_target_paths(state)
    has_target = bool(target_paths)
    has_single_target = _transfer_single_target_entry(state) is not None
    has_visible_entries = bool(_transfer_visible_entries(state))
    can_paste = state.clipboard.mode != "none" and bool(state.clipboard.paths)
    tab_count = len(state.browser_tabs) or 1
    chmod_item = (
        (
            CommandPaletteItem(
                id="change_permissions",
                label="Change permissions",
                shortcut=None,
                enabled=has_single_target,
            ),
            CommandPaletteItem(
                id="change_owner",
                label="Change owner",
                shortcut=None,
                enabled=has_target,
            ),
        )
        if _is_chmod_supported()
        else ()
    )

    return (
        CommandPaletteItem(
            id="history_search",
            label="History search",
            shortcut=None,
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
            shortcut=None,
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
            shortcut=None,
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
        *chmod_item,
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
    return query.casefold() in item.label.casefold()


def _command_match_score(item: CommandPaletteItem, query: str) -> int | None:
    """Return a small deterministic score, where lower values rank first."""

    normalized_query = " ".join(query.casefold().split())
    if not normalized_query:
        return 0
    label = item.label.casefold()
    keywords = tuple(keyword.casefold() for keyword in item.keywords)
    if normalized_query == label:
        return 0
    if label.startswith(normalized_query):
        return 1
    words = tuple(label.replace("/", " ").replace("-", " ").split())
    if any(word.startswith(normalized_query) for word in words):
        return 2
    if normalized_query in label or any(normalized_query in keyword for keyword in keywords):
        return 3
    if any(_is_subsequence(normalized_query, candidate) for candidate in (label, *keywords)):
        return 4
    return None


def _is_subsequence(query: str, candidate: str) -> bool:
    iterator = iter(candidate)
    return all(any(character == expected for character in iterator) for expected in query)


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


def _is_split_terminal_supported() -> bool:
    """Check if the embedded split terminal is available on this platform."""
    return is_split_terminal_supported()


def _is_chmod_supported() -> bool:
    """Return whether POSIX-style chmod is meaningful on the current platform."""

    return platform.system() != "Windows"
