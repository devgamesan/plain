"""Preview-specific loaders and helper types."""

from __future__ import annotations

import inspect
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

from zivo.models.config import ImagePreviewMode, PreviewResourceConfig
from zivo.services.bounded_process import run_bounded_process
from zivo.services.terminal_detection import supports_kitty_graphics

from .ooxml import (
    CORRUPT_MESSAGE as _OOXML_CORRUPT_MESSAGE,
)
from .ooxml import (
    ENCRYPTED_MESSAGE as _OOXML_ENCRYPTED_MESSAGE,
)
from .ooxml import (
    NO_TEXT_MESSAGE as _OOXML_NO_TEXT_MESSAGE,
)
from .ooxml import (
    extract_ooxml_preview,
)

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
PREVIEW_LIMITED_MESSAGE = "Preview limited by a safety limit"
PREVIEW_TIMEOUT_MESSAGE = "Preview stopped at a safety limit"
PREVIEW_RESOURCE_LIMIT_MESSAGE = "Preview stopped at a safety limit"
PREVIEW_CANCELLED_MESSAGE = "Preview cancelled"
PREVIEW_NO_TEXT_CONTENT_MESSAGE = "No text content found"
IMAGE_PREVIEW_DEPENDENCY_MESSAGE = "Preview unavailable: install `chafa` for image preview"
PDF_PREVIEW_DEPENDENCY_MESSAGE = "PDF preview unavailable: install `pdftotext`"
PDF_PREVIEW_ENCRYPTED_MESSAGE = "PDF preview unavailable: password-protected document"
OFFICE_PREVIEW_CORRUPT_MESSAGE = _OOXML_CORRUPT_MESSAGE
OFFICE_PREVIEW_ENCRYPTED_MESSAGE = _OOXML_ENCRYPTED_MESSAGE
OFFICE_PREVIEW_NO_TEXT_MESSAGE = _OOXML_NO_TEXT_MESSAGE
GREP_PREVIEW_ERROR_MESSAGE = "Preview unavailable: failed to load context"

GrepContextCacheKey = tuple[str, int, int, int, int, int]
GrepContextWindowCacheKey = tuple[str, int, int, int]
DEFAULT_GREP_CONTEXT_WINDOW_LOOKAHEAD_LINES = 64
_ANSI_CONTROL_SEQUENCE_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
_ANSI_OSC_SEQUENCE_RE = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
_ANSI_STRING_SEQUENCE_RE = re.compile(r"\x1b[P^_X].*?(?:\x1b\\)", re.DOTALL)
_ANSI_ESCAPE_SEQUENCE_RE = re.compile(r"\x1b(?:[@-Z\\-_])")
CancelCallback = Callable[[], bool]


@dataclass(frozen=True)
class PreviewResourceBudget:
    """Fixed safety limits shared by preview backends.

    These are normalized process limits.  Built-in defaults can be overridden by
    the advanced ``[preview]`` configuration section.
    """

    timeout_seconds: float = 5.0
    stdout_max_bytes: int = 256 * 1024
    stderr_max_bytes: int = 16 * 1024
    image_timeout_seconds: float = 15.0
    image_stdout_max_bytes: int = 2 * 1024 * 1024
    kitty_stdout_max_bytes: int = 32 * 1024 * 1024
    input_max_bytes: int = 256 * 1024 * 1024
    pdf_max_pages: int = 64
    pdf_max_content_stream_bytes: int = 1 * 1024 * 1024
    max_archive_entries: int = 4096
    max_archive_entry_bytes: int = 64 * 1024 * 1024
    max_archive_total_bytes: int = 256 * 1024 * 1024
    max_archive_compression_ratio: float = 100.0
    timeout_cache_seconds: float = 1.0

    @classmethod
    def from_config(cls, config: PreviewResourceConfig) -> "PreviewResourceBudget":
        """Convert user-facing KiB/MiB config values into process limits."""

        kib = 1024
        mib = 1024 * kib
        return cls(
            timeout_seconds=config.timeout_seconds,
            stdout_max_bytes=config.stdout_max_kib * kib,
            stderr_max_bytes=config.stderr_max_kib * kib,
            image_timeout_seconds=config.image_timeout_seconds,
            image_stdout_max_bytes=config.image_stdout_max_mib * mib,
            kitty_stdout_max_bytes=config.kitty_stdout_max_mib * mib,
            input_max_bytes=config.input_max_mib * mib,
            max_archive_entries=config.max_archive_entries,
            max_archive_entry_bytes=config.max_archive_entry_mib * mib,
            max_archive_total_bytes=config.max_archive_total_mib * mib,
            max_archive_compression_ratio=config.max_archive_compression_ratio,
            timeout_cache_seconds=config.timeout_cache_seconds,
        )


