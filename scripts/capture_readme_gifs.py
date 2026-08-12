#!/usr/bin/env python3
"""Regenerate the README walkthrough GIFs from deterministic Textual sessions.

The capture intentionally uses ``FakeBrowserSnapshotLoader`` rather than the
developer's filesystem.  This keeps names, timestamps, and preview contents
stable while still exercising the real application, reducer, and keymap paths.
The raster conversion is kept outside the application package because it is a
release/documentation helper, not a runtime dependency.
"""

from __future__ import annotations

import argparse
import asyncio
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Sequence

from PIL import Image

from zivo.app import create_app
from zivo.models import PasteAppliedChange, PasteExecutionResult, PasteSummary
from zivo.services import FakeBrowserSnapshotLoader
from zivo.state.actions import NavigateTransferToPath
from zivo.state.models import BrowserSnapshot, DirectoryEntryState, PaneState

BASE_PATH = "/tmp/zivo-readme-demo"
SRC_PATH = f"{BASE_PATH}/src"
DOCS_PATH = f"{BASE_PATH}/docs"
README_PATH = f"{BASE_PATH}/README.md"

TARGET_SPECS: dict[str, tuple[int, int]] = {
    "basic_operation.gif": (1000, 640),
    "command_palette.gif": (1000, 462),
    "transfer_mode_operation.gif": (1000, 640),
}

FRAME_DURATIONS_MS = (900, 700, 700, 1000, 1000)
TERMINAL_SIZE = (120, 24)


@dataclass(frozen=True)
class CapturedFrame:
    """One SVG frame and the time it should remain visible in the GIF."""

    svg_path: Path
    duration_ms: int


class CaptureClipboardService:
    """Return deterministic success for the transfer walkthrough."""

    def execute_paste(self, request, *, progress_callback=None, cancel_callback=None):
        del progress_callback, cancel_callback
        changes = tuple(
            PasteAppliedChange(
                source_path=source_path,
                destination_path=str(Path(request.destination_dir) / Path(source_path).name),
            )
            for source_path in request.source_paths
        )
        return PasteExecutionResult(
            summary=PasteSummary(
                mode=request.mode,
                destination_dir=request.destination_dir,
                total_count=len(request.source_paths),
                success_count=len(request.source_paths),
                skipped_count=0,
                failures=(),
                conflict_resolution=request.conflict_resolution,
            ),
            applied_changes=changes,
        )


def _entry(
    path: str,
    name: str,
    kind: str,
    *,
    size_bytes: int | None = None,
    modified_at: datetime | None = None,
) -> DirectoryEntryState:
    return DirectoryEntryState(
        path=path,
        name=name,
        kind=kind,
        size_bytes=size_bytes,
        modified_at=modified_at,
    )


def build_demo_loader() -> FakeBrowserSnapshotLoader:
    """Build the fixed directory and preview data used by every scenario."""

    entries = (
        _entry(
            DOCS_PATH,
            "docs",
            "dir",
            modified_at=datetime(2026, 8, 1, 10, 0),
        ),
        _entry(
            SRC_PATH,
            "src",
            "dir",
            modified_at=datetime(2026, 8, 2, 10, 0),
        ),
        _entry(
            README_PATH,
            "README.md",
            "file",
            size_bytes=2_048,
            modified_at=datetime(2026, 8, 3, 10, 0),
        ),
    )
    parent = PaneState(
        directory_path="/tmp",
        entries=(_entry(BASE_PATH, "zivo-readme-demo", "dir"),),
        cursor_path=BASE_PATH,
    )
    docs_child = PaneState(
        directory_path=DOCS_PATH,
        entries=(_entry(f"{DOCS_PATH}/guide.md", "guide.md", "file"),),
        cursor_path=f"{DOCS_PATH}/guide.md",
    )
    src_child = PaneState(
        directory_path=SRC_PATH,
        entries=(_entry(f"{SRC_PATH}/app.py", "app.py", "file"),),
        cursor_path=f"{SRC_PATH}/app.py",
    )
    readme_preview = PaneState(
        directory_path=BASE_PATH,
        entries=(),
        mode="preview",
        preview_path=README_PATH,
        preview_title="README.md",
        preview_content=(
            "# zivo\n\n"
            "A fast three-pane browser.\n\n"
            "Browse, preview, and operate files without leaving the keyboard."
        ),
        preview_kind="text",
    )
    base_snapshot = BrowserSnapshot(
        current_path=BASE_PATH,
        parent_pane=parent,
        current_pane=PaneState(
            directory_path=BASE_PATH,
            entries=entries,
            cursor_path=DOCS_PATH,
        ),
        child_pane=docs_child,
    )
    src_snapshot = BrowserSnapshot(
        current_path=SRC_PATH,
        parent_pane=parent,
        current_pane=PaneState(directory_path=SRC_PATH, entries=(), cursor_path=None),
        child_pane=PaneState(directory_path=SRC_PATH, entries=()),
    )
    return FakeBrowserSnapshotLoader(
        snapshots={BASE_PATH: base_snapshot, SRC_PATH: src_snapshot},
        child_panes={
            (BASE_PATH, DOCS_PATH): docs_child,
            (BASE_PATH, SRC_PATH): src_child,
            (BASE_PATH, README_PATH): readme_preview,
        },
    )


