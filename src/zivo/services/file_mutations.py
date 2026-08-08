"""Rename and create filesystem mutation service."""

import os
import stat
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath
from time import sleep
from typing import Mapping, Protocol

from zivo.adapters import FileOperationAdapter, LocalFileOperationAdapter
from zivo.models import (
    ChmodRequest,
    ChownRequest,
    CreatePathRequest,
    CreateSymlinkRequest,
    DeletePreparationResult,
    DeleteRequest,
    FileMutationResult,
    RecursiveChmodRequest,
    RecursiveChownRequest,
    RenameRequest,
)
from zivo.services.trash_operations import TrashService, resolve_trash_service

FileMutationRequest = (
    RenameRequest
    | CreatePathRequest
    | CreateSymlinkRequest
    | DeleteRequest
    | ChmodRequest
    | RecursiveChmodRequest
    | ChownRequest
    | RecursiveChownRequest
)


class FileMutationService(Protocol):
    """Boundary for asynchronous rename/create/delete operations."""

    def execute(
        self,
        request: FileMutationRequest,
    ) -> FileMutationResult: ...

    def prepare_delete(self, request: DeleteRequest) -> DeletePreparationResult: ...


@dataclass(frozen=True)
class LiveFileMutationService:
    """Execute rename/create/delete operations on the local filesystem."""

    adapter: FileOperationAdapter = field(default_factory=LocalFileOperationAdapter)
    trash_service: TrashService = field(default_factory=resolve_trash_service)

    def execute(
        self,
        request: FileMutationRequest,
    ) -> FileMutationResult:
        if isinstance(request, RenameRequest):
            return self._execute_rename(request)
        if isinstance(request, CreateSymlinkRequest):
            return self._execute_symlink(request)
        if isinstance(request, DeleteRequest):
            return self._execute_delete(request)
        if isinstance(request, ChmodRequest):
            return self._execute_chmod(request)
        if isinstance(request, RecursiveChmodRequest):
            return self._execute_recursive_chmod(request)
        if isinstance(request, ChownRequest):
            return self._execute_chown(request)
        if isinstance(request, RecursiveChownRequest):
            return self._execute_recursive_chown(request)
        return self._execute_create(request)

    def prepare_delete(self, request: DeleteRequest) -> DeletePreparationResult:
        """Collect size and target-kind metadata without following symlinks."""

        total_size_bytes = 0
        contains_directory = False
        failed_paths: list[str] = []
        for path in request.paths:
            size_bytes, is_directory, failures = _measure_delete_path(Path(path))
            total_size_bytes += size_bytes
            contains_directory = contains_directory or is_directory
            failed_paths.extend(failures)
        return DeletePreparationResult(
            request=request,
            total_size_bytes=total_size_bytes,
            contains_directory=contains_directory,
            failed_paths=tuple(dict.fromkeys(failed_paths)),
        )

    def _execute_rename(self, request: RenameRequest) -> FileMutationResult:
        source_path = _absolute_entry_path(request.source_path)
        destination_path = source_path.parent / request.new_name
        self.adapter.move_path(str(source_path), str(destination_path))
        return FileMutationResult(
            path=str(destination_path),
            message=f"Renamed to {request.new_name}",
            operation="rename",
            source_path=str(source_path),
        )

    def _execute_create(self, request: CreatePathRequest) -> FileMutationResult:
        target_path = _resolve_create_target(request.parent_dir, request.name)
        created_parents = self._create_missing_parent_directories(target_path)
        if request.kind == "file":
            try:
                self.adapter.create_file(str(target_path))
            except OSError as error:
                raise _create_error_with_created_parents(error, created_parents) from error
            message = f"Created file {request.name}"
        else:
            try:
                self.adapter.create_directory(str(target_path))
            except OSError as error:
                raise _create_error_with_created_parents(error, created_parents) from error
            message = f"Created directory {request.name}"
        return FileMutationResult(path=str(target_path), message=message)

    def _create_missing_parent_directories(self, target_path: Path) -> tuple[Path, ...]:
        """Create absent ancestors only; never roll back paths created before an error."""

        missing: list[Path] = []
        parent = target_path.parent
        while not parent.exists():
            missing.append(parent)
            parent = parent.parent
        if not parent.is_dir():
            raise OSError(f"Target parent is not a directory: {parent}")
        created: list[Path] = []
        try:
            for directory in reversed(missing):
                directory.mkdir()
                created.append(directory)
        except OSError as error:
            raise _create_error_with_created_parents(error, tuple(created)) from error
        return tuple(created)

    def _execute_symlink(self, request: CreateSymlinkRequest) -> FileMutationResult:
        source_path = _absolute_entry_path(request.source_path)
        destination_path = _absolute_entry_path(request.destination_path)
        self.adapter.create_symlink(
            str(source_path),
            str(destination_path),
            overwrite=request.overwrite,
        )
        return FileMutationResult(
            path=str(destination_path),
            message=f"Created symlink {destination_path.name}",
            operation="symlink",
            source_path=str(source_path),
        )

    def _execute_delete(self, request: DeleteRequest) -> FileMutationResult:
        removed_paths: list[str] = []
        failures: list[tuple[str, str]] = []
        trash_records = []

        for path in request.paths:
            try:
                if request.mode == "trash":
                    trash_record = self.trash_service.capture_restorable_trash(
                        path,
                        lambda current_path=path: self.adapter.send_to_trash(current_path),
                    )
                    if trash_record is not None:
                        trash_records.append(trash_record)
                else:
                    self.adapter.remove_path(path)
            except OSError as error:
                fallback_message = "Trash failed" if request.mode == "trash" else "Delete failed"
                failures.append((path, str(error) or fallback_message))
            else:
                removed_paths.append(path)

        if not removed_paths:
            if len(failures) == 1:
                failed_path = Path(failures[0][0]).name
                if request.mode == "trash":
                    raise OSError(f"Failed to trash {failed_path}: {failures[0][1]}")
                raise OSError(f"Failed to permanently delete {failed_path}: {failures[0][1]}")
            if request.mode == "trash":
                raise OSError(f"Failed to trash {len(failures)} items")
            raise OSError(f"Failed to permanently delete {len(failures)} items")

        if failures:
            message = (
                f"Trashed {len(removed_paths)}/{len(request.paths)} items"
                f" with {len(failures)} failure(s)"
                if request.mode == "trash"
                else (
                    f"Deleted {len(removed_paths)}/{len(request.paths)} items permanently"
                    f" with {len(failures)} failure(s)"
                )
            )
            return FileMutationResult(
                path=None,
                message=message,
                level="warning",
                removed_paths=tuple(removed_paths),
                operation="delete",
                delete_mode=request.mode,
                trash_records=tuple(trash_records),
            )

        noun = "item" if len(removed_paths) == 1 else "items"
        message = (
            f"Trashed {len(removed_paths)} {noun}"
            if request.mode == "trash"
            else f"Deleted {len(removed_paths)} {noun} permanently"
        )
        return FileMutationResult(
            path=None,
            message=message,
            removed_paths=tuple(removed_paths),
            operation="delete",
            delete_mode=request.mode,
            trash_records=tuple(trash_records),
        )

    def _execute_chmod(self, request: ChmodRequest) -> FileMutationResult:
        changed_paths: list[str] = []
        failures: list[tuple[str, str]] = []

        for path in request.paths:
            target_path = _absolute_entry_path(path)
            try:
                self.adapter.change_permissions(str(target_path), request.mode)
            except OSError as error:
                failures.append((str(target_path), str(error) or "Permission change failed"))
            else:
                changed_paths.append(str(target_path))

        if not changed_paths:
            if len(failures) == 1:
                failed_name = Path(failures[0][0]).name
                raise OSError(f"Failed to change permissions for {failed_name}: {failures[0][1]}")
            if failures:
                raise OSError(f"Failed to change permissions for {len(failures)} items")
            raise OSError("Change permissions requires at least one target")

        if failures:
            return FileMutationResult(
                path=None,
                message=(
                    f"Changed permissions to {request.mode:03o} for "
                    f"{len(changed_paths)}/{len(changed_paths) + len(failures)} items "
                    f"with {len(failures)} failure(s)"
                ),
                level="warning",
                operation="chmod",
            )

        if len(changed_paths) == 1:
            return FileMutationResult(
                path=changed_paths[0],
                message=f"Changed permissions to {request.mode:03o}",
                operation="chmod",
            )

        noun = "item" if len(changed_paths) == 1 else "items"
        return FileMutationResult(
            path=None,
            message=f"Changed permissions to {request.mode:03o} for {len(changed_paths)} {noun}",
            operation="chmod",
        )

    def _execute_recursive_chmod(self, request: RecursiveChmodRequest) -> FileMutationResult:
        changed_paths: list[str] = []
        failures: list[tuple[str, str]] = []

        for target_path in _iter_recursive_chmod_targets(request.paths):
            try:
                self.adapter.change_permissions(str(target_path), request.mode)
            except OSError as error:
                failures.append((str(target_path), str(error) or "Permission change failed"))
            else:
                changed_paths.append(str(target_path))

        if not changed_paths:
            if len(failures) == 1:
                failed_name = Path(failures[0][0]).name
                raise OSError(f"Failed to change permissions for {failed_name}: {failures[0][1]}")
            if failures:
                raise OSError(f"Failed to change permissions for {len(failures)} items")
            raise OSError("No files matched recursive permissions change")

        if failures:
            return FileMutationResult(
                path=None,
                message=(
                    f"Changed permissions to {request.mode:03o} for "
                    f"{len(changed_paths)}/{len(changed_paths) + len(failures)} items "
                    f"with {len(failures)} failure(s)"
                ),
                level="warning",
                operation="chmod",
            )

        noun = "item" if len(changed_paths) == 1 else "items"
        return FileMutationResult(
            path=str(_absolute_entry_path(request.paths[0])) if request.paths else None,
            message=f"Changed permissions to {request.mode:03o} for {len(changed_paths)} {noun}",
            operation="chmod",
        )

    def _execute_chown(self, request: ChownRequest) -> FileMutationResult:
        changed_paths: list[str] = []
        failures: list[tuple[str, str]] = []

        for path in request.paths:
            target_path = _absolute_entry_path(path)
            try:
                self.adapter.change_owner(str(target_path), request.owner, request.group)
            except OSError as error:
                failures.append((str(target_path), str(error) or "Owner change failed"))
            else:
                changed_paths.append(str(target_path))

        return _build_chown_result(
            changed_paths=changed_paths,
            failures=failures,
            owner=request.owner,
            group=request.group,
            empty_message="Change owner requires at least one target",
            result_path=None,
        )

    def _execute_recursive_chown(self, request: RecursiveChownRequest) -> FileMutationResult:
        changed_paths: list[str] = []
        failures: list[tuple[str, str]] = []

        for target_path in _iter_recursive_mutation_targets(request.paths):
            try:
                self.adapter.change_owner(str(target_path), request.owner, request.group)
            except OSError as error:
                failures.append((str(target_path), str(error) or "Owner change failed"))
            else:
                changed_paths.append(str(target_path))

        return _build_chown_result(
            changed_paths=changed_paths,
            failures=failures,
            owner=request.owner,
            group=request.group,
            empty_message="No files matched recursive owner change",
            result_path=str(_absolute_entry_path(request.paths[0])) if request.paths else None,
        )


