"""Status, palette, and dialog selectors."""

from pathlib import Path

from zivo.models import (
    AttributeDialogState,
    CommandPaletteItemViewState,
    CommandPaletteViewState,
    ConfigDialogState,
    ConflictDialogState,
    HelpBarState,
    InputBarState,
    InputDialogState,
    ShellCommandDialogState,
    StatusBarState,
)
from zivo.platform_support import is_split_terminal_supported

from .models import AppState
from .reducer_config import (
    CONFIG_EDITOR_CATEGORIES,
    CONFIG_GUI_EDITOR_PRESETS,
    config_editor_field_description,
    config_editor_labels,
    format_config_field_value,
)
from .selectors_shared import (
    _build_command_palette_items_view,
    _build_file_search_input_fields,
    _build_find_replace_input_fields,
    _build_grep_replace_input_fields,
    _build_grep_replace_selected_input_fields,
    _build_grep_search_input_fields,
    _build_replace_input_fields,
    _build_selected_files_grep_input_fields,
    _format_config_line,
    _format_custom_editor_hint,
    _format_modified_label_from_timestamp,
    _format_permissions_label,
    _format_size_label,
    _select_command_palette_window,
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

    return StatusBarState(
        message=state.notification.message if state.notification else None,
        message_level=state.notification.level if state.notification else None,
    )


def select_help_bar_state(state: AppState) -> HelpBarState:
    """Return the help content for the active mode."""

    if state.ui_mode == "CONFIRM":
        if state.delete_confirmation is not None:
            if (
                state.delete_confirmation.mode == "trash"
                and state.config.help_bar.confirm_delete
            ):
                return HelpBarState(state.config.help_bar.confirm_delete)
            if state.delete_confirmation.mode == "permanent":
                return HelpBarState(("enter confirm permanent delete | esc cancel",))
            return HelpBarState(("enter confirm delete | esc cancel",))
        if state.exit_confirmation is not None:
            if state.config.help_bar.confirm_exit:
                return HelpBarState(state.config.help_bar.confirm_exit)
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
        if state.config.help_bar.detail:
            return HelpBarState(state.config.help_bar.detail)
        return HelpBarState(("enter close | esc close",))
    if state.ui_mode == "CONFIG":
        if state.config.help_bar.config:
            return HelpBarState(state.config.help_bar.config)
        return HelpBarState(
            (
                "↑↓ or Ctrl+n/p choose | ←→ or Enter change | s save | e edit file | r reset help",
                "esc close",
            )
        )
    if state.ui_mode == "SHELL":
        # 結果表示状態の場合
        if state.shell_command is not None and state.shell_command.result is not None:
            return HelpBarState(("press esc to close",))
        # コマンド入力状態の場合
        if state.config.help_bar.shell:
            return HelpBarState(state.config.help_bar.shell)
        return HelpBarState(("type command | enter run | esc cancel",))
    if state.ui_mode == "FILTER":
        if state.config.help_bar.filter:
            return HelpBarState(state.config.help_bar.filter)
        return HelpBarState(("type filter | enter/down apply | esc clear",))
    if state.ui_mode == "RENAME":
        if state.config.help_bar.rename:
            return HelpBarState(state.config.help_bar.rename)
        return HelpBarState(("type name | enter apply | esc cancel",))
    if state.ui_mode == "CREATE":
        if state.config.help_bar.create:
            return HelpBarState(state.config.help_bar.create)
        return HelpBarState(("type name | enter apply | esc cancel",))
    if state.ui_mode == "EXTRACT":
        if state.config.help_bar.extract:
            return HelpBarState(state.config.help_bar.extract)
        return HelpBarState(("type destination path | enter extract | esc cancel",))
    if state.ui_mode == "ZIP":
        if state.config.help_bar.zip:
            return HelpBarState(state.config.help_bar.zip)
        return HelpBarState(("type zip path | enter compress | esc cancel",))
    if state.ui_mode == "SYMLINK":
        return HelpBarState(("type destination path | tab complete | enter create | esc cancel",))
    if state.ui_mode == "PALETTE":
        if state.command_palette is not None and state.command_palette.source == "file_search":
            if state.config.help_bar.palette_file_search:
                return HelpBarState(state.config.help_bar.palette_file_search)
            return HelpBarState(
                (
                    "type filename | ↑↓ or Ctrl+n/p select | enter jump | "
                    "Ctrl+e edit | Ctrl+o GUI | esc cancel",
                )
            )
        if state.command_palette is not None and state.command_palette.source == "grep_search":
            if state.config.help_bar.palette_grep_search:
                return HelpBarState(state.config.help_bar.palette_grep_search)
            return HelpBarState(
                (
                    "type text / tab fields / ↑↓ or Ctrl+n/p select | "
                    "enter jump | Ctrl+e edit | Ctrl+o GUI | esc cancel",
                )
            )
        if (
            state.command_palette is not None
            and state.command_palette.source in {
                "replace_text",
                "replace_in_found_files",
                "replace_in_grep_files",
                "grep_replace_selected",
            }
        ):
            return HelpBarState(
                (
                    "type text / tab fields / ↑↓ or Ctrl+n/p preview | "
                    "Shift+↑↓ scroll preview | enter apply | esc cancel",
                )
            )
        if (
            state.command_palette is not None
            and state.command_palette.source == "selected_files_grep"
        ):
            return HelpBarState(
                (
                    "type keyword / ↑↓ or Ctrl+n/p select | enter jump | "
                    "Ctrl+e edit | Ctrl+o GUI | esc cancel",
                )
            )
        if state.command_palette is not None and state.command_palette.source == "history":
            if state.config.help_bar.palette_history:
                return HelpBarState(state.config.help_bar.palette_history)
            return HelpBarState(("type path | ↑↓ or Ctrl+n/p select | enter jump | esc cancel",))
        if state.command_palette is not None and state.command_palette.source == "bookmarks":
            if state.config.help_bar.palette_bookmarks:
                return HelpBarState(state.config.help_bar.palette_bookmarks)
            return HelpBarState(("type path | ↑↓ or Ctrl+n/p select | enter jump | esc cancel",))
        if state.command_palette is not None and state.command_palette.source == "go_to_path":
            if state.config.help_bar.palette_go_to_path:
                return HelpBarState(state.config.help_bar.palette_go_to_path)
            return HelpBarState(
                ("type path | ↑↓ or Ctrl+n/p select | tab complete | enter jump | esc cancel",)
            )
        if state.config.help_bar.palette:
            return HelpBarState(state.config.help_bar.palette)
        return HelpBarState(("type command | ↑↓ or Ctrl+n/p select | enter run | esc cancel",))
    if state.ui_mode == "BUSY":
        if state.config.help_bar.busy:
            return HelpBarState(state.config.help_bar.busy)
        return HelpBarState(("processing...",))
    if state.layout_mode == "transfer":
        if state.config.help_bar.transfer:
            return HelpBarState(state.config.help_bar.transfer)
        return HelpBarState(
            (
                "[ ] focus | y copy-to-pane | m move-to-pane | p/Esc close | q quit",
                "Space select | c copy | x cut | v paste | d delete | r rename | z undo",
                ". hidden | N new-dir | : palette",
            )
        )
    if state.config.help_bar.browsing:
        return HelpBarState(state.config.help_bar.browsing)
    split_terminal_hint = " | t term" if is_split_terminal_supported() else ""
    return HelpBarState(
        (
            "enter open | e edit | O gui editor | i info | "
            "/ filter | s sort | . hidden | [ ] preview | q quit",
            "space select | c copy | x cut | v paste | d delete | r rename | z undo",
            f"f find | g grep | n new-file | N new-dir{split_terminal_hint} | : palette",
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

    if state.ui_mode not in {"RENAME", "CREATE", "EXTRACT", "ZIP", "SYMLINK"}:
        return None
    if state.pending_input is None:
        return None
    if state.ui_mode == "RENAME":
        title = "Rename"
    elif state.ui_mode == "EXTRACT":
        title = "Extract"
    elif state.ui_mode == "ZIP":
        title = "Compress"
    elif state.ui_mode == "SYMLINK":
        title = "Create Symlink"
    elif state.pending_input.create_kind == "file":
        title = "New File"
    else:
        title = "New Directory"
    return InputDialogState(
        title=title,
        prompt=state.pending_input.prompt,
        value=state.pending_input.value,
        cursor_pos=state.pending_input.cursor_pos,
        hint=(
            "tab complete | enter apply | esc cancel"
            if state.ui_mode == "SYMLINK"
            else "enter apply | esc cancel"
        ),
    )


def select_command_palette_state(state: AppState) -> CommandPaletteViewState | None:
    """Return the visible command palette entries for the active mode."""

    if state.ui_mode != "PALETTE" or state.command_palette is None:
        return None

    cursor_index = normalize_command_palette_cursor(state, state.command_palette.cursor_index)
    if state.command_palette.source == "file_search":
        visible_results, title = _select_file_search_window(
            state,
            state.command_palette.file_search_results,
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
            has_more_items=len(state.command_palette.file_search_results) > len(visible_results),
            input_fields=_build_file_search_input_fields(state.command_palette),
        )
    if state.command_palette.source == "grep_search":
        visible_results, title = _select_grep_search_window(
            state,
            state.command_palette.grep_search_results,
            cursor_index,
        )
        return CommandPaletteViewState(
            title=title,
            query=state.command_palette.grep_search_keyword,
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
            has_more_items=len(state.command_palette.grep_search_results) > len(visible_results),
        )
    if state.command_palette.source == "replace_text":
        visible_results, title = _select_replace_preview_window(
            state,
            state.command_palette.replace_preview_results,
            cursor_index,
        )
        return CommandPaletteViewState(
            title=title,
            query=state.command_palette.replace_find_text,
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
                len(state.command_palette.replace_preview_results) > len(visible_results)
            ),
        )
    if state.command_palette.source == "replace_in_found_files":
        visible_results, title = _select_find_replace_preview_window(
            state,
            state.command_palette.rff_preview_results,
            cursor_index,
        )
        return CommandPaletteViewState(
            title=title,
            query=state.command_palette.rff_filename_query,
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
                len(state.command_palette.rff_preview_results) > len(visible_results)
            ),
        )
    if state.command_palette.source == "replace_in_grep_files":
        visible_results, title = _select_find_replace_preview_window(
            state,
            state.command_palette.grf_preview_results,
            cursor_index,
        )
        return CommandPaletteViewState(
            title=title,
            query=state.command_palette.grf_keyword,
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
                len(state.command_palette.grf_preview_results) > len(visible_results)
            ),
        )
    if state.command_palette.source == "grep_replace_selected":
        visible_results, title = _select_find_replace_preview_window(
            state,
            state.command_palette.grs_preview_results,
            cursor_index,
        )
        return CommandPaletteViewState(
            title=title,
            query=state.command_palette.grs_keyword,
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
                len(state.command_palette.grs_preview_results) > len(visible_results)
            ),
        )
    if state.command_palette.source == "selected_files_grep":
        visible_results, title = _select_grep_search_window(
            state,
            state.command_palette.sfg.results,
            cursor_index,
        )
        return CommandPaletteViewState(
            title=title,
            query=state.command_palette.sfg.keyword,
            items=tuple(
                CommandPaletteItemViewState(
                    label=result.display_label,
                    shortcut=None,
                    enabled=True,
                    selected=index == cursor_index,
                )
                for index, result in visible_results
            ),
            empty_message=_selected_files_grep_empty_message(state),
            input_fields=_build_selected_files_grep_input_fields(state.command_palette),
            has_more_items=(len(state.command_palette.sfg.results) > len(visible_results)),
        )
    if state.command_palette.source == "history":
        return _build_command_palette_items_view(
            state,
            cursor_index,
            title="Directory History",
            empty_message="No directory history",
        )

    if state.command_palette.source == "bookmarks":
        return _build_command_palette_items_view(
            state,
            cursor_index,
            title="Bookmarks",
            empty_message="No bookmarks",
        )

    if state.command_palette.source == "go_to_path":
        selection_active = state.command_palette.history_and_navigation.go_to_path_selection_active
        empty_message = (
            "Type a path to jump to"
            if not state.command_palette.query.strip()
            else "No matching directories"
        )
        return _build_command_palette_items_view(
            state,
            cursor_index,
            title="Go to path",
            empty_message=empty_message,
            selected_override=selection_active or False,
        )

    items = get_command_palette_items(state)
    visible_window = compute_search_visible_window(state.terminal_height)
    visible_items, title = _select_command_palette_window(
        items,
        cursor_index,
        visible_window=visible_window,
    )
    return CommandPaletteViewState(
        title=title,
        query=state.command_palette.query,
        items=tuple(
            CommandPaletteItemViewState(
                label=item.label,
                shortcut=item.shortcut,
                enabled=item.enabled,
                selected=index == cursor_index,
            )
            for index, item in visible_items
        ),
        empty_message="No matching commands",
        has_more_items=len(items) > len(visible_items),
    )


