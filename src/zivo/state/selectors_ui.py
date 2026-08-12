"""Status, palette, and dialog selectors."""

import importlib.metadata
from pathlib import Path

from zivo.models import (
    AttributeDialogState,
    BulkRenameDialogState,
    BulkRenameRowViewState,
    CommandPaletteItemViewState,
    CommandPaletteViewState,
    ConfigDialogState,
    ConflictDialogState,
    HelpBarState,
    InputBarState,
    InputDialogState,
    NotificationDetailsDialogState,
    ShellCommandDialogState,
    StatusBarActionState,
    StatusBarState,
)
from zivo.platform_support import is_split_terminal_supported
from zivo.windows_paths import is_search_workspace_path

from .command_palette import _go_direct_path, parse_go_query
from .models import AppState
from .reducer_config import (
    CONFIG_EDITOR_CATEGORIES,
    CONFIG_GUI_EDITOR_PRESETS,
    config_editor_field_description,
    config_editor_labels,
    format_config_field_value,
)
from .reducer_pending_input import pending_input_parent_and_target
from .selectors_shared import (
    _build_command_palette_items_view,
    _build_file_search_input_fields,
    _build_find_replace_input_fields,
    _build_grep_replace_input_fields,
    _build_grep_replace_selected_input_fields,
    _build_grep_search_input_fields,
    _build_replace_input_fields,
    _format_config_line,
    _format_custom_editor_hint,
    _format_modified_label_from_timestamp,
    _format_permissions_label,
    _format_size_label,
    _select_file_search_window,
    _select_find_replace_preview_window,
    _select_grep_search_window,
    _select_replace_preview_window,
    compute_search_visible_window,
    get_command_palette_items,
    normalize_command_palette_cursor,
)


def _format_attribute_permissions_label(state: AppState) -> str:
    entry = state.attribute_inspection
    if entry is None:
        return "-"
    permission_str = _format_permissions_label(entry.permissions_mode)
    if entry.permissions_mode is None:
        return permission_str
    if entry.owner and entry.group:
        return f"{permission_str} {entry.owner} {entry.group}"
    if entry.owner:
        return f"{permission_str} {entry.owner}"
    return permission_str


def select_status_bar_state(state: AppState) -> StatusBarState:
    """Return a status bar model derived from app state."""

    operation = state.foreground_operation
    if operation is not None:
        message = operation.message
        if operation.cancel_requested:
            pass
        elif operation.total is None:
            if not message.endswith("…"):
                message = f"{message} …"
        elif message == "Processing..." or "/" in message:
            message = f"{operation.kind.title()} {operation.completed}/{operation.total}"
        else:
            message = f"{message} {operation.completed}/{operation.total}"
        if operation.current_path is not None:
            message = f"{message}: {_format_operation_path(operation.current_path)}"
        return StatusBarState(
            message=message,
            message_level="info",
            action=(
                StatusBarActionState(action_id="operation.cancel", label="Cancel")
                if operation.cancelable and not operation.cancel_requested
                else None
            ),
            notification_revision=state.notification_revision,
            auto_dismiss=False,
        )

    notification = state.notification
    return StatusBarState(
        message=notification.message if notification else None,
        message_level=notification.level if notification else None,
        action=(
            StatusBarActionState(
                action_id=notification.action.action_id,
                label=notification.action.label,
            )
            if notification is not None and notification.action is not None
            else None
        ),
        notification_revision=state.notification_revision,
        auto_dismiss=notification.auto_dismiss if notification else False,
    )


def _format_operation_path(path: str) -> str:
    """Keep operation paths useful without exposing an overly wide status line."""

    try:
        resolved = Path(path).expanduser()
        home = Path.home()
        if resolved == home:
            display = "~"
        elif resolved.is_relative_to(home):
            display = "~/" + str(resolved.relative_to(home))
        else:
            display = str(resolved)
    except (OSError, RuntimeError):
        display = path
    if len(display) <= 56:
        return display
    return f"{display[:24]}…{display[-28:]}"


def select_notification_details_dialog_state(
    state: AppState,
) -> NotificationDetailsDialogState | None:
    """Return the failure details overlay for the active notification."""

    details = state.notification_details
    if details is None:
        return None
    lines = [f"Failures: {details.failure_count}"]
    if details.skipped_count:
        lines.append(f"Skipped: {details.skipped_count}")
    if details.unprocessed_count:
        lines.append(f"Not processed: {details.unprocessed_count}")
    for failure in details.failures:
        lines.append(f"Path: {failure.path}")
        lines.append(f"Reason: {failure.reason}")
    for path in details.skipped_paths:
        lines.append(f"Skipped path: {path}")
    for path in details.unprocessed_paths:
        lines.append(f"Not processed path: {path}")
    recovery_action = details.recovery_action
    shortcut = (
        {
            "notification.undo": "z",
            "notification.retry": "r",
        }.get(recovery_action.action_id)
        if recovery_action is not None
        else None
    )
    options = ("enter close", "esc close")
    if recovery_action is not None and shortcut is not None:
        options = (f"{shortcut} {recovery_action.label}", *options)
    return NotificationDetailsDialogState(
        title="Notification details",
        lines=tuple(lines),
        options=options,
        recovery_action_id=recovery_action.action_id if recovery_action else None,
        recovery_action_label=recovery_action.label if recovery_action else None,
        recovery_action_shortcut=shortcut,
        recovery_action_revision=state.notification_revision,
    )


