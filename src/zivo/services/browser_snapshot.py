"""Snapshot loading services for three-pane browser state."""

from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass, field, replace
from pathlib import Path
from time import sleep
from typing import Mapping, Protocol

from zivo.adapters import DirectoryReader, LocalFilesystemAdapter
from zivo.archive_utils import is_supported_archive_path
from zivo.services import ArchiveListService, LiveArchiveListService
from zivo.services.previews import (
    DEFAULT_IMAGE_PREVIEW_COLUMNS,
    PREVIEW_PERMISSION_DENIED_MESSAGE,
    TEXT_PREVIEW_MAX_BYTES,
    ChafaImagePreviewLoader,
    ContextPreviewState,
    DocumentPreviewLoader,
    FilePreviewState,
    GrepContextCacheKey,
    ImagePreviewLoader,
    PandocDocumentPreviewLoader,
    _build_grep_context_cache_key,
    _build_text_preview_cache_key,
    _load_grep_context_preview,
    _load_text_preview,
)
from zivo.services.previews import (
    PREVIEW_UNSUPPORTED_MESSAGE as _preview_unsupported_message,
)
from zivo.services.previews import (
    preview_max_bytes_from_kib as _preview_max_bytes_from_kib,
)
from zivo.state.models import (
    AppState,
    BrowserSnapshot,
    DirectoryEntryState,
    GrepSearchResultState,
    PaneState,
    build_initial_app_state,
    resolve_parent_directory_path,
)
from zivo.windows_paths import (
    comparable_path,
    is_posix_path,
    is_search_workspace_path,
    is_windows_drive_root,
    is_windows_drives_root,
    is_windows_path,
    list_windows_drive_paths,
    normalize_windows_path,
)

DEFAULT_DIRECTORY_CACHE_CAPACITY = 64
DEFAULT_TEXT_PREVIEW_CACHE_CAPACITY = 128
DEFAULT_GREP_CONTEXT_CACHE_CAPACITY = 128
PREVIEW_UNSUPPORTED_MESSAGE = _preview_unsupported_message
preview_max_bytes_from_kib = _preview_max_bytes_from_kib


class BrowserSnapshotLoader(Protocol):
    """Boundary for loading pane snapshots outside the reducer."""

    def load_browser_snapshot(
        self,
        path: str,
        cursor_path: str | None = None,
        *,
        enable_image_preview: bool = True,
        enable_pdf_preview: bool = True,
        enable_office_preview: bool = True,
    ) -> BrowserSnapshot: ...

    def load_child_pane_snapshot(
        self,
        current_path: str,
        cursor_path: str | None,
        *,
        preview_max_bytes: int = TEXT_PREVIEW_MAX_BYTES,
        enable_text_preview: bool = True,
        enable_image_preview: bool = True,
        enable_pdf_preview: bool = True,
        enable_office_preview: bool = True,
        preview_columns: int = DEFAULT_IMAGE_PREVIEW_COLUMNS,
        image_preview_mode: str = "auto",
    ) -> PaneState: ...

    def load_current_pane_snapshot(
        self,
        path: str,
        cursor_path: str | None,
    ) -> tuple[str, PaneState, PaneState]: ...

    def load_parent_child_panes(
        self,
        path: str,
        cursor_path: str | None,
        current_pane: PaneState,
        *,
        enable_text_preview: bool = True,
        enable_image_preview: bool = True,
        image_preview_mode: str = "auto",
        enable_pdf_preview: bool = True,
        enable_office_preview: bool = True,
    ) -> tuple[PaneState, PaneState]: ...

    def load_grep_preview(
        self,
        current_path: str,
        result: GrepSearchResultState,
        *,
        context_lines: int = 3,
        preview_max_bytes: int = TEXT_PREVIEW_MAX_BYTES,
    ) -> PaneState: ...

    def invalidate_directory_listing_cache(
        self,
        paths: tuple[str, ...] = (),
    ) -> None: ...


