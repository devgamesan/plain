from pathlib import Path

import pytest

import zivo.services.text_replace as text_replace_module
from zivo.models import TextReplaceRequest
from zivo.services.text_replace import (
    InvalidTextReplaceQueryError,
    LiveTextReplaceService,
)


def test_live_text_replace_service_previews_and_applies_plain_text(tmp_path: Path) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("todo item\ntodo again\n", encoding="utf-8")
    service = LiveTextReplaceService()
    request = TextReplaceRequest(
        paths=(str(target),),
        find_text="todo",
        replace_text="done",
    )

    preview = service.preview(request)

    assert preview.total_match_count == 2
    assert preview.changed_entries[0].first_match_line_number == 1
    assert preview.changed_entries[0].first_match_before == "todo item"
    assert preview.changed_entries[0].first_match_after == "done item"
    assert preview.changed_entries[0].diff_text == preview.diff_text
    assert "--- " in preview.diff_text
    assert "+++ " in preview.diff_text

    result = service.apply(request)

    assert result.changed_paths == (str(target),)
    assert result.total_match_count == 2
    assert target.read_text(encoding="utf-8") == "done item\ndone again\n"


def test_live_text_replace_service_builds_per_file_diff_entries(tmp_path: Path) -> None:
    first = tmp_path / "notes.txt"
    second = tmp_path / "tasks.txt"
    first.write_text("todo item\n", encoding="utf-8")
    second.write_text("todo again\n", encoding="utf-8")
    service = LiveTextReplaceService()

    preview = service.preview(
        TextReplaceRequest(
            paths=(str(second), str(first)),
            find_text="todo",
            replace_text="done",
        )
    )

    assert [Path(entry.path).name for entry in preview.changed_entries] == [
        "notes.txt",
        "tasks.txt",
    ]
    assert all(
        "--- " in entry.diff_text and "+++ " in entry.diff_text
        for entry in preview.changed_entries
    )
    assert preview.changed_entries[0].diff_text != preview.changed_entries[1].diff_text


def test_live_text_replace_service_rejects_invalid_regex(tmp_path: Path) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("todo item\n", encoding="utf-8")
    service = LiveTextReplaceService()

    with pytest.raises(InvalidTextReplaceQueryError):
        service.preview(
            TextReplaceRequest(
                paths=(str(target),),
                find_text="re:(",
                replace_text="done",
            )
        )


def test_live_text_replace_service_apply_reuses_matcher_without_diff_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = tmp_path / "b.txt"
    second = tmp_path / "a.txt"
    first.write_text("todo one\n", encoding="utf-8")
    second.write_text("todo two\n", encoding="utf-8")
    service = LiveTextReplaceService()
    request = TextReplaceRequest(
        paths=(str(first), str(second)),
        find_text="todo",
        replace_text="done",
    )
    original_compile_pattern = text_replace_module._compile_pattern
    compile_count = 0

    def compile_pattern_spy(query: str):
        nonlocal compile_count
        compile_count += 1
        return original_compile_pattern(query)

    def fail_build_unified_diff(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("apply should not build preview diffs")

    monkeypatch.setattr(text_replace_module, "_compile_pattern", compile_pattern_spy)
    monkeypatch.setattr(text_replace_module, "_build_unified_diff", fail_build_unified_diff)

    result = service.apply(request)

    assert compile_count == 1
    assert result.changed_paths == (str(second), str(first))
    assert result.total_match_count == 2
    assert first.read_text(encoding="utf-8") == "done one\n"
    assert second.read_text(encoding="utf-8") == "done two\n"


def test_text_replace_cancels_between_files_without_partial_temporary_files(tmp_path) -> None:
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("todo one\n", encoding="utf-8")
    second.write_text("todo two\n", encoding="utf-8")
    progress_events: list[tuple[int, int | None, str | None]] = []

    result = LiveTextReplaceService().apply(
        TextReplaceRequest(
            paths=(str(first), str(second)),
            find_text="todo",
            replace_text="done",
        ),
        progress_callback=lambda completed, total, current: progress_events.append(
            (completed, total, current)
        ),
        cancel_callback=lambda: len(progress_events) >= 1,
    )

    assert result.cancelled is True
    assert result.changed_paths == (str(first),)
    assert result.unprocessed_paths == (str(second),)
    assert first.read_text(encoding="utf-8") == "done one\n"
    assert second.read_text(encoding="utf-8") == "todo two\n"
    assert list(tmp_path.glob(".*.zivo-*")) == []