DEFAULT_PREVIEW_RESOURCE_BUDGET = PreviewResourceBudget()


@dataclass(frozen=True)
class _PreviewProcessResult:
    """Normalized converter result used without exposing converter diagnostics."""

    exit_code: int
    stdout: str = ""
    stderr: str = ""
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    termination_reason: Literal["completed", "timed_out", "cancelled", "output_limited"] = (
        "completed"
    )


_ORIGINAL_SUBPROCESS_RUN = subprocess.run


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


def _strip_ansi_for_kitty(text: str) -> str:
    """Strip ANSI sequences that would interfere with Kitty graphics protocol.

    Unlike _strip_non_sgr_ansi, this preserves Kitty graphics protocol APC
    strings (ESC_G ... ESC\\) so they can be passed through to the terminal.
    """
    text = _ANSI_OSC_SEQUENCE_RE.sub("", text)

    def _replace(match: re.Match[str]) -> str:
        sequence = match.group(0)
        return sequence if sequence.endswith("m") else ""

    text = _ANSI_CONTROL_SEQUENCE_RE.sub(_replace, text)
    return text


@dataclass(frozen=True)
class FilePreviewState:
    kind: Literal["content", "message", "unavailable"]
    content: str | None = None
    content_kind: Literal["text", "image", "kitty"] = "text"
    message: str | None = None
    truncated: bool = False
    reason: str | None = None

    @classmethod
    def with_content(
        cls,
        content: str,
        truncated: bool,
        *,
        content_kind: Literal["text", "image", "kitty"] = "text",
        reason: str | None = None,
    ) -> "FilePreviewState":
        return cls(
            kind="content",
            content=content,
            content_kind=content_kind,
            truncated=truncated,
            reason=reason,
        )

    @classmethod
    def with_message(cls, message: str, *, reason: str | None = None) -> "FilePreviewState":
        return cls(kind="message", message=message, reason=reason)

    @classmethod
    def permission_denied(cls) -> "FilePreviewState":
        return cls(
            kind="message",
            message=PREVIEW_PERMISSION_DENIED_MESSAGE,
            reason="permission_denied",
        )

    @classmethod
    def unsupported(cls) -> "FilePreviewState":
        return cls(kind="message", message=PREVIEW_UNSUPPORTED_MESSAGE, reason="unsupported")

    @classmethod
    def unavailable(cls, reason: str = "disabled") -> "FilePreviewState":
        return cls(kind="unavailable", reason=reason)

    @classmethod
    def error(cls) -> "FilePreviewState":
        return cls(kind="message", message=PREVIEW_ERROR_MESSAGE, reason="error")


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


@dataclass(frozen=True)
class GrepContextWindowState:
    start_line: int
    lines: tuple[str, ...]
    hit_eof: bool = False

    @property
    def end_line(self) -> int:
        return self.start_line + len(self.lines) - 1


class DocumentPreviewLoader(Protocol):
    def load_preview(
        self,
        path: Path,
        *,
        preview_max_bytes: int,
        cancel_callback: CancelCallback | None = None,
    ) -> FilePreviewState | None: ...


class PdfPreviewLoader(Protocol):
    def load_preview(
        self,
        path: Path,
        *,
        preview_max_bytes: int,
        cancel_callback: CancelCallback | None = None,
    ) -> FilePreviewState | None: ...


class ImagePreviewLoader(Protocol):
    def load_preview(
        self,
        path: Path,
        *,
        preview_columns: int,
        preview_rows: int | None = None,
        image_preview_format: str = "symbols",
        cancel_callback: CancelCallback | None = None,
    ) -> FilePreviewState | None: ...


