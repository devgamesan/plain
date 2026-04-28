"""Recursive grep-search services for the command palette."""

import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from zivo.state.models import GrepSearchResultState

_REGEX_QUERY_PREFIX = "re:"


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
        is_cancelled: Callable[[], bool] | None = None,
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
        is_cancelled: Callable[[], bool] | None = None,
    ) -> tuple[GrepSearchResultState, ...]:
        stripped_query = query.strip()
        if not stripped_query:
            return ()

        root = Path(root_path).expanduser().resolve()
        if not root.exists():
            raise OSError(f"Not found: {root}")
        if not root.is_dir():
            raise OSError(f"Not a directory: {root}")

        command = self._build_command(
            stripped_query,
            show_hidden=show_hidden,
            include_globs=include_globs,
            exclude_globs=exclude_globs,
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
            stdout_lines: list[str] = []
            assert process.stdout is not None
            for line in process.stdout:
                if is_cancelled is not None and is_cancelled():
                    process.kill()
                    process.wait()
                    return ()
                stdout_lines.append(line)
            stderr_text = ""
            if process.stderr is not None:
                stderr_text = process.stderr.read()
            return_code = process.wait()
        finally:
            if process.stdout is not None:
                process.stdout.close()
            if process.stderr is not None:
                process.stderr.close()

        if return_code not in {0, 1}:
            message = stderr_text.strip() or "grep search failed"
            if self._is_nonfatal_ripgrep_error(return_code, stderr_text, stripped_query):
                return tuple(
                    sorted(
                        self._parse_results(root, stdout_lines),
                        key=lambda result: (result.display_path.casefold(), result.line_number),
                    )
                )
            if is_regex_grep_search_query(stripped_query):
                raise InvalidGrepSearchQueryError(message)
            raise OSError(message)

        results = self._parse_results(root, stdout_lines)
        return tuple(
            sorted(
                results,
                key=lambda result: (result.display_path.casefold(), result.line_number),
            )
        )

    def _build_command(
        self,
        query: str,
        *,
        show_hidden: bool,
        include_globs: tuple[str, ...] = (),
        exclude_globs: tuple[str, ...] = (),
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
        if is_regex_grep_search_query(query):
            command.extend(["-e", query.strip()[len(_REGEX_QUERY_PREFIX) :]])
        else:
            command.extend(["--fixed-strings", "--ignore-case", "-e", query])
        command.append(".")
        return command

    def _parse_results(
        self,
        root: Path,
        stdout_lines: list[str],
    ) -> list[GrepSearchResultState]:
        results: list[GrepSearchResultState] = []
        for line in stdout_lines:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if payload.get("type") != "match":
                continue
            data = payload.get("data", {})
            path_text = data.get("path", {}).get("text")
            raw_line = data.get("lines", {}).get("text", "")
            line_number = data.get("line_number")
            if not isinstance(path_text, str) or not isinstance(raw_line, str):
                continue
            if not isinstance(line_number, int):
                continue
            absolute_path = Path(path_text)
            if not absolute_path.is_absolute():
                absolute_path = (root / path_text).resolve()
            results.append(
                GrepSearchResultState(
                    path=str(absolute_path),
                    display_path=self._relative_display_path(root, absolute_path),
                    line_number=line_number,
                    line_text=raw_line.rstrip("\r\n"),
                )
            )
        return results

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

    def search(
        self,
        root_path: str,
        query: str,
        *,
        show_hidden: bool,
        include_globs: tuple[str, ...] = (),
        exclude_globs: tuple[str, ...] = (),
        is_cancelled: Callable[[], bool] | None = None,
    ) -> tuple[GrepSearchResultState, ...]:
        key = (root_path, query, include_globs, exclude_globs, show_hidden)
        self.executed_requests.append(key)
        if is_cancelled is not None and is_cancelled():
            return ()
        if key in self.invalid_query_messages:
            raise InvalidGrepSearchQueryError(self.invalid_query_messages[key])
        if key in self.failure_messages:
            raise OSError(self.failure_messages[key])
        return self.results_by_query.get(key, ())
