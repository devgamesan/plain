"""Custom action matching, expansion, and background execution."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from time import sleep
from typing import Mapping, Protocol

from zivo.models import (
    CustomActionExecutionRequest,
    CustomActionResult,
    ShellCommandResult,
)

from .bounded_process import CancelCallback, run_bounded_process


class CustomActionService(Protocol):
    """Boundary for running resolved custom actions."""

    def execute(
        self,
        request: CustomActionExecutionRequest,
        *,
        max_output_bytes: int = 1024 * 1024,
        timeout_seconds: int = 300,
        cancel_callback: CancelCallback | None = None,
    ) -> CustomActionResult: ...


@dataclass(frozen=True)
class LiveCustomActionService:
    """Run non-interactive custom actions without a shell."""

    extra_env: Mapping[str, str] = field(default_factory=dict)

    def execute(
        self,
        request: CustomActionExecutionRequest,
        *,
        max_output_bytes: int = 1024 * 1024,
        timeout_seconds: int = 300,
        cancel_callback: CancelCallback | None = None,
    ) -> CustomActionResult:
        cwd = Path(request.cwd).expanduser().resolve(strict=False)
        if not cwd.is_dir():
            raise OSError(f"Custom action requires a directory: {cwd}")

        env = dict(os.environ)
        env.update(self.extra_env)
        result = run_bounded_process(
            list(request.command),
            cwd=str(cwd),
            env=env,
            max_output_bytes=max_output_bytes,
            timeout_seconds=timeout_seconds,
            cancel_callback=cancel_callback,
        )
        return CustomActionResult(
            name=request.name,
            result=result,
        )


@dataclass(frozen=True)
class FakeCustomActionService:
    """Deterministic custom action runner for tests."""

    results: Mapping[tuple[str, tuple[str, ...], str], ShellCommandResult] = field(
        default_factory=dict
    )
    failure_messages: Mapping[tuple[str, tuple[str, ...], str], str] = field(
        default_factory=dict
    )
    default_delay_seconds: float = 0.0
    executed_requests: list[CustomActionExecutionRequest] = field(default_factory=list)

    def execute(
        self,
        request: CustomActionExecutionRequest,
        *,
        max_output_bytes: int = 1024 * 1024,
        timeout_seconds: int = 300,
        cancel_callback: CancelCallback | None = None,
    ) -> CustomActionResult:
        if self.default_delay_seconds > 0:
            sleep(self.default_delay_seconds)
        self.executed_requests.append(request)
        key = (request.name, request.command, request.cwd)
        if key in self.failure_messages:
            raise OSError(self.failure_messages[key])
        return CustomActionResult(
            name=request.name,
            result=self.results.get(key, ShellCommandResult(exit_code=0)),
        )
