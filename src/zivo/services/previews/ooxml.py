"""Bounded, standard-library OOXML text extraction for file previews.

This module deliberately has no dependency on preview/UI state.  It returns a
small result object which the preview service maps to ``FilePreviewState``.
"""

from __future__ import annotations

import posixpath
import time
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

CancelCallback = Callable[[], bool]

_OFFICE_RELATIONSHIPS_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
_R_ID = f"{{{_OFFICE_RELATIONSHIPS_NS}}}id"

RESOURCE_LIMIT_MESSAGE = "Preview stopped at a safety limit"
TIMEOUT_MESSAGE = "Preview stopped at a safety limit"
NO_TEXT_MESSAGE = "No extractable text found"
ENCRYPTED_MESSAGE = "Password-protected document"
CORRUPT_MESSAGE = "Document could not be read"


class PreviewResourceBudgetLike(Protocol):
    input_max_bytes: int
    max_archive_entries: int
    max_archive_entry_bytes: int
    max_archive_total_bytes: int
    max_archive_compression_ratio: float
    timeout_seconds: float


@dataclass(frozen=True)
class OoxmlPreviewResult:
    """Format-neutral result returned by the OOXML extractors."""

    content: str | None = None
    message: str | None = None
    truncated: bool = False
    reason: str | None = None


class _PreviewCancelled(Exception):
    pass


class _PreviewTimedOut(Exception):
    pass


class _PreviewResourceLimited(Exception):
    pass


class _PreviewCorrupt(Exception):
    pass


class _PreviewEncrypted(Exception):
    pass


class _OutputLimitReached(Exception):
    pass


@dataclass
class _OutputBuffer:
    max_bytes: int
    parts: list[str]
    size: int = 0

    def append(self, value: str) -> None:
        if not value:
            return
        encoded = value.encode("utf-8")
        remaining = self.max_bytes - self.size
        if len(encoded) <= remaining:
            self.parts.append(value)
            self.size += len(encoded)
            return
        if remaining > 0:
            partial = encoded[:remaining].decode("utf-8", errors="ignore")
            self.parts.append(partial)
            self.size += len(partial.encode("utf-8"))
        raise _OutputLimitReached(self.text())

    def text(self) -> str:
        return "".join(self.parts)


class _GuardedReader:
    """Bound a ZIP member read and reject XML declarations with entities."""

    def __init__(
        self,
        source,
        *,
        deadline: float,
        cancel_callback: CancelCallback | None,
    ) -> None:
        self._source = source
        self._deadline = deadline
        self._cancel_callback = cancel_callback
        self._scan_tail = b""

    def read(self, size: int = -1) -> bytes:
        self._check_limits()
        chunk = self._source.read(size)
        self._check_xml_declarations(chunk)
        return chunk

    def readline(self, size: int = -1) -> bytes:
        self._check_limits()
        chunk = self._source.readline(size)
        self._check_xml_declarations(chunk)
        return chunk

    def _check_limits(self) -> None:
        if self._cancel_callback is not None and self._cancel_callback():
            raise _PreviewCancelled
        if time.monotonic() > self._deadline:
            raise _PreviewTimedOut

    def _check_xml_declarations(self, chunk: bytes) -> None:
        if not chunk:
            return
        probe = (self._scan_tail + chunk).lower()
        if b"<!doctype" in probe or b"<!entity" in probe:
            raise _PreviewCorrupt
        self._scan_tail = probe[-16:]


