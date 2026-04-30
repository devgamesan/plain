"""macOS-specific external launcher commands."""

from __future__ import annotations

from dataclasses import dataclass

from .base import BasePlatformLaunchAdapter, _resolve_directory_path


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

    def run_in_terminal_window(self, cwd: str, command: tuple[str, ...]) -> None:
        """Run a command in a new Terminal.app window with a shell prompt after completion."""
        import os
        import shlex
        import subprocess

        resolved_cwd = _resolve_directory_path(cwd)
        cmd_str = " ".join(shlex.quote(arg) for arg in command)
        shell_cmd = os.environ.get("SHELL", "/bin/bash")
        full_command = f'cd {shlex.quote(str(resolved_cwd))} && {cmd_str}; exec {shell_cmd}'

        osascript_script = f'''
        tell application "Terminal"
            activate
            do script "{full_command.replace('"', '\\"')}"
        end tell
        '''

        try:
            subprocess.run(
                ("osascript", "-e", osascript_script),
                check=True,
                capture_output=True,
            )
        except (OSError, subprocess.CalledProcessError) as error:
            raise OSError(f"Failed to open Terminal.app: {error}") from error
