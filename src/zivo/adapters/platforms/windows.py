"""Windows-specific external launcher commands."""

from __future__ import annotations

from dataclasses import dataclass

from .base import (
    BasePlatformLaunchAdapter,
    _resolve_directory_path,
    _windows_cd_command,
    _windows_set_location_command,
)


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

    def run_in_terminal_window(self, cwd: str, command: tuple[str, ...]) -> None:
        """Run a command in a new terminal window with a shell prompt after completion."""
        import subprocess

        resolved_cwd = _resolve_directory_path(cwd)
        cmd_str = subprocess.list2cmdline(list(command))

        terminal = self._first_available_terminal()
        if terminal == "wt.exe":
            self._run_wt_terminal(str(resolved_cwd), cmd_str)
        elif terminal == "cmd.exe":
            self._run_cmd_terminal(str(resolved_cwd), cmd_str)
        else:
            raise OSError(f"No supported terminal found: {terminal}")

    def _first_available_terminal(self) -> str:
        """Return the first available terminal from defaults."""
        import shutil

        if shutil.which("wt.exe") is not None:
            return "wt.exe"
        if shutil.which("cmd.exe") is not None:
            return "cmd.exe"
        raise OSError("No supported terminal found on Windows")

    def _run_wt_terminal(self, cwd: str, cmd_str: str) -> None:
        """Run command in Windows Terminal."""
        import subprocess

        try:
            subprocess.run(
                ("wt.exe", "-d", cwd, "powershell.exe", "-NoExit", "-Command", cmd_str),
                check=True,
                capture_output=True,
            )
        except (OSError, subprocess.CalledProcessError) as error:
            raise OSError(f"Failed to open Windows Terminal: {error}") from error

    def _run_cmd_terminal(self, cwd: str, cmd_str: str) -> None:
        """Run command in cmd.exe window."""
        import subprocess

        escaped_path = cwd.replace('"', '""')
        full_cmd = f'cd /d "{escaped_path}" && {cmd_str} & cmd.exe'
        try:
            subprocess.run(
                ("cmd.exe", "/c", "start", "", "cmd.exe", "/k", full_cmd),
                check=True,
                capture_output=True,
            )
        except (OSError, subprocess.CalledProcessError) as error:
            raise OSError(f"Failed to open cmd.exe: {error}") from error