def extract_ooxml_preview(
    path: Path,
    *,
    preview_max_bytes: int,
    resource_budget: PreviewResourceBudgetLike,
    cancel_callback: CancelCallback | None = None,
) -> OoxmlPreviewResult:
    """Extract bounded plain text from a DOCX, XLSX, or PPTX package."""

    if path.suffix.casefold() not in {".docx", ".xlsx", ".pptx"}:
        return OoxmlPreviewResult(
            message="Preview unavailable for this file type",
            reason="unsupported",
        )
    if cancel_callback is not None and cancel_callback():
        return OoxmlPreviewResult(reason="cancelled")
    try:
        if path.stat().st_size > resource_budget.input_max_bytes:
            return OoxmlPreviewResult(message=RESOURCE_LIMIT_MESSAGE, reason="resource_limit")
    except PermissionError:
        return OoxmlPreviewResult(
            message="Preview unavailable: permission denied",
            reason="permission_denied",
        )
    except OSError:
        return OoxmlPreviewResult(message="Preview unavailable", reason="error")

    deadline = time.monotonic() + max(0.001, resource_budget.timeout_seconds)
    try:
        with zipfile.ZipFile(path) as archive:
            infos = _validate_archive(archive, resource_budget, cancel_callback)
            members = {info.filename: info for info in infos}
            if path.suffix.casefold() == ".docx":
                content = _extract_docx(
                    archive, members, preview_max_bytes, deadline, cancel_callback
                )
            elif path.suffix.casefold() == ".xlsx":
                content = _extract_xlsx(
                    archive, members, preview_max_bytes, deadline, cancel_callback
                )
            else:
                content = _extract_pptx(
                    archive, members, preview_max_bytes, deadline, cancel_callback
                )
    except _PreviewCancelled:
        return OoxmlPreviewResult(reason="cancelled")
    except _PreviewTimedOut:
        return OoxmlPreviewResult(message=TIMEOUT_MESSAGE, reason="timeout")
    except _PreviewResourceLimited:
        return OoxmlPreviewResult(message=RESOURCE_LIMIT_MESSAGE, reason="resource_limit")
    except _OutputLimitReached as exc:
        return OoxmlPreviewResult(
            content=str(exc.args[0]) if exc.args else "",
            truncated=True,
            reason="resource_limit",
        )
    except _PreviewEncrypted:
        return OoxmlPreviewResult(message=ENCRYPTED_MESSAGE, reason="encrypted")
    except (_PreviewCorrupt, ET.ParseError, KeyError, IndexError, ValueError, TypeError):
        return OoxmlPreviewResult(message=CORRUPT_MESSAGE, reason="corrupt")
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError):
        return OoxmlPreviewResult(message=CORRUPT_MESSAGE, reason="corrupt")

    if not content.strip():
        return OoxmlPreviewResult(message=NO_TEXT_MESSAGE, reason="no_text_content")
    return OoxmlPreviewResult(content=content, truncated=False)


def _validate_archive(
    archive: zipfile.ZipFile,
    resource_budget: PreviewResourceBudgetLike,
    cancel_callback: CancelCallback | None,
) -> list[zipfile.ZipInfo]:
    infos = archive.infolist()
    if len(infos) > resource_budget.max_archive_entries:
        raise _PreviewResourceLimited
    total_size = 0
    seen: set[str] = set()
    for info in infos:
        if cancel_callback is not None and cancel_callback():
            raise _PreviewCancelled
        if _unsafe_member_name(info.filename):
            raise _PreviewCorrupt
        if info.filename in seen:
            raise _PreviewCorrupt
        seen.add(info.filename)
        if info.flag_bits & 0x1:
            raise _PreviewEncrypted
        entry_size = max(0, info.file_size)
        if entry_size > resource_budget.max_archive_entry_bytes:
            raise _PreviewResourceLimited
        total_size += entry_size
        if total_size > resource_budget.max_archive_total_bytes:
            raise _PreviewResourceLimited
        if (
            entry_size > 0
            and info.compress_size == 0
        ) or (
            info.compress_size > 0
            and entry_size / info.compress_size > resource_budget.max_archive_compression_ratio
        ):
            raise _PreviewResourceLimited
    return infos


