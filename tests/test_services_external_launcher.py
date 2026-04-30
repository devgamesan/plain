import io
import re
import sys
from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest

from zivo.adapters import LocalExternalLaunchAdapter
from zivo.adapters.external_launcher import _build_command_candidate, _run_foreground_command
from zivo.models import EditorConfig, ExternalLaunchRequest, GuiEditorConfig, TerminalConfig
from zivo.services import LiveExternalLaunchService


@dataclass
class StubCommandRunner:
    executed: list[tuple[tuple[str, ...], str | None, str | None]] = field(default_factory=list)
    failing_commands: set[str] = field(default_factory=set)

    def __call__(self, command: tuple[str, ...], cwd: str | None, input_text: str | None) -> None:
        self.executed.append((command, cwd, input_text))
        if command[0] in self.failing_commands:
            raise OSError(f"{command[0]} failed")


@dataclass
class StubForegroundRunner:
    executed: list[tuple[tuple[str, ...], str | None]] = field(default_factory=list)
    failing_commands: set[str] = field(default_factory=set)

    def __call__(self, command: tuple[str, ...], cwd: str | None) -> None:
        self.executed.append((command, cwd))
        if command[0] in self.failing_commands:
            raise OSError(f"{command[0]} failed")


@dataclass
class StubExternalLaunchAdapter:
    opened_paths: list[str] = field(default_factory=list)
    edited_paths: list[str] = field(default_factory=list)
    gui_edited_paths: list[tuple[str, int | None, int | None]] = field(default_factory=list)
    terminal_paths: list[str] = field(default_factory=list)
    clipboard_payloads: list[str] = field(default_factory=list)

    def open_with_default_app(self, path: str) -> None:
        self.opened_paths.append(path)

    def open_in_editor(self, path: str) -> None:
        self.edited_paths.append(path)

    def open_in_gui_editor(
        self,
        path: str,
        line_number: int | None = None,
        column_number: int | None = None,
    ) -> None:
        self.gui_edited_paths.append((path, line_number, column_number))

    def open_terminal(self, path: str, launch_mode: str = "window") -> None:
        self.terminal_paths.append(path)

    def copy_to_clipboard(self, text: str) -> None:
        self.clipboard_payloads.append(text)


def test_local_external_launch_adapter_uses_xdg_open_on_linux(tmp_path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("plain\n", encoding="utf-8")
    runner = StubCommandRunner()
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Linux",
        command_available=lambda command: command if command == "xdg-open" else None,
        command_runner=runner,
    )

    adapter.open_with_default_app(str(readme))

    assert runner.executed == [
        (("xdg-open", str(readme.resolve())), str(tmp_path.resolve()), None)
    ]


def test_local_external_launch_adapter_falls_back_to_gio_open_on_linux(tmp_path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("plain\n", encoding="utf-8")
    runner = StubCommandRunner(failing_commands={"xdg-open"})
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Linux",
        command_available=lambda command: command if command in {"xdg-open", "gio"} else None,
        command_runner=runner,
        text_file_reader=lambda _path: "Linux version 6.8.0\n",
    )

    adapter.open_with_default_app(str(readme))

    assert runner.executed == [
        (("xdg-open", str(readme.resolve())), str(tmp_path.resolve()), None),
        (("gio", "open", str(readme.resolve())), str(tmp_path.resolve()), None),
    ]


def test_local_external_launch_adapter_uses_wslview_on_wsl(tmp_path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("plain\n", encoding="utf-8")
    runner = StubCommandRunner()
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Linux",
        command_available=lambda command: command if command == "wslview" else None,
        command_runner=runner,
        environment_variable=lambda name: "Ubuntu" if name == "WSL_DISTRO_NAME" else None,
    )

    adapter.open_with_default_app(str(readme))

    assert runner.executed == [
        (("wslview", str(readme.resolve())), str(tmp_path.resolve()), None)
    ]


def test_local_external_launch_adapter_falls_back_to_explorer_on_wsl(tmp_path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("plain\n", encoding="utf-8")
    runner = StubCommandRunner()
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Linux",
        command_available=lambda command: command if command == "explorer.exe" else None,
        command_runner=runner,
        environment_variable=lambda name: "Ubuntu" if name == "WSL_DISTRO_NAME" else None,
    )

    adapter.open_with_default_app(str(readme))

    assert runner.executed == [
        (("explorer.exe", str(readme.resolve())), str(tmp_path.resolve()), None)
    ]


