"""Zip compression service."""

import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from peneo.models import (
    CreateZipArchivePreparationResult,
    CreateZipArchiveRequest,
    CreateZipArchiveResult,
)

ProgressCallback = Callable[[int, int, str | None], None]


class ZipCompressService(Protocol):
    """Boundary for zip-compression preparation and execution operations."""

    def prepare(self, request: CreateZipArchiveRequest) -> CreateZipArchivePreparationResult: ...

    def execute(
        self,
        request: CreateZipArchiveRequest,
        *,
        progress_callback: ProgressCallback | None = None,
    ) -> CreateZipArchiveResult: ...


@dataclass(frozen=True)
class LiveZipCompressService:
    """Compress files and directories into a zip archive."""

    def prepare(self, request: CreateZipArchiveRequest) -> CreateZipArchivePreparationResult:
        root_dir = _resolve_root_dir(request.root_dir)
        source_paths = _resolve_source_paths(request.source_paths, root_dir)
        destination_path = _resolve_destination_path(request.destination_path)
        _validate_destination(source_paths, destination_path)
        entries = _build_archive_entries(source_paths, root_dir)
        return CreateZipArchivePreparationResult(
            request=CreateZipArchiveRequest(
                source_paths=tuple(str(path) for path in source_paths),
                destination_path=str(destination_path),
                root_dir=str(root_dir),
            ),
            total_entries=len(entries),
            destination_exists=destination_path.exists(),
        )

    def execute(
        self,
        request: CreateZipArchiveRequest,
        *,
        progress_callback: ProgressCallback | None = None,
    ) -> CreateZipArchiveResult:
        root_dir = _resolve_root_dir(request.root_dir)
        source_paths = _resolve_source_paths(request.source_paths, root_dir)
        destination_path = _resolve_destination_path(request.destination_path)
        _validate_destination(source_paths, destination_path)
        entries = _build_archive_entries(source_paths, root_dir)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        if destination_path.exists():
            destination_path.unlink()

        with zipfile.ZipFile(
            destination_path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
        ) as archive:
            total_entries = len(entries)
            for index, entry in enumerate(entries, start=1):
                if entry.is_dir:
                    archive.writestr(f"{entry.arcname}/", "")
                else:
                    archive.write(entry.source_path, arcname=entry.arcname)
                _report_progress(progress_callback, index, total_entries, str(entry.source_path))

        noun = "entry" if len(entries) == 1 else "entries"
        return CreateZipArchiveResult(
            destination_path=str(destination_path),
            archived_entries=len(entries),
            total_entries=len(entries),
            message=f"Created {destination_path.name} with {len(entries)} {noun}",
        )


@dataclass(frozen=True)
class FakeZipCompressService:
    """Deterministic zip service used by tests."""

    prepare_result: CreateZipArchivePreparationResult | None = None
    execute_result: CreateZipArchiveResult | None = None
    prepare_error: str | None = None
    execute_error: str | None = None

    def prepare(self, request: CreateZipArchiveRequest) -> CreateZipArchivePreparationResult:
        if self.prepare_error is not None:
            raise OSError(self.prepare_error)
        if self.prepare_result is not None:
            return self.prepare_result
        return CreateZipArchivePreparationResult(
            request=request,
            total_entries=len(request.source_paths),
        )

    def execute(
        self,
        request: CreateZipArchiveRequest,
        *,
        progress_callback: ProgressCallback | None = None,
    ) -> CreateZipArchiveResult:
        if self.execute_error is not None:
            raise OSError(self.execute_error)
        if progress_callback is not None:
            progress_callback(0, len(request.source_paths), None)
        if self.execute_result is not None:
            return self.execute_result
        total_entries = len(request.source_paths)
        return CreateZipArchiveResult(
            destination_path=request.destination_path,
            archived_entries=total_entries,
            total_entries=total_entries,
            message=f"Created {Path(request.destination_path).name} with {total_entries} entries",
        )


@dataclass(frozen=True)
class _ZipEntry:
    source_path: Path
    arcname: str
    is_dir: bool


def _resolve_root_dir(path: str) -> Path:
    root_dir = Path(path).expanduser().resolve()
    if not root_dir.is_dir():
        raise OSError(f"Zip root directory does not exist: {root_dir}")
    return root_dir


def _resolve_source_paths(source_paths: tuple[str, ...], root_dir: Path) -> tuple[Path, ...]:
    if not source_paths:
        raise OSError("Nothing to compress")
    resolved_paths = tuple(Path(path).expanduser().resolve() for path in source_paths)
    for path in resolved_paths:
        if not path.exists():
            raise OSError(f"Source path does not exist: {path}")
        if not path.is_relative_to(root_dir):
            raise OSError(f"Source path is outside the current directory: {path}")
    return resolved_paths


def _resolve_destination_path(path: str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _validate_destination(source_paths: tuple[Path, ...], destination_path: Path) -> None:
    if destination_path.exists() and destination_path.is_dir():
        raise OSError("Destination path already exists as a directory")

    for source_path in source_paths:
        if destination_path == source_path:
            raise OSError("Destination path cannot be one of the source paths")
        if source_path.is_dir() and not source_path.is_symlink():
            if destination_path.is_relative_to(source_path):
                raise OSError("Destination path cannot be inside a directory being compressed")


def _build_archive_entries(source_paths: tuple[Path, ...], root_dir: Path) -> tuple[_ZipEntry, ...]:
    entries: list[_ZipEntry] = []
    for source_path in source_paths:
        _append_entries(entries, source_path, root_dir)
    return tuple(entries)


def _append_entries(entries: list[_ZipEntry], source_path: Path, root_dir: Path) -> None:
    arcname = source_path.relative_to(root_dir).as_posix()
    if source_path.is_dir() and not source_path.is_symlink():
        entries.append(_ZipEntry(source_path=source_path, arcname=arcname, is_dir=True))
        for child in sorted(
            source_path.iterdir(),
            key=lambda path: (not path.is_dir(), path.name.casefold(), path.name),
        ):
            _append_entries(entries, child, root_dir)
        return

    entries.append(_ZipEntry(source_path=source_path, arcname=arcname, is_dir=False))


def _report_progress(
    progress_callback: ProgressCallback | None,
    completed_entries: int,
    total_entries: int,
    current_path: str | None,
) -> None:
    if progress_callback is None:
        return
    progress_callback(completed_entries, total_entries, current_path)
