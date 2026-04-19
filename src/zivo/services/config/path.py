"""Platform-specific config path resolution."""

from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import Callable

SystemNameResolver = Callable[[], str]
EnvironmentVariableReader = Callable[[str], str | None]
HomeDirectoryResolver = Callable[[], Path]
ConfigPathResolver = Callable[[], Path]


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