def _unsafe_member_name(name: str) -> bool:
    if not name or "\\" in name or "\x00" in name:
        return True
    normalized = posixpath.normpath(name)
    return name.startswith("/") or normalized.startswith("../") or normalized == ".."


def _open_member(
    archive: zipfile.ZipFile,
    members: dict[str, zipfile.ZipInfo],
    name: str,
    *,
    deadline: float,
    cancel_callback: CancelCallback | None,
):
    info = members.get(name)
    if info is None:
        raise _PreviewCorrupt
    if info.flag_bits & 0x1:
        raise _PreviewEncrypted
    try:
        return _GuardedReader(
            archive.open(info),
            deadline=deadline,
            cancel_callback=cancel_callback,
        )
    except RuntimeError as exc:
        if "password" in str(exc).casefold() or "encrypted" in str(exc).casefold():
            raise _PreviewEncrypted from exc
        raise _PreviewCorrupt from exc


def _parse_member(
    archive: zipfile.ZipFile,
    members: dict[str, zipfile.ZipInfo],
    name: str,
    *,
    deadline: float,
    cancel_callback: CancelCallback | None,
) -> ET.Element:
    reader = _open_member(
        archive,
        members,
        name,
        deadline=deadline,
        cancel_callback=cancel_callback,
    )
    try:
        return ET.parse(reader).getroot()
    finally:
        reader._source.close()


def _iter_member(
    archive: zipfile.ZipFile,
    members: dict[str, zipfile.ZipInfo],
    name: str,
    *,
    deadline: float,
    cancel_callback: CancelCallback | None,
) -> Iterator[tuple[str, ET.Element]]:
    reader = _open_member(
        archive,
        members,
        name,
        deadline=deadline,
        cancel_callback=cancel_callback,
    )
    try:
        yield from ET.iterparse(reader, events=("start", "end"))
    finally:
        reader._source.close()


def _check_cancel_or_timeout(deadline: float, cancel_callback: CancelCallback | None) -> None:
    if cancel_callback is not None and cancel_callback():
        raise _PreviewCancelled
    if time.monotonic() > deadline:
        raise _PreviewTimedOut


def _extract_docx(
    archive: zipfile.ZipFile,
    members: dict[str, zipfile.ZipInfo],
    preview_max_bytes: int,
    deadline: float,
    cancel_callback: CancelCallback | None,
) -> str:
    output = _OutputBuffer(max(1, preview_max_bytes), [])
    p_stack: list[list[str]] = []
    cell_stack: list[list[str]] = []
    row_stack: list[list[str]] = []
    for event, element in _iter_member(
        archive,
        members,
        "word/document.xml",
        deadline=deadline,
        cancel_callback=cancel_callback,
    ):
        _check_cancel_or_timeout(deadline, cancel_callback)
        tag = element.tag
        if event == "start":
            if tag == f"{{{_W_NS}}}p":
                p_stack.append([])
            elif tag == f"{{{_W_NS}}}tc":
                cell_stack.append([])
            elif tag == f"{{{_W_NS}}}tr":
                row_stack.append([])
            continue
        if tag == f"{{{_W_NS}}}t" and p_stack:
            p_stack[-1].append(element.text or "")
        elif tag in {f"{{{_W_NS}}}tab", f"{{{_W_NS}}}br", f"{{{_W_NS}}}cr"} and p_stack:
            p_stack[-1].append("\t" if tag == f"{{{_W_NS}}}tab" else "\n")
        elif tag == f"{{{_W_NS}}}p" and p_stack:
            paragraph = "".join(p_stack.pop())
            if cell_stack:
                cell_stack[-1].append(paragraph)
            else:
                output.append(paragraph + "\n")
        elif tag == f"{{{_W_NS}}}tc" and cell_stack:
            cell = "\n".join(cell_stack.pop())
            if row_stack:
                row_stack[-1].append(cell)
        elif tag == f"{{{_W_NS}}}tr" and row_stack:
            output.append(" | ".join(row_stack.pop()) + "\n")
        element.clear()
    return output.text()


