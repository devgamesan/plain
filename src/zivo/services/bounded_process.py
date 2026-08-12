"""Bounded non-interactive subprocess execution shared by command services."""

from __future__ import annotations

import locale
import os
import signal
import subprocess
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from time import monotonic, sleep
from typing import BinaryIO

from zivo.models import CommandTerminationReason, ShellCommandResult

CancelCallback = Callable[[], bool]
_READ_CHUNK_BYTES = 64 * 1024
_POLL_INTERVAL_SECONDS = 0.02
_TERMINATION_GRACE_SECONDS = 1.0
_OMISSION_MARKER = b"\n[... middle output omitted ...]\n"


@dataclass
class _BoundedStreamBuffer:
    limit: int

    def __post_init__(self) -> None:
        self._prefix_limit = (self.limit + 1) // 2
        self._suffix_limit = self.limit - self._prefix_limit
        self._prefix = bytearray()
        self._suffix = bytearray()
        self.total_bytes = 0

    def append(self, chunk: bytes) -> None:
        if not chunk:
            return
        self.total_bytes += len(chunk)
        prefix_remaining = self._prefix_limit - len(self._prefix)
        if prefix_remaining > 0:
            prefix_part = chunk[:prefix_remaining]
            self._prefix.extend(prefix_part)
            chunk = chunk[len(prefix_part) :]
        if not chunk or self._suffix_limit == 0:
            return
        self._suffix.extend(chunk)
        if len(self._suffix) > self._suffix_limit:
            del self._suffix[: len(self._suffix) - self._suffix_limit]

    @property
    def truncated(self) -> bool:
        return self.total_bytes > self.limit

    def value(self) -> bytes:
        if not self.truncated:
            return bytes(self._prefix) + bytes(self._suffix)
        return bytes(self._prefix) + _OMISSION_MARKER + bytes(self._suffix)


def run_bounded_process(
    command: Sequence[str],
    *,
    cwd: str,
    env: Mapping[str, str],
    max_output_bytes: int,
    timeout_seconds: int,
    cancel_callback: CancelCallback | None = None,
    os_name: str = os.name,
) -> ShellCommandResult:
    """Run a non-interactive command while bounding retained output and time."""

    if max_output_bytes < 1:
        raise ValueError("max_output_bytes must be positive")
    if timeout_seconds < 1:
        raise ValueError("timeout_seconds must be positive")

    popen_kwargs: dict[str, object] = {
        "cwd": cwd,
        "env": dict(env),
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": False,
    }
    if os_name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs["start_new_session"] = True

    process = subprocess.Popen(list(command), **popen_kwargs)
    stdout_buffer = _BoundedStreamBuffer(max_output_bytes)
    stderr_buffer = _BoundedStreamBuffer(max_output_bytes)
    stdout_thread = _start_reader(process.stdout, stdout_buffer, "stdout")
    stderr_thread = _start_reader(process.stderr, stderr_buffer, "stderr")

    started_at = monotonic()
    reason: CommandTerminationReason = "completed"
    while process.poll() is None:
        if cancel_callback is not None and cancel_callback():
            if process.poll() is not None:
                break
            reason = "cancelled"
            _stop_process(process, os_name=os_name)
            break
        if monotonic() - started_at >= timeout_seconds:
            if process.poll() is not None:
                break
            reason = "timed_out"
            _stop_process(process, os_name=os_name)
            break
        sleep(_POLL_INTERVAL_SECONDS)

    _finish_process(process)
    _finish_reader(stdout_thread, process.stdout)
    _finish_reader(stderr_thread, process.stderr)

    encoding = locale.getpreferredencoding(False)
    return ShellCommandResult(
        exit_code=process.returncode if process.returncode is not None else -1,
        stdout=stdout_buffer.value().decode(encoding, errors="replace"),
        stderr=stderr_buffer.value().decode(encoding, errors="replace"),
        stdout_truncated=stdout_buffer.truncated,
        stderr_truncated=stderr_buffer.truncated,
        termination_reason=reason,
        output_limit_bytes=max_output_bytes,
        timeout_seconds=timeout_seconds,
    )


def _start_reader(
    stream: BinaryIO | None,
    buffer: _BoundedStreamBuffer,
    stream_name: str,
) -> threading.Thread | None:
    if stream is None:
        return None

    def drain() -> None:
        try:
            while chunk := stream.read(_READ_CHUNK_BYTES):
                buffer.append(chunk)
        except (OSError, ValueError):
            return

    thread = threading.Thread(
        target=drain,
        name=f"bounded-process-{stream_name}",
        daemon=True,
    )
    thread.start()
    return thread


def _stop_process(process: subprocess.Popen[bytes], *, os_name: str) -> None:
    if process.poll() is not None:
        return
    try:
        if os_name == "nt":
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            os.killpg(process.pid, signal.SIGTERM)
    except (OSError, ProcessLookupError):
        try:
            process.terminate()
        except OSError:
            pass
    try:
        process.wait(timeout=_TERMINATION_GRACE_SECONDS)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        if os_name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                check=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            os.killpg(process.pid, signal.SIGKILL)
    except (OSError, ProcessLookupError):
        try:
            process.kill()
        except OSError:
            pass


def _finish_process(process: subprocess.Popen[bytes]) -> None:
    try:
        process.wait(timeout=_TERMINATION_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
        except OSError:
            pass
        try:
            process.wait(timeout=_TERMINATION_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            return


def _finish_reader(thread: threading.Thread | None, stream: BinaryIO | None) -> None:
    if thread is None:
        return
    thread.join(timeout=_TERMINATION_GRACE_SECONDS)
    if thread.is_alive() and stream is not None:
        try:
            stream.close()
        except OSError:
            pass
        thread.join(timeout=_TERMINATION_GRACE_SECONDS)
