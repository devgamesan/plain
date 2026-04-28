"""Helpers for platform-specific feature availability."""

from __future__ import annotations

import os
import platform


def is_native_windows() -> bool:
    """Return True when running on native Windows."""

    return platform.system() == "Windows"


def is_split_terminal_supported() -> bool:
    """Return whether the embedded split terminal is supported here."""

    return os.name == "posix" and not is_native_windows()


def split_terminal_unavailable_message() -> str:
    """Return a user-facing split-terminal availability message."""

    if is_native_windows():
        return "Split terminal is not available on native Windows"
    return "Split terminal is not available on this platform"
