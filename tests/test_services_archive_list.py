import tarfile
import zipfile
from io import BytesIO

import pytest

from peneo.services import LiveArchiveListService


def _create_zip_archive(path) -> None:
    with zipfile.ZipFile(path, mode="w") as archive:
        archive.writestr("docs/readme.txt", "hello\n")
        archive.writestr("notes.txt", "notes\n")
        archive.writestr("executable.sh", "#!/bin/bash\n")
        archive.writestr("src/main.py", "print('hello')\n")


def _create_tar_archive(path, mode: str) -> None:
    with tarfile.open(path, mode) as archive:
        for name, body in (
            ("docs/readme.txt", b"hello\n"),
            ("notes.txt", b"notes\n"),
            ("executable.sh", b"#!/bin/bash\n"),
            ("src/main.py", b"print('hello')\n"),
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
def test_archive_list_service_lists_supported_formats(
    tmp_path,
    archive_name,
    builder,
) -> None:
    archive_path = tmp_path / archive_name
    builder(archive_path)

    service = LiveArchiveListService()
    entries = service.list_archive_entries(str(archive_path))

    assert len(entries) == 4
    entry_names = {entry.name for entry in entries}
    assert "docs" in entry_names
    assert "notes.txt" in entry_names
    assert "executable.sh" in entry_names
    assert "src" in entry_names


def test_archive_list_service_sorts_directories_first(tmp_path) -> None:
    archive_path = tmp_path / "test.zip"
    with zipfile.ZipFile(archive_path, mode="w") as archive:
        archive.writestr("file1.txt", "content\n")
        archive.writestr("dir1/file.txt", "content\n")
        archive.writestr("file2.txt", "content\n")

    service = LiveArchiveListService()
    entries = service.list_archive_entries(str(archive_path))

    assert entries[0].kind == "dir"
    assert entries[0].name == "dir1"
    assert entries[1].kind == "file"
    assert entries[1].name == "file1.txt"
    assert entries[2].kind == "file"
    assert entries[2].name == "file2.txt"


def test_archive_list_service_includes_file_size_for_files(tmp_path) -> None:
    archive_path = tmp_path / "test.zip"
    with zipfile.ZipFile(archive_path, mode="w") as archive:
        archive.writestr("small.txt", "hi")
        archive.writestr("large.txt", "hello world\n")

    service = LiveArchiveListService()
    entries = service.list_archive_entries(str(archive_path))

    small_entry = next(e for e in entries if e.name == "small.txt")
    large_entry = next(e for e in entries if e.name == "large.txt")

    assert small_entry.size_bytes == 2
    assert large_entry.size_bytes == 12


def test_archive_list_service_filters_duplicate_names(tmp_path) -> None:
    archive_path = tmp_path / "test.zip"
    with zipfile.ZipFile(archive_path, mode="w") as archive:
        archive.writestr("dir/", "")
        archive.writestr("dir/file.txt", "content\n")

    service = LiveArchiveListService()
    entries = service.list_archive_entries(str(archive_path))

    assert len(entries) == 1
    assert entries[0].name == "dir"
    assert entries[0].kind == "dir"


def test_archive_list_service_raises_error_for_nonexistent_archive(tmp_path) -> None:
    service = LiveArchiveListService()

    with pytest.raises(OSError, match="Archive does not exist"):
        service.list_archive_entries(str(tmp_path / "nonexistent.zip"))


def test_archive_list_service_raises_error_for_unsupported_format(tmp_path) -> None:
    archive_path = tmp_path / "test.rar"
    archive_path.write_text("not a real archive")

    service = LiveArchiveListService()

    with pytest.raises(OSError, match="Unsupported archive format"):
        service.list_archive_entries(str(archive_path))


def test_archive_list_service_filters_path_traversal(tmp_path) -> None:
    archive_path = tmp_path / "test.zip"
    with zipfile.ZipFile(archive_path, mode="w") as archive:
        archive.writestr("safe.txt", "content\n")
        archive.writestr("../unsafe.txt", "content\n")

    service = LiveArchiveListService()
    entries = service.list_archive_entries(str(archive_path))

    assert len(entries) == 1
    assert entries[0].name == "safe.txt"


def test_archive_list_service_filters_absolute_paths(tmp_path) -> None:
    archive_path = tmp_path / "test.zip"
    with zipfile.ZipFile(archive_path, mode="w") as archive:
        archive.writestr("relative.txt", "content\n")
        archive.writestr("/absolute/path.txt", "content\n")

    service = LiveArchiveListService()
    entries = service.list_archive_entries(str(archive_path))

    assert len(entries) == 1
    assert entries[0].name == "relative.txt"


def test_archive_list_service_handles_empty_archive(tmp_path) -> None:
    archive_path = tmp_path / "empty.zip"
    with zipfile.ZipFile(archive_path, mode="w"):
        pass

    service = LiveArchiveListService()
    entries = service.list_archive_entries(str(archive_path))

    assert len(entries) == 0


def test_archive_list_service_creates_virtual_paths(tmp_path) -> None:
    archive_path = tmp_path / "test.zip"
    with zipfile.ZipFile(archive_path, mode="w") as archive:
        archive.writestr("internal/file.txt", "content\n")

    service = LiveArchiveListService()
    entries = service.list_archive_entries(str(archive_path))

    assert len(entries) == 1
    internal_dir = entries[0]
    assert internal_dir.name == "internal"
    assert internal_dir.kind == "dir"
    assert str(archive_path) in internal_dir.path
    assert "/internal" in internal_dir.path