def test_local_external_launch_adapter_uses_cmd_start_on_windows(tmp_path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("plain\n", encoding="utf-8")
    runner = StubCommandRunner()
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Windows",
        command_available=lambda command: command if command == "cmd.exe" else None,
        command_runner=runner,
    )

    adapter.open_with_default_app(str(readme))

    assert runner.executed == [
        (("cmd.exe", "/c", "start", "", str(readme.resolve())), str(tmp_path.resolve()), None)
    ]


def test_local_external_launch_adapter_runs_terminal_editor_in_current_terminal(tmp_path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("plain\n", encoding="utf-8")
    runner = StubForegroundRunner()
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Linux",
        command_available=lambda command: command if command == "nvim" else None,
        foreground_command_runner=runner,
        environment_variable=lambda name: "nvim -u NONE" if name == "EDITOR" else None,
    )

    adapter.open_in_editor(str(readme))

    assert runner.executed == [
        (("nvim", "-u", "NONE", str(readme.resolve())), str(tmp_path.resolve()))
    ]


def test_local_external_launch_adapter_prefers_configured_editor_command(tmp_path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("plain\n", encoding="utf-8")
    runner = StubForegroundRunner()
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Linux",
        command_available=lambda command: command if command in {"nvim", "vim"} else None,
        foreground_command_runner=runner,
        environment_variable=lambda _name: "vim" ,
        editor_command_template=EditorConfig(command="nvim -u NONE"),
    )

    adapter.open_in_editor(str(readme))

    assert runner.executed == [
        (("nvim", "-u", "NONE", str(readme.resolve())), str(tmp_path.resolve()))
    ]


def test_local_external_launch_adapter_ignores_gui_editor_environment_variable(tmp_path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("plain\n", encoding="utf-8")
    runner = StubForegroundRunner()
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Linux",
        command_available=lambda command: command if command == "vim" else None,
        foreground_command_runner=runner,
        environment_variable=lambda name: "code" if name == "EDITOR" else None,
    )

    adapter.open_in_editor(str(readme))

    assert runner.executed[0][0][0] in ("vim", "nvim")
    assert runner.executed[0][0][1] == str(readme.resolve())
    assert runner.executed[0][1] == str(tmp_path.resolve())


def test_local_external_launch_adapter_ignores_gui_configured_editor_command(tmp_path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("plain\n", encoding="utf-8")
    runner = StubForegroundRunner()
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Linux",
        command_available=lambda command: command if command == "vim" else None,
        foreground_command_runner=runner,
        editor_command_template=EditorConfig(command="code --wait"),
        environment_variable=lambda _name: None,
    )

    adapter.open_in_editor(str(readme))

    assert runner.executed[0][0][0] in ("vim", "nvim")
    assert runner.executed[0][0][1] == str(readme.resolve())
    assert runner.executed[0][1] == str(tmp_path.resolve())


def test_local_external_launch_adapter_falls_back_terminal_command_on_linux(tmp_path) -> None:
    runner = StubCommandRunner(failing_commands={"kgx"})
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Linux",
        command_available=lambda command: command if command in {"kgx", "gnome-terminal"} else None,
        command_runner=runner,
        text_file_reader=lambda _path: "Linux version 6.8.0\n",
    )

    adapter.open_terminal(str(tmp_path))

    assert runner.executed[0][1] == str(tmp_path)
    assert runner.executed[0][2] is None
    assert runner.executed[0][0][0] in ("kgx", "gnome-terminal", "konsole")


def test_local_external_launch_adapter_uses_wt_on_wsl_for_terminal(tmp_path) -> None:
    runner = StubCommandRunner()
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Linux",
        command_available=lambda command: command if command == "wt.exe" else None,
        command_runner=runner,
        environment_variable=lambda name: "Ubuntu" if name == "WSL_DISTRO_NAME" else None,
    )

    adapter.open_terminal(str(tmp_path))

    assert runner.executed == [
        (("wt.exe", "wsl.exe", "--cd", str(tmp_path.resolve())), str(tmp_path), None)
    ]


def test_local_external_launch_adapter_uses_open_on_macos(tmp_path) -> None:
    runner = StubCommandRunner()
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Darwin",
        command_available=lambda command: command if command == "open" else None,
        command_runner=runner,
    )

    adapter.open_terminal(str(tmp_path))

    assert runner.executed == [
        (("open", "-a", "Terminal", str(tmp_path.resolve())), str(tmp_path), None)
    ]