def _format_help_line(shortcuts: tuple[tuple[str, str], ...]) -> str:
    return " | ".join(f"{key} {label}" for key, label in shortcuts)


def select_help_bar_state(state: AppState) -> HelpBarState:
    """Return the help content for the active mode."""

    if state.foreground_operation is not None and state.ui_mode == "BROWSING":
        if state.layout_mode == "transfer":
            from .input_transfer import TRANSFER_HELP_LINES

            lines = tuple(_format_help_line(line) for line in TRANSFER_HELP_LINES)
        elif is_search_workspace_path(state.current_path):
            from .input_browsing import SEARCH_WORKSPACE_HELP_LINES

            lines = tuple(_format_help_line(line) for line in SEARCH_WORKSPACE_HELP_LINES)
        else:
            from .input_browsing import BROWSING_HELP_LINES

            lines = tuple(_format_help_line(line) for line in BROWSING_HELP_LINES)
        if (
            state.foreground_operation.cancelable
            and not state.foreground_operation.cancel_requested
        ):
            cancel_hint = "Esc cancel"
        else:
            cancel_hint = "finishing current item"
        return HelpBarState((f"{cancel_hint} | {lines[0]}", *lines[1:]))

    if state.ui_mode == "CONFIRM":
        if state.delete_confirmation is not None:
            confirmation = state.delete_confirmation
            if confirmation.additional_confirmation_armed:
                return HelpBarState(("D permanently delete | esc cancel",))
            if confirmation.requires_additional_confirmation:
                return HelpBarState(("enter review permanent delete | esc cancel",))
            if confirmation.mode == "permanent":
                return HelpBarState(("enter confirm permanent delete | esc cancel",))
            return HelpBarState(("enter confirm delete | esc cancel",))
        if state.exit_confirmation is not None:
            if state.foreground_operation is not None:
                return HelpBarState(("enter cancel and exit | esc cancel",))
            return HelpBarState(("enter confirm exit | esc cancel",))
        if state.archive_extract_confirmation is not None:
            return HelpBarState(("enter continue extraction | esc return to input",))
        if state.zip_compress_confirmation is not None:
            return HelpBarState(("enter overwrite zip | esc return to input",))
        if state.replace_confirmation is not None:
            return HelpBarState(("enter confirm replace | esc cancel",))
        if state.custom_action_confirmation is not None:
            return HelpBarState(("enter run custom action | esc cancel",))
        if state.name_conflict is not None:
            return HelpBarState(("enter return to input | esc return to input",))
        return HelpBarState(("resolve conflict in dialog",))
    if state.ui_mode == "DETAIL":
        return HelpBarState(("enter close | esc close",))
    if state.ui_mode == "CONFIG":
        return HelpBarState(
            (
                "↑↓ or Ctrl+j/k choose | ←→ or Enter change | s save | e advanced config",
                "esc close",
            )
        )
    if state.ui_mode == "SHELL":
        # 結果表示状態の場合
        if state.shell_command is not None and state.shell_command.result is not None:
            return HelpBarState(("r rerun | t terminal | esc close",))
        # コマンド入力状態の場合
        return HelpBarState(("type command | enter run | esc cancel",))
    if state.ui_mode == "FILTER":
        return HelpBarState(("type filter | enter/down apply | esc clear",))
    if state.ui_mode == "CHMOD":
        return HelpBarState(("type octal mode | enter apply | esc cancel",))
    if state.ui_mode == "CHOWN":
        return HelpBarState(("type owner[:group] | enter apply | esc cancel",))
    if state.ui_mode == "RENAME":
        return HelpBarState(("type name | enter apply | esc cancel",))
    if state.ui_mode == "CREATE":
        return HelpBarState(("type name | enter apply | esc cancel",))
    if state.ui_mode == "EXTRACT":
        return HelpBarState(("type destination path | enter extract | esc cancel",))
    if state.ui_mode == "ZIP":
        return HelpBarState(("type zip path | enter compress | esc cancel",))
    if state.ui_mode == "SYMLINK":
        return HelpBarState(("type destination path | tab complete | enter create | esc cancel",))
    if state.ui_mode == "PALETTE":
        if state.command_palette is not None and state.command_palette.source == "file_search":
            return HelpBarState(
                (
                    "type filename | ↑↓ or Ctrl+j/k select | enter jump | "
                    "Ctrl+w workspace | Ctrl+e edit | Ctrl+o GUI | esc cancel",
                )
            )
        if state.command_palette is not None and state.command_palette.source == "grep_search":
            return HelpBarState(
                (
                    "type text / tab fields / ↑↓ or Ctrl+j/k select | "
                    "enter jump | Ctrl+e edit | Ctrl+o GUI | "
                    "Ctrl+x export | esc cancel",
                )
            )
        return HelpBarState(("type command | ↑↓ or Ctrl+j/k select | enter run | esc cancel",))
    if state.ui_mode == "BUSY":
        operation = state.foreground_operation
        if operation is not None:
            if operation.cancel_requested:
                return HelpBarState(("finishing current item",))
            if operation.cancelable:
                return HelpBarState(("Esc cancel",))
        return HelpBarState(("processing...",))
    if state.layout_mode == "transfer":
        from .input_transfer import TRANSFER_HELP_LINES

        return HelpBarState(tuple(_format_help_line(line) for line in TRANSFER_HELP_LINES))
    if is_search_workspace_path(state.current_path):
        from .input_browsing import SEARCH_WORKSPACE_HELP_LINES

        return HelpBarState(
            tuple(_format_help_line(line) for line in SEARCH_WORKSPACE_HELP_LINES)
        )
    split_terminal_hint = " | t term" if is_split_terminal_supported() else ""
    from .input_browsing import (
        BROWSING_HELP_LINES,
        BROWSING_HELP_LINES_WITH_DETAILS,
        BROWSING_HELP_LINES_WITH_FILE_LIST,
    )

    browsing_lines = BROWSING_HELP_LINES
    if state.terminal_width < 80 and state.current_pane.cursor_path is not None:
        browsing_lines = (
            BROWSING_HELP_LINES_WITH_FILE_LIST
            if state.narrow_pane_view == "details"
            else BROWSING_HELP_LINES_WITH_DETAILS
        )

    return HelpBarState(
        (
            _format_help_line(browsing_lines[0]),
            _format_help_line(browsing_lines[1]),
            f"{_format_help_line(browsing_lines[2][:-1])}{split_terminal_hint} | "
            f"{_format_help_line(browsing_lines[2][-1:])}",
        )
    )


