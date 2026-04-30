"""WSL-specific external launcher commands."""

from __future__ import annotations

import subprocess
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

    def run_in_terminal_window(self, cwd: str, command: tuple[str, ...]) -> None:
        """Run a command in a new terminal window with a shell prompt after completion."""
        from .base import _resolve_directory_path

        resolved_cwd = _resolve_directory_path(cwd)
        cmd_str = " ".join(f'"{arg}"' for arg in command)

        terminal = self._first_available_terminal()
        if terminal == "wt.exe":
            self._run_wt_terminal(str(resolved_cwd), cmd_str)
        elif terminal == "cmd.exe":
            self._run_cmd_terminal(str(resolved_cwd), cmd_str)
        else:
            self._run_linux_terminal(str(resolved_cwd), cmd_str, terminal)

    def _first_available_terminal(self) -> str:
        """Return the first available terminal from defaults."""
        import shutil

        if shutil.which("wt.exe") is not None:
            return "wt.exe"
        if shutil.which("cmd.exe") is not None:
            return "cmd.exe"

        linux_defaults = LinuxPlatformLaunchAdapter(self.context).default_terminal_candidates("")
        for cmd_tuple in linux_defaults:
            if cmd_tuple and shutil.which(cmd_tuple[0]) is not None:
                return cmd_tuple[0]
        raise OSError("No supported terminal found on WSL")

    def _run_wt_terminal(self, cwd: str, cmd_str: str) -> None:
        """Run command in Windows Terminal."""
        try:
            subprocess.run(
                ("wt.exe", "wsl.exe", "--cd", cwd, "bash", "-c", f"{cmd_str}; exec $SHELL"),
                check=True,
                capture_output=True,
            )
        except (OSError, subprocess.CalledProcessError) as error:
            raise OSError(f"Failed to open Windows Terminal: {error}") from error

    def _run_cmd_terminal(self, cwd: str, cmd_str: str) -> None:
        """Run command in cmd.exe window."""
        import subprocess

        escaped_path = cwd.replace('"', '""')
        full_cmd = f'wsl.exe --cd "{escaped_path}" -- bash -c "{cmd_str}; exec $SHELL"'
        try:
            subprocess.run(
                ("cmd.exe", "/c", "start", "", "cmd.exe", "/k", full_cmd),
                check=True,
                capture_output=True,
            )
        except (OSError, subprocess.CalledProcessError) as error:
            raise OSError(f"Failed to open cmd.exe: {error}") from error

    def _run_linux_terminal(self, cwd: str, cmd_str: str, terminal: str) -> None:
        """Run command in a Linux terminal."""
        import os
        import subprocess

        shell_cmd = os.environ.get("SHELL", "/bin/bash")
        shell_command = f'cd "{cwd}" && {cmd_str}; exec {shell_cmd}'

        terminal_lower = terminal.lower()
        if terminal_lower in ("gnome-terminal", "gnome-console"):
            full_cmd = (terminal, "--", "sh", "-c", shell_command)
        else:
            full_cmd = (terminal, "-e", "sh", "-c", shell_command)

        try:
            subprocess.run(full_cmd, check=True, capture_output=True)
        except (OSError, subprocess.CalledProcessError) as error:
            raise OSError(f"Failed to open {terminal}: {error}") from error
