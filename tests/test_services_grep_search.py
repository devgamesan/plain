import builtins
import json
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


class _FakeTextStream:
    def __init__(self, lines: tuple[str, ...] = (), read_text: str = "") -> None:
        self._lines = lines
        self._read_text = read_text
        self.closed = False

    def __iter__(self):
        return iter(self._lines)

    def read(self) -> str:
        return self._read_text

    def close(self) -> None:
        self.closed = True


class _FakeGrepProcess:
    def __init__(
        self,
        stdout_lines: tuple[str, ...],
        *,
        return_code: int = 0,
        stderr_text: str = "",
    ) -> None:
        self.stdout = _FakeTextStream(stdout_lines)
        self.stderr = _FakeTextStream(read_text=stderr_text)
        self.return_code = return_code
        self.killed = False

    def wait(self) -> int:
        return self.return_code

    def kill(self) -> None:
        self.killed = True


def _rg_match_line(
    path: str,
    *,
    line_number: int,
    text: str,
    start: int = 0,
) -> str:
    return json.dumps(
        {
            "type": "match",
            "data": {
                "path": {"text": path},
                "lines": {"text": text},
                "line_number": line_number,
                "submatches": [{"start": start}],
            },
        }
    )


def test_live_grep_search_service_parses_stdout_lines_as_they_are_read(
    tmp_path,
    monkeypatch,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    process = _FakeGrepProcess(
        (
            _rg_match_line("z.txt", line_number=2, text="TODO: z\n", start=6),
            json.dumps({"type": "begin", "data": {"path": {"text": "z.txt"}}}),
            "{not json}\n",
            _rg_match_line("a.txt", line_number=1, text="TODO: a\r\n", start=0),
        )
    )

    monkeypatch.setattr(
        "zivo.services.grep_search.subprocess.Popen",
        lambda *args, **kwargs: process,
    )

    results = LiveGrepSearchService().search(str(root), "todo", show_hidden=False)

    assert [result.display_label for result in results] == [
        "a.txt:1: TODO: a",
        "z.txt:2: TODO: z",
    ]
    assert [result.column_number for result in results] == [1, 7]
    assert process.stdout.closed
    assert process.stderr.closed


def test_live_grep_search_service_skips_sort_for_ordered_stdout_lines(
    tmp_path,
    monkeypatch,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    process = _FakeGrepProcess(
        (
            _rg_match_line("a.txt", line_number=1, text="TODO: a\n"),
            _rg_match_line("a.txt", line_number=2, text="TODO: a2\n"),
            _rg_match_line("z.txt", line_number=1, text="TODO: z\n"),
        )
    )
    sorted_calls = 0

    def counting_sorted(*args, **kwargs):
        nonlocal sorted_calls
        sorted_calls += 1
        return builtins.sorted(*args, **kwargs)

    monkeypatch.setattr(
        "zivo.services.grep_search.subprocess.Popen",
        lambda *args, **kwargs: process,
    )
    monkeypatch.setattr("zivo.services.grep_search.sorted", counting_sorted, raising=False)

    results = LiveGrepSearchService().search(str(root), "todo", show_hidden=False)

    assert [result.display_label for result in results] == [
        "a.txt:1: TODO: a",
        "a.txt:2: TODO: a2",
        "z.txt:1: TODO: z",
    ]
    assert sorted_calls == 0


def test_live_grep_search_service_builds_target_and_filename_filters(
    tmp_path,
    monkeypatch,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    target = root / "docs"
    target.mkdir()
    process = _FakeGrepProcess(())
    commands: list[list[str]] = []

    def fake_popen(command, **kwargs):
        commands.append(command)
        return process

    monkeypatch.setattr("zivo.services.grep_search.subprocess.Popen", fake_popen)

    LiveGrepSearchService().search(
        str(root),
        "todo",
        show_hidden=False,
        target_paths=(str(target),),
        filename_filter="readme",
    )

    assert commands == [
        [
            "rg",
            "--json",
            "--line-number",
            "--color",
            "never",
            "--no-heading",
            "--no-ignore",
            "--no-messages",
            "--glob-case-insensitive",
            "-g",
            "*readme*",
            "--fixed-strings",
            "--ignore-case",
            "-e",
            "todo",
            "--",
            "docs",
        ]
    ]
    assert process.stdout.closed
    assert process.stderr.closed


def test_live_grep_search_service_stops_process_at_max_results(
    tmp_path,
    monkeypatch,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    process = _FakeGrepProcess(
        (
            _rg_match_line("a.txt", line_number=1, text="TODO a\n"),
            _rg_match_line("b.txt", line_number=1, text="TODO b\n"),
            _rg_match_line("c.txt", line_number=1, text="TODO c\n"),
        )
    )
    monkeypatch.setattr(
        "zivo.services.grep_search.subprocess.Popen",
        lambda *args, **kwargs: process,
    )

    results = LiveGrepSearchService().search(
        str(root),
        "todo",
        show_hidden=False,
        max_results=2,
    )

    assert [result.display_path for result in results] == ["a.txt", "b.txt"]
    assert process.killed is True
    assert process.stdout.closed
    assert process.stderr.closed


def test_live_grep_search_service_sorts_when_stdout_order_regresses(
    tmp_path,
    monkeypatch,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    process = _FakeGrepProcess(
        (
            _rg_match_line("z.txt", line_number=1, text="TODO: z\n"),
            _rg_match_line("a.txt", line_number=1, text="TODO: a\n"),
        )
    )
    sorted_calls = 0

    def counting_sorted(*args, **kwargs):
        nonlocal sorted_calls
        sorted_calls += 1
        return builtins.sorted(*args, **kwargs)

    monkeypatch.setattr(
        "zivo.services.grep_search.subprocess.Popen",
        lambda *args, **kwargs: process,
    )
    monkeypatch.setattr("zivo.services.grep_search.sorted", counting_sorted, raising=False)

    results = LiveGrepSearchService().search(str(root), "todo", show_hidden=False)

    assert [result.display_label for result in results] == [
        "a.txt:1: TODO: a",
        "z.txt:1: TODO: z",
    ]
    assert sorted_calls == 1


def test_live_grep_search_service_keeps_nonfatal_error_partial_results(
    tmp_path,
    monkeypatch,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    process = _FakeGrepProcess(
        (_rg_match_line("README.md", line_number=3, text="TODO\n"),),
        return_code=2,
        stderr_text="",
    )

    monkeypatch.setattr(
        "zivo.services.grep_search.subprocess.Popen",
        lambda *args, **kwargs: process,
    )

    results = LiveGrepSearchService().search(str(root), "todo", show_hidden=False)

    assert [result.display_label for result in results] == ["README.md:3: TODO"]


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
def test_live_grep_search_service_restricts_targets_and_filename_filter(tmp_path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    docs = root / "docs"
    docs.mkdir()
    (docs / "README.md").write_text("TODO: docs\n", encoding="utf-8")
    (docs / "guide.md").write_text("TODO: guide\n", encoding="utf-8")
    (root / "README.md").write_text("TODO: root\n", encoding="utf-8")

    results = LiveGrepSearchService().search(
        str(root),
        "todo",
        show_hidden=False,
        target_paths=(str(docs),),
        filename_filter="readme",
    )

    assert [result.display_path for result in results] == ["docs/README.md"]


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
