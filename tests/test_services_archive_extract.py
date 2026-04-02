import tarfile
import zipfile
from io import BytesIO

import pytest

from peneo.models import ExtractArchiveRequest
from peneo.services import LiveArchiveExtractService


def _create_zip_archive(path) -> None:
    with zipfile.ZipFile(path, mode="w") as archive:
        archive.writestr("docs/readme.txt", "hello\n")
        archive.writestr("notes.txt", "notes\n")


def _create_tar_archive(path, mode: str) -> None:
    with tarfile.open(path, mode) as archive:
        for name, body in (
            ("docs/readme.txt", b"hello\n"),
            ("notes.txt", b"notes\n"),
        ):
            info = tarfile.TarInfo(name=name)
            info.size = len(body)
            archive.addfile(info, BytesIO(body))


@pytest.mark.parametrize(
    ("archive_name", "builder"),
    (
        ("sample.zip", _create_zip_archive),
        ("sample.tar", lambda path: _create_tar_archive(path, "w")),
        ("sample.tar.gz", lambda path: _create_tar_archive(path, "w:gz")),
        ("sample.tar.bz2", lambda path: _create_tar_archive(path, "w:bz2")),
    ),
)
def test_archive_extract_service_extracts_supported_formats(
    tmp_path,
    archive_name,
    builder,
) -> None:
    archive_path = tmp_path / archive_name
    builder(archive_path)
    destination_path = tmp_path / "output"

    service = LiveArchiveExtractService()
    result = service.execute(
        ExtractArchiveRequest(
            source_path=str(archive_path),
            destination_path=str(destination_path),
        )
    )

    assert (destination_path / "docs" / "readme.txt").read_text(encoding="utf-8") == "hello\n"
    assert (destination_path / "notes.txt").read_text(encoding="utf-8") == "notes\n"
    assert result.destination_path == str(destination_path)
    assert result.extracted_entries == 2


def test_archive_extract_service_prepare_detects_conflicts(tmp_path) -> None:
    archive_path = tmp_path / "sample.zip"
    _create_zip_archive(archive_path)
    destination_path = tmp_path / "output"
    destination_path.mkdir()
    (destination_path / "notes.txt").write_text("existing\n", encoding="utf-8")

    service = LiveArchiveExtractService()
    result = service.prepare(
        ExtractArchiveRequest(
            source_path=str(archive_path),
            destination_path=str(destination_path),
        )
    )

    assert result.total_entries == 2
    assert len(result.conflicts) == 1
    assert result.conflicts[0].destination_path == str(destination_path / "notes.txt")


def test_archive_extract_service_reports_progress(tmp_path) -> None:
    archive_path = tmp_path / "sample.zip"
    _create_zip_archive(archive_path)
    destination_path = tmp_path / "output"
    progress_events: list[tuple[int, int, str | None]] = []

    service = LiveArchiveExtractService()
    service.execute(
        ExtractArchiveRequest(
            source_path=str(archive_path),
            destination_path=str(destination_path),
        ),
        progress_callback=lambda completed, total, current: progress_events.append(
            (completed, total, current)
        ),
    )

    assert progress_events == [
        (1, 2, str(destination_path / "docs" / "readme.txt")),
        (2, 2, str(destination_path / "notes.txt")),
    ]
