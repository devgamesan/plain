"""Safe, same-directory bulk rename service."""

from __future__ import annotations

import os
import platform
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from time import sleep
from typing import Callable, Mapping, Protocol

from zivo.adapters import FileOperationAdapter, LocalFileOperationAdapter
from zivo.models import (
    BulkRenameAppliedChange,
    BulkRenameExecutionResult,
    BulkRenamePlanItem,
    BulkRenameRequest,
    BulkRenameTarget,
    BulkRenameValidationResult,
)
from zivo.path_validation import validate_path_segment

BulkRenameProgressCallback = Callable[[int, int, str | None], None]


class BulkRenameService(Protocol):
    """Boundary for safe same-directory bulk rename operations."""

    def validate(self, request: BulkRenameRequest) -> BulkRenameValidationResult: ...

    def execute(
        self,
        request: BulkRenameRequest,
        *,
        progress_callback: BulkRenameProgressCallback | None = None,
    ) -> BulkRenameExecutionResult: ...


@dataclass(frozen=True)
class LiveBulkRenameService:
    """Validate and apply a bulk rename with temporary staging."""

    adapter: FileOperationAdapter = field(default_factory=LocalFileOperationAdapter)

    def validate(self, request: BulkRenameRequest) -> BulkRenameValidationResult:
        parent = _absolute_path(request.parent_dir)
        targets = tuple(_normalized_target(target) for target in request.targets)
        parent_exists = self.adapter.path_exists(str(parent))
        parent_is_directory = parent_exists and parent.is_dir() and not parent.is_symlink()
        parent_key = _path_key(str(parent))
        existing_names: dict[str, str] = {}
        if parent_is_directory:
            try:
                with os.scandir(parent) as entries:
                    existing_names = {
                        _path_key(str(parent / entry.name)): entry.name for entry in entries
                    }
            except OSError:
                existing_names = {}

        source_keys = {_path_key(target.source_path) for target in targets}
        source_occurrences: dict[str, int] = {}
        for target in targets:
            key = _path_key(target.source_path)
            source_occurrences[key] = source_occurrences.get(key, 0) + 1
        changed_source_keys = {
            _path_key(target.source_path)
            for target in targets
            if Path(target.source_path).name != target.new_name
        }
        destination_keys: dict[str, int] = {}
        raw_items: list[BulkRenamePlanItem] = []
        for index, target in enumerate(targets):
            source = _absolute_path(target.source_path)
            old_name = source.name
            source_key = _path_key(str(source))
            error = (
                "A source entry is selected more than once"
                if source_occurrences[source_key] > 1
                else self._validate_target(
                    target,
                    source=source,
                    parent=parent,
                    parent_key=parent_key,
                    parent_is_directory=parent_is_directory,
                    source_keys=source_keys,
                    changed_source_keys=changed_source_keys,
                    existing_names=existing_names,
                    destination_keys=destination_keys,
                )
            )
            if error is not None:
                raw_items.append(
                    BulkRenamePlanItem(
                        source_path=str(source),
                        old_name=old_name,
                        new_name=target.new_name,
                        status="error",
                        message=error,
                    )
                )
                continue
            status = "unchanged" if old_name == target.new_name else "ready"
            raw_items.append(
                BulkRenamePlanItem(
                    source_path=str(source),
                    old_name=old_name,
                    new_name=target.new_name,
                    status=status,
                )
            )
            if status != "unchanged":
                destination_keys[_path_key(str(parent / target.new_name))] = index
        return BulkRenameValidationResult(items=tuple(raw_items))

    def _validate_target(
        self,
        target: BulkRenameTarget,
        *,
        source: Path,
        parent: Path,
        parent_key: str,
        parent_is_directory: bool,
        source_keys: set[str],
        changed_source_keys: set[str],
        existing_names: dict[str, str],
        destination_keys: dict[str, int],
    ) -> str | None:
        if not parent_is_directory:
            return f"Target directory does not exist: {parent}"
        if _path_key(str(source.parent)) != parent_key:
            return "All targets must be in the same directory"
        if not self.adapter.path_exists(str(source)):
            return f"Source does not exist: {source.name}"
        if not os.access(parent, os.W_OK | os.X_OK):
            return f"Permission denied for '{parent}'"
        if target.new_name in {".", ".."}:
            return "'.' and '..' are not valid names"
        if "/" in target.new_name or "\\" in target.new_name:
            return "Names cannot include path separators"
        name_error = validate_path_segment(target.new_name)
        if name_error is not None:
            return name_error

        if target.new_name == source.name:
            return None

        destination = parent / target.new_name
        destination_key = _path_key(str(destination))
        source_key = _path_key(str(source))
        if destination_key in destination_keys:
            return f"Duplicate destination name '{target.new_name}'"
        existing_name = existing_names.get(destination_key)
        if (
            existing_name is not None
            and destination_key not in changed_source_keys
            and destination_key != source_key
        ):
            return f"An entry named '{target.new_name}' already exists"
        # A destination that points to an unchanged selected source is still a
        # collision; a changed source is deliberately allowed for swaps/cycles.
        if destination_key in source_keys and destination_key not in changed_source_keys:
            return f"An unchanged entry named '{target.new_name}' already exists"
        return None

    def execute(
        self,
        request: BulkRenameRequest,
        *,
        progress_callback: BulkRenameProgressCallback | None = None,
    ) -> BulkRenameExecutionResult:
        validation = self.validate(request)
        if not validation.executable:
            return BulkRenameExecutionResult(
                validation=validation,
                message=_validation_message(validation),
            )

        changed = tuple(
            (index, item)
            for index, item in enumerate(validation.items)
            if item.status == "ready"
        )
        total = len(changed)
        staged: dict[int, str] = {}
        reserved = {_path_key(item.source_path) for _index, item in changed}
        reserved.update(
            _path_key(str(Path(item.source_path).parent / item.new_name))
            for _index, item in changed
        )

        for completed, (index, item) in enumerate(changed):
            if progress_callback is not None:
                progress_callback(completed, total, item.source_path)
            try:
                temp_path = self._temporary_path(Path(item.source_path).parent, reserved)
                self.adapter.move_path(item.source_path, temp_path)
            except OSError as error:
                failed = _replace_item(
                    validation.items,
                    index,
                    status="failed",
                    message=str(error) or "Failed to stage rename",
                )
                for staged_index in reversed(tuple(staged)):
                    staged_item = failed[staged_index]
                    failed = self._restore_staged_item(
                        staged,
                        staged_index,
                        staged_item,
                        failed,
                    )
                failed = _mark_unattempted(failed, changed, failed_index=index)
                return BulkRenameExecutionResult(
                    validation=BulkRenameValidationResult(items=failed),
                    rolled_back=not any(item.status == "recovery_failed" for item in failed),
                    message="Bulk rename failed while preparing names",
                )
            staged[index] = temp_path

        finalized: list[int] = []
        items = validation.items
        for completed, (index, item) in enumerate(changed, start=1):
            if progress_callback is not None:
                progress_callback(completed - 1, total, item.source_path)
            destination = str(Path(item.source_path).parent / item.new_name)
            try:
                self.adapter.move_path(staged[index], destination)
            except OSError as error:
                items = _replace_item(
                    items,
                    index,
                    status="failed",
                    message=str(error) or "Failed to apply rename",
                )
                items = self._rollback(items, staged, finalized)
                return BulkRenameExecutionResult(
                    validation=BulkRenameValidationResult(items=items),
                    rolled_back=not any(item.status == "recovery_failed" for item in items),
                    message="Bulk rename failed while applying names",
                )
            finalized.append(index)
            items = _replace_item(
                items,
                index,
                status="renamed",
                current_path=destination,
            )
            if progress_callback is not None:
                progress_callback(completed, total, destination)

        applied_changes = tuple(
            BulkRenameAppliedChange(
                source_path=item.source_path,
                destination_path=item.current_path or item.source_path,
            )
            for item in items
            if item.status == "renamed"
        )
        return BulkRenameExecutionResult(
            validation=BulkRenameValidationResult(items=items),
            applied_changes=applied_changes,
            message=f"Renamed {len(applied_changes)} item(s)",
        )

    def _temporary_path(self, parent: Path, reserved: set[str]) -> str:
        for _ in range(100):
            candidate = parent / f".zivo-rename-{uuid.uuid4().hex}"
            candidate_string = str(candidate)
            if (
                _path_key(candidate_string) not in reserved
                and not self.adapter.path_exists(candidate_string)
            ):
                reserved.add(_path_key(candidate_string))
                return candidate_string
        raise OSError("Could not allocate a temporary rename path")

    def _restore_staged_item(
        self,
        staged: dict[int, str],
        index: int,
        item: BulkRenamePlanItem,
        items: tuple[BulkRenamePlanItem, ...],
    ) -> tuple[BulkRenamePlanItem, ...]:
        try:
            self.adapter.move_path(staged[index], item.source_path)
        except OSError as error:
            return _replace_item(
                items,
                index,
                status="recovery_failed",
                message=str(error) or "Failed to restore original name",
            )
        return _replace_item(items, index, status="restored", current_path=item.source_path)

    def _rollback(
        self,
        items: tuple[BulkRenamePlanItem, ...],
        staged: dict[int, str],
        finalized: list[int],
    ) -> tuple[BulkRenamePlanItem, ...]:
        next_items = items
        for index in reversed(finalized):
            item = next_items[index]
            destination = item.current_path or str(Path(item.source_path).parent / item.new_name)
            try:
                self.adapter.move_path(destination, staged[index])
            except OSError as error:
                next_items = _replace_item(
                    next_items,
                    index,
                    status="recovery_failed",
                    message=str(error) or "Failed to stage rollback",
                )
                staged.pop(index, None)
            else:
                next_items = _replace_item(next_items, index, status="failed")
        for index in reversed(tuple(staged)):
            if next_items[index].status == "recovery_failed":
                continue
            prior = next_items[index]
            next_items = self._restore_staged_item(staged, index, prior, next_items)
            if prior.status == "failed" and next_items[index].status == "restored":
                next_items = _replace_item(
                    next_items,
                    index,
                    status="failed",
                    message=prior.message,
                    current_path=prior.source_path,
                )
        return next_items


