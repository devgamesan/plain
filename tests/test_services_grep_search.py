import os
import shutil

import pytest

from zivo.services import InvalidGrepSearchQueryError, LiveGrepSearchService

skip_if_no_rg = pytest.mark.skipif(
    shutil.which("rg") is None,
    reason="ripgrep (rg) not available",
)
skip_if_windows_permission_semantics = pytest.mark.skipif(
    shutil.which("rg") is None or os.name == "nt",
    reason="permission-denied grep coverage is not reliable on native Windows runners",
)


@skip_if_no_rg
def test_live_grep_search_service_matches_file_contents_recursively(tmp_path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    docs = root / "docs"
    docs.mkdir()
    (docs / "README.md").write_text("TODO: update docs\n", encoding="utf-8")
    (docs / "guide.txt").write_text("guide\n", encoding="utf-8")

    service = LiveGrepSearchService()

    results = service.search(str(root), "todo", show_hidden=False)

    assert [result.display_label for result in results] == ["docs/README.md:1: TODO: update docs"]
    assert [result.column_number for result in results] == [1]


@skip_if_no_rg
def test_live_grep_search_service_populates_file_metadata(tmp_path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    target = root / "data.txt"
    target.write_text("TODO: item\n", encoding="utf-8")
    expected_size = target.stat().st_size

    service = LiveGrepSearchService()

    results = service.search(str(root), "todo", show_hidden=False)

    assert len(results) == 1
    result = results[0]
    assert result.display_path == "data.txt"
    assert result.size_bytes == expected_size
    assert result.modified_at is not None


@skip_if_no_rg
def test_live_grep_search_service_records_first_match_column(tmp_path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "README.md").write_text("prefix TODO item\n", encoding="utf-8")

    service = LiveGrepSearchService()

    results = service.search(str(root), "todo", show_hidden=False)

    assert [result.column_number for result in results] == [8]


@skip_if_no_rg
def test_live_grep_search_service_skips_hidden_paths_when_disabled(tmp_path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    hidden_dir = root / ".secret"
    hidden_dir.mkdir()
    (hidden_dir / "README.md").write_text("TODO: hidden\n", encoding="utf-8")

    service = LiveGrepSearchService()

    hidden_off = service.search(str(root), "todo", show_hidden=False)
    hidden_on = service.search(str(root), "todo", show_hidden=True)

    assert hidden_off == ()
    assert [result.display_path for result in hidden_on] == [".secret/README.md"]


@skip_if_no_rg
def test_live_grep_search_service_supports_regex_queries_with_re_prefix(tmp_path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "README.md").write_text("TODO: readme\n", encoding="utf-8")
    (root / "guide.txt").write_text("guide\n", encoding="utf-8")

    service = LiveGrepSearchService()

    results = service.search(str(root), r"re:TODO: .*", show_hidden=False)

    assert [result.display_path for result in results] == ["README.md"]


@skip_if_no_rg
def test_live_grep_search_service_filters_matches_by_included_extensions(tmp_path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "README.md").write_text("TODO: readme\n", encoding="utf-8")
    (root / "notes.txt").write_text("TODO: notes\n", encoding="utf-8")

    service = LiveGrepSearchService()

    results = service.search(
        str(root),
        "todo",
        show_hidden=False,
        include_globs=("*.md",),
    )

    assert [result.display_path for result in results] == ["README.md"]


@skip_if_no_rg
def test_live_grep_search_service_filters_matches_by_excluded_extensions(tmp_path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "README.md").write_text("TODO: readme\n", encoding="utf-8")
    (root / "notes.log").write_text("TODO: log\n", encoding="utf-8")

    service = LiveGrepSearchService()

    results = service.search(
        str(root),
        "todo",
        show_hidden=False,
        exclude_globs=("*.log",),
    )

    assert [result.display_path for result in results] == ["README.md"]


@skip_if_no_rg
def test_live_grep_search_service_raises_invalid_query_for_bad_regex(tmp_path) -> None:
    root = tmp_path / "project"
    root.mkdir()

    service = LiveGrepSearchService()

    with pytest.raises(InvalidGrepSearchQueryError):
        service.search(str(root), "re:[", show_hidden=False)


@skip_if_windows_permission_semantics
def test_live_grep_search_service_continues_when_some_paths_are_permission_denied(
    tmp_path,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    docs = root / "docs"
    docs.mkdir()
    (docs / "README.md").write_text("TODO: update docs\n", encoding="utf-8")
    blocked = root / "blocked"
    blocked.mkdir()
    (blocked / "secret.txt").write_text("TODO: hidden\n", encoding="utf-8")

    service = LiveGrepSearchService()

    blocked.chmod(0)
    try:
        results = service.search(str(root), "todo", show_hidden=False)
    finally:
        blocked.chmod(0o700)

    assert [result.display_label for result in results] == ["docs/README.md:1: TODO: update docs"]


@skip_if_windows_permission_semantics
def test_live_grep_search_service_ignores_permission_denied_without_matches(tmp_path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    docs = root / "docs"
    docs.mkdir()
    (docs / "README.md").write_text("guide\n", encoding="utf-8")
    blocked = root / "blocked"
    blocked.mkdir()
    (blocked / "secret.txt").write_text("TODO: hidden\n", encoding="utf-8")

    service = LiveGrepSearchService()

    blocked.chmod(0)
    try:
        results = service.search(str(root), "todo", show_hidden=False)
    finally:
        blocked.chmod(0o700)

    assert results == ()
