"""Tests for the grep results save service."""

from pathlib import Path

import pytest

from zivo.services.grep_export import FakeGrepExportService, LiveGrepExportService
from zivo.state.models import GrepSearchResultState


def _result(path: Path, line_number: int, line_text: str) -> GrepSearchResultState:
    return GrepSearchResultState(
        path=str(path),
        display_path=path.name,
        line_number=line_number,
        line_text=line_text,
    )


def test_fake_service_records_save_request() -> None:
    service = FakeGrepExportService()

    result = service.export(output_path="/tmp/out.txt", context_lines=3, results=())

    assert result == "/tmp/out.txt"
    assert service.exported == [
        {"output_path": "/tmp/out.txt", "context_lines": 3, "result_count": 0}
    ]


def test_fake_service_reports_configured_failure() -> None:
    service = FakeGrepExportService(failure_message="Disk full")

    with pytest.raises(OSError, match="Disk full"):
        service.export(output_path="/tmp/out.txt", context_lines=3, results=())


def test_live_service_writes_result_and_configured_context(tmp_path: Path) -> None:
    source = tmp_path / "main.py"
    source.write_text("one\ntwo\nneedle\nfour\nfive\n")
    output = tmp_path / "grep_results.txt"
    service = LiveGrepExportService()

    service.export(
        output_path=str(output),
        context_lines=1,
        results=(_result(source, 3, "needle"),),
    )

    assert output.read_text() == "main.py:3: needle\n2: two\n3: needle\n4: four\n"


def test_live_service_handles_missing_context_file(tmp_path: Path) -> None:
    output = tmp_path / "grep_results.txt"
    service = LiveGrepExportService()

    service.export(
        output_path=str(output),
        context_lines=3,
        results=(_result(tmp_path / "missing.py", 1, "needle"),),
    )

    assert output.read_text() == "missing.py:1: needle\n"
