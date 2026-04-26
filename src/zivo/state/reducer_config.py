"""Shared config editor definitions and helpers."""

from dataclasses import replace

from zivo.models import AppConfig
from zivo.theme_support import SUPPORTED_APP_THEMES, SUPPORTED_PREVIEW_SYNTAX_THEMES

from .models import SortState

CONFIG_SORT_FIELDS = ("name", "modified", "size")
CONFIG_THEMES = SUPPORTED_APP_THEMES
CONFIG_PREVIEW_SYNTAX_THEMES = SUPPORTED_PREVIEW_SYNTAX_THEMES
CONFIG_PREVIEW_MAX_KIB = (64, 128, 256, 512, 1024)
CONFIG_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
CONFIG_PASTE_ACTIONS = ("prompt", "overwrite", "skip", "rename")
CONFIG_TERMINAL_LAUNCH_MODES = ("window", "foreground")
CONFIG_EDITOR_COMMANDS = (None, "nvim", "vim", "nano", "hx", "micro", "emacs -nw")
CONFIG_SPLIT_TERMINAL_POSITIONS = ("bottom", "right", "overlay")
CONFIG_FILE_SEARCH_MAX_RESULTS = (None, 100, 500, 1000, 5000, 10000)


def normalize_config_editor_cursor(cursor_index: int) -> int:
    return max(0, min(len(config_editor_labels()) - 1, cursor_index))


def cycle_config_editor_value(config: AppConfig, cursor_index: int, delta: int) -> AppConfig:
    field_id = config_editor_field_ids()[normalize_config_editor_cursor(cursor_index)]
    if field_id == "editor.command":
        return replace(
            config,
            editor=replace(
                config.editor,
                command=cycle_editor_command(config.editor.command, delta),
            ),
        )
    if field_id == "terminal.launch_mode":
        return replace(
            config,
            terminal=replace(
                config.terminal,
                launch_mode=cycle_choice(
                    CONFIG_TERMINAL_LAUNCH_MODES,
                    config.terminal.launch_mode,
                    delta,
                ),
            ),
        )
    if field_id == "display.show_hidden_files":
        return replace(
            config,
            display=replace(
                config.display,
                show_hidden_files=not config.display.show_hidden_files,
            ),
        )
    if field_id == "display.show_directory_sizes":
        return replace(
            config,
            display=replace(
                config.display,
                show_directory_sizes=not config.display.show_directory_sizes,
            ),
        )
    if field_id == "display.enable_text_preview":
        return replace(
            config,
            display=replace(
                config.display,
                enable_text_preview=not config.display.enable_text_preview,
            ),
        )
    if field_id == "display.enable_image_preview":
        return replace(
            config,
            display=replace(
                config.display,
                enable_image_preview=not config.display.enable_image_preview,
            ),
        )
    if field_id == "display.enable_pdf_preview":
        return replace(
            config,
            display=replace(
                config.display,
                enable_pdf_preview=not config.display.enable_pdf_preview,
            ),
        )
    if field_id == "display.enable_office_preview":
        return replace(
            config,
            display=replace(
                config.display,
                enable_office_preview=not config.display.enable_office_preview,
            ),
        )
    if field_id == "display.show_help_bar":
        return replace(
            config,
            display=replace(
                config.display,
                show_help_bar=not config.display.show_help_bar,
            ),
        )
    if field_id == "display.theme":
        return replace(
            config,
            display=replace(
                config.display,
                theme=cycle_choice(
                    CONFIG_THEMES,
                    config.display.theme,
                    delta,
                ),
            ),
        )
    if field_id == "display.preview_syntax_theme":
        return replace(
            config,
            display=replace(
                config.display,
                preview_syntax_theme=cycle_choice(
                    CONFIG_PREVIEW_SYNTAX_THEMES,
                    config.display.preview_syntax_theme,
                    delta,
                ),
            ),
        )
    if field_id == "display.preview_max_kib":
        return replace(
            config,
            display=replace(
                config.display,
                preview_max_kib=cycle_choice(
                    CONFIG_PREVIEW_MAX_KIB,
                    config.display.preview_max_kib,
                    delta,
                ),
            ),
        )
    if field_id == "display.default_sort_field":
        return replace(
            config,
            display=replace(
                config.display,
                default_sort_field=cycle_choice(
                    CONFIG_SORT_FIELDS,
                    config.display.default_sort_field,
                    delta,
                ),
            ),
        )
    if field_id == "display.default_sort_descending":
        return replace(
            config,
            display=replace(
                config.display,
                default_sort_descending=not config.display.default_sort_descending,
            ),
        )
    if field_id == "display.directories_first":
        return replace(
            config,
            display=replace(
                config.display,
                directories_first=not config.display.directories_first,
            ),
        )
    if field_id == "display.grep_preview_context_lines":
        return replace(
            config,
            display=replace(
                config.display,
                grep_preview_context_lines=max(
                    0, config.display.grep_preview_context_lines + delta
                ),
            ),
        )
    if field_id == "display.split_terminal_position":
        return replace(
            config,
            display=replace(
                config.display,
                split_terminal_position=cycle_choice(
                    CONFIG_SPLIT_TERMINAL_POSITIONS,
                    config.display.split_terminal_position,
                    delta,
                ),
            ),
        )
    if field_id == "behavior.confirm_delete":
        return replace(
            config,
            behavior=replace(
                config.behavior,
                confirm_delete=not config.behavior.confirm_delete,
            ),
        )
    if field_id == "logging.level":
        return replace(
            config,
            logging=replace(
                config.logging,
                level=cycle_choice(
                    CONFIG_LOG_LEVELS,
                    config.logging.level,
                    delta,
                ),
            ),
        )
    if field_id == "file_search.max_results":
        current = config.file_search.max_results
        if current not in CONFIG_FILE_SEARCH_MAX_RESULTS:
            current = None
        current_index = CONFIG_FILE_SEARCH_MAX_RESULTS.index(current)
        new_max_results = CONFIG_FILE_SEARCH_MAX_RESULTS[
            (current_index + delta) % len(CONFIG_FILE_SEARCH_MAX_RESULTS)
        ]
        return replace(
            config,
            file_search=replace(
                config.file_search,
                max_results=new_max_results,
            ),
        )
    return replace(
        config,
        behavior=replace(
            config.behavior,
            paste_conflict_action=cycle_choice(
                CONFIG_PASTE_ACTIONS,
                config.behavior.paste_conflict_action,
                delta,
            ),
        ),
    )


