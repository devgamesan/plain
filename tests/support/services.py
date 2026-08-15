"""Blocking and recording services used by asynchronous app tests."""

import threading
import time

from zivo.models import AppConfig
from zivo.state import FileSearchResultState, GrepSearchResultState


class FakeConfigSaveService:
    """Record config saves and optionally fail them."""

    def __init__(
        self, *, saved_path: str | None = None, failure_message: str | None = None
    ) -> None:
        self.saved_path = saved_path
        self.failure_message = failure_message
        self.saved_requests: list[tuple[str, AppConfig]] = []

    def save(
        self, *, path: str, config: AppConfig, preserve_unmanaged: bool = False
    ) -> str:
        self.saved_requests.append((path, config))
        if self.failure_message is not None:
            raise OSError(self.failure_message)
        return self.saved_path or path


class BlockingFileSearchService:
    """Record file-search requests and block selected queries until released."""

    def __init__(
        self,
        *,
        results_by_query: (
            dict[tuple[str, str, bool], tuple[FileSearchResultState, ...]] | None
        ) = None,
        blocked_queries: tuple[str, ...] = (),
    ) -> None:
        self.results_by_query = results_by_query or {}
        self.blocked_queries = set(blocked_queries)
        self.executed_requests: list[tuple[str, str, bool]] = []
        self.cancelled_queries: list[str] = []
        self.started_queries: list[str] = []
        self.release_event = threading.Event()

    def search(
        self,
        root_path: str,
        query: str,
        *,
        show_hidden: bool,
        search_target: str = "all",
        include_extensions: tuple[str, ...] = (),
        exclude_extensions: tuple[str, ...] = (),
        max_results: int | None = None,
        is_cancelled=None,
    ) -> tuple[FileSearchResultState, ...]:
        key = (root_path, query, show_hidden)
        self.executed_requests.append(key)
        self.started_queries.append(query)
        if query in self.blocked_queries:
            while not self.release_event.is_set():
                if is_cancelled is not None and is_cancelled():
                    self.cancelled_queries.append(query)
                    return ()
                time.sleep(0.01)
        if is_cancelled is not None and is_cancelled():
            self.cancelled_queries.append(query)
            return ()
        return self.results_by_query.get(key, ())


class BlockingGrepSearchService:
    """Record grep requests and block selected queries until released."""

    def __init__(
        self,
        *,
        results_by_query: (
            dict[
                tuple[str, str, tuple[str, ...], tuple[str, ...], bool],
                tuple[GrepSearchResultState, ...],
            ]
            | None
        ) = None,
        blocked_queries: tuple[str, ...] = (),
    ) -> None:
        self.results_by_query = results_by_query or {}
        self.blocked_queries = set(blocked_queries)
        self.executed_requests: list[
            tuple[str, str, tuple[str, ...], tuple[str, ...], bool]
        ] = []
        self.executed_search_options: list[tuple[tuple[str, ...], str, int | None]] = []
        self.cancelled_queries: list[str] = []
        self.release_event = threading.Event()

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
        is_cancelled=None,
    ) -> tuple[GrepSearchResultState, ...]:
        key = (root_path, query, include_globs, exclude_globs, show_hidden)
        self.executed_requests.append(key)
        self.executed_search_options.append((target_paths, filename_filter, max_results))
        if query in self.blocked_queries:
            while not self.release_event.is_set():
                if is_cancelled is not None and is_cancelled():
                    self.cancelled_queries.append(query)
                    return ()
                time.sleep(0.01)
        if is_cancelled is not None and is_cancelled():
            self.cancelled_queries.append(query)
            return ()
        return self.results_by_query.get(key, ())


class BlockingDirectorySizeService:
    """Block directory-size requests until ``release`` is called."""

    def __init__(self) -> None:
        self.executed_requests: list[tuple[str, ...]] = []
        self.release_event = threading.Event()

    def calculate_sizes(
        self,
        paths: tuple[str, ...],
        *,
        is_cancelled=None,
    ) -> tuple[tuple[tuple[str, int], ...], tuple[tuple[str, str], ...]]:
        self.executed_requests.append(paths)
        while not self.release_event.wait(0.01):
            if is_cancelled is not None and is_cancelled():
                return (), ()
        return tuple((path, 1_000 * (index + 1)) for index, path in enumerate(paths)), ()

    def release(self) -> None:
        self.release_event.set()


__all__ = [
    "BlockingDirectorySizeService",
    "BlockingFileSearchService",
    "BlockingGrepSearchService",
    "FakeConfigSaveService",
]
