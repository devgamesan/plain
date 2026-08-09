"""Regression coverage for the pane visual hierarchy introduced by #1095."""

from dataclasses import replace
from pathlib import Path

import pytest
from textual.widgets import Label

from zivo import create_app
from zivo.models import AppConfig, CurrentSummaryState, DisplayConfig, PaneEntry, PaneHeadingState
from zivo.services import FakeBrowserSnapshotLoader
from zivo.state import BrowserSnapshot, DirectoryEntryState, PaneState, build_initial_app_state
from zivo.state.selectors import select_shell_data
from zivo.ui.pane_rendering import build_entry_label
from zivo.ui.panes import MainPane


def test_pane_heading_is_selector_owned_and_contains_summary_values() -> None:
    shell = select_shell_data(build_initial_app_state())

    heading = shell.current_heading

    assert heading.role == "Current"
    assert heading.target_name == "zivo"
    assert heading.item_count == shell.current_summary.item_count
    assert heading.selected_count == shell.current_summary.selected_count
    assert heading.sort_label == shell.current_summary.sort_label
    assert heading.active is True


def test_state_marker_keeps_row_state_legible_without_color() -> None:
    entry = PaneEntry(
        "run.sh",
        "file",
        selected=True,
        cut=True,
        symlink=True,
        executable=True,
    )
    pane = MainPane(
        title="Current Directory",
        entries=(entry,),
        summary=CurrentSummaryState(item_count=1, selected_count=1, sort_label="name asc"),
        cursor_index=0,
    )

    cells = pane._build_row_cells(
        entry,
        {"sel": 5, "name": 20, "size": 9, "modified": 16},
        row_index=0,
    )

    assert entry.state_marker(cursor=True) == ">x"
    assert cells[0].plain == ">x"
    assert cells[1].plain == "run.sh@*"
    assert build_entry_label(entry) == "run.sh@*"


def test_state_marker_keeps_selection_and_cut_in_fixed_slots() -> None:
    assert PaneEntry("selected.txt", "file", selected=True).state_marker() == "*"
    assert PaneEntry("cut.txt", "file", selected=True, cut=True).state_marker() == "x"
    assert PaneEntry("link", "file", symlink=True).type_marker == "@"
    assert PaneEntry("run.sh", "file", executable=True).type_marker == "*"


def test_inactive_heading_uses_a_non_active_marker() -> None:
    pane = MainPane(
        title="Transfer",
        entries=(),
        summary=CurrentSummaryState(item_count=0, selected_count=0, sort_label="name asc"),
        heading=PaneHeadingState(
            role="Right",
            target_name="destination",
            item_count=0,
            selected_count=0,
            sort_label="name asc",
            active=False,
        ),
    )

    assert pane._heading_text() == "  Right — destination"


@pytest.mark.asyncio
async def test_headless_browser_marks_current_pane_and_renders_heading() -> None:
    path = str(Path("/tmp/zivo-issue-1095-heading").resolve())
    entry_path = f"{path}/README.md"
    snapshot = BrowserSnapshot(
        current_path=path,
        parent_pane=PaneState(directory_path=str(Path(path).parent), entries=()),
        current_pane=PaneState(
            directory_path=path,
            entries=(DirectoryEntryState(entry_path, "README.md", "file"),),
            cursor_path=entry_path,
        ),
        child_pane=PaneState(directory_path=path, entries=()),
    )
    app = create_app(
        snapshot_loader=FakeBrowserSnapshotLoader(snapshots={path: snapshot}),
        initial_path=path,
    )

    async with app.run_test(size=(72, 20)) as pilot:
        for _ in range(20):
            if app.app_state.pending_browser_snapshot_request_id is None:
                break
            await pilot.pause(0.02)

        heading = app.query_one("#current-pane .pane-title", Label)
        assert "Current" in str(heading.renderable)
        assert "zivo-issue-1095-heading" in str(heading.renderable)
        assert app.query_one("#current-pane").has_class("active-pane")
        assert app.query_one("#current-pane").has_class("browser-active-pane")


