"""Regression coverage for the pane visual hierarchy introduced by #1095."""

from pathlib import Path

import pytest
from textual.widgets import Label

from zivo import create_app
from zivo.models import CurrentSummaryState, PaneEntry, PaneHeadingState
from zivo.services import FakeBrowserSnapshotLoader
from zivo.state import BrowserSnapshot, DirectoryEntryState, PaneState, build_initial_app_state
from zivo.state.selectors import select_shell_data
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

    assert entry.state_marker(cursor=True) == ">*x@+"
    assert cells[0].plain == ">*"


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