@dataclass(frozen=True)
class FakeBulkRenameService:
    """Deterministic bulk rename service for reducer and app tests."""

    results: Mapping[BulkRenameRequest, BulkRenameExecutionResult] = field(default_factory=dict)
    failure_messages: Mapping[BulkRenameRequest, str] = field(default_factory=dict)
    default_delay_seconds: float = 0.0

    def validate(self, request: BulkRenameRequest) -> BulkRenameValidationResult:
        result = self.results.get(request)
        if result is not None:
            return result.validation
        return BulkRenameValidationResult(
            items=tuple(
                BulkRenamePlanItem(
                    source_path=target.source_path,
                    old_name=Path(target.source_path).name,
                    new_name=target.new_name,
                    status=(
                        "unchanged"
                        if Path(target.source_path).name == target.new_name
                        else "ready"
                    ),
                )
                for target in request.targets
            )
        )

    def execute(
        self,
        request: BulkRenameRequest,
        *,
        progress_callback: BulkRenameProgressCallback | None = None,
    ) -> BulkRenameExecutionResult:
        if self.default_delay_seconds > 0:
            sleep(self.default_delay_seconds)
        if request in self.failure_messages:
            raise OSError(self.failure_messages[request])
        result = self.results.get(request)
        if result is None:
            validation = self.validate(request)
            changed = tuple(
                item for item in validation.items if item.status == "ready"
            )
            items = tuple(
                _replace_plan_item(
                    item,
                    status="renamed",
                    current_path=str(Path(item.source_path).parent / item.new_name),
                )
                if item.status == "ready"
                else item
                for item in validation.items
            )
            result = BulkRenameExecutionResult(
                validation=BulkRenameValidationResult(items=items),
                applied_changes=tuple(
                    BulkRenameAppliedChange(
                        source_path=item.source_path,
                        destination_path=str(Path(item.source_path).parent / item.new_name),
                    )
                    for item in changed
                ),
                message=f"Renamed {len(changed)} item(s)",
            )
        if progress_callback is not None:
            total = len(request.targets)
            for index, target in enumerate(request.targets, start=1):
                progress_callback(index, total, target.source_path)
        return result