def cycle_choice(options: tuple[str, ...], current: str, delta: int) -> str:
    current_index = options.index(current) if current in options else 0
    return options[(current_index + delta) % len(options)]


def cycle_editor_command(current: str | None, delta: int) -> str | None:
    if current in CONFIG_EDITOR_COMMANDS:
        current_index = CONFIG_EDITOR_COMMANDS.index(current)
    else:
        current_index = len(CONFIG_EDITOR_COMMANDS)
    return CONFIG_EDITOR_COMMANDS[(current_index + delta) % len(CONFIG_EDITOR_COMMANDS)]


def config_editor_field_ids() -> tuple[str, ...]:
    return (
        "editor.command",
        "terminal.launch_mode",
        "display.show_hidden_files",
        "display.theme",
        "display.show_directory_sizes",
        "display.enable_text_preview",
        "display.enable_image_preview",
        "display.enable_pdf_preview",
        "display.enable_office_preview",
        "display.preview_syntax_theme",
        "display.preview_max_kib",
        "display.show_help_bar",
        "display.default_sort_field",
        "display.default_sort_descending",
        "display.directories_first",
        "display.grep_preview_context_lines",
        "display.split_terminal_position",
        "behavior.confirm_delete",
        "behavior.paste_conflict_action",
        "logging.level",
        "file_search.max_results",
    )


def config_editor_labels() -> tuple[str, ...]:
    return (
        "Editor command",
        "Terminal launch mode",
        "Show hidden files",
        "Theme",
        "Show directory sizes",
        "Text preview",
        "Image preview",
        "PDF preview",
        "Office preview",
        "Preview syntax theme",
        "Preview max KiB",
        "Show help bar",
        "Default sort field",
        "Default sort descending",
        "Directories first",
        "Grep preview context lines",
        "Split terminal position",
        "Confirm delete",
        "Paste conflict action",
        "Log level",
        "File search max results",
    )


