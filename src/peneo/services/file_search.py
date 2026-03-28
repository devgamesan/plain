"""Recursive file-search services for the command palette."""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from peneo.state.models import FileSearchResultState


class FileSearchService(Protocol):
    """Boundary for recursive filename searches."""

    def search(
        self,
        root_path: str,
        query: str,
        *,
        show_hidden: bool,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> tuple[FileSearchResultState, ...]: ...


@dataclass(frozen=True)
class LiveFileSearchService:
    """Search the local filesystem for matching filenames."""

    def search(
        self,
        root_path: str,
        query: str,
        *,
        show_hidden: bool,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> tuple[FileSearchResultState, ...]:
        normalized_query = query.strip().casefold()
        if not normalized_query:
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
                if child.is_dir():
                    stack.append(child)
                    continue
                if normalized_query not in child.name.casefold():
                    continue
                results.append(
                    FileSearchResultState(
                        path=str(child),
                        display_path=str(child.relative_to(root)),
                    )
                )
        results.sort(key=lambda result: result.display_path.casefold())
        return tuple(results)


@dataclass
class FakeFileSearchService:
    """Deterministic file-search service used by tests."""

    results_by_query: dict[tuple[str, str, bool], tuple[FileSearchResultState, ...]] = field(
        default_factory=dict
    )
    failure_messages: dict[tuple[str, str, bool], str] = field(default_factory=dict)
    executed_requests: list[tuple[str, str, bool]] = field(default_factory=list)

    def search(
        self,
        root_path: str,
        query: str,
        *,
        show_hidden: bool,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> tuple[FileSearchResultState, ...]:
        key = (root_path, query, show_hidden)
        self.executed_requests.append(key)
        if is_cancelled is not None and is_cancelled():
            return ()
        if key in self.failure_messages:
            raise OSError(self.failure_messages[key])
        return self.results_by_query.get(key, ())