@dataclass(frozen=True)
class FakeFileMutationService:
    """Deterministic file-mutation service used by tests."""

    results: Mapping[
        FileMutationRequest,
        FileMutationResult,
    ] = field(default_factory=dict)
    failure_messages: Mapping[
        FileMutationRequest,
        str,
    ] = field(default_factory=dict)
    preparation_results: Mapping[DeleteRequest, DeletePreparationResult] = field(
        default_factory=dict
    )
    preparation_failure_messages: Mapping[DeleteRequest, str] = field(default_factory=dict)
    default_delay_seconds: float = 0.0

    def prepare_delete(self, request: DeleteRequest) -> DeletePreparationResult:
        if self.default_delay_seconds > 0:
            sleep(self.default_delay_seconds)
        if request in self.preparation_failure_messages:
            raise OSError(self.preparation_failure_messages[request])
        return self.preparation_results.get(
            request,
            DeletePreparationResult(
                request=request,
                total_size_bytes=0,
                contains_directory=False,
            ),
        )

    def execute(
        self,
        request: FileMutationRequest,
    ) -> FileMutationResult:
        if self.default_delay_seconds > 0:
            sleep(self.default_delay_seconds)

        if request in self.failure_messages:
            raise OSError(self.failure_messages[request])

        result = self.results.get(request)
        if result is not None:
            return result

        if isinstance(request, RenameRequest):
            source_path = _absolute_entry_path(request.source_path)
            return FileMutationResult(
                path=str(source_path.parent / request.new_name),
                message=f"Renamed to {request.new_name}",
                operation="rename",
                source_path=str(source_path),
            )

        if isinstance(request, CreateSymlinkRequest):
            destination_path = _absolute_entry_path(request.destination_path)
            return FileMutationResult(
                path=str(destination_path),
                message=f"Created symlink {destination_path.name}",
                operation="symlink",
                source_path=str(_absolute_entry_path(request.source_path)),
            )

        if isinstance(request, DeleteRequest):
            noun = "item" if len(request.paths) == 1 else "items"
            message = (
                f"Trashed {len(request.paths)} {noun}"
                if request.mode == "trash"
                else f"Deleted {len(request.paths)} {noun} permanently"
            )
            return FileMutationResult(
                path=None,
                message=message,
                removed_paths=request.paths,
                operation="delete",
                delete_mode=request.mode,
            )

        if isinstance(request, ChmodRequest):
            target_path = _absolute_entry_path(request.paths[0]) if request.paths else None
            if len(request.paths) == 1:
                message = f"Changed permissions to {request.mode:03o}"
            else:
                noun = "item" if len(request.paths) == 1 else "items"
                message = (
                    f"Changed permissions to {request.mode:03o} "
                    f"for {len(request.paths)} {noun}"
                )
            return FileMutationResult(
                path=str(target_path) if target_path is not None else None,
                message=message,
                operation="chmod",
            )

        if isinstance(request, RecursiveChmodRequest):
            noun = "item" if len(request.paths) == 1 else "items"
            return FileMutationResult(
                path=str(_absolute_entry_path(request.paths[0])) if request.paths else None,
                message=(
                    f"Changed permissions to {request.mode:03o} "
                    f"for {len(request.paths)} {noun}"
                ),
                operation="chmod",
            )

        if isinstance(request, ChownRequest | RecursiveChownRequest):
            noun = "item" if len(request.paths) == 1 else "items"
            suffix = "" if len(request.paths) == 1 else f" for {len(request.paths)} {noun}"
            owner_group = _format_owner_group(request.owner, request.group)
            return FileMutationResult(
                path=str(_absolute_entry_path(request.paths[0])) if request.paths else None,
                message=f"Changed owner to {owner_group}{suffix}",
                operation="chown",
            )

        target_path = _absolute_entry_path(request.parent_dir) / request.name
        message = (
            f"Created file {request.name}"
            if request.kind == "file"
            else f"Created directory {request.name}"
        )
        return FileMutationResult(path=str(target_path), message=message, operation="create")


