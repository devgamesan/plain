from pathlib import Path

import pytest

from zivo.services import InvalidFileSearchQueryError, LiveFileSearchService


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


def test_live_file_search_service_matches_case_insensitively_and_includes_directories(
    tmp_path,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "Readings").mkdir()
    (root / "README.MD").write_text("upper\n", encoding="utf-8")

    service = LiveFileSearchService()

    all_results = service.search(str(root), "read", show_hidden=False, search_target="all")
    assert {r.display_path for r in all_results} == {"Readings", "README.MD"}

    files_results = service.search(str(root), "read", show_hidden=False, search_target="files")
    assert [r.display_path for r in files_results] == ["README.MD"]

    dirs_results = service.search(str(root), "read", show_hidden=False, search_target="directories")
    assert [r.display_path for r in dirs_results] == ["Readings"]


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


def test_live_file_search_service_skips_entries_with_permission_errors_during_walk(
    tmp_path,
    monkeypatch,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    blocked = root / "blocked"
    blocked.mkdir()
    (blocked / "README-blocked.md").write_text("blocked\n", encoding="utf-8")
    ok = root / "ok"
    ok.mkdir()
    (ok / "README-ok.md").write_text("ok\n", encoding="utf-8")
    later = root / "later"
    later.mkdir()
    (later / "README-later.md").write_text("later\n", encoding="utf-8")

    original_is_dir = Path.is_dir

    def raising_is_dir(path: Path) -> bool:
        if path == blocked:
            raise PermissionError("denied")
        return original_is_dir(path)

    monkeypatch.setattr(Path, "is_dir", raising_is_dir)

    service = LiveFileSearchService()

    results = service.search(str(root), "read", show_hidden=False)

    assert [result.display_path for result in results] == [
        "later/README-later.md",
        "ok/README-ok.md",
    ]


def test_live_file_search_service_skips_entries_with_generic_os_errors_during_walk(
    tmp_path,
    monkeypatch,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    broken = root / "broken"
    broken.mkdir()
    (broken / "README-broken.md").write_text("broken\n", encoding="utf-8")
    ok = root / "ok"
    ok.mkdir()
    (ok / "README-ok.md").write_text("ok\n", encoding="utf-8")

    original_is_dir = Path.is_dir

    def raising_is_dir(path: Path) -> bool:
        if path == broken:
            raise OSError("transient failure")
        return original_is_dir(path)

    monkeypatch.setattr(Path, "is_dir", raising_is_dir)

    service = LiveFileSearchService()

    results = service.search(str(root), "read", show_hidden=False)

    assert [result.display_path for result in results] == ["ok/README-ok.md"]


def test_live_file_search_service_respects_max_results(tmp_path) -> None:
    """max_results が指定されている場合、結果が制限されることを確認."""
    root = tmp_path / "project"
    root.mkdir()

    # 100個のファイルを作成
    for index in range(100):
        (root / f"file_{index:03d}.txt").write_text(f"content {index}\n", encoding="utf-8")

    service = LiveFileSearchService()

    # max_results=10 を指定
    results = service.search(str(root), "file", show_hidden=False, max_results=10)

    # 結果が10件に制限されていることを確認
    assert len(results) == 10
    # 結果がソートされていることを確認
    display_paths = [result.display_path for result in results]
    assert display_paths == sorted(display_paths, key=str.casefold)


def test_live_file_search_service_no_limit_when_max_results_is_none(tmp_path) -> None:
    """max_results=None の場合、全結果が返されることを確認."""
    root = tmp_path / "project"
    root.mkdir()

    # 50個のファイルを作成
    for index in range(50):
        (root / f"file_{index:02d}.txt").write_text(f"content {index}\n", encoding="utf-8")

    service = LiveFileSearchService()

    # max_results=None（制限なし）を指定
    results = service.search(str(root), "file", show_hidden=False, max_results=None)

    # 全結果（50件）が返されることを確認
    assert len(results) == 50


def test_live_file_search_service_returns_sorted_results_with_limit(tmp_path) -> None:
    """max_results が指定されている場合でも、結果がソートされていることを確認."""
    root = tmp_path / "project"
    root.mkdir()

    # 辞書順でないファイル名を作成
    for name in ["z_file.txt", "a_file.txt", "m_file.txt", "b_file.txt"]:
        (root / name).write_text("content\n", encoding="utf-8")

    service = LiveFileSearchService()
    results = service.search(str(root), "file", show_hidden=False, max_results=3)

    # 3件が返されることを確認
    assert len(results) == 3
    # 結果がソートされていることを確認（ただし、辞書順の最初の3件とは限らない）
    display_paths = [result.display_path for result in results]
    assert display_paths == sorted(display_paths, key=str.casefold)