def config_editor_field_description(field_index: int, config: AppConfig) -> tuple[str, ...]:
    """Return short detail lines for the selected config editor field."""

    field_id = config_editor_field_ids()[field_index]
    if field_id == "editor.command":
        lines = [
            "How file editing is launched from zivo.",
            "Uses config.toml first, then $EDITOR, then built-in terminal editors.",
        ]
        if config.editor.command is None:
            lines.append("Current behavior: system default fallback chain is active.")
        elif config.editor.command in CONFIG_EDITOR_COMMANDS:
            lines.append(f"Current behavior: always prefer `{config.editor.command}`.")
        else:
            lines.append(
                f"Current behavior: custom raw command `{config.editor.command}` is preserved."
            )
        lines.append("Custom commands can only be edited in the raw config file with `e`.")
        return tuple(lines)
    if field_id == "terminal.launch_mode":
        return (
            "Controls how the external terminal command is launched.",
            "window opens a separate terminal app; foreground hands the current terminal over.",
            "Windows currently supports window mode only.",
            f"Current behavior: `{config.terminal.launch_mode}`.",
        )
    if field_id == "display.show_hidden_files":
        return (
            "Controls whether dotfiles and other hidden entries appear in browser panes.",
            "Current behavior: hidden files are "
            f"{'visible' if config.display.show_hidden_files else 'hidden'} on startup.",
        )
    if field_id == "display.theme":
        return (
            "Sets the application theme used by the panes, dialogs, and status UI.",
            "Changing this here previews the theme immediately before saving.",
            f"Current behavior: `{config.display.theme}`.",
        )
    if field_id == "display.show_directory_sizes":
        return (
            "Controls whether directory rows try to show aggregated directory size labels.",
            "Current behavior: directory size labels are "
            f"{'shown' if config.display.show_directory_sizes else 'hidden'} when available.",
        )
    if field_id == "display.enable_text_preview":
        return (
            "Controls text-file preview in the right pane and grep context preview windows.",
            "Current behavior: text preview is "
            f"{'enabled' if config.display.enable_text_preview else 'disabled'} on startup.",
        )
    if field_id == "display.enable_image_preview":
        return (
            "Controls image-file preview in the right pane using `chafa` output.",
            "Current behavior: image preview is "
            f"{'enabled' if config.display.enable_image_preview else 'disabled'} on startup.",
        )
    if field_id == "display.enable_pdf_preview":
        return (
            "Controls PDF preview conversion in the right pane.",
            "Uses the external `pdftotext` command when available.",
            "Current behavior: PDF preview is "
            f"{'enabled' if config.display.enable_pdf_preview else 'disabled'}.",
        )
    if field_id == "display.enable_office_preview":
        return (
            "Controls modern Office preview conversion in the right pane.",
            "Applies to docx, xlsx, and pptx files through pandoc.",
            "Current behavior: Office preview is "
            f"{'enabled' if config.display.enable_office_preview else 'disabled'}.",
        )
    if field_id == "display.preview_syntax_theme":
        return (
            "Controls syntax highlighting inside the preview pane.",
            "auto follows the brightness of the selected app theme.",
            f"Current behavior: `{config.display.preview_syntax_theme}`.",
        )
    if field_id == "display.preview_max_kib":
        return (
            "Limits how much text zivo reads into the preview pane for a single file.",
            "Higher values show more content but can make previews heavier.",
            f"Current behavior: {config.display.preview_max_kib} KiB.",
        )
    if field_id == "display.show_help_bar":
        return (
            "Controls whether the help bar is visible at the bottom of the UI.",
            "Current behavior: help bar is "
            f"{'shown' if config.display.show_help_bar else 'hidden'} on startup.",
        )
    if field_id == "display.default_sort_field":
        return (
            "Sets the default sort field used when a directory is first loaded.",
            "You can still change sorting later from the running UI.",
            f"Current behavior: sort by `{config.display.default_sort_field}`.",
        )
    if field_id == "display.default_sort_descending":
        return (
            "Controls whether the default sort starts in descending order.",
            "Current behavior: descending sort is "
            f"{'enabled' if config.display.default_sort_descending else 'disabled'}.",
        )
    if field_id == "display.directories_first":
        current_behavior = (
            "kept first."
            if config.display.directories_first
            else "mixed into the main sort order."
        )
        return (
            "Controls whether directories stay grouped before files in sorted lists.",
            f"Current behavior: directories are {current_behavior}",
        )
    if field_id == "display.grep_preview_context_lines":
        return (
            "Sets how many surrounding lines grep search previews include around each match.",
            "Increase this to show more context in grep preview results.",
            f"Current behavior: {config.display.grep_preview_context_lines} context lines.",
        )
    if field_id == "display.split_terminal_position":
        return (
            "Controls where the embedded split terminal appears.",
            "bottom docks below the browser, right docks beside it, overlay floats on top.",
            f"Current behavior: `{config.display.split_terminal_position}`.",
        )
    if field_id == "behavior.confirm_delete":
        return (
            "Controls whether delete and move-to-trash actions ask for confirmation first.",
            "Current behavior: confirmations are "
            f"{'enabled' if config.behavior.confirm_delete else 'disabled'} by default.",
        )
    if field_id == "behavior.paste_conflict_action":
        return (
            "Sets the default behavior when a paste target already exists.",
            "prompt asks every time; overwrite, skip, and rename apply immediately.",
            f"Current behavior: `{config.behavior.paste_conflict_action}`.",
        )
    if field_id == "logging.level":
        return (
            "Controls the minimum severity written to zivo's log file.",
            "This affects runtime diagnostics, not the status bar text in the UI.",
            f"Current behavior: `{config.logging.level}` and above are logged.",
        )
    if field_id == "file_search.max_results":
        current = (
            "unlimited"
            if config.file_search.max_results is None
            else str(config.file_search.max_results)
        )
        return (
            "Limits how many matches recursive file search can return in the command palette.",
            "Lower limits keep large searches responsive; unlimited returns every match found.",
            f"Current behavior: {current}.",
        )
    return ()