def select_input_bar_state(state: AppState) -> InputBarState | None:
    """Return contextual input state for the filter mode."""

    if state.pending_key_sequence is not None:
        keys = " ".join(state.pending_key_sequence.keys)
        next_keys = state.pending_key_sequence.possible_next_keys
        hint = "await next key | esc cancel"
        if next_keys:
            hint = f"await {'/'.join(next_keys)} | esc cancel"
        return InputBarState(
            mode_label="KEYS",
            prompt="Prefix: ",
            value=keys,
            cursor_pos=len(keys),
            hint=hint,
        )

    if state.ui_mode == "FILTER" or (state.filter.active and state.filter.query):
        hint = "esc clear"
        if state.ui_mode == "FILTER":
            hint = "enter/down apply | esc clear"
        return InputBarState(
            mode_label="FILTER",
            prompt="Filter: ",
            value=state.filter.query,
            cursor_pos=len(state.filter.query),
            hint=hint,
        )

    return None


def select_input_dialog_state(state: AppState) -> InputDialogState | None:
    """Return dialog content when the app is in an input mode."""

    if state.ui_mode not in {"CHMOD", "CHOWN", "RENAME", "CREATE", "EXTRACT", "ZIP", "SYMLINK"}:
        return None
    if state.pending_input is None:
        return None
    if state.ui_mode == "CHMOD":
        title = "Change Permissions"
    elif state.ui_mode == "CHOWN":
        title = "Change Owner"
    elif state.ui_mode == "RENAME":
        title = "Rename"
    elif state.ui_mode == "EXTRACT":
        title = "Extract"
    elif state.ui_mode == "ZIP":
        title = "Compress"
    elif state.ui_mode == "SYMLINK":
        title = "Create Symlink"
    else:
        title = "Create"
    details: tuple[str, ...] = ()
    if state.ui_mode in {"CHMOD", "CHOWN"}:
        target_paths = (
            state.pending_input.chmod_target_paths
            if state.ui_mode == "CHMOD"
            else state.pending_input.chown_target_paths
        ) or ()
        recursive = (
            state.pending_input.chmod_recursive
            if state.ui_mode == "CHMOD"
            else state.pending_input.chown_recursive
        )
        entries = (
            state.transfer_left.pane.entries
            if state.layout_mode == "transfer"
            and state.active_transfer_pane == "left"
            and state.transfer_left is not None
            else state.transfer_right.pane.entries
            if state.layout_mode == "transfer" and state.transfer_right is not None
            else state.current_pane.entries
        )
        entry_by_path = {entry.path: entry for entry in entries}
        selected_entries = tuple(
            entry_by_path[path] for path in target_paths if path in entry_by_path
        )
        directories = sum(entry.kind == "dir" for entry in selected_entries)
        files = sum(entry.kind == "file" for entry in selected_entries)
        symlinks = sum(entry.symlink for entry in selected_entries)
        kinds = ", ".join(
            part
            for part in (
                f"{files} file{'s' if files != 1 else ''}" if files else "",
                f"{directories} director{'ies' if directories != 1 else 'y'}"
                if directories
                else "",
                f"{symlinks} symlink{'s' if symlinks != 1 else ''}" if symlinks else "",
            )
            if part
        ) or "unknown types"
        details = (
            f"Targets: {len(target_paths)} ({kinds})",
            f"Recursive: {'Yes' if recursive else 'No'}",
            "Symlinks are skipped and never followed.",
        )
    elif state.ui_mode == "CREATE":
        parent_path, target_path = pending_input_parent_and_target(state)
        kind = "File" if state.pending_input.create_kind == "file" else "Directory"
        details = (
            f"Type: {kind} (Tab to switch)",
            f"Parent directory: {parent_path or 'Unavailable'}",
            f"Target: {target_path or 'Enter a relative path'}",
        )
    return InputDialogState(
        title=title,
        prompt=state.pending_input.prompt,
        value=state.pending_input.value,
        cursor_pos=state.pending_input.cursor_pos,
        hint=(
            "tab toggle recursive | enter apply | esc cancel"
            if state.ui_mode in {"CHMOD", "CHOWN"}
            else
            "tab complete | enter apply | esc cancel"
            if state.ui_mode == "SYMLINK"
            else "tab switch type | enter apply | esc cancel"
            if state.ui_mode == "CREATE"
            else "enter apply | esc cancel"
        ),
        details=details,
    )


