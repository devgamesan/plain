from pathlib import Path

import pytest

from peneo.services import LiveShellCommandService


def test_live_shell_command_service_executes_in_cwd(tmp_path: Path) -> None:
    service = LiveShellCommandService(shell="/bin/sh")

    result = service.execute(cwd=str(tmp_path), command="pwd")

    assert result.exit_code == 0
    assert result.stdout.strip() == str(tmp_path.resolve())
    assert result.stderr == ""


def test_live_shell_command_service_captures_nonzero_exit_and_stderr(tmp_path: Path) -> None:
    service = LiveShellCommandService(shell="/bin/sh")

    result = service.execute(cwd=str(tmp_path), command="printf boom >&2; exit 7")

    assert result.exit_code == 7
    assert result.stdout == ""
    assert result.stderr == "boom"


def test_live_shell_command_service_rejects_missing_directory(tmp_path: Path) -> None:
    service = LiveShellCommandService(shell="/bin/sh")

    with pytest.raises(OSError, match="Shell command requires a directory"):
        service.execute(cwd=str(tmp_path / "missing"), command="pwd")