def _extract_xlsx(
    archive: zipfile.ZipFile,
    members: dict[str, zipfile.ZipInfo],
    preview_max_bytes: int,
    deadline: float,
    cancel_callback: CancelCallback | None,
) -> str:
    shared_strings = _read_shared_strings(archive, members, deadline, cancel_callback)
    workbook = _parse_member(
        archive,
        members,
        "xl/workbook.xml",
        deadline=deadline,
        cancel_callback=cancel_callback,
    )
    relationships = _read_relationships(
        archive,
        members,
        "xl/_rels/workbook.xml.rels",
        deadline=deadline,
        cancel_callback=cancel_callback,
    )
    output = _OutputBuffer(max(1, preview_max_bytes), [])
    sheet_count = 0
    for sheet in workbook.iter():
        _check_cancel_or_timeout(deadline, cancel_callback)
        if _local_name(sheet.tag) != "sheet":
            continue
        sheet_count += 1
        sheet_name = sheet.attrib.get("name", f"Sheet {sheet_count}")
        relationship_id = next(
            (value for key, value in sheet.attrib.items() if _local_name(key) == "id"),
            None,
        )
        if not relationship_id or relationship_id not in relationships:
            raise _PreviewCorrupt
        target = _resolve_target("xl/workbook.xml", relationships[relationship_id])
        if not target.startswith("xl/") or target not in members:
            raise _PreviewCorrupt
        output.append(f"[Sheet: {sheet_name}]\n")
        _append_worksheet(
            output,
            archive,
            members,
            target,
            shared_strings,
            deadline,
            cancel_callback,
        )
    if sheet_count == 0:
        raise _PreviewCorrupt
    return output.text()


def _read_shared_strings(
    archive: zipfile.ZipFile,
    members: dict[str, zipfile.ZipInfo],
    deadline: float,
    cancel_callback: CancelCallback | None,
) -> list[str]:
    if "xl/sharedStrings.xml" not in members:
        return []
    values: list[str] = []
    parts: list[str] = []
    for event, element in _iter_member(
        archive,
        members,
        "xl/sharedStrings.xml",
        deadline=deadline,
        cancel_callback=cancel_callback,
    ):
        _check_cancel_or_timeout(deadline, cancel_callback)
        tag = _local_name(element.tag)
        if event == "end" and tag == "t":
            parts.append(element.text or "")
        elif event == "end" and tag == "si":
            values.append("".join(parts))
            parts.clear()
        if event == "end":
            element.clear()
    return values


def _append_worksheet(
    output: _OutputBuffer,
    archive: zipfile.ZipFile,
    members: dict[str, zipfile.ZipInfo],
    target: str,
    shared_strings: list[str],
    deadline: float,
    cancel_callback: CancelCallback | None,
) -> None:
    cell_type: str | None = None
    cell_ref: str | None = None
    formula: str | None = None
    value: str | None = None
    inline_parts: list[str] = []
    for event, element in _iter_member(
        archive,
        members,
        target,
        deadline=deadline,
        cancel_callback=cancel_callback,
    ):
        _check_cancel_or_timeout(deadline, cancel_callback)
        tag = _local_name(element.tag)
        if event == "start" and tag == "c":
            cell_ref = element.attrib.get("r")
            cell_type = element.attrib.get("t")
            formula = None
            value = None
            inline_parts = []
        elif event == "end" and tag == "f":
            formula = "".join(element.itertext())
        elif event == "end" and tag == "v":
            value = "".join(element.itertext())
        elif event == "end" and tag == "t" and cell_type == "inlineStr":
            inline_parts.append(element.text or "")
        elif event == "end" and tag == "c":
            if cell_ref is not None:
                display = _cell_display_value(
                    cell_type, value, formula, inline_parts, shared_strings
                )
                if display:
                    output.append(f"{cell_ref} = {display}\n")
            cell_ref = None
            cell_type = None
            formula = None
            value = None
            inline_parts = []
        if event == "end":
            element.clear()


