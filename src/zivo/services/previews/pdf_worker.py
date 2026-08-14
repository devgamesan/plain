"""Bounded pypdf worker used by the PDF preview service.

The worker is intentionally a separate process.  A malformed or unusually
large content stream must not be able to block the Textual worker that owns
the browser snapshot.  The parent process supplies the timeout and terminates
this worker when the request is stale or exceeds its wall-clock budget.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _configure_limits(max_content_stream_bytes: int) -> None:
    from pypdf import filters
    from pypdf.generic import _data_structures

    for name in (
        "MAX_DECLARED_STREAM_LENGTH",
        "MAX_ARRAY_BASED_STREAM_OUTPUT_LENGTH",
        "ZLIB_MAX_OUTPUT_LENGTH",
        "ZLIB_MAX_BUFFER_SIZE",
        "LZW_MAX_OUTPUT_LENGTH",
        "RUN_LENGTH_MAX_OUTPUT_LENGTH",
    ):
        if hasattr(filters, name):
            setattr(filters, name, min(getattr(filters, name), max_content_stream_bytes))
    _data_structures.CONTENT_STREAM_ARRAY_MAX_LENGTH = min(
        _data_structures.CONTENT_STREAM_ARRAY_MAX_LENGTH,
        4096,
    )


def _append_page_text(
    output: str,
    page_number: int,
    page_text: str,
    max_output_bytes: int,
) -> tuple[str, bool]:
    prefix = f"--- Page {page_number} ---\n"
    candidate = output + prefix + page_text
    if len(candidate.encode("utf-8")) <= max_output_bytes:
        return candidate, False
    remaining = max_output_bytes - len(output.encode("utf-8"))
    if remaining <= 0:
        return output, True
    prefix_bytes = prefix.encode("utf-8")
    text_budget = remaining - len(prefix_bytes)
    if text_budget <= 0:
        return output, True
    text_bytes = page_text.encode("utf-8")[:text_budget]
    partial = text_bytes.decode("utf-8", errors="ignore")
    return output + prefix + partial, True


def extract_pdf(
    path: Path,
    *,
    max_pages: int,
    max_output_bytes: int,
    max_content_stream_bytes: int,
) -> dict[str, Any]:
    try:
        from pypdf import PdfReader
    except ImportError:
        return {"reason": "dependency_missing"}

    _configure_limits(max_content_stream_bytes)
    try:
        reader = PdfReader(path, strict=False)
        if reader.is_encrypted:
            return {"reason": "encrypted"}
        output = ""
        has_text = False
        for page_number, page in enumerate(reader.pages, start=1):
            if page_number > max_pages:
                return {"reason": "resource_limit", "content": output, "truncated": True}
            page_text = page.extract_text() or ""
            if page_text.strip():
                has_text = True
            output, truncated = _append_page_text(
                output,
                page_number,
                page_text,
                max_output_bytes,
            )
            if truncated:
                return {"reason": "resource_limit", "content": output, "truncated": True}
        if not has_text:
            return {"reason": "no_text_content"}
        return {"reason": "success", "content": output, "truncated": False}
    except PermissionError:
        return {"reason": "permission_denied"}
    except Exception as error:  # noqa: BLE001 - PDF parsers expose varied error types
        if type(error).__name__ == "LimitReachedError":
            return {"reason": "resource_limit"}
        return {"reason": "corrupt", "error": type(error).__name__}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--max-pages", type=int, required=True)
    parser.add_argument("--max-output-bytes", type=int, required=True)
    parser.add_argument("--max-content-stream-bytes", type=int, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            extract_pdf(
                args.path,
                max_pages=max(1, args.max_pages),
                max_output_bytes=max(1, args.max_output_bytes),
                max_content_stream_bytes=max(1, args.max_content_stream_bytes),
            ),
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
