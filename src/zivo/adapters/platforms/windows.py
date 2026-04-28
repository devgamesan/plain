"""Windows-specific external launcher commands."""

from __future__ import annotations

from dataclasses import dataclass

from .base import BasePlatformLaunchAdapter, _windows_cd_command, _windows_set_location_command


@dataclass(frozen=True)
class WindowsPlatformLaunchAdapter(BasePlatformLaunchAdapter):
    @property
    def platform_kind(self) -> str:
        return "windows"

    def default_app_candidates(self, path: str) -> tuple[tuple[str, ...], ...]:
        return (
            ("cmd.exe", "/c", "start", "", path),
            ("powershell.exe", "-NoProfile", "-Command", "Start-Process", path),
        )

    def default_terminal_candidates(self, path: str) -> tuple[tuple[str, ...], ...]:
        return (
            ("wt.exe", "-d", path),
            (
                "cmd.exe",
                "/c",
                "start",
                "",
                "powershell.exe",
                "-NoExit",
                "-Command",
                _windows_set_location_command(path),
            ),
            (
                "cmd.exe",
                "/c",
                "start",
                "",
                "cmd.exe",
                "/k",
                _windows_cd_command(path),
            ),
        )

    def clipboard_candidates(self) -> tuple[tuple[str, ...], ...]:
        return (
            ("clip.exe",),
            ("powershell.exe", "-NoProfile", "-Command", "Set-Clipboard"),
        )

    def clipboard_read_candidates(self) -> tuple[tuple[str, ...], ...]:
        return (("powershell.exe", "-NoProfile", "-Command", "Get-Clipboard"),)
