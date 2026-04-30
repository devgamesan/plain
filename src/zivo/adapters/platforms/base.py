"""Shared platform launcher infrastructure."""

from __future__ import annotations

import shlex
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from zivo.models import EditorConfig, GuiEditorConfig, TerminalConfig

PlatformKind = Literal["linux", "wsl", "darwin", "windows"]
CommandRunner = Callable[[Sequence[str], str | None, str | None], None]
ForegroundCommandRunner = Callable[[Sequence[str], str | None], None]
CommandAvailability = Callable[[str], str | None]
CommandOutputReader = Callable[[Sequence[str]], str]
ClipboardFallback = Callable[[str], None]
ClipboardReader = Callable[[], str]
EnvironmentVariableReader = Callable[[str], str | None]
TextFileReader = Callable[[str], str]

TERMINAL_EDITOR_NAMES = frozenset(
    {"edit", "emacs", "helix", "hx", "kak", "micro", "msedit", "nano", "nvim", "vi", "vim"}
)
EMBEDDED_LINE_NUMBER_EDITOR_NAMES = frozenset({"edit", "msedit"})

_PLATFORM_TEMPLATE_KEYS: dict[PlatformKind, tuple[str, ...]] = {
    "linux": ("linux",),
    "darwin": ("macos",),
    "wsl": ("windows", "linux"),
    "windows": ("windows",),
}


@dataclass(frozen=True)
class PlatformAdapterContext:
    """Dependencies shared by all platform-specific launcher implementations."""

    command_available: CommandAvailability
    command_runner: CommandRunner
    foreground_command_runner: ForegroundCommandRunner
    clipboard_command_reader: CommandOutputReader
    environment_variable: EnvironmentVariableReader
    text_file_reader: TextFileReader
    clipboard_fallbacks: tuple[ClipboardFallback, ...]
    clipboard_readers: tuple[ClipboardReader, ...]
    terminal_command_templates: TerminalConfig
    editor_command_template: EditorConfig
    gui_editor_command_template: GuiEditorConfig


