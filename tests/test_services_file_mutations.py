import os
from dataclasses import dataclass, field
from stat import S_IMODE

import pytest

from zivo.models import (
    ChmodRequest,
    ChownRequest,
    CreatePathRequest,
    CreateSymlinkRequest,
    DeleteRequest,
    RecursiveChmodRequest,
    RecursiveChownRequest,
    RenameRequest,
)
from zivo.services import LiveFileMutationService
from zivo.services.trash_operations import WindowsTrashService


def _absolute(path: str) -> str:
    return os.path.abspath(os.path.expanduser(path))


@dataclass
class StubFileOperationAdapter:
    deleted_paths: list[str] = field(default_factory=list)
    trashed_paths: list[str] = field(default_factory=list)
    failing_paths: set[str] = field(default_factory=set)
    moved_paths: list[tuple[str, str]] = field(default_factory=list)
    created_files: list[str] = field(default_factory=list)
    created_directories: list[str] = field(default_factory=list)
    created_symlinks: list[tuple[str, str, bool]] = field(default_factory=list)
    changed_permissions: list[tuple[str, int]] = field(default_factory=list)
    changed_owners: list[tuple[str, str | None, str | None]] = field(default_factory=list)

    def path_exists(self, path: str) -> bool:
        return False

    def paths_are_same(self, source: str, destination: str) -> bool:
        return source == destination

    def remove_path(self, path: str) -> None:
        if path in self.failing_paths:
            raise OSError("permission denied")
        self.deleted_paths.append(path)

    def copy_path(self, source: str, destination: str) -> None:
        raise NotImplementedError

    def move_path(self, source: str, destination: str) -> None:
        if source in self.failing_paths or destination in self.failing_paths:
            raise OSError("rename failed")
        self.moved_paths.append((source, destination))

    def generate_renamed_path(self, destination: str) -> str:
        raise NotImplementedError

    def create_file(self, path: str) -> None:
        if path in self.failing_paths:
            raise OSError("file creation failed")
        self.created_files.append(path)

    def create_directory(self, path: str) -> None:
        if path in self.failing_paths:
            raise OSError("directory creation failed")
        self.created_directories.append(path)

    def create_symlink(self, source: str, destination: str, *, overwrite: bool = False) -> None:
        if source in self.failing_paths or destination in self.failing_paths:
            raise OSError("symlink creation failed")
        self.created_symlinks.append((source, destination, overwrite))

    def change_permissions(self, path: str, mode: int) -> None:
        if path in self.failing_paths:
            raise OSError("chmod failed")
        self.changed_permissions.append((path, mode))

    def change_owner(self, path: str, owner: str | None, group: str | None) -> None:
        if path in self.failing_paths:
            raise OSError("chown failed")
        self.changed_owners.append((path, owner, group))

    def send_to_trash(self, path: str) -> None:
        if path in self.failing_paths:
            raise OSError("permission denied")
        self.trashed_paths.append(path)


def test_file_mutation_service_trashes_single_path() -> None:
    adapter = StubFileOperationAdapter()
    service = LiveFileMutationService(adapter=adapter)

    result = service.execute(
        DeleteRequest(paths=("/tmp/zivo/docs",), mode="trash")
    )

    assert adapter.trashed_paths == ["/tmp/zivo/docs"]
    assert result.message == "Moved 1 item to trash"
    assert result.removed_paths == ("/tmp/zivo/docs",)


def test_file_mutation_service_does_not_create_trash_restore_record_on_windows() -> None:
    adapter = StubFileOperationAdapter()
    service = LiveFileMutationService(
        adapter=adapter,
        trash_service=WindowsTrashService(),
    )

    result = service.execute(DeleteRequest(paths=("C:/Users/test/docs",), mode="trash"))

    assert adapter.trashed_paths == ["C:/Users/test/docs"]
    assert result.trash_records == ()