def _absolute_path(path: str) -> Path:
    return Path(os.path.abspath(os.path.expanduser(path)))


def _normalized_target(target: BulkRenameTarget) -> BulkRenameTarget:
    return BulkRenameTarget(
        source_path=str(_absolute_path(target.source_path)),
        new_name=target.new_name,
    )


def _path_key(path: str) -> str:
    normalized = os.path.normcase(os.path.abspath(path))
    if os.name == "nt" or platform.system() == "Darwin":
        return normalized.casefold()
    return normalized


def _replace_plan_item(
    item: BulkRenamePlanItem,
    *,
    status: str,
    message: str | None = None,
    current_path: str | None = None,
) -> BulkRenamePlanItem:
    return BulkRenamePlanItem(
        source_path=item.source_path,
        old_name=item.old_name,
        new_name=item.new_name,
        status=status,  # type: ignore[arg-type]
        message=item.message if message is None else message,
        current_path=item.current_path if current_path is None else current_path,
    )


def _replace_item(
    items: tuple[BulkRenamePlanItem, ...],
    index: int,
    *,
    status: str,
    message: str | None = None,
    current_path: str | None = None,
) -> tuple[BulkRenamePlanItem, ...]:
    updated = list(items)
    updated[index] = _replace_plan_item(
        updated[index],
        status=status,
        message=message,
        current_path=current_path,
    )
    return tuple(updated)


def _mark_unattempted(
    items: tuple[BulkRenamePlanItem, ...],
    changed: tuple[tuple[int, BulkRenamePlanItem], ...],
    *,
    failed_index: int,
) -> tuple[BulkRenamePlanItem, ...]:
    next_items = items
    for index, _item in changed:
        if index == failed_index or next_items[index].status != "ready":
            continue
        next_items = _replace_item(
            next_items,
            index,
            status="failed",
            message="Not attempted after an earlier rename failure",
        )
    return next_items


def _validation_message(validation: BulkRenameValidationResult) -> str:
    if validation.error_count:
        return f"Bulk rename has {validation.error_count} validation error(s)"
    return "No names have changed"