def _cell_display_value(
    cell_type: str | None,
    value: str | None,
    formula: str | None,
    inline_parts: list[str],
    shared_strings: list[str],
) -> str:
    if cell_type == "s":
        if value is None or not value.strip():
            return ""
        index = int(value)
        if index < 0 or index >= len(shared_strings):
            raise _PreviewCorrupt
        display = shared_strings[index]
    elif cell_type == "inlineStr":
        display = "".join(inline_parts)
    else:
        display = value or ""
    if formula:
        formula_display = f"={formula}"
        return f"{formula_display} (cached: {display})" if display else formula_display
    return display


def _extract_pptx(
    archive: zipfile.ZipFile,
    members: dict[str, zipfile.ZipInfo],
    preview_max_bytes: int,
    deadline: float,
    cancel_callback: CancelCallback | None,
) -> str:
    presentation = _parse_member(
        archive,
        members,
        "ppt/presentation.xml",
        deadline=deadline,
        cancel_callback=cancel_callback,
    )
    relationships = _read_relationships(
        archive,
        members,
        "ppt/_rels/presentation.xml.rels",
        deadline=deadline,
        cancel_callback=cancel_callback,
    )
    output = _OutputBuffer(max(1, preview_max_bytes), [])
    slide_count = 0
    for slide_id in presentation.iter():
        _check_cancel_or_timeout(deadline, cancel_callback)
        if _local_name(slide_id.tag) != "sldId":
            continue
        slide_count += 1
        relationship_id = slide_id.attrib.get(_R_ID) or next(
            (value for key, value in slide_id.attrib.items() if _local_name(key) == "id"),
            None,
        )
        if not relationship_id or relationship_id not in relationships:
            raise _PreviewCorrupt
        target = _resolve_target("ppt/presentation.xml", relationships[relationship_id])
        if not target.startswith("ppt/") or target not in members:
            raise _PreviewCorrupt
        output.append(f"[Slide {slide_count}]\n")
        _append_slide(output, archive, members, target, deadline, cancel_callback)
    if slide_count == 0:
        raise _PreviewCorrupt
    return output.text()


def _append_slide(
    output: _OutputBuffer,
    archive: zipfile.ZipFile,
    members: dict[str, zipfile.ZipInfo],
    target: str,
    deadline: float,
    cancel_callback: CancelCallback | None,
) -> None:
    paragraph: list[str] = []
    for event, element in _iter_member(
        archive,
        members,
        target,
        deadline=deadline,
        cancel_callback=cancel_callback,
    ):
        _check_cancel_or_timeout(deadline, cancel_callback)
        tag = element.tag
        if event == "start" and tag == f"{{{_A_NS}}}p":
            paragraph = []
        elif event == "end" and tag == f"{{{_A_NS}}}t":
            paragraph.append(element.text or "")
        elif event == "end" and tag == f"{{{_A_NS}}}p":
            output.append("".join(paragraph) + "\n")
            paragraph = []
        if event == "end":
            element.clear()


def _read_relationships(
    archive: zipfile.ZipFile,
    members: dict[str, zipfile.ZipInfo],
    name: str,
    *,
    deadline: float,
    cancel_callback: CancelCallback | None,
) -> dict[str, str]:
    root = _parse_member(
        archive,
        members,
        name,
        deadline=deadline,
        cancel_callback=cancel_callback,
    )
    relationships: dict[str, str] = {}
    for relationship in root:
        if _local_name(relationship.tag) != "Relationship":
            continue
        relationship_id = relationship.attrib.get("Id")
        target = relationship.attrib.get("Target")
        if relationship_id and target:
            relationships[relationship_id] = target
    return relationships


def _resolve_target(source: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join(posixpath.dirname(source), target))


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