def test_file_mutation_service_renames_single_path() -> None:
    adapter = StubFileOperationAdapter()
    service = LiveFileMutationService(adapter=adapter)

    result = service.execute(
        RenameRequest(source_path="/tmp/zivo/docs", new_name="docs-old")
    )

    assert adapter.moved_paths == [(_absolute("/tmp/zivo/docs"), _absolute("/tmp/zivo/docs-old"))]
    assert result.path == _absolute("/tmp/zivo/docs-old")
    assert result.message == "Renamed to docs-old"


@pytest.mark.skipif(os.name == "nt", reason="symlink creation requires extra Windows privileges")
def test_file_mutation_service_renames_symlink_without_following_target(tmp_path) -> None:
    target = tmp_path / "target.txt"
    target.write_text("secret\n", encoding="utf-8")
    link = tmp_path / "link.txt"
    link.symlink_to(target)
    service = LiveFileMutationService()

    result = service.execute(
        RenameRequest(source_path=str(link), new_name="renamed-link.txt")
    )

    renamed = tmp_path / "renamed-link.txt"
    assert link.exists() is False
    assert renamed.is_symlink()
    assert target.exists()
    assert result.path == str(renamed)
    assert result.message == "Renamed to renamed-link.txt"


def test_file_mutation_service_raises_rename_error() -> None:
    adapter = StubFileOperationAdapter(failing_paths={_absolute("/tmp/zivo/docs-old")})
    service = LiveFileMutationService(adapter=adapter)

    with pytest.raises(OSError, match="rename failed"):
        service.execute(RenameRequest(source_path="/tmp/zivo/docs", new_name="docs-old"))


def test_file_mutation_service_creates_file() -> None:
    adapter = StubFileOperationAdapter()
    service = LiveFileMutationService(adapter=adapter)

    result = service.execute(
        CreatePathRequest(parent_dir="/tmp/zivo", name="README.md", kind="file")
    )

    assert adapter.created_files == [_absolute("/tmp/zivo/README.md")]
    assert result.path == _absolute("/tmp/zivo/README.md")
    assert result.message == "Created file README.md"


def test_file_mutation_service_creates_directory() -> None:
    adapter = StubFileOperationAdapter()
    service = LiveFileMutationService(adapter=adapter)

    result = service.execute(CreatePathRequest(parent_dir="/tmp/zivo", name="docs", kind="dir"))

    assert adapter.created_directories == [_absolute("/tmp/zivo/docs")]
    assert result.path == _absolute("/tmp/zivo/docs")
    assert result.message == "Created directory docs"


def test_file_mutation_service_creates_symlink() -> None:
    adapter = StubFileOperationAdapter()
    service = LiveFileMutationService(adapter=adapter)

    result = service.execute(
        CreateSymlinkRequest(
            source_path="/tmp/zivo/docs",
            destination_path="/tmp/zivo/docs.link",
        )
    )

    assert adapter.created_symlinks == [
        (_absolute("/tmp/zivo/docs"), _absolute("/tmp/zivo/docs.link"), False)
    ]
    assert result.path == _absolute("/tmp/zivo/docs.link")
    assert result.message == "Created symlink docs.link"


def test_file_mutation_service_changes_permissions() -> None:
    adapter = StubFileOperationAdapter()
    service = LiveFileMutationService(adapter=adapter)

    result = service.execute(ChmodRequest(paths=("/tmp/zivo/run.sh",), mode=0o755))

    assert adapter.changed_permissions == [(_absolute("/tmp/zivo/run.sh"), 0o755)]
    assert result.path == _absolute("/tmp/zivo/run.sh")
    assert result.message == "Changed permissions to 755"
    assert result.operation == "chmod"


def test_file_mutation_service_raises_chmod_error() -> None:
    adapter = StubFileOperationAdapter(failing_paths={_absolute("/tmp/zivo/run.sh")})
    service = LiveFileMutationService(adapter=adapter)

    with pytest.raises(OSError, match="Failed to change permissions for run.sh: chmod failed"):
        service.execute(ChmodRequest(paths=("/tmp/zivo/run.sh",), mode=0o755))


