"""Persist normalized application config."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from zivo.models import AppConfig

from .render import render_app_config


class ConfigSaveService(Protocol):
    """Boundary for persisting the normalized application config."""

    def save(self, *, path: str, config: AppConfig) -> str: ...


class LiveConfigSaveService:
    """Write the normalized application config to disk."""

    def save(self, *, path: str, config: AppConfig) -> str:
        config_path = Path(path).expanduser()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(render_app_config(config), encoding="utf-8")
        return str(config_path)