@dataclass(frozen=True)
class BasePlatformLaunchAdapter:
    """Common external launch behavior with platform-specific candidate hooks."""

    context: PlatformAdapterContext

    @property
    def platform_kind(self) -> PlatformKind:
        raise NotImplementedError

    def open_with_default_app(self, path: str) -> None:
        resolved_path = _resolve_existing_path(path)
        cwd = str(resolved_path if resolved_path.is_dir() else resolved_path.parent)
        self._run_first_available(
            self.default_app_candidates(str(resolved_path)),
            context=f"open {resolved_path}",
            cwd=cwd,
        )

    def open_in_editor(self, path: str, line_number: int | None = None) -> None:
        resolved_path = _resolve_existing_path(path)
        candidates = self._editor_candidates(str(resolved_path), line_number)
        errors: list[str] = []
        for command in candidates:
            try:
                self.context.foreground_command_runner(command, str(resolved_path.parent))
                return
            except OSError as error:
                errors.append(str(error) or f"{command[0]} failed")

        raise OSError(errors[-1] if errors else f"Failed to open {resolved_path} in editor")

    def open_in_gui_editor(
        self,
        path: str,
        line_number: int | None = None,
        column_number: int | None = None,
    ) -> None:
        resolved_path = _resolve_existing_path(path)
        cwd = str(resolved_path if resolved_path.is_dir() else resolved_path.parent)
        self._run_first_available(
            self._gui_editor_commands(
                str(resolved_path),
                line_number=line_number,
                column_number=column_number,
            ),
            context=f"open {resolved_path} in GUI editor",
            cwd=cwd,
        )

    def open_terminal(
        self,
        path: str,
        launch_mode: Literal["window", "foreground"] = "window",
    ) -> None:
        resolved_path = _resolve_directory_path(path)
        if launch_mode == "foreground":
            command = self._foreground_terminal_command()
            self.context.foreground_command_runner(command, str(resolved_path))
            return

        self._run_first_available(
            self.terminal_candidates(str(resolved_path)),
            context=f"open terminal in {resolved_path}",
            cwd=str(resolved_path),
        )

    def copy_to_clipboard(self, text: str) -> None:
        available_candidates = [
            command
            for command in self.clipboard_candidates()
            if self.context.command_available(command[0]) is not None
        ]
        if available_candidates:
            self._run_first_available(
                tuple(available_candidates),
                context="copy to clipboard",
                input_text=text,
            )
            return

        fallback_errors: list[str] = []
        for fallback in self.context.clipboard_fallbacks:
            try:
                fallback(text)
                return
            except OSError as error:
                fallback_errors.append(str(error) or "clipboard fallback failed")

        if fallback_errors:
            raise OSError(fallback_errors[-1])
        raise OSError("No supported command found to copy to clipboard")

    def get_from_clipboard(self) -> str:
        available_candidates = [
            command
            for command in self.clipboard_read_candidates()
            if self._command_exists(command[0])
        ]
        if available_candidates:
            return self._read_first_available(tuple(available_candidates))

        fallback_errors: list[str] = []
        for reader in self.context.clipboard_readers:
            try:
                return reader()
            except OSError as error:
                fallback_errors.append(str(error) or "clipboard reader failed")

        if fallback_errors:
            raise OSError(fallback_errors[-1])
        raise OSError("No supported command found to read from clipboard")

    def default_app_candidates(self, path: str) -> tuple[tuple[str, ...], ...]:
        raise NotImplementedError

    def terminal_candidates(self, path: str) -> tuple[tuple[str, ...], ...]:
        return self._configured_terminal_commands(path) + self.default_terminal_candidates(path)

    def default_terminal_candidates(self, path: str) -> tuple[tuple[str, ...], ...]:
        raise NotImplementedError

    def run_in_terminal_window(self, cwd: str, command: tuple[str, ...]) -> None:
        """Run a command in a new terminal window with a shell prompt after completion."""
        raise NotImplementedError

    def clipboard_candidates(self) -> tuple[tuple[str, ...], ...]:
        raise NotImplementedError

    def clipboard_read_candidates(self) -> tuple[tuple[str, ...], ...]:
        raise NotImplementedError

    def _run_first_available(
        self,
        candidates: tuple[tuple[str, ...], ...],
        *,
        context: str,
        cwd: str | None = None,
        input_text: str | None = None,
    ) -> None:
        available_candidates = [
            command for command in candidates if self._command_exists(command[0])
        ]
        if not available_candidates:
            raise OSError(f"No supported command found to {context}")

        errors: list[str] = []
        for command in available_candidates:
            try:
                self.context.command_runner(command, cwd, input_text)
                return
            except OSError as error:
                errors.append(str(error) or f"{command[0]} failed")

        raise OSError(errors[-1] if errors else f"Failed to {context}")

    def _read_first_available(self, candidates: tuple[tuple[str, ...], ...]) -> str:
        errors: list[str] = []
        for command in candidates:
            try:
                return self.context.clipboard_command_reader(command)
            except OSError as error:
                errors.append(str(error) or f"{command[0]} failed")

        raise OSError(errors[-1] if errors else "Failed to read from clipboard")

    def _editor_candidates(
        self,
        path: str,
        line_number: int | None = None,
    ) -> tuple[tuple[str, ...], ...]:
        editor_commands = [
            command
            for command in self._terminal_editor_commands(path, line_number)
            if self._command_exists(command[0])
        ]
        if not editor_commands:
            raise OSError("No supported terminal editor found")
        return tuple(editor_commands)

    def _terminal_editor_commands(
        self,
        path: str,
        line_number: int | None = None,
    ) -> tuple[tuple[str, ...], ...]:
        is_windows = self.platform_kind == "windows"
        commands: list[tuple[str, ...]] = []

        configured_editor_command = self.context.editor_command_template.command
        if configured_editor_command:
            candidate = _build_command_candidate(
                tuple(shlex.split(configured_editor_command, posix=not is_windows)),
                path,
                line_number,
            )
            if candidate is not None:
                commands.append(candidate)

        editor_command = self.context.environment_variable("EDITOR")
        if editor_command:
            try:
                parsed_command = tuple(shlex.split(editor_command, posix=not is_windows))
            except ValueError as error:
                raise OSError(f"Invalid EDITOR value: {error}") from error
            candidate = _build_command_candidate(parsed_command, path, line_number)
            if candidate is not None:
                commands.append(candidate)

        commands.extend(self._default_terminal_editor_commands(path, line_number))
        return _dedupe_commands(commands)

    def _default_terminal_editor_commands(
        self,
        path: str,
        line_number: int | None = None,
    ) -> tuple[tuple[str, ...], ...]:
        if line_number is not None:
            commands = (
                ("nvim", f"+{line_number}", path),
                ("vim", f"+{line_number}", path),
                ("nano", f"+{line_number}", path),
                ("hx", f"+{line_number}", path),
                ("micro", f"+{line_number}", path),
                ("emacs", "-nw", f"+{line_number}", path),
            )
        else:
            commands = (
                ("nvim", path),
                ("vim", path),
                ("nano", path),
                ("hx", path),
                ("micro", path),
                ("emacs", "-nw", path),
            )
        if self.platform_kind == "windows":
            edit_command = ("edit", f"{path}:{line_number}") if line_number is not None else (
                "edit",
                path,
            )
            commands = commands + (edit_command,)
        return commands

    def _command_exists(self, command: str) -> bool:
        command_path = Path(command)
        if command_path.is_absolute():
            return command_path.exists()
        return self.context.command_available(command) is not None

    def _foreground_terminal_command(self) -> tuple[str, ...]:
        if self.platform_kind == "windows":
            powershell = self.context.command_available("powershell.exe")
            if powershell is not None:
                return (powershell, "-NoExit", "-NoLogo")
            return ("cmd.exe", "/k")

        shell = self.context.environment_variable("SHELL")
        if shell:
            try:
                parsed = tuple(shlex.split(shell))
            except ValueError as error:
                raise OSError(f"Invalid SHELL value: {error}") from error
            if parsed and self._command_exists(parsed[0]):
                return (*parsed, "-i")
        if self._command_exists("/bin/bash"):
            return ("/bin/bash", "-i")
        raise OSError("No supported interactive shell found for foreground terminal mode")

    def _configured_terminal_commands(self, path: str) -> tuple[tuple[str, ...], ...]:
        template_keys = _PLATFORM_TEMPLATE_KEYS[self.platform_kind]
        template_map = {
            "linux": self.context.terminal_command_templates.linux,
            "macos": self.context.terminal_command_templates.macos,
            "windows": self.context.terminal_command_templates.windows,
        }
        commands: list[tuple[str, ...]] = []
        for key in template_keys:
            for template in template_map[key]:
                try:
                    rendered = template.format(path=_render_template_path(path, key))
                    parsed_command = tuple(shlex.split(rendered, posix=key != "windows"))
                except (IndexError, KeyError, ValueError):
                    continue
                if parsed_command:
                    commands.append(parsed_command)
        return _dedupe_commands(commands)

    def _gui_editor_commands(
        self,
        path: str,
        *,
        line_number: int | None = None,
        column_number: int | None = None,
    ) -> tuple[tuple[str, ...], ...]:
        config = self.context.gui_editor_command_template
        commands: list[tuple[str, ...]] = []
        if line_number is not None:
            commands.append(
                _render_gui_editor_template(
                    config.command,
                    path,
                    line_number=line_number,
                    column_number=column_number,
                    platform_kind=self.platform_kind,
                )
            )
            if config.fallback_command:
                commands.append(
                    _render_gui_editor_template(
                        config.fallback_command,
                        path,
                        line_number=line_number,
                        column_number=column_number,
                        platform_kind=self.platform_kind,
                    )
                )
        else:
            if config.fallback_command:
                commands.append(
                    _render_gui_editor_template(
                        config.fallback_command,
                        path,
                        line_number=1,
                        column_number=1,
                        platform_kind=self.platform_kind,
                    )
                )
            if config.command:
                commands.append(
                    _render_gui_editor_template(
                        config.command,
                        path,
                        line_number=1,
                        column_number=1,
                        platform_kind=self.platform_kind,
                    )
                )
        return _dedupe_commands(tuple(command for command in commands if command))


