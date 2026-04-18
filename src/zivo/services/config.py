"""Load and validate the startup configuration file."""

from __future__ import annotations

import os
import platform
import shlex
import tomllib
from dataclasses import replace
from pathlib import Path
from typing import Callable, Protocol

from zivo.models import (
    AppConfig,
    BookmarkConfig,
    ConfigLoadResult,
    DisplayConfig,
    EditorConfig,
    HelpBarConfig,
    LoggingConfig,
    TerminalConfig,
)
from zivo.models.config import BehaviorConfig
from zivo.theme_support import (
    SUPPORTED_APP_THEME_DISPLAY,
    SUPPORTED_APP_THEMES,
    SUPPORTED_PREVIEW_SYNTAX_THEME_DISPLAY,
    SUPPORTED_PREVIEW_SYNTAX_THEMES,
)

SystemNameResolver = Callable[[], str]
EnvironmentVariableReader = Callable[[str], str | None]
HomeDirectoryResolver = Callable[[], Path]
ConfigPathResolver = Callable[[], Path]


class ConfigSaveService(Protocol):
    """Boundary for persisting the normalized application config."""

    def save(self, *, path: str, config: AppConfig) -> str: ...

_VALID_SORT_FIELDS = frozenset({"name", "modified", "size"})
_VALID_THEMES = frozenset(SUPPORTED_APP_THEMES)
_VALID_PREVIEW_SYNTAX_THEMES = frozenset(SUPPORTED_PREVIEW_SYNTAX_THEMES)
_VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})
_VALID_PASTE_ACTIONS = frozenset({"overwrite", "skip", "rename", "prompt"})
_VALID_SPLIT_TERMINAL_POSITIONS = frozenset({"bottom", "right", "overlay"})
_VALID_TERMINAL_EDITOR_NAMES = frozenset(
    {"emacs", "helix", "hx", "kak", "micro", "nano", "nvim", "vi", "vim"}
)
_VALIDATION_PATH = "/tmp/zivo"


def _validate_section_dict(
    section: object,
    section_name: str,
    warnings: list[str],
) -> dict[str, object] | None:
    """Return the section if it is a dict, otherwise None (with optional warning)."""
    if section is None:
        return None
    if not isinstance(section, dict):
        warnings.append(f"{section_name} must be a table; using defaults.")
        return None
    return section


class AppConfigLoader:
    """Resolve, create, parse, and validate the user configuration file."""

    def __init__(
        self,
        *,
        config_path_resolver: ConfigPathResolver | None = None,
    ) -> None:
        self._config_path_resolver = config_path_resolver or resolve_config_path

    def load(self) -> ConfigLoadResult:
        path = self._config_path_resolver()
        config = AppConfig()

        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(_render_default_config(), encoding="utf-8")
            return ConfigLoadResult(config=config, path=str(path), created=True)

        try:
            document = tomllib.loads(path.read_text(encoding="utf-8"))
        except OSError as error:
            return ConfigLoadResult(
                config=config,
                path=str(path),
                warnings=(f"Failed to read config: {error}",),
            )
        except tomllib.TOMLDecodeError as error:
            return ConfigLoadResult(
                config=config,
                path=str(path),
                warnings=(f"Failed to parse config.toml: {error}",),
            )

        warnings: list[str] = []
        if not isinstance(document, dict):
            return ConfigLoadResult(
                config=config,
                path=str(path),
                warnings=("Config root must be a TOML table; using defaults.",),
            )

        terminal = _load_terminal_config(document.get("terminal"), warnings)
        editor = _load_editor_config(document.get("editor"), warnings)
        display = _load_display_config(document.get("display"), warnings)
        behavior = _load_behavior_config(document.get("behavior"), warnings)
        logging = _load_logging_config(document.get("logging"), warnings)
        bookmarks = _load_bookmark_config(document.get("bookmarks"), warnings)
        help_bar = _load_help_bar_config(document.get("help_bar"), warnings)
        return ConfigLoadResult(
            config=AppConfig(
                terminal=terminal,
                editor=editor,
                display=display,
                behavior=behavior,
                logging=logging,
                bookmarks=bookmarks,
                help_bar=help_bar,
            ),
            path=str(path),
            warnings=tuple(warnings),
        )


