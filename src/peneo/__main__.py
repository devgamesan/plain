"""CLI entrypoint for Peneo."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence

from .app import create_app
from .services import configure_file_logging, load_app_config
from .state import NotificationState


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""

    parser = argparse.ArgumentParser(prog="peneo")
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
        "peneo-cd() {\n"
        "  local target status\n"
        '  target="$(command peneo --print-last-dir "$@")"\n'
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
        app = create_app(
            app_config=config_result.config,
            config_path=config_result.path,
            startup_notification=startup_notification,
        )
        app.run(mouse=False)
    except Exception:
        logger.exception("Peneo crashed during startup or runtime")
        raise

    if args.print_last_dir:
        target_path = app.return_value or app.app_state.current_path
        sys.stdout.write(f"{target_path}\n")

    return app.return_code


def _startup_notification(
    config_warnings: tuple[str, ...],
    logging_warning: str = "",
) -> NotificationState | None:
    messages = list(config_warnings)
    if logging_warning:
        messages.append(logging_warning)
    if not messages:
        return None
    return NotificationState(level="warning", message="Startup warnings: " + "; ".join(messages))


def _app_logger() -> logging.Logger:
    return logging.getLogger("peneo")


if __name__ == "__main__":
    raise SystemExit(main())
