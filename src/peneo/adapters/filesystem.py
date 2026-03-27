"""Filesystem adapter for reading local directory entries."""

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
        for child in directory.iterdir():
            entry = _build_directory_entry(child)
            if entry is not None:
                entries.append(entry)
        entries.sort(key=lambda entry: (entry.kind != "dir", entry.name.casefold()))
        return tuple(entries)

def _build_directory_entry(path: Path) -> DirectoryEntryState | None:
    try:
        stat_result = path.stat()
    except FileNotFoundError:
        # Skip broken symlinks or entries removed during iteration.
        return None
    kind = "dir" if path.is_dir() else "file"
    return DirectoryEntryState(
        path=str(path),
        name=path.name,
        kind=kind,
        size_bytes=None if kind == "dir" else stat_result.st_size,
        modified_at=datetime.fromtimestamp(stat_result.st_mtime),
        hidden=path.name.startswith("."),
        permissions_mode=stat_result.st_mode,
    )