def select_conflict_dialog_state(state: AppState) -> ConflictDialogState | None:
    """Return dialog content when the app is waiting on conflict input."""

    if state.delete_confirmation is not None:
        confirmation = state.delete_confirmation
        target_count = len(confirmation.paths)
        first_name = Path(confirmation.paths[0]).name
        noun = "item" if target_count == 1 else "items"
        if confirmation.mode == "permanent":
            message = f"Permanently delete {target_count} {noun}? This cannot be undone."
            if target_count > 1:
                message = (
                    f"Permanently delete {target_count} items? "
                    f"The first target is {first_name}. This cannot be undone."
                )
            title = "Permanent Delete Confirmation"
        else:
            message = f"Move {target_count} {noun} to trash?"
            if target_count > 1:
                message = f"Move {target_count} items to trash? The first target is {first_name}."
            title = "Delete Confirmation"
        return ConflictDialogState(
            title=title,
            message=message,
            options=("enter confirm", "esc cancel"),
        )

    if state.empty_trash_confirmation is not None:
        confirmation = state.empty_trash_confirmation
        platform_name = "Linux" if confirmation.platform == "linux" else "macOS"
        message = (
            f"Permanently delete all items from the {platform_name} trash? "
            "This cannot be undone."
        )
        return ConflictDialogState(
            title="Empty Trash Confirmation",
            message=message,
            options=("enter confirm", "esc cancel"),
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
        return ConflictDialogState(
            title="Exit Confirmation",
            message="Exit the application?",
            options=("enter confirm", "esc cancel"),
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
        _format_custom_editor_hint(config.editor.command),
        "GUI editor presets: "
        + ", ".join(name for name, _config in CONFIG_GUI_EDITOR_PRESETS),
        "Terminal launch templates: edit config.toml with e",
        f"  Linux templates: {len(config.terminal.linux)}",
        f"  macOS templates: {len(config.terminal.macos)}",
        f"  Windows templates: {len(config.terminal.windows)}",
    ])

    title = "Config Editor"
    if state.config_editor.dirty:
        title = "Config Editor*"
    return ConfigDialogState(
        title=title,
        lines=tuple(lines_list),
        options=(
            "↑↓/Ctrl+n/p choose",
            "←→/enter change",
            "s save",
            "e edit file",
            "r reset help",
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
            options=("esc close",),
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
        result=None,
    )


def _file_search_empty_message(state: AppState) -> str:
    if state.pending_file_search_request_id is not None:
        return "Searching files..."
    if (
        state.command_palette is not None
        and state.command_palette.source == "file_search"
        and state.command_palette.file_search_error_message is not None
    ):
        return state.command_palette.file_search_error_message
    return "No matching files"


def _grep_search_empty_message(state: AppState) -> str:
    if state.pending_grep_search_request_id is not None:
        return "Searching matches..."
    if (
        state.command_palette is not None
        and state.command_palette.source == "grep_search"
        and state.command_palette.grep_search_error_message is not None
    ):
        return state.command_palette.grep_search_error_message
    return "No matching lines"


def _replace_text_empty_message(state: AppState) -> str:
    if state.pending_replace_preview_request_id is not None:
        return "Previewing diff in right pane..."
    if state.command_palette is None or state.command_palette.source != "replace_text":
        return ""
    if state.command_palette.replace_error_message is not None:
        return state.command_palette.replace_error_message
    if not state.command_palette.replace_find_text.strip():
        return "Type text to find"
    if state.command_palette.replace_status_message is not None:
        return state.command_palette.replace_status_message
    if state.command_palette.replace_total_match_count > 0:
        return "Preview shown in right pane. Press Enter to apply."
    return "No matching files"


def _find_replace_empty_message(state: AppState) -> str:
    if state.pending_file_search_request_id is not None:
        return "Searching files..."
    if state.command_palette is None or state.command_palette.source != "replace_in_found_files":
        return ""
    if state.command_palette.rff_file_error_message is not None:
        return state.command_palette.rff_file_error_message
    if not state.command_palette.rff_filename_query.strip():
        return "Type a filename pattern"
    if state.pending_replace_preview_request_id is not None:
        return "Previewing diff in right pane..."
    if state.command_palette.rff_error_message is not None:
        return state.command_palette.rff_error_message
    if not state.command_palette.rff_find_text.strip():
        file_count = len(state.command_palette.rff_file_results)
        if file_count == 0:
            return "No matching files"
        return f"{file_count} file(s) found. Tab to Find field."
    if state.command_palette.rff_status_message is not None:
        return state.command_palette.rff_status_message
    if state.command_palette.rff_total_match_count > 0:
        return "Preview shown in right pane. Press Enter to apply."
    return "No matching files"


def _grep_replace_empty_message(state: AppState) -> str:
    if state.pending_grep_search_request_id is not None:
        return "Searching..."
    if state.command_palette is None or state.command_palette.source != "replace_in_grep_files":
        return ""
    if state.command_palette.grf_grep_error_message is not None:
        return state.command_palette.grf_grep_error_message
    if not state.command_palette.grf_keyword.strip():
        return "Type a search keyword"
    if not state.command_palette.grf_replacement_text.strip():
        file_count = len(state.command_palette.grf_grep_results)
        if file_count == 0:
            return "No matching lines"
        return f"{file_count} result(s) found. Tab to Replace field."
    if state.pending_replace_preview_request_id is not None:
        return "Previewing diff in right pane..."
    if state.command_palette.grf_error_message is not None:
        return state.command_palette.grf_error_message
    if state.command_palette.grf_status_message is not None:
        return state.command_palette.grf_status_message
    if state.command_palette.grf_total_match_count > 0:
        return "Preview shown in right pane. Press Enter to apply."
    return "No matching files"


def _grep_replace_selected_empty_message(state: AppState) -> str:
    if state.pending_grep_search_request_id is not None:
        return "Searching..."
    if state.command_palette is None or state.command_palette.source != "grep_replace_selected":
        return ""
    if state.command_palette.grs_grep_error_message is not None:
        return state.command_palette.grs_grep_error_message
    if not state.command_palette.grs_keyword.strip():
        return "Type a search keyword"
    if not state.command_palette.grs_replacement_text.strip():
        file_count = len(state.command_palette.grs_grep_results)
        if file_count == 0:
            return "No matching lines in selected files"
        return f"{file_count} result(s) found. Tab to Replace field."
    if state.pending_replace_preview_request_id is not None:
        return "Previewing diff in right pane..."
    if state.command_palette.grs_error_message is not None:
        return state.command_palette.grs_error_message
    if state.command_palette.grs_status_message is not None:
        return state.command_palette.grs_status_message
    if state.command_palette.grs_total_match_count > 0:
        return "Preview shown in right pane. Press Enter to apply."
    return "No matching files"


def _selected_files_grep_empty_message(state: AppState) -> str:
    if state.pending_grep_search_request_id is not None:
        return "Searching..."
    if state.command_palette is None or state.command_palette.source != "selected_files_grep":
        return ""
    if state.command_palette.sfg.error_message is not None:
        return state.command_palette.sfg.error_message
    if not state.command_palette.sfg.keyword.strip():
        return "Type a search keyword"
    if not state.command_palette.sfg.results:
        return "No matches found in selected files"
    return ""
