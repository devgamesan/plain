import threading
import time

import pytest

from zivo.services import LiveSplitTerminalService


@pytest.mark.skipif(
    condition=__import__("os").name != "posix",
    reason="split terminal PTY behavior is POSIX-only",
)
def test_live_split_terminal_service_starts_and_echoes_input(tmp_path) -> None:
    outputs: list[str] = []
    exit_codes: list[int | None] = []
    exited = threading.Event()
    service = LiveSplitTerminalService(shell_command=("/bin/sh", "-c", "printf READY; cat"))

    session = service.start(
        str(tmp_path),
        on_output=outputs.append,
        on_exit=lambda code: (exit_codes.append(code), exited.set()),
    )
    session.write("hello\n")

    deadline = time.time() + 2
    while "READY" not in "".join(outputs) or "hello" not in "".join(outputs):
        if time.time() >= deadline:
            raise AssertionError(f"split terminal did not echo expected output: {outputs}")
        time.sleep(0.05)

    session.close()
    assert exited.wait(2)
    assert exit_codes


@pytest.mark.skipif(
    condition=__import__("os").name != "posix",
    reason="split terminal PTY behavior is POSIX-only",
)
def test_live_split_terminal_service_requires_directory(tmp_path) -> None:
    service = LiveSplitTerminalService(shell_command=("/bin/sh", "-c", "cat"))
    file_path = tmp_path / "README.md"
    file_path.write_text("plain\n", encoding="utf-8")

    with pytest.raises(OSError, match="requires a directory"):
        service.start(
            str(file_path),
            on_output=lambda _data: None,
            on_exit=lambda _code: None,
        )