@dataclass
class LiveBrowserSnapshotLoader:
    """Load three-pane snapshots from the local filesystem."""

    filesystem: DirectoryReader = field(default_factory=LocalFilesystemAdapter)
    archive_list: ArchiveListService = field(default_factory=LiveArchiveListService)
    directory_cache_capacity: int = DEFAULT_DIRECTORY_CACHE_CAPACITY
    text_preview_cache_capacity: int = DEFAULT_TEXT_PREVIEW_CACHE_CAPACITY
    grep_context_cache_capacity: int = DEFAULT_GREP_CONTEXT_CACHE_CAPACITY
    document_preview_loader: "DocumentPreviewLoader | None" = None
    image_preview_loader: "ImagePreviewLoader | None" = None
    app_state: "AppState | None" = field(default=None, compare=False, repr=False)
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
    _text_preview_cache: OrderedDict[
        tuple[
            str, int, int, int, bool, bool, bool, bool, int, str
        ],
        "FilePreviewState",
    ] = field(
        default_factory=OrderedDict,
        init=False,
        repr=False,
        compare=False,
    )
    _text_preview_cache_lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
        compare=False,
    )
    _grep_context_cache: "OrderedDict[GrepContextCacheKey, ContextPreviewState]" = field(
        default_factory=OrderedDict,
        init=False,
        repr=False,
        compare=False,
    )
    _grep_context_cache_lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
        compare=False,
    )
    _document_preview_loader_lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
        compare=False,
    )
    _image_preview_loader_lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
        compare=False,
    )

    def load_browser_snapshot(
        self,
        path: str,
        cursor_path: str | None = None,
        *,
        show_hidden: bool = False,
        enable_image_preview: bool = True,
        image_preview_mode: str = "auto",
        enable_pdf_preview: bool = True,
        enable_office_preview: bool = True,
    ) -> BrowserSnapshot:
        resolved_path, parent_path = resolve_parent_directory_path(path)
        current_entries = self._list_directory(resolved_path)
        resolved_cursor_path = _resolve_cursor_path(current_entries, cursor_path, show_hidden)

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
            child_pane=self.load_child_pane_snapshot(
                resolved_path,
                resolved_cursor_path,
                enable_image_preview=enable_image_preview,
                image_preview_mode=image_preview_mode,
                enable_pdf_preview=enable_pdf_preview,
                enable_office_preview=enable_office_preview,
            ),
        )

    def load_child_pane_snapshot(
        self,
        current_path: str,
        cursor_path: str | None,
        *,
        preview_max_bytes: int = TEXT_PREVIEW_MAX_BYTES,
        enable_text_preview: bool = True,
        enable_image_preview: bool = True,
        image_preview_mode: str = "auto",
        enable_pdf_preview: bool = True,
        enable_office_preview: bool = True,
        preview_columns: int = DEFAULT_IMAGE_PREVIEW_COLUMNS,
    ) -> PaneState:
        if cursor_path is None:
            return PaneState(directory_path=current_path, entries=())

        if is_windows_drive_root(cursor_path):
            try:
                child_entries = self._list_directory(normalize_windows_path(cursor_path))
                return PaneState(
                    directory_path=normalize_windows_path(cursor_path),
                    entries=child_entries,
                )
            except OSError as error:
                if _is_permission_denied_error(error):
                    return PaneState(
                        directory_path=normalize_windows_path(cursor_path),
                        entries=(),
                        mode="preview",
                        preview_message=PREVIEW_PERMISSION_DENIED_MESSAGE,
                    )
                raise

        child_path = Path(cursor_path).expanduser().resolve()
        if child_path.is_dir():
            try:
                child_entries = self._list_directory(str(child_path))
                return PaneState(directory_path=str(child_path), entries=child_entries)
            except OSError as error:
                if _is_permission_denied_error(error):
                    return PaneState(
                        directory_path=str(child_path),
                        entries=(),
                        mode="preview",
                        preview_message=PREVIEW_PERMISSION_DENIED_MESSAGE,
                    )
                raise

        if is_supported_archive_path(child_path):
            try:
                child_entries = self.archive_list.list_archive_entries(str(child_path))
                return PaneState(directory_path=str(child_path), entries=child_entries)
            except OSError:
                return PaneState(directory_path=current_path, entries=())

        preview = self._load_cached_text_preview(
            child_path,
            preview_max_bytes=preview_max_bytes,
            enable_text_preview=enable_text_preview,
            enable_image_preview=enable_image_preview,
            image_preview_mode=image_preview_mode,
            enable_pdf_preview=enable_pdf_preview,
            enable_office_preview=enable_office_preview,
            preview_columns=preview_columns,
        )
        if preview.kind != "unavailable":
            return PaneState(
                directory_path=current_path,
                entries=(),
                mode="preview",
                preview_path=str(child_path),
                preview_content=preview.content,
                preview_kind=preview.content_kind,
                preview_message=preview.message,
                preview_truncated=preview.truncated,
            )

        return PaneState(directory_path=current_path, entries=())

    def load_current_pane_snapshot(
        self,
        path: str,
        cursor_path: str | None,
        *,
        show_hidden: bool = False,
    ) -> tuple[str, PaneState, PaneState]:
        """Load current pane + minimal parent (Phase 1 of progressive loading).

        Returns:
            (current_path, current_pane, parent_pane)
        """
        resolved_path, parent_path = resolve_parent_directory_path(path)
        current_entries = self._list_directory(resolved_path)
        resolved_cursor_path = _resolve_cursor_path(current_entries, cursor_path, show_hidden)

        if parent_path is None:
            parent_directory_path = resolved_path
            parent_entries = ()
            parent_cursor_path = None
        else:
            parent_directory_path = parent_path
            # Try to load parent from cache for Phase 1
            parent_entries = self._get_cached_directory_entries(parent_path)
            if parent_entries is None:
                # No cache available, use empty parent for now
                parent_entries = ()
            parent_cursor_path = (
                resolved_path if _contains_path(parent_entries, resolved_path) else None
            )

        current_pane = PaneState(
            directory_path=resolved_path,
            entries=current_entries,
            cursor_path=resolved_cursor_path,
        )
        parent_pane = PaneState(
            directory_path=parent_directory_path,
            entries=parent_entries,
            cursor_path=parent_cursor_path,
        )

        return resolved_path, current_pane, parent_pane

    def load_parent_child_panes(
        self,
        path: str,
        cursor_path: str | None,
        current_pane: PaneState,
        *,
        enable_text_preview: bool = True,
        enable_image_preview: bool = True,
        image_preview_mode: str = "auto",
        enable_pdf_preview: bool = True,
        enable_office_preview: bool = True,
    ) -> tuple[PaneState, PaneState]:
        """Load complete parent + child panes (Phase 2 of progressive loading).

        Returns:
            (parent_pane, child_pane)
        """
        resolved_path, parent_path = resolve_parent_directory_path(path)

        # Load complete parent pane
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

        parent_pane = PaneState(
            directory_path=parent_directory_path,
            entries=parent_entries,
            cursor_path=parent_cursor_path,
        )

        # Load child pane using existing method
        resolved_cursor_path = current_pane.cursor_path
        child_pane = self.load_child_pane_snapshot(
            resolved_path,
            resolved_cursor_path,
            enable_text_preview=enable_text_preview,
            enable_image_preview=enable_image_preview,
            image_preview_mode=image_preview_mode,
            enable_pdf_preview=enable_pdf_preview,
            enable_office_preview=enable_office_preview,
        )

        return parent_pane, child_pane

    def load_grep_preview(
        self,
        current_path: str,
        result: GrepSearchResultState,
        *,
        context_lines: int = 3,
        preview_max_bytes: int = TEXT_PREVIEW_MAX_BYTES,
    ) -> PaneState:
        child_path = Path(result.path).expanduser().resolve()

        # Check cache first
        if self.grep_context_cache_capacity > 0:
            cache_key = _build_grep_context_cache_key(
                child_path,
                result.line_number,
                context_lines,
                preview_max_bytes,
            )
            if isinstance(cache_key, ContextPreviewState):
                preview = cache_key
            else:
                cached_preview = self._get_cached_grep_context(cache_key)
                if cached_preview is not None:
                    preview = cached_preview
                else:
                    preview = _load_grep_context_preview(
                        child_path,
                        result.line_number,
                        context_lines,
                        preview_max_bytes=preview_max_bytes,
                    )
                    self._store_cached_grep_context(cache_key, preview)
        else:
            preview = _load_grep_context_preview(
                child_path,
                result.line_number,
                context_lines,
                preview_max_bytes=preview_max_bytes,
            )

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
        # Handle virtual search workspace paths
        if is_search_workspace_path(path):
            return self._read_virtual_search_directory(path)

        if is_windows_drives_root(path):
            return tuple(
                DirectoryEntryState(
                    path=drive,
                    name=drive,
                    kind="dir",
                )
                for drive in list_windows_drive_paths()
            )
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

    def _read_virtual_search_directory(self, virtual_path: str) -> tuple:
        """Read directory entries from a virtual search workspace.

        Args:
            virtual_path: A search:// virtual path

        Returns:
            A tuple of DirectoryEntryState objects from the search workspace cache
        """
        from zivo.windows_paths import file_search_result_to_directory_entry

        # Get search results from workspace cache
        if self.app_state is None:
            return ()

        search_results = self.app_state.search_workspaces.get(virtual_path, ())

        # Convert FileSearchResultState to DirectoryEntryState
        return tuple(file_search_result_to_directory_entry(result) for result in search_results)

    def _load_cached_text_preview(
        self,
        path: Path,
        *,
        preview_max_bytes: int,
        enable_text_preview: bool,
        enable_image_preview: bool,
        image_preview_mode: str = "auto",
        enable_pdf_preview: bool,
        enable_office_preview: bool,
        preview_columns: int,
    ) -> "FilePreviewState":
        if self.text_preview_cache_capacity <= 0 or image_preview_mode == "kitty":
            return _load_text_preview(
                path,
                preview_max_bytes=preview_max_bytes,
                enable_text_preview=enable_text_preview,
                enable_image_preview=enable_image_preview,
                image_preview_mode=image_preview_mode,
                enable_pdf_preview=enable_pdf_preview,
                enable_office_preview=enable_office_preview,
                document_preview_loader=self._resolve_document_preview_loader(),
                image_preview_loader=self._resolve_image_preview_loader(),
                preview_columns=preview_columns,
            )
        cache_key = _build_text_preview_cache_key(
            path,
            preview_max_bytes,
            enable_text_preview,
            enable_image_preview,
            enable_pdf_preview,
            enable_office_preview,
            preview_columns,
            image_preview_mode,
        )
        if isinstance(cache_key, FilePreviewState):
            return cache_key
        cached_preview = self._get_cached_text_preview(cache_key)
        if cached_preview is not None:
            return cached_preview
        preview = _load_text_preview(
            path,
            preview_max_bytes=preview_max_bytes,
            enable_text_preview=enable_text_preview,
            enable_image_preview=enable_image_preview,
            image_preview_mode=image_preview_mode,
            enable_pdf_preview=enable_pdf_preview,
            enable_office_preview=enable_office_preview,
            document_preview_loader=self._resolve_document_preview_loader(),
            image_preview_loader=self._resolve_image_preview_loader(),
            preview_columns=preview_columns,
        )
        self._store_cached_text_preview(cache_key, preview)
        return preview

    def _resolve_document_preview_loader(self) -> "DocumentPreviewLoader":
        with self._document_preview_loader_lock:
            if self.document_preview_loader is None:
                object.__setattr__(
                    self,
                    "document_preview_loader",
                    PandocDocumentPreviewLoader(),
                )
            return self.document_preview_loader

    def _resolve_image_preview_loader(self) -> "ImagePreviewLoader":
        with self._image_preview_loader_lock:
            if self.image_preview_loader is None:
                object.__setattr__(
                    self,
                    "image_preview_loader",
                    ChafaImagePreviewLoader(),
                )
            return self.image_preview_loader

    def _get_cached_text_preview(
        self,
        cache_key: tuple[str, int, int, int, bool, bool, bool, bool, int, str],
    ) -> "FilePreviewState | None":
        with self._text_preview_cache_lock:
            preview = self._text_preview_cache.get(cache_key)
            if preview is None:
                return None
            self._text_preview_cache.move_to_end(cache_key)
            return preview

    def _store_cached_text_preview(
        self,
        cache_key: tuple[str, int, int, int, bool, bool, bool, bool, int, str],
        preview: "FilePreviewState",
    ) -> None:
        with self._text_preview_cache_lock:
            self._text_preview_cache[cache_key] = preview
            self._text_preview_cache.move_to_end(cache_key)
            while len(self._text_preview_cache) > self.text_preview_cache_capacity:
                self._text_preview_cache.popitem(last=False)

    def _get_cached_grep_context(
        self,
        cache_key: GrepContextCacheKey,
    ) -> "ContextPreviewState | None":
        with self._grep_context_cache_lock:
            preview = self._grep_context_cache.get(cache_key)
            if preview is None:
                return None
            self._grep_context_cache.move_to_end(cache_key)
            return preview

    def _store_cached_grep_context(
        self,
        cache_key: GrepContextCacheKey,
        preview: "ContextPreviewState",
    ) -> None:
        with self._grep_context_cache_lock:
            self._grep_context_cache[cache_key] = preview
            self._grep_context_cache.move_to_end(cache_key)
            while len(self._grep_context_cache) > self.grep_context_cache_capacity:
                self._grep_context_cache.popitem(last=False)


