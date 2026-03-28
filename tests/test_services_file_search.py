import pytest

from peneo.services import InvalidFileSearchQueryError, LiveFileSearchService


def test_live_file_search_service_matches_files_recursively(tmp_path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    docs = root / "docs"
    docs.mkdir()
    (docs / "README.md").write_text("readme\n", encoding="utf-8")
    (docs / "guide.txt").write_text("guide\n", encoding="utf-8")

    service = LiveFileSearchService()

    results = service.search(str(root), "read", show_hidden=False)

    assert [result.display_path for result in results] == ["docs/README.md"]


def test_live_file_search_service_skips_hidden_paths_when_disabled(tmp_path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    hidden_dir = root / ".secret"
    hidden_dir.mkdir()
    (hidden_dir / "README.md").write_text("secret\n", encoding="utf-8")

    service = LiveFileSearchService()

    hidden_off = service.search(str(root), "read", show_hidden=False)
    hidden_on = service.search(str(root), "read", show_hidden=True)

    assert hidden_off == ()
    assert [result.display_path for result in hidden_on] == [".secret/README.md"]


def test_live_file_search_service_matches_case_insensitively_and_ignores_directories(
    tmp_path,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "Readings").mkdir()
    (root / "README.MD").write_text("upper\n", encoding="utf-8")

    service = LiveFileSearchService()

    results = service.search(str(root), "read", show_hidden=False)

    assert [result.display_path for result in results] == ["README.MD"]


def test_live_file_search_service_supports_regex_queries_with_re_prefix(tmp_path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "README.md").write_text("readme\n", encoding="utf-8")
    (root / "guide.txt").write_text("guide\n", encoding="utf-8")

    service = LiveFileSearchService()

    results = service.search(str(root), r"re:^README\.md$", show_hidden=False)

    assert [result.display_path for result in results] == ["README.md"]


def test_live_file_search_service_uses_python_regex_case_rules(tmp_path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "README.md").write_text("readme\n", encoding="utf-8")

    service = LiveFileSearchService()

    case_sensitive = service.search(str(root), r"re:^readme\.md$", show_hidden=False)
    case_insensitive = service.search(str(root), r"re:(?i)^readme\.md$", show_hidden=False)

    assert case_sensitive == ()
    assert [result.display_path for result in case_insensitive] == ["README.md"]


def test_live_file_search_service_raises_invalid_query_for_bad_regex(tmp_path) -> None:
    root = tmp_path / "project"
    root.mkdir()

    service = LiveFileSearchService()

    with pytest.raises(InvalidFileSearchQueryError, match="Invalid regex"):
        service.search(str(root), "re:[", show_hidden=False)


def test_live_file_search_service_stops_when_cancelled(tmp_path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    for index in range(3):
        nested = root / f"dir-{index}"
        nested.mkdir()
        (nested / f"README-{index}.md").write_text("readme\n", encoding="utf-8")

    service = LiveFileSearchService()
    cancelled = False

    def is_cancelled() -> bool:
        nonlocal cancelled
        cancelled = True
        return True

    results = service.search(str(root), "read", show_hidden=False, is_cancelled=is_cancelled)

    assert cancelled is True
    assert results == ()