def select_bulk_rename_dialog_state(state: AppState) -> BulkRenameDialogState | None:
    """Project reducer bulk rename state into the overlay view model."""

    editor = state.bulk_rename
    if editor is None:
        return None
    unchanged = sum(item.status == "unchanged" for item in editor.items)
    errors = sum(
        item.status in {"error", "failed", "recovery_failed"}
        for item in editor.items
    )
    changed = sum(
        item.status in {"ready", "renamed", "restored"}
        for item in editor.items
    )
    rows = tuple(
        BulkRenameRowViewState(
            old_name=item.old_name,
            new_name=item.new_name,
            status=item.status,
            message=item.message,
        )
        for item in editor.items
    )
    summary = f"{changed} changes · {unchanged} unchanged · {errors} errors"
    progress = None
    if editor.progress_total:
        progress = (
            f"Renaming {editor.progress_completed}/{editor.progress_total}"
            + (f": {editor.progress_path}" if editor.progress_path else "")
        )
    return BulkRenameDialogState(
        title=(
            f"Rename {len(editor.items)} selected items"
            if editor.result_message is None
            else "Bulk rename result"
        ),
        rows=rows,
        base_name=editor.base_name,
        active_field=editor.active_field,
        summary=summary,
        error_message=(
            "; ".join(
                item.message
                for item in editor.items
                if item.status == "error" and item.message
            )
            or None
        ),
        result_message=editor.result_message,
        apply_enabled=(
            state.ui_mode == "BULK_RENAME"
            and editor.result_message is None
            and changed > 0
            and errors == 0
        ),
        progress=progress,
    )


