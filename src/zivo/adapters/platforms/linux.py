"""Linux-specific external launcher commands."""

from __future__ import annotations

from dataclasses import dataclass

from .base import BasePlatformLaunchAdapter


@dataclass(frozen=True)
class LinuxPlatformLaunchAdapter(BasePlatformLaunchAdapter):
    @property
    def platform_kind(self) -> str:
        return "linux"

    def default_app_candidates(self, path: str) -> tuple[tuple[str, ...], ...]:
        return (("xdg-open", path), ("gio", "open", path))

    def default_terminal_candidates(self, path: str) -> tuple[tuple[str, ...], ...]:
        return (
            ("kgx",),
            ("gnome-console",),
            ("gnome-terminal",),
            ("xfce4-terminal",),
            ("mate-terminal",),
            ("tilix",),
            ("konsole",),
            ("lxterminal",),
            ("x-terminal-emulator",),
            ("xterm",),
        )

    def clipboard_candidates(self) -> tuple[tuple[str, ...], ...]:
        return (
            ("wl-copy",),
            ("xclip", "-in", "-selection", "clipboard"),
            ("xsel", "--clipboard", "--input"),
        )

    def clipboard_read_candidates(self) -> tuple[tuple[str, ...], ...]:
        return (
            ("wl-paste", "--no-newline"),
            ("xclip", "-out", "-selection", "clipboard"),
            ("xsel", "--clipboard", "--output"),
        )
