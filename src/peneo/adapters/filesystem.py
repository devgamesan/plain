"""Filesystem adapter for reading local directory entries."""
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from peneo.state.models import DirectoryEntryState


class DirectoryReader(Protocol):
    """Boundary for reading directory entries from an external filesystem."""

    def list_directory(self, path: str) -> tuple[DirectoryEntryState, ...]: ...


@dataclass(frozen=True)
class LocalFilesystemAdapter:
    """Read and normalize directory contents from the local filesystem."""

    def list_directory(self, path: str) -> tuple[DirectoryEntryState, ...]:
        directory = Path(path).expanduser().resolve()
        entries: list[DirectoryEntryState] = []
        with os.scandir(directory) as children:
            for child in children:
                entry = _build_directory_entry(child)
                if entry is not None:
                    entries.append(entry)
        entries.sort(key=lambda entry: (entry.kind != "dir", entry.name.casefold()))
        return tuple(entries)


def _build_directory_entry(entry: os.DirEntry[str]) -> DirectoryEntryState | None:
    try:
        stat_result = entry.stat()
        kind = "dir" if entry.is_dir() else "file"
    except FileNotFoundError:
        # Skip broken symlinks or entries removed during iteration.
        return None
    return DirectoryEntryState(
        path=entry.path,
        name=entry.name,
        kind=kind,
        size_bytes=None if kind == "dir" else stat_result.st_size,
        modified_at=datetime.fromtimestamp(stat_result.st_mtime),
        hidden=entry.name.startswith("."),
    )
