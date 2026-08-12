"""Archive inspection and extraction services."""

import bz2
import gzip
import os
import shutil
import stat
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Protocol

from zivo.archive_utils import (
    detect_archive_format,
)
from zivo.models import (
    ArchiveFormat,
    ExtractArchiveConflict,
    ExtractArchivePreparationResult,
    ExtractArchiveRequest,
    ExtractArchiveResult,
    OperationCancelCallback,
    OperationProgressCallback,
    emit_operation_progress,
)

ProgressCallback = OperationProgressCallback


class ArchiveExtractService(Protocol):
    """Boundary for archive preparation and extraction operations."""

    def prepare(self, request: ExtractArchiveRequest) -> ExtractArchivePreparationResult: ...

    def execute(
        self,
        request: ExtractArchiveRequest,
        *,
        progress_callback: ProgressCallback | None = None,
        cancel_callback: OperationCancelCallback | None = None,
    ) -> ExtractArchiveResult: ...
@dataclass(frozen=True)
class LiveArchiveExtractService:
    """Prepare and extract supported archives using the Python standard library."""

    def prepare(self, request: ExtractArchiveRequest) -> ExtractArchivePreparationResult:
        source_path = _resolve_source_path(request.source_path)
        destination_path = _resolve_destination_path(request.destination_path)
        archive_format = _require_supported_archive(source_path)
        entries = _scan_archive_entries(source_path, archive_format)
        _validate_archive_destinations(
            destination_path,
            tuple(entry.destination_parts for entry in entries),
        )
        conflicts = _scan_conflicts(entries, destination_path)
        return ExtractArchivePreparationResult(
            request=ExtractArchiveRequest(
                source_path=str(source_path),
                destination_path=str(destination_path),
            ),
            format=archive_format,
            total_entries=len(entries),
            conflicts=conflicts,
        )

    def execute(
        self,
        request: ExtractArchiveRequest,
        *,
        progress_callback: ProgressCallback | None = None,
        cancel_callback: OperationCancelCallback | None = None,
    ) -> ExtractArchiveResult:
        source_path = _resolve_source_path(request.source_path)
        destination_path = _resolve_destination_path(request.destination_path)
        archive_format = _require_supported_archive(source_path)
        if archive_format == "zip":
            extracted_entries, unprocessed_paths, cancelled = _extract_zip_archive(
                source_path,
                destination_path,
                progress_callback=progress_callback,
                cancel_callback=cancel_callback,
            )
        elif archive_format == "gz":
            extracted_entries, unprocessed_paths, cancelled = _extract_gz_archive(
                source_path,
                destination_path,
                progress_callback=progress_callback,
                cancel_callback=cancel_callback,
            )
        elif archive_format == "bz2":
            extracted_entries, unprocessed_paths, cancelled = _extract_bz2_archive(
                source_path,
                destination_path,
                progress_callback=progress_callback,
                cancel_callback=cancel_callback,
            )
        else:
            extracted_entries, unprocessed_paths, cancelled = _extract_tar_archive(
                source_path,
                destination_path,
                progress_callback=progress_callback,
                cancel_callback=cancel_callback,
            )

        total_entries = extracted_entries + len(unprocessed_paths)
        noun = "entry" if extracted_entries == 1 else "entries"
        message = (
            f"Extraction cancelled after {extracted_entries} {noun}"
            if cancelled
            else f"Extracted {extracted_entries} {noun} to {destination_path.name}"
        )
        return ExtractArchiveResult(
            destination_path=str(destination_path),
            extracted_entries=extracted_entries,
            total_entries=total_entries,
            message=message,
            level="warning" if cancelled else "info",
            cancelled=cancelled,
            unprocessed_paths=tuple(unprocessed_paths),
        )


