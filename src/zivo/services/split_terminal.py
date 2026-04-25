"""Embedded split-terminal session services."""

from __future__ import annotations

import os
import shlex
import struct
import subprocess
import sys
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from time import sleep
from typing import Protocol

if sys.platform != "win32":
    import pty
    import select
    import termios
else:
    pty = None  # type: ignore[assignment]
    select = None  # type: ignore[assignment]
    termios = None  # type: ignore[assignment]

SplitTerminalOutputHandler = Callable[[str], None]
SplitTerminalExitHandler = Callable[[int | None], None]


class SplitTerminalSession(Protocol):
    """Long-lived interactive shell session."""

    def close(self) -> None: ...

    def resize(self, *, columns: int, rows: int) -> None: ...

    def write(self, data: str) -> None: ...


class SplitTerminalService(Protocol):
    """Boundary for starting embedded terminal sessions."""

    def start(
        self,
        cwd: str,
        *,
        on_output: SplitTerminalOutputHandler,
        on_exit: SplitTerminalExitHandler,
    ) -> SplitTerminalSession: ...


@dataclass(frozen=True)
class LiveSplitTerminalService:
    """Start PTY-backed interactive shells for the split terminal."""

    shell_command: tuple[str, ...] | None = None
    extra_env: Mapping[str, str] = field(default_factory=dict)

    def start(
        self,
        cwd: str,
        *,
        on_output: SplitTerminalOutputHandler,
        on_exit: SplitTerminalExitHandler,
    ) -> SplitTerminalSession:
        if os.name != "posix":
            raise OSError("Split terminal is currently supported only on POSIX platforms")

        resolved_cwd = str(Path(cwd).expanduser().resolve())
        if not Path(resolved_cwd).is_dir():
            raise OSError(f"Split terminal requires a directory: {resolved_cwd}")

        command = self.shell_command or _default_shell_command()
        env = dict(os.environ)
        env.update(self.extra_env)

        master_fd, slave_fd = pty.openpty()
        try:
            process = subprocess.Popen(
                command,
                cwd=resolved_cwd,
                env=env,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                start_new_session=True,
                close_fds=True,
            )
        except Exception:
            os.close(master_fd)
            os.close(slave_fd)
            raise

        os.close(slave_fd)
        session = _PtySplitTerminalSession(
            process=process,
            master_fd=master_fd,
            on_output=on_output,
            on_exit=on_exit,
        )
        session.start()
        return session


@dataclass
class FakeSplitTerminalSession:
    """Deterministic split-terminal session for tests."""

    cwd: str
    on_output: SplitTerminalOutputHandler
    on_exit: SplitTerminalExitHandler
    writes: list[str] = field(default_factory=list)
    close_count: int = 0
    resize_calls: list[tuple[int, int]] = field(default_factory=list)

    def write(self, data: str) -> None:
        self.writes.append(data)

    def resize(self, *, columns: int, rows: int) -> None:
        self.resize_calls.append((columns, rows))

    def close(self) -> None:
        self.close_count += 1
        self.on_exit(0)

    def emit_output(self, data: str) -> None:
        self.on_output(data)

    def finish(self, exit_code: int | None = 0) -> None:
        self.on_exit(exit_code)


@dataclass(frozen=True)
class FakeSplitTerminalService:
    """Fake split-terminal starter used by UI tests."""

    failure_message: str | None = None
    default_delay_seconds: float = 0.0
    started_cwds: list[str] = field(default_factory=list)
    sessions: list[FakeSplitTerminalSession] = field(default_factory=list)

    def start(
        self,
        cwd: str,
        *,
        on_output: SplitTerminalOutputHandler,
        on_exit: SplitTerminalExitHandler,
    ) -> FakeSplitTerminalSession:
        if self.default_delay_seconds > 0:
            sleep(self.default_delay_seconds)
        self.started_cwds.append(cwd)
        if self.failure_message is not None:
            raise OSError(self.failure_message)
        session = FakeSplitTerminalSession(cwd=cwd, on_output=on_output, on_exit=on_exit)
        self.sessions.append(session)
        return session


@dataclass
class _PtySplitTerminalSession:
    """Interactive PTY subprocess plus output reader thread."""

    process: subprocess.Popen[bytes]
    master_fd: int
    on_output: SplitTerminalOutputHandler
    on_exit: SplitTerminalExitHandler
    _closed: threading.Event = field(default_factory=threading.Event)
    _exit_notified: threading.Event = field(default_factory=threading.Event)
    _reader_thread: threading.Thread | None = None

    def start(self) -> None:
        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()

    def write(self, data: str) -> None:
        if self._closed.is_set():
            raise OSError("Split terminal session is closed")
        os.write(self.master_fd, data.encode())

    def resize(self, *, columns: int, rows: int) -> None:
        if self._closed.is_set():
            return
        winsize = struct.pack("HHHH", rows, columns, 0, 0)
        try:
            termios.tcsetwinsize(self.master_fd, (rows, columns))
        except AttributeError:
            import fcntl

            fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)

    def close(self) -> None:
        if self._closed.is_set():
            return
        self._closed.set()
        try:
            self.process.terminate()
        except ProcessLookupError:
            pass
        try:
            self.process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            try:
                self.process.kill()
            except ProcessLookupError:
                pass
        self._close_master_fd()
        self._notify_exit(self.process.poll())

    def _reader_loop(self) -> None:
        try:
            while not self._closed.is_set():
                ready, _, _ = select.select([self.master_fd], [], [], 0.1)
                if self.master_fd in ready:
                    chunks: list[str] = []
                    while True:
                        try:
                            chunk = os.read(self.master_fd, 4096)
                        except OSError:
                            chunk = b""
                        if not chunk:
                            break
                        chunks.append(chunk.decode(errors="replace"))
                        more_ready, _, _ = select.select([self.master_fd], [], [], 0)
                        if self.master_fd not in more_ready:
                            break
                    if chunks:
                        self.on_output("".join(chunks))
                    elif self.process.poll() is not None:
                        break
                if self.process.poll() is not None and not ready:
                    break
        finally:
            self._closed.set()
            self._close_master_fd()
            self._notify_exit(self.process.poll())

    def _close_master_fd(self) -> None:
        try:
            os.close(self.master_fd)
        except OSError:
            pass

    def _notify_exit(self, exit_code: int | None) -> None:
        if self._exit_notified.is_set():
            return
        self._exit_notified.set()
        self.on_exit(exit_code)


def _default_shell_command() -> tuple[str, ...]:
    shell = os.environ.get("SHELL")
    if shell:
        parsed = tuple(shlex.split(shell))
        if parsed:
            return (*parsed, "-i")
    return ("/bin/bash", "-i")
