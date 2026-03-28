"""OS adapter for launching default applications, terminals, and clipboard commands."""

import os
import platform
import shlex
import shutil
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

from peneo.models import EditorConfig, TerminalConfig

CommandRunner = Callable[[Sequence[str], str | None, str | None], None]
ForegroundCommandRunner = Callable[[Sequence[str], str | None], None]
CommandAvailability = Callable[[str], str | None]
SystemNameResolver = Callable[[], str]
ClipboardFallback = Callable[[str], None]
EnvironmentVariableReader = Callable[[str], str | None]
TextFileReader = Callable[[str], str]
PlatformKind = Literal["linux", "wsl", "darwin"]
TERMINAL_EDITOR_NAMES = frozenset(
    {"emacs", "helix", "hx", "kak", "micro", "nano", "nvim", "vi", "vim"}
)


class ExternalLaunchAdapter(Protocol):
    """Boundary for external process launches."""

    def open_with_default_app(self, path: str) -> None: ...

    def open_in_editor(self, path: str) -> None: ...

    def open_terminal(self, path: str) -> None: ...

    def copy_to_clipboard(self, text: str) -> None: ...


@dataclass(frozen=True)
class LocalExternalLaunchAdapter:
    """Launch applications and terminals via OS-specific commands."""

    system_name_resolver: SystemNameResolver = platform.system
    command_available: CommandAvailability = shutil.which
    command_runner: CommandRunner = field(default_factory=lambda: _run_detached_command)
    foreground_command_runner: ForegroundCommandRunner = field(
        default_factory=lambda: _run_foreground_command
    )
    environment_variable: EnvironmentVariableReader = field(
        default_factory=lambda: os.environ.get
    )
    text_file_reader: TextFileReader = field(default_factory=lambda: _read_text_file)
    clipboard_fallbacks: tuple[ClipboardFallback, ...] = field(
        default_factory=lambda: (_copy_to_clipboard_with_tkinter,)
    )
    terminal_command_templates: TerminalConfig = field(default_factory=TerminalConfig)
    editor_command_template: EditorConfig = field(default_factory=EditorConfig)

    def open_with_default_app(self, path: str) -> None:
        resolved_path = _resolve_existing_path(path)
        platform_kind = self._platform_kind()
        candidates = self._default_app_candidates(platform_kind, str(resolved_path))
        cwd = str(resolved_path if resolved_path.is_dir() else resolved_path.parent)
        self._run_first_available(candidates, context=f"open {resolved_path}", cwd=cwd)

    def open_in_editor(self, path: str) -> None:
        resolved_path = _resolve_existing_path(path)
        candidates = self._editor_candidates(str(resolved_path))
        errors: list[str] = []
        for command in candidates:
            try:
                self.foreground_command_runner(command, str(resolved_path.parent))
                return
            except OSError as error:
                errors.append(str(error) or f"{command[0]} failed")

        raise OSError(errors[-1] if errors else f"Failed to open {resolved_path} in editor")

    def open_terminal(self, path: str) -> None:
        resolved_path = _resolve_directory_path(path)
        candidates = self._terminal_candidates(self._platform_kind(), str(resolved_path))
        self._run_first_available(
            candidates,
            context=f"open terminal in {resolved_path}",
            cwd=str(resolved_path),
        )

    def copy_to_clipboard(self, text: str) -> None:
        candidates = self._clipboard_candidates(self._platform_kind())
        available_candidates = [
            command for command in candidates if self.command_available(command[0]) is not None
        ]
        if available_candidates:
            self._run_first_available(
                available_candidates,
                context="copy to clipboard",
                input_text=text,
            )
            return

        fallback_errors: list[str] = []
        for fallback in self.clipboard_fallbacks:
            try:
                fallback(text)
                return
            except OSError as error:
                fallback_errors.append(str(error) or "clipboard fallback failed")

        if fallback_errors:
            raise OSError(fallback_errors[-1])
        raise OSError("No supported command found to copy to clipboard")

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
                self.command_runner(command, cwd, input_text)
                return
            except OSError as error:
                errors.append(str(error) or f"{command[0]} failed")

        raise OSError(errors[-1] if errors else f"Failed to {context}")

    def _platform_kind(self) -> PlatformKind:
        system_name = self.system_name_resolver()
        if system_name == "Darwin":
            return "darwin"
        if system_name == "Linux":
            if _is_wsl_environment(self.environment_variable, self.text_file_reader):
                return "wsl"
            return "linux"
        if system_name == "Windows":
            raise OSError("Windows native is unsupported; run Peneo from WSL")
        raise OSError(f"Unsupported operating system: {system_name}")

    def _default_app_candidates(
        self,
        platform_kind: PlatformKind,
        path: str,
    ) -> tuple[tuple[str, ...], ...]:
        if platform_kind == "linux":
            return (
                ("xdg-open", path),
                ("gio", "open", path),
            )
        if platform_kind == "wsl":
            return (
                ("wslview", path),
                ("explorer.exe", path),
                ("xdg-open", path),
                ("gio", "open", path),
            )
        if platform_kind == "darwin":
            return (("open", path),)
        raise OSError(f"Unsupported platform kind: {platform_kind}")

    def _editor_candidates(self, path: str) -> tuple[tuple[str, ...], ...]:
        editor_commands = [
            command
            for command in self._terminal_editor_commands(path)
            if self._command_exists(command[0])
        ]
        if not editor_commands:
            raise OSError("No supported terminal editor found")

        return tuple(editor_commands)

    def _terminal_editor_commands(self, path: str) -> tuple[tuple[str, ...], ...]:
        commands: list[tuple[str, ...]] = []
        configured_editor_command = self.editor_command_template.command
        if configured_editor_command:
            parsed_command = tuple(shlex.split(configured_editor_command))
            if parsed_command and _is_terminal_editor_command(parsed_command[0]):
                commands.append(parsed_command + (path,))

        editor_command = self.environment_variable("EDITOR")
        if editor_command:
            try:
                parsed_command = tuple(shlex.split(editor_command))
            except ValueError as error:
                raise OSError(f"Invalid EDITOR value: {error}") from error
            if parsed_command and _is_terminal_editor_command(parsed_command[0]):
                commands.append(parsed_command + (path,))

        commands.extend(self._default_terminal_editor_commands(path))
        return _dedupe_commands(commands)

    def _default_terminal_editor_commands(self, path: str) -> tuple[tuple[str, ...], ...]:
        platform_kind = self._platform_kind()
        if platform_kind in {"linux", "wsl", "darwin"}:
            return (
                ("nvim", path),
                ("vim", path),
                ("nano", path),
                ("hx", path),
                ("micro", path),
                ("emacs", "-nw", path),
            )
        raise OSError(f"Unsupported platform kind: {platform_kind}")

    def _command_exists(self, command: str) -> bool:
        command_path = Path(command)
        if command_path.is_absolute():
            return command_path.exists()
        return self.command_available(command) is not None

    def _terminal_candidates(
        self,
        platform_kind: PlatformKind,
        path: str,
    ) -> tuple[tuple[str, ...], ...]:
        configured_commands = self._configured_terminal_commands(platform_kind, path)
        if platform_kind == "linux":
            return configured_commands + (
                ("kgx",),
                ("gnome-console",),
                ("gnome-terminal",),
                ("xfce4-terminal",),
                ("mate-terminal",),
                ("tilix",),
                ("konsole",),
                ("lxterminal",),
                ("x-terminal-emulator",),
                ("xterm",),
            )
        if platform_kind == "wsl":
            return configured_commands + (
                ("wt.exe", "wsl.exe", "--cd", path),
                ("cmd.exe", "/c", "start", "", "wsl.exe", "--cd", path),
                ("kgx",),
                ("gnome-console",),
                ("gnome-terminal",),
                ("xfce4-terminal",),
                ("mate-terminal",),
                ("tilix",),
                ("konsole",),
                ("lxterminal",),
                ("x-terminal-emulator",),
                ("xterm",),
            )
        if platform_kind == "darwin":
            return configured_commands + (("open", "-a", "Terminal", path),)
        raise OSError(f"Unsupported platform kind: {platform_kind}")

    def _configured_terminal_commands(
        self,
        platform_kind: PlatformKind,
        path: str,
    ) -> tuple[tuple[str, ...], ...]:
        templates: list[str] = []
        if platform_kind == "linux":
            templates.extend(self.terminal_command_templates.linux)
        elif platform_kind == "darwin":
            templates.extend(self.terminal_command_templates.macos)
        elif platform_kind == "wsl":
            templates.extend(self.terminal_command_templates.windows)
            templates.extend(self.terminal_command_templates.linux)

        commands: list[tuple[str, ...]] = []
        for template in templates:
            try:
                rendered = template.format(path=path)
                parsed_command = tuple(shlex.split(rendered))
            except (IndexError, KeyError, ValueError):
                continue
            if parsed_command:
                commands.append(parsed_command)
        return _dedupe_commands(commands)

    def _clipboard_candidates(self, platform_kind: PlatformKind) -> tuple[tuple[str, ...], ...]:
        if platform_kind == "linux":
            return (
                ("wl-copy",),
                ("xclip", "-in", "-selection", "clipboard"),
                ("xsel", "--clipboard", "--input"),
            )
        if platform_kind == "wsl":
            return (
                ("clip.exe",),
                ("wl-copy",),
                ("xclip", "-in", "-selection", "clipboard"),
                ("xsel", "--clipboard", "--input"),
            )
        if platform_kind == "darwin":
            return (("pbcopy",),)
        raise OSError(f"Unsupported platform kind: {platform_kind}")


def _run_detached_command(command: Sequence[str], cwd: str | None, input_text: str | None) -> None:
    if input_text is not None:
        try:
            subprocess.run(
                list(command),
                input=input_text,
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                cwd=cwd,
                check=True,
            )
        except subprocess.CalledProcessError as error:
            detail = (error.stderr or "").strip() or str(error)
            raise OSError(detail) from error
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
        )
    except subprocess.CalledProcessError as error:
        raise OSError(str(error) or f"{command[0]} failed") from error


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


def _read_text_file(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


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


def _is_terminal_editor_command(command: str) -> bool:
    return Path(command).name.casefold() in TERMINAL_EDITOR_NAMES


def _dedupe_commands(commands: Sequence[tuple[str, ...]]) -> tuple[tuple[str, ...], ...]:
    seen: set[tuple[str, ...]] = set()
    unique_commands: list[tuple[str, ...]] = []
    for command in commands:
        if command in seen:
            continue
        seen.add(command)
        unique_commands.append(command)
    return tuple(unique_commands)


def _is_wsl_environment(
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
