import os
import sys
from pathlib import Path
from time import monotonic

from zivo.services.bounded_process import run_bounded_process


def _run_python(tmp_path: Path, source: str, **kwargs):
    return run_bounded_process(
        [sys.executable, "-c", source],
        cwd=str(tmp_path),
        env=os.environ,
        max_output_bytes=kwargs.pop("max_output_bytes", 1024),
        timeout_seconds=kwargs.pop("timeout_seconds", 5),
        **kwargs,
    )


def test_bounded_process_captures_normal_output_and_closes_stdin(tmp_path: Path) -> None:
    result = _run_python(
        tmp_path,
        "import sys; data=sys.stdin.read(); print(f'stdin={data!r}'); "
        "print('warning', file=sys.stderr)",
    )

    assert result.exit_code == 0
    assert result.stdout == "stdin=''\n"
    assert result.stderr == "warning\n"
    assert result.termination_reason == "completed"
    assert result.stdout_truncated is False
    assert result.stderr_truncated is False


def test_bounded_process_keeps_prefix_and_suffix_for_each_stream(tmp_path: Path) -> None:
    result = _run_python(
        tmp_path,
        "import sys; sys.stdout.write('A'*100+'Z'*100); "
        "sys.stderr.write('B'*100+'Y'*100)",
        max_output_bytes=100,
    )

    assert result.exit_code == 0
    assert result.stdout.startswith("A" * 50)
    assert "middle output omitted" in result.stdout
    assert result.stdout.endswith("Z" * 50)
    assert result.stderr.startswith("B" * 50)
    assert "middle output omitted" in result.stderr
    assert result.stderr.endswith("Y" * 50)
    assert result.stdout_truncated is True
    assert result.stderr_truncated is True
    assert result.output_limit_bytes == 100


def test_bounded_process_times_out_and_returns_partial_output(tmp_path: Path) -> None:
    result = _run_python(
        tmp_path,
        "import time; print('started', flush=True); time.sleep(10)",
        timeout_seconds=1,
    )

    assert result.termination_reason == "timed_out"
    assert result.stdout == "started\n"
    assert result.timeout_seconds == 1


def test_bounded_process_honors_cancel_callback(tmp_path: Path) -> None:
    result = _run_python(
        tmp_path,
        "import time; time.sleep(10)",
        cancel_callback=lambda: True,
    )

    assert result.termination_reason == "cancelled"


def test_bounded_process_escalates_when_terminate_is_ignored(tmp_path: Path) -> None:
    if os.name == "nt":
        return
    started_at = monotonic()

    result = _run_python(
        tmp_path,
        "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        "print('ready', flush=True); time.sleep(10)",
        timeout_seconds=1,
    )

    assert result.termination_reason == "timed_out"
    assert result.stdout == "ready\n"
    assert monotonic() - started_at < 4


def test_bounded_process_replaces_invalid_output_bytes(tmp_path: Path) -> None:
    result = _run_python(
        tmp_path,
        "import os; os.write(1, bytes([255]))",
    )

    assert result.exit_code == 0
    assert "�" in result.stdout


def test_bounded_process_supports_prefix_only_stream_limits_and_stops_writer(
    tmp_path: Path,
) -> None:
    result = _run_python(
        tmp_path,
        "import sys; sys.stdout.write('A'*100000); sys.stderr.write('B'*100000)",
        max_output_bytes=64,
        stdout_max_output_bytes=16,
        stderr_max_output_bytes=24,
        prefix_only=True,
        terminate_on_output_limit=True,
    )

    assert result.termination_reason == "output_limited"
    assert result.stdout.startswith("A")
    assert len(result.stdout) <= 16
    assert result.stderr.startswith("B")
    assert len(result.stderr) <= 24
    assert result.stdout_truncated is True or result.stderr_truncated is True
