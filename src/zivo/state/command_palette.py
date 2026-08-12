"""Command palette definitions and filtering helpers."""

import os
import platform
from dataclasses import dataclass, replace
from pathlib import Path

from zivo.archive_utils import is_supported_archive_path
from zivo.models import CustomActionContext, custom_action_matches
from zivo.platform_support import is_split_terminal_supported
from zivo.windows_paths import (
    display_path,
    is_search_workspace_path,
    is_windows_drives_root,
    is_windows_path,
    list_windows_drive_paths,
    normalize_windows_path,
)

from .entry_state_helpers import select_transfer_target_paths, select_visible_entry_states
from .models import (
    AppState,
    GoCandidateSource,
    GoCandidateState,
    GoCompletionState,
    GoSourceFilter,
    select_browser_tabs,
)
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


NOTIFICATION_ACTION_IDS = frozenset(
    {
        "notification.undo",
        "notification.open_destination",
        "notification.retry",
        "notification.details",
        "notification.shell_result",
    }
)

BACKGROUND_OPERATION_BLOCKED_COMMAND_IDS = frozenset(
    {
        "undo_last_operation",
        "replace_text",
        "rename",
        "change_permissions",
        "change_owner",
        "create_symlink",
        "compress_as_zip",
        "extract_archive",
        "edit_with_terminal_editor",
        "edit_with_gui_editor",
        "open",
        "duplicate_targets",
        "paste_clipboard",
        "delete_targets",
        "permanent_delete_targets",
        "transfer_copy_to_opposite_pane",
        "transfer_move_to_opposite_pane",
        "open_current_directory_with_file_manager",
        "open_current_directory_with_terminal",
        "run_shell_command",
        "create",
    }
)


