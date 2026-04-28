"""WSL-specific external launcher commands."""

from __future__ import annotations

from dataclasses import dataclass

from .base import BasePlatformLaunchAdapter
from .linux import LinuxPlatformLaunchAdapter


@dataclass(frozen=True)
class WslPlatformLaunchAdapter(BasePlatformLaunchAdapter):
    @property
    def platform_kind(self) -> str:
        return "wsl"

    def default_app_candidates(self, path: str) -> tuple[tuple[str, ...], ...]:
        return (("wslview", path), ("explorer.exe", path))

    def default_terminal_candidates(self, path: str) -> tuple[tuple[str, ...], ...]:
        linux_defaults = LinuxPlatformLaunchAdapter(self.context).default_terminal_candidates(path)
        return (
            ("wt.exe", "wsl.exe", "--cd", path),
            ("cmd.exe", "/c", "start", "", "wsl.exe", "--cd", path),
        ) + linux_defaults

    def clipboard_candidates(self) -> tuple[tuple[str, ...], ...]:
        return (("clip.exe",),)

    def clipboard_read_candidates(self) -> tuple[tuple[str, ...], ...]:
        return (("powershell.exe", "-noprofile", "-command", "Get-Clipboard"),)