def select_command_palette_state(state: AppState) -> CommandPaletteViewState | None:
    """Return the visible command palette entries for the active mode."""

    if state.ui_mode != "PALETTE" or state.command_palette is None:
        return None

    cursor_index = normalize_command_palette_cursor(state, state.command_palette.cursor_index)
    if state.command_palette.source == "file_search":
        visible_results, title = _select_file_search_window(
            state,
            state.command_palette.file_search.results,
            cursor_index,
        )
        return CommandPaletteViewState(
            title=title,
            query=state.command_palette.query,
            items=tuple(
                CommandPaletteItemViewState(
                    label=(
                        f"{result.display_path}/"
                        if result.entry_type == "directory"
                        else result.display_path
                    ),
                    shortcut=None,
                    enabled=True,
                    selected=index == cursor_index,
                )
                for index, result in visible_results
            ),
            empty_message=_file_search_empty_message(state),
            has_more_items=len(state.command_palette.file_search.results) > len(visible_results),
            input_fields=_build_file_search_input_fields(state.command_palette),
            footer_message=_search_truncation_message(state, "file_search"),
        )
    if state.command_palette.source == "grep_search":
        visible_results, title = _select_grep_search_window(
            state,
            state.command_palette.grep_search.results,
            cursor_index,
        )
        return CommandPaletteViewState(
            title=title,
            query=state.command_palette.grep_search.keyword,
            items=tuple(
                CommandPaletteItemViewState(
                    label=result.display_label,
                    shortcut=None,
                    enabled=True,
                    selected=index == cursor_index,
                )
                for index, result in visible_results
            ),
            empty_message=_grep_search_empty_message(state),
            input_fields=_build_grep_search_input_fields(state.command_palette),
            has_more_items=len(state.command_palette.grep_search.results) > len(visible_results),
            footer_message=_search_truncation_message(state, "grep_search"),
        )
    if state.command_palette.source == "replace_text":
        visible_results, title = _select_replace_preview_window(
            state,
            state.command_palette.replace_preview.preview_results,
            cursor_index,
        )
        return CommandPaletteViewState(
            title=title,
            query=state.command_palette.replace_preview.find_text,
            items=tuple(
                CommandPaletteItemViewState(
                    label=result.display_label,
                    shortcut=None,
                    enabled=True,
                    selected=index == cursor_index,
                )
                for index, result in visible_results
            ),
            empty_message=_replace_text_empty_message(state),
            input_fields=_build_replace_input_fields(state.command_palette),
            has_more_items=(
                len(state.command_palette.replace_preview.preview_results) > len(visible_results)
            ),
            footer_message=_replace_result_context_message(state),
        )
    if state.command_palette.source == "replace_in_found_files":
        visible_results, title = _select_find_replace_preview_window(
            state,
            state.command_palette.rff.preview_results,
            cursor_index,
        )
        return CommandPaletteViewState(
            title=title,
            query=state.command_palette.rff.filename_query,
            items=tuple(
                CommandPaletteItemViewState(
                    label=result.display_label,
                    shortcut=None,
                    enabled=True,
                    selected=index == cursor_index,
                )
                for index, result in visible_results
            ),
            empty_message=_find_replace_empty_message(state),
            input_fields=_build_find_replace_input_fields(state.command_palette),
            has_more_items=(
                len(state.command_palette.rff.preview_results) > len(visible_results)
            ),
        )
    if state.command_palette.source == "replace_in_grep_files":
        visible_results, title = _select_find_replace_preview_window(
            state,
            state.command_palette.grf.preview_results,
            cursor_index,
        )
        return CommandPaletteViewState(
            title=title,
            query=state.command_palette.grf.keyword,
            items=tuple(
                CommandPaletteItemViewState(
                    label=result.display_label,
                    shortcut=None,
                    enabled=True,
                    selected=index == cursor_index,
                )
                for index, result in visible_results
            ),
            empty_message=_grep_replace_empty_message(state),
            input_fields=_build_grep_replace_input_fields(state.command_palette),
            has_more_items=(
                len(state.command_palette.grf.preview_results) > len(visible_results)
            ),
        )
    if state.command_palette.source == "grep_replace_selected":
        visible_results, title = _select_find_replace_preview_window(
            state,
            state.command_palette.grs.preview_results,
            cursor_index,
        )
        return CommandPaletteViewState(
            title=title,
            query=state.command_palette.grs.keyword,
            items=tuple(
                CommandPaletteItemViewState(
                    label=result.display_label,
                    shortcut=None,
                    enabled=True,
                    selected=index == cursor_index,
                )
                for index, result in visible_results
            ),
            empty_message=_grep_replace_selected_empty_message(state),
            input_fields=_build_grep_replace_selected_input_fields(state.command_palette),
            has_more_items=(
                len(state.command_palette.grs.preview_results) > len(visible_results)
            ),
        )
    if state.command_palette.source == "go":
        source_filter = state.command_palette.history_and_navigation.go_source_filter
        source_filter, _ = parse_go_query(state.command_palette.query, source_filter)
        filter_title = {
            "bookmarks": "Bookmarks",
            "recent": "Recent",
            "open_tabs": "Open tabs",
            "home": "Home",
        }.get(source_filter)
        title = f"Go — {filter_title}" if filter_title else "Go"
        footer_message = {
            "all": "Filters: @bookmark @history @tab @home | arrows select, Enter go",
            "bookmarks": "Bookmarks filter active | type to search, Enter go",
            "recent": "Recent filter active | type to search, Enter go",
            "open_tabs": "Open tabs filter active | type to search, Enter go",
            "home": "Home filter active | type to search, Enter go",
        }[source_filter]
        completion = state.command_palette.go_completion
        if completion.loading:
            footer_message = f"{footer_message} | Searching directories…"
        elif completion.error_message and _go_direct_path(
            completion.query, completion.base_path
        ) is not None:
            footer_message = f"{footer_message} | {completion.error_message}"
        elif completion.results_truncated:
            footer_message = (
                f"{footer_message} | More matches available — type more characters"
            )
        empty_message = (
            completion.error_message
            or ("Searching directories…" if completion.loading else None)
            or (
                "No matching destinations"
                if completion.query.strip()
                else "Type a path or destination"
            )
        )
        return _build_command_palette_items_view(
            state,
            cursor_index,
            title=title,
            empty_message=(
                "No bookmarks"
                if source_filter == "bookmarks" and not completion.query.strip()
                else empty_message
            ),
            footer_message=footer_message,
        )

    items = get_command_palette_items(state)
    # Keep the complete command list in the view model so the widget can scroll
    # to commands below the fold. Search-result palettes retain their bounded
    # windows because those sources can contain thousands of filesystem rows.
    visible_window = compute_search_visible_window(state.terminal_height)
    visible_items = tuple(enumerate(items))
    title = "Command Palette"
    selected_item = items[cursor_index] if items else None
    rendered_line_count = len(items)
    if not state.command_palette.query.strip():
        section_count = len({item.category for item in items})
        rendered_line_count += section_count + max(0, section_count - 1)
    return CommandPaletteViewState(
        title=title,
        query=state.command_palette.query,
        items=tuple(
            CommandPaletteItemViewState(
                label=item.label,
                shortcut=item.shortcut,
                enabled=item.enabled,
                selected=index == cursor_index,
                command_id=item.id,
                category=item.category,
                disabled_reason=item.disabled_reason,
            )
            for index, item in visible_items
        ),
        empty_message="No matching commands",
        has_more_items=rendered_line_count > visible_window,
        footer_message=(
            selected_item.disabled_reason
            if selected_item is not None and not selected_item.enabled
            else None
        ),
    )