def load_app_config(*, config_path_resolver: ConfigPathResolver | None = None) -> ConfigLoadResult:
    """Convenience wrapper for loading the user configuration."""

    return AppConfigLoader(config_path_resolver=config_path_resolver).load()


class LiveConfigSaveService:
    """Write the normalized application config to disk."""

    def save(self, *, path: str, config: AppConfig) -> str:
        config_path = Path(path).expanduser()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(render_app_config(config), encoding="utf-8")
        return str(config_path)


def resolve_config_path(
    *,
    system_name_resolver: SystemNameResolver = platform.system,
    environment_variable: EnvironmentVariableReader = os.environ.get,
    home_directory_resolver: HomeDirectoryResolver = Path.home,
) -> Path:
    """Return the platform-specific configuration file path."""

    system_name = system_name_resolver()
    home_directory = home_directory_resolver().expanduser()
    if system_name == "Linux":
        base_dir = environment_variable("XDG_CONFIG_HOME")
        if base_dir:
            return Path(base_dir).expanduser() / "zivo" / "config.toml"
        return home_directory / ".config" / "zivo" / "config.toml"
    if system_name == "Darwin":
        return home_directory / "Library" / "Application Support" / "zivo" / "config.toml"
    if system_name == "Windows":
        base_dir = environment_variable("APPDATA")
        if base_dir:
            return Path(base_dir).expanduser() / "zivo" / "config.toml"
        return home_directory / "AppData" / "Roaming" / "zivo" / "config.toml"
    raise OSError(f"Unsupported operating system for config path resolution: {system_name}")


def _load_terminal_config(section: object, warnings: list[str]) -> TerminalConfig:
    validated = _validate_section_dict(section, "terminal", warnings)
    if validated is None:
        return TerminalConfig()
    return TerminalConfig(
        linux=_load_command_templates(validated, "linux", warnings),
        macos=_load_command_templates(validated, "macos", warnings),
        windows=_load_command_templates(validated, "windows", warnings),
    )


def _load_display_config(section: object, warnings: list[str]) -> DisplayConfig:
    config = DisplayConfig()
    validated = _validate_section_dict(section, "display", warnings)
    if validated is None:
        return config

    config = replace(
        config,
        show_hidden_files=_read_bool(
            validated,
            key="show_hidden_files",
            default=config.show_hidden_files,
            warnings=warnings,
            section_name="display",
        ),
        show_directory_sizes=_read_bool(
            validated,
            key="show_directory_sizes",
            default=config.show_directory_sizes,
            warnings=warnings,
            section_name="display",
        ),
        show_preview=_read_bool(
            validated,
            key="show_preview",
            default=config.show_preview,
            warnings=warnings,
            section_name="display",
        ),
        default_sort_descending=_read_bool(
            validated,
            key="default_sort_descending",
            default=config.default_sort_descending,
            warnings=warnings,
            section_name="display",
        ),
        directories_first=_read_bool(
            validated,
            key="directories_first",
            default=config.directories_first,
            warnings=warnings,
            section_name="display",
        ),
        grep_preview_context_lines=_read_int(
            validated,
            key="grep_preview_context_lines",
            default=config.grep_preview_context_lines,
            minimum=0,
            warnings=warnings,
            section_name="display",
        ),
    )
    config = replace(
        config,
        theme=_read_enum(
            validated,
            key="theme",
            default=config.theme,
            valid_values=_VALID_THEMES,
            valid_display=SUPPORTED_APP_THEME_DISPLAY,
            section_name="display",
            warnings=warnings,
        ),
        preview_syntax_theme=_read_enum(
            validated,
            key="preview_syntax_theme",
            default=config.preview_syntax_theme,
            valid_values=_VALID_PREVIEW_SYNTAX_THEMES,
            valid_display=SUPPORTED_PREVIEW_SYNTAX_THEME_DISPLAY,
            section_name="display",
            warnings=warnings,
        ),
        default_sort_field=_read_enum(
            validated,
            key="default_sort_field",
            default=config.default_sort_field,
            valid_values=_VALID_SORT_FIELDS,
            valid_display="name, modified, size",
            section_name="display",
            warnings=warnings,
        ),
        split_terminal_position=_read_enum(
            validated,
            key="split_terminal_position",
            default=config.split_terminal_position,
            valid_values=_VALID_SPLIT_TERMINAL_POSITIONS,
            valid_display="bottom, right, overlay",
            section_name="display",
            warnings=warnings,
        ),
    )
    return config


