"""Snapshot loading services for three-pane browser state."""

import threading
from collections import OrderedDict
from dataclasses import dataclass, field, replace
from pathlib import Path
from time import sleep
from typing import Literal, Mapping, Protocol

from peneo.adapters import DirectoryReader, LocalFilesystemAdapter
from peneo.archive_utils import is_supported_archive_path
from peneo.services import ArchiveListService, LiveArchiveListService
from peneo.state.models import (
    AppState,
    BrowserSnapshot,
    DirectoryEntryState,
    GrepSearchResultState,
    PaneState,
    build_initial_app_state,
    resolve_parent_directory_path,
)

DEFAULT_DIRECTORY_CACHE_CAPACITY = 64
TEXT_PREVIEW_MAX_BYTES = 64 * 1024
TEXT_PREVIEW_EXTENSIONS = frozenset(
    {
        ".adoc",
        ".ada",
        ".adb",
        ".ads",
        ".asm",
        ".avsc",
        ".bat",
        ".bib",
        ".c",
        ".capnp",
        ".cbl",
        ".cc",
        ".cfg",
        ".cljs",
        ".clj",
        ".cmd",
        ".cob",
        ".conf",
        ".config",
        ".containerfile",
        ".compose",
        ".cpp",
        ".cr",
        ".cql",
        ".css",
        ".css.map",
        ".csv",
        ".cypher",
        ".d",
        ".dart",
        ".diff",
        ".dockerfile",
        ".edn",
        ".elm",
        ".erl",
        ".ex",
        ".exs",
        ".f",
        ".f90",
        ".fish",
        ".geojson",
        ".go",
        ".gql",
        ".gradle",
        ".groovy",
        ".h",
        ".har",
        ".hcl",
        ".hrl",
        ".hpp",
        ".html",
        ".htmx",
        ".ics",
        ".ini",
        ".java",
        ".js.map",
        ".js",
        ".jl",
        ".json",
        ".jsonl",
        ".jsx",
        ".jsx.map",
        ".hs",
        ".ksh",
        ".kt",
        ".kts",
        ".kube",
        ".latex",
        ".less",
        ".log",
        ".lua",
        ".m",
        ".md",
        ".mjs.map",
        ".make",
        ".mk",
        ".ml",
        ".mli",
        ".mm",
        ".mysql",
        ".ndjson",
        ".nim",
        ".nomad",
        ".opts",
        ".org",
        ".pas",
        ".pcss",
        ".postcss",
        ".pp",
        ".prop",
        ".properties",
        ".proto",
        ".ps1",
        ".psql",
        ".psv",
        ".py",
        ".patch",
        ".rej",
        ".rb",
        ".ron",
        ".rst",
        ".rs",
        ".s",
        ".sass",
        ".scala",
        ".scss",
        ".sh",
        ".srt",
        ".sv",
        ".svh",
        ".swift",
        ".svelte",
        ".sql",
        ".tcl",
        ".tex",
        ".text",
        ".tf",
        ".tfvars",
        ".thrift",
        ".toml",
        ".topojson",
        ".ts",
        ".ts.map",
        ".tsx",
        ".tsx.map",
        ".tsv",
        ".txt",
        ".v",
        ".vh",
        ".vue",
        ".vtt",
        ".wxml",
        ".wxss",
        ".xml",
        ".yaml",
        ".yml",
        ".zig",
        ".zsh",
    }
)
TEXT_PREVIEW_FILENAMES = frozenset(
    {
        ".babelrc",
        ".editorconfig",
        ".env",
        ".eslintrc",
        ".gitattributes",
        ".gitignore",
        ".gitmodules",
        ".npmrc",
        ".prettierrc",
        ".stylelintrc",
        ".yarnrc",
        "containerfile",
        "dockerfile",
    }
)
PREVIEW_PERMISSION_DENIED_MESSAGE = "Preview unavailable: permission denied"
PREVIEW_UNSUPPORTED_MESSAGE = "Preview unavailable for this file type"
PREVIEW_ERROR_MESSAGE = "Preview unavailable"
GREP_PREVIEW_ERROR_MESSAGE = "Preview unavailable: failed to load context"


