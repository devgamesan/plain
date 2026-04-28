"""Windows-specific virtual drive root helpers."""

from __future__ import annotations

import ntpath
import os
import platform
import posixpath
import re
from string import ascii_uppercase

WINDOWS_DRIVES_ROOT = "::zivo::windows-drives::"
WINDOWS_DRIVES_LABEL = "Drives"
_WINDOWS_DRIVE_PATTERN = re.compile(r"^[a-zA-Z]:([\\/])?$")
_WINDOWS_DRIVE_PREFIX_PATTERN = re.compile(r"^[a-zA-Z]:?$")


class ComparableWindowsPath(str):
    """String subclass that compares Windows paths after normalization."""

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str) and is_windows_path(other):
            return normalize_windows_path(str(self)) == normalize_windows_path(other)
        return super().__eq__(other)

    def __hash__(self) -> int:
        return str.__hash__(self)


def is_windows_platform() -> bool:
    """Return True when Windows-specific path behavior should be enabled."""

    return platform.system() == "Windows"


def is_windows_drives_root(path: str) -> bool:
    """Return True when the path points to the virtual Windows drive listing."""

    return path == WINDOWS_DRIVES_ROOT


def is_windows_drive_root(path: str) -> bool:
    """Return True for drive-root paths such as ``C:\\``."""

    if not path:
        return False
    return _WINDOWS_DRIVE_PATTERN.fullmatch(path.replace("/", "\\")) is not None


def is_windows_path(path: str) -> bool:
    """Return True when the path uses Windows drive or UNC syntax."""

    if not path:
        return False
    normalized_path = path.replace("/", "\\")
    drive, _ = ntpath.splitdrive(normalized_path)
    return bool(drive) or normalized_path.startswith("\\\\")


def is_posix_path(path: str) -> bool:
    """Return True when the path uses rooted POSIX syntax."""

    return bool(path) and path.startswith("/")


def normalize_windows_path(path: str) -> str:
    """Normalize drive-root paths without depending on host OS path parsing."""

    if is_windows_drives_root(path):
        return path
    if not is_windows_path(path):
        return path
    candidate = path.replace("/", "\\")
    drive, tail = ntpath.splitdrive(candidate)
    if not drive:
        return path
    if tail in ("", "."):
        return f"{drive}\\"
    return ntpath.normpath(candidate)


def display_path(path: str) -> str:
    """Render a user-facing path label."""

    if is_windows_drives_root(path):
        return WINDOWS_DRIVES_LABEL
    return path


def comparable_path(path: str | None) -> str | None:
    """Wrap Windows paths for direct-equality comparisons without changing display."""

    if path is None or not is_windows_path(path):
        return path
    return ComparableWindowsPath(path)


def paths_equal(left: str | None, right: str | None) -> bool:
    """Compare paths while treating Windows separators as equivalent."""

    if left is None or right is None:
        return left == right
    if is_windows_path(left) and is_windows_path(right):
        return normalize_windows_path(left) == normalize_windows_path(right)
    return left == right


def list_windows_drive_paths() -> tuple[str, ...]:
    """Return available Windows drive roots."""

    if not is_windows_platform():
        return ()
    drives = tuple(
        f"{letter}:\\"
        for letter in ascii_uppercase
        if os.path.exists(f"{letter}:\\")
    )
    return drives


def resolve_parent_directory_path(path: str) -> tuple[str, str | None]:
    """Return the resolved path and its distinct parent, if one exists."""

    if is_windows_drives_root(path):
        return WINDOWS_DRIVES_ROOT, None

    if is_windows_path(path):
        normalized_path = normalize_windows_path(path)
        if is_windows_drive_root(normalized_path):
            return normalized_path, WINDOWS_DRIVES_ROOT
        parent_path = ntpath.dirname(normalized_path)
        if not parent_path or parent_path == normalized_path:
            return normalized_path, None
        return normalized_path, normalize_windows_path(parent_path)

    if is_posix_path(path):
        normalized_path = posixpath.normpath(path) or "/"
        if normalized_path == "/":
            return "/", None
        parent_path = posixpath.dirname(normalized_path) or "/"
        return normalized_path, parent_path

    from pathlib import Path

    resolved_path = Path(path).expanduser().resolve()
    parent_path = resolved_path.parent
    if parent_path == resolved_path:
        return str(resolved_path), None
    return str(resolved_path), str(parent_path)


def expand_windows_path(query: str, base_path: str) -> str | None:
    """Resolve a Windows path query independently from host OS semantics."""

    raw_query = os.path.expanduser(query.strip())
    if not raw_query:
        return None
    normalized_query = raw_query.replace("/", "\\")
    if not (
        is_windows_drives_root(base_path)
        or is_windows_path(base_path)
        or normalized_query.startswith("\\")
        or _WINDOWS_DRIVE_PREFIX_PATTERN.fullmatch(normalized_query) is not None
    ):
        return None

    if _WINDOWS_DRIVE_PATTERN.fullmatch(normalized_query):
        return normalize_windows_path(normalized_query)

    if normalized_query.startswith("\\\\"):
        return ntpath.normpath(normalized_query)

    drive, _ = ntpath.splitdrive(normalized_query)
    if drive:
        return ntpath.normpath(normalized_query)

    if is_windows_drives_root(base_path):
        return None

    normalized_base = normalize_windows_path(base_path)
    if not ntpath.splitdrive(normalized_base)[0]:
        return None
    return ntpath.normpath(ntpath.join(normalized_base, normalized_query))


def split_windows_completion_query(query: str) -> tuple[str, str] | None:
    """Return ``(parent, prefix)`` for Windows drive completion shortcuts."""

    raw_query = query.strip().replace("/", "\\")
    if not raw_query:
        return WINDOWS_DRIVES_ROOT, ""
    if _WINDOWS_DRIVE_PREFIX_PATTERN.fullmatch(raw_query):
        return WINDOWS_DRIVES_ROOT, raw_query.rstrip(":").casefold()
    return None


def basename(path: str) -> str:
    """Return the final path segment while preserving input path style."""

    if is_windows_path(path):
        return ntpath.basename(normalize_windows_path(path))
    if is_posix_path(path):
        return posixpath.basename(path)
    from pathlib import Path

    return Path(path).name


def join_path(base_path: str, name: str) -> str:
    """Join a child name while preserving input path style."""

    if is_windows_path(base_path):
        return normalize_windows_path(ntpath.join(normalize_windows_path(base_path), name))
    if is_posix_path(base_path):
        return posixpath.join(base_path, name)
    from pathlib import Path

    return str(Path(base_path) / name)
