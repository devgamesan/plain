"""Render the normalized application config back to TOML."""

from __future__ import annotations

from zivo.models import AppConfig

from .shared import HELP_BAR_FIELDS


def render_default_config() -> str:
    """Render the default config file contents."""

    return render_app_config(AppConfig())


def render_app_config(config: AppConfig) -> str:
    """Render the normalized application config as TOML."""

    sections = [
        render_terminal_section(config),
        render_editor_section(config),
        render_gui_editor_section(config),
        render_display_section(config),
        render_behavior_section(config),
        render_logging_section(config),
        render_bookmarks_section(config),
        render_help_bar_section(config),
        render_file_search_section(config),
        render_actions_section(config),
    ]
    return "\n\n".join(sections) + "\n"


def render_terminal_section(config: AppConfig) -> str:
    linux = render_command_array(config.terminal.linux)
    macos = render_command_array(config.terminal.macos)
    windows = render_command_array(config.terminal.windows)
    return (
        "[terminal]\n"
        "# Optional OS-specific terminal launch templates.\n"
        "# Use {path} for the working directory.\n"
        "# Examples:\n"
        '# linux = [\n'
        '#   "konsole --working-directory {path}",\n'
        '#   "gnome-terminal --working-directory={path}",\n'
        '# ]\n'
        '# macos = ["open -a Terminal {path}"]\n'
        '# windows = ["wt -d {path}"]\n'
        f"linux = [{linux}]\n"
        f"macos = [{macos}]\n"
        f"windows = [{windows}]"
    )


def render_editor_section(config: AppConfig) -> str:
    command = render_optional_toml_string(config.editor.command)
    return (
        "[editor]\n"
        "# Optional terminal editor command for `e`.\n"
        "# Use a shell-style command without the file path; zivo appends it automatically.\n"
        "# Examples:\n"
        '# command = "nvim -u NONE"\n'
        '# command = "emacs -nw"\n'
        f"command = {command}"
    )


def render_gui_editor_section(config: AppConfig) -> str:
    return (
        "[gui_editor]\n"
        "# Optional GUI editor templates for `O` and search-result Ctrl+o.\n"
        "# Use {path}, {line}, and {column}. Defaults target VS Code.\n"
        "# The config editor can switch between common presets;\n"
        "# custom templates are preserved here.\n"
        "# Examples: code, codium, cursor, subl, zed, idea, pycharm, webstorm, kate.\n"
        '# command = "code --goto {path}:{line}:{column}"\n'
        '# fallback_command = "code {path}"\n'
        f"command = {render_toml_string(config.gui_editor.command)}\n"
        f"fallback_command = {render_toml_string(config.gui_editor.fallback_command)}"
    )


def render_display_section(config: AppConfig) -> str:
    return (
        "[display]\n"
        f"show_hidden_files = {render_bool(config.display.show_hidden_files)}\n"
        f"show_directory_sizes = {render_bool(config.display.show_directory_sizes)}\n"
        f"enable_text_preview = {render_bool(config.display.enable_text_preview)}\n"
        f"enable_image_preview = {render_bool(config.display.enable_image_preview)}\n"
        f"enable_pdf_preview = {render_bool(config.display.enable_pdf_preview)}\n"
        f"enable_office_preview = {render_bool(config.display.enable_office_preview)}\n"
        f'theme = "{config.display.theme}"\n'
        f'preview_syntax_theme = "{config.display.preview_syntax_theme}"\n'
        f"preview_max_kib = {config.display.preview_max_kib}\n"
        f'default_sort_field = "{config.display.default_sort_field}"\n'
        f"default_sort_descending = {render_bool(config.display.default_sort_descending)}\n"
        f"directories_first = {render_bool(config.display.directories_first)}\n"
        f"grep_preview_context_lines = {config.display.grep_preview_context_lines}"
    )


def render_behavior_section(config: AppConfig) -> str:
    return (
        "[behavior]\n"
        f"confirm_delete = {render_bool(config.behavior.confirm_delete)}\n"
        f'paste_conflict_action = "{config.behavior.paste_conflict_action}"'
    )