def test_file_mutation_service_changes_permissions_for_multiple_paths() -> None:
    adapter = StubFileOperationAdapter()
    service = LiveFileMutationService(adapter=adapter)

    result = service.execute(
        ChmodRequest(paths=("/tmp/zivo/run.sh", "/tmp/zivo/build.sh"), mode=0o755)
    )

    assert adapter.changed_permissions == [
        (_absolute("/tmp/zivo/run.sh"), 0o755),
        (_absolute("/tmp/zivo/build.sh"), 0o755),
    ]
    assert result.path is None
    assert result.message == "Changed permissions to 755 for 2 items"
    assert result.operation == "chmod"


def test_file_mutation_service_chmod_reports_partial_failures() -> None:
    adapter = StubFileOperationAdapter(failing_paths={_absolute("/tmp/zivo/build.sh")})
    service = LiveFileMutationService(adapter=adapter)

    result = service.execute(
        ChmodRequest(paths=("/tmp/zivo/run.sh", "/tmp/zivo/build.sh"), mode=0o755)
    )

    assert adapter.changed_permissions == [(_absolute("/tmp/zivo/run.sh"), 0o755)]
    assert result.level == "warning"
    assert result.message == "Changed permissions to 755 for 1/2 items with 1 failure(s)"


def test_file_mutation_service_changes_owner() -> None:
    adapter = StubFileOperationAdapter()
    service = LiveFileMutationService(adapter=adapter)

    result = service.execute(
        ChownRequest(paths=("/tmp/zivo/run.sh",), owner="alice", group="staff")
    )

    assert adapter.changed_owners == [(_absolute("/tmp/zivo/run.sh"), "alice", "staff")]
    assert result.path == _absolute("/tmp/zivo/run.sh")
    assert result.message == "Changed owner to alice:staff"
    assert result.operation == "chown"


def test_file_mutation_service_changes_group_only() -> None:
    adapter = StubFileOperationAdapter()
    service = LiveFileMutationService(adapter=adapter)

    result = service.execute(ChownRequest(paths=("/tmp/zivo/run.sh",), group="staff"))

    assert adapter.changed_owners == [(_absolute("/tmp/zivo/run.sh"), None, "staff")]
    assert result.message == "Changed owner to :staff"


def test_file_mutation_service_changes_owner_for_multiple_paths() -> None:
    adapter = StubFileOperationAdapter()
    service = LiveFileMutationService(adapter=adapter)

    result = service.execute(
        ChownRequest(
            paths=("/tmp/zivo/run.sh", "/tmp/zivo/build.sh"),
            owner="alice",
            group=None,
        )
    )

    assert adapter.changed_owners == [
        (_absolute("/tmp/zivo/run.sh"), "alice", None),
        (_absolute("/tmp/zivo/build.sh"), "alice", None),
    ]
    assert result.path is None
    assert result.message == "Changed owner to alice for 2 items"
    assert result.operation == "chown"


def test_file_mutation_service_chown_reports_partial_failures() -> None:
    adapter = StubFileOperationAdapter(failing_paths={_absolute("/tmp/zivo/build.sh")})
    service = LiveFileMutationService(adapter=adapter)

    result = service.execute(
        ChownRequest(
            paths=("/tmp/zivo/run.sh", "/tmp/zivo/build.sh"),
            owner="alice",
        )
    )

    assert adapter.changed_owners == [(_absolute("/tmp/zivo/run.sh"), "alice", None)]
    assert result.level == "warning"
    assert result.message == "Changed owner to alice for 1/2 items with 1 failure(s)"