def _is_permission_denied_error(error: OSError) -> bool:
    return str(error).startswith("Permission denied:")


@dataclass
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
    app_state: "AppState | None" = field(default=None, compare=False, repr=False)

    def load_browser_snapshot(
        self,
        path: str,
        cursor_path: str | None = None,
        *,
        show_hidden: bool = False,
        enable_image_preview: bool = True,
        enable_pdf_preview: bool = True,
        enable_office_preview: bool = True,
    ) -> BrowserSnapshot:
        delay = self.per_path_delay_seconds.get(path, self.default_delay_seconds)
        if delay > 0:
            sleep(delay)

        if path in self.failure_messages:
            raise OSError(self.failure_messages[path])

        snapshot = self.snapshots.get(path)
        if snapshot is None and is_windows_path(path):
            normalized_path = normalize_windows_path(path)
            snapshot = next(
                (
                    candidate
                    for candidate_path, candidate in self.snapshots.items()
                    if is_windows_path(candidate_path)
                    and normalize_windows_path(candidate_path) == normalized_path
                ),
                None,
            )
        if snapshot is not None:
            return self._resolve_snapshot(snapshot, cursor_path)

        return _build_fallback_snapshot(path, cursor_path)

    def load_child_pane_snapshot(
        self,
        current_path: str,
        cursor_path: str | None,
        *,
        preview_max_bytes: int = TEXT_PREVIEW_MAX_BYTES,
        enable_text_preview: bool = True,
        enable_image_preview: bool = True,
        image_preview_mode: str = "auto",
        enable_pdf_preview: bool = True,
        enable_office_preview: bool = True,
        preview_columns: int = DEFAULT_IMAGE_PREVIEW_COLUMNS,
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

    def load_current_pane_snapshot(
        self,
        path: str,
        cursor_path: str | None,
        *,
        show_hidden: bool = False,
    ) -> tuple[str, PaneState, PaneState]:
        """Load current pane + minimal parent (Phase 1 of progressive loading)."""
        snapshot = self.load_browser_snapshot(path, cursor_path, show_hidden=show_hidden)
        return snapshot.current_path, snapshot.current_pane, snapshot.parent_pane

    def load_parent_child_panes(
        self,
        path: str,
        cursor_path: str | None,
        current_pane: PaneState,
        *,
        enable_text_preview: bool = True,
        enable_image_preview: bool = True,
        image_preview_mode: str = "auto",
        enable_pdf_preview: bool = True,
        enable_office_preview: bool = True,
    ) -> tuple[PaneState, PaneState]:
        """Load complete parent + child panes (Phase 2 of progressive loading)."""
        snapshot = self.load_browser_snapshot(path, cursor_path)
        return snapshot.parent_pane, snapshot.child_pane

    def load_grep_preview(
        self,
        current_path: str,
        result: GrepSearchResultState,
        *,
        context_lines: int = 3,
        preview_max_bytes: int = TEXT_PREVIEW_MAX_BYTES,
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
            dict.fromkeys(
                path if is_windows_drives_root(path) else str(Path(path).expanduser().resolve())
                for path in paths
            )
        )
        self.invalidated_directory_listing_paths.append(normalized_paths)

    def _resolve_snapshot(
        self,
        snapshot: BrowserSnapshot,
        cursor_path: str | None,
    ) -> BrowserSnapshot:
        normalized_snapshot = replace(
            snapshot,
            current_path=comparable_path(snapshot.current_path),
            parent_pane=replace(
                snapshot.parent_pane,
                cursor_path=comparable_path(snapshot.parent_pane.cursor_path),
            ),
            current_pane=replace(
                snapshot.current_pane,
                cursor_path=comparable_path(snapshot.current_pane.cursor_path),
            ),
        )
        matched_cursor_path = self._match_snapshot_cursor_path(snapshot, cursor_path)
        if matched_cursor_path is None:
            return normalized_snapshot

        current_pane = replace(
            normalized_snapshot.current_pane,
            cursor_path=comparable_path(matched_cursor_path),
        )
        child_pane = normalized_snapshot.child_pane
        child_key = self._match_child_pane_key(snapshot.current_path, matched_cursor_path)
        if child_key is not None:
            child_pane = self.child_panes[child_key]
        elif child_pane.directory_path != matched_cursor_path:
            cursor_entry = next(
                entry
                for entry in snapshot.current_pane.entries
                if entry.path == matched_cursor_path
            )
            if cursor_entry.kind == "dir":
                child_pane = PaneState(directory_path=matched_cursor_path, entries=())
            else:
                child_pane = PaneState(directory_path=snapshot.current_path, entries=())

        return replace(
            normalized_snapshot,
            current_pane=current_pane,
            child_pane=child_pane,
        )

    def _match_snapshot_cursor_path(
        self,
        snapshot: BrowserSnapshot,
        cursor_path: str | None,
    ) -> str | None:
        if cursor_path is None:
            return None
        if _contains_path(snapshot.current_pane.entries, cursor_path):
            return cursor_path
        if not is_windows_path(cursor_path):
            return None
        normalized_cursor = normalize_windows_path(cursor_path)
        for entry in snapshot.current_pane.entries:
            if is_windows_path(entry.path) and (
                normalize_windows_path(entry.path) == normalized_cursor
            ):
                return entry.path
        return None

    def _match_child_pane_key(
        self,
        current_path: str,
        cursor_path: str,
    ) -> tuple[str, str | None] | None:
        direct_key = (current_path, cursor_path)
        if direct_key in self.child_panes:
            return direct_key
        if not (is_windows_path(current_path) and is_windows_path(cursor_path)):
            return None
        normalized_current = normalize_windows_path(current_path)
        normalized_cursor = normalize_windows_path(cursor_path)
        for key in self.child_panes:
            key_current, key_cursor = key
            if key_cursor is None:
                continue
            if not (is_windows_path(key_current) and is_windows_path(key_cursor)):
                continue
            if (
                normalize_windows_path(key_current) == normalized_current
                and normalize_windows_path(key_cursor) == normalized_cursor
            ):
                return key
        return None


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


def _resolve_cursor_path(
    entries,
    cursor_path: str | None,
    show_hidden: bool = False,
) -> str | None:
    if cursor_path and _contains_path(entries, cursor_path):
        return cursor_path
    if not entries:
        return None
    if show_hidden:
        return entries[0].path
    for entry in entries:
        if not entry.hidden:
            return entry.path
    return entries[0].path


def _contains_path(entries, path: str) -> bool:
    return any(entry.path == path for entry in entries)


def _normalize_directory_cache_path(path: str) -> str:
    # Handle virtual search workspace paths - return as-is
    if is_search_workspace_path(path):
        return path
    if is_windows_drives_root(path):
        return path
    if is_posix_path(path):
        return path
    if is_windows_path(path):
        return normalize_windows_path(path)
    return str(Path(path).expanduser().resolve())
def _format_grep_preview_title(result: GrepSearchResultState) -> str:
    return f"Preview: {result.display_path}:{result.line_number}"
