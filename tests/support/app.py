"""Shared Textual app helpers used by app and widget tests."""

import asyncio
from pathlib import Path

from textual.css.query import NoMatches

from zivo.state import BrowserSnapshot, DirectoryEntryState, PaneState


def build_snapshot(
    path: str,
    current_entries: tuple[DirectoryEntryState, ...],
    *,
    child_path: str | None = None,
    child_entries: tuple[DirectoryEntryState, ...] = (),
) -> BrowserSnapshot:
    """Build a compact three-pane snapshot for headless app tests."""

    cursor_path = current_entries[0].path if current_entries else None
    parent_path = str(Path(path).parent)
    parent_entries = (
        DirectoryEntryState(path, Path(path).name, "dir"),
        DirectoryEntryState(f"{parent_path}/sibling", "sibling", "dir"),
    )
    return BrowserSnapshot(
        current_path=path,
        parent_pane=PaneState(
            directory_path=parent_path,
            entries=parent_entries,
            cursor_path=path,
        ),
        current_pane=PaneState(
            directory_path=path,
            entries=current_entries,
            cursor_path=cursor_path,
        ),
        child_pane=PaneState(
            directory_path=child_path or path,
            entries=child_entries,
        ),
    )


async def wait_for_snapshot_loaded(app, expected_path: str, timeout: float = 0.5) -> None:
    """Wait until the app has applied the snapshot for ``expected_path``."""

    resolved_expected = str(Path(expected_path).resolve())
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        if (
            app.app_state.current_path == resolved_expected
            and app.app_state.pending_browser_snapshot_request_id is None
            and app.app_state.current_pane.entries
        ):
            return
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError(f"snapshot did not load for {expected_path}")
        await asyncio.sleep(0.01)


async def wait_for_widget(app, selector: str, widget_type, timeout: float = 0.5):
    """Wait until a widget matching ``selector`` is mounted."""

    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        try:
            return app.query_one(selector, widget_type)
        except NoMatches:
            if asyncio.get_running_loop().time() >= deadline:
                raise
            await asyncio.sleep(0.01)


__all__ = ["build_snapshot", "wait_for_snapshot_loaded", "wait_for_widget"]
