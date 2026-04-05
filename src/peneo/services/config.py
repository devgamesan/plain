"""Load and validate the startup configuration file."""

from __future__ import annotations

import os
import platform
import shlex
import tomllib
from dataclasses import replace
from pathlib import Path
from textwrap import dedent
from typing import Callable, Protocol

from peneo.models import (
    AppConfig,
    BookmarkConfig,
    ConfigLoadResult,
    DisplayConfig,
    EditorConfig,
    HelpBarConfig,
    LoggingConfig,
    TerminalConfig,
)
from peneo.models.config import BehaviorConfig

SystemNameResolver = Callable[[], str]
EnvironmentVariableReader = Callable[[str], str | None]
HomeDirectoryResolver = Callable[[], Path]
ConfigPathResolver = Callable[[], Path]


class ConfigSaveService(Protocol):
    """Boundary for persisting the normalized application config."""

    def save(self, *, path: str, config: AppConfig) -> str: ...

_VALID_SORT_FIELDS = frozenset({"name", "modified", "size"})
_VALID_THEMES = frozenset({"textual-dark", "textual-light"})
_VALID_PASTE_ACTIONS = frozenset({"overwrite", "skip", "rename", "prompt"})
_VALID_TERMINAL_EDITOR_NAMES = frozenset(
    {"emacs", "helix", "hx", "kak", "micro", "nano", "nvim", "vi", "vim"}
)
_VALIDATION_PATH = "/tmp/peneo"


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
            return Path(base_dir).expanduser() / "peneo" / "config.toml"
        return home_directory / ".config" / "peneo" / "config.toml"
    if system_name == "Darwin":
        return home_directory / "Library" / "Application Support" / "peneo" / "config.toml"
    if system_name == "Windows":
        base_dir = environment_variable("APPDATA")
        if base_dir:
            return Path(base_dir).expanduser() / "peneo" / "config.toml"
        return home_directory / "AppData" / "Roaming" / "peneo" / "config.toml"
    raise OSError(f"Unsupported operating system for config path resolution: {system_name}")


def _load_terminal_config(section: object, warnings: list[str]) -> TerminalConfig:
    if section is None:
        return TerminalConfig()
    if not isinstance(section, dict):
        warnings.append("terminal must be a table; using defaults.")
        return TerminalConfig()
    return TerminalConfig(
        linux=_load_command_templates(section, "linux", warnings),
        macos=_load_command_templates(section, "macos", warnings),
        windows=_load_command_templates(section, "windows", warnings),
    )


def _load_display_config(section: object, warnings: list[str]) -> DisplayConfig:
    config = DisplayConfig()
    if section is None:
        return config
    if not isinstance(section, dict):
        warnings.append("display must be a table; using defaults.")
        return config

    config = replace(
        config,
        show_hidden_files=_read_bool(
            section,
            key="show_hidden_files",
            default=config.show_hidden_files,
            warnings=warnings,
            section_name="display",
        ),
        show_directory_sizes=_read_bool(
            section,
            key="show_directory_sizes",
            default=config.show_directory_sizes,
            warnings=warnings,
            section_name="display",
        ),
        default_sort_descending=_read_bool(
            section,
            key="default_sort_descending",
            default=config.default_sort_descending,
            warnings=warnings,
            section_name="display",
        ),
        directories_first=_read_bool(
            section,
            key="directories_first",
            default=config.directories_first,
            warnings=warnings,
            section_name="display",
        ),
    )
    theme = section.get("theme", config.theme)
    if isinstance(theme, str) and theme in _VALID_THEMES:
        config = replace(config, theme=theme)
    elif "theme" in section:
        warnings.append(
            "display.theme must be one of textual-dark, textual-light; using default."
        )

    sort_field = section.get("default_sort_field", config.default_sort_field)
    if isinstance(sort_field, str) and sort_field in _VALID_SORT_FIELDS:
        return replace(config, default_sort_field=sort_field)

    if "default_sort_field" in section:
        warnings.append(
            "display.default_sort_field must be one of name, modified, size; using default."
        )
    return config


