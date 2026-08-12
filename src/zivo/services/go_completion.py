"""Low-latency directory completion for the unified Go palette."""

from __future__ import annotations

import ntpath
import os
import threading
import time
from bisect import bisect_left
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from zivo.state.natural_sort import natural_sort_key
from zivo.windows_paths import (
    expand_windows_path,
    is_windows_drives_root,
    is_windows_path,
    list_windows_drive_paths,
    normalize_windows_path,
    split_windows_completion_query,
)

GO_COMPLETION_MAX_RESULTS = 500
GO_COMPLETION_CACHE_TTL_SECONDS = 0.5


@dataclass(frozen=True)
class GoPathCompletionResult:
    """Directory candidates and whether the result was capped."""

    paths: tuple[str, ...] = ()
    truncated: bool = False
    error_message: str | None = None


@dataclass(frozen=True)
class _CachedDirectoryListing:
    expires_at: float
    entries: tuple[tuple[str, bool], ...]
    names: tuple[str, ...]


class GoPathCompletionService:
    """Cache parent listings and filter them without blocking the reducer."""

    def __init__(
        self,
        *,
        cache_ttl_seconds: float = GO_COMPLETION_CACHE_TTL_SECONDS,
        max_results: int = GO_COMPLETION_MAX_RESULTS,
    ) -> None:
        self.cache_ttl_seconds = cache_ttl_seconds
        self.max_results = max_results
        self._cache: dict[str, _CachedDirectoryListing] = {}
        self._lock = threading.Lock()

    def complete(
        self,
        query: str,
        base_path: str,
        *,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> GoPathCompletionResult:
        """Return matching directories, cooperatively checking cancellation."""

        raw_query = query.strip()
        if not raw_query:
            return GoPathCompletionResult()
        is_cancelled = is_cancelled or (lambda: False)
        if is_cancelled():
            return GoPathCompletionResult()

        windows_mode = _uses_windows_path_rules(base_path, raw_query)
        if windows_mode:
            shortcut = split_windows_completion_query(raw_query)
            if shortcut is not None:
                _, prefix = shortcut
                return self._drive_candidates(prefix)
            resolved = expand_windows_path(raw_query, base_path)
            if resolved is None:
                return GoPathCompletionResult()
            trailing = raw_query.endswith(("\\", "/"))
            parent = resolved if trailing else ntpath.dirname(resolved)
            prefix = "" if trailing else ntpath.basename(resolved).casefold()
            if is_windows_drives_root(parent):
                return self._drive_candidates(prefix)
            return self._filter_listing(parent, prefix, windows=True, is_cancelled=is_cancelled)

        resolved = _resolve_posix_path(raw_query, base_path)
        if resolved is None:
            return GoPathCompletionResult()
        trailing = raw_query.endswith(os.sep)
        if os.altsep is not None and raw_query.endswith(os.altsep):
            trailing = True
        parent = str(resolved if trailing else resolved.parent)
        prefix = "" if trailing else resolved.name.casefold()
        return self._filter_listing(parent, prefix, windows=False, is_cancelled=is_cancelled)

    def invalidate(self, paths: tuple[str, ...] = ()) -> None:
        """Invalidate cached listings whose directory is affected by a change."""

        with self._lock:
            if not paths:
                self._cache.clear()
                return
            invalidated = {_cache_key(path) for path in paths}
            self._cache = {
                key: value for key, value in self._cache.items() if key not in invalidated
            }

    def _drive_candidates(self, prefix: str) -> GoPathCompletionResult:
        matches = tuple(
            drive
            for drive in list_windows_drive_paths()
            if not prefix or drive[0].casefold().startswith(prefix.casefold())
        )
        return GoPathCompletionResult(tuple(sorted(matches, key=natural_sort_key)))

    def _filter_listing(
        self,
        parent: str,
        prefix: str,
        *,
        windows: bool,
        is_cancelled: Callable[[], bool],
    ) -> GoPathCompletionResult:
        if is_cancelled():
            return GoPathCompletionResult()
        try:
            listing = self._listing(parent, windows=windows)
        except (OSError, PermissionError) as error:
            return GoPathCompletionResult(
                error_message=f"Unable to read directory: {error.strerror or error}"
            )
        entries = listing.entries
        if prefix:
            start = bisect_left(listing.names, prefix.casefold())
            end = bisect_left(listing.names, f"{prefix.casefold()}\uffff")
            entries = entries[start:end]
        matches: list[str] = []
        for name, is_dir in entries:
            if is_cancelled():
                return GoPathCompletionResult()
            if not is_dir or (prefix and not name.casefold().startswith(prefix)):
                continue
            path = ntpath.join(parent, name) if windows else os.path.join(parent, name)
            matches.append(normalize_windows_path(path))
        matches.sort(
            key=lambda path: (
                natural_sort_key(ntpath.basename(path) if windows else Path(path).name),
                path.casefold() if windows else path,
            )
        )
        truncated = len(matches) > self.max_results
        return GoPathCompletionResult(tuple(matches[: self.max_results]), truncated)

    def _listing(self, parent: str, *, windows: bool) -> _CachedDirectoryListing:
        key = _cache_key(parent, windows=windows)
        now = time.monotonic()
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None and cached.expires_at > now:
                return cached
        if not os.path.isdir(parent):
            return _CachedDirectoryListing(expires_at=now, entries=(), names=())
        entries: list[tuple[str, bool]] = []
        with os.scandir(parent) as iterator:
            for child in iterator:
                try:
                    entries.append((child.name, child.is_dir(follow_symlinks=True)))
                except OSError:
                    continue
        result = tuple(sorted(entries, key=lambda item: item[0].casefold()))
        cached_result = _CachedDirectoryListing(
            expires_at=now + self.cache_ttl_seconds,
            entries=result,
            names=tuple(name.casefold() for name, _is_dir in result),
        )
        with self._lock:
            self._cache[key] = cached_result
        return cached_result


def _resolve_posix_path(query: str, base_path: str) -> Path | None:
    candidate = Path(os.path.expanduser(query))
    if not candidate.is_absolute():
        candidate = Path(base_path) / candidate
    try:
        return candidate.resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        return None


def _cache_key(path: str, *, windows: bool = False) -> str:
    if windows:
        return normalize_windows_path(path).casefold()
    return os.path.normcase(os.path.abspath(path))


def _uses_windows_path_rules(base_path: str, query: str) -> bool:
    if is_windows_path(base_path) or is_windows_drives_root(base_path):
        return True
    normalized_query = query.strip().replace("/", "\\")
    if not normalized_query or query.strip().startswith("/"):
        return False
    if normalized_query.startswith("\\"):
        return True
    return bool(ntpath.splitdrive(normalized_query)[0])
