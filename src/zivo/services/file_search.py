"""Recursive file-search services for the command palette."""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

from zivo.state.models import FileSearchResultState


class FileSearchService(Protocol):
    """Boundary for recursive filename searches."""

    def search(
        self,
        root_path: str,
        query: str,
        *,
        show_hidden: bool,
        max_results: int | None = None,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> tuple[FileSearchResultState, ...]: ...


_REGEX_QUERY_PREFIX = "re:"


class InvalidFileSearchQueryError(ValueError):
    """Raised when the file-search query cannot be interpreted."""


@dataclass(frozen=True)
class ParsedFileSearchQuery:
    """Normalized file-search query used by the search service."""

    raw_query: str
    mode: Literal["plain", "regex"]
    normalized_plain_query: str = ""
    pattern: re.Pattern[str] | None = None

    @property
    def is_regex(self) -> bool:
        return self.mode == "regex"

    def matches(self, filename: str) -> bool:
        if self.pattern is not None:
            return self.pattern.search(filename) is not None
        return self.normalized_plain_query in filename.casefold()


def is_regex_file_search_query(query: str) -> bool:
    """Return whether the trimmed query uses regex mode."""

    return query.strip().startswith(_REGEX_QUERY_PREFIX)


def parse_file_search_query(query: str) -> ParsedFileSearchQuery:
    """Parse a file-search query into plain or regex matching mode."""

    stripped_query = query.strip()
    if is_regex_file_search_query(stripped_query):
        pattern_source = stripped_query[len(_REGEX_QUERY_PREFIX) :]
        try:
            pattern = re.compile(pattern_source)
        except re.error as error:
            raise InvalidFileSearchQueryError(f"Invalid regex: {error}") from error
        return ParsedFileSearchQuery(
            raw_query=stripped_query,
            mode="regex",
            pattern=pattern,
        )
    return ParsedFileSearchQuery(
        raw_query=stripped_query,
        mode="plain",
        normalized_plain_query=stripped_query.casefold(),
    )


def _is_walkable_directory(path: Path) -> bool:
    """Return whether a path should be traversed, skipping unreadable entries."""

    try:
        return path.is_dir()
    except OSError:
        return False


@dataclass(frozen=True)
class LiveFileSearchService:
    """Search the local filesystem for matching filenames."""

    def search(
        self,
        root_path: str,
        query: str,
        *,
        show_hidden: bool,
        max_results: int | None = None,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> tuple[FileSearchResultState, ...]:
        parsed_query = parse_file_search_query(query)
        if not parsed_query.raw_query:
            return ()

        root = Path(root_path).expanduser().resolve()
        if not root.exists():
            raise OSError(f"Not found: {root}")
        if not root.is_dir():
            raise OSError(f"Not a directory: {root}")

        results: list[FileSearchResultState] = []
        stack = [root]

        while stack:
            if is_cancelled is not None and is_cancelled():
                return ()
            directory = stack.pop()
            try:
                children = tuple(directory.iterdir())
            except (FileNotFoundError, PermissionError):
                continue

            for child in children:
                if is_cancelled is not None and is_cancelled():
                    return ()
                if not show_hidden and child.name.startswith("."):
                    continue
                if _is_walkable_directory(child):
                    stack.append(child)
                    continue
                if not parsed_query.matches(child.name):
                    continue
                results.append(
                    FileSearchResultState(
                        path=str(child),
                        display_path=str(child.relative_to(root)),
                    )
                )

                # max_results が指定されている場合のみ制限を適用
                if max_results is not None and len(results) >= max_results:
                    # 早期終了する前にソート
                    results.sort(key=lambda result: result.display_path.casefold())
                    return tuple(results)

        results.sort(key=lambda result: result.display_path.casefold())
        return tuple(results)


@dataclass
class FakeFileSearchService:
    """Deterministic file-search service used by tests."""

    results_by_query: dict[tuple[str, str, bool], tuple[FileSearchResultState, ...]] = field(
        default_factory=dict
    )
    failure_messages: dict[tuple[str, str, bool], str] = field(default_factory=dict)
    invalid_query_messages: dict[tuple[str, str, bool], str] = field(default_factory=dict)
    executed_requests: list[tuple[str, str, bool]] = field(default_factory=list)

    def search(
        self,
        root_path: str,
        query: str,
        *,
        show_hidden: bool,
        max_results: int | None = None,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> tuple[FileSearchResultState, ...]:
        key = (root_path, query, show_hidden)
        self.executed_requests.append(key)
        if is_cancelled is not None and is_cancelled():
            return ()
        if key in self.invalid_query_messages:
            raise InvalidFileSearchQueryError(self.invalid_query_messages[key])
        if key in self.failure_messages:
            raise OSError(self.failure_messages[key])

        results = self.results_by_query.get(key, ())

        # max_results が指定されている場合のみ制限を適用
        if max_results is not None and len(results) > max_results:
            limited_results = tuple(
                sorted(results, key=lambda r: r.display_path.casefold())[:max_results]
            )
            return limited_results

        return results
