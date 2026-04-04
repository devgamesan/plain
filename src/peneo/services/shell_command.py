"""Background shell command execution services."""

from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from time import sleep
from typing import Mapping, Protocol

from peneo.models import ShellCommandResult


class ShellCommandService(Protocol):
    """Boundary for running non-interactive shell commands."""

    def execute(self, *, cwd: str, command: str) -> ShellCommandResult: ...


@dataclass(frozen=True)
class LiveShellCommandService:
    """Run shell commands in a background worker."""

    shell: str | None = None
    extra_env: Mapping[str, str] = field(default_factory=dict)

    def execute(self, *, cwd: str, command: str) -> ShellCommandResult:
        resolved_cwd = Path(cwd).expanduser().resolve()
        if not resolved_cwd.is_dir():
            raise OSError(f"Shell command requires a directory: {resolved_cwd}")

        shell_command = self._shell_command()
        env = dict(os.environ)
        env.update(self.extra_env)

        completed = subprocess.run(
            [*shell_command, "-lc", command],
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

    def _shell_command(self) -> tuple[str, ...]:
        configured_shell = self.shell or os.environ.get("SHELL")
        if configured_shell:
            parsed = tuple(shlex.split(configured_shell))
            if parsed:
                return parsed
        return ("/bin/bash",)


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
