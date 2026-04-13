"""Manual benchmark for current-pane projection strategies."""

from __future__ import annotations

import argparse
import time
from dataclasses import replace
from datetime import datetime, timedelta
from statistics import mean

from zivo.state import (
    AppState,
    CurrentPaneDeltaState,
    DirectoryEntryState,
    DirectorySizeCacheEntry,
    DirectorySizeDeltaState,
    PaneState,
    build_placeholder_app_state,
    select_shell_data,
)
from zivo.state.selectors import compute_current_pane_visible_window

CURRENT_PATH = "/tmp/zivo-benchmark"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark full vs viewport current-pane projection.",
    )
    parser.add_argument(
        "--entries",
        type=int,
        default=10_000,
        help="Number of current-pane entries",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=200,
        help="Timed iterations per operation and projection mode",
    )
    parser.add_argument(
        "--terminal-height",
        type=int,
        default=24,
        help="Terminal height used to derive the viewport window",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    entries = build_entries(args.entries)

    print(
        "current pane projection benchmark "
        f"(entries={args.entries}, iterations={args.iterations}, "
        f"terminal_height={args.terminal_height})"
    )
    print("")
    print("mode      op                rendered_rows  mean_ms  p95_ms")
    print("--------  ----------------  -------------  -------  ------")

    for mode in ("full", "viewport"):
        base_state = build_benchmark_state(
            entries=entries,
            terminal_height=args.terminal_height,
            projection_mode=mode,
        )
        for operation in (
            "cursor_move",
            "page_scroll",
            "selection_toggle",
            "directory_size_reflect",
        ):
            result = benchmark_operation(
                base_state=base_state,
                entries=entries,
                operation=operation,
                iterations=args.iterations,
            )
            print(
                f"{mode:<8}  {operation:<16}  {result.rendered_rows:>13}  "
                f"{result.mean_ms:>7.2f}  {result.p95_ms:>6.2f}"
            )


def build_entries(count: int) -> tuple[DirectoryEntryState, ...]:
    base_time = datetime(2026, 4, 5, 12, 0)
    return tuple(
        DirectoryEntryState(
            path=f"{CURRENT_PATH}/dir_{index:05d}",
            name=f"dir_{index:05d}",
            kind="dir",
            modified_at=base_time - timedelta(minutes=index),
        )
        for index in range(count)
    )


def build_benchmark_state(
    *,
    entries: tuple[DirectoryEntryState, ...],
    terminal_height: int,
    projection_mode: str,
) -> AppState:
    state = build_placeholder_app_state(
        CURRENT_PATH,
        current_pane_projection_mode=projection_mode,
    )
    return replace(
        state,
        terminal_height=terminal_height,
        current_pane=PaneState(
            directory_path=CURRENT_PATH,
            entries=entries,
            cursor_path=entries[0].path if entries else None,
        ),
        child_pane=PaneState(directory_path=CURRENT_PATH, entries=()),
    )


class BenchmarkResult:
    def __init__(self, *, rendered_rows: int, mean_ms: float, p95_ms: float) -> None:
        self.rendered_rows = rendered_rows
        self.mean_ms = mean_ms
        self.p95_ms = p95_ms


def benchmark_operation(
    *,
    base_state: AppState,
    entries: tuple[DirectoryEntryState, ...],
    operation: str,
    iterations: int,
) -> BenchmarkResult:
    if not entries:
        return BenchmarkResult(rendered_rows=0, mean_ms=0.0, p95_ms=0.0)

    timings_ms: list[float] = []
    rendered_rows = 0
    visible_window = compute_current_pane_visible_window(base_state.terminal_height)

    for iteration in range(iterations):
        state = build_operation_state(
            base_state=base_state,
            entries=entries,
            operation=operation,
            iteration=iteration,
            visible_window=visible_window,
        )
        started_at = time.perf_counter()
        select_shell_data(state)
        timings_ms.append((time.perf_counter() - started_at) * 1_000)
        if state.current_pane_projection_mode == "viewport":
            rendered_rows = min(visible_window, len(entries) - state.current_pane_window_start)
        else:
            rendered_rows = len(entries)

    return BenchmarkResult(
        rendered_rows=rendered_rows,
        mean_ms=mean(timings_ms),
        p95_ms=percentile(timings_ms, 95),
    )


def build_operation_state(
    *,
    base_state: AppState,
    entries: tuple[DirectoryEntryState, ...],
    operation: str,
    iteration: int,
    visible_window: int,
) -> AppState:
    if operation == "cursor_move":
        target_index = min(len(entries) - 1, (iteration + 1) % len(entries))
        return apply_cursor_path(base_state, entries[target_index].path)

    if operation == "page_scroll":
        page_size = max(1, visible_window)
        target_index = min(len(entries) - 1, ((iteration + 1) * page_size) % len(entries))
        return apply_cursor_path(base_state, entries[target_index].path)

    if operation == "selection_toggle":
        target_index = min(len(entries) - 1, iteration % len(entries))
        target_path = entries[target_index].path
        selected_paths = frozenset({target_path}) if iteration % 2 == 0 else frozenset()
        return replace(
            apply_cursor_path(base_state, target_path),
            current_pane=replace(
                base_state.current_pane,
                cursor_path=target_path,
                selected_paths=selected_paths,
            ),
            current_pane_delta=CurrentPaneDeltaState(
                changed_paths=(target_path,),
                revision=iteration + 1,
            ),
        )

    if operation == "directory_size_reflect":
        target_index = min(len(entries) - 1, iteration % len(entries))
        target_path = entries[target_index].path
        return replace(
            apply_cursor_path(base_state, target_path),
            config=replace(
                base_state.config,
                display=replace(base_state.config.display, show_directory_sizes=True),
            ),
            directory_size_cache=(
                DirectorySizeCacheEntry(
                    path=target_path,
                    status="ready",
                    size_bytes=(iteration + 1) * 1024,
                ),
            ),
            directory_size_delta=DirectorySizeDeltaState(
                changed_paths=(target_path,),
                revision=iteration + 1,
            ),
        )

    raise ValueError(f"Unsupported benchmark operation: {operation}")


def apply_cursor_path(state: AppState, cursor_path: str) -> AppState:
    if state.current_pane_projection_mode != "viewport":
        return replace(
            state,
            current_pane=replace(state.current_pane, cursor_path=cursor_path),
        )

    visible_entries = state.current_pane.entries
    cursor_index = next(
        index for index, entry in enumerate(visible_entries) if entry.path == cursor_path
    )
    visible_window = compute_current_pane_visible_window(state.terminal_height)
    window_start = min(
        max(0, cursor_index - visible_window + 1),
        max(0, len(visible_entries) - visible_window),
    )
    return replace(
        state,
        current_pane=replace(state.current_pane, cursor_path=cursor_path),
        current_pane_window_start=window_start,
    )


def percentile(values: list[float], value: int) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * (value / 100))))
    return ordered[index]


if __name__ == "__main__":
    main()
