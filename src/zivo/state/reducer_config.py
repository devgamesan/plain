"""Shared config editor definitions and helpers."""

from dataclasses import replace

from zivo.models import AppConfig, GuiEditorConfig
from zivo.models.config_editor import CONFIG_EDITOR_FIELDS
from zivo.theme_support import SUPPORTED_APP_THEMES, SUPPORTED_PREVIEW_SYNTAX_THEMES

from .models import SortState

CONFIG_SORT_FIELDS = ("name", "modified", "size")
CONFIG_THEMES = SUPPORTED_APP_THEMES
CONFIG_PREVIEW_SYNTAX_THEMES = SUPPORTED_PREVIEW_SYNTAX_THEMES
CONFIG_EDITOR_COMMANDS = (None, "nvim", "vim", "nano", "hx", "micro", "emacs -nw", "edit")
CONFIG_GUI_EDITOR_PRESETS: tuple[tuple[str, GuiEditorConfig], ...] = (
    (
        "VS Code",
        GuiEditorConfig(
            command="code --goto {path}:{line}:{column}",
            fallback_command="code {path}",
        ),
    ),
    (
        "VSCodium",
        GuiEditorConfig(
            command="codium --goto {path}:{line}:{column}",
            fallback_command="codium {path}",
        ),
    ),
    (
        "Cursor",
        GuiEditorConfig(
            command="cursor --goto {path}:{line}:{column}",
            fallback_command="cursor {path}",
        ),
    ),
    (
        "Sublime Text",
        GuiEditorConfig(
            command="subl {path}:{line}:{column}",
            fallback_command="subl {path}",
        ),
    ),
    (
        "Zed",
        GuiEditorConfig(
            command="zed {path}:{line}:{column}",
            fallback_command="zed {path}",
        ),
    ),
    (
        "JetBrains IDEA",
        GuiEditorConfig(
            command="idea --line {line} {path}",
            fallback_command="idea {path}",
        ),
    ),
    (
        "PyCharm",
        GuiEditorConfig(
            command="pycharm --line {line} {path}",
            fallback_command="pycharm {path}",
        ),
    ),
    (
        "WebStorm",
        GuiEditorConfig(
            command="webstorm --line {line} {path}",
            fallback_command="webstorm {path}",
        ),
    ),
    (
        "Kate",
        GuiEditorConfig(
            command="kate --line {line} --column {column} {path}",
            fallback_command="kate {path}",
        ),
    ),
)


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
    if field_id == "gui_editor.preset":
        return replace(config, gui_editor=cycle_gui_editor_preset(config.gui_editor, delta))
    if field_id == "display.show_hidden_files":
        return replace(
            config,
            display=replace(
                config.display,
                show_hidden_files=not config.display.show_hidden_files,
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
    if field_id == "behavior.confirm_delete":
        return replace(
            config,
            behavior=replace(
                config.behavior,
                confirm_delete=not config.behavior.confirm_delete,
            ),
        )
    return config


def cycle_choice(options: tuple[str, ...], current: str, delta: int) -> str:
    current_index = options.index(current) if current in options else 0
    return options[(current_index + delta) % len(options)]


def cycle_editor_command(current: str | None, delta: int) -> str | None:
    if current in CONFIG_EDITOR_COMMANDS:
        current_index = CONFIG_EDITOR_COMMANDS.index(current)
    else:
        current_index = len(CONFIG_EDITOR_COMMANDS)
    return CONFIG_EDITOR_COMMANDS[(current_index + delta) % len(CONFIG_EDITOR_COMMANDS)]


def cycle_gui_editor_preset(current: GuiEditorConfig, delta: int) -> GuiEditorConfig:
    current_index = _gui_editor_preset_index(current)
    if current_index is None:
        selected_index = 0 if delta >= 0 else len(CONFIG_GUI_EDITOR_PRESETS) - 1
    else:
        selected_index = (current_index + delta) % len(CONFIG_GUI_EDITOR_PRESETS)
    return CONFIG_GUI_EDITOR_PRESETS[selected_index][1]


def config_editor_field_ids() -> tuple[str, ...]:
    return tuple(field.field_id for field in CONFIG_EDITOR_FIELDS)


def config_editor_labels() -> tuple[str, ...]:
    return tuple(field.label for field in CONFIG_EDITOR_FIELDS)


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
    if field_id == "gui_editor.preset":
        lines = [
            "How GUI editor launches are built for `O` and search-result Ctrl+o.",
            "Choosing a preset updates both positioned and fallback GUI editor templates.",
        ]
        preset_name = _gui_editor_preset_name(config.gui_editor)
        if preset_name is None:
            lines.append("Current behavior: custom raw GUI editor templates are preserved.")
        else:
            lines.append(f"Current behavior: `{preset_name}` is selected.")
        lines.append(
            "Custom GUI editor templates can only be edited in the raw config file with `e`."
        )
        return tuple(lines)
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
    if field_id == "display.default_sort_field":
        return (
            "Sets the default sort field used when a directory is first loaded.",
            "The 'name' field sorts entries in natural order (e.g. file2 before file10).",
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
    if field_id == "behavior.confirm_delete":
        return (
            "Controls whether delete and move-to-trash actions ask for confirmation first.",
            "Current behavior: confirmations are "
            f"{'enabled' if config.behavior.confirm_delete else 'disabled'} by default.",
        )
    return ()


CONFIG_EDITOR_CATEGORIES: tuple[tuple[str, tuple[int, ...]], ...] = tuple(
    (
        category,
        tuple(
            index
            for index, field in enumerate(CONFIG_EDITOR_FIELDS)
            if field.category == category
        ),
    )
    for category in dict.fromkeys(field.category for field in CONFIG_EDITOR_FIELDS)
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
        confirm_exit=config.behavior.confirm_exit,
        paste_conflict_action=config.behavior.paste_conflict_action,
    )


def format_config_field_value(field_index: int, config: AppConfig) -> str:
    field_id = config_editor_field_ids()[field_index]
    if field_id == "editor.command":
        return _format_editor_command_value(config.editor.command)
    if field_id == "gui_editor.preset":
        return _format_gui_editor_value(config.gui_editor)
    if field_id == "terminal.launch_mode":
        return config.terminal.launch_mode
    if field_id == "display.show_hidden_files":
        return _format_bool(config.display.show_hidden_files)
    if field_id == "display.theme":
        return config.display.theme
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
    if field_id == "display.default_sort_field":
        return config.display.default_sort_field
    if field_id == "display.default_sort_descending":
        return _format_bool(config.display.default_sort_descending)
    if field_id == "display.directories_first":
        return _format_bool(config.display.directories_first)
    if field_id == "behavior.confirm_delete":
        return _format_bool(config.behavior.confirm_delete)
    return ""


def _format_bool(value: bool) -> str:
    return "true" if value else "false"


def _format_editor_command_value(command: str | None) -> str:
    if command is None:
        return "system default"
    if command in {"nvim", "vim", "nano", "hx", "micro", "emacs -nw", "edit"}:
        return command
    return "custom (raw config only)"


def _format_gui_editor_value(config: GuiEditorConfig) -> str:
    preset_name = _gui_editor_preset_name(config)
    if preset_name is None:
        return "custom (raw config only)"
    return preset_name


def _gui_editor_preset_name(config: GuiEditorConfig) -> str | None:
    current_index = _gui_editor_preset_index(config)
    if current_index is None:
        return None
    return CONFIG_GUI_EDITOR_PRESETS[current_index][0]


def _gui_editor_preset_index(config: GuiEditorConfig) -> int | None:
    for index, (_name, preset_config) in enumerate(CONFIG_GUI_EDITOR_PRESETS):
        if config == preset_config:
            return index
    return None