@pytest.mark.skipif(os.name == "nt", reason="symlink handling differs on Windows")
def test_file_mutation_service_recursive_chown_skips_symlinks(tmp_path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    ok_file = root / "ok.txt"
    ok_file.write_text("ok\n", encoding="utf-8")
    target = tmp_path / "target"
    target.mkdir()
    link = root / "target-link"
    link.symlink_to(target, target_is_directory=True)
    adapter = StubFileOperationAdapter()
    service = LiveFileMutationService(adapter=adapter)

    result = service.execute(RecursiveChownRequest(paths=(str(root),), group="staff"))

    assert adapter.changed_owners == [
        (str(root), None, "staff"),
        (str(ok_file), None, "staff"),
    ]
    assert result.message == "Changed owner to :staff for 2 items"


@pytest.mark.skipif(os.name == "nt", reason="chown is not supported on native Windows")
def test_file_mutation_service_recursive_chown_reports_partial_failures(tmp_path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    ok_file = root / "ok.txt"
    ok_file.write_text("ok\n", encoding="utf-8")
    failing_file = root / "fail.txt"
    failing_file.write_text("fail\n", encoding="utf-8")
    adapter = StubFileOperationAdapter(failing_paths={str(failing_file)})
    service = LiveFileMutationService(adapter=adapter)

    result = service.execute(RecursiveChownRequest(paths=(str(root),), owner="alice"))

    assert result.level == "warning"
    assert result.message == "Changed owner to alice for 2/3 items with 1 failure(s)"
    assert (str(root), "alice", None) in adapter.changed_owners
    assert (str(ok_file), "alice", None) in adapter.changed_owners


@pytest.mark.skipif(os.name == "nt", reason="chmod is not supported on native Windows")
def test_file_mutation_service_changes_permissions_recursively(tmp_path) -> None:
    root = tmp_path / "project"
    nested = root / "src"
    nested.mkdir(parents=True)
    script = nested / "run.sh"
    script.write_text("#!/bin/sh\n", encoding="utf-8")
    readme = root / "README.md"
    readme.write_text("docs\n", encoding="utf-8")
    service = LiveFileMutationService()

    result = service.execute(RecursiveChmodRequest(paths=(str(root),), mode=0o700))

    assert S_IMODE(root.stat().st_mode) == 0o700
    assert S_IMODE(nested.stat().st_mode) == 0o700
    assert S_IMODE(script.stat().st_mode) == 0o700
    assert S_IMODE(readme.stat().st_mode) == 0o700
    assert result.message == "Changed permissions to 700 for 4 items"
    assert result.operation == "chmod"


@pytest.mark.skipif(os.name == "nt", reason="symlink handling differs on Windows")
def test_file_mutation_service_recursive_chmod_skips_symlinks(tmp_path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    target = tmp_path / "target"
    target.mkdir()
    target_file = target / "secret.txt"
    target_file.write_text("secret\n", encoding="utf-8")
    link = root / "target-link"
    link.symlink_to(target, target_is_directory=True)
    service = LiveFileMutationService()
    original_target_mode = S_IMODE(target.stat().st_mode)
    original_file_mode = S_IMODE(target_file.stat().st_mode)

    result = service.execute(RecursiveChmodRequest(paths=(str(root),), mode=0o700))

    assert S_IMODE(root.stat().st_mode) == 0o700
    assert S_IMODE(target.stat().st_mode) == original_target_mode
    assert S_IMODE(target_file.stat().st_mode) == original_file_mode
    assert result.message == "Changed permissions to 700 for 1 item"


@pytest.mark.skipif(os.name == "nt", reason="chmod is not supported on native Windows")
def test_file_mutation_service_recursive_chmod_reports_partial_failures(tmp_path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    ok_file = root / "ok.txt"
    ok_file.write_text("ok\n", encoding="utf-8")
    failing_file = root / "fail.txt"
    failing_file.write_text("fail\n", encoding="utf-8")
    adapter = StubFileOperationAdapter(failing_paths={str(failing_file)})
    service = LiveFileMutationService(adapter=adapter)

    result = service.execute(RecursiveChmodRequest(paths=(str(root),), mode=0o700))

    assert result.level == "warning"
    assert result.message == "Changed permissions to 700 for 2/3 items with 1 failure(s)"
    assert (str(root), 0o700) in adapter.changed_permissions
    assert (str(ok_file), 0o700) in adapter.changed_permissions


@pytest.mark.skipif(os.name == "nt", reason="chmod is not supported on native Windows")
def test_file_mutation_service_recursive_chmod_raises_when_all_targets_fail(tmp_path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    adapter = StubFileOperationAdapter(failing_paths={str(root)})
    service = LiveFileMutationService(adapter=adapter)

    with pytest.raises(OSError, match="Failed to change permissions for project"):
        service.execute(RecursiveChmodRequest(paths=(str(root),), mode=0o700))


@pytest.mark.skipif(os.name == "nt", reason="symlink creation requires extra Windows privileges")
def test_file_mutation_service_creates_relative_symlink_on_disk(tmp_path) -> None:
    target = tmp_path / "docs"
    target.mkdir()
    destination = tmp_path / "docs.link"
    service = LiveFileMutationService()

    result = service.execute(
        CreateSymlinkRequest(source_path=str(target), destination_path=str(destination))
    )

    assert destination.is_symlink()
    assert os.readlink(destination) == "docs"
    assert destination.resolve() == target.resolve()
    assert result.path == str(destination)


@pytest.mark.skipif(os.name == "nt", reason="symlink creation requires extra Windows privileges")
def test_file_mutation_service_overwrites_existing_symlink_destination(tmp_path) -> None:
    target = tmp_path / "docs"
    target.mkdir()
    other = tmp_path / "other"
    other.mkdir()
    destination = tmp_path / "docs.link"
    destination.symlink_to(other)
    service = LiveFileMutationService()

    service.execute(
        CreateSymlinkRequest(
            source_path=str(target),
            destination_path=str(destination),
            overwrite=True,
        )
    )

    assert destination.is_symlink()
    assert destination.resolve() == target.resolve()


def test_file_mutation_service_raises_create_file_error() -> None:
    adapter = StubFileOperationAdapter(failing_paths={_absolute("/tmp/zivo/README.md")})
    service = LiveFileMutationService(adapter=adapter)

    with pytest.raises(OSError, match="file creation failed"):
        service.execute(CreatePathRequest(parent_dir="/tmp/zivo", name="README.md", kind="file"))


def test_file_mutation_service_raises_create_directory_error() -> None:
    adapter = StubFileOperationAdapter(failing_paths={_absolute("/tmp/zivo/docs")})
    service = LiveFileMutationService(adapter=adapter)

    with pytest.raises(OSError, match="directory creation failed"):
        service.execute(CreatePathRequest(parent_dir="/tmp/zivo", name="docs", kind="dir"))


def test_file_mutation_service_creates_missing_parents_for_nested_file(tmp_path) -> None:
    service = LiveFileMutationService()

    result = service.execute(
        CreatePathRequest(
            parent_dir=str(tmp_path), name="reports/2026/january.txt", kind="file"
        )
    )

    target = tmp_path / "reports" / "2026" / "january.txt"
    assert target.is_file()
    assert result.path == str(target)
    assert result.message == "Created file reports/2026/january.txt"


def test_file_mutation_service_rejects_create_path_outside_parent(tmp_path) -> None:
    service = LiveFileMutationService()

    with pytest.raises(OSError, match="must stay within the current directory"):
        service.execute(
            CreatePathRequest(parent_dir=str(tmp_path), name="../escape.txt", kind="file")
        )

    assert not (tmp_path.parent / "escape.txt").exists()


def test_file_mutation_service_keeps_created_parents_when_final_create_fails(tmp_path) -> None:
    target = tmp_path / "reports" / "january.txt"
    adapter = StubFileOperationAdapter(failing_paths={str(target)})
    service = LiveFileMutationService(adapter=adapter)

    with pytest.raises(OSError, match="created parent directories"):
        service.execute(
            CreatePathRequest(parent_dir=str(tmp_path), name="reports/january.txt", kind="file")
        )

    assert (tmp_path / "reports").is_dir()


def test_file_mutation_service_reports_partial_delete_failures() -> None:
    adapter = StubFileOperationAdapter(failing_paths={"/tmp/zivo/src"})
    service = LiveFileMutationService(adapter=adapter)

    result = service.execute(
        DeleteRequest(paths=("/tmp/zivo/docs", "/tmp/zivo/src"), mode="trash")
    )

    assert adapter.trashed_paths == ["/tmp/zivo/docs"]
    assert result.level == "warning"
    assert result.removed_paths == ("/tmp/zivo/docs",)


def test_file_mutation_service_raises_when_all_deletes_fail() -> None:
    adapter = StubFileOperationAdapter(failing_paths={"/tmp/zivo/docs"})
    service = LiveFileMutationService(adapter=adapter)

    with pytest.raises(OSError, match="Failed to move docs to trash"):
        service.execute(DeleteRequest(paths=("/tmp/zivo/docs",), mode="trash"))


@pytest.mark.skipif(os.name == "nt", reason="symlink creation requires extra Windows privileges")
def test_file_mutation_service_trashes_symlink_without_following_target(tmp_path) -> None:
    target = tmp_path / "target.txt"
    target.write_text("secret\n", encoding="utf-8")
    link = tmp_path / "link.txt"
    link.symlink_to(target)
    service = LiveFileMutationService()

    result = service.execute(DeleteRequest(paths=(str(link),), mode="trash"))

    assert link.exists() is False
    assert target.exists()
    assert result.removed_paths == (str(link),)


def test_file_mutation_service_permanently_deletes_single_path() -> None:
    adapter = StubFileOperationAdapter()
    service = LiveFileMutationService(adapter=adapter)

    result = service.execute(DeleteRequest(paths=("/tmp/zivo/docs",), mode="permanent"))

    assert adapter.deleted_paths == ["/tmp/zivo/docs"]
    assert adapter.trashed_paths == []
    assert result.message == "Permanently deleted 1 item"
    assert result.removed_paths == ("/tmp/zivo/docs",)


def test_file_mutation_service_prepares_permanent_delete_metadata(tmp_path) -> None:
    directory = tmp_path / "docs"
    directory.mkdir()
    (directory / "guide.md").write_bytes(b"guide")
    notes = tmp_path / "notes.txt"
    notes.write_bytes(b"notes-data")
    request = DeleteRequest(paths=(str(directory), str(notes)), mode="permanent")

    result = LiveFileMutationService().prepare_delete(request)

    assert result.request == request
    assert result.total_size_bytes == 15
    assert result.contains_directory is True
    assert result.failed_paths == ()


def test_file_mutation_service_reports_unreadable_delete_metadata(tmp_path) -> None:
    missing = tmp_path / "missing.txt"
    request = DeleteRequest(paths=(str(missing),), mode="permanent")

    result = LiveFileMutationService().prepare_delete(request)

    assert result.total_size_bytes == 0
    assert result.contains_directory is False
    assert result.failed_paths == (str(missing),)


def test_file_mutation_service_reports_partial_permanent_delete_failures() -> None:
    adapter = StubFileOperationAdapter(failing_paths={"/tmp/zivo/src"})
    service = LiveFileMutationService(adapter=adapter)

    result = service.execute(
        DeleteRequest(paths=("/tmp/zivo/docs", "/tmp/zivo/src"), mode="permanent")
    )

    assert adapter.deleted_paths == ["/tmp/zivo/docs"]
    assert result.level == "warning"
    assert result.message == "Permanently deleted 1/2 items with 1 failure(s)"
    assert result.removed_paths == ("/tmp/zivo/docs",)


def test_file_mutation_service_raises_when_all_permanent_deletes_fail() -> None:
    adapter = StubFileOperationAdapter(failing_paths={"/tmp/zivo/docs"})
    service = LiveFileMutationService(adapter=adapter)

    with pytest.raises(OSError, match="Failed to permanently delete docs"):
        service.execute(DeleteRequest(paths=("/tmp/zivo/docs",), mode="permanent"))


@pytest.mark.skipif(os.name == "nt", reason="symlink creation requires extra Windows privileges")
def test_file_mutation_service_permanently_deletes_symlink_without_following_target(
    tmp_path,
) -> None:
    target = tmp_path / "target.txt"
    target.write_text("secret\n", encoding="utf-8")
    link = tmp_path / "link.txt"
    link.symlink_to(target)
    service = LiveFileMutationService()

    result = service.execute(DeleteRequest(paths=(str(link),), mode="permanent"))

    assert link.exists() is False
    assert target.exists()
    assert result.message == "Permanently deleted 1 item"
    assert result.removed_paths == (str(link),)
