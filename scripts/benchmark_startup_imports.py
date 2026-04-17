"""Benchmark non-TUI command startup time.

Measures wall-clock time for init and help commands
to verify lazy import improvements.

Usage:
    uv run python scripts/benchmark_startup_imports.py
"""

import subprocess
import sys
import time


def measure(command: list[str], runs: int = 20) -> float:
    """Return mean wall-clock time in ms for the given command."""
    times: list[float] = []
    for _ in range(runs):
        t0 = time.perf_counter()
        subprocess.run(command, capture_output=True)
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000)
    return sum(times) / len(times)


def main() -> None:
    python = sys.executable

    init_cmd = [python, "-c", "from zivo.__main__ import main; main(['init', 'bash'])"]
    import_cmd = [python, "-c", "import zivo; zivo.create_app"]

    init_time = measure(init_cmd)
    import_time = measure(import_cmd)

    print(f"zivo init bash:            {init_time:.0f}ms (avg of 20 runs)")
    print(f"zivo create_app (TUI):     {import_time:.0f}ms (avg of 20 runs)")
    print(f"estimated savings:         {import_time - init_time:.0f}ms")


if __name__ == "__main__":
    main()