@dataclass
class OfficeDocumentPreviewLoader:
    """Extract plain text from modern Office Open XML packages in-process."""

    resource_budget: PreviewResourceBudget = DEFAULT_PREVIEW_RESOURCE_BUDGET

    def load_preview(
        self,
        path: Path,
        *,
        preview_max_bytes: int,
        cancel_callback: CancelCallback | None = None,
    ) -> FilePreviewState | None:
        result = extract_ooxml_preview(
            path,
            preview_max_bytes=preview_max_bytes,
            resource_budget=self.resource_budget,
            cancel_callback=cancel_callback,
        )
        if result.content is not None:
            if result.truncated and not result.content:
                return FilePreviewState.with_message(
                    PREVIEW_RESOURCE_LIMIT_MESSAGE,
                    reason="resource_limit",
                )
            return FilePreviewState.with_content(
                result.content,
                result.truncated,
                reason=result.reason,
            )
        if result.reason == "cancelled":
            return FilePreviewState.unavailable("cancelled")
        message = result.message or PREVIEW_ERROR_MESSAGE
        return FilePreviewState.with_message(message, reason=result.reason)


@dataclass
class PdftotextPdfPreviewLoader:
    resource_budget: PreviewResourceBudget = DEFAULT_PREVIEW_RESOURCE_BUDGET
    pdftotext_path: str | None = field(default=None, init=False, repr=False)
    pdftotext_missing: bool = field(default=False, init=False, repr=False)

    def load_preview(
        self,
        path: Path,
        *,
        preview_max_bytes: int,
        cancel_callback: CancelCallback | None = None,
    ) -> FilePreviewState | None:
        pdftotext = self._resolve_pdftotext()
        if pdftotext is None:
            return FilePreviewState.with_message(
                PDF_PREVIEW_DEPENDENCY_MESSAGE,
                reason="dependency_missing",
            )
        limited = _preview_input_limit(path, self.resource_budget, cancel_callback)
        if limited is not None:
            return limited
        command = [pdftotext, "-q", str(path), "-"]
        try:
            result = _run_preview_process(
                command,
                path=path,
                preview_max_bytes=preview_max_bytes,
                resource_budget=self.resource_budget,
                cancel_callback=cancel_callback,
            )
        except (OSError, subprocess.SubprocessError, FileNotFoundError):
            return None
        if result.termination_reason == "cancelled":
            return FilePreviewState.unavailable("cancelled")
        if result.termination_reason == "timed_out" and not result.stdout.strip():
            return FilePreviewState.with_message(PREVIEW_TIMEOUT_MESSAGE, reason="timeout")
        if result.termination_reason == "output_limited" and not result.stdout.strip():
            return FilePreviewState.with_message(
                PREVIEW_RESOURCE_LIMIT_MESSAGE,
                reason="resource_limit",
            )
        if result.exit_code != 0 and not result.stdout.strip():
            return None
        content = _normalize_preview_newlines(result.stdout)
        if not content.strip():
            return FilePreviewState.with_message(
                PREVIEW_NO_TEXT_CONTENT_MESSAGE,
                reason="no_text_content",
            )
        return _preview_text_from_process_result(result, preview_max_bytes)

    def _resolve_pdftotext(self) -> str | None:
        if self.pdftotext_missing:
            return None
        if self.pdftotext_path is not None:
            return self.pdftotext_path
        pdftotext = shutil.which("pdftotext")
        if pdftotext is None:
            self.pdftotext_missing = True
            return None
        self.pdftotext_path = pdftotext
        return pdftotext