async def _wait_for(
    predicate: Callable[[], bool],
    pilot,
    *,
    timeout_seconds: float = 2.0,
) -> None:
    """Wait for a reducer/worker transition without relying on wall-clock sleeps."""

    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while not predicate():
        if asyncio.get_running_loop().time() >= deadline:
            raise TimeoutError("Timed out while preparing a README capture frame")
        await pilot.pause(0.05)


async def _wait_for_browser(app, pilot, path: str) -> None:
    # Let the key action enqueue its worker before checking the pre-action state.
    await pilot.pause(0.05)
    await _wait_for(
        lambda: (
            app.app_state.current_path == path
            and app.app_state.pending_browser_snapshot_request_id is None
        ),
        pilot,
    )
    await pilot.pause(0.1)


async def _wait_for_child(app, pilot) -> None:
    await pilot.pause(0.05)
    await _wait_for(
        lambda: app.app_state.pending_child_pane_request_id is None,
        pilot,
    )
    await pilot.pause(0.1)


def _capture_svg(app, directory: Path, index: int, duration_ms: int) -> CapturedFrame:
    path = directory / f"frame-{index:02d}.svg"
    app.save_screenshot(filename=path.name, path=str(directory))
    return CapturedFrame(path, duration_ms)


async def _capture_basic(directory: Path) -> list[CapturedFrame]:
    loader = build_demo_loader()
    app = create_app(snapshot_loader=loader, initial_path=BASE_PATH)
    frames: list[CapturedFrame] = []
    async with app.run_test(size=TERMINAL_SIZE) as pilot:
        await _wait_for_browser(app, pilot, BASE_PATH)
        await _wait_for_child(app, pilot)
        frames.append(_capture_svg(app, directory, 0, FRAME_DURATIONS_MS[0]))

        await pilot.press("down")
        await _wait_for_child(app, pilot)
        frames.append(_capture_svg(app, directory, 1, FRAME_DURATIONS_MS[1]))

        await pilot.press("down")
        await _wait_for_child(app, pilot)
        frames.append(_capture_svg(app, directory, 2, FRAME_DURATIONS_MS[2]))

        await pilot.press("space")
        await pilot.pause(0.1)
        frames.append(_capture_svg(app, directory, 3, FRAME_DURATIONS_MS[3]))
    return frames


async def _capture_command_palette(directory: Path) -> list[CapturedFrame]:
    loader = build_demo_loader()
    app = create_app(snapshot_loader=loader, initial_path=BASE_PATH)
    frames: list[CapturedFrame] = []
    async with app.run_test(size=TERMINAL_SIZE) as pilot:
        await _wait_for_browser(app, pilot, BASE_PATH)
        await _wait_for_child(app, pilot)

        await pilot.press(":")
        await pilot.pause(0.1)
        frames.append(_capture_svg(app, directory, 0, FRAME_DURATIONS_MS[0]))

        await pilot.press("r", "e", "l", "o", "a", "d")
        await pilot.pause(0.1)
        frames.append(_capture_svg(app, directory, 1, FRAME_DURATIONS_MS[1]))

        await pilot.press("enter")
        await _wait_for_browser(app, pilot, BASE_PATH)
        await _wait_for_child(app, pilot)
        frames.append(_capture_svg(app, directory, 2, FRAME_DURATIONS_MS[2]))
    return frames


