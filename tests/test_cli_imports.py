"""Verify non-TUI commands avoid heavy imports."""

import subprocess
import sys


def test_init_command_does_not_import_textual() -> None:
    """zivo init bash should not import textual or pygments."""
    script = (
        "import sys; "
        "from zivo.__main__ import main; "
        "main(['init', 'bash']); "
        "assert 'textual' not in sys.modules, "
        "'textual was imported during init command'; "
        "assert 'pygments' not in sys.modules, "
        "'pygments was imported during init command'"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"init command failed or imported heavy deps.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "zivo-cd()" in result.stdout