class BrowserSnapshotLoader(Protocol):
    """Boundary for loading pane snapshots outside the reducer."""

    def load_browser_snapshot(
        self,
        path: str,
        cursor_path: str | None = None,
    ) -> BrowserSnapshot: ...

    def load_child_pane_snapshot(
        self,
        current_path: str,
        cursor_path: str | None,
    ) -> PaneState: ...

    def load_grep_preview(
        self,
        current_path: str,
        result: GrepSearchResultState,
        *,
        context_lines: int = 3,
    ) -> PaneState: ...

    def invalidate_directory_listing_cache(
        self,
        paths: tuple[str, ...] = (),
    ) -> None: ...


@dataclass(frozen=True)
class LiveBrowserSnapshotLoader:
    """Load three-pane snapshots from the local filesystem."""

    filesystem: DirectoryReader = field(default_factory=LocalFilesystemAdapter)
    archive_list: ArchiveListService = field(default_factory=LiveArchiveListService)
    directory_cache_capacity: int = DEFAULT_DIRECTORY_CACHE_CAPACITY
    _directory_entries_cache: OrderedDict[str, tuple[DirectoryEntryState, ...]] = field(
        default_factory=OrderedDict,
        init=False,
        repr=False,
        compare=False,
    )
    _directory_entries_cache_lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
        compare=False,
    )

    def load_browser_snapshot(
        self,
        path: str,
        cursor_path: str | None = None,
    ) -> BrowserSnapshot:
        resolved_path, parent_path = resolve_parent_directory_path(path)
        current_entries = self._list_directory(resolved_path)
        resolved_cursor_path = _resolve_cursor_path(current_entries, cursor_path)

        if parent_path is None:
            parent_directory_path = resolved_path
            parent_entries = ()
            parent_cursor_path = None
        else:
            parent_directory_path = parent_path
            parent_entries = self._list_directory(parent_path)
            parent_cursor_path = (
                resolved_path if _contains_path(parent_entries, resolved_path) else None
            )

        return BrowserSnapshot(
            current_path=resolved_path,
            parent_pane=PaneState(
                directory_path=parent_directory_path,
                entries=parent_entries,
                cursor_path=parent_cursor_path,
            ),
            current_pane=PaneState(
                directory_path=resolved_path,
                entries=current_entries,
                cursor_path=resolved_cursor_path,
            ),
            child_pane=self.load_child_pane_snapshot(resolved_path, resolved_cursor_path),
        )

    def load_child_pane_snapshot(
        self,
        current_path: str,
        cursor_path: str | None,
    ) -> PaneState:
        if cursor_path is None:
            return PaneState(directory_path=current_path, entries=())

        child_path = Path(cursor_path).expanduser().resolve()
        if child_path.is_dir():
            child_entries = self._list_directory(str(child_path))
            return PaneState(directory_path=str(child_path), entries=child_entries)

        if is_supported_archive_path(child_path):
            try:
                child_entries = self.archive_list.list_archive_entries(str(child_path))
                return PaneState(directory_path=str(child_path), entries=child_entries)
            except OSError:
                return PaneState(directory_path=current_path, entries=())

        preview = _load_text_preview(child_path)
        if preview.kind != "unavailable":
            return PaneState(
                directory_path=current_path,
                entries=(),
                mode="preview",
                preview_path=str(child_path),
                preview_content=preview.content,
                preview_message=preview.message,
                preview_truncated=preview.truncated,
            )

        return PaneState(directory_path=current_path, entries=())

    def load_grep_preview(
        self,
        current_path: str,
        result: GrepSearchResultState,
        *,
        context_lines: int = 3,
    ) -> PaneState:
        child_path = Path(result.path).expanduser().resolve()
        preview = _load_grep_context_preview(child_path, result.line_number, context_lines)
        return PaneState(
            directory_path=current_path,
            entries=(),
            mode="preview",
            preview_path=str(child_path),
            preview_title=_format_grep_preview_title(result),
            preview_content=preview.content,
            preview_message=preview.message,
            preview_start_line=preview.start_line,
            preview_highlight_line=preview.highlight_line,
        )

    def invalidate_directory_listing_cache(
        self,
        paths: tuple[str, ...] = (),
    ) -> None:
        normalized_paths = tuple(
            dict.fromkeys(_normalize_directory_cache_path(path) for path in paths)
        )
        with self._directory_entries_cache_lock:
            if not normalized_paths:
                self._directory_entries_cache.clear()
                return
            for path in normalized_paths:
                self._directory_entries_cache.pop(path, None)

    def _list_directory(self, path: str):
        resolved_path = _normalize_directory_cache_path(path)
        cached_entries = self._get_cached_directory_entries(resolved_path)
        if cached_entries is not None:
            return cached_entries
        entries = self._read_directory(resolved_path)
        self._store_cached_directory_entries(resolved_path, entries)
        return entries

    def _get_cached_directory_entries(
        self,
        path: str,
    ) -> tuple[DirectoryEntryState, ...] | None:
        with self._directory_entries_cache_lock:
            entries = self._directory_entries_cache.get(path)
            if entries is None:
                return None
            self._directory_entries_cache.move_to_end(path)
            return entries

    def _store_cached_directory_entries(
        self,
        path: str,
        entries: tuple[DirectoryEntryState, ...],
    ) -> None:
        if self.directory_cache_capacity <= 0:
            return
        with self._directory_entries_cache_lock:
            self._directory_entries_cache[path] = entries
            self._directory_entries_cache.move_to_end(path)
            while len(self._directory_entries_cache) > self.directory_cache_capacity:
                self._directory_entries_cache.popitem(last=False)

    def _read_directory(self, path: str):
        try:
            return self.filesystem.list_directory(path)
        except PermissionError as error:
            raise OSError(f"Permission denied: {path}") from error
        except FileNotFoundError as error:
            raise OSError(f"Not found: {path}") from error
        except NotADirectoryError as error:
            raise OSError(f"Not a directory: {path}") from error
        except OSError as error:
            raise OSError(str(error) or f"Failed to load directory: {path}") from error


