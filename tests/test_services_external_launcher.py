from dataclasses import dataclass, field

import pytest

from peneo.adapters import LocalExternalLaunchAdapter
from peneo.models import EditorConfig, ExternalLaunchRequest, TerminalConfig
from peneo.services import LiveExternalLaunchService


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
    terminal_paths: list[str] = field(default_factory=list)
    clipboard_payloads: list[str] = field(default_factory=list)

    def open_with_default_app(self, path: str) -> None:
        self.opened_paths.append(path)

    def open_in_editor(self, path: str) -> None:
        self.edited_paths.append(path)

    def open_terminal(self, path: str) -> None:
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

    assert runner.executed == [(("vim", str(readme.resolve())), str(tmp_path.resolve()))]


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

    assert runner.executed == [(("vim", str(readme.resolve())), str(tmp_path.resolve()))]


def test_local_external_launch_adapter_falls_back_terminal_command_on_linux(tmp_path) -> None:
    runner = StubCommandRunner(failing_commands={"kgx"})
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Linux",
        command_available=lambda command: command if command in {"kgx", "gnome-terminal"} else None,
        command_runner=runner,
        text_file_reader=lambda _path: "Linux version 6.8.0\n",
    )

    adapter.open_terminal(str(tmp_path))

    assert runner.executed == [
        (("kgx",), str(tmp_path), None),
        (("gnome-terminal",), str(tmp_path), None),
    ]


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


def test_local_external_launch_adapter_copies_to_clipboard_on_linux() -> None:
    runner = StubCommandRunner()
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Linux",
        command_available=lambda command: command if command == "wl-copy" else None,
        command_runner=runner,
    )

    adapter.copy_to_clipboard("/tmp/peneo/docs\n/tmp/peneo/README.md")

    assert runner.executed == [
        (("wl-copy",), None, "/tmp/peneo/docs\n/tmp/peneo/README.md")
    ]


def test_local_external_launch_adapter_uses_clip_exe_on_wsl() -> None:
    runner = StubCommandRunner()
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Linux",
        command_available=lambda command: command if command == "clip.exe" else None,
        command_runner=runner,
        environment_variable=lambda name: "Ubuntu" if name == "WSL_DISTRO_NAME" else None,
    )

    adapter.copy_to_clipboard("/tmp/peneo/docs\n/tmp/peneo/README.md")

    assert runner.executed == [
        (("clip.exe",), None, "/tmp/peneo/docs\n/tmp/peneo/README.md")
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


def test_local_external_launch_adapter_rejects_windows_native_support(tmp_path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("plain\n", encoding="utf-8")
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Windows",
        command_available=lambda command: command,
        command_runner=StubCommandRunner(),
    )

    with pytest.raises(OSError, match="Windows native is unsupported"):
        adapter.open_with_default_app(str(readme))


def test_local_external_launch_adapter_uses_clipboard_fallback_when_commands_missing() -> None:
    copied: list[str] = []

    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Linux",
        command_available=lambda command: None,
        command_runner=runner_not_expected,
        clipboard_fallbacks=(copied.append,),
    )

    adapter.copy_to_clipboard("/tmp/peneo/docs")

    assert copied == ["/tmp/peneo/docs"]


def test_live_external_launch_service_formats_open_error(tmp_path) -> None:
    missing = tmp_path / "missing.txt"
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Linux",
        command_available=lambda command: command if command == "xdg-open" else None,
        command_runner=StubCommandRunner(),
    )
    service = LiveExternalLaunchService(adapter=adapter)

    with pytest.raises(OSError, match=f"Failed to open {missing.resolve()}: Not found: "):
        service.execute(ExternalLaunchRequest(kind="open_file", path=str(missing)))


def test_live_external_launch_service_opens_file_with_adapter() -> None:
    adapter = StubExternalLaunchAdapter()
    service = LiveExternalLaunchService(adapter=adapter)

    service.execute(ExternalLaunchRequest(kind="open_file", path="/tmp/peneo/README.md"))

    assert adapter.opened_paths == ["/tmp/peneo/README.md"]


def test_live_external_launch_service_opens_terminal_with_adapter() -> None:
    adapter = StubExternalLaunchAdapter()
    service = LiveExternalLaunchService(adapter=adapter)

    service.execute(ExternalLaunchRequest(kind="open_terminal", path="/tmp/peneo"))

    assert adapter.terminal_paths == ["/tmp/peneo"]


def test_live_external_launch_service_copies_paths_with_expected_payload() -> None:
    adapter = StubExternalLaunchAdapter()
    service = LiveExternalLaunchService(adapter=adapter)

    service.execute(
        ExternalLaunchRequest(
            kind="copy_paths",
            paths=("/tmp/peneo/docs", "/tmp/peneo/README.md"),
        )
    )

    assert adapter.clipboard_payloads == ["/tmp/peneo/docs\n/tmp/peneo/README.md"]


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
        match=f"Failed to open {missing.resolve()} in editor: Not found: ",
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
        match=f"Failed to open terminal in {readme.resolve()}: Not a directory: ",
    ):
        service.execute(ExternalLaunchRequest(kind="open_terminal", path=str(readme)))


def test_live_external_launch_service_formats_windows_native_error(tmp_path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("plain\n", encoding="utf-8")
    adapter = LocalExternalLaunchAdapter(
        system_name_resolver=lambda: "Windows",
        command_available=lambda command: command,
        command_runner=StubCommandRunner(),
    )
    service = LiveExternalLaunchService(adapter=adapter)

    with pytest.raises(
        OSError,
        match=(
            f"Failed to open {readme.resolve()}: "
            "Windows native is unsupported; run Peneo from WSL"
        ),
    ):
        service.execute(ExternalLaunchRequest(kind="open_file", path=str(readme)))


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
                paths=("/tmp/peneo/docs", "/tmp/peneo/README.md"),
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

    assert runner.executed == [
        (("vim", "+100", str(readme.resolve())), str(tmp_path.resolve()))
    ]


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

    assert runner.executed == [
        (("nano", "+1", str(readme.resolve())), str(tmp_path.resolve()))
    ]


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

    assert runner.executed == [
        (("vim", "+42", str(readme.resolve())), str(tmp_path.resolve()))
    ]


def runner_not_expected(
    command: tuple[str, ...],
    cwd: str | None,
    input_text: str | None,
) -> None:
    raise AssertionError(f"command runner should not be used: {command}, {cwd}, {input_text}")
