"""Preview and apply text replacement across selected files."""

import difflib
import os
import re
import stat
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from zivo.models import (
    OperationCancelCallback,
    OperationProgressCallback,
    TextReplacePreviewEntry,
    TextReplacePreviewResult,
    TextReplaceRequest,
    TextReplaceResult,
    emit_operation_progress,
)

_REGEX_QUERY_PREFIX = "re:"


class TextReplaceService(Protocol):
    """Boundary for previewing and applying text replacement."""

    def preview(self, request: TextReplaceRequest) -> TextReplacePreviewResult: ...

    def apply(
        self,
        request: TextReplaceRequest,
        *,
        progress_callback: OperationProgressCallback | None = None,
        cancel_callback: OperationCancelCallback | None = None,
    ) -> TextReplaceResult: ...


class InvalidTextReplaceQueryError(ValueError):
    """Raised when the search pattern cannot be compiled."""


@dataclass(frozen=True)
class LiveTextReplaceService:
    """Replace plain text or regular expressions in UTF-8 text files."""

    encoding: str = "utf-8"

    def preview(self, request: TextReplaceRequest) -> TextReplacePreviewResult:
        matcher = _compile_pattern(request.find_text)
        result = _preview_replacements(request, matcher, self.encoding)
        return TextReplacePreviewResult(
            request=request,
            changed_entries=result.changed_entries,
            total_match_count=result.total_match_count,
            diff_text=result.diff_text,
            skipped_paths=result.skipped_paths,
        )

    def apply(
        self,
        request: TextReplaceRequest,
        *,
        progress_callback: OperationProgressCallback | None = None,
        cancel_callback: OperationCancelCallback | None = None,
    ) -> TextReplaceResult:
        matcher = _compile_pattern(request.find_text)
        result = _apply_replacements(
            request,
            matcher,
            self.encoding,
            progress_callback=progress_callback,
            cancel_callback=cancel_callback,
        )

        file_count = len(result.changed_paths)
        skipped_count = len(result.skipped_paths)
        message = f"Replaced {result.total_match_count} match(es) in {file_count} file(s)"
        level = "info"
        if skipped_count:
            level = "warning"
            message += f"; skipped {skipped_count} unreadable file(s)"
        message += "; Undo unavailable"
        if result.cancelled:
            level = "warning"
            message = (
                f"Replacement cancelled after {file_count} file(s); "
                f"{len(result.unprocessed_paths)} not processed; Undo unavailable"
            )
        return TextReplaceResult(
            request=request,
            changed_paths=result.changed_paths,
            total_match_count=result.total_match_count,
            message=message,
            level=level,
            skipped_paths=result.skipped_paths,
            cancelled=result.cancelled,
            unprocessed_paths=result.unprocessed_paths,
        )


@dataclass(frozen=True)
class _PreviewReplacementResult:
    changed_entries: tuple[TextReplacePreviewEntry, ...]
    total_match_count: int
    diff_text: str
    skipped_paths: tuple[str, ...]


@dataclass(frozen=True)
class _ApplyReplacementResult:
    changed_paths: tuple[str, ...]
    total_match_count: int
    skipped_paths: tuple[str, ...]
    cancelled: bool = False
    unprocessed_paths: tuple[str, ...] = ()


def _preview_replacements(
    request: TextReplaceRequest,
    matcher: "_PatternMatcher",
    encoding: str,
) -> _PreviewReplacementResult:
    changed_entries: list[TextReplacePreviewEntry] = []
    diff_chunks: list[str] = []
    skipped_paths: list[str] = []
    total_match_count = 0

    for raw_path in request.paths:
        path = Path(raw_path)
        try:
            original = path.read_text(encoding=encoding)
        except (OSError, UnicodeDecodeError):
            skipped_paths.append(str(path))
            continue

        replaced, match_count = matcher.replace(original, request.replace_text)
        if match_count <= 0:
            continue

        preview_entry = _build_preview_entry(path, original, replaced, match_count)
        if preview_entry is None:
            skipped_paths.append(str(path))
            continue

        changed_entries.append(preview_entry)
        diff_chunks.append(preview_entry.diff_text)
        total_match_count += match_count

    changed_entries.sort(key=lambda entry: entry.path.casefold())
    return _PreviewReplacementResult(
        changed_entries=tuple(changed_entries),
        total_match_count=total_match_count,
        diff_text="".join(diff_chunks),
        skipped_paths=tuple(skipped_paths),
    )


def _apply_replacements(
    request: TextReplaceRequest,
    matcher: "_PatternMatcher",
    encoding: str,
    *,
    progress_callback: OperationProgressCallback | None = None,
    cancel_callback: OperationCancelCallback | None = None,
) -> _ApplyReplacementResult:
    changed_paths: list[str] = []
    skipped_paths: list[str] = []
    total_match_count = 0
    processed_count = 0

    for index, raw_path in enumerate(request.paths):
        if cancel_callback is not None and cancel_callback():
            return _ApplyReplacementResult(
                changed_paths=tuple(changed_paths),
                total_match_count=total_match_count,
                skipped_paths=tuple(skipped_paths),
                cancelled=True,
                unprocessed_paths=tuple(request.paths[index:]),
            )
        path = Path(raw_path)
        try:
            original = path.read_text(encoding=encoding)
        except (OSError, UnicodeDecodeError):
            skipped_paths.append(str(path))
            processed_count += 1
            _report_progress(progress_callback, processed_count, len(request.paths), str(path))
            continue

        replaced, match_count = matcher.replace(original, request.replace_text)
        if match_count <= 0:
            processed_count += 1
            _report_progress(progress_callback, processed_count, len(request.paths), str(path))
            continue
        if _find_first_changed_line(original, replaced) is None:
            skipped_paths.append(str(path))
            processed_count += 1
            _report_progress(progress_callback, processed_count, len(request.paths), str(path))
            continue
        _write_text_atomically(path, replaced, encoding)
        changed_paths.append(str(path))
        total_match_count += match_count
        processed_count += 1
        _report_progress(progress_callback, processed_count, len(request.paths), str(path))

    changed_paths.sort(key=str.casefold)
    return _ApplyReplacementResult(
        changed_paths=tuple(changed_paths),
        total_match_count=total_match_count,
        skipped_paths=tuple(skipped_paths),
    )


