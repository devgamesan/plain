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
CONFIG_EDITOR_COMMANDS = (None, "nvim", "vim", "nano", "hx", "micro", "emacs -nw")
CONFIG_SPLIT_TERMINAL_POSITIONS = ("bottom", "right", "overlay")


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
    if field_id == "display.show_preview":
        return replace(
            config,
            display=replace(
                config.display,
                show_preview=not config.display.show_preview,
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
        "display.show_hidden_files",
        "display.theme",
        "display.show_directory_sizes",
        "display.show_preview",
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
    )


def config_editor_labels() -> tuple[str, ...]:
    return (
        "Editor command",
        "Show hidden files",
        "Theme",
        "Show directory sizes",
        "Show preview",
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
    )


CONFIG_EDITOR_CATEGORIES: tuple[tuple[str, tuple[int, ...]], ...] = (
    ("External", (0,)),
    ("Display", (2, 5, 1, 3, 4, 6, 7, 11, 12)),
    ("Sorting", (8, 9, 10)),
    ("Behavior", (13, 14)),
    ("Logging", (15,)),
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
    if field_id == "display.show_hidden_files":
        return _format_bool(config.display.show_hidden_files)
    if field_id == "display.theme":
        return config.display.theme
    if field_id == "display.show_directory_sizes":
        return _format_bool(config.display.show_directory_sizes)
    if field_id == "display.show_preview":
        return _format_bool(config.display.show_preview)
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
    return ""


def _format_bool(value: bool) -> str:
    return "true" if value else "false"


def _format_editor_command_value(command: str | None) -> str:
    if command is None:
        return "system default"
    if command in {"nvim", "vim", "nano", "hx", "micro", "emacs -nw"}:
        return command
    return "custom (raw config only)"
