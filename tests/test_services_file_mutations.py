from dataclasses import dataclass, field

import pytest

from peneo.models import CreatePathRequest, DeleteRequest, RenameRequest
from peneo.services import LiveFileMutationService


@dataclass
class StubFileOperationAdapter:
    deleted_paths: list[str] = field(default_factory=list)
    trashed_paths: list[str] = field(default_factory=list)
    failing_paths: set[str] = field(default_factory=set)
    moved_paths: list[tuple[str, str]] = field(default_factory=list)
    created_files: list[str] = field(default_factory=list)
    created_directories: list[str] = field(default_factory=list)

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

    def send_to_trash(self, path: str) -> None:
        if path in self.failing_paths:
            raise OSError("permission denied")
        self.trashed_paths.append(path)


def test_file_mutation_service_trashes_single_path() -> None:
    adapter = StubFileOperationAdapter()
    service = LiveFileMutationService(adapter=adapter)

    result = service.execute(
        DeleteRequest(paths=("/tmp/peneo/docs",), mode="trash")
    )

    assert adapter.trashed_paths == ["/tmp/peneo/docs"]
    assert result.message == "Trashed 1 item"
    assert result.removed_paths == ("/tmp/peneo/docs",)


def test_file_mutation_service_renames_single_path() -> None:
    adapter = StubFileOperationAdapter()
    service = LiveFileMutationService(adapter=adapter)

    result = service.execute(
        RenameRequest(source_path="/tmp/peneo/docs", new_name="docs-old")
    )

    assert adapter.moved_paths == [("/tmp/peneo/docs", "/tmp/peneo/docs-old")]
    assert result.path == "/tmp/peneo/docs-old"
    assert result.message == "Renamed to docs-old"


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
    adapter = StubFileOperationAdapter(failing_paths={"/tmp/peneo/docs-old"})
    service = LiveFileMutationService(adapter=adapter)

    with pytest.raises(OSError, match="rename failed"):
        service.execute(RenameRequest(source_path="/tmp/peneo/docs", new_name="docs-old"))


def test_file_mutation_service_creates_file() -> None:
    adapter = StubFileOperationAdapter()
    service = LiveFileMutationService(adapter=adapter)

    result = service.execute(
        CreatePathRequest(parent_dir="/tmp/peneo", name="README.md", kind="file")
    )

    assert adapter.created_files == ["/tmp/peneo/README.md"]
    assert result.path == "/tmp/peneo/README.md"
    assert result.message == "Created file README.md"


def test_file_mutation_service_creates_directory() -> None:
    adapter = StubFileOperationAdapter()
    service = LiveFileMutationService(adapter=adapter)

    result = service.execute(CreatePathRequest(parent_dir="/tmp/peneo", name="docs", kind="dir"))

    assert adapter.created_directories == ["/tmp/peneo/docs"]
    assert result.path == "/tmp/peneo/docs"
    assert result.message == "Created directory docs"


def test_file_mutation_service_raises_create_file_error() -> None:
    adapter = StubFileOperationAdapter(failing_paths={"/tmp/peneo/README.md"})
    service = LiveFileMutationService(adapter=adapter)

    with pytest.raises(OSError, match="file creation failed"):
        service.execute(CreatePathRequest(parent_dir="/tmp/peneo", name="README.md", kind="file"))


def test_file_mutation_service_raises_create_directory_error() -> None:
    adapter = StubFileOperationAdapter(failing_paths={"/tmp/peneo/docs"})
    service = LiveFileMutationService(adapter=adapter)

    with pytest.raises(OSError, match="directory creation failed"):
        service.execute(CreatePathRequest(parent_dir="/tmp/peneo", name="docs", kind="dir"))


def test_file_mutation_service_reports_partial_delete_failures() -> None:
    adapter = StubFileOperationAdapter(failing_paths={"/tmp/peneo/src"})
    service = LiveFileMutationService(adapter=adapter)

    result = service.execute(
        DeleteRequest(paths=("/tmp/peneo/docs", "/tmp/peneo/src"), mode="trash")
    )

    assert adapter.trashed_paths == ["/tmp/peneo/docs"]
    assert result.level == "warning"
    assert result.removed_paths == ("/tmp/peneo/docs",)


def test_file_mutation_service_raises_when_all_deletes_fail() -> None:
    adapter = StubFileOperationAdapter(failing_paths={"/tmp/peneo/docs"})
    service = LiveFileMutationService(adapter=adapter)

    with pytest.raises(OSError, match="Failed to trash docs"):
        service.execute(DeleteRequest(paths=("/tmp/peneo/docs",), mode="trash"))


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

    result = service.execute(DeleteRequest(paths=("/tmp/peneo/docs",), mode="permanent"))

    assert adapter.deleted_paths == ["/tmp/peneo/docs"]
    assert adapter.trashed_paths == []
    assert result.message == "Deleted 1 item permanently"
    assert result.removed_paths == ("/tmp/peneo/docs",)


def test_file_mutation_service_reports_partial_permanent_delete_failures() -> None:
    adapter = StubFileOperationAdapter(failing_paths={"/tmp/peneo/src"})
    service = LiveFileMutationService(adapter=adapter)

    result = service.execute(
        DeleteRequest(paths=("/tmp/peneo/docs", "/tmp/peneo/src"), mode="permanent")
    )

    assert adapter.deleted_paths == ["/tmp/peneo/docs"]
    assert result.level == "warning"
    assert result.message == "Deleted 1/2 items permanently with 1 failure(s)"
    assert result.removed_paths == ("/tmp/peneo/docs",)


def test_file_mutation_service_raises_when_all_permanent_deletes_fail() -> None:
    adapter = StubFileOperationAdapter(failing_paths={"/tmp/peneo/docs"})
    service = LiveFileMutationService(adapter=adapter)

    with pytest.raises(OSError, match="Failed to permanently delete docs"):
        service.execute(DeleteRequest(paths=("/tmp/peneo/docs",), mode="permanent"))


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
    assert result.message == "Deleted 1 item permanently"
    assert result.removed_paths == (str(link),)
