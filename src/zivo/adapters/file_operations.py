"""Filesystem adapter for mutating local files and directories."""

import os
from dataclasses import dataclass
from pathlib import Path
from shutil import copy2, copytree, move, rmtree
from typing import Protocol

from send2trash import send2trash


class FileOperationAdapter(Protocol):
    """Boundary for copy/move style filesystem mutations."""

    def path_exists(self, path: str) -> bool: ...

    def paths_are_same(self, source: str, destination: str) -> bool: ...

    def remove_path(self, path: str) -> None: ...

    def copy_path(self, source: str, destination: str) -> None: ...

    def move_path(self, source: str, destination: str) -> None: ...

    def generate_renamed_path(self, destination: str) -> str: ...

    def create_file(self, path: str) -> None: ...

    def create_directory(self, path: str) -> None: ...

    def send_to_trash(self, path: str) -> None: ...


@dataclass(frozen=True)
class LocalFileOperationAdapter:
    """Implement copy/move operations on the local filesystem."""

    def path_exists(self, path: str) -> bool:
        return os.path.lexists(self._entry_path(path))

    def paths_are_same(self, source: str, destination: str) -> bool:
        source_path = self._entry_path(source)
        destination_path = self._entry_path(destination)
        if source_path == destination_path:
            return True
        try:
            return os.path.samefile(str(source_path), str(destination_path))
        except OSError:
            return False

    def remove_path(self, path: str) -> None:
        target = self._entry_path(path)
        if target.is_dir() and not target.is_symlink():
            rmtree(target)
            return
        target.unlink()

    def copy_path(self, source: str, destination: str) -> None:
        source_path = self._entry_path(source)
        destination_path = self._entry_path(destination)
        if source_path == destination_path:
            raise OSError("Source and destination are the same path")
        if source_path.exists() and destination_path.exists():
            if os.path.samefile(str(source_path), str(destination_path)):
                raise OSError("Source and destination are the same path")
        if source_path.is_symlink():
            destination_path.symlink_to(os.readlink(source_path))
            return
        if source_path.is_dir():
            copytree(source_path, destination_path, symlinks=True)
            return
        copy2(source_path, destination_path)

    def move_path(self, source: str, destination: str) -> None:
        source_path = self._entry_path(source)
        destination_path = self._entry_path(destination)
        if source_path == destination_path:
            raise OSError("Source and destination are the same path")
        try:
            move(str(source_path), str(destination_path))
        except OSError as error:
            raise OSError(str(error) or "Rename failed") from error

    def generate_renamed_path(self, destination: str) -> str:
        destination_path = self._entry_path(destination)
        parent = destination_path.parent

        if destination_path.suffix:
            stem = destination_path.stem
            suffix = destination_path.suffix
            pattern = "{stem} copy{counter}{suffix}"
        else:
            stem = destination_path.name
            suffix = ""
            pattern = "{stem} copy{counter}"

        for index in range(1, 1_000):
            counter = "" if index == 1 else f" {index}"
            candidate = parent / pattern.format(stem=stem, counter=counter, suffix=suffix)
            if not self.path_exists(str(candidate)):
                return str(candidate)

        raise OSError(f"Could not generate renamed path for {destination_path}")

    def create_file(self, path: str) -> None:
        target = self._entry_path(path)
        try:
            target.touch(exist_ok=False)
        except OSError as error:
            raise OSError(str(error) or "File creation failed") from error

    def create_directory(self, path: str) -> None:
        target = self._entry_path(path)
        try:
            target.mkdir(exist_ok=False)
        except OSError as error:
            raise OSError(str(error) or "Directory creation failed") from error

    def send_to_trash(self, path: str) -> None:
        target = self._entry_path(path)
        try:
            send2trash(str(target))
        except OSError as error:
            raise OSError(str(error) or "Trash failed") from error

    @staticmethod
    def _entry_path(path: str) -> Path:
        return Path(os.path.abspath(os.path.expanduser(path)))