def _resolve_existing_path(path: str) -> Path:
    resolved_path = Path(path).expanduser().resolve()
    if not resolved_path.exists():
        raise OSError(f"Not found: {resolved_path}")
    return resolved_path


def _resolve_directory_path(path: str) -> Path:
    resolved_path = _resolve_existing_path(path)
    if not resolved_path.is_dir():
        raise OSError(f"Not a directory: {resolved_path}")
    return resolved_path


def _render_template_path(path: str, template_key: str) -> str:
    if template_key == "windows":
        import subprocess

        return subprocess.list2cmdline([path])
    return shlex.quote(path)


def _render_gui_editor_template(
    template: str,
    path: str,
    *,
    line_number: int,
    column_number: int | None,
    platform_kind: PlatformKind,
) -> tuple[str, ...]:
    if not template.strip():
        return ()
    template_key = "windows" if platform_kind == "windows" else "linux"
    rendered = template.format(
        path=_render_template_path(path, template_key),
        line=max(1, line_number),
        column=max(1, column_number or 1),
    )
    return tuple(shlex.split(rendered, posix=platform_kind != "windows"))


def _windows_set_location_command(path: str) -> str:
    escaped_path = path.replace("'", "''")
    return f"Set-Location -LiteralPath '{escaped_path}'"


def _windows_cd_command(path: str) -> str:
    escaped_path = path.replace('"', '""')
    return f'cd /d "{escaped_path}"'


def _is_terminal_editor_command(command: str) -> bool:
    return Path(command).name.casefold() in TERMINAL_EDITOR_NAMES


def _build_command_candidate(
    parsed_command: tuple[str, ...],
    path: str,
    line_number: int | None = None,
) -> tuple[str, ...] | None:
    if not parsed_command or not _is_terminal_editor_command(parsed_command[0]):
        return None
    if line_number is not None:
        editor_name = Path(parsed_command[0]).name.casefold()
        if editor_name in EMBEDDED_LINE_NUMBER_EDITOR_NAMES:
            return parsed_command + (f"{path}:{line_number}",)
        return parsed_command + (f"+{line_number}", path)
    return parsed_command + (path,)


def _dedupe_commands(commands: Sequence[tuple[str, ...]]) -> tuple[tuple[str, ...], ...]:
    seen: set[tuple[str, ...]] = set()
    unique_commands: list[tuple[str, ...]] = []
    for command in commands:
        if command in seen:
            continue
        seen.add(command)
        unique_commands.append(command)
    return tuple(unique_commands)


def is_wsl_environment(
    environment_variable: EnvironmentVariableReader,
    text_file_reader: TextFileReader,
) -> bool:
    if environment_variable("WSL_DISTRO_NAME") is not None:
        return True
    if environment_variable("WSL_INTEROP") is not None:
        return True

    try:
        proc_version = text_file_reader("/proc/version")
    except OSError:
        return False
    return "microsoft" in proc_version.casefold()
