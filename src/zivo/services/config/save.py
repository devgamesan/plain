"""Persist normalized application config."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Protocol

from zivo.models import AppConfig

from .render import render_app_config, render_optional_toml_string, render_toml_string

CONFIG_EDITOR_MANAGED_SETTINGS: tuple[tuple[str, str], ...] = (
    ("editor", "command"),
    ("gui_editor", "command"),
    ("gui_editor", "fallback_command"),
    ("display", "show_hidden_files"),
    ("display", "theme"),
    ("display", "enable_text_preview"),
    ("display", "enable_image_preview"),
    ("display", "enable_pdf_preview"),
    ("display", "enable_office_preview"),
    ("display", "default_sort_field"),
    ("display", "default_sort_descending"),
    ("display", "directories_first"),
    ("behavior", "confirm_delete"),
)


class ConfigSaveService(Protocol):
    """Boundary for persisting the normalized application config."""

    def save(
        self, *, path: str, config: AppConfig, preserve_unmanaged: bool = False
    ) -> str: ...


class LiveConfigSaveService:
    """Write the normalized application config to disk."""

    def save(
        self, *, path: str, config: AppConfig, preserve_unmanaged: bool = False
    ) -> str:
        config_path = Path(path).expanduser()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        if preserve_unmanaged and config_path.exists():
            existing = config_path.read_text(encoding="utf-8")
            contents = update_config_editor_settings(existing, config)
        else:
            contents = render_app_config(config)
        config_path.write_text(contents, encoding="utf-8")
        return str(config_path)


def update_config_editor_settings(contents: str, config: AppConfig) -> str:
    """Update only the settings exposed by Config Editor in a TOML document.

    Keeping all other text intact preserves advanced, future, and user-defined
    settings (as well as their comments) when a basic setting is saved from the UI.
    """

    values = {
        ("editor", "command"): render_optional_toml_string(config.editor.command),
        ("gui_editor", "command"): render_toml_string(config.gui_editor.command),
        ("gui_editor", "fallback_command"): render_toml_string(
            config.gui_editor.fallback_command
        ),
        ("display", "show_hidden_files"): _render_bool(config.display.show_hidden_files),
        ("display", "theme"): render_toml_string(config.display.theme),
        ("display", "enable_text_preview"): _render_bool(
            config.display.enable_text_preview
        ),
        ("display", "enable_image_preview"): _render_bool(
            config.display.enable_image_preview
        ),
        ("display", "enable_pdf_preview"): _render_bool(config.display.enable_pdf_preview),
        ("display", "enable_office_preview"): _render_bool(
            config.display.enable_office_preview
        ),
        ("display", "default_sort_field"): render_toml_string(
            config.display.default_sort_field
        ),
        ("display", "default_sort_descending"): _render_bool(
            config.display.default_sort_descending
        ),
        ("display", "directories_first"): _render_bool(config.display.directories_first),
        ("behavior", "confirm_delete"): _render_bool(config.behavior.confirm_delete),
    }
    for section, key in CONFIG_EDITOR_MANAGED_SETTINGS:
        contents = _set_toml_value(contents, section, key, values[(section, key)])
    return contents


def _set_toml_value(contents: str, section: str, key: str, value: str) -> str:
    section_pattern = re.compile(
        rf"(?ms)^(?P<header>\[{re.escape(section)}\][^\n]*\n)(?P<body>.*?)(?=^\[|\Z)"
    )
    section_match = section_pattern.search(contents)
    key_pattern = re.compile(rf"^(?P<indent>\s*){re.escape(key)}\s*=.*$", re.MULTILINE)
    if section_match is None:
        separator = "" if not contents or contents.endswith("\n\n") else "\n"
        return f"{contents}{separator}[{section}]\n{key} = {value}\n"

    body = section_match.group("body")
    key_match = key_pattern.search(body)
    if key_match is None:
        updated_body = f"{body}{key} = {value}\n"
    else:
        updated_body = key_pattern.sub(
            lambda match: f"{match.group('indent')}{key} = {value}", body, count=1
        )
    before_body = contents[: section_match.start("body")]
    after_body = contents[section_match.end("body") :]
    return f"{before_body}{updated_body}{after_body}"


def _render_bool(value: bool) -> str:
    return "true" if value else "false"
