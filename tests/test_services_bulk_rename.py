from pathlib import Path

from zivo.adapters import LocalFileOperationAdapter
from zivo.models import (
    BulkRenameRequest,
    BulkRenameTarget,
    UndoEntry,
    UndoMovePathStep,
)
from zivo.services import LiveBulkRenameService, LiveUndoService


def _request(parent: Path, *pairs: tuple[str, str]) -> BulkRenameRequest:
    return BulkRenameRequest(
        parent_dir=str(parent),
        targets=tuple(
            BulkRenameTarget(str(parent / old_name), new_name)
            for old_name, new_name in pairs
        ),
    )


def test_bulk_rename_validation_reports_unchanged_and_collisions(tmp_path: Path) -> None:
    (tmp_path / "a.txt").touch()
    (tmp_path / "b.txt").touch()

    unchanged = LiveBulkRenameService().validate(
        _request(tmp_path, ("a.txt", "a.txt"), ("b.txt", "b.txt"))
    )
    assert unchanged.unchanged_count == 2
    assert unchanged.changed_count == 0
    assert not unchanged.executable

    collision = LiveBulkRenameService().validate(
        _request(tmp_path, ("a.txt", "b.txt"), ("b.txt", "b.txt"))
    )
    assert collision.error_count == 1
    assert collision.items[0].status == "error"
    assert not collision.executable


def test_bulk_rename_executes_swap_through_temporary_paths(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("A")
    (tmp_path / "b.txt").write_text("B")
    request = _request(tmp_path, ("a.txt", "b.txt"), ("b.txt", "a.txt"))
    progress: list[tuple[int, int, str | None]] = []

    result = LiveBulkRenameService().execute(
        request,
        progress_callback=lambda completed, total, path: progress.append(
            (completed, total, path)
        ),
    )

    assert result.failure_count == 0
    assert result.success_count == 2
    assert (tmp_path / "a.txt").read_text() == "B"
    assert (tmp_path / "b.txt").read_text() == "A"
    assert not list(tmp_path.glob(".zivo-rename-*"))
    assert progress[-1][0:2] == (2, 2)


class _FailOnDestinationAdapter(LocalFileOperationAdapter):
    _failed = False

    def move_path(self, source: str, destination: str) -> None:
        if Path(destination).name == "b.txt" and not self._failed:
            object.__setattr__(self, "_failed", True)
            raise OSError("injected destination failure")
        super().move_path(source, destination)


def test_bulk_rename_rolls_back_when_final_move_fails(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("A")
    (tmp_path / "b.txt").write_text("B")
    request = _request(tmp_path, ("a.txt", "b.txt"), ("b.txt", "c.txt"))

    result = LiveBulkRenameService(adapter=_FailOnDestinationAdapter()).execute(request)

    assert result.failure_count >= 1
    assert result.rolled_back
    assert (tmp_path / "a.txt").read_text() == "A"
    assert (tmp_path / "b.txt").read_text() == "B"
    assert not (tmp_path / "c.txt").exists()
    assert not list(tmp_path.glob(".zivo-rename-*"))


def test_bulk_rename_undo_also_handles_swaps_safely(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("A")
    (tmp_path / "b.txt").write_text("B")
    request = _request(tmp_path, ("a.txt", "b.txt"), ("b.txt", "a.txt"))
    LiveBulkRenameService().execute(request)
    undo = UndoEntry(
        kind="bulk_rename",
        steps=(
            UndoMovePathStep(str(tmp_path / "b.txt"), str(tmp_path / "a.txt")),
            UndoMovePathStep(str(tmp_path / "a.txt"), str(tmp_path / "b.txt")),
        ),
    )

    result = LiveUndoService().execute(undo)

    assert result.level == "info"
    assert (tmp_path / "a.txt").read_text() == "A"
    assert (tmp_path / "b.txt").read_text() == "B"
    assert not list(tmp_path.glob(".zivo-undo-rename-*"))