@dataclass
class PypdfPdfPreviewLoader:
    """Extract bounded PDF text in a disposable pypdf worker process."""

    resource_budget: PreviewResourceBudget = DEFAULT_PREVIEW_RESOURCE_BUDGET

    def load_preview(
        self,
        path: Path,
        *,
        preview_max_bytes: int,
        cancel_callback: CancelCallback | None = None,
    ) -> FilePreviewState | None:
        limited = _preview_input_limit(path, self.resource_budget, cancel_callback)
        if limited is not None:
            return limited
        command = [
            sys.executable,
            "-m",
            "zivo.services.previews.pdf_worker",
            str(path),
            "--max-pages",
            str(self.resource_budget.pdf_max_pages),
            "--max-output-bytes",
            str(max(1, preview_max_bytes)),
            "--max-content-stream-bytes",
            str(self.resource_budget.pdf_max_content_stream_bytes),
        ]
        try:
            result = _run_preview_process(
                command,
                path=path,
                preview_max_bytes=max(1, preview_max_bytes) + 4096,
                resource_budget=self.resource_budget,
                cancel_callback=cancel_callback,
            )
        except (OSError, subprocess.SubprocessError, FileNotFoundError):
            return FilePreviewState.error()
        if result.termination_reason == "cancelled":
            return FilePreviewState.unavailable("cancelled")
        if result.termination_reason == "timed_out":
            return FilePreviewState.with_message(PREVIEW_TIMEOUT_MESSAGE, reason="timeout")
        if result.termination_reason == "output_limited":
            return FilePreviewState.with_message(
                PREVIEW_RESOURCE_LIMIT_MESSAGE,
                reason="resource_limit",
            )
        if result.exit_code != 0:
            return FilePreviewState.error()
        try:
            payload = json.loads(result.stdout)
        except (TypeError, ValueError):
            return FilePreviewState.error()
        reason = payload.get("reason")
        if reason == "success":
            return FilePreviewState.with_content(
                str(payload.get("content") or ""),
                bool(payload.get("truncated")),
                reason="resource_limit" if payload.get("truncated") else None,
            )
        if reason == "no_text_content":
            return FilePreviewState.with_message(
                PREVIEW_NO_TEXT_CONTENT_MESSAGE,
                reason="no_text_content",
            )
        if reason == "encrypted":
            return FilePreviewState.with_message(
                PDF_PREVIEW_ENCRYPTED_MESSAGE,
                reason="encrypted",
            )
        if reason == "permission_denied":
            return FilePreviewState.permission_denied()
        if reason == "dependency_missing":
            return FilePreviewState.with_message(
                "PDF preview backend unavailable",
                reason="dependency_missing",
            )
        if reason == "resource_limit":
            content = str(payload.get("content") or "")
            if content:
                return FilePreviewState.with_content(content, True, reason="resource_limit")
            return FilePreviewState.with_message(
                PREVIEW_RESOURCE_LIMIT_MESSAGE,
                reason="resource_limit",
            )
        if reason == "corrupt":
            return FilePreviewState.with_message(PREVIEW_ERROR_MESSAGE, reason="corrupt")
        return None


@dataclass
class HybridPdfPreviewLoader:
    """Use pypdf first, with one bounded pdftotext fallback for parser failures."""

    resource_budget: PreviewResourceBudget = DEFAULT_PREVIEW_RESOURCE_BUDGET
    pypdf_loader: PdfPreviewLoader | None = None
    pdftotext_loader: PdfPreviewLoader | None = None

    def load_preview(
        self,
        path: Path,
        *,
        preview_max_bytes: int,
        cancel_callback: CancelCallback | None = None,
    ) -> FilePreviewState | None:
        primary_loader = self.pypdf_loader or PypdfPdfPreviewLoader(
            resource_budget=self.resource_budget
        )
        primary = primary_loader.load_preview(
            path,
            preview_max_bytes=preview_max_bytes,
            cancel_callback=cancel_callback,
        )
        if primary is None:
            return None
        if primary.reason not in {"no_text_content", "unsupported", "corrupt"}:
            return primary
        fallback_loader = self.pdftotext_loader or PdftotextPdfPreviewLoader(
            resource_budget=self.resource_budget
        )
        fallback = fallback_loader.load_preview(
            path,
            preview_max_bytes=preview_max_bytes,
            cancel_callback=cancel_callback,
        )
        if fallback is not None and fallback.kind == "content":
            return fallback
        return primary


def resolve_image_preview_format(image_preview_mode: ImagePreviewMode) -> str:
    """Return the chafa format string for the given preview mode.

    In auto mode, the terminal is probed at call time and "kitty" is
    returned when the Kitty graphics protocol is available.
    """
    if image_preview_mode == "kitty":
        return "kitty"
    if image_preview_mode == "auto":
        if supports_kitty_graphics():
            return "kitty"
    return "symbols"


