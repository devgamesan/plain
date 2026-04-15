"""Service for trash lifecycle operations across supported platforms."""

import configparser
import platform
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

from zivo.models import TrashRestoreRecord


class TrashService:
    """Boundary for trash operations."""

    def get_trash_path(self) -> str | None:
        """Return the trash directory path or None if not found."""

    def empty_trash(self) -> tuple[int, str]:
        """Empty trash and return (removed_count, error_message)."""

    def capture_restorable_trash(
        self,
        path: str,
        send_to_trash: Callable[[], None],
    ) -> TrashRestoreRecord | None:
        """Send an entry to trash and, when possible, capture restore metadata."""

    def restore(self, record: TrashRestoreRecord) -> str:
        """Restore a trashed entry back to its original path."""


@dataclass(frozen=True)
class LinuxTrashService:
    """Trash operations for Linux (freedesktop.org standard)."""

    def get_trash_path(self) -> str | None:
        trash_path = self._trash_root()
        return str(trash_path) if trash_path.exists() else None

    def empty_trash(self) -> tuple[int, str]:
        trash_path = self.get_trash_path()
        if not trash_path:
            return 0, "Trash directory not found"

        files_path = Path(trash_path) / "files"
        if not files_path.exists():
            return 0, "No items in trash"

        removed_count = 0
        failures = []

        try:
            for item in files_path.iterdir():
                try:
                    _remove_path(item)
                    removed_count += 1
                except OSError as error:
                    failures.append(f"{item.name}: {error}")

            info_path = Path(trash_path) / "info"
            if info_path.exists():
                for metadata_file in info_path.iterdir():
                    try:
                        metadata_file.unlink()
                    except OSError:
                        pass

            if failures:
                return removed_count, f"Removed {removed_count} items with {len(failures)} failures"
            return removed_count, ""
        except Exception as error:  # pragma: no cover - defensive fallback
            return 0, f"Failed to empty trash: {error}"

    def capture_restorable_trash(
        self,
        path: str,
        send_to_trash: Callable[[], None],
    ) -> TrashRestoreRecord | None:
        files_dir = self._trash_root() / "files"
        info_dir = self._trash_root() / "info"
        before_info = {item.name for item in info_dir.iterdir()} if info_dir.exists() else set()

        send_to_trash()

        if not info_dir.exists():
            return None

        resolved_original = str(Path(path).expanduser().resolve(strict=False))
        new_info_names = sorted({item.name for item in info_dir.iterdir()} - before_info)
        new_info_paths = [info_dir / name for name in new_info_names]
        matches: list[TrashRestoreRecord] = []
        for info_path in new_info_paths:
            original_path = _parse_trashinfo_original_path(info_path)
            if original_path != resolved_original:
                continue
            trashed_name = info_path.name.removesuffix(".trashinfo")
            trashed_path = files_dir / trashed_name
            if not trashed_path.exists():
                continue
            matches.append(
                TrashRestoreRecord(
                    original_path=original_path,
                    trashed_path=str(trashed_path),
                    metadata_path=str(info_path),
                )
            )

        if not matches:
            return None
        return max(matches, key=lambda record: Path(record.metadata_path).stat().st_mtime)

    def restore(self, record: TrashRestoreRecord) -> str:
        trashed_path = Path(record.trashed_path)
        metadata_path = Path(record.metadata_path)
        original_path = Path(record.original_path)
        if not trashed_path.exists():
            raise OSError(f"Trashed entry not found: {trashed_path.name}")
        if original_path.exists():
            raise OSError(f"Restore destination already exists: {original_path.name}")

        original_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(trashed_path), str(original_path))
        except OSError as error:
            raise OSError(str(error) or f"Failed to restore {original_path.name}") from error

        try:
            if metadata_path.exists():
                metadata_path.unlink()
        except OSError as error:
            raise OSError(str(error) or f"Failed to remove trash metadata for {original_path.name}")
        return str(original_path)

    @staticmethod
    def _trash_root() -> Path:
        return Path.home() / ".local/share/Trash"


@dataclass(frozen=True)
class MacOsTrashService:
    """Trash operations for macOS."""

    def get_trash_path(self) -> str | None:
        trash_path = Path.home() / ".Trash"
        return str(trash_path) if trash_path.exists() else None

    def empty_trash(self) -> tuple[int, str]:
        trash_dir = Path.home() / ".Trash"
        if not trash_dir.exists():
            return 0, ""

        items = [item for item in trash_dir.iterdir() if item.name != ".DS_Store"]
        if not items:
            return 0, ""

        result = subprocess.run(
            ["osascript", "-e", 'tell application "Finder" to empty trash'],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return len(items), ""

        removed_count = 0
        failures = []
        for item in items:
            try:
                _remove_path(item)
                removed_count += 1
            except OSError as error:
                failures.append(f"{item.name}: {error}")

        if failures:
            return removed_count, f"Removed {removed_count} items with {len(failures)} failures"
        return removed_count, ""

    def capture_restorable_trash(
        self,
        path: str,
        send_to_trash: Callable[[], None],
    ) -> TrashRestoreRecord | None:
        send_to_trash()
        return None

    def restore(self, record: TrashRestoreRecord) -> str:
        raise OSError("Trash restore is not supported on this platform")


@dataclass(frozen=True)
class UnsupportedPlatformTrashService:
    """Placeholder for unsupported platforms."""

    def get_trash_path(self) -> str | None:
        return None

    def empty_trash(self) -> tuple[int, str]:
        return 0, "Empty trash is not supported on this platform"

    def capture_restorable_trash(
        self,
        path: str,
        send_to_trash: Callable[[], None],
    ) -> TrashRestoreRecord | None:
        send_to_trash()
        return None

    def restore(self, record: TrashRestoreRecord) -> str:
        raise OSError("Trash restore is not supported on this platform")


def _remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
        return
    path.unlink()


def _parse_trashinfo_original_path(info_path: Path) -> str | None:
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read(info_path, encoding="utf-8")
    except (configparser.Error, OSError):
        return None
    if not parser.has_section("Trash Info"):
        return None
    encoded_path = parser.get("Trash Info", "Path", fallback=None)
    if encoded_path is None:
        return None
    return str(Path(unquote(encoded_path)).expanduser().resolve(strict=False))


def resolve_trash_service(
) -> LinuxTrashService | MacOsTrashService | UnsupportedPlatformTrashService:
    """Return appropriate trash service based on platform."""

    system = platform.system()
    if system == "Linux":
        return LinuxTrashService()
    if system == "Darwin":
        return MacOsTrashService()
    return UnsupportedPlatformTrashService()
