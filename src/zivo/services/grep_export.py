"""Grep results export services."""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from zivo.state.models import GrepSearchResultState


class GrepExportService(Protocol):
    """Boundary for exporting grep search results to a file."""

    def export(
        self,
        *,
        output_path: str,
        context_lines: int,
        results: tuple[GrepSearchResultState, ...],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> str: ...


@dataclass(frozen=True)
class LiveGrepExportService:
    """Export grep results to a text file with configured context lines."""

    encoding: str = "utf-8"
    fallback_encoding: str = "latin-1"

    def export(
        self,
        *,
        output_path: str,
        context_lines: int,
        results: tuple[GrepSearchResultState, ...],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> str:
        output = Path(output_path).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)

        total = len(results)
        content = self._format_context(results, context_lines)

        if progress_callback:
            progress_callback(total, total)

        output.write_text(content, encoding=self.encoding)
        return str(output)

    def _format_context(
        self, results: tuple[GrepSearchResultState, ...], context_lines: int
    ) -> str:
        chunks: list[str] = []
        for result in results:
            window = self._read_context_window(result.path, result.line_number, context_lines)
            chunks.append(f"{result.display_path}:{result.line_number}: {result.line_text}")
            if window:
                for line in window:
                    chunks.append(line)
            chunks.append("")
        return "\n".join(chunks).rstrip("\n") + ("\n" if results else "")

    def _read_context_window(
        self, file_path: str, line_number: int, context_lines: int
    ) -> list[str]:
        try:
            content = self._read_file_safely(file_path)
        except OSError:
            return []

        lines = content.splitlines()
        start = max(0, line_number - context_lines - 1)
        end = min(len(lines), line_number + context_lines)
        return [f"{i + 1}: {lines[i]}" for i in range(start, end) if i >= 0 and i < len(lines)]

    def _read_file_safely(self, path: str) -> str:
        try:
            return Path(path).read_text(encoding=self.encoding)
        except (UnicodeDecodeError, OSError):
            try:
                return Path(path).read_text(encoding=self.fallback_encoding)
            except (UnicodeDecodeError, OSError):
                raise OSError(f"Cannot read file: {path}")


@dataclass
class FakeGrepExportService:
    """Deterministic grep export service used by tests."""

    exported: list[dict] = field(default_factory=list)
    failure_message: str | None = None

    def export(
        self,
        *,
        output_path: str,
        context_lines: int,
        results: tuple[GrepSearchResultState, ...],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> str:
        if self.failure_message:
            raise OSError(self.failure_message)
        self.exported.append(
            {
                "output_path": output_path,
                "context_lines": context_lines,
                "result_count": len(results),
            }
        )
        return output_path
