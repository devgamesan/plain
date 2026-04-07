"""Service for emptying trash on different platforms.

This module provides platform-specific trash emptying functionality using Python's
standard library (shutil, pathlib) for safe and reliable file deletion.

Security Design:
- Uses only Python standard library (no external commands or dependencies)
- Individual error handling per file (partial failure tolerance)
- Symlink checks to prevent accidental deletion outside trash directories
- Targets only platform-specific trash directories (no risk to non-trash files)
- Best-effort metadata cleanup (orphaned metadata is non-critical)

Platform Support:
- Linux: ~/.local/share/Trash/ (freedesktop.org standard)
- macOS: ~/.Trash/
- Windows: Not supported (requires Windows API calls)
"""

import platform
import shutil
from dataclasses import dataclass
from pathlib import Path


class TrashService:
    """Boundary for trash operations."""

    def get_trash_path(self) -> str | None:
        """Return the trash directory path or None if not found."""

    def empty_trash(self) -> tuple[int, str]:
        """Empty trash and return (removed_count, error_message)."""


@dataclass(frozen=True)
class LinuxTrashService:
    """Trash operations for Linux (freedesktop.org standard)."""

    def get_trash_path(self) -> str | None:
        home = Path.home()
        trash_path = home / ".local/share/Trash"
        return str(trash_path) if trash_path.exists() else None

    def empty_trash(self) -> tuple[int, str]:
        """Empty trash using Python standard library for safety.

        Security considerations:
        - Uses shutil.rmtree() and Path.unlink() from Python stdlib
        - Individual error handling per file (partial failure tolerance)
        - Symlink check to prevent accidental deletion outside trash
        - Targets only trash directory (no risk of deleting non-trash files)

        Returns:
            tuple[int, str]: (removed_count, error_message)
                - error_message is empty on full success
                - error_message contains details on partial/total failure
        """
        trash_path = self.get_trash_path()
        if not trash_path:
            return 0, "Trash directory not found"

        files_path = Path(trash_path) / "files"
        if not files_path.exists():
            return 0, "No items in trash"

        removed_count = 0
        failures = []

        try:
            # Remove individual items with per-file error handling
            # This ensures partial failures don't prevent deletion of other items
            for item in files_path.iterdir():
                try:
                    if item.is_dir() and not item.is_symlink():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
                    removed_count += 1
                except OSError as e:
                    failures.append(f"{item.name}: {str(e)}")

            # Clean up metadata directory (best effort)
            # Metadata failures are non-critical as orphaned files will be cleaned up later
            info_path = Path(trash_path) / "info"
            if info_path.exists():
                for metadata_file in info_path.iterdir():
                    try:
                        metadata_file.unlink()
                    except OSError:
                        pass  # Best effort cleanup - metadata is non-critical

            if failures:
                error_msg = f"Removed {removed_count} items with {len(failures)} failures"
                return removed_count, error_msg

            return removed_count, ""

        except Exception as e:
            return 0, f"Failed to empty trash: {str(e)}"


@dataclass(frozen=True)
class MacOsTrashService:
    """Trash operations for macOS."""

    def get_trash_path(self) -> str | None:
        home = Path.home()
        trash_path = home / ".Trash"
        return str(trash_path) if trash_path.exists() else None

    def empty_trash(self) -> tuple[int, str]:
        """Empty trash using Python standard library for safety.

        Security considerations:
        - Uses shutil.rmtree() and Path.unlink() from Python stdlib
        - Individual error handling per file (partial failure tolerance)
        - Symlink check to prevent accidental deletion outside trash
        - Targets only trash directory (no risk of deleting non-trash files)

        Returns:
            tuple[int, str]: (removed_count, error_message)
        """
        trash_path = self.get_trash_path()
        if not trash_path:
            return 0, "Trash directory not found"

        trash_dir = Path(trash_path)
        if not trash_dir.exists():
            return 0, "No items in trash"

        removed_count = 0
        failures = []

        try:
            # Remove individual items with per-file error handling
            for item in trash_dir.iterdir():
                try:
                    if item.is_dir() and not item.is_symlink():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
                    removed_count += 1
                except OSError as e:
                    failures.append(f"{item.name}: {str(e)}")

            if failures:
                error_msg = f"Removed {removed_count} items with {len(failures)} failures"
                return removed_count, error_msg

            return removed_count, ""

        except Exception as e:
            return 0, f"Failed to empty trash: {str(e)}"


@dataclass(frozen=True)
class UnsupportedPlatformTrashService:
    """Placeholder for unsupported platforms (Windows)."""

    def get_trash_path(self) -> str | None:
        return None

    def empty_trash(self) -> tuple[int, str]:
        return 0, "Empty trash is not supported on this platform"


def resolve_trash_service(
) -> "LinuxTrashService | MacOsTrashService | UnsupportedPlatformTrashService":
    """Return appropriate trash service based on platform."""
    system = platform.system()
    if system == "Linux":
        return LinuxTrashService()
    elif system == "Darwin":
        return MacOsTrashService()
    else:
        return UnsupportedPlatformTrashService()