def _absolute_entry_path(path: str) -> Path:
    return Path(os.path.abspath(os.path.expanduser(path)))


def _measure_delete_path(path: Path) -> tuple[int, bool, tuple[str, ...]]:
    """Return content size, directory presence, and unreadable paths."""

    try:
        path_stat = path.lstat()
    except OSError:
        return 0, False, (str(path),)

    if stat.S_ISLNK(path_stat.st_mode) or not stat.S_ISDIR(path_stat.st_mode):
        return path_stat.st_size, False, ()

    total_size = 0
    failures: list[str] = []
    try:
        with os.scandir(path) as iterator:
            for entry in iterator:
                child_size, _contains_directory, child_failures = _measure_delete_path(
                    Path(entry.path)
                )
                total_size += child_size
                failures.extend(child_failures)
    except OSError:
        failures.append(str(path))
    return total_size, True, tuple(failures)


def _iter_recursive_chmod_targets(paths: tuple[str, ...]) -> tuple[Path, ...]:
    return _iter_recursive_mutation_targets(paths)


def _iter_recursive_mutation_targets(paths: tuple[str, ...]) -> tuple[Path, ...]:
    targets: list[Path] = []
    for path in paths:
        root = _absolute_entry_path(path)
        if root.is_symlink():
            continue
        targets.append(root)
        if root.is_dir():
            for current_root, dirnames, filenames in os.walk(root, followlinks=False):
                current_path = Path(current_root)
                dirnames[:] = [
                    dirname
                    for dirname in dirnames
                    if not (current_path / dirname).is_symlink()
                ]
                for dirname in dirnames:
                    targets.append(current_path / dirname)
                for filename in filenames:
                    child = current_path / filename
                    if not child.is_symlink():
                        targets.append(child)
    return tuple(targets)


