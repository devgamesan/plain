"""Shared setup for browser snapshot service tests."""

# Test support re-exports service and model types used by split modules.
# ruff: noqa: F401

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from zivo.adapters import LocalFilesystemAdapter
from zivo.services import (
    PREVIEW_PERMISSION_DENIED_MESSAGE,
    FakeBrowserSnapshotLoader,
    LiveBrowserSnapshotLoader,
)
from zivo.services.browser_snapshot import (
    FilePreviewState,
    PdftotextPdfPreviewLoader,
    _resolve_cursor_path,
)
from zivo.state import BrowserSnapshot, GrepSearchResultState
from zivo.state.models import DirectoryEntryState, PaneState


@dataclass
class StubFilesystemAdapter:
    entries_by_path: dict[str, tuple[DirectoryEntryState, ...]] = field(default_factory=dict)
    errors_by_path: dict[str, Exception] = field(default_factory=dict)
    list_directory_calls: list[str] = field(default_factory=list)
    list_directory_summary_calls: list[str] = field(default_factory=list)

    def list_directory(self, path: str) -> tuple[DirectoryEntryState, ...]:
        self.list_directory_calls.append(path)
        if path in self.errors_by_path:
            raise self.errors_by_path[path]
        return self.entries_by_path[path]

    def list_directory_summary(self, path: str) -> tuple[DirectoryEntryState, ...]:
        self.list_directory_calls.append(path)
        self.list_directory_summary_calls.append(path)
        if path in self.errors_by_path:
            raise self.errors_by_path[path]
        return self.entries_by_path[path]


@dataclass
class StubDocumentPreviewLoader:
    previews_by_path: dict[str, FilePreviewState] = field(default_factory=dict)
    calls: list[str] = field(default_factory=list)

    def load_preview(self, path: Path, *, preview_max_bytes: int) -> FilePreviewState | None:
        self.calls.append(f"{path}:{preview_max_bytes}")
        return self.previews_by_path.get(str(path))


@dataclass
class StubPdfPreviewLoader:
    previews_by_path: dict[str, FilePreviewState] = field(default_factory=dict)
    calls: list[str] = field(default_factory=list)

    def load_preview(self, path: Path, *, preview_max_bytes: int) -> FilePreviewState | None:
        self.calls.append(f"{path}:{preview_max_bytes}")
        return self.previews_by_path.get(str(path))


@dataclass
class StubImagePreviewLoader:
    previews_by_path: dict[str, FilePreviewState] = field(default_factory=dict)
    calls: list[str] = field(default_factory=list)

    def load_preview(
        self, path: Path, *, preview_columns: int, image_preview_format: str = "symbols"
    ) -> FilePreviewState | None:
        self.calls.append(f"{path}:{preview_columns}:{image_preview_format}")
        return self.previews_by_path.get(str(path))


def _build_stub_filesystem(*paths: str) -> StubFilesystemAdapter:
    live_filesystem = LocalFilesystemAdapter()
    filesystem = StubFilesystemAdapter()
    for path in paths:
        filesystem.entries_by_path[path] = live_filesystem.list_directory(path)
    return filesystem


