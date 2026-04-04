"""Shared models for background shell command execution."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ShellCommandResult:
    """Captured result from a non-interactive shell command."""

    exit_code: int
    stdout: str = ""
    stderr: str = ""
