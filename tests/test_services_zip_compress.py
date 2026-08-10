import zipfile

from zivo.models import CreateZipArchiveRequest
from zivo.services import LiveZipCompressService


def test_zip_compress_service_creates_archive_for_selected_targets(tmp_path) -> None:
    root_dir = tmp_path / "project"
    root_dir.mkdir()
    docs_dir = root_dir / "docs"
    docs_dir.mkdir()
    (docs_dir / "readme.txt").write_text("hello\n", encoding="utf-8")
    notes_path = root_dir / "notes.txt"
    notes_path.write_text("notes\n", encoding="utf-8")
    destination_path = root_dir / "bundle.zip"
    progress_events: list[tuple[int, int, str | None]] = []

    service = LiveZipCompressService()
    result = service.execute(
        CreateZipArchiveRequest(
            source_paths=(str(docs_dir), str(notes_path)),
            destination_path=str(destination_path),
            root_dir=str(root_dir),
        ),
        progress_callback=lambda completed, total, current: progress_events.append(
            (completed, total, current)
        ),
    )

    with zipfile.ZipFile(destination_path) as archive:
        assert set(archive.namelist()) == {"docs/", "docs/readme.txt", "notes.txt"}
        assert archive.read("docs/readme.txt").decode("utf-8").replace("\r\n", "\n") == "hello\n"
        assert archive.read("notes.txt").decode("utf-8").replace("\r\n", "\n") == "notes\n"

    assert result.destination_path == str(destination_path)
    assert result.archived_entries == 3
    assert progress_events == [
        (1, 3, str(docs_dir)),
        (2, 3, str(docs_dir / "readme.txt")),
        (3, 3, str(notes_path)),
    ]


def test_zip_compress_service_prepare_detects_existing_destination(tmp_path) -> None:
    root_dir = tmp_path / "project"
    root_dir.mkdir()
    source_path = root_dir / "notes.txt"
    source_path.write_text("notes\n", encoding="utf-8")
    destination_path = root_dir / "notes.zip"
    destination_path.write_text("existing\n", encoding="utf-8")

    service = LiveZipCompressService()
    result = service.prepare(
        CreateZipArchiveRequest(
            source_paths=(str(source_path),),
            destination_path=str(destination_path),
            root_dir=str(root_dir),
        )
    )

    assert result.total_entries == 1
    assert result.destination_exists is True


def test_zip_compress_cancel_preserves_existing_destination_and_cleans_temp(tmp_path) -> None:
    root_dir = tmp_path / "project"
    root_dir.mkdir()
    first = root_dir / "one.txt"
    second = root_dir / "two.txt"
    first.write_text("one\n", encoding="utf-8")
    second.write_text("two\n", encoding="utf-8")
    destination_path = root_dir / "bundle.zip"
    destination_path.write_text("existing archive\n", encoding="utf-8")
    progress_events: list[tuple[int, int | None, str | None]] = []

    result = LiveZipCompressService().execute(
        CreateZipArchiveRequest(
            source_paths=(str(first), str(second)),
            destination_path=str(destination_path),
            root_dir=str(root_dir),
        ),
        progress_callback=lambda completed, total, current: progress_events.append(
            (completed, total, current)
        ),
        cancel_callback=lambda: len(progress_events) >= 1,
    )

    assert result.cancelled is True
    assert destination_path.read_text(encoding="utf-8") == "existing archive\n"
    assert list(root_dir.glob(".bundle.zip.zivo-*.zip")) == []
