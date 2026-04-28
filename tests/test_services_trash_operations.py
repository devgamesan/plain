from pathlib import Path
from unittest.mock import MagicMock

import pytest

from zivo.models import TrashRestoreRecord
from zivo.services.trash_operations import LinuxTrashService, MacOsTrashService, WindowsTrashService


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


def test_macos_capture_restorable_trash_creates_record(tmp_path, monkeypatch) -> None:
    trash_dir = tmp_path / ".Trash"
    trash_dir.mkdir()
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    original_path = tmp_path / "docs"
    original_path.write_text("hello", encoding="utf-8")

    def fake_send_to_trash() -> None:
        original_path.rename(trash_dir / "docs")

    service = MacOsTrashService()
    record = service.capture_restorable_trash(str(original_path), fake_send_to_trash)

    assert record is not None
    assert record.original_path == str(original_path)
    assert record.trashed_path == str(trash_dir / "docs")
    assert Path(record.metadata_path).exists()
    content = Path(record.metadata_path).read_text(encoding="utf-8")
    assert "[Zivo Restore Info]" in content
    assert f"OriginalPath={original_path}" in content


def test_macos_capture_restorable_trash_handles_name_collision(tmp_path, monkeypatch) -> None:
    trash_dir = tmp_path / ".Trash"
    trash_dir.mkdir()
    (trash_dir / "docs").write_text("existing", encoding="utf-8")
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    original_path = tmp_path / "docs"
    original_path.write_text("hello", encoding="utf-8")

    def fake_send_to_trash() -> None:
        original_path.rename(trash_dir / "docs 1")

    service = MacOsTrashService()
    record = service.capture_restorable_trash(str(original_path), fake_send_to_trash)

    assert record is not None
    assert record.trashed_path == str(trash_dir / "docs 1")


def test_macos_restore_moves_file_back(tmp_path, monkeypatch) -> None:
    trash_dir = tmp_path / ".Trash"
    trash_dir.mkdir()
    metadata_dir = trash_dir / ".zivo-restore"
    metadata_dir.mkdir()
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    trashed_path = trash_dir / "docs"
    trashed_path.write_text("restored\n", encoding="utf-8")
    metadata_path = metadata_dir / "20260416T120000_docs.restoreinfo"
    metadata_path.write_text(
        "[Zivo Restore Info]\nOriginalPath=/tmp/project/docs\n"
        "TrashedPath=docs\nDeletionDate=2026-04-16T12:00:00\n",
        encoding="utf-8",
    )

    destination = tmp_path / "restored" / "docs"
    record = TrashRestoreRecord(
        original_path=str(destination),
        trashed_path=str(trashed_path),
        metadata_path=str(metadata_path),
    )

    restored_path = MacOsTrashService().restore(record)

    assert restored_path == str(destination)
    assert destination.read_text(encoding="utf-8") == "restored\n"
    assert not trashed_path.exists()
    assert not metadata_path.exists()


def test_macos_restore_raises_when_trashed_missing(tmp_path, monkeypatch) -> None:
    trash_dir = tmp_path / ".Trash"
    trash_dir.mkdir()
    metadata_dir = trash_dir / ".zivo-restore"
    metadata_dir.mkdir()
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    record = TrashRestoreRecord(
        original_path=str(tmp_path / "dest"),
        trashed_path=str(trash_dir / "missing"),
        metadata_path=str(metadata_dir / "meta.restoreinfo"),
    )

    with pytest.raises(OSError, match="Trashed entry not found"):
        MacOsTrashService().restore(record)


def test_macos_restore_raises_when_destination_exists(tmp_path, monkeypatch) -> None:
    trash_dir = tmp_path / ".Trash"
    trash_dir.mkdir()
    metadata_dir = trash_dir / ".zivo-restore"
    metadata_dir.mkdir()
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    trashed_path = trash_dir / "docs"
    trashed_path.write_text("data", encoding="utf-8")
    destination = tmp_path / "docs"
    destination.write_text("already here", encoding="utf-8")

    record = TrashRestoreRecord(
        original_path=str(destination),
        trashed_path=str(trashed_path),
        metadata_path=str(metadata_dir / "meta.restoreinfo"),
    )

    with pytest.raises(OSError, match="Restore destination already exists"):
        MacOsTrashService().restore(record)


def test_macos_capture_returns_none_when_no_new_entry(
    tmp_path, monkeypatch,
) -> None:
    trash_dir = tmp_path / ".Trash"
    trash_dir.mkdir()
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    original_path = tmp_path / "docs"
    original_path.write_text("hello", encoding="utf-8")

    service = MacOsTrashService()
    record = service.capture_restorable_trash(str(original_path), lambda: None)

    assert record is None


