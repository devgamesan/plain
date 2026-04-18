"""Preview and apply text replacement across selected files."""

import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from zivo.models import (
    TextReplacePreviewEntry,
    TextReplacePreviewResult,
    TextReplaceRequest,
    TextReplaceResult,
)

_REGEX_QUERY_PREFIX = "re:"


class TextReplaceService(Protocol):
    """Boundary for previewing and applying text replacement."""

    def preview(self, request: TextReplaceRequest) -> TextReplacePreviewResult: ...

    def apply(self, request: TextReplaceRequest) -> TextReplaceResult: ...


class InvalidTextReplaceQueryError(ValueError):
    """Raised when the search pattern cannot be compiled."""


@dataclass(frozen=True)
class LiveTextReplaceService:
    """Replace plain text or regular expressions in UTF-8 text files."""

    encoding: str = "utf-8"

    def preview(self, request: TextReplaceRequest) -> TextReplacePreviewResult:
        matcher = _compile_pattern(request.find_text)
        changed_entries: list[TextReplacePreviewEntry] = []
        diff_chunks: list[str] = []
        skipped_paths: list[str] = []
        total_match_count = 0

        for raw_path in request.paths:
            path = Path(raw_path)
            try:
                original = path.read_text(encoding=self.encoding)
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
        return TextReplacePreviewResult(
            request=request,
            changed_entries=tuple(changed_entries),
            total_match_count=total_match_count,
            diff_text="".join(diff_chunks),
            skipped_paths=tuple(skipped_paths),
        )

    def apply(self, request: TextReplaceRequest) -> TextReplaceResult:
        preview = self.preview(request)
        changed_paths: list[str] = []

        for entry in preview.changed_entries:
            path = Path(entry.path)
            original = path.read_text(encoding=self.encoding)
            replaced, match_count = _compile_pattern(request.find_text).replace(
                original,
                request.replace_text,
            )
            if match_count <= 0:
                continue
            path.write_text(replaced, encoding=self.encoding)
            changed_paths.append(entry.path)

        file_count = len(changed_paths)
        skipped_count = len(preview.skipped_paths)
        message = f"Replaced {preview.total_match_count} match(es) in {file_count} file(s)"
        level = "info"
        if skipped_count:
            level = "warning"
            message += f"; skipped {skipped_count} unreadable file(s)"
        return TextReplaceResult(
            request=request,
            changed_paths=tuple(changed_paths),
            total_match_count=preview.total_match_count,
            message=message,
            level=level,
            skipped_paths=preview.skipped_paths,
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

    def apply(self, request: TextReplaceRequest) -> TextReplaceResult:
        self.apply_requests.append(request)
        if request in self.apply_failures:
            raise OSError(self.apply_failures[request])
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
    diff_text = _build_unified_diff(path, original, replaced)
    original_lines = original.splitlines()
    replaced_lines = replaced.splitlines()
    line_count = min(len(original_lines), len(replaced_lines))
    for index in range(line_count):
        if original_lines[index] == replaced_lines[index]:
            continue
        return TextReplacePreviewEntry(
            path=str(path),
            diff_text=diff_text,
            match_count=match_count,
            first_match_line_number=index + 1,
            first_match_before=original_lines[index],
            first_match_after=replaced_lines[index],
        )
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
