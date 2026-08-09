"""Safe same-directory duplication service."""

import os
import platform
from dataclasses import dataclass, field
from pathlib import Path
from time import sleep
from typing import Callable, Mapping, Protocol

from zivo.adapters import FileOperationAdapter, LocalFileOperationAdapter
from zivo.models import (
    DuplicateAppliedChange,
    DuplicateExecutionResult,
    DuplicateFailure,
    DuplicateRequest,
    DuplicateSummary,
)
from zivo.path_validation import validate_path_segment

DuplicateProgressCallback = Callable[[int, int, str | None], None]


class DuplicateOperationService(Protocol):
    """Boundary for asynchronous same-directory duplication."""

    def execute_duplicate(
        self,
        request: DuplicateRequest,
        *,
        progress_callback: DuplicateProgressCallback | None = None,
    ) -> DuplicateExecutionResult: ...


@dataclass(frozen=True)
class LiveDuplicateOperationService:
    """Duplicate local entries without overwriting existing paths."""

    adapter: FileOperationAdapter = field(default_factory=LocalFileOperationAdapter)

    def execute_duplicate(
        self,
        request: DuplicateRequest,
        *,
        progress_callback: DuplicateProgressCallback | None = None,
    ) -> DuplicateExecutionResult:
        destination_dir = _absolute_entry_path(request.destination_dir)
        if not self.adapter.path_exists(str(destination_dir)):
            raise OSError(f"Destination directory does not exist: {destination_dir}")
        if not destination_dir.is_dir() or destination_dir.is_symlink():
            raise OSError(f"Destination is not a directory: {destination_dir}")

        prepared, preflight_failures = self._prepare_targets(request, destination_dir)
        applied_changes: list[DuplicateAppliedChange] = []
        failures: list[DuplicateFailure] = list(preflight_failures)
        total = len(request.source_paths)
        completed = 0
        if progress_callback is not None:
            for failure in preflight_failures:
                completed += 1
                progress_callback(completed, total, failure.source_path)
        for source_path, destination_path in prepared:
            if progress_callback is not None:
                progress_callback(completed, total, source_path)
            try:
                self.adapter.copy_path(source_path, destination_path)
            except OSError as error:
                failures.append(
                    DuplicateFailure(
                        source_path=source_path,
                        destination_path=destination_path,
                        message=str(error) or "Duplicate failed",
                    )
                )
            else:
                applied_changes.append(
                    DuplicateAppliedChange(
                        source_path=source_path,
                        destination_path=destination_path,
                    )
                )
            completed += 1
            if progress_callback is not None:
                progress_callback(completed, total, source_path)

        return DuplicateExecutionResult(
            summary=DuplicateSummary(
                destination_dir=str(destination_dir),
                total_count=len(request.source_paths),
                success_count=len(applied_changes),
                failures=tuple(failures),
            ),
            applied_changes=tuple(applied_changes),
        )

    def _prepare_targets(
        self,
        request: DuplicateRequest,
        destination_dir: Path,
    ) -> tuple[tuple[tuple[str, str], ...], tuple[DuplicateFailure, ...]]:
        prepared: list[tuple[str, str]] = []
        failures: list[DuplicateFailure] = []
        reserved: set[str] = set()
        for source in request.source_paths:
            source_path = _absolute_entry_path(source)
            destination_path: str | None = None
            try:
                if not self.adapter.path_exists(str(source_path)):
                    raise OSError("Source path does not exist")
                if source_path.is_dir() and not source_path.is_symlink():
                    resolved_source = source_path.resolve(strict=False)
                    resolved_destination = destination_dir.resolve(strict=False)
                    if resolved_destination.is_relative_to(resolved_source):
                        raise OSError("Cannot duplicate a directory into its own contents")
                destination_path = self._next_duplicate_path(
                    source_path,
                    destination_dir,
                    reserved,
                )
                if not os.access(destination_dir, os.W_OK | os.X_OK):
                    raise OSError("Permission denied for destination directory")
            except OSError as error:
                failures.append(
                    DuplicateFailure(
                        source_path=str(source_path),
                        destination_path=destination_path,
                        message=str(error) or "Duplicate validation failed",
                    )
                )
                continue
            reserved.add(_path_key(destination_path))
            prepared.append((str(source_path), destination_path))
        return tuple(prepared), tuple(failures)

    def _next_duplicate_path(
        self,
        source_path: Path,
        destination_dir: Path,
        reserved: set[str],
    ) -> str:
        name = source_path.name
        suffix = source_path.suffix
        stem = source_path.stem if suffix else name
        for index in range(1, 1_000_000):
            counter = "" if index == 1 else f" {index}"
            candidate_name = f"{stem} copy{counter}{suffix}"
            validation_error = validate_path_segment(candidate_name)
            if validation_error is not None:
                raise OSError(validation_error)
            candidate = destination_dir / candidate_name
            candidate_string = str(candidate)
            if (
                not self.adapter.path_exists(candidate_string)
                and _path_key(candidate_string) not in reserved
            ):
                return candidate_string
        raise OSError(f"Could not generate duplicate name for {source_path}")


@dataclass(frozen=True)
class FakeDuplicateOperationService:
    """Deterministic duplicate service used by reducer and app tests."""

    results: Mapping[DuplicateRequest, DuplicateExecutionResult] = field(default_factory=dict)
    failure_messages: Mapping[DuplicateRequest, str] = field(default_factory=dict)
    default_delay_seconds: float = 0.0

    def execute_duplicate(
        self,
        request: DuplicateRequest,
        *,
        progress_callback: DuplicateProgressCallback | None = None,
    ) -> DuplicateExecutionResult:
        if self.default_delay_seconds > 0:
            sleep(self.default_delay_seconds)
        if request in self.failure_messages:
            raise OSError(self.failure_messages[request])
        result = self.results.get(request)
        if result is not None:
            if progress_callback is not None:
                for index, source_path in enumerate(request.source_paths, start=1):
                    progress_callback(index - 1, len(request.source_paths), source_path)
                    progress_callback(index, len(request.source_paths), source_path)
            return result
        applied_changes = tuple(
            DuplicateAppliedChange(
                source_path=source_path,
                destination_path=_fake_destination_path(request.destination_dir, source_path),
            )
            for source_path in request.source_paths
        )
        return DuplicateExecutionResult(
            summary=DuplicateSummary(
                destination_dir=request.destination_dir,
                total_count=len(request.source_paths),
                success_count=len(request.source_paths),
            ),
            applied_changes=applied_changes,
        )


def _absolute_entry_path(path: str) -> Path:
    return Path(os.path.abspath(os.path.expanduser(path)))


def _path_key(path: str) -> str:
    normalized = os.path.normcase(os.path.abspath(path))
    if platform.system() == "Darwin":
        return normalized.casefold()
    return normalized


def _fake_destination_path(destination_dir: str, source_path: str) -> str:
    source = Path(source_path)
    stem = source.stem if source.suffix else source.name
    return str(_absolute_entry_path(destination_dir) / f"{stem} copy{source.suffix}")
