"""Recursive file-search services for the command palette."""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

from zivo.state.models import FileSearchResultState, FileSearchTarget
from zivo.state.natural_sort import natural_sort_key

FileSearchProgressCallback = Callable[[tuple[FileSearchResultState, ...], bool], None]
_SEARCH_BATCH_SIZE = 32


class FileSearchService(Protocol):
    """Boundary for recursive filename searches."""

    def search(
        self,
        root_path: str,
        query: str,
        *,
        show_hidden: bool,
        search_target: FileSearchTarget = "all",
        include_extensions: tuple[str, ...] = (),
        exclude_extensions: tuple[str, ...] = (),
        max_results: int | None = None,
        is_cancelled: Callable[[], bool] | None = None,
        on_results: FileSearchProgressCallback | None = None,
    ) -> tuple[FileSearchResultState, ...]: ...


_REGEX_QUERY_PREFIX = "re:"


def _extension_suffix(pattern: str) -> str:
    """Convert a normalized extension glob (``*.py``) to a suffix."""

    return pattern.removeprefix("*").casefold()


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
    """Return whether a real directory should be traversed."""

    try:
        return path.is_dir() and not path.is_symlink()
    except OSError:
        return False


def _is_directory(path: Path) -> bool:
    """Return whether a path is a directory, following symlinks for classification."""

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
        search_target: FileSearchTarget = "all",
        include_extensions: tuple[str, ...] = (),
        exclude_extensions: tuple[str, ...] = (),
        max_results: int | None = None,
        is_cancelled: Callable[[], bool] | None = None,
        on_results: FileSearchProgressCallback | None = None,
    ) -> tuple[FileSearchResultState, ...]:
        parsed_query = parse_file_search_query(query)
        has_extension_filters = bool(include_extensions or exclude_extensions)
        if not parsed_query.raw_query and not has_extension_filters:
            return ()
        if search_target == "directories" and has_extension_filters:
            return ()

        root = Path(root_path).expanduser().resolve()
        if not root.exists():
            raise OSError(f"Not found: {root}")
        if not root.is_dir():
            raise OSError(f"Not a directory: {root}")

        results: list[FileSearchResultState] = []
        pending_results: list[FileSearchResultState] = []
        stack = [root]

        def emit_results(*, truncated: bool = False) -> None:
            if on_results is None or (not pending_results and not truncated):
                return
            on_results(tuple(pending_results), truncated)
            pending_results.clear()

        while stack:
            if is_cancelled is not None and is_cancelled():
                return ()
            directory = stack.pop()
            try:
                for child in directory.iterdir():
                    if is_cancelled is not None and is_cancelled():
                        return ()
                    if not show_hidden and child.name.startswith("."):
                        continue
                    is_dir = _is_directory(child)
                    if _is_walkable_directory(child):
                        stack.append(child)
                    if search_target == "directories" and not is_dir:
                        continue
                    if search_target == "files" and is_dir:
                        continue
                    if has_extension_filters:
                        if is_dir:
                            continue
                        lowered_name = child.name.casefold()
                        if include_extensions and not any(
                            lowered_name.endswith(_extension_suffix(pattern))
                            for pattern in include_extensions
                        ):
                            continue
                        if any(
                            lowered_name.endswith(_extension_suffix(pattern))
                            for pattern in exclude_extensions
                        ):
                            continue
                    if not parsed_query.matches(child.name):
                        continue
                    if max_results is not None and len(results) >= max_results:
                        emit_results(truncated=True)
                        return tuple(
                            sorted(
                                results,
                                key=lambda result: natural_sort_key(result.display_path),
                            )
                        )
                    results.append(
                        FileSearchResultState(
                            path=str(child),
                            display_path=child.relative_to(root).as_posix(),
                            entry_type="directory" if is_dir else "file",
                        )
                    )
                    pending_results.append(results[-1])
                    if len(results) == 1 or len(pending_results) >= _SEARCH_BATCH_SIZE:
                        emit_results()
            except (FileNotFoundError, PermissionError):
                continue

        emit_results()
        results.sort(key=lambda result: natural_sort_key(result.display_path))
        return tuple(results)


@dataclass
class FakeFileSearchService:
    """Deterministic file-search service used by tests."""

    results_by_query: dict[tuple[str, ...], tuple[FileSearchResultState, ...]] = field(
        default_factory=dict
    )
    failure_messages: dict[tuple[str, ...], str] = field(default_factory=dict)
    invalid_query_messages: dict[tuple[str, ...], str] = field(default_factory=dict)
    executed_requests: list[tuple[str, ...]] = field(default_factory=list)

    def search(
        self,
        root_path: str,
        query: str,
        *,
        show_hidden: bool,
        search_target: FileSearchTarget = "all",
        include_extensions: tuple[str, ...] = (),
        exclude_extensions: tuple[str, ...] = (),
        max_results: int | None = None,
        is_cancelled: Callable[[], bool] | None = None,
        on_results: FileSearchProgressCallback | None = None,
    ) -> tuple[FileSearchResultState, ...]:
        key_parts = [root_path, query, show_hidden]
        if search_target != "all":
            key_parts.append(search_target)
        if include_extensions or exclude_extensions:
            key_parts.extend((include_extensions, exclude_extensions))
        key = tuple(key_parts)
        self.executed_requests.append(key)
        if is_cancelled is not None and is_cancelled():
            return ()
        if key in self.invalid_query_messages:
            raise InvalidFileSearchQueryError(self.invalid_query_messages[key])
        if key in self.failure_messages:
            raise OSError(self.failure_messages[key])

        results = self.results_by_query.get(key, ())

        # max_results が指定されている場合のみ制限を適用
        if max_results is not None:
            if max_results <= 0:
                return ()
            if len(results) > max_results:
                if on_results is not None:
                    on_results(tuple(results[:max_results]), True)
                limited_results = tuple(
                    sorted(results, key=lambda r: natural_sort_key(r.display_path))[:max_results]
                )
                return limited_results

        if on_results is not None and results:
            on_results(results, False)
        return results
