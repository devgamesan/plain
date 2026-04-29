"""Preview-specific loaders and helper types."""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

TEXT_PREVIEW_MAX_BYTES = 64 * 1024
DEFAULT_IMAGE_PREVIEW_COLUMNS = 80
IMAGE_PREVIEW_EXTENSIONS = frozenset(
    {".avif", ".bmp", ".gif", ".jpeg", ".jpg", ".png", ".svg", ".tif", ".tiff", ".webp"}
)
PDF_PREVIEW_EXTENSIONS = frozenset({".pdf"})
OFFICE_PREVIEW_EXTENSIONS = frozenset({".docx", ".xlsx", ".pptx"})
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
IMAGE_PREVIEW_DEPENDENCY_MESSAGE = "Preview unavailable: install `chafa` for image preview"
GREP_PREVIEW_ERROR_MESSAGE = "Preview unavailable: failed to load context"

GrepContextCacheKey = tuple[str, int, int, int, int, int]
_ANSI_CONTROL_SEQUENCE_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
_ANSI_OSC_SEQUENCE_RE = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
_ANSI_STRING_SEQUENCE_RE = re.compile(r"\x1b[P^_X].*?(?:\x1b\\)", re.DOTALL)
_ANSI_ESCAPE_SEQUENCE_RE = re.compile(r"\x1b(?:[@-Z\\-_])")


def _normalize_preview_newlines(text: str) -> str:
    return text.replace("\r\n", "\n")


def _strip_non_sgr_ansi(text: str) -> str:
    text = _ANSI_OSC_SEQUENCE_RE.sub("", text)
    text = _ANSI_STRING_SEQUENCE_RE.sub("", text)

    def _replace(match: re.Match[str]) -> str:
        sequence = match.group(0)
        return sequence if sequence.endswith("m") else ""

    text = _ANSI_CONTROL_SEQUENCE_RE.sub(_replace, text)
    return _ANSI_ESCAPE_SEQUENCE_RE.sub("", text)


@dataclass(frozen=True)
class FilePreviewState:
    kind: Literal["content", "message", "unavailable"]
    content: str | None = None
    content_kind: Literal["text", "image"] = "text"
    message: str | None = None
    truncated: bool = False

    @classmethod
    def with_content(
        cls,
        content: str,
        truncated: bool,
        *,
        content_kind: Literal["text", "image"] = "text",
    ) -> "FilePreviewState":
        return cls(
            kind="content",
            content=content,
            content_kind=content_kind,
            truncated=truncated,
        )

    @classmethod
    def with_message(cls, message: str) -> "FilePreviewState":
        return cls(kind="message", message=message)

    @classmethod
    def permission_denied(cls) -> "FilePreviewState":
        return cls(kind="message", message=PREVIEW_PERMISSION_DENIED_MESSAGE)

    @classmethod
    def unsupported(cls) -> "FilePreviewState":
        return cls(kind="message", message=PREVIEW_UNSUPPORTED_MESSAGE)

    @classmethod
    def unavailable(cls) -> "FilePreviewState":
        return cls(kind="unavailable")

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


class DocumentPreviewLoader(Protocol):
    def load_preview(
        self,
        path: Path,
        *,
        preview_max_bytes: int,
    ) -> FilePreviewState | None: ...


class ImagePreviewLoader(Protocol):
    def load_preview(
        self,
        path: Path,
        *,
        preview_columns: int,
    ) -> FilePreviewState | None: ...


