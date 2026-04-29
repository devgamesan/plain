import os
from pathlib import Path

import pytest

from zivo.services import LiveShellCommandService


def test_live_shell_command_service_executes_in_cwd(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_run(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return type(
            "Completed",
            (),
            {"returncode": 0, "stdout": f"{tmp_path.resolve()}\n", "stderr": ""},
        )()

    monkeypatch.setattr("zivo.services.shell_command.subprocess.run", fake_run)
    service = LiveShellCommandService(shell="/bin/sh", os_name="posix")

    result = service.execute(cwd=str(tmp_path), command="pwd")

    assert result.exit_code == 0
    assert result.stdout.strip() == str(tmp_path.resolve())
    assert result.stderr == ""
    assert captured["args"] == (["/bin/sh", "-lc", "pwd"],)
    assert captured["kwargs"]["cwd"] == str(tmp_path.resolve())


def test_live_shell_command_service_captures_nonzero_exit_and_stderr(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_run(*args, **kwargs):
        return type(
            "Completed",
            (),
            {"returncode": 7, "stdout": "", "stderr": "boom"},
        )()

    monkeypatch.setattr("zivo.services.shell_command.subprocess.run", fake_run)
    service = LiveShellCommandService(shell="/bin/sh", os_name="posix")

    result = service.execute(cwd=str(tmp_path), command="printf boom >&2; exit 7")

    assert result.exit_code == 7
    assert result.stdout == ""
    assert result.stderr == "boom"


def test_live_shell_command_service_rejects_missing_directory(tmp_path: Path) -> None:
    service = LiveShellCommandService(shell="/bin/sh", os_name="posix")

    with pytest.raises(OSError, match="Shell command requires a directory"):
        service.execute(cwd=str(tmp_path / "missing"), command="pwd")


@pytest.mark.skipif(os.name != "nt", reason="Windows-only shell selection test")
def test_live_shell_command_service_uses_powershell_on_windows(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_run(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return type(
            "Completed",
            (),
            {"returncode": 0, "stdout": "done\n", "stderr": ""},
        )()

    monkeypatch.setattr("zivo.services.shell_command.subprocess.run", fake_run)
    service = LiveShellCommandService(
        os_name="nt",
        command_available=lambda command: command if command == "powershell.exe" else None,
    )

    result = service.execute(cwd=str(tmp_path), command="Get-Location")

    assert result.exit_code == 0
    assert captured["args"] == (["powershell.exe", "-NoProfile", "-Command", "Get-Location"],)


@pytest.mark.skipif(os.name != "nt", reason="Windows-only shell selection test")
def test_live_shell_command_service_falls_back_to_pwsh_on_windows(
    monkeypatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    def fake_run(*args, **kwargs):
        captured["args"] = args
        return type(
            "Completed",
            (),
            {"returncode": 0, "stdout": "", "stderr": ""},
        )()

    monkeypatch.setattr("zivo.services.shell_command.subprocess.run", fake_run)
    service = LiveShellCommandService(
        os_name="nt",
        command_available=lambda command: command if command == "pwsh" else None,
    )

    service.execute(cwd=str(tmp_path), command="Get-ChildItem")

    assert captured["args"] == (["pwsh", "-NoProfile", "-Command", "Get-ChildItem"],)


@pytest.mark.skipif(os.name != "nt", reason="Windows-only shell selection test")
def test_live_shell_command_service_falls_back_to_cmd_on_windows(
    monkeypatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    def fake_run(*args, **kwargs):
        captured["args"] = args
        return type(
            "Completed",
            (),
            {"returncode": 0, "stdout": "", "stderr": ""},
        )()

    monkeypatch.setattr("zivo.services.shell_command.subprocess.run", fake_run)
    service = LiveShellCommandService(
        os_name="nt",
        command_available=lambda command: command if command == "cmd.exe" else None,
    )

    service.execute(cwd=str(tmp_path), command="dir")

    assert captured["args"] == (["cmd.exe", "/c", "dir"],)


@pytest.mark.skipif(os.name != "nt", reason="Windows-only shell selection test")
def test_live_shell_command_service_uses_windows_shell_override(
    monkeypatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    def fake_run(*args, **kwargs):
        captured["args"] = args
        return type(
            "Completed",
            (),
            {"returncode": 0, "stdout": "", "stderr": ""},
        )()

    monkeypatch.setattr("zivo.services.shell_command.subprocess.run", fake_run)
    service = LiveShellCommandService(
        shell="pwsh -NoLogo",
        os_name="nt",
        command_available=lambda command: None,
    )

    service.execute(cwd=str(tmp_path), command="Get-Date")

    assert captured["args"] == (["pwsh", "-NoLogo", "-NoProfile", "-Command", "Get-Date"],)


@pytest.mark.skipif(os.name != "nt", reason="Windows-only shell selection test")
def test_live_shell_command_service_rejects_unknown_windows_shell_override(
    tmp_path: Path,
) -> None:
    service = LiveShellCommandService(
        shell="bash",
        os_name="nt",
        command_available=lambda command: None,
    )

    with pytest.raises(
        OSError,
        match="Windows shell command override must target powershell.exe, pwsh, or cmd.exe",
    ):
        service.execute(cwd=str(tmp_path), command="pwd")