@dataclass(frozen=True)
class FakeBrowserSnapshotLoader:
    """Deterministic loader used by tests."""

    snapshots: Mapping[str, BrowserSnapshot] = field(default_factory=dict)
    child_panes: Mapping[tuple[str, str | None], PaneState] = field(default_factory=dict)
    grep_previews: Mapping[tuple[str, str, int], PaneState] = field(default_factory=dict)
    failure_messages: Mapping[str, str] = field(default_factory=dict)
    child_failure_messages: Mapping[tuple[str, str | None], str] = field(default_factory=dict)
    default_delay_seconds: float = 0.0
    per_path_delay_seconds: Mapping[str, float] = field(default_factory=dict)
    child_delay_seconds: Mapping[tuple[str, str | None], float] = field(default_factory=dict)
    archive_list: ArchiveListService = field(default_factory=LiveArchiveListService)
    executed_child_pane_requests: list[tuple[str, str | None]] = field(default_factory=list)
    executed_grep_preview_requests: list[tuple[str, str, int]] = field(default_factory=list)
    invalidated_directory_listing_paths: list[tuple[str, ...]] = field(default_factory=list)

    def load_browser_snapshot(
        self,
        path: str,
        cursor_path: str | None = None,
    ) -> BrowserSnapshot:
        delay = self.per_path_delay_seconds.get(path, self.default_delay_seconds)
        if delay > 0:
            sleep(delay)

        if path in self.failure_messages:
            raise OSError(self.failure_messages[path])

        snapshot = self.snapshots.get(path)
        if snapshot is not None:
            return self._resolve_snapshot(snapshot, cursor_path)

        return _build_fallback_snapshot(path, cursor_path)

    def load_child_pane_snapshot(
        self,
        current_path: str,
        cursor_path: str | None,
    ) -> PaneState:
        key = (current_path, cursor_path)
        self.executed_child_pane_requests.append(key)
        delay = self.child_delay_seconds.get(key, self.default_delay_seconds)
        if delay > 0:
            sleep(delay)

        if key in self.child_failure_messages:
            raise OSError(self.child_failure_messages[key])

        pane = self.child_panes.get(key)
        if pane is not None:
            return pane

        return PaneState(directory_path=current_path, entries=())

    def load_grep_preview(
        self,
        current_path: str,
        result: GrepSearchResultState,
        *,
        context_lines: int = 3,
    ) -> PaneState:
        key = (current_path, result.path, result.line_number)
        self.executed_grep_preview_requests.append(key)
        delay = self.child_delay_seconds.get(
            (current_path, result.path),
            self.default_delay_seconds,
        )
        if delay > 0:
            sleep(delay)

        pane = self.grep_previews.get(key)
        if pane is not None:
            return pane

        return PaneState(directory_path=current_path, entries=())

    def invalidate_directory_listing_cache(
        self,
        paths: tuple[str, ...] = (),
    ) -> None:
        normalized_paths = tuple(
            dict.fromkeys(_normalize_directory_cache_path(path) for path in paths)
        )
        self.invalidated_directory_listing_paths.append(normalized_paths)

    def _resolve_snapshot(
        self,
        snapshot: BrowserSnapshot,
        cursor_path: str | None,
    ) -> BrowserSnapshot:
        if cursor_path is None or not _contains_path(snapshot.current_pane.entries, cursor_path):
            return snapshot

        current_pane = replace(snapshot.current_pane, cursor_path=cursor_path)
        child_pane = snapshot.child_pane
        if (snapshot.current_path, cursor_path) in self.child_panes:
            child_pane = self.child_panes[(snapshot.current_path, cursor_path)]
        elif child_pane.directory_path != cursor_path:
            cursor_entry = next(
                entry for entry in snapshot.current_pane.entries if entry.path == cursor_path
            )
            if cursor_entry.kind == "dir":
                child_pane = PaneState(directory_path=cursor_path, entries=())
            else:
                child_pane = PaneState(directory_path=snapshot.current_path, entries=())

        return replace(snapshot, current_pane=current_pane, child_pane=child_pane)