@dataclass(frozen=True)
class FakeArchiveExtractService:
    """Deterministic archive service used by tests."""

    prepare_result: ExtractArchivePreparationResult | None = None
    execute_result: ExtractArchiveResult | None = None
    prepare_error: str | None = None
    execute_error: str | None = None

    def prepare(self, request: ExtractArchiveRequest) -> ExtractArchivePreparationResult:
        if self.prepare_error is not None:
            raise OSError(self.prepare_error)
        if self.prepare_result is not None:
            return self.prepare_result
        archive_format = detect_archive_format(request.source_path)
        if archive_format is None:
            raise OSError("Unsupported archive format")
        return ExtractArchivePreparationResult(
            request=request,
            format=archive_format,
            total_entries=0,
        )

    def execute(
        self,
        request: ExtractArchiveRequest,
        *,
        progress_callback: ProgressCallback | None = None,
        cancel_callback: OperationCancelCallback | None = None,
    ) -> ExtractArchiveResult:
        if self.execute_error is not None:
            raise OSError(self.execute_error)
        if cancel_callback is not None and cancel_callback():
            return ExtractArchiveResult(
                destination_path=request.destination_path,
                extracted_entries=0,
                total_entries=0,
                message="Extraction cancelled",
                level="warning",
                cancelled=True,
            )
        if progress_callback is not None:
            emit_operation_progress(progress_callback, 0, 0, None)
        if self.execute_result is not None:
            return self.execute_result
        return ExtractArchiveResult(
            destination_path=request.destination_path,
            extracted_entries=0,
            total_entries=0,
            message="Extracted 0 entries",
        )
def _resolve_source_path(path: str) -> Path:
    return Path(os.path.abspath(os.path.expanduser(path)))


def _resolve_destination_path(path: str) -> Path:
    # Keep the destination lexical so existing links are rejected instead of
    # being silently followed to a different extraction root.
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
    destination_parts: tuple[str, ...]
    is_dir: bool


_REPARSE_POINT_ATTRIBUTE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400)


def _validate_destination_path(destination_root: Path, target_path: Path) -> None:
    """Reject symlinks and reparse points anywhere on an extraction path."""

    try:
        target_path.relative_to(destination_root)
    except ValueError as error:
        raise OSError(
            "Unsafe archive extraction path: "
            f"{target_path} is outside destination {destination_root}"
        ) from error

    for candidate in reversed(target_path.parents):
        _validate_destination_component(candidate)
    _validate_destination_component(target_path)


def _validate_destination_component(path: Path) -> None:
    try:
        path_stat = path.lstat()
    except FileNotFoundError:
        return
    except OSError as error:
        raise OSError(f"Cannot inspect archive extraction path: {path}") from error

    if stat.S_ISLNK(path_stat.st_mode) or (
        getattr(path_stat, "st_file_attributes", 0) & _REPARSE_POINT_ATTRIBUTE
    ):
        raise OSError(
            "Unsafe archive extraction path: "
            f"{path} is a symlink or Windows reparse point"
        )


def _validate_archive_destinations(
    destination_root: Path,
    destination_parts: tuple[tuple[str, ...], ...],
) -> None:
    _validate_destination_path(destination_root, destination_root)
    for parts in destination_parts:
        _validate_destination_path(destination_root, destination_root.joinpath(*parts))


def _scan_archive_entries(
    source_path: Path,
    archive_format: ArchiveFormat,
) -> tuple[_ArchiveEntry, ...]:
    if archive_format == "zip":
        with zipfile.ZipFile(source_path) as archive:
            return tuple(
                _ArchiveEntry(
                    archive_path=info.filename,
                    destination_parts=parts,
                    is_dir=info.is_dir(),
                )
                for info in archive.infolist()
                if (parts := _normalize_archive_member_path(info.filename)) is not None
            )

    if archive_format in ("gz", "bz2"):
        entry_name = _get_decompressed_entry_name(source_path)
        return (
            _ArchiveEntry(
                archive_path=entry_name,
                destination_parts=(entry_name,),
                is_dir=False,
            ),
        )

    with tarfile.open(source_path, mode="r:*") as archive:
        return tuple(
            _ArchiveEntry(
                archive_path=member.name,
                destination_parts=parts,
                is_dir=member.isdir(),
            )
            for member in archive.getmembers()
            if (parts := _normalize_archive_member_path(member.name)) is not None
            and (member.isdir() or member.isfile())
        )


