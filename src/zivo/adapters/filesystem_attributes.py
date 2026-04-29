"""Internal helpers for OS-aware filesystem attribute resolution."""

from __future__ import annotations

import os
import platform
from collections.abc import Callable
from functools import lru_cache
from typing import Protocol

from zivo.adapters.platforms.base import is_wsl_environment

EnvironmentVariableReader = Callable[[str], str | None]
TextFileReader = Callable[[str], str]


class FileAttributeResolver(Protocol):
    """Resolve optional owner/group names for a filesystem stat result."""

    def resolve_owner_group(self, stat_result: os.stat_result) -> tuple[str | None, str | None]: ...


class NullFileAttributeResolver:
    """Return no owner/group details on platforms without supported lookup."""

    def resolve_owner_group(self, stat_result: os.stat_result) -> tuple[str | None, str | None]:
        return (None, None)


class UnixFileAttributeResolver:
    """Resolve owner/group names with Unix account databases when available."""

    def resolve_owner_group(self, stat_result: os.stat_result) -> tuple[str | None, str | None]:
        uid = getattr(stat_result, "st_uid", None)
        gid = getattr(stat_result, "st_gid", None)
        return (_resolve_user_name(uid), _resolve_group_name(gid))


def resolve_owner_group(
    stat_result: os.stat_result,
    *,
    system_name: str | None = None,
    environment_variable: EnvironmentVariableReader = os.environ.get,
    text_file_reader: TextFileReader | None = None,
) -> tuple[str | None, str | None]:
    """Return best-effort owner/group names for the current environment."""

    return _select_file_attribute_resolver(
        system_name or platform.system(),
        environment_variable=environment_variable,
        text_file_reader=text_file_reader or _read_text_file,
    ).resolve_owner_group(stat_result)


@lru_cache(maxsize=None)
def _select_file_attribute_resolver(
    system_name: str,
    *,
    environment_variable: EnvironmentVariableReader,
    text_file_reader: TextFileReader,
) -> FileAttributeResolver:
    if system_name == "Windows":
        return NullFileAttributeResolver()
    if system_name == "Linux" and is_wsl_environment(environment_variable, text_file_reader):
        return UnixFileAttributeResolver()
    if system_name in {"Linux", "Darwin"}:
        return UnixFileAttributeResolver()
    return NullFileAttributeResolver()


def _read_text_file(path: str) -> str:
    return open(path, encoding="utf-8").read()


@lru_cache(maxsize=256)
def _resolve_user_name(uid: int | None) -> str | None:
    if uid is None:
        return None
    try:
        import pwd
    except ImportError:
        return None
    try:
        return pwd.getpwuid(uid).pw_name
    except (KeyError, OSError):
        return None


@lru_cache(maxsize=256)
def _resolve_group_name(gid: int | None) -> str | None:
    if gid is None:
        return None
    try:
        import grp
    except ImportError:
        return None
    try:
        return grp.getgrgid(gid).gr_name
    except (KeyError, OSError):
        return None