def snapshot_from_app_state(state: AppState) -> BrowserSnapshot:
    """Convert reducer state into a loader response payload."""

    return BrowserSnapshot(
        current_path=state.current_path,
        parent_pane=state.parent_pane,
        current_pane=state.current_pane,
        child_pane=state.child_pane,
    )


def _build_fallback_snapshot(path: str, cursor_path: str | None) -> BrowserSnapshot:
    initial_state = build_initial_app_state()
    if path == initial_state.current_path:
        state = initial_state
        if cursor_path and _contains_path(state.current_pane.entries, cursor_path):
            state = replace(
                state,
                current_pane=replace(state.current_pane, cursor_path=cursor_path),
            )
        return snapshot_from_app_state(state)

    resolved_path, parent_path = resolve_parent_directory_path(path)
    return BrowserSnapshot(
        current_path=resolved_path,
        parent_pane=PaneState(directory_path=parent_path or resolved_path, entries=()),
        current_pane=PaneState(directory_path=resolved_path, entries=(), cursor_path=cursor_path),
        child_pane=PaneState(directory_path=resolved_path, entries=()),
    )


def _resolve_cursor_path(entries, cursor_path: str | None) -> str | None:
    if cursor_path and _contains_path(entries, cursor_path):
        return cursor_path
    if not entries:
        return None
    return entries[0].path


def _contains_path(entries, path: str) -> bool:
    return any(entry.path == path for entry in entries)


def _normalize_directory_cache_path(path: str) -> str:
    return str(Path(path).expanduser().resolve())


def _load_text_preview(path: Path) -> "FilePreviewState":
    if not _is_preview_candidate(path):
        return FilePreviewState.unsupported()

    try:
        with path.open("rb") as handle:
            chunk = handle.read(TEXT_PREVIEW_MAX_BYTES + 1)
    except PermissionError:
        return FilePreviewState.permission_denied()
    except OSError:
        return FilePreviewState.error()

    if b"\x00" in chunk[:TEXT_PREVIEW_MAX_BYTES]:
        return FilePreviewState.unsupported()

    truncated = len(chunk) > TEXT_PREVIEW_MAX_BYTES
    preview_bytes = chunk[:TEXT_PREVIEW_MAX_BYTES]
    try:
        preview_text = preview_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return FilePreviewState.unsupported()

    return FilePreviewState.with_content(preview_text, truncated)


