"""Load and validate the startup configuration file."""

from __future__ import annotations

import shlex
import tomllib
from dataclasses import replace
from pathlib import Path

from zivo.models import (
    AppConfig,
    BookmarkConfig,
    ConfigLoadResult,
    DisplayConfig,
    EditorConfig,
    FileSearchConfig,
    HelpBarConfig,
    LoggingConfig,
    TerminalConfig,
)
from zivo.models.config import BehaviorConfig
from zivo.theme_support import (
    SUPPORTED_APP_THEME_DISPLAY,
    SUPPORTED_PREVIEW_SYNTAX_THEME_DISPLAY,
)

from .path import ConfigPathResolver, resolve_config_path
from .render import render_default_config
from .schema import read_bool, read_enum, read_int, validate_section_dict
from .shared import (
    HELP_BAR_FIELDS,
    VALID_LOG_LEVELS,
    VALID_PASTE_ACTIONS,
    VALID_PREVIEW_MAX_KIB,
    VALID_PREVIEW_SYNTAX_THEMES,
    VALID_SORT_FIELDS,
    VALID_SPLIT_TERMINAL_POSITIONS,
    VALID_TERMINAL_EDITOR_NAMES,
    VALID_THEMES,
    VALIDATION_PATH,
)


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
            path.write_text(render_default_config(), encoding="utf-8")
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

        return ConfigLoadResult(
            config=AppConfig(
                terminal=load_terminal_config(document.get("terminal"), warnings),
                editor=load_editor_config(document.get("editor"), warnings),
                display=load_display_config(document.get("display"), warnings),
                behavior=load_behavior_config(document.get("behavior"), warnings),
                logging=load_logging_config(document.get("logging"), warnings),
                bookmarks=load_bookmark_config(document.get("bookmarks"), warnings),
                help_bar=load_help_bar_config(document.get("help_bar"), warnings),
                file_search=load_file_search_config(document.get("file_search"), warnings),
            ),
            path=str(path),
            warnings=tuple(warnings),
        )


def load_app_config(*, config_path_resolver: ConfigPathResolver | None = None) -> ConfigLoadResult:
    """Convenience wrapper for loading the user configuration."""

    return AppConfigLoader(config_path_resolver=config_path_resolver).load()


def load_terminal_config(section: object, warnings: list[str]) -> TerminalConfig:
    validated = validate_section_dict(section, "terminal", warnings)
    if validated is None:
        return TerminalConfig()
    return TerminalConfig(
        linux=load_command_templates(validated, "linux", warnings),
        macos=load_command_templates(validated, "macos", warnings),
        windows=load_command_templates(validated, "windows", warnings),
    )


def load_display_config(section: object, warnings: list[str]) -> DisplayConfig:
    config = DisplayConfig()
    validated = validate_section_dict(section, "display", warnings)
    if validated is None:
        return config

    config = replace(
        config,
        show_hidden_files=read_bool(
            validated,
            key="show_hidden_files",
            default=config.show_hidden_files,
            warnings=warnings,
            section_name="display",
        ),
        show_directory_sizes=read_bool(
            validated,
            key="show_directory_sizes",
            default=config.show_directory_sizes,
            warnings=warnings,
            section_name="display",
        ),
        show_preview=read_bool(
            validated,
            key="show_preview",
            default=config.show_preview,
            warnings=warnings,
            section_name="display",
        ),
        default_sort_descending=read_bool(
            validated,
            key="default_sort_descending",
            default=config.default_sort_descending,
            warnings=warnings,
            section_name="display",
        ),
        directories_first=read_bool(
            validated,
            key="directories_first",
            default=config.directories_first,
            warnings=warnings,
            section_name="display",
        ),
        grep_preview_context_lines=read_int(
            validated,
            key="grep_preview_context_lines",
            default=config.grep_preview_context_lines,
            minimum=0,
            warnings=warnings,
            section_name="display",
        ),
    )
    return replace(
        config,
        theme=read_enum(
            validated,
            key="theme",
            default=config.theme,
            valid_values=VALID_THEMES,
            valid_display=SUPPORTED_APP_THEME_DISPLAY,
            section_name="display",
            warnings=warnings,
        ),
        preview_syntax_theme=read_enum(
            validated,
            key="preview_syntax_theme",
            default=config.preview_syntax_theme,
            valid_values=VALID_PREVIEW_SYNTAX_THEMES,
            valid_display=SUPPORTED_PREVIEW_SYNTAX_THEME_DISPLAY,
            section_name="display",
            warnings=warnings,
        ),
        preview_max_kib=read_int(
            validated,
            key="preview_max_kib",
            default=config.preview_max_kib,
            valid_values=VALID_PREVIEW_MAX_KIB,
            warnings=warnings,
            section_name="display",
        ),
        default_sort_field=read_enum(
            validated,
            key="default_sort_field",
            default=config.default_sort_field,
            valid_values=VALID_SORT_FIELDS,
            valid_display="name, modified, size",
            section_name="display",
            warnings=warnings,
        ),
        split_terminal_position=read_enum(
            validated,
            key="split_terminal_position",
            default=config.split_terminal_position,
            valid_values=VALID_SPLIT_TERMINAL_POSITIONS,
            valid_display="bottom, right, overlay",
            section_name="display",
            warnings=warnings,
        ),
    )