def select_conflict_dialog_state(state: AppState) -> ConflictDialogState | None:
    """Return dialog content when the app is waiting on conflict input."""

    if state.delete_confirmation is not None:
        confirmation = state.delete_confirmation
        target_count = len(confirmation.paths)
        noun = "item" if target_count == 1 else "items"
        if confirmation.mode == "permanent":
            names = tuple(Path(path).name or path for path in confirmation.paths[:3])
            names_label = ", ".join(names)
            remaining_count = max(0, target_count - len(names))
            if remaining_count:
                names_label = f"{names_label}, and {remaining_count} more"
            size_label = _format_size_label(confirmation.total_size_bytes)
            size_note = (
                f"at least {size_label}; size unavailable for "
                f"{len(confirmation.failed_paths)} path(s)"
                if confirmation.failed_paths
                else size_label
            )
            message = (
                f"Permanently delete {target_count} {noun} ({size_note})? "
                f"Targets: {names_label}. This cannot be undone."
            )
            if confirmation.additional_confirmation_armed:
                title = "Final Permanent Delete Confirmation"
                message = f"{message} Press D to permanently delete now."
                options = ("D permanently delete", "esc cancel")
            elif confirmation.requires_additional_confirmation:
                title = "Permanent Delete Confirmation"
                message = f"{message} Press Enter to continue to the final confirmation."
                options = ("enter review", "esc cancel")
            else:
                title = "Permanent Delete Confirmation"
                options = ("enter confirm", "esc cancel")
        else:
            first_name = Path(confirmation.paths[0]).name
            message = f"Move {target_count} {noun} to trash?"
            if target_count > 1:
                message = f"Move {target_count} items to trash? The first target is {first_name}."
            title = "Delete Confirmation"
            options = ("enter confirm", "esc cancel")
        return ConflictDialogState(
            title=title,
            message=message,
            options=options,
        )

    if state.archive_extract_confirmation is not None:
        confirmation = state.archive_extract_confirmation
        destination_name = Path(confirmation.first_conflict_path).name
        message = (
            f"{confirmation.conflict_count} archive path(s) already exist in the destination. "
            f"The first conflict is {destination_name}. Continue extraction?"
        )
        return ConflictDialogState(
            title="Extract Archive Confirmation",
            message=message,
            options=("enter continue", "esc return to input"),
        )

    if state.exit_confirmation is not None:
        if state.foreground_operation is not None:
            operation_name = state.foreground_operation.kind.title()
            message = (
                f"{operation_name} is in progress. "
                "Cancel and exit when the current item finishes?"
            )
            options = ("enter cancel and exit", "esc cancel")
        else:
            message = "Exit the application?"
            options = ("enter confirm", "esc cancel")
        return ConflictDialogState(
            title="Exit Confirmation",
            message=message,
            options=options,
        )

    if state.zip_compress_confirmation is not None:
        confirmation = state.zip_compress_confirmation
        destination_name = Path(confirmation.request.destination_path).name
        return ConflictDialogState(
            title="Zip Compression Confirmation",
            message=(
                f"{destination_name} already exists. "
                f"Overwrite it and continue compressing {confirmation.total_entries} item(s)?"
            ),
            options=("enter overwrite", "esc return to input"),
        )

    if state.symlink_overwrite_confirmation is not None:
        confirmation = state.symlink_overwrite_confirmation
        destination_name = Path(confirmation.request.destination_path).name
        return ConflictDialogState(
            title="Symlink Overwrite Confirmation",
            message=f"{destination_name} already exists. Overwrite it and create the symlink?",
            options=("enter overwrite", "esc return to input"),
        )

    if state.replace_confirmation is not None:
        confirmation = state.replace_confirmation
        file_count = len(confirmation.target_paths)
        match_count = confirmation.total_match_count
        message = (
            f"Replace '{confirmation.find_text}' with '{confirmation.replacement_text}' "
            f"in {file_count} file(s) ({match_count} match(es))?"
        )
        if confirmation.result_origin is not None:
            origin_labels = {"find": "Find", "grep": "Grep", "workspace": "Search Workspace"}
            origin = origin_labels[confirmation.result_origin]
            query = f' "{confirmation.result_query}"' if confirmation.result_query else ""
            message = f"{origin}{query}: {message}"
        title = "Replace Text Confirmation"
        return ConflictDialogState(
            title=title,
            message=message,
            options=("enter confirm", "esc cancel"),
        )

    if state.custom_action_confirmation is not None:
        request = state.custom_action_confirmation.request
        command = " ".join(request.command)
        mode_display = {
            "background": "background mode",
            "terminal": "the current terminal",
            "terminal_window": "a new terminal window",
        }.get(request.mode, f"{request.mode} mode")
        message = (
            f"Run {request.name} in {mode_display} from {request.cwd}? "
            f"Command: {command}"
        )
        return ConflictDialogState(
            title="Custom Action Confirmation",
            message=message,
            options=("enter run", "esc cancel"),
        )

    if state.name_conflict is not None:
        name = state.name_conflict.name
        if state.name_conflict.kind == "rename":
            title = "Rename Conflict"
            message = f"'{name}' already exists. Enter a different name before renaming."
        elif state.name_conflict.kind == "create_file":
            title = "Create File Conflict"
            message = f"'{name}' already exists. Enter a different name before creating the file."
        else:
            title = "Create Directory Conflict"
            message = (
                f"'{name}' already exists. Enter a different name before creating the directory."
            )
        return ConflictDialogState(
            title=title,
            message=message,
            options=("enter return to input", "esc return to input"),
        )

    if state.paste_conflict is None:
        return None

    first_conflict = state.paste_conflict.first_conflict
    conflict_count = len(state.paste_conflict.conflicts)
    destination_name = Path(first_conflict.destination_path).name
    source_name = Path(first_conflict.source_path).name
    return ConflictDialogState(
        title="Paste Conflict",
        message=(
            f"{destination_name} already exists for {source_name}. "
            f"{conflict_count} conflict(s) pending."
        ),
        options=tuple(
            {
                "overwrite": "o overwrite",
                "skip": "s skip",
                "rename": "r rename",
            }[resolution]
            for resolution in state.paste_conflict.available_resolutions
        )
        + ("esc cancel",),
    )


