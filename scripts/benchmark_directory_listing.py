"""Manual benchmark for deferred directory metadata loading."""

from __future__ import annotations

import argparse
import shutil
import tempfile
import time
from pathlib import Path
from statistics import mean

from zivo.adapters import LocalFilesystemAdapter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark lightweight directory listing vs on-demand inspection.",
    )
    parser.add_argument(
        "--files",
        type=int,
        default=8_000,
        help="Number of files to create in the benchmark directory.",
    )
    parser.add_argument(
        "--dirs",
        type=int,
        default=2_000,
        help="Number of directories to create in the benchmark directory.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=10,
        help="Timed iterations per measurement.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    adapter = LocalFilesystemAdapter()

    with tempfile.TemporaryDirectory(prefix="zivo-benchmark-listdir-") as tmp_dir:
        root = Path(tmp_dir)
        build_fixture(root, files=args.files, dirs=args.dirs)

        list_timings = time_call(
            args.iterations,
            lambda: adapter.list_directory(str(root)),
        )
        entries = adapter.list_directory(str(root))
        first_file = next((entry.path for entry in entries if entry.kind == "file"), None)
        inspect_one_timings = (
            time_call(args.iterations, lambda: adapter.inspect_entry(first_file))
            if first_file is not None
            else []
        )
        inspect_all_timings = time_call(
            args.iterations,
            lambda: tuple(adapter.inspect_entry(entry.path) for entry in entries),
        )

        print(
            "directory listing benchmark "
            f"(files={args.files}, dirs={args.dirs}, iterations={args.iterations})"
        )
        print("")
        print("operation             mean_ms  p95_ms")
        print("--------------------  -------  ------")
        print_row("list_directory", list_timings)
        if inspect_one_timings:
            print_row("inspect_entry(one)", inspect_one_timings)
        print_row("inspect_entry(all)", inspect_all_timings)
        print("")
        print(
            "Use the same command on another commit or branch to compare before/after."
        )


def build_fixture(root: Path, *, files: int, dirs: int) -> None:
    for index in range(dirs):
        (root / f"dir_{index:05d}").mkdir()
    for index in range(files):
        (root / f"file_{index:05d}.txt").write_text("zivo benchmark\n", encoding="utf-8")
    shutil.rmtree(root / "dir_00000")
    (root / "broken-link").symlink_to(root / "dir_00000")


def time_call(iterations: int, fn) -> list[float]:
    timings_ms: list[float] = []
    for _ in range(iterations):
        started_at = time.perf_counter()
        fn()
        timings_ms.append((time.perf_counter() - started_at) * 1_000)
    return timings_ms


def percentile(values: list[float], percent: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((percent / 100) * (len(ordered) - 1))))
    return ordered[index]


def print_row(label: str, values: list[float]) -> None:
    print(f"{label:<20}  {mean(values):>7.2f}  {percentile(values, 95):>6.2f}")


if __name__ == "__main__":
    main()
