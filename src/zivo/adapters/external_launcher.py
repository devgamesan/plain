"""OS adapter for launching default applications, terminals, and clipboard commands."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Literal, Protocol

from zivo.adapters.platforms import (
    PlatformAdapterContext,
    PlatformKind,
    resolve_platform_adapter,
    resolve_platform_kind,
)
from zivo.adapters.platforms.base import (
    ClipboardFallback,
    ClipboardReader,
    CommandAvailability,
    CommandRunner,
    EnvironmentVariableReader,
    ForegroundCommandRunner,
    TextFileReader,
)
from zivo.adapters.platforms.base import (
    _build_command_candidate as _base_build_command_candidate,
)
from zivo.adapters.platforms.base import (
    is_wsl_environment as _base_is_wsl_environment,
)
from zivo.models import EditorConfig, GuiEditorConfig, TerminalConfig

SystemNameResolver = Callable[[], str]
CommandOutputReader = Callable[[Sequence[str]], str]
_build_command_candidate = _base_build_command_candidate
_is_wsl_environment = _base_is_wsl_environment


class ExternalLaunchAdapter(Protocol):
    """Boundary for external process launches."""

    def open_with_default_app(self, path: str) -> None: ...

    def open_in_editor(self, path: str, line_number: int | None = None) -> None: ...

    def open_in_gui_editor(
        self,
        path: str,
        line_number: int | None = None,
        column_number: int | None = None,
    ) -> None: ...

    def open_terminal(
        self, path: str, launch_mode: Literal["window", "foreground"] = "window"
    ) -> None: ...

    def run_in_terminal_window(self, cwd: str, command: tuple[str, ...]) -> None: ...

    def copy_to_clipboard(self, text: str) -> None: ...

    def get_from_clipboard(self) -> str: ...


@dataclass(frozen=True)
class LocalExternalLaunchAdapter:
    """Launch applications and terminals via OS-specific commands."""

    system_name_resolver: SystemNameResolver = platform.system
    command_available: CommandAvailability = field(default_factory=lambda: shutil.which)
    command_runner: CommandRunner = field(default_factory=lambda: _run_detached_command)
    foreground_command_runner: ForegroundCommandRunner = field(
        default_factory=lambda: _run_foreground_command
    )
    clipboard_command_reader: CommandOutputReader = field(
        default_factory=lambda: _read_command_output
    )
    environment_variable: EnvironmentVariableReader = field(
        default_factory=lambda: os.environ.get
    )
    text_file_reader: TextFileReader = field(default_factory=lambda: _read_text_file)
    clipboard_fallbacks: tuple[ClipboardFallback, ...] = field(
        default_factory=lambda: (_copy_to_clipboard_with_tkinter,)
    )
    clipboard_readers: tuple[ClipboardReader, ...] = field(
        default_factory=lambda: (_read_from_clipboard_with_tkinter,)
    )
    terminal_command_templates: TerminalConfig = field(default_factory=TerminalConfig)
    editor_command_template: EditorConfig = field(default_factory=EditorConfig)
    gui_editor_command_template: GuiEditorConfig = field(default_factory=GuiEditorConfig)

    def open_with_default_app(self, path: str) -> None:
        self._platform_adapter().open_with_default_app(path)

    def open_in_editor(self, path: str, line_number: int | None = None) -> None:
        self._platform_adapter().open_in_editor(path, line_number)

    def open_in_gui_editor(
        self,
        path: str,
        line_number: int | None = None,
        column_number: int | None = None,
    ) -> None:
        self._platform_adapter().open_in_gui_editor(path, line_number, column_number)

    def open_terminal(
        self, path: str, launch_mode: Literal["window", "foreground"] = "window"
    ) -> None:
        self._platform_adapter().open_terminal(path, launch_mode)

    def run_in_terminal_window(self, cwd: str, command: tuple[str, ...]) -> None:
        self._platform_adapter().run_in_terminal_window(cwd, command)

    def copy_to_clipboard(self, text: str) -> None:
        self._platform_adapter().copy_to_clipboard(text)

    def get_from_clipboard(self) -> str:
        return self._platform_adapter().get_from_clipboard()

    def _platform_kind(self) -> PlatformKind:
        return resolve_platform_kind(
            self.system_name_resolver(),
            environment_variable=self.environment_variable,
            text_file_reader=self.text_file_reader,
        )

    def _platform_adapter(self):
        return resolve_platform_adapter(self._platform_kind(), self._platform_context())

    def _platform_context(self) -> PlatformAdapterContext:
        return PlatformAdapterContext(
            command_available=self.command_available,
            command_runner=self.command_runner,
            foreground_command_runner=self.foreground_command_runner,
            clipboard_command_reader=self.clipboard_command_reader,
            environment_variable=self.environment_variable,
            text_file_reader=self.text_file_reader,
            clipboard_fallbacks=self.clipboard_fallbacks,
            clipboard_readers=self.clipboard_readers,
            terminal_command_templates=self.terminal_command_templates,
            editor_command_template=self.editor_command_template,
            gui_editor_command_template=self.gui_editor_command_template,
        )

    def _command_exists(self, command: str) -> bool:
        return self._platform_adapter()._command_exists(command)


def _run_detached_command(command: Sequence[str], cwd: str | None, input_text: str | None) -> None:
    if input_text is not None:
        try:
            subprocess.run(
                list(command),
                input=input_text,
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=cwd,
                check=True,
            )
        except subprocess.CalledProcessError as error:
            raise OSError(str(error) or f"{command[0]} failed") from error
        return

    subprocess.Popen(
        list(command),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=cwd,
        start_new_session=True,
    )


def _run_foreground_command(command: Sequence[str], cwd: str | None) -> None:
    try:
        subprocess.run(
            list(command),
            cwd=cwd,
            check=True,
            stdin=sys.stdin,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
    except subprocess.CalledProcessError as error:
        raise OSError(str(error) or f"{command[0]} failed") from error


def _read_command_output(command: Sequence[str]) -> str:
    try:
        result = subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as error:
        raise OSError(str(error) or f"{command[0]} failed") from error
    return result.stdout


def _copy_to_clipboard_with_tkinter(text: str) -> None:
    try:
        import tkinter
    except ImportError as error:
        raise OSError("tkinter clipboard fallback is unavailable") from error

    root = None
    try:
        root = tkinter.Tk()
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
    except tkinter.TclError as error:
        raise OSError(f"tkinter clipboard fallback failed: {error}") from error
    finally:
        if root is not None:
            root.destroy()


def _read_from_clipboard_with_tkinter() -> str:
    try:
        import tkinter
    except ImportError as error:
        raise OSError("tkinter clipboard reader is unavailable") from error

    root = None
    try:
        root = tkinter.Tk()
        root.withdraw()
        try:
            return root.clipboard_get()
        except tkinter.TclError as error:
            raise OSError(f"tkinter clipboard reader failed: {error}") from error
    finally:
        if root is not None:
            root.destroy()


def _read_text_file(path: str) -> str:
    from pathlib import Path

    return Path(path).read_text(encoding="utf-8")