def load_editor_config(section: object, warnings: list[str]) -> EditorConfig:
    validated = validate_section_dict(section, "editor", warnings)
    if validated is None:
        return EditorConfig()

    command = validated.get("command")
    if command is None:
        return EditorConfig()
    if not isinstance(command, str):
        warnings.append("editor.command must be a non-empty string; using default.")
        return EditorConfig()
    if not command.strip():
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
    if Path(parsed[0]).name.casefold() not in VALID_TERMINAL_EDITOR_NAMES:
        warnings.append(
            "editor.command must target a supported terminal editor; using default."
        )
        return EditorConfig()
    return EditorConfig(command=command)


def load_behavior_config(section: object, warnings: list[str]) -> BehaviorConfig:
    config = BehaviorConfig()
    validated = validate_section_dict(section, "behavior", warnings)
    if validated is None:
        return config

    return replace(
        config,
        confirm_delete=read_bool(
            validated,
            key="confirm_delete",
            default=config.confirm_delete,
            warnings=warnings,
            section_name="behavior",
        ),
        paste_conflict_action=read_enum(
            validated,
            key="paste_conflict_action",
            default=config.paste_conflict_action,
            valid_values=VALID_PASTE_ACTIONS,
            valid_display="overwrite, skip, rename, prompt",
            section_name="behavior",
            warnings=warnings,
        ),
    )


def load_bookmark_config(section: object, warnings: list[str]) -> BookmarkConfig:
    validated = validate_section_dict(section, "bookmarks", warnings)
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
        paths.append(str(expanded.resolve(strict=False)))

    return BookmarkConfig(paths=tuple(dict.fromkeys(paths)))


def load_help_bar_config(section: object, warnings: list[str]) -> HelpBarConfig:
    validated = validate_section_dict(section, "help_bar", warnings)
    if validated is None:
        return HelpBarConfig()

    values = {
        field: load_help_lines(validated, field, warnings) for field in HELP_BAR_FIELDS
    }
    return HelpBarConfig(**values)


def load_help_lines(
    section: dict[str, object],
    key: str,
    warnings: list[str],
) -> tuple[str, ...]:
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


def load_file_search_config(section: object, warnings: list[str]) -> FileSearchConfig:
    config = FileSearchConfig()
    validated = validate_section_dict(section, "file_search", warnings)
    if validated is None:
        return config

    max_results = validated.get("max_results")
    if max_results is None:
        return config

    if not isinstance(max_results, int):
        warnings.append("file_search.max_results must be an integer or null; using default.")
        return config

    if max_results < 0:
        warnings.append("file_search.max_results must be 0 or greater; using default.")
        return config

    return FileSearchConfig(max_results=max_results)


def load_logging_config(section: object, warnings: list[str]) -> LoggingConfig:
    config = LoggingConfig()
    validated = validate_section_dict(section, "logging", warnings)
    if validated is None:
        return config

    config = replace(
        config,
        enabled=read_bool(
            validated,
            key="enabled",
            default=config.enabled,
            warnings=warnings,
            section_name="logging",
        ),
        level=read_enum(
            validated,
            key="level",
            default=config.level,
            valid_values=VALID_LOG_LEVELS,
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


def load_command_templates(
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
            rendered = item.format(path=VALIDATION_PATH)
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
