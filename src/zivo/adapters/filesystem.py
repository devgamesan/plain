"""Filesystem adapter for reading local directory entries."""

import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from zivo.state.models import DirectoryEntryState

from .filesystem_attributes import resolve_owner_group


class DirectoryReader(Protocol):
    """Boundary for reading directory entries from an external filesystem."""

    def list_directory(self, path: str) -> tuple[DirectoryEntryState, ...]: ...


class DirectorySizeReader(Protocol):
    """Boundary for recursive directory-size calculations."""

    def calculate_directory_size(
        self,
        path: str,
        *,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> int: ...


class DirectoryAttributeReader(Protocol):
    """Boundary for reading detailed metadata for a single filesystem path."""

    def inspect_entry(self, path: str) -> DirectoryEntryState | None: ...


@dataclass(frozen=True)
class LocalFilesystemAdapter:
    """Read and normalize directory contents from the local filesystem."""

    def list_directory(self, path: str) -> tuple[DirectoryEntryState, ...]:
        directory = Path(path).expanduser().resolve()
        entries: list[DirectoryEntryState] = []
        with os.scandir(directory) as iterator:
            for child in iterator:
                entry = _build_directory_entry_summary(child)
                if entry is not None:
                    entries.append(entry)
        entries.sort(key=lambda entry: (entry.kind != "dir", entry.name.casefold()))
        return tuple(entries)

    def inspect_entry(self, path: str) -> DirectoryEntryState | None:
        entry_path = Path(path).expanduser()
        return _build_directory_entry_details(entry_path)

    def calculate_directory_size(
        self,
        path: str,
        *,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> int:
        directory = Path(path).expanduser().resolve()
        if not directory.exists():
            raise FileNotFoundError(path)
        if not directory.is_dir():
            raise NotADirectoryError(path)
        return _calculate_directory_size(directory, is_cancelled=is_cancelled)


def _build_directory_entry_summary(entry: os.DirEntry[str]) -> DirectoryEntryState | None:
    is_symlink = entry.is_symlink()
    hidden = entry.name.startswith(".")
    try:
        kind = "dir" if entry.is_dir(follow_symlinks=False) else "file"
    except FileNotFoundError:
        if is_symlink:
            return DirectoryEntryState(
                path=entry.path,
                name=entry.name,
                kind="file",
                hidden=hidden,
                symlink=True,
            )
        return None

    if kind == "file" and is_symlink:
        try:
            if entry.is_dir():
                kind = "dir"
        except FileNotFoundError:
            return DirectoryEntryState(
                path=entry.path,
                name=entry.name,
                kind="file",
                hidden=hidden,
                symlink=True,
            )

    try:
        stat_result = entry.stat()
    except FileNotFoundError:
        if is_symlink:
            return DirectoryEntryState(
                path=entry.path,
                name=entry.name,
                kind="file",
                hidden=hidden,
                symlink=True,
            )
        return None
    return DirectoryEntryState(
        path=entry.path,
        name=entry.name,
        kind=kind,
        size_bytes=None if kind == "dir" else stat_result.st_size,
        modified_at=datetime.fromtimestamp(stat_result.st_mtime),
        hidden=hidden,
        permissions_mode=stat_result.st_mode,
        symlink=is_symlink,
    )


def _build_directory_entry_details(path: Path) -> DirectoryEntryState | None:
    is_symlink = path.is_symlink()
    try:
        stat_result = path.stat()
    except FileNotFoundError:
        if is_symlink:
            return DirectoryEntryState(
                path=str(path),
                name=path.name,
                kind="file",
                hidden=path.name.startswith("."),
                symlink=True,
            )
        return None
    kind = "dir" if path.is_dir() else "file"
    owner, group = resolve_owner_group(stat_result)
    return DirectoryEntryState(
        path=str(path),
        name=path.name,
        kind=kind,
        size_bytes=None if kind == "dir" else stat_result.st_size,
        modified_at=datetime.fromtimestamp(stat_result.st_mtime),
        hidden=path.name.startswith("."),
        permissions_mode=stat_result.st_mode,
        owner=owner,
        group=group,
        symlink=is_symlink,
    )


def _calculate_directory_size(
    directory: Path,
    *,
    is_cancelled: Callable[[], bool] | None = None,
) -> int:
    if is_cancelled is not None and is_cancelled():
        raise DirectorySizeCancelled()

    total_size = 0
    try:
        with os.scandir(directory) as iterator:
            for child in iterator:
                if is_cancelled is not None and is_cancelled():
                    raise DirectorySizeCancelled()
                try:
                    if child.is_symlink():
                        continue
                    if child.is_dir(follow_symlinks=False):
                        total_size += _calculate_directory_size(
                            Path(child.path),
                            is_cancelled=is_cancelled,
                        )
                        continue
                    total_size += child.stat(follow_symlinks=False).st_size
                except (FileNotFoundError, PermissionError):
                    continue
    except PermissionError:
        return 0
    return total_size


class DirectorySizeCancelled(RuntimeError):
    """Raised internally to abort a recursive size walk."""