@dataclass
class FakeTextReplaceService:
    """Deterministic text-replace service used by tests."""

    preview_results: dict[TextReplaceRequest, TextReplacePreviewResult] = field(
        default_factory=dict
    )
    apply_results: dict[TextReplaceRequest, TextReplaceResult] = field(default_factory=dict)
    preview_failures: dict[TextReplaceRequest, str] = field(default_factory=dict)
    apply_failures: dict[TextReplaceRequest, str] = field(default_factory=dict)
    preview_requests: list[TextReplaceRequest] = field(default_factory=list)
    apply_requests: list[TextReplaceRequest] = field(default_factory=list)

    def preview(self, request: TextReplaceRequest) -> TextReplacePreviewResult:
        self.preview_requests.append(request)
        if request in self.preview_failures:
            raise OSError(self.preview_failures[request])
        return self.preview_results.get(
            request,
            TextReplacePreviewResult(
                request=request,
                changed_entries=(),
                total_match_count=0,
                diff_text="",
            ),
        )

    def apply(
        self,
        request: TextReplaceRequest,
        *,
        progress_callback: OperationProgressCallback | None = None,
        cancel_callback: OperationCancelCallback | None = None,
    ) -> TextReplaceResult:
        self.apply_requests.append(request)
        if request in self.apply_failures:
            raise OSError(self.apply_failures[request])
        if cancel_callback is not None and cancel_callback() and request.paths:
            return TextReplaceResult(
                request=request,
                changed_paths=(),
                total_match_count=0,
                message="Replacement cancelled",
                level="warning",
                cancelled=True,
                unprocessed_paths=request.paths,
            )
        return self.apply_results.get(
            request,
            TextReplaceResult(
                request=request,
                changed_paths=(),
                total_match_count=0,
                message="Replaced 0 match(es) in 0 file(s)",
            ),
        )


@dataclass(frozen=True)
class _PatternMatcher:
    pattern: str
    regex: re.Pattern[str]

    def replace(self, text: str, replacement: str) -> tuple[str, int]:
        return self.regex.subn(replacement, text)


def _compile_pattern(query: str) -> _PatternMatcher:
    stripped_query = query.strip()
    if not stripped_query:
        raise InvalidTextReplaceQueryError("Find text is required")
    if stripped_query.startswith(_REGEX_QUERY_PREFIX):
        pattern = stripped_query[len(_REGEX_QUERY_PREFIX) :]
        try:
            return _PatternMatcher(pattern=pattern, regex=re.compile(pattern))
        except re.error as error:
            raise InvalidTextReplaceQueryError(str(error)) from error
    escaped = re.escape(stripped_query)
    return _PatternMatcher(pattern=escaped, regex=re.compile(escaped))


def _build_preview_entry(
    path: Path,
    original: str,
    replaced: str,
    match_count: int,
) -> TextReplacePreviewEntry | None:
    first_changed_line = _find_first_changed_line(original, replaced)
    if first_changed_line is None:
        return None

    line_number, before, after = first_changed_line
    diff_text = _build_unified_diff(path, original, replaced)
    return TextReplacePreviewEntry(
        path=str(path),
        diff_text=diff_text,
        match_count=match_count,
        first_match_line_number=line_number,
        first_match_before=before,
        first_match_after=after,
    )


def _find_first_changed_line(
    original: str,
    replaced: str,
) -> tuple[int, str, str] | None:
    original_lines = original.splitlines()
    replaced_lines = replaced.splitlines()
    line_count = min(len(original_lines), len(replaced_lines))
    for index in range(line_count):
        if original_lines[index] == replaced_lines[index]:
            continue
        return index + 1, original_lines[index], replaced_lines[index]
    return None


def _build_unified_diff(
    path: Path,
    original: str,
    replaced: str,
) -> str:
    return "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            replaced.splitlines(keepends=True),
            fromfile=str(path),
            tofile=f"{path} (replaced)",
            lineterm="\n",
        )
    )


def _write_text_atomically(path: Path, text: str, encoding: str) -> None:
    """Write replacement content beside the target, then replace atomically."""

    target_path = path.resolve() if path.is_symlink() else path
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target_path.name}.zivo-",
        dir=str(target_path.parent),
    )
    os.close(file_descriptor)
    temporary_path = Path(temporary_name)
    try:
        temporary_path.write_text(text, encoding=encoding)
        if target_path.exists() and not target_path.is_symlink():
            temporary_path.chmod(stat.S_IMODE(target_path.stat().st_mode))
        os.replace(temporary_path, target_path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _report_progress(
    callback: OperationProgressCallback | None,
    completed: int,
    total: int,
    current_path: str | None,
) -> None:
    if callback is not None:
        emit_operation_progress(callback, completed, total, current_path)
