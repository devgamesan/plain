"""Manual benchmark for unified Go directory completion."""

from __future__ import annotations

import argparse
import tempfile
import time
from pathlib import Path
from statistics import mean

from zivo.services import GoPathCompletionService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark Go path completion.")
    parser.add_argument("--dirs", type=int, default=5_000)
    parser.add_argument("--iterations", type=int, default=10)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with tempfile.TemporaryDirectory(prefix="zivo-benchmark-go-") as tmp_dir:
        root = Path(tmp_dir)
        build_fixture(root, args.dirs)
        service = GoPathCompletionService(cache_ttl_seconds=60, max_results=500)

        cold = time_call(
            args.iterations,
            lambda: service.complete("directory_", str(root)),
        )
        warm = time_call(
            args.iterations,
            lambda: service.complete("directory_000", str(root)),
        )

        print(
            "Go completion benchmark "
            f"(dirs={args.dirs}, iterations={args.iterations})"
        )
        print("")
        print("operation             mean_ms  p95_ms")
        print("--------------------  -------  ------")
        print_row("cold listing", cold)
        print_row("cached prefix", warm)
        print("")
        print("Compare the same command on another commit or branch.")


def build_fixture(root: Path, count: int) -> None:
    for index in range(count):
        (root / f"directory_{index:05d}").mkdir()
    (root / "not-a-directory.txt").write_text("zivo benchmark\n", encoding="utf-8")


def time_call(iterations: int, fn) -> list[float]:
    timings_ms: list[float] = []
    for _ in range(iterations):
        started_at = time.perf_counter()
        fn()
        timings_ms.append((time.perf_counter() - started_at) * 1_000)
    return timings_ms


def percentile(values: list[float], percent: int) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, round((percent / 100) * (len(ordered) - 1)))
    return ordered[index]


def print_row(label: str, values: list[float]) -> None:
    print(f"{label:<20}  {mean(values):>7.2f}  {percentile(values, 95):>6.2f}")


if __name__ == "__main__":
    main()
