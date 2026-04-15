import bz2
import gzip
import tarfile
import zipfile
from io import BytesIO

import pytest

from zivo.models import ExtractArchiveRequest
from zivo.services import LiveArchiveExtractService


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


def _create_gz_archive(path) -> None:
    with gzip.open(path, "wb") as f:
        f.write(b"hello from gzip\n")


def _create_bz2_archive(path) -> None:
    with bz2.open(path, "wb") as f:
        f.write(b"hello from bz2\n")


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


@pytest.mark.parametrize(
    ("archive_name", "builder", "expected_entry_name", "expected_content"),
    (
        ("sample.log.gz", _create_gz_archive, "sample.log", "hello from gzip\n"),
        ("sample.log.bz2", _create_bz2_archive, "sample.log", "hello from bz2\n"),
    ),
)
def test_archive_extract_service_extracts_single_file_compressed(
    tmp_path,
    archive_name,
    builder,
    expected_entry_name,
    expected_content,
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

    extracted_file = destination_path / expected_entry_name
    assert extracted_file.read_text(encoding="utf-8") == expected_content
    assert result.extracted_entries == 1


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
