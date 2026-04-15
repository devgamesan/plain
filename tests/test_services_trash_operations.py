from unittest.mock import MagicMock

from zivo.models import TrashRestoreRecord
from zivo.services.trash_operations import LinuxTrashService, MacOsTrashService


def test_linux_trash_service_captures_restorable_metadata(tmp_path, monkeypatch) -> None:
    trash_root = tmp_path / "Trash"
    files_dir = trash_root / "files"
    info_dir = trash_root / "info"
    files_dir.mkdir(parents=True)
    info_dir.mkdir(parents=True)
    monkeypatch.setattr(LinuxTrashService, "_trash_root", staticmethod(lambda: trash_root))

    original_path = tmp_path / "docs"

    def fake_send_to_trash() -> None:
        (files_dir / "docs").write_text("trashed\n", encoding="utf-8")
        (info_dir / "docs.trashinfo").write_text(
            "[Trash Info]\nPath="
            f"{original_path}\nDeletionDate=2026-04-12T12:00:00\n",
            encoding="utf-8",
        )

    service = LinuxTrashService()

    record = service.capture_restorable_trash(str(original_path), fake_send_to_trash)

    assert record == TrashRestoreRecord(
        original_path=str(original_path),
        trashed_path=str(files_dir / "docs"),
        metadata_path=str(info_dir / "docs.trashinfo"),
    )


def test_linux_trash_service_restores_record(tmp_path, monkeypatch) -> None:
    trash_root = tmp_path / "Trash"
    files_dir = trash_root / "files"
    info_dir = trash_root / "info"
    files_dir.mkdir(parents=True)
    info_dir.mkdir(parents=True)
    monkeypatch.setattr(LinuxTrashService, "_trash_root", staticmethod(lambda: trash_root))

    trashed_path = files_dir / "docs"
    trashed_path.write_text("restored\n", encoding="utf-8")
    metadata_path = info_dir / "docs.trashinfo"
    metadata_path.write_text(
        "[Trash Info]\nPath=/tmp/project/docs\nDeletionDate=2026-04-12T12:00:00\n",
        encoding="utf-8",
    )

    destination = tmp_path / "restored" / "docs"
    record = TrashRestoreRecord(
        original_path=str(destination),
        trashed_path=str(trashed_path),
        metadata_path=str(metadata_path),
    )

    restored_path = LinuxTrashService().restore(record)

    assert restored_path == str(destination)
    assert destination.read_text(encoding="utf-8") == "restored\n"
    assert trashed_path.exists() is False
    assert metadata_path.exists() is False


def test_macos_empty_trash_counts_items_and_calls_osascript(tmp_path, monkeypatch) -> None:
    trash_dir = tmp_path / ".Trash"
    trash_dir.mkdir()
    (trash_dir / "file1.txt").write_text("data")
    (trash_dir / "folder1").mkdir()
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    mock_run = MagicMock(return_value=MagicMock(returncode=0, stderr=""))
    monkeypatch.setattr("zivo.services.trash_operations.subprocess.run", mock_run)

    service = MacOsTrashService()
    count, error = service.empty_trash()

    assert count == 2
    assert error == ""
    mock_run.assert_called_once_with(
        ["osascript", "-e", 'tell application "Finder" to empty trash'],
        capture_output=True,
        text=True,
        check=False,
    )


def test_macos_empty_trash_skips_ds_store_in_count(tmp_path, monkeypatch) -> None:
    trash_dir = tmp_path / ".Trash"
    trash_dir.mkdir()
    (trash_dir / ".DS_Store").write_text("metadata")
    (trash_dir / "real_file.txt").write_text("data")
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    mock_run = MagicMock(return_value=MagicMock(returncode=0, stderr=""))
    monkeypatch.setattr("zivo.services.trash_operations.subprocess.run", mock_run)

    service = MacOsTrashService()
    count, error = service.empty_trash()

    assert count == 1
    assert error == ""


def test_macos_empty_trash_returns_zero_when_trash_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    service = MacOsTrashService()
    count, error = service.empty_trash()

    assert count == 0
    assert error == ""


def test_macos_empty_trash_returns_zero_when_only_ds_store(tmp_path, monkeypatch) -> None:
    trash_dir = tmp_path / ".Trash"
    trash_dir.mkdir()
    (trash_dir / ".DS_Store").write_text("metadata")
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    service = MacOsTrashService()
    count, error = service.empty_trash()

    assert count == 0
    assert error == ""


def test_macos_empty_trash_returns_error_on_osascript_failure(tmp_path, monkeypatch) -> None:
    trash_dir = tmp_path / ".Trash"
    trash_dir.mkdir()
    (trash_dir / "file.txt").write_text("data")
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    mock_run = MagicMock(return_value=MagicMock(returncode=1, stderr="not authorized"))
    monkeypatch.setattr("zivo.services.trash_operations.subprocess.run", mock_run)

    service = MacOsTrashService()
    count, error = service.empty_trash()

    assert count == 0
    assert "Full Disk Access" in error