def _format_owner_group(owner: str | None, group: str | None) -> str:
    if owner is not None and group is not None:
        return f"{owner}:{group}"
    if owner is not None:
        return owner
    if group is not None:
        return f":{group}"
    return "<unchanged>"


def _create_error_with_created_parents(
    error: OSError, created_parents: tuple[Path, ...]
) -> OSError:
    """Preserve an execution error while telling the user which parents remain."""

    if not created_parents:
        return OSError(str(error) or "Create failed")
    paths = ", ".join(str(path) for path in created_parents)
    return OSError(f"{str(error) or 'Create failed'}; created parent directories: {paths}")


def _resolve_create_target(parent_dir: str, name: str) -> Path:
    """Defend the mutation boundary against absolute and escaping create paths."""

    if Path(name).is_absolute() or PureWindowsPath(name).is_absolute():
        raise OSError("Name or path must be relative")
    base_path = _absolute_entry_path(parent_dir)
    target_path = Path(os.path.abspath(base_path / name))
    try:
        target_path.relative_to(base_path)
    except ValueError as error:
        raise OSError("Name or path must stay within the current directory") from error
    try:
        target_path.resolve(strict=False).relative_to(base_path.resolve(strict=False))
    except ValueError as error:
        raise OSError("Name or path must stay within the current directory") from error
    return target_path


def _build_chown_result(
    *,
    changed_paths: list[str],
    failures: list[tuple[str, str]],
    owner: str | None,
    group: str | None,
    empty_message: str,
    result_path: str | None,
) -> FileMutationResult:
    owner_group = _format_owner_group(owner, group)

    if not changed_paths:
        if len(failures) == 1:
            failed_name = Path(failures[0][0]).name
            raise OSError(f"Failed to change owner for {failed_name}: {failures[0][1]}")
        if failures:
            raise OSError(f"Failed to change owner for {len(failures)} items")
        raise OSError(empty_message)

    if failures:
        return FileMutationResult(
            path=None,
            message=(
                f"Changed owner to {owner_group} for "
                f"{len(changed_paths)}/{len(changed_paths) + len(failures)} items "
                f"with {len(failures)} failure(s)"
            ),
            level="warning",
            operation="chown",
        )

    if len(changed_paths) == 1:
        return FileMutationResult(
            path=changed_paths[0],
            message=f"Changed owner to {owner_group}",
            operation="chown",
        )

    noun = "item" if len(changed_paths) == 1 else "items"
    return FileMutationResult(
        path=result_path,
        message=f"Changed owner to {owner_group} for {len(changed_paths)} {noun}",
        operation="chown",
    )