def test_local_external_launch_adapter_uses_wt_on_windows_for_terminal(tmp_path) -> None:
    runner = StubCommandRunner()
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Windows",
        command_available=lambda command: command if command == "wt.exe" else None,
        command_runner=runner,
    )

    adapter.open_terminal(str(tmp_path))

    assert runner.executed == [
        (("wt.exe", "-d", str(tmp_path.resolve())), str(tmp_path), None)
    ]


def test_local_external_launch_adapter_prefers_configured_terminal_commands(tmp_path) -> None:
    runner = StubCommandRunner()
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Linux",
        command_available=lambda command: command if command in {"konsole", "kgx"} else None,
        command_runner=runner,
        terminal_command_templates=TerminalConfig(
            linux=("konsole --working-directory {path}",),
        ),
    )

    adapter.open_terminal(str(tmp_path))

    assert runner.executed == [
        (
            ("konsole", "--working-directory", str(tmp_path.resolve())),
            str(tmp_path),
            None,
        )
    ]


def test_local_external_launch_adapter_uses_windows_templates_first_on_wsl(tmp_path) -> None:
    runner = StubCommandRunner()
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Linux",
        command_available=lambda command: command if command == "wt.exe" else None,
        command_runner=runner,
        environment_variable=lambda name: "Ubuntu" if name == "WSL_DISTRO_NAME" else None,
        terminal_command_templates=TerminalConfig(
            windows=("wt.exe -d {path}",),
            linux=("konsole --working-directory {path}",),
        ),
    )

    adapter.open_terminal(str(tmp_path))

    assert runner.executed == [
        (("wt.exe", "-d", str(tmp_path.resolve())), str(tmp_path), None)
    ]


def test_local_external_launch_adapter_runs_terminal_in_foreground_mode(tmp_path) -> None:
    runner = StubForegroundRunner()
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Linux",
        command_available=lambda command: command if command == "bash" else None,
        foreground_command_runner=runner,
        environment_variable=lambda name: "bash" if name == "SHELL" else None,
    )

    adapter.open_terminal(str(tmp_path), launch_mode="foreground")

    assert runner.executed == [(("bash", "-i"), str(tmp_path))]


def test_windows_foreground_terminal_uses_powershell(tmp_path) -> None:
    runner = StubForegroundRunner()
    pwsh = "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe"
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Windows",
        command_available=lambda command: pwsh
        if command == "powershell.exe"
        else None,
        foreground_command_runner=runner,
    )

    adapter.open_terminal(str(tmp_path), launch_mode="foreground")

    assert runner.executed == [
        ((pwsh, "-NoExit", "-NoLogo"), str(tmp_path))
    ]


def test_windows_foreground_terminal_falls_back_to_cmd(tmp_path) -> None:
    runner = StubForegroundRunner()
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Windows",
        command_available=lambda command: None,
        foreground_command_runner=runner,
    )

    adapter.open_terminal(str(tmp_path), launch_mode="foreground")

    assert runner.executed == [(("cmd.exe", "/k"), str(tmp_path))]


def test_local_external_launch_adapter_copies_to_clipboard_on_linux() -> None:
    runner = StubCommandRunner()
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Linux",
        command_available=lambda command: command if command in {"wl-copy", "xclip"} else None,
        command_runner=runner,
    )

    adapter.copy_to_clipboard("/tmp/zivo/docs\n/tmp/zivo/README.md")

    assert runner.executed[0][1] is None
    assert runner.executed[0][2] == "/tmp/zivo/docs\n/tmp/zivo/README.md"
    assert runner.executed[0][0][0] in ("wl-copy", "xclip")


def test_local_external_launch_adapter_uses_clip_exe_on_wsl() -> None:
    runner = StubCommandRunner()
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Linux",
        command_available=lambda command: command if command == "clip.exe" else None,
        command_runner=runner,
        environment_variable=lambda name: "Ubuntu" if name == "WSL_DISTRO_NAME" else None,
    )

    adapter.copy_to_clipboard("/tmp/zivo/docs\n/tmp/zivo/README.md")

    assert runner.executed == [
        (("clip.exe",), None, "/tmp/zivo/docs\n/tmp/zivo/README.md")
    ]