@dataclass
class PandocDocumentPreviewLoader:
    pandoc_path: str | None = field(default=None, init=False, repr=False)
    pandoc_missing: bool = field(default=False, init=False, repr=False)

    def load_preview(
        self,
        path: Path,
        *,
        preview_max_bytes: int,
    ) -> FilePreviewState | None:
        pandoc = self._resolve_pandoc()
        if pandoc is None:
            return None
        try:
            result = subprocess.run(
                [
                    pandoc,
                    "--from",
                    path.suffix.lstrip(".").lower(),
                    "--to",
                    "markdown",
                    str(path),
                ],
                check=True,
                capture_output=True,
            )
        except (OSError, subprocess.SubprocessError, ValueError):
            return None

        try:
            content = _normalize_preview_newlines(result.stdout.decode("utf-8"))
        except UnicodeDecodeError:
            content = _normalize_preview_newlines(
                result.stdout.decode("utf-8", errors="ignore")
            )
        if not content.strip():
            return None
        return _truncate_preview_text(content, preview_max_bytes)

    def _resolve_pandoc(self) -> str | None:
        if self.pandoc_missing:
            return None
        if self.pandoc_path is not None:
            return self.pandoc_path
        pandoc = shutil.which("pandoc")
        if pandoc is None:
            self.pandoc_missing = True
            return None
        self.pandoc_path = pandoc
        return pandoc


@dataclass
class ChafaImagePreviewLoader:
    chafa_path: str | None = field(default=None, init=False, repr=False)
    chafa_missing: bool = field(default=False, init=False, repr=False)

    def load_preview(
        self,
        path: Path,
        *,
        preview_columns: int,
    ) -> FilePreviewState | None:
        chafa = self._resolve_chafa()
        if chafa is None:
            return None
        try:
            result = subprocess.run(
                [
                    chafa,
                    "--format",
                    "symbols",
                    "--colors",
                    "full",
                    "--animate",
                    "off",
                    "--fit-width",
                    "--size",
                    f"{max(1, preview_columns)}x",
                    str(path),
                ],
                check=True,
                capture_output=True,
            )
        except (OSError, subprocess.SubprocessError, ValueError):
            return None

        try:
            content = _normalize_preview_newlines(result.stdout.decode("utf-8"))
        except UnicodeDecodeError:
            content = _normalize_preview_newlines(
                result.stdout.decode("utf-8", errors="ignore")
            )
        content = _strip_non_sgr_ansi(content)
        if not content.strip():
            return None
        return FilePreviewState.with_content(content, False, content_kind="image")

    def _resolve_chafa(self) -> str | None:
        if self.chafa_missing:
            return None
        if self.chafa_path is not None:
            return self.chafa_path
        chafa = shutil.which("chafa")
        if chafa is None:
            self.chafa_missing = True
            return None
        self.chafa_path = chafa
        return chafa


def _build_text_preview_cache_key(
    path: Path,
    preview_max_bytes: int,
    enable_text_preview: bool,
    enable_image_preview: bool,
    enable_pdf_preview: bool,
    enable_office_preview: bool,
    preview_columns: int,
) -> tuple[str, int, int, int, bool, bool, bool, bool, int] | FilePreviewState:
    preview_limit = max(1, preview_max_bytes)
    try:
        stat = path.stat()
    except PermissionError:
        return FilePreviewState.permission_denied()
    except OSError:
        return FilePreviewState.error()
    return (
        str(path),
        stat.st_mtime_ns,
        stat.st_size,
        preview_limit,
        enable_text_preview,
        enable_image_preview,
        enable_pdf_preview,
        enable_office_preview,
        max(1, preview_columns),
    )


def _build_grep_context_cache_key(
    path: Path,
    line_number: int,
    context_lines: int,
    preview_max_bytes: int,
) -> GrepContextCacheKey | ContextPreviewState:
    preview_limit = max(1, preview_max_bytes)
    try:
        stat = path.stat()
    except PermissionError:
        return ContextPreviewState.with_message(PREVIEW_PERMISSION_DENIED_MESSAGE)
    except OSError:
        return ContextPreviewState.with_message(GREP_PREVIEW_ERROR_MESSAGE)
    return (
        str(path),
        stat.st_mtime_ns,
        stat.st_size,
        line_number,
        context_lines,
        preview_limit,
    )