def _load_editor_config(section: object, warnings: list[str]) -> EditorConfig:
    if section is None:
        return EditorConfig()
    if not isinstance(section, dict):
        warnings.append("editor must be a table; using defaults.")
        return EditorConfig()

    command = section.get("command")
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
    if section is None:
        return config
    if not isinstance(section, dict):
        warnings.append("behavior must be a table; using defaults.")
        return config

    config = replace(
        config,
        confirm_delete=_read_bool(
            section,
            key="confirm_delete",
            default=config.confirm_delete,
            warnings=warnings,
            section_name="behavior",
        ),
    )
    paste_action = section.get("paste_conflict_action", config.paste_conflict_action)
    if isinstance(paste_action, str) and paste_action in _VALID_PASTE_ACTIONS:
        return replace(config, paste_conflict_action=paste_action)

    if "paste_conflict_action" in section:
        warnings.append(
            "behavior.paste_conflict_action must be one of "
            "overwrite, skip, rename, prompt; using default."
        )
    return config


def _load_bookmark_config(section: object, warnings: list[str]) -> BookmarkConfig:
    if section is None:
        return BookmarkConfig()
    if not isinstance(section, dict):
        warnings.append("bookmarks must be a table; using defaults.")
        return BookmarkConfig()

    raw_paths = section.get("paths")
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
    if section is None:
        return HelpBarConfig()
    if not isinstance(section, dict):
        warnings.append("help_bar must be a table; using defaults.")
        return HelpBarConfig()

    return HelpBarConfig(
        browsing=_load_help_lines(section, "browsing", warnings),
        filter=_load_help_lines(section, "filter", warnings),
        rename=_load_help_lines(section, "rename", warnings),
        create=_load_help_lines(section, "create", warnings),
        extract=_load_help_lines(section, "extract", warnings),
        zip=_load_help_lines(section, "zip", warnings),
        palette=_load_help_lines(section, "palette", warnings),
        palette_file_search=_load_help_lines(section, "palette_file_search", warnings),
        palette_grep_search=_load_help_lines(section, "palette_grep_search", warnings),
        palette_history=_load_help_lines(section, "palette_history", warnings),
        palette_bookmarks=_load_help_lines(section, "palette_bookmarks", warnings),
        palette_go_to_path=_load_help_lines(section, "palette_go_to_path", warnings),
        shell=_load_help_lines(section, "shell", warnings),
        config=_load_help_lines(section, "config", warnings),
        confirm_delete=_load_help_lines(section, "confirm_delete", warnings),
        detail=_load_help_lines(section, "detail", warnings),
        busy=_load_help_lines(section, "busy", warnings),
        split_terminal=_load_help_lines(section, "split_terminal", warnings),
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
    if section is None:
        return config
    if not isinstance(section, dict):
        warnings.append("logging must be a table; using defaults.")
        return config

    config = replace(
        config,
        enabled=_read_bool(
            section,
            key="enabled",
            default=config.enabled,
            warnings=warnings,
            section_name="logging",
        ),
    )

    path = section.get("path", config.path)
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


def _render_default_config() -> str:
    return render_app_config(AppConfig())


def render_app_config(config: AppConfig) -> str:
    return dedent(
        """
        [terminal]
        # Optional OS-specific terminal launch templates.
        # Use {{path}} for the working directory.
        # Examples:
        # linux = [
        #   "konsole --working-directory {{path}}",
        #   "gnome-terminal --working-directory={{path}}",
        # ]
        # macos = ["open -a Terminal {{path}}"]
        # windows = ["wt -d {{path}}"]
        linux = [{linux}]
        macos = [{macos}]
        windows = [{windows}]

        [editor]
        # Optional terminal editor command for `e`.
        # Use a shell-style command without the file path; Peneo appends it automatically.
        # Examples:
        # command = "nvim -u NONE"
        # command = "emacs -nw"
        command = {editor_command}

        [display]
        show_hidden_files = {show_hidden_files}
        show_directory_sizes = {show_directory_sizes}
        theme = "{theme}"
        default_sort_field = "{default_sort_field}"
        default_sort_descending = {default_sort_descending}
        directories_first = {directories_first}

        [behavior]
        confirm_delete = {confirm_delete}
        paste_conflict_action = "{paste_conflict_action}"

        [logging]
        # Optional file output for startup and unhandled exceptions.
        # Leave empty to write peneo.log next to config.toml.
        enabled = {logging_enabled}
        path = {logging_path}

        [bookmarks]
        # Optional bookmarked directories shown in the command palette.
        # Use absolute paths.
        # Example:
        # paths = ["/home/user/src", "/home/user/docs"]
        paths = [{bookmark_paths}]

        [help_bar]
        # Optional custom help bar text for each UI mode.
        # Leave empty to use built-in defaults.
        # Example:
        # browsing = ["Custom help line 1", "Custom help line 2"]
        browsing = {help_bar_browsing}
        filter = {help_bar_filter}
        rename = {help_bar_rename}
        create = {help_bar_create}
        extract = {help_bar_extract}
        zip = {help_bar_zip}
        palette = {help_bar_palette}
        palette_file_search = {help_bar_palette_file_search}
        palette_grep_search = {help_bar_palette_grep_search}
        palette_history = {help_bar_palette_history}
        palette_bookmarks = {help_bar_palette_bookmarks}
        palette_go_to_path = {help_bar_palette_go_to_path}
        shell = {help_bar_shell}
        config = {help_bar_config}
        confirm_delete = {help_bar_confirm_delete}
        detail = {help_bar_detail}
        busy = {help_bar_busy}
        split_terminal = {help_bar_split_terminal}
        """
    ).format(
        linux=_render_command_array(config.terminal.linux),
        macos=_render_command_array(config.terminal.macos),
        windows=_render_command_array(config.terminal.windows),
        editor_command=_render_optional_toml_string(config.editor.command),
        show_hidden_files=_render_bool(config.display.show_hidden_files),
        show_directory_sizes=_render_bool(config.display.show_directory_sizes),
        theme=config.display.theme,
        default_sort_field=config.display.default_sort_field,
        default_sort_descending=_render_bool(config.display.default_sort_descending),
        directories_first=_render_bool(config.display.directories_first),
        confirm_delete=_render_bool(config.behavior.confirm_delete),
        paste_conflict_action=config.behavior.paste_conflict_action,
        logging_enabled=_render_bool(config.logging.enabled),
        logging_path=_render_optional_toml_string(config.logging.path),
        bookmark_paths=_render_command_array(config.bookmarks.paths),
        help_bar_browsing=_render_help_lines(config.help_bar.browsing),
        help_bar_filter=_render_help_lines(config.help_bar.filter),
        help_bar_rename=_render_help_lines(config.help_bar.rename),
        help_bar_create=_render_help_lines(config.help_bar.create),
        help_bar_extract=_render_help_lines(config.help_bar.extract),
        help_bar_zip=_render_help_lines(config.help_bar.zip),
        help_bar_palette=_render_help_lines(config.help_bar.palette),
        help_bar_palette_file_search=_render_help_lines(config.help_bar.palette_file_search),
        help_bar_palette_grep_search=_render_help_lines(config.help_bar.palette_grep_search),
        help_bar_palette_history=_render_help_lines(config.help_bar.palette_history),
        help_bar_palette_bookmarks=_render_help_lines(config.help_bar.palette_bookmarks),
        help_bar_palette_go_to_path=_render_help_lines(config.help_bar.palette_go_to_path),
        help_bar_shell=_render_help_lines(config.help_bar.shell),
        help_bar_config=_render_help_lines(config.help_bar.config),
        help_bar_confirm_delete=_render_help_lines(config.help_bar.confirm_delete),
        help_bar_detail=_render_help_lines(config.help_bar.detail),
        help_bar_busy=_render_help_lines(config.help_bar.busy),
        help_bar_split_terminal=_render_help_lines(config.help_bar.split_terminal),
    ).lstrip()


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