def test_local_external_launch_adapter_uses_clip_exe_on_windows() -> None:
    runner = StubCommandRunner()
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Windows",
        command_available=lambda command: command if command == "clip.exe" else None,
        command_runner=runner,
    )

    adapter.copy_to_clipboard("/tmp/zivo/docs\n/tmp/zivo/README.md")

    assert runner.executed == [
        (("clip.exe",), None, "/tmp/zivo/docs\n/tmp/zivo/README.md")
    ]


def test_local_external_launch_adapter_raises_last_terminal_error_when_all_candidates_fail(
    tmp_path,
) -> None:
    runner = StubCommandRunner(
        failing_commands={
            "kgx",
            "gnome-console",
            "gnome-terminal",
            "xfce4-terminal",
            "mate-terminal",
            "tilix",
            "konsole",
            "lxterminal",
            "x-terminal-emulator",
            "xterm",
        }
    )
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Linux",
        command_available=lambda command: (
            command
            if command
            in {
                "kgx",
                "gnome-console",
                "gnome-terminal",
                "xfce4-terminal",
                "mate-terminal",
                "tilix",
                "konsole",
                "lxterminal",
                "x-terminal-emulator",
                "xterm",
            }
            else None
        ),
        command_runner=runner,
        text_file_reader=lambda _path: "Linux version 6.8.0\n",
    )

    with pytest.raises(OSError, match="xterm failed"):
        adapter.open_terminal(str(tmp_path))


def test_local_external_launch_adapter_reports_invalid_editor_value(tmp_path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("plain\n", encoding="utf-8")
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Linux",
        command_available=lambda command: command if command == "nvim" else None,
        command_runner=StubCommandRunner(),
        environment_variable=lambda name: "'" if name == "EDITOR" else None,
    )

    with pytest.raises(OSError, match="Invalid EDITOR value"):
        adapter.open_in_editor(str(readme))


def test_local_external_launch_adapter_reads_from_windows_clipboard(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        assert args == (["powershell.exe", "-NoProfile", "-Command", "Get-Clipboard"],)
        assert kwargs == {"capture_output": True, "text": True, "check": True}
        return SimpleNamespace(stdout="clipboard text", returncode=0)

    monkeypatch.setattr("zivo.adapters.external_launcher.subprocess.run", fake_run)
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Windows",
        command_available=lambda command: command if command == "powershell.exe" else None,
    )

    assert adapter.get_from_clipboard() == "clipboard text"


def test_local_external_launch_adapter_uses_clipboard_fallback_when_commands_missing() -> None:
    copied: list[str] = []

    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Linux",
        command_available=lambda command: None,
        command_runner=runner_not_expected,
        clipboard_fallbacks=(copied.append,),
    )

    adapter.copy_to_clipboard("/tmp/zivo/docs")

    assert copied == ["/tmp/zivo/docs"]


def test_live_external_launch_service_formats_open_error(tmp_path) -> None:
    missing = tmp_path / "missing.txt"
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Linux",
        command_available=lambda command: command if command == "xdg-open" else None,
        command_runner=StubCommandRunner(),
    )
    service = LiveExternalLaunchService(adapter=adapter)

    with pytest.raises(
        OSError,
        match=re.escape(f"Failed to open {missing.resolve()}: Not found: "),
    ):
        service.execute(ExternalLaunchRequest(kind="open_file", path=str(missing)))


def test_live_external_launch_service_opens_file_with_adapter() -> None:
    adapter = StubExternalLaunchAdapter()
    service = LiveExternalLaunchService(adapter=adapter)

    service.execute(ExternalLaunchRequest(kind="open_file", path="/tmp/zivo/README.md"))

    assert adapter.opened_paths == ["/tmp/zivo/README.md"]


def test_live_external_launch_service_opens_terminal_with_adapter() -> None:
    adapter = StubExternalLaunchAdapter()
    service = LiveExternalLaunchService(adapter=adapter)

    service.execute(ExternalLaunchRequest(kind="open_terminal", path="/tmp/zivo"))

    assert adapter.terminal_paths == ["/tmp/zivo"]


def test_live_external_launch_service_opens_gui_editor_with_adapter() -> None:
    adapter = StubExternalLaunchAdapter()
    service = LiveExternalLaunchService(adapter=adapter)

    service.execute(
        ExternalLaunchRequest(
            kind="open_gui_editor",
            path="/tmp/zivo/README.md",
            line_number=12,
            column_number=4,
        )
    )

    assert adapter.gui_edited_paths == [("/tmp/zivo/README.md", 12, 4)]


