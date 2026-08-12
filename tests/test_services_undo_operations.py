from dataclasses import dataclass, field

import pytest

from zivo.models import (
    TrashRestoreRecord,
    UndoDeletePathStep,
    UndoEntry,
    UndoMovePathStep,
    UndoRestoreTrashStep,
)
from zivo.services.undo_operations import LiveUndoService


@dataclass
class StubFileOperationAdapter:
    deleted_paths: list[str] = field(default_factory=list)
    moved_paths: list[tuple[str, str]] = field(default_factory=list)
    failing_paths: set[str] = field(default_factory=set)

    def path_exists(self, path: str) -> bool:
        return False

    def paths_are_same(self, source: str, destination: str) -> bool:
        return source == destination

    def remove_path(self, path: str) -> None:
        if path in self.failing_paths:
            raise OSError("delete failed")
        self.deleted_paths.append(path)

    def copy_path(self, source: str, destination: str) -> None:
        raise NotImplementedError

    def move_path(self, source: str, destination: str) -> None:
        if source in self.failing_paths or destination in self.failing_paths:
            raise OSError("move failed")
        self.moved_paths.append((source, destination))

    def generate_renamed_path(self, destination: str) -> str:
        raise NotImplementedError

    def create_file(self, path: str) -> None:
        raise NotImplementedError

    def create_directory(self, path: str) -> None:
        raise NotImplementedError

    def send_to_trash(self, path: str) -> None:
        raise NotImplementedError


@dataclass
class StubTrashService:
    restored_records: list[TrashRestoreRecord] = field(default_factory=list)
    failing_paths: set[str] = field(default_factory=set)

    def get_trash_path(self) -> str | None:
        return "/tmp/trash"

    def capture_restorable_trash(self, path, send_to_trash):
        raise NotImplementedError

    def restore(self, record: TrashRestoreRecord) -> str:
        if record.original_path in self.failing_paths:
            raise OSError("restore failed")
        self.restored_records.append(record)
        return record.original_path


def test_live_undo_service_removes_copied_paths() -> None:
    adapter = StubFileOperationAdapter()
    service = LiveUndoService(adapter=adapter, trash_service=StubTrashService())

    result = service.execute(
        UndoEntry(
            kind="paste_copy",
            steps=(
                UndoDeletePathStep(path="/tmp/project/docs copy/child.txt"),
                UndoDeletePathStep(path="/tmp/project/docs copy"),
            ),
        )
    )

    assert adapter.deleted_paths == [
        "/tmp/project/docs copy/child.txt",
        "/tmp/project/docs copy",
    ]
    assert result.message == "Undid copied items (2 items)"
    assert result.removed_paths == (
        "/tmp/project/docs copy/child.txt",
        "/tmp/project/docs copy",
    )


def test_live_undo_service_moves_paths_back_for_rename() -> None:
    adapter = StubFileOperationAdapter()
    service = LiveUndoService(adapter=adapter, trash_service=StubTrashService())

    result = service.execute(
        UndoEntry(
            kind="rename",
            steps=(
                UndoMovePathStep(
                    source_path="/tmp/project/manuals",
                    destination_path="/tmp/project/docs",
                ),
            ),
        )
    )

    assert adapter.moved_paths == [("/tmp/project/manuals", "/tmp/project/docs")]
    assert result.path == "/tmp/project/docs"
    assert result.message == "Undid rename"


def test_live_undo_service_restores_trash_records() -> None:
    record = TrashRestoreRecord(
        original_path="/tmp/project/docs",
        trashed_path="/tmp/trash/files/docs",
        metadata_path="/tmp/trash/info/docs.trashinfo",
    )
    trash_service = StubTrashService()
    service = LiveUndoService(adapter=StubFileOperationAdapter(), trash_service=trash_service)

    result = service.execute(
        UndoEntry(
            kind="trash_delete",
            steps=(UndoRestoreTrashStep(record=record),),
        )
    )

    assert trash_service.restored_records == [record]
    assert result.path == "/tmp/project/docs"
    assert result.message == "Restored item from trash"


def test_live_undo_service_raises_when_all_steps_fail() -> None:
    adapter = StubFileOperationAdapter(failing_paths={"/tmp/project/docs copy"})
    service = LiveUndoService(adapter=adapter, trash_service=StubTrashService())

    with pytest.raises(OSError, match="delete failed"):
        service.execute(
            UndoEntry(
                kind="paste_copy",
                steps=(UndoDeletePathStep(path="/tmp/project/docs copy"),),
            )
        )
