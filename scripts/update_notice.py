"""Regenerate NOTICE.txt from the frozen production dependency set."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run(*args: str, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=capture_output,
        text=True,
    )


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="zivo-notice-") as temporary_directory:
        temporary_root = Path(temporary_directory)
        requirements = temporary_root / "production-requirements.txt"
        production_environment = temporary_root / "production-venv"

        run(
            "uv",
            "export",
            "--frozen",
            "--no-dev",
            "--no-emit-project",
            "--format",
            "requirements.txt",
            "--output-file",
            str(requirements),
            capture_output=True,
        )
        run("uv", "venv", "--python", sys.executable, str(production_environment))

        python_name = "python.exe" if os.name == "nt" else "python"
        python_directory = "Scripts" if os.name == "nt" else "bin"
        production_python = production_environment / python_directory / python_name
        run(
            "uv",
            "pip",
            "install",
            "--python",
            str(production_python),
            "--requirement",
            str(requirements),
        )

        result = run(
            "uv",
            "run",
            "--locked",
            "--no-sync",
            "pip-licenses",
            "--python",
            str(production_python),
            "--format=plain",
            "--from=mixed",
            "--with-urls",
            capture_output=True,
        )

    notice = "\n".join(line.rstrip() for line in result.stdout.splitlines()) + "\n"
    (PROJECT_ROOT / "NOTICE.txt").write_text(notice, encoding="utf-8")


if __name__ == "__main__":
    main()