def _load_text_preview(
    path: Path,
    *,
    preview_max_bytes: int = TEXT_PREVIEW_MAX_BYTES,
    enable_text_preview: bool = True,
    enable_image_preview: bool = True,
    enable_pdf_preview: bool = True,
    enable_office_preview: bool = True,
    document_preview_loader: DocumentPreviewLoader | None = None,
    image_preview_loader: ImagePreviewLoader | None = None,
    preview_columns: int = DEFAULT_IMAGE_PREVIEW_COLUMNS,
) -> FilePreviewState:
    if _is_image_preview_candidate(path):
        if not enable_image_preview:
            return FilePreviewState.unavailable()
        loader = image_preview_loader or ChafaImagePreviewLoader()
        preview = loader.load_preview(path, preview_columns=max(1, preview_columns))
        if preview is not None:
            return preview
        return FilePreviewState.with_message(IMAGE_PREVIEW_DEPENDENCY_MESSAGE)

    if _is_pdf_preview_candidate(path):
        if not enable_pdf_preview:
            return FilePreviewState.unavailable()
        preview = _load_pdf_preview(path, preview_max_bytes=preview_max_bytes)
        if preview is not None:
            return preview
        return FilePreviewState.unsupported()

    if _is_office_preview_candidate(path):
        if not enable_office_preview:
            return FilePreviewState.unavailable()
        loader = document_preview_loader or PandocDocumentPreviewLoader()
        preview = loader.load_preview(path, preview_max_bytes=preview_max_bytes)
        if preview is not None:
            return preview
        return FilePreviewState.unsupported()

    if not enable_text_preview:
        return FilePreviewState.unavailable()

    preview_limit = max(1, preview_max_bytes)
    try:
        with path.open("rb") as handle:
            chunk = handle.read(preview_limit + 1)
    except PermissionError:
        return FilePreviewState.permission_denied()
    except OSError:
        return FilePreviewState.error()

    if b"\x00" in chunk[:preview_limit]:
        if _has_image_signature(path, header=chunk[:32]):
            if not enable_image_preview:
                return FilePreviewState.unavailable()
            loader = image_preview_loader or ChafaImagePreviewLoader()
            preview = loader.load_preview(path, preview_columns=max(1, preview_columns))
            if preview is not None:
                return preview
        return FilePreviewState.unsupported()

    truncated = len(chunk) > preview_limit
    preview_bytes = chunk[:preview_limit]
    try:
        preview_text = _normalize_preview_newlines(preview_bytes.decode("utf-8"))
    except UnicodeDecodeError:
        if _has_image_signature(path, header=chunk[:32]):
            if not enable_image_preview:
                return FilePreviewState.unavailable()
            loader = image_preview_loader or ChafaImagePreviewLoader()
            preview = loader.load_preview(path, preview_columns=max(1, preview_columns))
            if preview is not None:
                return preview
        return FilePreviewState.unsupported()

    return FilePreviewState.with_content(preview_text, truncated)


def _load_pdf_preview(
    path: Path,
    *,
    preview_max_bytes: int,
) -> FilePreviewState | None:
    pdftotext = shutil.which("pdftotext")
    if pdftotext is None:
        return None
    try:
        path_str = str(path)
        if " " in path_str:
            path_str = f'"{path_str}"'
        result = subprocess.run(
            [pdftotext, "-q", path_str, "-"],
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.SubprocessError, FileNotFoundError):
        return None
    try:
        content = _normalize_preview_newlines(result.stdout.decode("utf-8"))
    except UnicodeDecodeError:
        content = _normalize_preview_newlines(
            result.stdout.decode("utf-8", errors="ignore")
        )
    if not content.strip():
        return FilePreviewState.with_message("PDF preview: no text content found")
    return _truncate_preview_text(content, preview_max_bytes)