def _load_editor_config(section: object, warnings: list[str]) -> EditorConfig:
    validated = _validate_section_dict(section, "editor", warnings)
    if validated is None:
        return EditorConfig()

    command = validated.get("command")
    if command is None:
        return EditorConfig()
    if not isinstance(command, str) or not command.strip():
        warnings.append("editor.command must be a non-empty string; using default.")
        return EditorConfig()

    try:
        parsed = tuple(shlex.split(command))
    except ValueError as error:
        warnings.append(
            f"editor.command is not a valid shell-style command: {error}; using default."
        )
        return EditorConfig()

    if not parsed:
        warnings.append("editor.command did not produce an executable command; using default.")
        return EditorConfig()
    if Path(parsed[0]).name.casefold() not in _VALID_TERMINAL_EDITOR_NAMES:
        warnings.append(
            "editor.command must target a supported terminal editor; using default."
        )
        return EditorConfig()
    return EditorConfig(command=command)


def _load_behavior_config(section: object, warnings: list[str]) -> BehaviorConfig:
    config = BehaviorConfig()
    validated = _validate_section_dict(section, "behavior", warnings)
    if validated is None:
        return config

    config = replace(
        config,
        confirm_delete=_read_bool(
            validated,
            key="confirm_delete",
            default=config.confirm_delete,
            warnings=warnings,
            section_name="behavior",
        ),
        paste_conflict_action=_read_enum(
            validated,
            key="paste_conflict_action",
            default=config.paste_conflict_action,
            valid_values=_VALID_PASTE_ACTIONS,
            valid_display="overwrite, skip, rename, prompt",
            section_name="behavior",
            warnings=warnings,
        ),
    )
    return config


def _load_bookmark_config(section: object, warnings: list[str]) -> BookmarkConfig:
    validated = _validate_section_dict(section, "bookmarks", warnings)
    if validated is None:
        return BookmarkConfig()

    raw_paths = validated.get("paths")
    if raw_paths is None:
        return BookmarkConfig()
    if not isinstance(raw_paths, list):
        warnings.append("bookmarks.paths must be an array of absolute path strings; using default.")
        return BookmarkConfig()

    paths: list[str] = []
    for index, item in enumerate(raw_paths):
        field_name = f"bookmarks.paths[{index}]"
        if not isinstance(item, str) or not item.strip():
            warnings.append(f"{field_name} must be a non-empty absolute path string; ignoring it.")
            continue
        expanded = Path(item).expanduser()
        if not expanded.is_absolute():
            warnings.append(f"{field_name} must be an absolute path; ignoring it.")
            continue
        normalized = str(expanded.resolve(strict=False))
        paths.append(normalized)

    return BookmarkConfig(paths=tuple(dict.fromkeys(paths)))


def _load_help_bar_config(section: object, warnings: list[str]) -> HelpBarConfig:
    validated = _validate_section_dict(section, "help_bar", warnings)
    if validated is None:
        return HelpBarConfig()

    return HelpBarConfig(
        browsing=_load_help_lines(validated, "browsing", warnings),
        filter=_load_help_lines(validated, "filter", warnings),
        rename=_load_help_lines(validated, "rename", warnings),
        create=_load_help_lines(validated, "create", warnings),
        extract=_load_help_lines(validated, "extract", warnings),
        zip=_load_help_lines(validated, "zip", warnings),
        palette=_load_help_lines(validated, "palette", warnings),
        palette_file_search=_load_help_lines(validated, "palette_file_search", warnings),
        palette_grep_search=_load_help_lines(validated, "palette_grep_search", warnings),
        palette_history=_load_help_lines(validated, "palette_history", warnings),
        palette_bookmarks=_load_help_lines(validated, "palette_bookmarks", warnings),
        palette_go_to_path=_load_help_lines(validated, "palette_go_to_path", warnings),
        shell=_load_help_lines(validated, "shell", warnings),
        config=_load_help_lines(validated, "config", warnings),
        confirm_delete=_load_help_lines(validated, "confirm_delete", warnings),
        detail=_load_help_lines(validated, "detail", warnings),
        busy=_load_help_lines(validated, "busy", warnings),
        split_terminal=_load_help_lines(validated, "split_terminal", warnings),
    )