def test_live_external_launch_service_opens_terminal_in_foreground_mode(tmp_path) -> None:
    runner = StubForegroundRunner()
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Linux",
        command_available=lambda command: command if command == "bash" else None,
        foreground_command_runner=runner,
        environment_variable=lambda name: "bash" if name == "SHELL" else None,
    )
    service = LiveExternalLaunchService(adapter=adapter)
    path = str(tmp_path.resolve())

    service.execute(
        ExternalLaunchRequest(
            kind="open_terminal",
            path=path,
            terminal_launch_mode="foreground",
        )
    )

    assert runner.executed == [(("bash", "-i"), path)]


def test_live_external_launch_service_opens_terminal_in_windows_foreground_mode(tmp_path) -> None:
    runner = StubForegroundRunner()
    pwsh = "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe"
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Windows",
        command_available=lambda command: pwsh
        if command == "powershell.exe"
        else None,
        foreground_command_runner=runner,
    )
    service = LiveExternalLaunchService(adapter=adapter)
    path = str(tmp_path.resolve())

    service.execute(
        ExternalLaunchRequest(
            kind="open_terminal",
            path=path,
            terminal_launch_mode="foreground",
        )
    )

    assert runner.executed == [
        ((pwsh, "-NoExit", "-NoLogo"), path)
    ]


def test_live_external_launch_service_copies_paths_with_expected_payload() -> None:
    adapter = StubExternalLaunchAdapter()
    service = LiveExternalLaunchService(adapter=adapter)

    service.execute(
        ExternalLaunchRequest(
            kind="copy_paths",
            paths=("/tmp/zivo/docs", "/tmp/zivo/README.md"),
        )
    )

    assert adapter.clipboard_payloads == ["/tmp/zivo/docs\n/tmp/zivo/README.md"]


def test_live_external_launch_service_formats_editor_error(tmp_path) -> None:
    missing = tmp_path / "missing.txt"
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Linux",
        command_available=lambda command: command if command == "gedit" else None,
        command_runner=StubCommandRunner(),
        environment_variable=lambda name: None,
    )
    service = LiveExternalLaunchService(adapter=adapter)

    with pytest.raises(
        OSError,
        match=re.escape(f"Failed to open {missing.resolve()} in editor: Not found: "),
    ):
        service.execute(ExternalLaunchRequest(kind="open_editor", path=str(missing)))


def test_live_external_launch_service_formats_terminal_error_for_file(tmp_path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("plain\n", encoding="utf-8")
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Linux",
        command_available=lambda command: command if command == "konsole" else None,
        command_runner=StubCommandRunner(),
    )
    service = LiveExternalLaunchService(adapter=adapter)

    with pytest.raises(
        OSError,
        match=re.escape(f"Failed to open terminal in {readme.resolve()}: Not a directory: "),
    ):
        service.execute(ExternalLaunchRequest(kind="open_terminal", path=str(readme)))


def test_live_external_launch_service_opens_file_on_windows(tmp_path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("plain\n", encoding="utf-8")
    runner = StubCommandRunner()
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Windows",
        command_available=lambda command: command if command == "cmd.exe" else None,
        command_runner=runner,
    )
    service = LiveExternalLaunchService(adapter=adapter)

    service.execute(ExternalLaunchRequest(kind="open_file", path=str(readme)))

    assert runner.executed == [
        (("cmd.exe", "/c", "start", "", str(readme.resolve())), str(tmp_path.resolve()), None)
    ]


def test_live_external_launch_service_formats_copy_error() -> None:
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Linux",
        command_available=lambda command: None,
        command_runner=StubCommandRunner(),
        clipboard_fallbacks=(),
    )
    service = LiveExternalLaunchService(adapter=adapter)

    with pytest.raises(
        OSError,
        match=(
            "Failed to copy 2 paths to system clipboard: "
            "No supported command found to copy to clipboard"
        ),
    ):
        service.execute(
            ExternalLaunchRequest(
                kind="copy_paths",
                paths=("/tmp/zivo/docs", "/tmp/zivo/README.md"),
            )
        )


def test_local_external_launch_adapter_opens_editor_with_line_number(tmp_path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("plain\n", encoding="utf-8")
    runner = StubForegroundRunner()
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Linux",
        command_available=lambda command: command if command == "nvim" else None,
        foreground_command_runner=runner,
        environment_variable=lambda name: None,
    )

    adapter.open_in_editor(str(readme), line_number=42)

    assert runner.executed == [
        (("nvim", "+42", str(readme.resolve())), str(tmp_path.resolve()))
    ]