@dataclass
class ChafaImagePreviewLoader:
    resource_budget: PreviewResourceBudget = DEFAULT_PREVIEW_RESOURCE_BUDGET
    chafa_path: str | None = field(default=None, init=False, repr=False)
    chafa_missing: bool = field(default=False, init=False, repr=False)
    supports_animate_option: bool | None = field(default=None, init=False, repr=False)

    def load_preview(
        self,
        path: Path,
        *,
        preview_columns: int,
        preview_rows: int | None = None,
        image_preview_format: str = "symbols",
        cancel_callback: CancelCallback | None = None,
    ) -> FilePreviewState | None:
        chafa = self._resolve_chafa()
        if chafa is None:
            return None
        limited = _preview_input_limit(path, self.resource_budget, cancel_callback)
        if limited is not None:
            return limited
        args = self._build_chafa_command(
            chafa,
            path,
            preview_columns=preview_columns,
            preview_rows=preview_rows,
            chafa_format=image_preview_format,
        )
        try:
            output_limit = (
                self.resource_budget.kitty_stdout_max_bytes
                if image_preview_format == "kitty"
                else self.resource_budget.image_stdout_max_bytes
            )
            result = _run_preview_process(
                args,
                path=path,
                preview_max_bytes=output_limit,
                resource_budget=self.resource_budget,
                stdout_max_bytes=output_limit,
                timeout_seconds=self.resource_budget.image_timeout_seconds,
                cancel_callback=cancel_callback,
            )
            if result.exit_code != 0 and result.termination_reason == "completed":
                raise subprocess.CalledProcessError(
                    result.exit_code,
                    args,
                    output=result.stdout.encode("utf-8"),
                    stderr=result.stderr.encode("utf-8"),
                )
            self.supports_animate_option = "--animate" in args
        except subprocess.CalledProcessError as error:
            if not self._should_retry_without_animate(error, args):
                return FilePreviewState.error()
            self.supports_animate_option = False
            fallback_args = self._build_chafa_command(
                chafa,
                path,
                preview_columns=preview_columns,
                preview_rows=preview_rows,
                chafa_format=image_preview_format,
            )
            try:
                result = _run_preview_process(
                    fallback_args,
                    path=path,
                    preview_max_bytes=output_limit,
                    resource_budget=self.resource_budget,
                    stdout_max_bytes=output_limit,
                    timeout_seconds=self.resource_budget.image_timeout_seconds,
                    cancel_callback=cancel_callback,
                )
                if result.exit_code != 0 and result.termination_reason == "completed":
                    return FilePreviewState.error()
            except (OSError, subprocess.SubprocessError, ValueError):
                return FilePreviewState.error()
        except (OSError, subprocess.SubprocessError, ValueError):
            return FilePreviewState.error()

        if result.termination_reason == "cancelled":
            return FilePreviewState.unavailable("cancelled")
        if result.termination_reason in {"timed_out", "output_limited"}:
            return FilePreviewState.with_message(
                PREVIEW_TIMEOUT_MESSAGE
                if result.termination_reason == "timed_out"
                else PREVIEW_RESOURCE_LIMIT_MESSAGE,
                reason=(
                    "timeout"
                    if result.termination_reason == "timed_out"
                    else "resource_limit"
                ),
            )
        content = _normalize_preview_newlines(result.stdout)
        if image_preview_format == "kitty":
            content = _strip_ansi_for_kitty(content)
            if not content.strip():
                return FilePreviewState.error()
            return FilePreviewState.with_content(content, False, content_kind="kitty")
        content = _strip_non_sgr_ansi(content)
        if not content.strip():
            return FilePreviewState.error()
        return FilePreviewState.with_content(content, False, content_kind="image")

    def _build_chafa_command(
        self,
        chafa: str,
        path: Path,
        *,
        preview_columns: int,
        preview_rows: int | None = None,
        chafa_format: str = "symbols",
    ) -> list[str]:
        args = [
            chafa,
            "--format",
            chafa_format,
            "--colors",
            "full",
        ]
        if self.supports_animate_option is False:
            args.extend(["--duration", "0"])
        else:
            args.extend(["--animate", "off"])
        size = f"{max(1, preview_columns)}x"
        if chafa_format == "kitty" and preview_rows is not None:
            size += str(max(1, preview_rows))
        args.extend(["--size", size, str(path)])
        return args

    def _should_retry_without_animate(
        self,
        error: subprocess.CalledProcessError,
        args: list[str],
    ) -> bool:
        if "--animate" not in args:
            return False
        stderr = error.stderr or b""
        return b"Unknown option --animate" in stderr

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


