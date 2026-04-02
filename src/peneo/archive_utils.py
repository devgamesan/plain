"""Pure archive-path helpers shared across state and services."""

from pathlib import Path
from typing import Literal

ArchiveFormat = Literal["zip", "tar", "tar.gz", "tar.bz2"]

SUPPORTED_ARCHIVE_SUFFIXES: tuple[tuple[str, ArchiveFormat], ...] = (
    (".tar.gz", "tar.gz"),
    (".tar.bz2", "tar.bz2"),
    (".zip", "zip"),
    (".tar", "tar"),
)


def detect_archive_format(path: str | Path) -> ArchiveFormat | None:
    """Return the supported archive format for the given path."""

    name = Path(path).name.casefold()
    for suffix, archive_format in SUPPORTED_ARCHIVE_SUFFIXES:
        if name.endswith(suffix):
            return archive_format
    return None


def is_supported_archive_path(path: str | Path) -> bool:
    """Return whether the path points to a supported archive."""

    return detect_archive_format(path) is not None


def strip_archive_suffix(name: str) -> str:
    """Remove the supported archive suffix from a file name."""

    lower_name = name.casefold()
    for suffix, _archive_format in SUPPORTED_ARCHIVE_SUFFIXES:
        if lower_name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def default_extract_destination(source_path: str | Path) -> str:
    """Return the default destination path for an archive extraction."""

    source = Path(source_path).expanduser().resolve()
    return str(source.parent / strip_archive_suffix(source.name))


def resolve_extract_destination_input(source_path: str | Path, value: str) -> str:
    """Resolve an absolute or relative extract destination input."""

    source = Path(source_path).expanduser().resolve()
    destination = Path(value).expanduser()
    if not destination.is_absolute():
        destination = source.parent / destination
    return str(destination.resolve(strict=False))
