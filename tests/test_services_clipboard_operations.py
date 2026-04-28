import os

import pytest

from zivo.models import PasteConflictPrompt, PasteRequest
from zivo.services import LiveClipboardOperationService

skip_if_windows_symlink_privilege_required = pytest.mark.skipif(
    os.name == "nt",
    reason="symlink creation requires extra Windows privileges",
)


def test_clipboard_service_requests_resolution_when_destination_exists(tmp_path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source = source_dir / "docs"
    source.mkdir()
    destination = tmp_path / "target"
    destination.mkdir()
    (destination / "docs").mkdir()

    service = LiveClipboardOperationService()

    result = service.execute_paste(
        PasteRequest(
            mode="copy",
            source_paths=(str(source),),
            destination_dir=str(destination),
        )
    )

    assert isinstance(result, PasteConflictPrompt)
    assert result.conflicts[0].destination_path == str(destination / "docs")


def test_clipboard_service_rename_copies_into_same_directory(tmp_path) -> None:
    source = tmp_path / "README.md"
    source.write_text("plain\n", encoding="utf-8")

    service = LiveClipboardOperationService()

    result = service.execute_paste(
        PasteRequest(
            mode="copy",
            source_paths=(str(source),),
            destination_dir=str(tmp_path),
            conflict_resolution="rename",
        )
    )

    assert result.summary.success_count == 1
    assert (tmp_path / "README copy.md").read_text(encoding="utf-8") == "plain\n"


@skip_if_windows_symlink_privilege_required
def test_clipboard_service_copy_preserves_symlink_entry(tmp_path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    target = source_dir / "target.txt"
    target.write_text("secret\n", encoding="utf-8")
    link = source_dir / "link.txt"
    link.symlink_to(target)
    destination = tmp_path / "target-dir"
    destination.mkdir()

    service = LiveClipboardOperationService()

    result = service.execute_paste(
        PasteRequest(
            mode="copy",
            source_paths=(str(link),),
            destination_dir=str(destination),
        )
    )

    copied_link = destination / "link.txt"
    assert result.summary.success_count == 1
    assert copied_link.is_symlink()
    assert copied_link.resolve() == target.resolve()
    assert target.exists()


def test_clipboard_service_skip_avoids_conflicting_write(tmp_path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source = source_dir / "README.md"
    source.write_text("new\n", encoding="utf-8")
    destination = tmp_path / "target"
    destination.mkdir()
    existing = destination / "README.md"
    existing.write_text("old\n", encoding="utf-8")

    service = LiveClipboardOperationService()

    result = service.execute_paste(
        PasteRequest(
            mode="copy",
            source_paths=(str(source),),
            destination_dir=str(destination),
            conflict_resolution="skip",
        )
    )

    assert result.summary.skipped_count == 1
    assert existing.read_text(encoding="utf-8") == "old\n"


def test_clipboard_service_overwrite_replaces_existing_file(tmp_path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source = source_dir / "README.md"
    source.write_text("new\n", encoding="utf-8")
    destination = tmp_path / "target"
    destination.mkdir()
    existing = destination / "README.md"
    existing.write_text("old\n", encoding="utf-8")

    service = LiveClipboardOperationService()

    result = service.execute_paste(
        PasteRequest(
            mode="copy",
            source_paths=(str(source),),
            destination_dir=str(destination),
            conflict_resolution="overwrite",
        )
    )

    assert result.summary.success_count == 1
    assert existing.read_text(encoding="utf-8") == "new\n"


@skip_if_windows_symlink_privilege_required
def test_clipboard_service_overwrite_replaces_symlink_entry_not_target(tmp_path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source = source_dir / "README.md"
    source.write_text("new\n", encoding="utf-8")
    destination = tmp_path / "target"
    destination.mkdir()
    protected = tmp_path / "protected.txt"
    protected.write_text("keep\n", encoding="utf-8")
    existing = destination / "README.md"
    existing.symlink_to(protected)

    service = LiveClipboardOperationService()

    result = service.execute_paste(
        PasteRequest(
            mode="copy",
            source_paths=(str(source),),
            destination_dir=str(destination),
            conflict_resolution="overwrite",
        )
    )

    assert result.summary.success_count == 1
    assert existing.is_symlink() is False
    assert existing.read_text(encoding="utf-8") == "new\n"
    assert protected.read_text(encoding="utf-8") == "keep\n"


def test_clipboard_service_cut_moves_source(tmp_path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source = source_dir / "note.txt"
    source.write_text("move\n", encoding="utf-8")
    destination = tmp_path / "target"
    destination.mkdir()

    service = LiveClipboardOperationService()

    result = service.execute_paste(
        PasteRequest(
            mode="cut",
            source_paths=(str(source),),
            destination_dir=str(destination),
        )
    )

    assert result.summary.success_count == 1
    assert source.exists() is False
    assert (destination / "note.txt").read_text(encoding="utf-8") == "move\n"


@skip_if_windows_symlink_privilege_required
def test_clipboard_service_cut_moves_symlink_without_following_target(tmp_path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    target = source_dir / "target.txt"
    target.write_text("secret\n", encoding="utf-8")
    link = source_dir / "link.txt"
    link.symlink_to(target)
    destination = tmp_path / "target-dir"
    destination.mkdir()

    service = LiveClipboardOperationService()

    result = service.execute_paste(
        PasteRequest(
            mode="cut",
            source_paths=(str(link),),
            destination_dir=str(destination),
        )
    )

    moved_link = destination / "link.txt"
    assert result.summary.success_count == 1
    assert link.exists() is False
    assert moved_link.is_symlink()
    assert moved_link.resolve() == target.resolve()
    assert target.exists()
