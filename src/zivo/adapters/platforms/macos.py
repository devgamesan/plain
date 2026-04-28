"""macOS-specific external launcher commands."""

from __future__ import annotations

from dataclasses import dataclass

from .base import BasePlatformLaunchAdapter


@dataclass(frozen=True)
class MacOSPlatformLaunchAdapter(BasePlatformLaunchAdapter):
    @property
    def platform_kind(self) -> str:
        return "darwin"

    def default_app_candidates(self, path: str) -> tuple[tuple[str, ...], ...]:
        return (("open", path),)

    def default_terminal_candidates(self, path: str) -> tuple[tuple[str, ...], ...]:
        return (("open", "-a", "Terminal", path),)

    def clipboard_candidates(self) -> tuple[tuple[str, ...], ...]:
        return (("pbcopy",),)

    def clipboard_read_candidates(self) -> tuple[tuple[str, ...], ...]:
        return (("pbpaste",),)
