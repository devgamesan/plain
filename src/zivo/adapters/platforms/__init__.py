"""Platform-specific external launcher implementations."""

from __future__ import annotations

from .base import (
    BasePlatformLaunchAdapter,
    PlatformAdapterContext,
    PlatformKind,
    is_wsl_environment,
)
from .linux import LinuxPlatformLaunchAdapter
from .macos import MacOSPlatformLaunchAdapter
from .windows import WindowsPlatformLaunchAdapter
from .wsl import WslPlatformLaunchAdapter


def resolve_platform_kind(
    system_name: str,
    *,
    environment_variable,
    text_file_reader,
) -> PlatformKind:
    if system_name == "Darwin":
        return "darwin"
    if system_name == "Linux":
        if is_wsl_environment(environment_variable, text_file_reader):
            return "wsl"
        return "linux"
    if system_name == "Windows":
        return "windows"
    raise OSError(f"Unsupported operating system: {system_name}")


def resolve_platform_adapter(
    kind: PlatformKind,
    context: PlatformAdapterContext,
) -> BasePlatformLaunchAdapter:
    if kind == "linux":
        return LinuxPlatformLaunchAdapter(context)
    if kind == "wsl":
        return WslPlatformLaunchAdapter(context)
    if kind == "darwin":
        return MacOSPlatformLaunchAdapter(context)
    return WindowsPlatformLaunchAdapter(context)
