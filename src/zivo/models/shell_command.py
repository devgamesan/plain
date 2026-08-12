"""Shared models for background shell command execution."""

from dataclasses import dataclass
from typing import Literal

CommandTerminationReason = Literal["completed", "timed_out", "cancelled"]


@dataclass(frozen=True)
class ShellCommandResult:
    """Captured result from a non-interactive shell command."""

    exit_code: int
    stdout: str = ""
    stderr: str = ""
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    termination_reason: CommandTerminationReason = "completed"
    output_limit_bytes: int | None = None
    timeout_seconds: int | None = None