def test_local_external_launch_adapter_opens_vim_with_line_number(tmp_path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("plain\n", encoding="utf-8")
    runner = StubForegroundRunner()
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Linux",
        command_available=lambda command: command if command == "vim" else None,
        foreground_command_runner=runner,
        environment_variable=lambda name: None,
    )

    adapter.open_in_editor(str(readme), line_number=100)

    assert runner.executed[0][0][0] in ("vim", "nvim")
    assert runner.executed[0][0][1] == "+100"
    assert runner.executed[0][0][2] == str(readme.resolve())
    assert runner.executed[0][1] == str(tmp_path.resolve())


def test_local_external_launch_adapter_opens_nano_with_line_number(tmp_path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("plain\n", encoding="utf-8")
    runner = StubForegroundRunner()
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Linux",
        command_available=lambda command: command if command == "nano" else None,
        foreground_command_runner=runner,
        environment_variable=lambda name: None,
    )

    adapter.open_in_editor(str(readme), line_number=1)

    assert runner.executed[0][0][0] in ("nano", "nvim")
    assert runner.executed[0][0][1] == "+1"
    assert runner.executed[0][0][2] == str(readme.resolve())
    assert runner.executed[0][1] == str(tmp_path.resolve())


def test_live_external_launch_service_opens_editor_with_line_number(tmp_path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("plain\n", encoding="utf-8")
    runner = StubForegroundRunner()
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Linux",
        command_available=lambda command: command if command == "vim" else None,
        foreground_command_runner=runner,
        environment_variable=lambda name: None,
    )
    service = LiveExternalLaunchService(adapter=adapter)

    service.execute(ExternalLaunchRequest(kind="open_editor", path=str(readme), line_number=42))

    assert runner.executed[0][0][0] in ("vim", "nvim")
    assert runner.executed[0][0][1] == "+42"
    assert runner.executed[0][0][2] == str(readme.resolve())
    assert runner.executed[0][1] == str(tmp_path.resolve())


def test_local_external_launch_adapter_opens_gui_editor_with_line_and_column(tmp_path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("plain\n", encoding="utf-8")
    runner = StubCommandRunner()
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Linux",
        command_available=lambda command: command if command == "code" else None,
        command_runner=runner,
        gui_editor_command_template=GuiEditorConfig(),
        text_file_reader=lambda _path: "Linux version 6.8.0\n",
    )

    adapter.open_in_gui_editor(str(readme), line_number=42, column_number=7)

    assert runner.executed == [
        (("code", "--goto", f"{readme.resolve()}:42:7"), str(tmp_path.resolve()), None)
    ]


def test_local_external_launch_adapter_uses_gui_editor_fallback_without_line(tmp_path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("plain\n", encoding="utf-8")
    runner = StubCommandRunner()
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Linux",
        command_available=lambda command: command if command == "code" else None,
        command_runner=runner,
        gui_editor_command_template=GuiEditorConfig(),
        text_file_reader=lambda _path: "Linux version 6.8.0\n",
    )

    adapter.open_in_gui_editor(str(readme))

    assert runner.executed == [
        (("code", str(readme.resolve())), str(tmp_path.resolve()), None)
    ]


def test_local_external_launch_adapter_falls_back_for_gui_editor_when_command_fails(
    tmp_path,
) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("plain\n", encoding="utf-8")
    runner = StubCommandRunner(failing_commands={"codium"})
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Linux",
        command_available=lambda command: command if command in {"codium", "code"} else None,
        command_runner=runner,
        gui_editor_command_template=GuiEditorConfig(
            command="codium --goto {path}:{line}:{column}",
            fallback_command="code {path}",
        ),
        text_file_reader=lambda _path: "Linux version 6.8.0\n",
    )

    adapter.open_in_gui_editor(str(readme), line_number=3, column_number=2)

    assert runner.executed[0][1] == str(tmp_path.resolve())
    assert runner.executed[0][2] is None
    assert runner.executed[0][0][0] in ("codium", "code")