def _load_help_lines(section: dict[str, object], key: str, warnings: list[str]) -> tuple[str, ...]:
    raw_value = section.get(key)
    if raw_value is None:
        return ()
    if not isinstance(raw_value, list):
        warnings.append(f"help_bar.{key} must be an array of strings; ignoring it.")
        return ()

    lines: list[str] = []
    for index, item in enumerate(raw_value):
        field_name = f"help_bar.{key}[{index}]"
        if not isinstance(item, str):
            warnings.append(f"{field_name} must be a string; ignoring it.")
            continue
        if item.strip():
            lines.append(item.strip())

    return tuple(lines)


def _load_logging_config(section: object, warnings: list[str]) -> LoggingConfig:
    config = LoggingConfig()
    validated = _validate_section_dict(section, "logging", warnings)
    if validated is None:
        return config

    config = replace(
        config,
        enabled=_read_bool(
            validated,
            key="enabled",
            default=config.enabled,
            warnings=warnings,
            section_name="logging",
        ),
        level=_read_enum(
            validated,
            key="level",
            default=config.level,
            valid_values=_VALID_LOG_LEVELS,
            valid_display="DEBUG, INFO, WARNING, ERROR, CRITICAL",
            section_name="logging",
            warnings=warnings,
        ),
    )

    path = validated.get("path", config.path)
    if path is None:
        return config
    if not isinstance(path, str):
        warnings.append("logging.path must be a string; using default.")
        return config
    normalized_path = path.strip() or None
    return replace(config, path=normalized_path)


def _load_command_templates(
    section: dict[str, object],
    key: str,
    warnings: list[str],
) -> tuple[str, ...]:
    raw_value = section.get(key)
    if raw_value is None:
        return ()
    if not isinstance(raw_value, list):
        warnings.append(f"terminal.{key} must be an array of strings; ignoring it.")
        return ()

    commands: list[str] = []
    for index, item in enumerate(raw_value):
        field_name = f"terminal.{key}[{index}]"
        if not isinstance(item, str) or not item.strip():
            warnings.append(f"{field_name} must be a non-empty string; ignoring it.")
            continue
        try:
            rendered = item.format(path=_VALIDATION_PATH)
        except (IndexError, KeyError, ValueError) as error:
            warnings.append(f"{field_name} has an invalid placeholder: {error}; ignoring it.")
            continue
        try:
            parsed = tuple(shlex.split(rendered))
        except ValueError as error:
            warnings.append(
                f"{field_name} is not a valid shell-style command: {error}; ignoring it."
            )
            continue
        if not parsed:
            warnings.append(f"{field_name} did not produce an executable command; ignoring it.")
            continue
        commands.append(item)
    return tuple(commands)


def _read_bool(
    section: dict[str, object],
    *,
    key: str,
    default: bool,
    warnings: list[str],
    section_name: str,
) -> bool:
    value = section.get(key, default)
    if isinstance(value, bool):
        return value
    if key in section:
        warnings.append(f"{section_name}.{key} must be true or false; using default.")
    return default


def _read_int(
    section: dict[str, object],
    *,
    key: str,
    default: int,
    minimum: int = 0,
    warnings: list[str],
    section_name: str,
) -> int:
    value = section.get(key, default)
    if isinstance(value, int) and not isinstance(value, bool):
        if value >= minimum:
            return value
        if key in section:
            warnings.append(
                f"{section_name}.{key} must be >= {minimum}; using default."
            )
        return default
    if key in section:
        warnings.append(f"{section_name}.{key} must be an integer; using default.")
    return default


def _read_enum(
    section: dict[str, object],
    *,
    key: str,
    default: str,
    valid_values: frozenset[str],
    valid_display: str,
    section_name: str,
    warnings: list[str],
) -> str:
    value = section.get(key, default)
    if isinstance(value, str) and value in valid_values:
        return value
    if key in section:
        warnings.append(f"{section_name}.{key} must be one of {valid_display}; using default.")
    return default


def _render_default_config() -> str:
    return render_app_config(AppConfig())


def _render_terminal_section(config: AppConfig) -> str:
    linux = _render_command_array(config.terminal.linux)
    macos = _render_command_array(config.terminal.macos)
    windows = _render_command_array(config.terminal.windows)
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


