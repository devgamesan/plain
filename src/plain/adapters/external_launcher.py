"""OS adapter for launching default applications, terminals, and clipboard commands."""

import platform
import shutil
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

CommandRunner = Callable[[Sequence[str], str | None, str | None], None]
CommandAvailability = Callable[[str], str | None]
SystemNameResolver = Callable[[], str]
ClipboardFallback = Callable[[str], None]


class ExternalLaunchAdapter(Protocol):
    """Boundary for external process launches."""

    def open_with_default_app(self, path: str) -> None: ...

    def open_terminal(self, path: str) -> None: ...

    def copy_to_clipboard(self, text: str) -> None: ...


@dataclass(frozen=True)
class LocalExternalLaunchAdapter:
    """Launch applications and terminals via OS-specific commands."""

    system_name_resolver: SystemNameResolver = platform.system
    command_available: CommandAvailability = shutil.which
    command_runner: CommandRunner = field(default_factory=lambda: _run_detached_command)
    clipboard_fallbacks: tuple[ClipboardFallback, ...] = field(
        default_factory=lambda: (_copy_to_clipboard_with_tkinter,)
    )

    def open_with_default_app(self, path: str) -> None:
        resolved_path = _resolve_existing_path(path)
        candidates = self._default_app_candidates(str(resolved_path))
        self._run_first_available(candidates, context=f"open {resolved_path}")

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
