"""External application, terminal, and clipboard launch services."""

from dataclasses import dataclass, field
from time import sleep
from typing import Mapping, Protocol

from plain.adapters import ExternalLaunchAdapter, LocalExternalLaunchAdapter
from plain.models import ExternalLaunchRequest


class ExternalLaunchService(Protocol):
    """Boundary for asynchronous external process launches."""

    def execute(self, request: ExternalLaunchRequest) -> None: ...


@dataclass(frozen=True)
class LiveExternalLaunchService:
    """Launch files and terminals through the OS adapter."""

    adapter: ExternalLaunchAdapter = field(default_factory=LocalExternalLaunchAdapter)

    def execute(self, request: ExternalLaunchRequest) -> None:
        if request.kind == "copy_paths":
            try:
                self.adapter.copy_to_clipboard(_format_clipboard_payload(request.paths))
            except OSError as error:
                raise OSError(_format_copy_error(request.paths, str(error))) from error
            return

        if request.kind == "open_file":
            path = _require_path(request)
            try:
                self.adapter.open_with_default_app(path)
            except OSError as error:
                raise OSError(_format_open_error(path, str(error))) from error
            return

        if request.kind == "open_editor":
            path = _require_path(request)
            try:
                self.adapter.open_in_editor(path)
            except OSError as error:
                raise OSError(_format_editor_error(path, str(error))) from error
            return

        path = _require_path(request)
        try:
            self.adapter.open_terminal(path)
        except OSError as error:
            raise OSError(_format_terminal_error(path, str(error))) from error


@dataclass(frozen=True)
class FakeExternalLaunchService:
    """Deterministic external launcher used by tests."""

    failure_messages: Mapping[ExternalLaunchRequest, str] = field(default_factory=dict)
    default_delay_seconds: float = 0.0
    executed_requests: list[ExternalLaunchRequest] = field(default_factory=list)

    def execute(self, request: ExternalLaunchRequest) -> None:
        if self.default_delay_seconds > 0:
            sleep(self.default_delay_seconds)

        self.executed_requests.append(request)
        if request in self.failure_messages:
            raise OSError(self.failure_messages[request])


def _format_open_error(path: str, detail: str) -> str:
    return f"Failed to open {path}: {detail}"


def _format_editor_error(path: str, detail: str) -> str:
    return f"Failed to open {path} in editor: {detail}"


def _format_terminal_error(path: str, detail: str) -> str:
    return f"Failed to open terminal in {path}: {detail}"


def _format_copy_error(paths: tuple[str, ...], detail: str) -> str:
    count = len(paths)
    noun = "path" if count == 1 else "paths"
    return f"Failed to copy {count} {noun} to system clipboard: {detail}"


def _format_clipboard_payload(paths: tuple[str, ...]) -> str:
    return "\n".join(paths)


def _require_path(request: ExternalLaunchRequest) -> str:
    if request.path is None:
        raise OSError(f"Missing path for {request.kind}")
    return request.path