def _render_editor_section(config: AppConfig) -> str:
    command = _render_optional_toml_string(config.editor.command)
    return (
        "[editor]\n"
        "# Optional terminal editor command for `e`.\n"
        "# Use a shell-style command without the file path; zivo appends it automatically.\n"
        "# Examples:\n"
        '# command = "nvim -u NONE"\n'
        '# command = "emacs -nw"\n'
        f"command = {command}"
    )


def _render_display_section(config: AppConfig) -> str:
    return (
        "[display]\n"
        f"show_hidden_files = {_render_bool(config.display.show_hidden_files)}\n"
        f"show_directory_sizes = {_render_bool(config.display.show_directory_sizes)}\n"
        f"show_preview = {_render_bool(config.display.show_preview)}\n"
        f'theme = "{config.display.theme}"\n'
        f'preview_syntax_theme = "{config.display.preview_syntax_theme}"\n'
        f'default_sort_field = "{config.display.default_sort_field}"\n'
        f"default_sort_descending = {_render_bool(config.display.default_sort_descending)}\n"
        f"directories_first = {_render_bool(config.display.directories_first)}\n"
        f"grep_preview_context_lines = {config.display.grep_preview_context_lines}\n"
        f'split_terminal_position = "{config.display.split_terminal_position}"'
    )


def _render_behavior_section(config: AppConfig) -> str:
    return (
        "[behavior]\n"
        f"confirm_delete = {_render_bool(config.behavior.confirm_delete)}\n"
        f'paste_conflict_action = "{config.behavior.paste_conflict_action}"'
    )


def _render_logging_section(config: AppConfig) -> str:
    path = _render_optional_toml_string(config.logging.path)
    return (
        "[logging]\n"
        "# Optional file output for startup and unhandled exceptions.\n"
        "# Leave empty to write zivo.log next to config.toml.\n"
        f"enabled = {_render_bool(config.logging.enabled)}\n"
        f'level = "{config.logging.level}"\n'
        f"path = {path}"
    )


def _render_bookmarks_section(config: AppConfig) -> str:
    paths = _render_command_array(config.bookmarks.paths)
    return (
        "[bookmarks]\n"
        "# Optional bookmarked directories shown in the command palette.\n"
        "# Use absolute paths.\n"
        "# Example:\n"
        '# paths = ["/home/user/src", "/home/user/docs"]\n'
        f"paths = [{paths}]"
    )


_HELP_BAR_FIELDS = (
    "browsing",
    "filter",
    "rename",
    "create",
    "extract",
    "zip",
    "palette",
    "palette_file_search",
    "palette_grep_search",
    "palette_history",
    "palette_bookmarks",
    "palette_go_to_path",
    "shell",
    "config",
    "confirm_delete",
    "detail",
    "busy",
    "split_terminal",
)


def _render_help_bar_section(config: AppConfig) -> str:
    lines = [
        "[help_bar]",
        "# Optional custom help bar text for each UI mode.",
        "# Leave empty to use built-in defaults.",
        "# Example:",
        '# browsing = ["Custom help line 1", "Custom help line 2"]',
    ]
    for field in _HELP_BAR_FIELDS:
        lines.append(f"{field} = {_render_help_lines(getattr(config.help_bar, field))}")
    return "\n".join(lines)


def render_app_config(config: AppConfig) -> str:
    sections = [
        _render_terminal_section(config),
        _render_editor_section(config),
        _render_display_section(config),
        _render_behavior_section(config),
        _render_logging_section(config),
        _render_bookmarks_section(config),
        _render_help_bar_section(config),
    ]
    return "\n\n".join(sections) + "\n"


def _render_command_array(commands: tuple[str, ...]) -> str:
    return ", ".join(_render_toml_string(command) for command in commands)


def _render_bool(value: bool) -> str:
    return "true" if value else "false"


def _render_toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _render_optional_toml_string(value: str | None) -> str:
    if value is None:
        return '""'
    return _render_toml_string(value)


def _render_help_lines(lines: tuple[str, ...]) -> str:
    if not lines:
        return "[]"
    rendered = ", ".join(_render_toml_string(line) for line in lines)
    return f"[{rendered}]"