def select_attribute_dialog_state(state: AppState) -> AttributeDialogState | None:
    """Return dialog content when the app is showing read-only attributes."""

    if state.ui_mode == "ABOUT":
        return AttributeDialogState(
            title="About zivo",
            lines=(
                f"Version: {importlib.metadata.version('zivo')}",
                "Author: devgamesan",
                "License: MIT License",
                "Repository: https://github.com/devgamesan/zivo",
            ),
            options=("enter close", "esc close"),
        )

    if state.attribute_inspection is None:
        return None

    entry = state.attribute_inspection
    kind_label = "Directory" if entry.kind == "dir" else "File"
    hidden_label = "Yes" if entry.hidden else "No"
    symlink_label = "Yes" if entry.symlink else "No"
    return AttributeDialogState(
        title=f"Attributes: {entry.name}",
        lines=(
            f"Name: {entry.name}",
            f"Type: {kind_label}",
            f"Symlink: {symlink_label}",
            f"Path: {entry.path}",
            f"Size: {_format_size_label(entry.size_bytes)}",
            f"Modified: {_format_modified_label_from_timestamp(entry.modified_at)}",
            f"Hidden: {hidden_label}",
            f"Permissions: {_format_attribute_permissions_label(state)}",
        ),
        options=("enter close", "esc close"),
    )


def select_config_dialog_state(state: AppState) -> ConfigDialogState | None:
    """Return dialog content when the app is showing editable config values."""

    if state.ui_mode != "CONFIG" or state.config_editor is None:
        return None

    config = state.config_editor.draft
    selected_index = state.config_editor.cursor_index
    labels = config_editor_labels()
    lines_list: list[str] = [
        f"Path: {state.config_editor.path}",
        "",
    ]

    for header, field_indices in CONFIG_EDITOR_CATEGORIES:
        lines_list.append(f"  ── {header} ──")
        for field_idx in field_indices:
            lines_list.append(
                _format_config_line(
                    is_selected=(field_idx == selected_index),
                    label=labels[field_idx],
                    value=format_config_field_value(field_idx, config),
                )
            )

    lines_list.extend([
        "",
        "  ── Selected Setting ──",
        f"  {labels[selected_index]}",
    ])
    lines_list.extend(
        f"  {line}" for line in config_editor_field_description(selected_index, config)
    )
    lines_list.extend([
        "",
        "  ── Advanced Settings ──",
        "  Edit config.toml with e for advanced, custom, and future settings.",
        "  Saving here preserves settings that are not shown above.",
        _format_custom_editor_hint(config.editor.command),
        "GUI editor presets: " + ", ".join(name for name, _config in CONFIG_GUI_EDITOR_PRESETS),
    ])

    title = "Config Editor (Basic Settings)"
    if state.config_editor.dirty:
        title = f"{title}*"
    return ConfigDialogState(
        title=title,
        lines=tuple(lines_list),
        options=(
            "↑↓/Ctrl+j/k choose",
            "←→/enter change",
            "s save",
            "e advanced config",
            "esc close",
        ),
    )


def select_shell_command_dialog_state(state: AppState) -> ShellCommandDialogState | None:
    """Return dialog content when the app is collecting a shell command."""

    if state.ui_mode != "SHELL" or state.shell_command is None:
        return None

    # 結果がある場合は結果表示モード
    if state.shell_command.result is not None:
        return ShellCommandDialogState(
            title="Shell Command Result",
            cwd=state.shell_command.cwd,
            prompt="Command: ",
            command=state.shell_command.command,
            cursor_pos=state.shell_command.cursor_pos,
            options=("r rerun", "t terminal", "esc close"),
            result=state.shell_command.result,
        )

    # コマンド入力モード
    return ShellCommandDialogState(
        title="Run Shell Command",
        cwd=state.shell_command.cwd,
        prompt="Command: ",
        command=state.shell_command.command,
        cursor_pos=state.shell_command.cursor_pos,
        options=("enter run", "esc cancel"),
        guidance="Runs in the background; use t for interactive commands.",
        result=None,
    )


def _file_search_empty_message(state: AppState) -> str:
    if state.pending_file_search_request_id is not None:
        return "Searching files..."
    if (
        state.command_palette is not None
        and state.command_palette.source == "file_search"
        and state.command_palette.file_search.error_message is not None
    ):
        return state.command_palette.file_search.error_message
    file_search = state.command_palette.file_search if state.command_palette else None
    if file_search is not None and (
        file_search.include_extensions or file_search.exclude_extensions
    ):
        return "No matching files for the current extension filters"
    return "No matching files"


def _search_truncation_message(state: AppState, source: str) -> str | None:
    if state.command_palette is None:
        return None
    if source == "file_search":
        truncated = state.command_palette.file_search.results_truncated
        configured_limit = state.config.file_search.max_results
    else:
        truncated = state.command_palette.grep_search.results_truncated
        configured_limit = state.config.grep_search.max_results
    if not truncated:
        return None
    from zivo.models.config import DEFAULT_SEARCH_MAX_RESULTS

    limit = configured_limit or DEFAULT_SEARCH_MAX_RESULTS
    return (
        f"Showing first {limit:,} results — more results omitted. "
        "Refine the query or change max_results."
    )