def _scan_conflicts(
    entries: tuple[_ArchiveEntry, ...],
    destination_path: Path,
) -> tuple[ExtractArchiveConflict, ...]:
    conflicts: dict[str, ExtractArchiveConflict] = {}
    for entry in entries:
        target_path = destination_path.joinpath(*entry.destination_parts)
        if target_path.exists():
            key = str(target_path)
            conflicts.setdefault(
                key,
                ExtractArchiveConflict(
                    archive_path=entry.archive_path,
                    destination_path=key,
                ),
            )
    return tuple(conflicts.values())


def _normalize_archive_member_path(name: str) -> tuple[str, ...] | None:
    normalized_name = name.replace("\\", "/")
    member_path = PurePosixPath(normalized_name)
    windows_member_path = PureWindowsPath(normalized_name)
    if member_path.is_absolute() or windows_member_path.drive or windows_member_path.root:
        raise OSError(f"Archive entry uses an absolute path: {name}")

    parts = tuple(part for part in member_path.parts if part not in {"", "."})
    if not parts:
        return None
    if any(part == ".." for part in parts):
        raise OSError(f"Archive entry escapes the destination directory: {name}")
    return parts


def _get_decompressed_entry_name(source_path: Path) -> str:
    """Derive the decompressed filename by stripping the compression suffix."""
    name = source_path.name
    lower = name.casefold()
    if lower.endswith(".bz2") and len(name) > 4:
        return name[:-4]
    if lower.endswith(".gz") and len(name) > 3:
        return name[:-3]
    return name


def _extract_zip_archive(
    source_path: Path,
    destination_path: Path,
    *,
    progress_callback: ProgressCallback | None,
    cancel_callback: OperationCancelCallback | None,
) -> tuple[int, tuple[str, ...], bool]:
    with zipfile.ZipFile(source_path) as archive:
        entries = [
            (info, parts)
            for info in archive.infolist()
            if (parts := _normalize_archive_member_path(info.filename)) is not None
        ]
        _validate_archive_destinations(
            destination_path,
            tuple(parts for _, parts in entries),
        )
        total_entries = len(entries)
        extracted_entries = 0

        for index, (info, parts) in enumerate(entries):
            if cancel_callback is not None and cancel_callback():
                return (
                    extracted_entries,
                    tuple(
                        str(destination_path.joinpath(*remaining_parts))
                        for _, remaining_parts in entries[index:]
                    ),
                    True,
                )
            target_path = destination_path.joinpath(*parts)
            if info.is_dir():
                _prepare_directory_target(target_path, destination_path)
            else:
                _prepare_file_target(target_path, destination_path)
                _write_archive_file_atomically(
                    target_path,
                    lambda temporary_path: _copy_stream(
                        archive.open(info),
                        temporary_path,
                    ),
                    destination_root=destination_path,
                )
            extracted_entries += 1
            _report_progress(progress_callback, extracted_entries, total_entries, str(target_path))

    return extracted_entries, (), False


def _extract_tar_archive(
    source_path: Path,
    destination_path: Path,
    *,
    progress_callback: ProgressCallback | None,
    cancel_callback: OperationCancelCallback | None,
) -> tuple[int, tuple[str, ...], bool]:
    with tarfile.open(source_path, mode="r:*") as archive:
        members = [
            (member, parts)
            for member in archive.getmembers()
            if (parts := _normalize_archive_member_path(member.name)) is not None
            and (member.isdir() or member.isfile())
        ]
        _validate_archive_destinations(
            destination_path,
            tuple(parts for _, parts in members),
        )
        total_entries = len(members)
        extracted_entries = 0

        for index, (member, parts) in enumerate(members):
            if cancel_callback is not None and cancel_callback():
                return (
                    extracted_entries,
                    tuple(
                        str(destination_path.joinpath(*remaining_parts))
                        for _, remaining_parts in members[index:]
                    ),
                    True,
                )
            target_path = destination_path.joinpath(*parts)
            if member.isdir():
                _prepare_directory_target(target_path, destination_path)
            elif member.isfile():
                _prepare_file_target(target_path, destination_path)
                extracted_file = archive.extractfile(member)
                if extracted_file is None:
                    raise OSError(f"Failed to read archive member: {member.name}")
                _write_archive_file_atomically(
                    target_path,
                    lambda temporary_path: _copy_stream(extracted_file, temporary_path),
                    destination_root=destination_path,
                )
            else:
                raise OSError(f"Unsupported archive member type: {member.name}")
            extracted_entries += 1
            _report_progress(progress_callback, extracted_entries, total_entries, str(target_path))

    return extracted_entries, (), False