def _as_preview_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return value.decode("utf-8", errors="ignore")


def _run_preview_process(
    command: list[str],
    *,
    path: Path,
    preview_max_bytes: int,
    resource_budget: PreviewResourceBudget,
    cancel_callback: CancelCallback | None,
    stdout_max_bytes: int | None = None,
    timeout_seconds: float | None = None,
) -> _PreviewProcessResult:
    """Run a converter with bounded output and process-group termination.

    The subprocess.run compatibility branch keeps existing loader injection
    tests and embedders working while the normal path always uses the bounded
    runner.  It is only selected when subprocess.run has been monkeypatched.
    """

    if subprocess.run is not _ORIGINAL_SUBPROCESS_RUN:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            stdin=subprocess.DEVNULL,
        )
        return _PreviewProcessResult(
            exit_code=0,
            stdout=_as_preview_text(getattr(completed, "stdout", None)),
            stderr=_as_preview_text(getattr(completed, "stderr", None)),
        )

    stdout_limit = max(
        1,
        min(
            preview_max_bytes,
            resource_budget.stdout_max_bytes
            if stdout_max_bytes is None
            else stdout_max_bytes,
        ),
    )
    process_timeout = (
        resource_budget.timeout_seconds
        if timeout_seconds is None
        else timeout_seconds
    )
    result = run_bounded_process(
        command,
        cwd=str(path.parent),
        env=os.environ,
        max_output_bytes=max(stdout_limit, resource_budget.stderr_max_bytes),
        stdout_max_output_bytes=stdout_limit,
        stderr_max_output_bytes=resource_budget.stderr_max_bytes,
        timeout_seconds=process_timeout,
        cancel_callback=cancel_callback,
        prefix_only=True,
        terminate_on_output_limit=True,
    )
    return _PreviewProcessResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        stdout_truncated=result.stdout_truncated,
        stderr_truncated=result.stderr_truncated,
        termination_reason=result.termination_reason,
    )


def _preview_input_limit(
    path: Path,
    resource_budget: PreviewResourceBudget,
    cancel_callback: CancelCallback | None,
) -> FilePreviewState | None:
    if cancel_callback is not None and cancel_callback():
        return FilePreviewState.unavailable("cancelled")
    try:
        size = path.stat().st_size
    except OSError:
        return None
    if size > resource_budget.input_max_bytes:
        return FilePreviewState.with_message(
            PREVIEW_RESOURCE_LIMIT_MESSAGE,
            reason="resource_limit",
        )
    return None


def _call_preview_loader(loader: object, path: Path, **kwargs: object):
    """Call built-in or test loaders without requiring the new optional kwargs."""

    load_preview = getattr(loader, "load_preview")
    try:
        parameters = inspect.signature(load_preview).parameters
    except (TypeError, ValueError):
        return load_preview(path, **kwargs)
    accepts_kwargs = any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    )
    if not accepts_kwargs:
        kwargs = {key: value for key, value in kwargs.items() if key in parameters}
    return load_preview(path, **kwargs)


def _preview_text_from_process_result(
    result: _PreviewProcessResult,
    preview_max_bytes: int,
) -> FilePreviewState | None:
    if result.termination_reason == "cancelled":
        return FilePreviewState.unavailable("cancelled")
    if not result.stdout.strip():
        if result.termination_reason == "timed_out":
            return FilePreviewState.with_message(PREVIEW_TIMEOUT_MESSAGE, reason="timeout")
        if result.termination_reason == "output_limited":
            return FilePreviewState.with_message(
                PREVIEW_RESOURCE_LIMIT_MESSAGE,
                reason="resource_limit",
            )
        if result.exit_code == 0:
            return FilePreviewState.with_message(
                PREVIEW_NO_TEXT_CONTENT_MESSAGE,
                reason="no_text_content",
            )
        if result.exit_code != 0:
            return None
        return None
    reason = None
    limited = result.stdout_truncated
    if result.termination_reason == "timed_out":
        reason = "timeout"
        limited = True
    elif result.termination_reason == "output_limited" or result.stdout_truncated:
        reason = "resource_limit"
        limited = True
    preview = _truncate_preview_text(result.stdout, preview_max_bytes, reason=reason)
    if limited and not preview.truncated:
        return FilePreviewState.with_content(
            preview.content or "",
            True,
            reason=reason or "resource_limit",
        )
    return preview


