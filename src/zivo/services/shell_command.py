"""Background shell command execution services."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from time import sleep
from typing import Callable, Mapping, Protocol

from zivo.models import ShellCommandResult


class ShellCommandService(Protocol):
    """Boundary for running non-interactive shell commands."""

    def execute(self, *, cwd: str, command: str) -> ShellCommandResult: ...


@dataclass(frozen=True)
class LiveShellCommandService:
    """Run shell commands in a background worker."""

    shell: str | None = None
    extra_env: Mapping[str, str] = field(default_factory=dict)
    os_name: str = os.name
    command_available: Callable[[str], str | None] = shutil.which

    def execute(self, *, cwd: str, command: str) -> ShellCommandResult:
        resolved_cwd = Path(cwd).expanduser().resolve()
        if not resolved_cwd.is_dir():
            raise OSError(f"Shell command requires a directory: {resolved_cwd}")

        shell_command = self._build_command_invocation(command)
        env = dict(os.environ)
        env.update(self.extra_env)

        completed = subprocess.run(
            list(shell_command),
            cwd=str(resolved_cwd),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        return ShellCommandResult(
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    def _build_command_invocation(self, command: str) -> tuple[str, ...]:
        shell_command = self._shell_command()
        if self.os_name == "nt":
            return self._build_windows_command_invocation(shell_command, command)
        return (*shell_command, "-lc", command)

    def _shell_command(self) -> tuple[str, ...]:
        if self.os_name == "nt":
            if self.shell:
                parsed = tuple(shlex.split(self.shell, posix=False))
                if parsed:
                    return parsed
            return self._default_windows_shell()

        configured_shell = self.shell or os.environ.get("SHELL")
        if configured_shell:
            parsed = tuple(shlex.split(configured_shell))
            if parsed:
                return parsed
        return ("/bin/bash",)

    def _build_windows_command_invocation(
        self,
        shell_command: tuple[str, ...],
        command: str,
    ) -> tuple[str, ...]:
        shell_name = Path(shell_command[0]).name.casefold()
        if shell_name in {"powershell.exe", "powershell", "pwsh.exe", "pwsh"}:
            return (*shell_command, "-NoProfile", "-Command", command)
        if shell_name in {"cmd.exe", "cmd"}:
            return (*shell_command, "/c", command)
        raise OSError(
            "Windows shell command override must target powershell.exe, pwsh, or cmd.exe"
        )

    def _default_windows_shell(self) -> tuple[str, ...]:
        for command in ("powershell.exe", "pwsh", "cmd.exe"):
            if self._command_exists(command):
                return (command,)
        raise OSError("No supported Windows shell found for shell commands")

    def _command_exists(self, command: str) -> bool:
        command_path = Path(command)
        if command_path.is_absolute():
            return command_path.exists()
        return self.command_available(command) is not None


@dataclass(frozen=True)
class FakeShellCommandService:
    """Deterministic shell command runner for tests."""

    results: Mapping[tuple[str, str], ShellCommandResult] = field(default_factory=dict)
    failure_messages: Mapping[tuple[str, str], str] = field(default_factory=dict)
    default_delay_seconds: float = 0.0
    executed_commands: list[tuple[str, str]] = field(default_factory=list)

    def execute(self, *, cwd: str, command: str) -> ShellCommandResult:
        if self.default_delay_seconds > 0:
            sleep(self.default_delay_seconds)

        request = (cwd, command)
        self.executed_commands.append(request)
        if request in self.failure_messages:
            raise OSError(self.failure_messages[request])
        return self.results.get(request, ShellCommandResult(exit_code=0))