def _extract_gz_archive(
    source_path: Path,
    destination_path: Path,
    *,
    progress_callback: ProgressCallback | None,
    cancel_callback: OperationCancelCallback | None,
) -> tuple[int, tuple[str, ...], bool]:
    entry_name = _get_decompressed_entry_name(source_path)
    target_path = destination_path / entry_name
    if cancel_callback is not None and cancel_callback():
        return 0, (str(target_path),), True
    _validate_archive_destinations(destination_path, ((entry_name,),))
    _prepare_file_target(target_path, destination_path)
    _write_archive_file_atomically(
        target_path,
        lambda temporary_path: _copy_stream(gzip.open(source_path, "rb"), temporary_path),
        destination_root=destination_path,
    )
    _report_progress(progress_callback, 1, 1, str(target_path))
    return 1, (), False


def _extract_bz2_archive(
    source_path: Path,
    destination_path: Path,
    *,
    progress_callback: ProgressCallback | None,
    cancel_callback: OperationCancelCallback | None,
) -> tuple[int, tuple[str, ...], bool]:
    entry_name = _get_decompressed_entry_name(source_path)
    target_path = destination_path / entry_name
    if cancel_callback is not None and cancel_callback():
        return 0, (str(target_path),), True
    _validate_archive_destinations(destination_path, ((entry_name,),))
    _prepare_file_target(target_path, destination_path)
    _write_archive_file_atomically(
        target_path,
        lambda temporary_path: _copy_stream(bz2.open(source_path, "rb"), temporary_path),
        destination_root=destination_path,
    )
    _report_progress(progress_callback, 1, 1, str(target_path))
    return 1, (), False


def _prepare_directory_target(target_path: Path, destination_root: Path) -> None:
    _validate_destination_path(destination_root, target_path)
    if target_path.exists() and not target_path.is_dir():
        raise OSError(f"Cannot replace file with directory: {target_path.name}")
    target_path.mkdir(parents=True, exist_ok=True)


def _prepare_file_target(target_path: Path, destination_root: Path) -> None:
    _validate_destination_path(destination_root, target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists() and target_path.is_dir():
        raise OSError(f"Cannot replace directory with file: {target_path.name}")


def _write_archive_file_atomically(
    target_path: Path,
    writer,
    *,
    destination_root: Path,
) -> None:
    """Write one extracted file beside its destination, then replace atomically."""

    _validate_destination_path(destination_root, target_path)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target_path.name}.zivo-",
        dir=str(target_path.parent),
    )
    os.close(file_descriptor)
    temporary_path = Path(temporary_name)
    try:
        writer(temporary_path)
        if target_path.exists() and not target_path.is_symlink():
            temporary_path.chmod(stat.S_IMODE(target_path.stat().st_mode))
        _validate_destination_path(destination_root, target_path)
        os.replace(temporary_path, target_path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _copy_stream(source_file, temporary_path: Path) -> None:
    with source_file, temporary_path.open("wb") as destination_file:
        shutil.copyfileobj(source_file, destination_file)


def _report_progress(
    progress_callback: ProgressCallback | None,
    completed_entries: int,
    total_entries: int,
    current_path: str | None,
) -> None:
    if progress_callback is None:
        return
    emit_operation_progress(progress_callback, completed_entries, total_entries, current_path)