def _build_text_preview_cache_key(
    path: Path,
    preview_max_bytes: int,
    enable_text_preview: bool,
    enable_image_preview: bool,
    enable_pdf_preview: bool,
    enable_office_preview: bool,
    preview_columns: int,
    image_preview_mode: ImagePreviewMode = "auto",
) -> tuple[str, int, int, int, bool, bool, bool, bool, int, str] | FilePreviewState:
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
        image_preview_mode,
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
    pdf_preview_loader: PdfPreviewLoader | None = None,
    image_preview_loader: ImagePreviewLoader | None = None,
    preview_columns: int = DEFAULT_IMAGE_PREVIEW_COLUMNS,
    image_preview_mode: ImagePreviewMode = "auto",
    cancel_callback: CancelCallback | None = None,
    resource_budget: PreviewResourceBudget = DEFAULT_PREVIEW_RESOURCE_BUDGET,
) -> FilePreviewState:
    if cancel_callback is not None and cancel_callback():
        return FilePreviewState.unavailable("cancelled")
    if _is_image_preview_candidate(path):
        if not enable_image_preview:
            return FilePreviewState.unavailable()
        loader = image_preview_loader or ChafaImagePreviewLoader(
            resource_budget=resource_budget
        )
        fmt = resolve_image_preview_format(image_preview_mode)
        preview = _call_preview_loader(
            loader,
            path,
            preview_columns=max(1, preview_columns),
            image_preview_format=fmt,
            cancel_callback=cancel_callback,
        )
        if preview is not None:
            return preview
        return FilePreviewState.with_message(
            IMAGE_PREVIEW_DEPENDENCY_MESSAGE,
            reason="dependency_missing",
        )

    if _is_pdf_preview_candidate(path):
        if not enable_pdf_preview:
            return FilePreviewState.unavailable()
        loader = pdf_preview_loader or HybridPdfPreviewLoader(
            resource_budget=resource_budget
        )
        preview = _call_preview_loader(
            loader,
            path,
            preview_max_bytes=preview_max_bytes,
            cancel_callback=cancel_callback,
        )
        if preview is not None:
            return preview
        return FilePreviewState.unsupported()

    if _is_office_preview_candidate(path):
        if not enable_office_preview:
            return FilePreviewState.unavailable()
        loader = document_preview_loader or OfficeDocumentPreviewLoader(
            resource_budget=resource_budget
        )
        preview = _call_preview_loader(
            loader,
            path,
            preview_max_bytes=preview_max_bytes,
            cancel_callback=cancel_callback,
        )
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
    if cancel_callback is not None and cancel_callback():
        return FilePreviewState.unavailable("cancelled")

    if b"\x00" in chunk[:preview_limit]:
        if _has_image_signature(path, header=chunk[:32]):
            if not enable_image_preview:
                return FilePreviewState.unavailable()
            loader = image_preview_loader or ChafaImagePreviewLoader(
                resource_budget=resource_budget
            )
            fmt = resolve_image_preview_format(image_preview_mode)
            preview = _call_preview_loader(
                loader,
                path,
                preview_columns=max(1, preview_columns),
                image_preview_format=fmt,
                cancel_callback=cancel_callback,
            )
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
            loader = image_preview_loader or ChafaImagePreviewLoader(
                resource_budget=resource_budget
            )
            fmt = resolve_image_preview_format(image_preview_mode)
            preview = _call_preview_loader(
                loader,
                path,
                preview_columns=max(1, preview_columns),
                image_preview_format=fmt,
                cancel_callback=cancel_callback,
            )
            if preview is not None:
                return preview
        return FilePreviewState.unsupported()

    return FilePreviewState.with_content(preview_text, truncated)


def _load_pdf_preview(
    path: Path,
    *,
    preview_max_bytes: int,
) -> FilePreviewState | None:
    return HybridPdfPreviewLoader().load_preview(
        path,
        preview_max_bytes=preview_max_bytes,
    )


def _load_grep_context_preview(
    path: Path,
    line_number: int,
    context_lines: int,
    *,
    preview_max_bytes: int = TEXT_PREVIEW_MAX_BYTES,
    cancel_callback: CancelCallback | None = None,
) -> ContextPreviewState:
    return _load_grep_context_window(
        path,
        line_number,
        context_lines,
        preview_max_bytes=preview_max_bytes,
        cancel_callback=cancel_callback,
    )[0]


