"""Linux-specific external launcher commands."""

from __future__ import annotations

from dataclasses import dataclass

from .base import BasePlatformLaunchAdapter, _resolve_directory_path


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

    def run_in_terminal_window(self, cwd: str, command: tuple[str, ...]) -> None:
        """Run a command in a new terminal window with a shell prompt after completion."""
        import os
        import shlex

        resolved_cwd = _resolve_directory_path(cwd)
        shell_cmd = os.environ.get("SHELL", "/bin/bash")
        cmd_str = " ".join(shlex.quote(arg) for arg in command)
        shell_command = f'cd {shlex.quote(str(resolved_cwd))} && {cmd_str}; exec {shell_cmd}'

        terminal_args = self._terminal_command_with_shell(shell_command)

        try:
            self.context.command_runner(terminal_args, None, None)
        except OSError as error:
            raise OSError(f"Failed to open terminal window: {error}") from error

    def _terminal_command_with_shell(self, shell_command: str) -> tuple[str, ...]:
        """Build a terminal command that runs the shell command."""
        terminal = self._first_available_terminal()
        if terminal is None:
            raise OSError("No supported terminal found")

        terminal_lower = terminal.lower()
        if terminal_lower in ("gnome-terminal", "gnome-console"):
            return (terminal, "--", "sh", "-c", shell_command)
        if terminal_lower in (
            "xfce4-terminal",
            "mate-terminal",
            "tilix",
            "konsole",
            "lxterminal",
            "x-terminal-emulator",
            "xterm",
        ):
            return (terminal, "-e", "sh", "-c", shell_command)
        return (terminal, "-e", "sh", "-c", shell_command)

    def _first_available_terminal(self) -> str | None:
        """Return the first available terminal from defaults."""
        import shutil
        for cmd_tuple in self.default_terminal_candidates(""):
            if cmd_tuple and shutil.which(cmd_tuple[0]) is not None:
                return cmd_tuple[0]
        return None
