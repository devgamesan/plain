"""Recursive grep-search services for the command palette."""

import glob as glob_module
import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from zivo.state.models import GrepSearchResultState

_REGEX_QUERY_PREFIX = "re:"
GrepSearchProgressCallback = Callable[[tuple[GrepSearchResultState, ...], bool], None]
_SEARCH_BATCH_SIZE = 32


class GrepSearchService(Protocol):
    """Boundary for recursive content searches."""

    def search(
        self,
        root_path: str,
        query: str,
        *,
        show_hidden: bool,
        include_globs: tuple[str, ...] = (),
        exclude_globs: tuple[str, ...] = (),
        target_paths: tuple[str, ...] = (),
        filename_filter: str = "",
        max_results: int | None = None,
        is_cancelled: Callable[[], bool] | None = None,
        on_results: GrepSearchProgressCallback | None = None,
    ) -> tuple[GrepSearchResultState, ...]: ...


class InvalidGrepSearchQueryError(ValueError):
    """Raised when the grep query cannot be interpreted."""


def is_regex_grep_search_query(query: str) -> bool:
    """Return whether the trimmed query uses regex mode."""

    return query.strip().startswith(_REGEX_QUERY_PREFIX)


@dataclass(frozen=True)
class LiveGrepSearchService:
    """Search file contents recursively with ripgrep."""

    rg_executable: str = "rg"

    def search(
        self,
        root_path: str,
        query: str,
        *,
        show_hidden: bool,
        include_globs: tuple[str, ...] = (),
        exclude_globs: tuple[str, ...] = (),
        target_paths: tuple[str, ...] = (),
        filename_filter: str = "",
        max_results: int | None = None,
        is_cancelled: Callable[[], bool] | None = None,
        on_results: GrepSearchProgressCallback | None = None,
    ) -> tuple[GrepSearchResultState, ...]:
        stripped_query = query.strip()
        if not stripped_query:
            return ()

        root = Path(root_path).expanduser().resolve()
        if not root.exists():
            raise OSError(f"Not found: {root}")
        if not root.is_dir():
            raise OSError(f"Not a directory: {root}")
        if max_results is not None and max_results <= 0:
            return ()

        search_paths = self._resolve_search_paths(root, target_paths)
        if target_paths and not search_paths:
            return ()

        command = self._build_command(
            stripped_query,
            show_hidden=show_hidden,
            include_globs=include_globs,
            exclude_globs=exclude_globs,
            target_paths=search_paths,
            filename_filter=filename_filter,
        )
        try:
            process = subprocess.Popen(
                command,
                cwd=root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except FileNotFoundError as error:
            raise OSError(f"Not found: {self.rg_executable}") from error

        try:
            results: list[GrepSearchResultState] = []
            pending_results: list[GrepSearchResultState] = []
            previous_sort_key: tuple[str, int] | None = None
            results_are_sorted = True

            def emit_results(*, truncated: bool = False) -> None:
                if on_results is None or (not pending_results and not truncated):
                    return
                on_results(tuple(pending_results), truncated)
                pending_results.clear()

            assert process.stdout is not None
            for line in process.stdout:
                if is_cancelled is not None and is_cancelled():
                    process.kill()
                    process.wait()
                    return ()
                result = self._parse_result_line(root, line)
                if result is not None:
                    if max_results is not None and len(results) >= max_results:
                        _stop_process(process)
                        emit_results(truncated=True)
                        return _ordered_grep_results(results, results_are_sorted)
                    sort_key = _grep_result_sort_key(result)
                    if previous_sort_key is not None and sort_key < previous_sort_key:
                        results_are_sorted = False
                    previous_sort_key = sort_key
                    results.append(result)
                    pending_results.append(result)
                    if len(results) == 1 or len(pending_results) >= _SEARCH_BATCH_SIZE:
                        emit_results()
            stderr_text = ""
            if process.stderr is not None:
                stderr_text = process.stderr.read()
            return_code = process.wait()
            emit_results()
        finally:
            if process.stdout is not None:
                process.stdout.close()
            if process.stderr is not None:
                process.stderr.close()

        if return_code not in {0, 1}:
            message = stderr_text.strip() or "grep search failed"
            if self._is_nonfatal_ripgrep_error(return_code, stderr_text, stripped_query):
                return _ordered_grep_results(results, results_are_sorted)
            if is_regex_grep_search_query(stripped_query):
                raise InvalidGrepSearchQueryError(message)
            raise OSError(message)

        return _ordered_grep_results(results, results_are_sorted)

    def _build_command(
        self,
        query: str,
        *,
        show_hidden: bool,
        include_globs: tuple[str, ...] = (),
        exclude_globs: tuple[str, ...] = (),
        target_paths: tuple[str, ...] = (),
        filename_filter: str = "",
    ) -> list[str]:
        command = [
            self.rg_executable,
            "--json",
            "--line-number",
            "--color",
            "never",
            "--no-heading",
            "--no-ignore",
            "--no-messages",
        ]
        if show_hidden:
            command.append("--hidden")
        for glob in include_globs:
            command.extend(["-g", glob])
        for glob in exclude_globs:
            command.extend(["-g", f"!{glob}"])
        filename_glob = _filename_filter_glob(filename_filter)
        if filename_glob is not None:
            command.extend(["--glob-case-insensitive", "-g", filename_glob])
        if is_regex_grep_search_query(query):
            command.extend(["-e", query.strip()[len(_REGEX_QUERY_PREFIX) :]])
        else:
            command.extend(["--fixed-strings", "--ignore-case", "-e", query])
        command.append("--")
        command.extend(target_paths or (".",))
        return command

    @staticmethod
    def _resolve_search_paths(root: Path, target_paths: tuple[str, ...]) -> tuple[str, ...]:
        if not target_paths:
            return ()

        resolved_paths: list[str] = []
        for target_path in target_paths:
            candidate = Path(target_path).expanduser()
            if not candidate.is_absolute():
                candidate = root / candidate
            candidate = candidate.resolve(strict=False)
            try:
                relative_path = candidate.relative_to(root)
            except ValueError:
                continue
            if not candidate.exists():
                continue
            relative_text = relative_path.as_posix() or "."
            if relative_text not in resolved_paths:
                resolved_paths.append(relative_text)
        return tuple(resolved_paths)

    def _parse_result_line(
        self,
        root: Path,
        line: str,
    ) -> GrepSearchResultState | None:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return None
        if payload.get("type") != "match":
            return None
        data = payload.get("data", {})
        path_text = data.get("path", {}).get("text")
        raw_line = data.get("lines", {}).get("text", "")
        line_number = data.get("line_number")
        column_number = _first_submatch_column(data.get("submatches"))
        if not isinstance(path_text, str) or not isinstance(raw_line, str):
            return None
        if not isinstance(line_number, int):
            return None
        absolute_path = Path(path_text)
        if not absolute_path.is_absolute():
            absolute_path = (root / path_text).resolve()
        return GrepSearchResultState(
            path=str(absolute_path),
            display_path=self._relative_display_path(root, absolute_path),
            line_number=line_number,
            line_text=raw_line.rstrip("\r\n"),
            column_number=column_number,
        )

    @staticmethod
    def _relative_display_path(root: Path, path: Path) -> str:
        try:
            return path.relative_to(root).as_posix()
        except ValueError:
            return path.as_posix()

    @staticmethod
    def _is_nonfatal_ripgrep_error(return_code: int, stderr_text: str, query: str) -> bool:
        return (
            return_code == 2
            and not stderr_text.strip()
            and not is_regex_grep_search_query(query)
        )


@dataclass
class FakeGrepSearchService:
    """Deterministic grep-search service used by tests."""

    results_by_query: dict[
        tuple[str, str, tuple[str, ...], tuple[str, ...], bool],
        tuple[GrepSearchResultState, ...],
    ] = field(default_factory=dict)
    failure_messages: dict[tuple[str, str, tuple[str, ...], tuple[str, ...], bool], str] = field(
        default_factory=dict
    )
    invalid_query_messages: dict[
        tuple[str, str, tuple[str, ...], tuple[str, ...], bool],
        str,
    ] = field(default_factory=dict)
    executed_requests: list[tuple[str, str, tuple[str, ...], tuple[str, ...], bool]] = field(
        default_factory=list
    )
    executed_search_options: list[tuple[tuple[str, ...], str, int | None]] = field(
        default_factory=list
    )

    def search(
        self,
        root_path: str,
        query: str,
        *,
        show_hidden: bool,
        include_globs: tuple[str, ...] = (),
        exclude_globs: tuple[str, ...] = (),
        target_paths: tuple[str, ...] = (),
        filename_filter: str = "",
        max_results: int | None = None,
        is_cancelled: Callable[[], bool] | None = None,
        on_results: GrepSearchProgressCallback | None = None,
    ) -> tuple[GrepSearchResultState, ...]:
        key = (root_path, query, include_globs, exclude_globs, show_hidden)
        self.executed_requests.append(key)
        self.executed_search_options.append((target_paths, filename_filter, max_results))
        if is_cancelled is not None and is_cancelled():
            return ()
        if key in self.invalid_query_messages:
            raise InvalidGrepSearchQueryError(self.invalid_query_messages[key])
        if key in self.failure_messages:
            raise OSError(self.failure_messages[key])
        results = self.results_by_query.get(key, ())
        if max_results is not None:
            truncated = len(results) > max_results
            limited_results = results[:max_results]
            if on_results is not None and limited_results:
                on_results(limited_results, truncated)
            elif on_results is not None and truncated:
                on_results((), True)
            return limited_results
        if on_results is not None and results:
            on_results(results, False)
        return results


def _filename_filter_glob(filename_filter: str) -> str | None:
    """Translate a plain basename filter to an rg glob when it is safe to do so."""

    if not filename_filter or is_regex_grep_search_query(filename_filter):
        return None
    if "/" in filename_filter or "\\" in filename_filter:
        return None
    return f"*{glob_module.escape(filename_filter)}*"


def _stop_process(process: subprocess.Popen[str]) -> None:
    try:
        process.kill()
    except ProcessLookupError:
        pass
    process.wait()


def _first_submatch_column(submatches: object) -> int:
    if not isinstance(submatches, list):
        return 1
    for submatch in submatches:
        if not isinstance(submatch, dict):
            continue
        start = submatch.get("start")
        if isinstance(start, int):
            return max(1, start + 1)
    return 1


def _ordered_grep_results(
    results: list[GrepSearchResultState],
    results_are_sorted: bool,
) -> tuple[GrepSearchResultState, ...]:
    if results_are_sorted:
        return tuple(results)
    return tuple(sorted(results, key=_grep_result_sort_key))


def _grep_result_sort_key(result: GrepSearchResultState) -> tuple[str, int]:
    return (result.display_path.casefold(), result.line_number)