def test_windows_trash_service_captures_restorable_metadata(tmp_path, monkeypatch) -> None:
    original_path = "C:/Users/test/docs"
    sent_to_trash: list[str] = []

    def fake_powershell_stdout(lines: list[str]) -> MagicMock:
        return MagicMock(returncode=0, stdout="\n".join(lines), stderr="")

    call_count = 0

    def mock_subprocess_run(cmd, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return fake_powershell_stdout([
                "C:/Users/test/existing1",
                "C:/Users/test/existing2",
            ])
        return fake_powershell_stdout([
            "C:/Users/test/existing1",
            "C:/Users/test/existing2",
            original_path,
        ])

    monkeypatch.setattr(
        "zivo.services.trash_operations.subprocess.run",
        mock_subprocess_run,
    )

    service = WindowsTrashService()
    record = service.capture_restorable_trash(
        original_path,
        lambda: sent_to_trash.append(original_path),
    )

    assert sent_to_trash == [original_path]
    assert record is not None
    assert record.original_path == original_path
    assert record.trashed_path == "docs"
    assert record.metadata_path == ""


def test_windows_trash_service_capture_returns_none_when_no_new_items(
    tmp_path, monkeypatch,
) -> None:
    sent_to_trash: list[str] = []

    def fake_powershell_stdout(lines: list[str]) -> MagicMock:
        return MagicMock(returncode=0, stdout="\n".join(lines), stderr="")

    def mock_subprocess_run(cmd, *args, **kwargs):
        return fake_powershell_stdout([
            "C:/Users/test/docs",
            "C:/Users/test/other",
        ])

    monkeypatch.setattr(
        "zivo.services.trash_operations.subprocess.run",
        mock_subprocess_run,
    )

    service = WindowsTrashService()
    record = service.capture_restorable_trash(
        "C:/Users/test/docs",
        lambda: sent_to_trash.append("C:/Users/test/docs"),
    )

    assert sent_to_trash == ["C:/Users/test/docs"]
    assert record is None


def test_windows_trash_service_capture_handles_powershell_failure(
    monkeypatch,
) -> None:
    sent_to_trash: list[str] = []

    mock_run = MagicMock(return_value=MagicMock(returncode=1, stderr="error"))
    monkeypatch.setattr("zivo.services.trash_operations.subprocess.run", mock_run)

    service = WindowsTrashService()
    record = service.capture_restorable_trash(
        "C:/Users/test/docs",
        lambda: sent_to_trash.append("C:/Users/test/docs"),
    )

    assert sent_to_trash == ["C:/Users/test/docs"]
    assert record is None


def test_windows_empty_trash_powershell_success(monkeypatch) -> None:
    mock_run = MagicMock(return_value=MagicMock(returncode=0, stderr=""))
    monkeypatch.setattr("zivo.services.trash_operations.subprocess.run", mock_run)

    count, error = WindowsTrashService().empty_trash()

    assert count == 1
    assert error == ""
    mock_run.assert_called_once_with(
        ["powershell.exe", "-NoProfile", "-Command", "Clear-RecycleBin -Force"],
        capture_output=True,
        text=True,
        check=False,
    )


def test_windows_empty_trash_powershell_failure(monkeypatch) -> None:
    mock_run = MagicMock(
        return_value=MagicMock(returncode=1, stderr="access denied")
    )
    monkeypatch.setattr("zivo.services.trash_operations.subprocess.run", mock_run)

    count, error = WindowsTrashService().empty_trash()

    assert count == 0
    assert error == "Failed to empty Recycle Bin"


def test_windows_trash_service_restore_succeeds(monkeypatch) -> None:
    original_path = "C:/Users/test/docs"
    record = TrashRestoreRecord(
        original_path=original_path,
        trashed_path="docs",
        metadata_path="",
    )

    mock_run = MagicMock(
        return_value=MagicMock(returncode=0, stdout="", stderr=""),
    )
    monkeypatch.setattr("zivo.services.trash_operations.subprocess.run", mock_run)

    result = WindowsTrashService().restore(record)

    assert result == original_path
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "powershell.exe"
    assert "-NoProfile" in cmd
    assert "-Command" in cmd
    script_arg = cmd[cmd.index("-Command") + 1]
    assert "GetDetailsOf" in script_arg
    assert "InvokeVerb('undelete')" in script_arg
    assert "'C:/Users/test/docs'" in script_arg


def test_windows_trash_service_restore_raises_when_not_found(monkeypatch) -> None:
    record = TrashRestoreRecord(
        original_path="C:/Users/test/missing",
        trashed_path="missing",
        metadata_path="",
    )

    mock_run = MagicMock(return_value=MagicMock(returncode=1, stdout="", stderr=""))
    monkeypatch.setattr("zivo.services.trash_operations.subprocess.run", mock_run)

    with pytest.raises(
        OSError,
        match="Failed to restore 'C:/Users/test/missing' from Recycle Bin: "
        "item not found",
    ):
        WindowsTrashService().restore(record)


def test_windows_trash_service_restore_raises_when_verb_fails(monkeypatch) -> None:
    record = TrashRestoreRecord(
        original_path="C:/Users/test/stuck",
        trashed_path="stuck",
        metadata_path="",
    )

    mock_run = MagicMock(return_value=MagicMock(returncode=2, stdout="", stderr=""))
    monkeypatch.setattr("zivo.services.trash_operations.subprocess.run", mock_run)

    with pytest.raises(
        OSError,
        match="Failed to restore 'C:/Users/test/stuck' from Recycle Bin: "
        "restore verb had no effect",
    ):
        WindowsTrashService().restore(record)
