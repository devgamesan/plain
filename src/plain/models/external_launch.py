"""Shared models for external application, terminal, and clipboard launches."""

from dataclasses import dataclass
from typing import Literal

ExternalLaunchKind = Literal["open_file", "open_terminal", "copy_paths"]


@dataclass(frozen=True)
class ExternalLaunchRequest:
    """A request to launch an external process or copy paths to the clipboard."""

    kind: ExternalLaunchKind
    path: str | None = None
    paths: tuple[str, ...] = ()