async def _capture_transfer(directory: Path) -> list[CapturedFrame]:
    loader = build_demo_loader()
    app = create_app(
        snapshot_loader=loader,
        clipboard_service=CaptureClipboardService(),
        initial_path=BASE_PATH,
    )
    frames: list[CapturedFrame] = []
    async with app.run_test(size=TERMINAL_SIZE) as pilot:
        await _wait_for_browser(app, pilot, BASE_PATH)
        await pilot.press("p")
        await _wait_for(
            lambda: (
                app.app_state.layout_mode == "transfer"
                and app.app_state.transfer_left is not None
                and app.app_state.transfer_right is not None
            ),
            pilot,
        )
        await pilot.pause(0.1)
        frames.append(_capture_svg(app, directory, 0, FRAME_DURATIONS_MS[0]))

        await app.dispatch_actions((NavigateTransferToPath(SRC_PATH),))
        await _wait_for(
            lambda: app.app_state.transfer_left is not None
            and app.app_state.transfer_left.current_path == SRC_PATH
            and app.app_state.transfer_left.pending_snapshot_request_id is None,
            pilot,
        )
        frames.append(_capture_svg(app, directory, 1, FRAME_DURATIONS_MS[1]))

        await pilot.press("tab")
        await pilot.press("down", "down", "space")
        await pilot.pause(0.1)
        frames.append(_capture_svg(app, directory, 2, FRAME_DURATIONS_MS[2]))

        await pilot.press("c")
        await pilot.pause(0.4)
        frames.append(_capture_svg(app, directory, 3, FRAME_DURATIONS_MS[3]))
    return frames


def _find_rsvg_convert() -> str:
    executable = shutil.which("rsvg-convert")
    if executable is None:
        raise RuntimeError(
            "rsvg-convert is required to regenerate README GIFs "
            "(install librsvg with Homebrew or your OS package manager)"
        )
    return executable


def _render_svg(svg_path: Path, png_path: Path, size: tuple[int, int], rsvg: str) -> None:
    width, height = size
    subprocess.run(
        [
            rsvg,
            "-w",
            str(width),
            "-h",
            str(height),
            str(svg_path),
            "-o",
            str(png_path),
        ],
        check=True,
    )


def _assemble_gif(
    frames: Sequence[CapturedFrame],
    output_path: Path,
    size: tuple[int, int],
    rsvg: str,
    directory: Path,
) -> None:
    png_paths: list[Path] = []
    for index, frame in enumerate(frames):
        png_path = directory / f"frame-{index:02d}.png"
        _render_svg(frame.svg_path, png_path, size, rsvg)
        png_paths.append(png_path)

    images = [Image.open(path).convert("RGB") for path in png_paths]
    if not images:
        raise RuntimeError(f"No frames captured for {output_path.name}")
    if any(image.size != size for image in images):
        raise RuntimeError(f"Unexpected frame dimensions for {output_path.name}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(
        output_path,
        format="GIF",
        save_all=True,
        append_images=images[1:],
        duration=[frame.duration_ms for frame in frames],
        loop=0,
        disposal=2,
        optimize=False,
    )
    for image in images:
        image.close()


async def _capture_all(output_dir: Path) -> None:
    rsvg = _find_rsvg_convert()
    scenario_functions = (
        ("basic_operation.gif", _capture_basic),
        ("command_palette.gif", _capture_command_palette),
        ("transfer_mode_operation.gif", _capture_transfer),
    )
    with tempfile.TemporaryDirectory(prefix="zivo-readme-gifs-") as temporary_dir:
        temporary_path = Path(temporary_dir)
        for name, capture in scenario_functions:
            scenario_dir = temporary_path / name.removesuffix(".gif")
            scenario_dir.mkdir(parents=True, exist_ok=True)
            frames = await capture(scenario_dir)
            _assemble_gif(
                frames,
                output_dir / name,
                TARGET_SPECS[name],
                rsvg,
                scenario_dir,
            )
            with Image.open(output_dir / name) as image:
                if image.size != TARGET_SPECS[name] or image.n_frames != len(frames):
                    raise RuntimeError(f"Generated GIF validation failed for {name}")
            print(f"wrote {output_dir / name} ({len(frames)} frames)")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("docs/resources"),
        help="directory for the three README GIFs (default: docs/resources)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    asyncio.run(_capture_all(args.output_dir))


if __name__ == "__main__":
    main()