CONFIG_EDITOR_CATEGORIES: tuple[tuple[str, tuple[int, ...]], ...] = (
    ("External", (0, 1)),
    ("Display", (3, 8, 2, 4, 5, 6, 7, 9, 10, 14, 15)),
    ("Sorting", (11, 12, 13)),
    ("Behavior", (16, 17)),
    ("Logging", (18,)),
    ("File Search", (19,)),
)


def config_editor_visual_order() -> tuple[int, ...]:
    """Return field indices in visual display order."""

    result: list[int] = []
    for _header, field_indices in CONFIG_EDITOR_CATEGORIES:
        result.extend(field_indices)
    return tuple(result)


def move_config_cursor_visual(cursor_index: int, delta: int) -> int:
    """Move cursor by *delta* steps in visual order, returning the new field index."""

    order = config_editor_visual_order()
    try:
        pos = order.index(cursor_index)
    except ValueError:
        pos = 0
    new_pos = max(0, min(len(order) - 1, pos + delta))
    return order[new_pos]


def apply_config_to_runtime_state(state, config: AppConfig):
    return replace(
        state,
        show_hidden=config.display.show_hidden_files,
        show_help_bar=config.display.show_help_bar,
        sort=SortState(
            field=config.display.default_sort_field,
            descending=config.display.default_sort_descending,
            directories_first=config.display.directories_first,
        ),
        confirm_delete=config.behavior.confirm_delete,
        paste_conflict_action=config.behavior.paste_conflict_action,
    )


def format_config_field_value(field_index: int, config: AppConfig) -> str:
    field_id = config_editor_field_ids()[field_index]
    if field_id == "editor.command":
        return _format_editor_command_value(config.editor.command)
    if field_id == "terminal.launch_mode":
        return config.terminal.launch_mode
    if field_id == "display.show_hidden_files":
        return _format_bool(config.display.show_hidden_files)
    if field_id == "display.theme":
        return config.display.theme
    if field_id == "display.show_directory_sizes":
        return _format_bool(config.display.show_directory_sizes)
    if field_id == "display.enable_text_preview":
        return _format_bool(config.display.enable_text_preview)
    if field_id == "display.enable_image_preview":
        return _format_bool(config.display.enable_image_preview)
    if field_id == "display.enable_pdf_preview":
        return _format_bool(config.display.enable_pdf_preview)
    if field_id == "display.enable_office_preview":
        return _format_bool(config.display.enable_office_preview)
    if field_id == "display.preview_syntax_theme":
        return config.display.preview_syntax_theme
    if field_id == "display.preview_max_kib":
        return f"{config.display.preview_max_kib} KiB"
    if field_id == "display.show_help_bar":
        return _format_bool(config.display.show_help_bar)
    if field_id == "display.default_sort_field":
        return config.display.default_sort_field
    if field_id == "display.default_sort_descending":
        return _format_bool(config.display.default_sort_descending)
    if field_id == "display.directories_first":
        return _format_bool(config.display.directories_first)
    if field_id == "display.grep_preview_context_lines":
        return str(config.display.grep_preview_context_lines)
    if field_id == "display.split_terminal_position":
        return config.display.split_terminal_position
    if field_id == "behavior.confirm_delete":
        return _format_bool(config.behavior.confirm_delete)
    if field_id == "behavior.paste_conflict_action":
        return config.behavior.paste_conflict_action
    if field_id == "logging.level":
        return config.logging.level
    if field_id == "file_search.max_results":
        if config.file_search.max_results is None:
            return "unlimited"
        return str(config.file_search.max_results)
    return ""


def _format_bool(value: bool) -> str:
    return "true" if value else "false"


def _format_editor_command_value(command: str | None) -> str:
    if command is None:
        return "system default"
    if command in {"nvim", "vim", "nano", "hx", "micro", "emacs -nw"}:
        return command
    return "custom (raw config only)"
