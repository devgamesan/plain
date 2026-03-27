"""CLI entrypoint for Peneo."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from .app import create_app


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

    app = create_app()
    app.run()

    if args.print_last_dir:
        target_path = app.return_value or app.app_state.current_path
        sys.stdout.write(f"{target_path}\n")

    return app.return_code


if __name__ == "__main__":
    raise SystemExit(main())
