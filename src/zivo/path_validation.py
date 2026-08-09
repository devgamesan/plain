"""Cross-platform filesystem entry-name validation helpers."""

import os
import platform

MAX_PATH_SEGMENT_BYTES = 255


def validate_path_segment(segment: str, *, is_macos: bool | None = None) -> str | None:
    """Return a user-facing validation error for one path segment."""

    if not segment:
        return "Name cannot be empty"
    if "\x00" in segment:
        return "Names cannot include null characters"
    if len(segment.encode("utf-8")) > MAX_PATH_SEGMENT_BYTES:
        return f"Path segment exceeds maximum length of {MAX_PATH_SEGMENT_BYTES} bytes"
    if is_macos is None:
        is_macos = os.name == "posix" and platform.system() == "Darwin"
    if is_macos and ":" in segment:
        return "Names cannot include colons"
    if os.name == "nt":
        if any(char in '<>:"/\\|?*' for char in segment) or segment.endswith((" ", ".")):
            return f"Invalid path segment '{segment}'"
        stem = segment.split(".", 1)[0].upper()
        reserved_names = {
            "CON",
            "PRN",
            "AUX",
            "NUL",
            *(f"COM{index}" for index in range(1, 10)),
            *(f"LPT{index}" for index in range(1, 10)),
        }
        if stem in reserved_names:
            return f"Reserved path segment '{segment}'"
    return None