def render_logging_section(config: AppConfig) -> str:
    path = render_optional_toml_string(config.logging.path)
    return (
        "[logging]\n"
        "# Optional file output for startup and unhandled exceptions.\n"
        "# Leave empty to write zivo.log next to config.toml.\n"
        f"enabled = {render_bool(config.logging.enabled)}\n"
        f'level = "{config.logging.level}"\n'
        f"path = {path}"
    )


def render_bookmarks_section(config: AppConfig) -> str:
    paths = render_command_array(config.bookmarks.paths)
    return (
        "[bookmarks]\n"
        "# Optional bookmarked directories shown in the command palette.\n"
        "# Use absolute paths.\n"
        "# Example:\n"
        '# paths = ["/home/user/src", "/home/user/docs"]\n'
        f"paths = [{paths}]"
    )


def render_help_bar_section(config: AppConfig) -> str:
    lines = [
        "[help_bar]",
        "# Optional custom help bar text for each UI mode.",
        "# Leave empty to use built-in defaults.",
        "# Example:",
        '# browsing = ["Custom help line 1", "Custom help line 2"]',
    ]
    for field in HELP_BAR_FIELDS:
        lines.append(f"{field} = {render_help_lines(getattr(config.help_bar, field))}")
    return "\n".join(lines)


def render_file_search_section(config: AppConfig) -> str:
    max_results = config.file_search.max_results
    if max_results is None:
        max_results_line = "# max_results = 1000  # Optional: limit file search results"
    else:
        max_results_line = f"max_results = {max_results}"
    return (
        "[file_search]\n"
        "# Optional file search behavior settings.\n"
        "# Leave max_results empty (null) for no limit (default).\n"
        "# Set to a positive integer to limit the number of results.\n"
        "# Example:\n"
        "# max_results = 1000\n"
        f"{max_results_line}"
    )


def render_actions_section(config: AppConfig) -> str:
    lines = [
        "[actions]",
        "# Optional command palette custom actions.",
        "# See docs/custom-actions.md for full syntax, examples, and safety notes.",
    ]
    if not config.actions.custom:
        lines.extend(
            [
                "#",
                "# [[actions.custom]]",
                '# name = "Optimize PNG"',
                '# command = ["oxipng", "-o", "4", "{file}"]',
                '# when = "single_file"',
                '# mode = "background"',
                '# extensions = ["png"]',
                "#",
                "# [[actions.custom]]",
                '# name = "Open lazygit"',
                '# command = ["lazygit"]',
                '# when = "always"',
                '# mode = "terminal"',
                '# cwd = "{cwd}"',
                "#",
                "# [[actions.custom]]",
                '# name = "Open lazygit in new terminal"',
                '# command = ["lazygit"]',
                '# when = "always"',
                '# mode = "terminal_window"',
                '# cwd = "{cwd}"',
            ]
        )
        return "\n".join(lines)

    for action in config.actions.custom:
        lines.extend(
            [
                "",
                "[[actions.custom]]",
                f"name = {render_toml_string(action.name)}",
                f"command = [{render_command_array(action.command)}]",
                f"when = {render_toml_string(action.when)}",
                f"mode = {render_toml_string(action.mode)}",
            ]
        )
        if action.cwd is not None:
            lines.append(f"cwd = {render_toml_string(action.cwd)}")
        if action.extensions:
            lines.append(f"extensions = [{render_command_array(action.extensions)}]")
    return "\n".join(lines)


def render_command_array(commands: tuple[str, ...]) -> str:
    return ", ".join(render_toml_string(command) for command in commands)


def render_bool(value: bool) -> str:
    return "true" if value else "false"


def render_toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def render_optional_toml_string(value: str | None) -> str:
    if value is None:
        return '""'
    return render_toml_string(value)


def render_help_lines(lines: tuple[str, ...]) -> str:
    if not lines:
        return "[]"
    rendered = ", ".join(render_toml_string(line) for line in lines)
    return f"[{rendered}]"
