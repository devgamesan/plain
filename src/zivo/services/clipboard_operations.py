"""Clipboard-backed file operation service."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from time import sleep
from typing import Mapping, Protocol

from zivo.adapters import FileOperationAdapter, LocalFileOperationAdapter
from zivo.models import (
    OperationCancelCallback,
    OperationProgressCallback,
    PasteAppliedChange,
    PasteConflict,
    PasteConflictPrompt,
    PasteExecutionResult,
    PasteFailure,
    PasteRequest,
    PasteSummary,
    emit_operation_progress,
)


class ClipboardOperationService(Protocol):
    """Boundary for asynchronous clipboard operations."""

    def execute_paste(
        self,
        request: PasteRequest,
        *,
        progress_callback: OperationProgressCallback | None = None,
        cancel_callback: OperationCancelCallback | None = None,
    ) -> PasteConflictPrompt | PasteExecutionResult: ...


@dataclass(frozen=True)
class LiveClipboardOperationService:
    """Execute clipboard operations on the local filesystem."""

    adapter: FileOperationAdapter = field(default_factory=LocalFileOperationAdapter)

    def execute_paste(
        self,
        request: PasteRequest,
        *,
        progress_callback: OperationProgressCallback | None = None,
        cancel_callback: OperationCancelCallback | None = None,
    ) -> PasteConflictPrompt | PasteExecutionResult:
        conflicts = self._collect_conflicts(request)
        if conflicts and request.conflict_resolution is None:
            return PasteConflictPrompt(request=request, conflicts=conflicts)

        success_count = 0
        skipped_count = 0
        skipped_paths: list[str] = []
        overwrote_count = 0
        failures: list[PasteFailure] = []
        applied_changes: list[PasteAppliedChange] = []
        unprocessed_paths: list[str] = []
        processed_count = 0

        for index, source_path in enumerate(request.source_paths):
            if cancel_callback is not None and cancel_callback():
                unprocessed_paths.extend(request.source_paths[index:])
                break
            destination_path = self._destination_for_source(source_path, request.destination_dir)
            conflict = self._is_conflict(source_path, destination_path)

            if conflict:
                resolution = request.conflict_resolution
                if resolution == "skip":
                    skipped_count += 1
                    skipped_paths.append(source_path)
                    processed_count += 1
                    _report_progress(
                        progress_callback,
                        processed_count,
                        len(request.source_paths),
                        source_path,
                    )
                    continue
                if resolution == "rename":
                    destination_path = self.adapter.generate_renamed_path(destination_path)
                elif resolution == "overwrite":
                    if self.adapter.paths_are_same(source_path, destination_path):
                        failures.append(
                            PasteFailure(
                                source_path=source_path,
                                destination_path=destination_path,
                                message="Source and destination are the same path",
                            )
                        )
                        processed_count += 1
                        _report_progress(
                            progress_callback,
                            processed_count,
                            len(request.source_paths),
                            source_path,
                        )
                        continue
                    self.adapter.remove_path(destination_path)
                    overwrote_count += 1

            try:
                if request.mode == "copy":
                    self.adapter.copy_path(source_path, destination_path)
                else:
                    self.adapter.move_path(source_path, destination_path)
            except OSError as error:
                failures.append(
                    PasteFailure(
                        source_path=source_path,
                        destination_path=destination_path,
                        message=str(error) or "Paste failed",
                    )
                )
            else:
                success_count += 1
                processed_count += 1
                applied_changes.append(
                    PasteAppliedChange(
                        source_path=source_path,
                        destination_path=destination_path,
                    )
                )
            _report_progress(
                progress_callback,
                processed_count,
                len(request.source_paths),
                source_path,
            )

        return PasteExecutionResult(
            summary=PasteSummary(
                mode=request.mode,
                destination_dir=request.destination_dir,
                total_count=len(request.source_paths),
                success_count=success_count,
                skipped_count=skipped_count,
                failures=tuple(failures),
                conflict_resolution=request.conflict_resolution,
                overwrote_count=overwrote_count,
                skipped_paths=tuple(skipped_paths),
                cancelled=bool(unprocessed_paths),
                unprocessed_paths=tuple(unprocessed_paths),
            ),
            applied_changes=tuple(applied_changes),
        )

    def _collect_conflicts(self, request: PasteRequest) -> tuple[PasteConflict, ...]:
        conflicts: list[PasteConflict] = []
        for source_path in request.source_paths:
            destination_path = self._destination_for_source(source_path, request.destination_dir)
            if self._is_conflict(source_path, destination_path):
                conflicts.append(
                    PasteConflict(
                        source_path=source_path,
                        destination_path=destination_path,
                    )
                )
        return tuple(conflicts)

    def _is_conflict(self, source_path: str, destination_path: str) -> bool:
        return self.adapter.path_exists(destination_path) or self.adapter.paths_are_same(
            source_path,
            destination_path,
        )

    @staticmethod
    def _destination_for_source(source_path: str, destination_dir: str) -> str:
        return str(_absolute_entry_path(destination_dir) / Path(source_path).name)


@dataclass(frozen=True)
class FakeClipboardOperationService:
    """Deterministic clipboard-operation service used by tests."""

    results: Mapping[PasteRequest, PasteConflictPrompt | PasteExecutionResult] = field(
        default_factory=dict
    )
    failure_messages: Mapping[PasteRequest, str] = field(default_factory=dict)
    default_delay_seconds: float = 0.0

    def execute_paste(
        self,
        request: PasteRequest,
        *,
        progress_callback: OperationProgressCallback | None = None,
        cancel_callback: OperationCancelCallback | None = None,
    ) -> PasteConflictPrompt | PasteExecutionResult:
        if self.default_delay_seconds > 0:
            sleep(self.default_delay_seconds)

        if request in self.failure_messages:
            raise OSError(self.failure_messages[request])

        if cancel_callback is not None and cancel_callback() and request.source_paths:
            return PasteExecutionResult(
                summary=PasteSummary(
                    mode=request.mode,
                    destination_dir=request.destination_dir,
                    total_count=len(request.source_paths),
                    success_count=0,
                    skipped_count=0,
                    failures=(),
                    conflict_resolution=request.conflict_resolution,
                    cancelled=True,
                    unprocessed_paths=request.source_paths,
                )
            )

        result = self.results.get(request)
        if result is None:
            return PasteExecutionResult(
                summary=PasteSummary(
                    mode=request.mode,
                    destination_dir=request.destination_dir,
                    total_count=len(request.source_paths),
                    success_count=len(request.source_paths),
                    skipped_count=0,
                    failures=(),
                    conflict_resolution=request.conflict_resolution,
                ),
                applied_changes=tuple(
                    PasteAppliedChange(
                        source_path=source_path,
                        destination_path=self._destination_for_source(
                            source_path,
                            request.destination_dir,
                        ),
                    )
                    for source_path in request.source_paths
                ),
            )
        if progress_callback is not None and isinstance(result, PasteExecutionResult):
            summary = result.summary
            emit_operation_progress(
                progress_callback,
                summary.success_count + summary.skipped_count + summary.failure_count,
                summary.total_count,
                None,
            )
        return result


def _absolute_entry_path(path: str) -> Path:
    return Path(os.path.abspath(os.path.expanduser(path)))


def _report_progress(
    callback: OperationProgressCallback | None,
    completed: int,
    total: int,
    current_path: str | None,
) -> None:
    if callback is not None:
        emit_operation_progress(callback, completed, total, current_path)