def test_run_foreground_command_uses_current_standard_streams(monkeypatch) -> None:
    stdin = io.StringIO()
    stdout = io.StringIO()
    stderr = io.StringIO()
    captured: dict[str, object] = {}

    def fake_run(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(sys, "stdin", stdin)
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "stderr", stderr)
    monkeypatch.setattr("zivo.adapters.external_launcher.subprocess.run", fake_run)

    _run_foreground_command(("nvim", "README.md"), "/tmp/project")

    assert captured["args"] == (["nvim", "README.md"],)
    assert captured["kwargs"] == {
        "cwd": "/tmp/project",
        "check": True,
        "stdin": stdin,
        "stdout": stdout,
        "stderr": stderr,
    }


def runner_not_expected(
    command: tuple[str, ...],
    cwd: str | None,
    input_text: str | None,
) -> None:
    raise AssertionError(f"command runner should not be used: {command}, {cwd}, {input_text}")


# --- Tests for _build_command_candidate ---


def test_build_command_candidate_with_line_number() -> None:
    result = _build_command_candidate(("nvim",), "/tmp/file.py", line_number=42)
    assert result == ("nvim", "+42", "/tmp/file.py")


def test_build_command_candidate_without_line_number() -> None:
    result = _build_command_candidate(("vim",), "/tmp/file.py")
    assert result == ("vim", "/tmp/file.py")


def test_build_command_candidate_with_extra_flags() -> None:
    result = _build_command_candidate(("emacs", "-nw"), "/tmp/file.py", line_number=10)
    assert result == ("emacs", "-nw", "+10", "/tmp/file.py")


def test_build_command_candidate_returns_none_for_empty_command() -> None:
    result = _build_command_candidate((), "/tmp/file.py")
    assert result is None


def test_build_command_candidate_returns_none_for_gui_editor() -> None:
    result = _build_command_candidate(("code", "--wait"), "/tmp/file.py")
    assert result is None


def test_build_command_candidate_for_edit_with_line_number() -> None:
    result = _build_command_candidate(("edit",), "/tmp/file.py", line_number=42)
    assert result == ("edit", "/tmp/file.py:42")


def test_build_command_candidate_for_edit_without_line_number() -> None:
    result = _build_command_candidate(("edit",), "/tmp/file.py")
    assert result == ("edit", "/tmp/file.py")


def test_build_command_candidate_for_msedit_with_line_number() -> None:
    result = _build_command_candidate(("msedit",), "/tmp/file.py", line_number=10)
    assert result == ("msedit", "/tmp/file.py:10")


# --- Tests for Windows editor support ---


def test_windows_default_editor_commands_include_edit(tmp_path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("plain\n", encoding="utf-8")
    runner = StubForegroundRunner()
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Windows",
        command_available=lambda command: command if command == "edit" else None,
        foreground_command_runner=runner,
        environment_variable=lambda _name: None,
        editor_command_template=EditorConfig(command=None),
    )

    adapter.open_in_editor(str(readme))

    assert runner.executed == [
        (("edit", str(readme.resolve())), str(tmp_path.resolve()))
    ]


def test_windows_default_editor_commands_include_edit_with_line_number(tmp_path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("plain\n", encoding="utf-8")
    runner = StubForegroundRunner()
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Windows",
        command_available=lambda command: command if command == "edit" else None,
        foreground_command_runner=runner,
        environment_variable=lambda _name: None,
        editor_command_template=EditorConfig(command=None),
    )

    adapter.open_in_editor(str(readme), line_number=42)

    assert runner.executed == [
        (("edit", f"{str(readme.resolve())}:42"), str(tmp_path.resolve()))
    ]


# --- Tests for _command_exists ---


def test_command_exists_finds_command_on_path() -> None:
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Linux",
        command_available=lambda cmd: f"/usr/bin/{cmd}" if cmd == "nvim" else None,
    )
    assert adapter._command_exists("nvim") is True


def test_command_exists_returns_false_for_missing_command() -> None:
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Linux",
        command_available=lambda _cmd: None,
    )
    assert adapter._command_exists("nonexistent-editor") is False


def test_command_exists_checks_absolute_path(tmp_path) -> None:
    script = tmp_path / "my-editor"
    script.write_text("#!/bin/sh\n")
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Linux",
        command_available=lambda _cmd: None,
    )
    assert adapter._command_exists(str(script)) is True


def test_command_exists_returns_false_for_missing_absolute_path() -> None:
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Linux",
        command_available=lambda _cmd: None,
    )
    assert adapter._command_exists("/nonexistent/path/editor") is False
