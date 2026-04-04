"""Logging setup for file-based crash investigation."""

from __future__ import annotations

import logging
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Callable

from peneo.models import LoggingConfig

from .config import resolve_config_path

DefaultLogPathResolver = Callable[[str], Path]
_HANDLER_NAME = "peneo-file-handler"
_ACTIVE_LOGGER_NAME = "peneo"
_HOOKS_INSTALLED = False
_ORIGINAL_SYS_EXCEPTHOOK = sys.excepthook
_ORIGINAL_THREADING_EXCEPTHOOK = threading.excepthook


@dataclass(frozen=True)
class LoggingSetupResult:
    """Outcome of the startup logging setup."""

    enabled: bool
    path: str = ""
    warning: str = ""


def configure_file_logging(
    *,
    config: LoggingConfig,
    config_path: str,
    logger_name: str = "peneo",
    default_log_path_resolver: DefaultLogPathResolver | None = None,
) -> LoggingSetupResult:
    """Configure file logging for startup and unhandled exceptions."""

    logger = logging.getLogger(logger_name)
    _set_active_logger_name(logger_name)
    if not config.enabled:
        _remove_managed_handlers(logger)
        _install_exception_hooks()
        return LoggingSetupResult(enabled=False)

    log_path = _resolve_log_path(
        config.path,
        config_path=config_path,
        resolver=default_log_path_resolver or resolve_default_log_path,
    )
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(log_path, encoding="utf-8")
    except OSError as error:
        return LoggingSetupResult(
            enabled=False,
            warning=f"Failed to initialize log file output: {error}",
        )

    handler.set_name(_HANDLER_NAME)
    handler.setLevel(logging.ERROR)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    _replace_managed_handlers(logger, handler)
    logger.setLevel(logging.ERROR)
    logger.propagate = False
    _install_exception_hooks()
    return LoggingSetupResult(enabled=True, path=str(log_path))


def resolve_default_log_path(config_path: str) -> Path:
    """Resolve the default log path next to the config file."""

    if config_path.strip():
        return Path(config_path).expanduser().parent / "peneo.log"
    return resolve_config_path().parent / "peneo.log"


def _resolve_log_path(
    configured_path: str | None,
    *,
    config_path: str,
    resolver: DefaultLogPathResolver,
) -> Path:
    if configured_path:
        return Path(configured_path).expanduser()
    return resolver(config_path)


def _replace_managed_handlers(logger: logging.Logger, handler: logging.Handler) -> None:
    _remove_managed_handlers(logger)
    logger.addHandler(handler)


def _remove_managed_handlers(logger: logging.Logger) -> None:
    removable = [handler for handler in logger.handlers if handler.get_name() == _HANDLER_NAME]
    for handler in removable:
        logger.removeHandler(handler)
        handler.close()


def _set_active_logger_name(logger_name: str) -> None:
    global _ACTIVE_LOGGER_NAME
    _ACTIVE_LOGGER_NAME = logger_name


def _install_exception_hooks() -> None:
    global _HOOKS_INSTALLED
    if _HOOKS_INSTALLED:
        return
    sys.excepthook = _log_sys_exception
    threading.excepthook = _log_thread_exception
    _HOOKS_INSTALLED = True


def _log_sys_exception(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_traceback: TracebackType | None,
) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        _ORIGINAL_SYS_EXCEPTHOOK(exc_type, exc_value, exc_traceback)
        return
    logging.getLogger(_ACTIVE_LOGGER_NAME).error(
        "Unhandled exception",
        exc_info=(exc_type, exc_value, exc_traceback),
    )
    _ORIGINAL_SYS_EXCEPTHOOK(exc_type, exc_value, exc_traceback)


def _log_thread_exception(args: threading.ExceptHookArgs) -> None:
    if issubclass(args.exc_type, KeyboardInterrupt):
        _ORIGINAL_THREADING_EXCEPTHOOK(args)
        return
    logging.getLogger(_ACTIVE_LOGGER_NAME).error(
        "Unhandled thread exception",
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
    )
    _ORIGINAL_THREADING_EXCEPTHOOK(args)
