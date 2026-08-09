import os

import pytest

from zivo.adapters import LocalFileOperationAdapter
from zivo.models import DuplicateRequest
from zivo.services import LiveDuplicateOperationService


def test_duplicate_file_preserves_extension_and_uses_smallest_available_name(tmp_path) -> None:
    source = tmp_path / "report.pdf"
    source.write_text("report", encoding="utf-8")
    (tmp_path / "report copy.pdf").write_text("existing", encoding="utf-8")
    (tmp_path / "report copy 3.pdf").write_text("existing", encoding="utf-8")

    result = LiveDuplicateOperationService().execute_duplicate(
        DuplicateRequest((str(source),), str(tmp_path))
    )

    destination = tmp_path / "report copy 2.pdf"
    assert result.summary.success_count == 1
    assert destination.read_text(encoding="utf-8") == "report"
    assert (tmp_path / "report copy.pdf").read_text(encoding="utf-8") == "existing"


def test_duplicate_directory_and_extensionless_file_use_copy_suffix(tmp_path) -> None:
    directory = tmp_path / "docs"
    directory.mkdir()
    (directory / "notes.txt").write_text("notes", encoding="utf-8")
    source = tmp_path / "LICENSE"
    source.write_text("license", encoding="utf-8")

    result = LiveDuplicateOperationService().execute_duplicate(
        DuplicateRequest((str(directory), str(source)), str(tmp_path))
    )

    assert result.summary.success_count == 2
    assert (tmp_path / "docs copy" / "notes.txt").read_text(encoding="utf-8") == "notes"
    assert (tmp_path / "LICENSE copy").read_text(encoding="utf-8") == "license"


@pytest.mark.skipif(os.name == "nt", reason="symlink creation requires extra Windows privileges")
def test_duplicate_symlink_copies_link_without_following_target(tmp_path) -> None:
    target = tmp_path / "target.txt"
    target.write_text("secret", encoding="utf-8")
    link = tmp_path / "link.txt"
    link.symlink_to(target)

    result = LiveDuplicateOperationService().execute_duplicate(
        DuplicateRequest((str(link),), str(tmp_path))
    )

    duplicate = tmp_path / "link copy.txt"
    assert result.summary.success_count == 1
    assert duplicate.is_symlink()
    assert duplicate.resolve() == target.resolve()
    assert duplicate.read_text(encoding="utf-8") == "secret"


def test_duplicate_reserves_names_for_multiple_sources(tmp_path) -> None:
    first = tmp_path / "report.pdf"
    second = tmp_path / "report copy.pdf"
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")

    result = LiveDuplicateOperationService().execute_duplicate(
        DuplicateRequest((str(first), str(second)), str(tmp_path))
    )

    assert result.summary.success_count == 2
    assert (tmp_path / "report copy 2.pdf").read_text(encoding="utf-8") == "first"
    assert (tmp_path / "report copy copy.pdf").read_text(encoding="utf-8") == "second"


def test_duplicate_continues_after_one_copy_failure(tmp_path) -> None:
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")

    class FailingAdapter(LocalFileOperationAdapter):
        def copy_path(self, source: str, destination: str) -> None:
            if source.endswith("first.txt"):
                raise OSError("permission denied")
            super().copy_path(source, destination)

    result = LiveDuplicateOperationService(adapter=FailingAdapter()).execute_duplicate(
        DuplicateRequest((str(first), str(second)), str(tmp_path))
    )

    assert result.summary.success_count == 1
    assert result.summary.failure_count == 1
    assert (tmp_path / "second copy.txt").exists()


def test_duplicate_continues_after_one_preflight_failure(tmp_path) -> None:
    valid = tmp_path / "valid.txt"
    valid.write_text("valid", encoding="utf-8")

    result = LiveDuplicateOperationService().execute_duplicate(
        DuplicateRequest((str(tmp_path / "missing.txt"), str(valid)), str(tmp_path))
    )

    assert result.summary.success_count == 1
    assert result.summary.failure_count == 1
    assert (tmp_path / "valid copy.txt").read_text(encoding="utf-8") == "valid"


def test_duplicate_rejects_destination_inside_source_directory(tmp_path) -> None:
    source = tmp_path / "docs"
    source.mkdir()
    destination = source / "nested"
    destination.mkdir()

    result = LiveDuplicateOperationService().execute_duplicate(
        DuplicateRequest((str(source),), str(destination))
    )

    assert result.summary.success_count == 0
    assert result.summary.failure_count == 1
    assert "own contents" in result.summary.failures[0].message