def _load_grep_context_preview(
    path: Path,
    line_number: int,
    context_lines: int,
    *,
    preview_max_bytes: int = TEXT_PREVIEW_MAX_BYTES,
) -> ContextPreviewState:
    preview_limit = max(1, preview_max_bytes)
    start_line = max(1, line_number - max(0, context_lines))
    end_line = line_number + max(0, context_lines)
    lines: list[str] = []
    last_line = 0
    bytes_read = 0

    try:
        with path.open("rb") as handle:
            current_line = 0
            while current_line < end_line:
                line_bytes = handle.readline()
                if not line_bytes:
                    break

                bytes_read += len(line_bytes)
                current_line += 1

                if bytes_read <= preview_limit:
                    if b"\x00" in line_bytes:
                        return ContextPreviewState.with_message(PREVIEW_UNSUPPORTED_MESSAGE)
                    try:
                        line_bytes.decode("utf-8")
                    except UnicodeDecodeError:
                        return ContextPreviewState.with_message(PREVIEW_UNSUPPORTED_MESSAGE)

                if current_line >= start_line:
                    try:
                        line_text = _normalize_preview_newlines(line_bytes.decode("utf-8"))
                        lines.append(line_text)
                        last_line = current_line
                    except UnicodeDecodeError:
                        return ContextPreviewState.with_message(GREP_PREVIEW_ERROR_MESSAGE)

    except PermissionError:
        return ContextPreviewState.with_message(PREVIEW_PERMISSION_DENIED_MESSAGE)
    except OSError:
        return ContextPreviewState.with_message(GREP_PREVIEW_ERROR_MESSAGE)

    if not lines or last_line < line_number:
        return ContextPreviewState.with_message(GREP_PREVIEW_ERROR_MESSAGE)

    return ContextPreviewState.with_content(
        "".join(lines),
        start_line=start_line,
        highlight_line=line_number,
    )


def _is_text_content(path: Path, blocksize: int = 512) -> bool:
    try:
        with path.open("rb") as f:
            chunk = f.read(blocksize)
    except (PermissionError, OSError):
        return False

    if not chunk:
        return True

    if b"\x00" in chunk:
        return False

    try:
        chunk.decode("utf-8")
        return True
    except UnicodeDecodeError:
        pass

    printable = sum((32 <= b <= 126) or b in (9, 10, 13) for b in chunk)
    return printable / len(chunk) > 0.7


def _is_preview_candidate(path: Path) -> bool:
    if (
        _is_image_preview_candidate(path)
        or _is_pdf_preview_candidate(path)
        or _is_office_preview_candidate(path)
    ):
        return True

    if path.name.casefold() in TEXT_PREVIEW_FILENAMES:
        return True
    suffix = path.suffix.casefold()
    if suffix in TEXT_PREVIEW_EXTENSIONS:
        return True

    return _is_text_content(path)


def _is_pdf_preview_candidate(path: Path) -> bool:
    return path.suffix.casefold() in PDF_PREVIEW_EXTENSIONS


def _is_image_preview_candidate(path: Path) -> bool:
    return path.suffix.casefold() in IMAGE_PREVIEW_EXTENSIONS


def _has_image_signature(path: Path, *, header: bytes | None = None) -> bool:
    if header is None:
        try:
            with path.open("rb") as handle:
                header = handle.read(32)
        except OSError:
            return False
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    if header.startswith((b"\xff\xd8\xff", b"GIF87a", b"GIF89a", b"BM")):
        return True
    if header.startswith((b"II*\x00", b"MM\x00*")):
        return True
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return True
    if len(header) >= 12 and header[4:12] in {
        b"ftypavif",
        b"ftypavis",
        b"ftypmif1",
        b"ftypmsf1",
    }:
        return True
    return False


def _is_office_preview_candidate(path: Path) -> bool:
    return path.suffix.casefold() in OFFICE_PREVIEW_EXTENSIONS


def _truncate_preview_text(content: str, preview_max_bytes: int) -> FilePreviewState:
    preview_limit = max(1, preview_max_bytes)
    encoded = content.encode("utf-8")
    truncated = len(encoded) > preview_limit
    if not truncated:
        return FilePreviewState.with_content(content, False)

    preview_bytes = encoded[:preview_limit]
    preview_text = preview_bytes.decode("utf-8", errors="ignore")
    return FilePreviewState.with_content(preview_text, True)


def preview_max_bytes_from_kib(preview_max_kib: int) -> int:
    return max(1, preview_max_kib) * 1024