@pytest.mark.asyncio
async def test_overlay_mode_removes_active_pane_emphasis() -> None:
    path = str(Path("/tmp/zivo-issue-1095-overlay").resolve())
    snapshot = BrowserSnapshot(
        current_path=path,
        parent_pane=PaneState(directory_path=str(Path(path).parent), entries=()),
        current_pane=PaneState(directory_path=path, entries=()),
        child_pane=PaneState(directory_path=path, entries=()),
    )
    app = create_app(
        snapshot_loader=FakeBrowserSnapshotLoader(snapshots={path: snapshot}),
        initial_path=path,
    )

    async with app.run_test(size=(72, 20)) as pilot:
        for _ in range(20):
            if app.app_state.pending_browser_snapshot_request_id is None:
                break
            await pilot.pause(0.02)

        current_pane = app.query_one("#current-pane")
        assert current_pane.has_class("active-pane")

        await pilot.press(":")
        await pilot.pause()

        assert app.app_state.ui_mode == "PALETTE"
        assert not current_pane.has_class("active-pane")
        assert not current_pane.has_class("browser-active-pane")

        await pilot.press("escape")
        await pilot.pause()
        assert app.app_state.ui_mode == "BROWSING"
        assert current_pane.has_class("active-pane")


@pytest.mark.asyncio
@pytest.mark.parametrize("width", (60, 72, 100, 120))
async def test_heading_summary_and_table_keep_separate_regions(width: int) -> None:
    path = str(Path(f"/tmp/zivo-issue-1095-width-{width}").resolve())
    snapshot = BrowserSnapshot(
        current_path=path,
        parent_pane=PaneState(directory_path=str(Path(path).parent), entries=()),
        current_pane=PaneState(directory_path=path, entries=()),
        child_pane=PaneState(directory_path=path, entries=()),
    )
    app = create_app(
        snapshot_loader=FakeBrowserSnapshotLoader(snapshots={path: snapshot}),
        initial_path=path,
    )

    async with app.run_test(size=(width, 20)) as pilot:
        for _ in range(20):
            if app.app_state.pending_browser_snapshot_request_id is None:
                break
            await pilot.pause(0.02)

        pane = app.query_one("#current-pane")
        title = app.query_one("#current-pane .pane-title")
        summary = app.query_one("#current-pane .pane-summary")
        table = app.query_one("#current-pane-table")

        assert title.region.width <= pane.region.width
        assert summary.region.width <= pane.region.width
        assert title.region.y + title.region.height <= summary.region.y
        assert summary.region.y + summary.region.height <= table.region.y


@pytest.mark.asyncio
@pytest.mark.parametrize("theme", ("textual-dark", "textual-light"))
async def test_browser_active_heading_keeps_theme_contrast(theme: str) -> None:
    path = str(Path(f"/tmp/zivo-issue-1095-theme-{theme}").resolve())
    snapshot = BrowserSnapshot(
        current_path=path,
        parent_pane=PaneState(directory_path=str(Path(path).parent), entries=()),
        current_pane=PaneState(directory_path=path, entries=()),
        child_pane=PaneState(directory_path=path, entries=()),
    )
    config = replace(
        AppConfig(),
        display=replace(DisplayConfig(), theme=theme),
    )
    app = create_app(
        snapshot_loader=FakeBrowserSnapshotLoader(snapshots={path: snapshot}),
        initial_path=path,
        app_config=config,
    )

    async with app.run_test(size=(72, 20)) as pilot:
        for _ in range(20):
            if app.app_state.pending_browser_snapshot_request_id is None:
                break
            await pilot.pause(0.02)

        title = app.query_one("#current-pane .pane-title")
        assert title.styles.color is not None
        assert title.styles.background is not None
        assert title.styles.color != title.styles.background
