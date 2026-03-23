"""Filesystem adapter for reading local directory entries."""

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from plain.state.models import DirectoryEntryState


class DirectoryReader(Protocol):
    """Boundary for reading directory entries from an external filesystem."""

    def list_directory(self, path: str) -> tuple[DirectoryEntryState, ...]: ...

    def list_directory_recursive(
        self,
        path: str,
        query: str,
    ) -> tuple[DirectoryEntryState, ...]: ...


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

    def list_directory_recursive(
        self,
        path: str,
        query: str,
    ) -> tuple[DirectoryEntryState, ...]:
        directory = Path(path).expanduser().resolve()
        if not directory.exists():
            raise FileNotFoundError(path)
        if not directory.is_dir():
            raise NotADirectoryError(path)

        lowered_query = query.casefold()
        with os.scandir(directory):
            pass

        entries: list[DirectoryEntryState] = []
        for current_root, dir_names, file_names in os.walk(directory):
            root_path = Path(current_root)
            for child_name in (*dir_names, *file_names):
                if lowered_query not in child_name.casefold():
                    continue
                entry = _build_directory_entry(root_path / child_name)
                if entry is not None:
                    entries.append(entry)
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
    )