_COMMAND_METADATA: dict[str, CommandPaletteMetadata] = {
    "notification.undo": CommandPaletteMetadata("Suggested", ("undo", "notification"), 0),
    "notification.open_destination": CommandPaletteMetadata(
        "Suggested", ("open", "destination", "notification"), 1
    ),
    "notification.retry": CommandPaletteMetadata("Suggested", ("retry", "notification"), 2),
    "notification.details": CommandPaletteMetadata(
        "Suggested", ("details", "notification"), 3
    ),
    "notification.shell_result": CommandPaletteMetadata(
        "Suggested", ("result", "shell", "command"), 3
    ),
    "go": CommandPaletteMetadata(
        "Navigate", ("go", "path", "directory", "history", "recent", "bookmark"), 5
    ),
    "file_search": CommandPaletteMetadata("Search", ("find", "files", "filename"), 20),
    "grep_search": CommandPaletteMetadata(
        "Search", ("grep", "search", "search contents", "text", "content", "contents"), 21
    ),
    "go_back": CommandPaletteMetadata("Navigate", ("back", "previous"), 32),
    "go_forward": CommandPaletteMetadata("Navigate", ("forward", "next"), 33),
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
    "toggle_narrow_pane_view": CommandPaletteMetadata(
        "View", ("preview", "contents", "details", "file list", "pane"), 43
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
    "duplicate_targets": CommandPaletteMetadata(
        "File", ("duplicate", "clone", "copy", "replicate"), 15
    ),
    "cut_targets": CommandPaletteMetadata("File", ("cut", "move"), 16),
    "paste_clipboard": CommandPaletteMetadata(
        "File", ("paste", "clipboard", "insert"), 16
    ),
    "delete_targets": CommandPaletteMetadata(
        "File", ("delete", "trash", "remove"), 17
    ),
    "permanent_delete_targets": CommandPaletteMetadata(
        "File", ("delete", "permanent", "irreversible", "remove"), 18
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
    "create": CommandPaletteMetadata(
        "File", ("new", "file", "directory", "folder", "create", "touch", "mkdir"), 18
    ),
    "transfer_copy_to_opposite_pane": CommandPaletteMetadata(
        "File", ("copy", "transfer", "other pane"), 20
    ),
    "transfer_move_to_opposite_pane": CommandPaletteMetadata(
        "File", ("move", "transfer", "other pane"), 21
    ),
}

_CATEGORY_ORDER = (
    "Suggested",
    "Navigate",
    "File",
    "Search",
    "View",
    "System",
    "Custom actions",
)


SEARCH_WORKSPACE_COMMAND_IDS = frozenset(
    {
        "notification.undo",
        "notification.open_destination",
        "notification.retry",
        "notification.details",
        "notification.shell_result",
        "go_back",
        "go_forward",
        "go",
        "go_to_home_directory",
        "undo_last_operation",
        "new_tab",
        "next_tab",
        "previous_tab",
        "close_current_tab",
        "exit",
        "select_all",
        "replace_text",
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

    if state.command_palette.source == "go":
        candidates = select_go_candidates(
            state,
            source_filter=state.command_palette.history_and_navigation.go_source_filter,
            query=state.command_palette.query,
        )
        return tuple(
            CommandPaletteItem(
                id="go_direct" if candidate.sources == ("direct",) else f"go_candidate:{index}",
                label=_go_candidate_label(candidate),
                shortcut=None,
                enabled=True,
                path=candidate.path,
            )
            for index, candidate in enumerate(candidates)
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
    if (
        state.command_palette.source == "commands"
        and not query.strip()
        and state.notification is not None
        and state.notification.action is not None
    ):
        action = state.notification.action
        items = (
            CommandPaletteItem(
                id=action.action_id,
                label=action.label,
                shortcut=None,
                enabled=True,
                category="Suggested",
                context_priority=0,
            ),
            *items,
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
    elif state.command_palette.source == "go":
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
            id="go",
            label="Go",
            shortcut="G",
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
            shortcut=None,
            enabled=tab_count > 1,
        ),
        CommandPaletteItem(
            id="previous_tab",
            label="Previous tab",
            shortcut=None,
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
            label=(
                "Replace selected results"
                if is_search_workspace_path(state.current_path)
                else "Replace text"
            ),
            shortcut=None,
            enabled=(
                bool(select_target_file_paths(state))
                if is_search_workspace_path(state.current_path)
                else True
            ),
            disabled_reason=(
                "Select a file result to replace"
                if is_search_workspace_path(state.current_path)
                and not select_target_file_paths(state)
                else None
            ),
        ),
    ]

    if state.terminal_width < 80 and not is_search_workspace_path(state.current_path):
        has_cursor = state.current_pane.cursor_path is not None
        items.append(
            CommandPaletteItem(
                id="toggle_narrow_pane_view",
                label=(
                    "Back to file list"
                    if state.narrow_pane_view == "details"
                    else "Show preview or contents"
                ),
                shortcut="tab",
                enabled=has_cursor,
                disabled_reason="Details view requires a focused item" if not has_cursor else None,
            )
        )

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
            items.append(
                CommandPaletteItem(
                    id="permanent_delete_targets",
                    label="Permanently delete",
                    shortcut="D",
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
                id="create",
                label="Create",
                shortcut=None,
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
    rename_label = f"Rename {len(target_paths)} items" if len(target_paths) >= 2 else "Rename"
    items = (
        CommandPaletteItem("show_attributes", "Show attributes", None, has_single_target),
        CommandPaletteItem(
            "rename",
            rename_label,
            "r",
            has_target and not search_workspace,
        ),
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
            "duplicate_targets",
            "Duplicate selection or cursor target",
            None,
            has_target and not search_workspace,
        ),
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
        CommandPaletteItem(
            "permanent_delete_targets",
            "Permanently delete",
            "D",
            has_target and not search_workspace,
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
        operation = state.foreground_operation
        operation_blocked = operation is not None and (
            item.id in BACKGROUND_OPERATION_BLOCKED_COMMAND_IDS
            or item.id.startswith("custom_action:")
        )
        if operation_blocked:
            enabled = False
            reason = f"{operation.kind.title()} is in progress"
        elif search_workspace and item.id not in SEARCH_WORKSPACE_COMMAND_IDS:
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
    if item_id in {"transfer_copy_to_opposite_pane", "transfer_move_to_opposite_pane"}:
        return "Select or focus an item to transfer"
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
        "duplicate_targets",
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
        "create",
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
            id="go",
            label="Go",
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
            shortcut=None,
            enabled=True,
        ),
        CommandPaletteItem(
            id="next_tab",
            label="Next tab",
            shortcut=None,
            enabled=tab_count > 1,
        ),
        CommandPaletteItem(
            id="previous_tab",
            label="Previous tab",
            shortcut=None,
            enabled=tab_count > 1,
        ),
        CommandPaletteItem(
            id="close_current_tab",
            label="Close current tab",
            shortcut=None,
            enabled=tab_count > 1,
        ),
        CommandPaletteItem(
            id="transfer_copy_to_opposite_pane",
            label="Copy to opposite pane",
            shortcut="c",
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
            label=(
                f"Rename {len(target_paths)} items"
                if len(target_paths) >= 2
                else "Rename"
            ),
            shortcut="r",
            enabled=has_target,
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
            id="permanent_delete_targets",
            label="Permanently delete",
            shortcut="D",
            enabled=has_target,
        ),
        CommandPaletteItem(
            id="create",
            label="Create file",
            shortcut="n",
            enabled=_active_transfer_pane_state(state) is not None,
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


_GO_EMPTY_QUERY_LIMIT = 12
_GO_SOURCE_LABELS: dict[GoCandidateSource, str] = {
    "home": "Home",
    "bookmark": "Bookmark",
    "recent": "Recent",
    "open_tab": "Open tab",
    "direct": "Path",
}
_GO_FILTER_PREFIXES: tuple[tuple[str, GoSourceFilter], ...] = (
    ("@bookmarks", "bookmarks"),
    ("@bookmark", "bookmarks"),
    ("@history", "recent"),
    ("@recent", "recent"),
    ("@tabs", "open_tabs"),
    ("@tab", "open_tabs"),
    ("@home", "home"),
    ("@all", "all"),
)


def parse_go_query(
    query: str,
    default_filter: GoSourceFilter = "all",
) -> tuple[GoSourceFilter, str]:
    """Parse an optional ``@source`` prefix from a Go query."""

    stripped = query.strip()
    lowered = stripped.casefold()
    for prefix, source_filter in _GO_FILTER_PREFIXES:
        if lowered == prefix:
            return source_filter, ""
        if lowered.startswith(prefix + " "):
            return source_filter, stripped[len(prefix) :].strip()
    return default_filter, query


def _go_path_key(path: str) -> str:
    """Return the platform-aware key used to merge Go candidates."""

    if is_windows_path(path):
        return normalize_windows_path(path).casefold()
    if path.startswith(("search://", "::zivo::")):
        return os.path.normpath(path)
    return os.path.realpath(os.path.normpath(path))


def _go_base_path(state: AppState) -> str:
    if state.layout_mode == "transfer":
        transfer = _active_transfer_pane_state(state)
        if transfer is not None:
            return transfer.current_path
    return state.current_path


def _go_history_paths(state: AppState) -> tuple[str, ...]:
    if state.layout_mode == "transfer":
        transfer = _active_transfer_pane_state(state)
        if transfer is not None:
            return tuple(reversed(transfer.history.visited_all))
    return tuple(reversed(state.history.visited_all))


def _go_direct_path(query: str, base_path: str) -> str | None:
    """Resolve an existing directory query for the direct Go candidate."""

    raw_query = query.strip()
    if not raw_query:
        return None
    if is_windows_path(raw_query) or is_windows_path(base_path):
        expanded = os.path.expanduser(raw_query).replace("/", "\\")
        if not is_windows_path(expanded):
            expanded = os.path.join(normalize_windows_path(base_path), expanded)
        try:
            return normalize_windows_path(expanded) if os.path.isdir(expanded) else None
        except (OSError, ValueError, RuntimeError):
            return None
    try:
        candidate = Path(os.path.expanduser(raw_query))
        if not candidate.is_absolute():
            candidate = Path(base_path) / candidate
        candidate = candidate.resolve()
        return str(candidate) if candidate.is_dir() else None
    except (OSError, RuntimeError, ValueError):
        return None


def _go_query_has_trailing_separator(query: str, base_path: str) -> bool:
    """Return whether a Go query asks for the next directory level."""

    raw_query = query.strip()
    if not raw_query:
        return False
    if is_windows_path(raw_query) or is_windows_path(base_path) or is_windows_drives_root(
        base_path
    ):
        return raw_query.endswith(("/", "\\"))
    return raw_query.endswith(os.sep) or (
        os.altsep is not None and raw_query.endswith(os.altsep)
    )


def _go_candidate_label(candidate: GoCandidateState) -> str:
    label = _display_path(candidate.path)
    if not candidate.sources:
        return label
    badges = " ".join(f"[{_GO_SOURCE_LABELS[source]}]" for source in candidate.sources)
    return f"{label} {badges}"


def _go_match_score(path: str, query: str) -> int | None:
    normalized_query = " ".join(query.casefold().split())
    if not normalized_query:
        return 0
    display = _display_path(path).casefold()
    normalized_path = path.casefold()
    basename = path.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1].casefold()
    if normalized_query in {display, normalized_path}:
        return 0
    if basename.startswith(normalized_query):
        return 1
    words = tuple(part for part in normalized_path.replace("\\", "/").split("/") if part)
    if any(word.startswith(normalized_query) for word in words):
        return 2
    if normalized_query in display or normalized_query in normalized_path:
        return 3
    return None


def select_go_candidates(
    state: AppState,
    *,
    source_filter: GoSourceFilter = "all",
    query: str = "",
) -> tuple[GoCandidateState, ...]:
    """Collect, merge, and rank destinations for the unified Go palette."""

    effective_filter, search_query = parse_go_query(query, source_filter)
    merged: dict[str, GoCandidateState] = {}

    def add(path: str, source: GoCandidateSource, tab_index: int | None = None) -> None:
        if not path:
            return
        key = _go_path_key(path)
        existing = merged.get(key)
        if existing is None:
            merged[key] = GoCandidateState(path=path, sources=(source,), tab_index=tab_index)
            return
        sources = existing.sources if source in existing.sources else (*existing.sources, source)
        merged[key] = replace(
            existing,
            sources=sources,
            tab_index=existing.tab_index if existing.tab_index is not None else tab_index,
        )

    add(os.path.expanduser("~"), "home")
    for path in state.config.bookmarks.paths:
        add(path, "bookmark")
    for path in _go_history_paths(state):
        add(path, "recent")
    for index, tab in enumerate(select_browser_tabs(state)):
        add(tab.current_path, "open_tab", index)

    base_path = _go_base_path(state)
    if is_windows_drives_root(base_path) or is_windows_path(base_path):
        for path in list_windows_drive_paths():
            add(path, "direct")

    completion = (
        state.command_palette.go_completion
        if state.command_palette is not None
        else GoCompletionState()
    )
    if (
        effective_filter == "all"
        and search_query.strip()
        and completion.query.strip() == search_query.strip()
        and completion.base_path == base_path
    ):
        for path in completion.paths:
            add(path, "direct")

    candidates = tuple(
        candidate
        for candidate in merged.values()
        if effective_filter == "all"
        or (effective_filter == "bookmarks" and "bookmark" in candidate.sources)
        or (effective_filter == "recent" and "recent" in candidate.sources)
        or (effective_filter == "open_tabs" and "open_tab" in candidate.sources)
        or (effective_filter == "home" and "home" in candidate.sources)
    )
    direct_path = (
        _go_direct_path(search_query, _go_base_path(state))
        if effective_filter == "all"
        else None
    )
    if direct_path is not None:
        direct_key = _go_path_key(direct_path)
        existing_direct = merged.get(direct_key)
        direct_candidate = GoCandidateState(path=direct_path, sources=("direct",))
        if existing_direct is not None:
            direct_candidate = replace(
                existing_direct,
                path=direct_path,
                sources=(
                    "direct",
                    *(source for source in existing_direct.sources if source != "direct"),
                ),
            )
            candidates = tuple(
                candidate
                for candidate in candidates
                if _go_path_key(candidate.path) != direct_key
            )
        candidates = (
            direct_candidate,
            *candidates,
        )

    if search_query.strip():
        ranked: list[tuple[int, int, GoCandidateState]] = []
        for index, candidate in enumerate(candidates):
            score = (
                0
                if "direct" in candidate.sources
                else _go_match_score(candidate.path, search_query)
            )
            if score is not None:
                ranked.append((score, index, candidate))
        candidates = tuple(
            candidate
            for _, _, candidate in sorted(ranked, key=lambda item: (item[0], item[1]))
        )
    elif effective_filter == "all":
        candidates = candidates[:_GO_EMPTY_QUERY_LIMIT]
    return candidates


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
    return select_transfer_target_paths(state)


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