def _load_grep_context_preview(
    path: Path,
    line_number: int,
    context_lines: int,
) -> "ContextPreviewState":
    if not _is_preview_candidate(path):
        return ContextPreviewState.with_message(PREVIEW_UNSUPPORTED_MESSAGE)

    try:
        with path.open("rb") as handle:
            sample = handle.read(TEXT_PREVIEW_MAX_BYTES + 1)
    except PermissionError:
        return ContextPreviewState.with_message(PREVIEW_PERMISSION_DENIED_MESSAGE)
    except OSError:
        return ContextPreviewState.with_message(GREP_PREVIEW_ERROR_MESSAGE)

    if b"\x00" in sample[:TEXT_PREVIEW_MAX_BYTES]:
        return ContextPreviewState.with_message(PREVIEW_UNSUPPORTED_MESSAGE)

    try:
        sample.decode("utf-8")
    except UnicodeDecodeError:
        return ContextPreviewState.with_message(PREVIEW_UNSUPPORTED_MESSAGE)

    start_line = max(1, line_number - max(0, context_lines))
    end_line = line_number + max(0, context_lines)
    lines: list[str] = []
    last_line = 0
    try:
        with path.open("r", encoding="utf-8") as handle:
            for current_line, line in enumerate(handle, start=1):
                if current_line < start_line:
                    continue
                if current_line > end_line:
                    break
                lines.append(line)
                last_line = current_line
    except PermissionError:
        return ContextPreviewState.with_message(PREVIEW_PERMISSION_DENIED_MESSAGE)
    except (OSError, UnicodeDecodeError):
        return ContextPreviewState.with_message(GREP_PREVIEW_ERROR_MESSAGE)

    if not lines or last_line < line_number:
        return ContextPreviewState.with_message(GREP_PREVIEW_ERROR_MESSAGE)

    return ContextPreviewState.with_content(
        "".join(lines),
        start_line=start_line,
        highlight_line=line_number,
    )


@dataclass(frozen=True)
class FilePreviewState:
    kind: Literal["content", "message", "unavailable"]
    content: str | None = None
    message: str | None = None
    truncated: bool = False

    @classmethod
    def with_content(cls, content: str, truncated: bool) -> "FilePreviewState":
        return cls(kind="content", content=content, truncated=truncated)

    @classmethod
    def permission_denied(cls) -> "FilePreviewState":
        return cls(kind="message", message=PREVIEW_PERMISSION_DENIED_MESSAGE)

    @classmethod
    def unsupported(cls) -> "FilePreviewState":
        return cls(kind="message", message=PREVIEW_UNSUPPORTED_MESSAGE)

    @classmethod
    def error(cls) -> "FilePreviewState":
        return cls(kind="message", message=PREVIEW_ERROR_MESSAGE)


@dataclass(frozen=True)
class ContextPreviewState:
    content: str | None = None
    message: str | None = None
    start_line: int | None = None
    highlight_line: int | None = None

    @classmethod
    def with_content(
        cls,
        content: str,
        *,
        start_line: int,
        highlight_line: int,
    ) -> "ContextPreviewState":
        return cls(
            content=content,
            start_line=start_line,
            highlight_line=highlight_line,
        )

    @classmethod
    def with_message(cls, message: str) -> "ContextPreviewState":
        return cls(message=message)


def _format_grep_preview_title(result: GrepSearchResultState) -> str:
    return f"Preview: {result.display_path}:{result.line_number}"


def _is_preview_candidate(path: Path) -> bool:
    if path.name.casefold() in TEXT_PREVIEW_FILENAMES:
        return True
    suffix = path.suffix.casefold()
    if suffix in TEXT_PREVIEW_EXTENSIONS:
        return True
    return suffix == ""
