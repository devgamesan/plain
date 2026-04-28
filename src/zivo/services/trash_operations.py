"""Service for trash lifecycle operations across supported platforms."""

import configparser
import platform
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
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

        _excluded = {".DS_Store", ".zivo-restore"}
        items = [item for item in trash_dir.iterdir() if item.name not in _excluded]
        if not items:
            return 0, ""

        result = subprocess.run(
            ["osascript", "-e", 'tell application "Finder" to empty trash'],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return 0, (
                "Failed to empty trash. Grant Full Disk Access to your"
                " terminal in System Settings > Privacy & Security"
            )
        return len(items), ""

    def capture_restorable_trash(
        self,
        path: str,
        send_to_trash: Callable[[], None],
    ) -> TrashRestoreRecord | None:
        trash_dir = Path.home() / ".Trash"
        resolved_original = str(Path(path).expanduser().resolve(strict=False))

        before = _snapshot_trash_dir(trash_dir)

        send_to_trash()

        after = _snapshot_trash_dir(trash_dir)
        new_names = sorted(after - before)

        if not new_names:
            return None

        candidates = [
            trash_dir / name for name in new_names if (trash_dir / name).exists()
        ]
        if not candidates:
            return None

        trashed_path = max(candidates, key=lambda p: p.stat().st_mtime)
        metadata_dir = _metadata_dir()
        metadata_path = _write_restore_metadata(
            metadata_dir, resolved_original, str(trashed_path),
        )

        return TrashRestoreRecord(
            original_path=resolved_original,
            trashed_path=str(trashed_path),
            metadata_path=str(metadata_path),
        )

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


@dataclass(frozen=True)
class WindowsTrashService:
    """Trash operations for native Windows."""

    def get_trash_path(self) -> str | None:
        return None

    def empty_trash(self) -> tuple[int, str]:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", "Clear-RecycleBin -Force"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return 0, "Failed to empty Recycle Bin"
        return 1, ""

    def capture_restorable_trash(
        self,
        path: str,
        send_to_trash: Callable[[], None],
    ) -> TrashRestoreRecord | None:
        before = self._get_recycle_bin_original_paths()

        send_to_trash()

        after = self._get_recycle_bin_original_paths()
        new_paths = sorted(after - before)

        resolved_original = str(Path(path).expanduser().resolve(strict=False))
        lower_original = resolved_original.lower()
        lower_new = [p.lower() for p in new_paths]
        if lower_original in lower_new:
            match = resolved_original
        elif not new_paths:
            match = None
        else:
            match = new_paths[-1]

        if match is None:
            return None

        name = Path(match).name

        return TrashRestoreRecord(
            original_path=match,
            trashed_path=name,
            metadata_path="",
        )

    def restore(self, record: TrashRestoreRecord) -> str:
        escaped_path = record.original_path.replace("'", "''")
        escaped_name = record.trashed_path.replace("'", "''")
        ps_script = (
            f"$shell = New-Object -ComObject Shell.Application;"
            f"$rb = $shell.NameSpace(0xa);"
            f"$items = $rb.Items();"
            f"$targetPath = '{escaped_path}'.ToLower();"
            f"$targetName = '{escaped_name}'.ToLower();"
            f"$count = $items.Count;"
            f"$bestItem = $null;"
            f"$bestTime = [DateTime]::MinValue;"
            f"for ($i = 0; $i -lt $count; $i++) {{"
            f"  $item = $items.Item($i);"
            f"  if ($item.Path.ToLower() -eq $targetPath) {{"
            f"    if ($targetName -eq '' -or $item.Name.ToLower() -eq $targetName) {{"
            f"      $modTime = $item.ModifyDate;"
            f"      if ($bestItem -eq $null -or $modTime -gt $bestTime) {{"
            f"        $bestItem = $item;"
            f"        $bestTime = $modTime;"
            f"      }}"
            f"    }}"
            f"  }}"
            f"}}"
            f"if ($bestItem -eq $null) {{ exit 1 }};"
            f"$bestItem.InvokeVerb('undelete');"
            f"$checkItems = $rb.Items();"
            f"for ($i = 0; $i -lt $checkItems.Count; $i++) {{"
            f"  if ($checkItems.Item($i).Path.ToLower() -eq $targetPath) {{"
            f"    $bestItem.InvokeVerb('restore');"
            f"    break;"
            f"  }}"
            f"}}"
            f"for ($i = 0; $i -lt $checkItems.Count; $i++) {{"
            f"  if ($checkItems.Item($i).Path.ToLower() -eq $targetPath) {{"
            f"    exit 2"
            f"  }}"
            f"}}"
        )
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command", ps_script],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            raise OSError(
                f"Failed to restore '{record.original_path}' from Recycle Bin: "
                "PowerShell not available"
            )
        if result.returncode == 1:
            raise OSError(
                f"Failed to restore '{record.original_path}' from Recycle Bin: "
                "item not found"
            )
        if result.returncode == 2:
            raise OSError(
                f"Failed to restore '{record.original_path}' from Recycle Bin: "
                "restore verb had no effect"
            )
        return record.original_path

    @staticmethod
    def _get_recycle_bin_original_paths() -> set[str]:
        ps_script = (
            "$shell = New-Object -ComObject Shell.Application;"
            "$rb = $shell.NameSpace(0xa);"
            "$items = $rb.Items();"
            "$count = $items.Count;"
            "for ($i = 0; $i -lt $count; $i++) {"
            "  $items.Item($i).Path"
            "}"
        )
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command", ps_script],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            return set()
        if result.returncode != 0:
            return set()
        return {line.strip() for line in result.stdout.splitlines() if line.strip()}


@dataclass(frozen=True)
class UnsupportedPlatformTrashService:
    """Placeholder for platforms without any trash integration."""

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


def _snapshot_trash_dir(trash_dir: Path) -> set[str]:
    """Return item names in the macOS trash directory, excluding system entries."""
    if not trash_dir.exists():
        return set()
    excluded = {".DS_Store", ".zivo-restore"}
    return {item.name for item in trash_dir.iterdir() if item.name not in excluded}


def _metadata_dir() -> Path:
    """Return (and create if needed) the macOS restore metadata directory."""
    metadata_dir = Path.home() / ".Trash" / ".zivo-restore"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    return metadata_dir


def _write_restore_metadata(
    metadata_dir: Path,
    original_path: str,
    trashed_path: str,
) -> Path:
    """Write a restore metadata file and return its path."""
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    safe_name = (
        original_path.replace("\\", "_")
        .replace("/", "_")
        .replace(":", "_")
        .lstrip("_")
    )
    metadata_path = metadata_dir / f"{timestamp}_{safe_name}.restoreinfo"

    content = (
        "[Zivo Restore Info]\n"
        f"OriginalPath={original_path}\n"
        f"TrashedPath={trashed_path}\n"
        f"DeletionDate={datetime.now().isoformat()}\n"
    )
    metadata_path.write_text(content, encoding="utf-8")
    return metadata_path


def resolve_trash_service(
) -> LinuxTrashService | MacOsTrashService | WindowsTrashService | UnsupportedPlatformTrashService:
    """Return appropriate trash service based on platform."""

    system = platform.system()
    if system == "Linux":
        return LinuxTrashService()
    if system == "Darwin":
        return MacOsTrashService()
    if system == "Windows":
        return WindowsTrashService()
    return UnsupportedPlatformTrashService()
