"""CLI entrypoint for zivo."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import IO, TYPE_CHECKING, Iterator

if TYPE_CHECKING:
    from .state import NotificationState


@dataclass(frozen=True)
class _StandardStreams:
    stdin: IO[str]
    stdout: IO[str]
    stderr: IO[str]


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""

    parser = argparse.ArgumentParser(prog="zivo")
    parser.add_argument(
        "--print-last-dir",
        action="store_true",
        help="print the last visited directory after the TUI exits",
    )
    subparsers = parser.add_subparsers(dest="command")
    init_parser = subparsers.add_parser("init", help="print shell integration snippets")
    init_parser.add_argument("shell", choices=("bash", "zsh"))
    return parser


def render_shell_init(shell: str) -> str:
    """Return shell integration for the requested shell."""

    if shell not in {"bash", "zsh"}:
        raise ValueError(f"Unsupported shell: {shell}")
    return (
        "zivo-cd() {\n"
        "  local target status\n"
        '  target="$(command zivo --print-last-dir "$@")"\n'
        "  status=$?\n"
        "  if [ $status -ne 0 ]; then\n"
        "    return $status\n"
        "  fi\n"
        '  if [ -n "$target" ]; then\n'
        '    builtin cd -- "$target"\n'
        "  fi\n"
        "}\n"
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Textual app or print shell integration."""

    args = build_parser().parse_args(argv)
    if args.command == "init":
        sys.stdout.write(render_shell_init(args.shell))
        return 0

    from .app import create_app
    from .services import configure_file_logging, load_app_config

    config_result = load_app_config()
    logging_result = configure_file_logging(
        config=config_result.config.logging,
        config_path=config_result.path,
    )
    startup_notification = _startup_notification(
        config_result.warnings,
        logging_result.warning,
    )

    logger = _app_logger()
    try:
        with _shell_integration_stdio(args.print_last_dir):
            app = create_app(
                app_config=config_result.config,
                config_path=config_result.path,
                startup_notification=startup_notification,
            )
            app.run(mouse=False)
    except Exception:
        logger.exception("zivo crashed during startup or runtime")
        raise

    if args.print_last_dir:
        target_path = app.return_value or app.app_state.current_path
        sys.stdout.write(f"{target_path}\n")

    return app.return_code


def _startup_notification(
    config_warnings: tuple[str, ...],
    logging_warning: str = "",
) -> NotificationState | None:
    from .state import NotificationState

    messages = list(config_warnings)
    if logging_warning:
        messages.append(logging_warning)
    if not messages:
        return None
    return NotificationState(level="warning", message="Startup warnings: " + "; ".join(messages))


def _app_logger() -> logging.Logger:
    return logging.getLogger("zivo")


def _capture_standard_streams() -> _StandardStreams:
    return _StandardStreams(
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )


def _install_standard_streams(streams: _StandardStreams) -> None:
    sys.stdin = streams.stdin
    sys.stdout = streams.stdout
    sys.stderr = streams.stderr
    sys.__stdin__ = streams.stdin
    sys.__stdout__ = streams.stdout
    sys.__stderr__ = streams.stderr


def _should_use_tty_streams(print_last_dir: bool) -> bool:
    return print_last_dir and not sys.stdout.isatty() and sys.stderr.isatty()


def _open_tty_streams() -> _StandardStreams:
    return _StandardStreams(
        stdin=open("/dev/tty", encoding="utf-8"),
        stdout=open("/dev/tty", "w", encoding="utf-8", buffering=1),
        stderr=open("/dev/tty", "w", encoding="utf-8", buffering=1),
    )


def _close_standard_streams(streams: _StandardStreams) -> None:
    for stream in (streams.stdin, streams.stdout, streams.stderr):
        stream.close()


@contextmanager
def _shell_integration_stdio(print_last_dir: bool) -> Iterator[None]:
    if not _should_use_tty_streams(print_last_dir):
        yield
        return

    try:
        tty_streams = _open_tty_streams()
    except OSError:
        yield
        return

    original_streams = _capture_standard_streams()
    try:
        _install_standard_streams(tty_streams)
        yield
    finally:
        _install_standard_streams(original_streams)
        _close_standard_streams(tty_streams)


if __name__ == "__main__":
    raise SystemExit(main())