def _grep_search_empty_message(state: AppState) -> str:
    if state.pending_grep_search_request_id is not None:
        return "Searching matches..."
    if (
        state.command_palette is not None
        and state.command_palette.source == "grep_search"
        and state.command_palette.grep_search.scope_message is not None
    ):
        return state.command_palette.grep_search.scope_message
    if (
        state.command_palette is not None
        and state.command_palette.source == "grep_search"
        and state.command_palette.grep_search.error_message is not None
    ):
        return state.command_palette.grep_search.error_message
    return "No matching lines"


def _replace_text_empty_message(state: AppState) -> str:
    if state.pending_replace_preview_request_id is not None:
        return "Previewing diff in right pane..."
    if state.command_palette is None or state.command_palette.source != "replace_text":
        return ""
    if state.command_palette.replace_preview.error_message is not None:
        return state.command_palette.replace_preview.error_message
    if not state.command_palette.replace_preview.find_text.strip():
        return "Type text to find"
    if state.command_palette.replace_preview.status_message is not None:
        return state.command_palette.replace_preview.status_message
    if state.command_palette.replace_preview.total_match_count > 0:
        return "Preview shown in right pane. Press Enter to apply."
    return "No matching files"


def _replace_result_context_message(state: AppState) -> str | None:
    if state.command_palette is None or state.command_palette.source != "replace_text":
        return None
    preview = state.command_palette.replace_preview
    if preview.result_origin is None:
        return None
    origin_labels = {"find": "Find", "grep": "Grep", "workspace": "Search Workspace"}
    origin = origin_labels[preview.result_origin]
    query = f' "{preview.result_query}"' if preview.result_query else ""
    file_count = preview.result_file_count or len(preview.target_paths)
    match_count = preview.result_match_count
    if match_count:
        return (
            f"{origin}{query} · {file_count} file(s) / "
            f"{match_count} match(es) · preview before apply"
        )
    return f"{origin}{query} · {file_count} file(s) · preview before apply"


def _find_replace_empty_message(state: AppState) -> str:
    if state.pending_file_search_request_id is not None:
        return "Searching files..."
    if state.command_palette is None or state.command_palette.source != "replace_in_found_files":
        return ""
    if state.command_palette.rff.file_error_message is not None:
        return state.command_palette.rff.file_error_message
    if not state.command_palette.rff.filename_query.strip():
        return "Type a filename pattern"
    if state.pending_replace_preview_request_id is not None:
        return "Previewing diff in right pane..."
    if state.command_palette.rff.error_message is not None:
        return state.command_palette.rff.error_message
    if not state.command_palette.rff.find_text.strip():
        file_count = len(state.command_palette.rff.file_results)
        if file_count == 0:
            return "No matching files"
        return f"{file_count} file(s) found. Tab to Find field."
    if state.command_palette.rff.status_message is not None:
        return state.command_palette.rff.status_message
    if state.command_palette.rff.total_match_count > 0:
        return "Preview shown in right pane. Press Enter to apply."
    return "No matching files"


def _grep_replace_empty_message(state: AppState) -> str:
    if state.pending_grep_search_request_id is not None:
        return "Searching..."
    if state.command_palette is None or state.command_palette.source != "replace_in_grep_files":
        return ""
    if state.command_palette.grf.grep_error_message is not None:
        return state.command_palette.grf.grep_error_message
    if not state.command_palette.grf.keyword.strip():
        return "Type a search keyword"
    if not state.command_palette.grf.replacement_text.strip():
        file_count = len(state.command_palette.grf.grep_results)
        if file_count == 0:
            return "No matching lines"
        return f"{file_count} result(s) found. Tab to Replace field."
    if state.pending_replace_preview_request_id is not None:
        return "Previewing diff in right pane..."
    if state.command_palette.grf.error_message is not None:
        return state.command_palette.grf.error_message
    if state.command_palette.grf.status_message is not None:
        return state.command_palette.grf.status_message
    if state.command_palette.grf.total_match_count > 0:
        return "Preview shown in right pane. Press Enter to apply."
    return "No matching files"


def _grep_replace_selected_empty_message(state: AppState) -> str:
    if state.pending_grep_search_request_id is not None:
        return "Searching..."
    if state.command_palette is None or state.command_palette.source != "grep_replace_selected":
        return ""
    if state.command_palette.grs.grep_error_message is not None:
        return state.command_palette.grs.grep_error_message
    if not state.command_palette.grs.keyword.strip():
        return "Type a search keyword"
    if not state.command_palette.grs.replacement_text.strip():
        file_count = len(state.command_palette.grs.grep_results)
        if file_count == 0:
            return "No matching lines in selected files"
        return f"{file_count} result(s) found. Tab to Replace field."
    if state.pending_replace_preview_request_id is not None:
        return "Previewing diff in right pane..."
    if state.command_palette.grs.error_message is not None:
        return state.command_palette.grs.error_message
    if state.command_palette.grs.status_message is not None:
        return state.command_palette.grs.status_message
    if state.command_palette.grs.total_match_count > 0:
        return "Preview shown in right pane. Press Enter to apply."
    return "No matching files"
