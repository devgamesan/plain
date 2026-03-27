"""OS adapter for launching default applications, terminals, and clipboard commands."""

import os
import platform
import shlex
import shutil
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

CommandRunner = Callable[[Sequence[str], str | None, str | None], None]
ForegroundCommandRunner = Callable[[Sequence[str], str | None], None]
CommandAvailability = Callable[[str], str | None]
SystemNameResolver = Callable[[], str]
ClipboardFallback = Callable[[str], None]
EnvironmentVariableReader = Callable[[str], str | None]
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
    clipboard_fallbacks: tuple[ClipboardFallback, ...] = field(
        default_factory=lambda: (_copy_to_clipboard_with_tkinter,)
    )

    def open_with_default_app(self, path: str) -> None:
        resolved_path = _resolve_existing_path(path)
        candidates = self._default_app_candidates(str(resolved_path))
        self._run_first_available(candidates, context=f"open {resolved_path}")

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
        candidates = self._terminal_candidates(str(resolved_path))
        self._run_first_available(
            candidates,
            context=f"open terminal in {resolved_path}",
            cwd=str(resolved_path),
        )

    def copy_to_clipboard(self, text: str) -> None:
        candidates = self._clipboard_candidates()
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
            command for command in candidates if self.command_available(command[0]) is not None
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

    def _default_app_candidates(self, path: str) -> tuple[tuple[str, ...], ...]:
        system_name = self.system_name_resolver()
        if system_name == "Linux":
            return (("xdg-open", path),)
        if system_name == "Darwin":
            return (("open", path),)
        if system_name == "Windows":
            return (("cmd", "/c", "start", "", path),)
        raise OSError(f"Unsupported operating system: {system_name}")

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
        system_name = self.system_name_resolver()
        if system_name in {"Linux", "Darwin", "Windows"}:
            return (
                ("nvim", path),
                ("vim", path),
                ("nano", path),
                ("hx", path),
                ("micro", path),
                ("emacs", "-nw", path),
            )
        raise OSError(f"Unsupported operating system: {system_name}")

    def _command_exists(self, command: str) -> bool:
        command_path = Path(command)
        if command_path.is_absolute():
            return command_path.exists()
        return self.command_available(command) is not None

    def _terminal_candidates(self, path: str) -> tuple[tuple[str, ...], ...]:
        system_name = self.system_name_resolver()
        if system_name == "Linux":
            return (
                ("konsole",),
                ("gnome-terminal",),
                ("xfce4-terminal",),
                ("xterm",),
                ("x-terminal-emulator",),
            )
        if system_name == "Darwin":
            return (("open", "-a", "Terminal", path),)
        if system_name == "Windows":
            escaped_path = path.replace("'", "''")
            powershell_command = f"Set-Location -LiteralPath '{escaped_path}'"
            return (
                ("cmd", "/c", "start", "", "wt", "-d", path),
                (
                    "cmd",
                    "/c",
                    "start",
                    "",
                    "powershell",
                    "-NoExit",
                    "-Command",
                    powershell_command,
                ),
            )
        raise OSError(f"Unsupported operating system: {system_name}")

    def _clipboard_candidates(self) -> tuple[tuple[str, ...], ...]:
        system_name = self.system_name_resolver()
        if system_name == "Linux":
            return (
                ("wl-copy",),
                ("xclip", "-in", "-selection", "clipboard"),
                ("xsel", "--clipboard", "--input"),
            )
        if system_name == "Darwin":
            return (("pbcopy",),)
        if system_name == "Windows":
            return (("clip",),)
        raise OSError(f"Unsupported operating system: {system_name}")


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
