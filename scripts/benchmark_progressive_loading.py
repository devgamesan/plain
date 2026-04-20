"""Benchmark progressive browser snapshot loading vs blocking mode."""

from __future__ import annotations

import argparse
import shutil
import tempfile
import time
from pathlib import Path
from statistics import mean

from zivo.services import LiveBrowserSnapshotLoader


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark progressive loading vs blocking mode.",
    )
    parser.add_argument(
        "--files",
        type=int,
        default=100,
        help="Number of files to create in each benchmark directory.",
    )
    parser.add_argument(
        "--dirs",
        type=int,
        default=100,
        help="Number of directories to create in the benchmark tree.",
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
    loader = LiveBrowserSnapshotLoader()

    with tempfile.TemporaryDirectory(prefix="zivo-benchmark-progressive-") as tmp_dir:
        root = Path(tmp_dir)
        build_fixture(root, files=args.files, dirs=args.dirs)

        # Measure blocking mode (baseline)
        blocking_timings = time_call(
            args.iterations,
            lambda: loader.load_browser_snapshot(str(root)),
        )

        # Measure progressive mode - Phase 1 (current pane only)
        progressive_phase1_timings = time_call(
            args.iterations,
            lambda: loader.load_current_pane_snapshot(str(root), None),
        )

        # Measure progressive mode - Phase 2 (parent + child)
        # Use a sample current_pane for Phase 2
        _, sample_current_pane, _ = loader.load_current_pane_snapshot(str(root), None)
        progressive_phase2_timings = time_call(
            args.iterations,
            lambda: loader.load_parent_child_panes(str(root), None, sample_current_pane),
        )

        # Calculate total progressive time (Phase 1 + Phase 2)
        progressive_total_timings = [
            p1 + p2 for p1, p2 in zip(progressive_phase1_timings, progressive_phase2_timings)
        ]

        # Calculate first paint improvement
        blocking_mean = mean(blocking_timings)
        progressive_phase1_mean = mean(progressive_phase1_timings)
        improvement_ratio = (
            blocking_mean / progressive_phase1_mean if progressive_phase1_mean > 0 else 0
        )
        time_saved_ms = blocking_mean - progressive_phase1_mean

        print(
            "progressive loading benchmark "
            f"(files={args.files}, dirs={args.dirs}, iterations={args.iterations})"
        )
        print("")
        print("operation                           mean_ms  p95_ms")
        print("--------------------------------  -------  ------")
        print_row("blocking (baseline)", blocking_timings)
        print_row("progressive phase1 (first paint)", progressive_phase1_timings)
        print_row("progressive phase2 (parent+child)", progressive_phase2_timings)
        print_row("progressive total (phase1+2)", progressive_total_timings)
        print("")
        print("first paint improvement:")
        print(f"  blocking:        {blocking_mean:.2f} ms")
        print(f"  progressive:     {progressive_phase1_mean:.2f} ms")
        print(f"  improvement:     {improvement_ratio:.2f}x faster")
        print(f"  time saved:      {time_saved_ms:.2f} ms")
        print("")
        print("Use the same command on another commit or branch to compare before/after.")


def build_fixture(root: Path, *, files: int, dirs: int) -> None:
    """Build a benchmark fixture with nested directories and files."""
    # Create nested directory structure
    for i in range(dirs):
        dir_path = root / f"dir_{i:05d}"
        dir_path.mkdir(exist_ok=True)

        # Add some files to each directory
        files_per_dir = max(1, files // dirs)
        for j in range(files_per_dir):
            (dir_path / f"file_{j:05d}.txt").write_text(
                "zivo benchmark content\n",
                encoding="utf-8",
            )

    # Add some files at root level
    remaining_files = files - (dirs * (files // dirs))
    for i in range(remaining_files):
        (root / f"root_file_{i:05d}.txt").write_text(
            "zivo benchmark content\n",
            encoding="utf-8",
        )

    # Create a broken symlink to test error handling
    shutil.rmtree(root / "dir_00000", ignore_errors=True)
    (root / "broken-link").symlink_to(root / "dir_00000")


def time_call(iterations: int, fn) -> list[float]:
    """Time a function call over multiple iterations."""
    timings_ms: list[float] = []
    for _ in range(iterations):
        started_at = time.perf_counter()
        fn()
        timings_ms.append((time.perf_counter() - started_at) * 1_000)
    return timings_ms


def percentile(values: list[float], percent: int) -> float:
    """Calculate a percentile of a list of values."""
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = (percent / 100) * (len(sorted_values) - 1)
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = index - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def print_row(label: str, timings: list[float]) -> None:
    """Print a benchmark result row."""
    mean_ms = mean(timings) if timings else 0.0
    p95_ms = percentile(timings, 95) if timings else 0.0
    print(f"{label:34}  {mean_ms:7.2f}  {p95_ms:6.2f}")


if __name__ == "__main__":
    main()
