"""Archive inspection service for listing archive contents."""

import os
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Protocol

from peneo.archive_utils import detect_archive_format
from peneo.models import ArchiveFormat
from peneo.state.models import DirectoryEntryState


class ArchiveListService(Protocol):
    """Boundary for listing archive contents."""

    def list_archive_entries(self, archive_path: str) -> tuple[DirectoryEntryState, ...]: ...


@dataclass(frozen=True)
class LiveArchiveListService:
    """List contents of supported archives using the Python standard library."""

    def list_archive_entries(self, archive_path: str) -> tuple[DirectoryEntryState, ...]:
        source_path = _resolve_source_path(archive_path)
        archive_format = _require_supported_archive(source_path)
        entries = _scan_archive_entries(source_path, archive_format)
        return _build_directory_entries(source_path, entries)


@dataclass(frozen=True)
class FakeArchiveListService:
    """Deterministic archive list service used by tests."""

    entries: tuple[DirectoryEntryState, ...] = ()
    error_message: str | None = None

    def list_archive_entries(self, archive_path: str) -> tuple[DirectoryEntryState, ...]:
        if self.error_message is not None:
            raise OSError(self.error_message)
        return self.entries


def _resolve_source_path(path: str) -> Path:
    return Path(os.path.abspath(os.path.expanduser(path)))


def _require_supported_archive(source_path: Path) -> ArchiveFormat:
    archive_format = detect_archive_format(source_path)
    if archive_format is None:
        raise OSError(f"Unsupported archive format: {source_path.name}")
    if not source_path.is_file():
        raise OSError(f"Archive does not exist: {source_path}")
    return archive_format


@dataclass(frozen=True)
class _ArchiveEntry:
    archive_path: str
    display_name: str
    is_dir: bool
    size_bytes: int | None


def _scan_archive_entries(
    source_path: Path,
    archive_format: ArchiveFormat,
) -> tuple[_ArchiveEntry, ...]:
    if archive_format == "zip":
        with zipfile.ZipFile(source_path) as archive:
            return tuple(
                _ArchiveEntry(
                    archive_path=info.filename,
                    display_name=_get_display_name(info.filename),
                    is_dir=info.is_dir(),
                    size_bytes=info.file_size if not info.is_dir() else None,
                )
                for info in archive.infolist()
                if _normalize_archive_member_path(info.filename) is not None
            )

    with tarfile.open(source_path, mode="r:*") as archive:
        return tuple(
            _ArchiveEntry(
                archive_path=member.name,
                display_name=_get_display_name(member.name),
                is_dir=member.isdir(),
                size_bytes=member.size if not member.isdir() else None,
            )
            for member in archive.getmembers()
            if _normalize_archive_member_path(member.name) is not None
            and (member.isdir() or member.isfile())
        )


def _normalize_archive_member_path(name: str) -> tuple[str, ...] | None:
    normalized_name = name.replace("\\", "/")
    member_path = PurePosixPath(normalized_name)
    if member_path.is_absolute():
        return None

    parts = tuple(part for part in member_path.parts if part not in {"", "."})
    if not parts:
        return None
    if any(part == ".." for part in parts):
        return None
    return parts


def _get_display_name(archive_path: str) -> str:
    parts = _normalize_archive_member_path(archive_path)
    if parts is None:
        return archive_path
    return parts[-1]


def _build_virtual_path(archive_path: Path, entry: _ArchiveEntry) -> str:
    return f"{archive_path}/{entry.archive_path}"


def _build_directory_entries(
    archive_path: Path,
    entries: tuple[_ArchiveEntry, ...],
) -> tuple[DirectoryEntryState, ...]:
    top_level_items: dict[str, dict] = {}

    for entry in entries:
        parts = _normalize_archive_member_path(entry.archive_path)
        if parts is None:
            continue

        top_level_name = parts[0]
        is_directory = entry.is_dir or len(parts) > 1

        if top_level_name not in top_level_items:
            top_level_items[top_level_name] = {
                "name": top_level_name,
                "kind": "dir" if is_directory else "file",
                "size_bytes": None if is_directory else entry.size_bytes,
                "archive_path": top_level_name if is_directory else entry.archive_path,
            }
        else:
            existing = top_level_items[top_level_name]
            if existing["kind"] == "file" and is_directory:
                existing["kind"] = "dir"
                existing["size_bytes"] = None
                existing["archive_path"] = top_level_name

    directory_entries: list[DirectoryEntryState] = []
    for item in top_level_items.values():
        directory_entries.append(
            DirectoryEntryState(
                path=f"{archive_path}/{item['archive_path']}",
                name=item["name"],
                kind=item["kind"],
                size_bytes=item["size_bytes"],
                modified_at=None,
                hidden=False,
                permissions_mode=None,
            )
        )

    directory_entries.sort(key=lambda e: (e.kind != "dir", e.name.casefold()))
    return tuple(directory_entries)