def _build_grep_context_preview_from_window(
    window: GrepContextWindowState,
    line_number: int,
    context_lines: int,
) -> ContextPreviewState | None:
    start_line = max(1, line_number - max(0, context_lines))
    end_line = line_number + max(0, context_lines)
    if window.start_line > start_line:
        return None
    if window.end_line < line_number:
        return None
    if window.end_line < end_line and not window.hit_eof:
        return None

    offset = start_line - window.start_line
    count = min(end_line, window.end_line) - start_line + 1
    lines = window.lines[offset : offset + count]
    if len(lines) < count:
        return None

    return ContextPreviewState.with_content(
        "".join(lines),
        start_line=start_line,
        highlight_line=line_number,
    )


def _load_grep_context_window(
    path: Path,
    line_number: int,
    context_lines: int,
    *,
    preview_max_bytes: int = TEXT_PREVIEW_MAX_BYTES,
    lookahead_lines: int = DEFAULT_GREP_CONTEXT_WINDOW_LOOKAHEAD_LINES,
    cancel_callback: CancelCallback | None = None,
) -> tuple[ContextPreviewState, GrepContextWindowState | None]:
    preview_limit = max(1, preview_max_bytes)
    start_line = max(1, line_number - max(0, context_lines))
    end_line = line_number + max(0, context_lines)
    window_end_line = end_line + max(0, lookahead_lines)
    lines: list[str] = []
    last_line = 0
    bytes_read = 0
    current_line = 0

    try:
        with path.open("rb") as handle:
            while current_line < window_end_line:
                if cancel_callback is not None and cancel_callback():
                    return ContextPreviewState.with_message(PREVIEW_CANCELLED_MESSAGE), None
                line_bytes = handle.readline()
                if not line_bytes:
                    break

                bytes_read += len(line_bytes)
                current_line += 1

                if bytes_read <= preview_limit:
                    if b"\x00" in line_bytes:
                        return (
                            ContextPreviewState.with_message(PREVIEW_UNSUPPORTED_MESSAGE),
                            None,
                        )
                    try:
                        line_bytes.decode("utf-8")
                    except UnicodeDecodeError:
                        return (
                            ContextPreviewState.with_message(PREVIEW_UNSUPPORTED_MESSAGE),
                            None,
                        )

                if current_line >= start_line:
                    try:
                        line_text = _normalize_preview_newlines(line_bytes.decode("utf-8"))
                        lines.append(line_text)
                        last_line = current_line
                    except UnicodeDecodeError:
                        return (
                            ContextPreviewState.with_message(GREP_PREVIEW_ERROR_MESSAGE),
                            None,
                        )

    except PermissionError:
        return ContextPreviewState.with_message(PREVIEW_PERMISSION_DENIED_MESSAGE), None
    except OSError:
        return ContextPreviewState.with_message(GREP_PREVIEW_ERROR_MESSAGE), None

    if not lines or last_line < line_number:
        return ContextPreviewState.with_message(GREP_PREVIEW_ERROR_MESSAGE), None

    window = GrepContextWindowState(
        start_line=start_line,
        lines=tuple(lines),
        hit_eof=current_line < window_end_line,
    )
    preview = _build_grep_context_preview_from_window(
        window,
        line_number,
        context_lines,
    )
    if preview is None:
        preview = ContextPreviewState.with_message(GREP_PREVIEW_ERROR_MESSAGE)
    return preview, window


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


def _truncate_preview_text(
    content: str,
    preview_max_bytes: int,
    *,
    reason: str | None = None,
) -> FilePreviewState:
    preview_limit = max(1, preview_max_bytes)
    encoded = content.encode("utf-8")
    truncated = len(encoded) > preview_limit
    if not truncated:
        return FilePreviewState.with_content(content, False, reason=reason)

    preview_bytes = encoded[:preview_limit]
    preview_text = preview_bytes.decode("utf-8", errors="ignore")
    return FilePreviewState.with_content(preview_text, True, reason=reason)


def preview_max_bytes_from_kib(preview_max_kib: int) -> int:
    return max(1, preview_max_kib) * 1024
