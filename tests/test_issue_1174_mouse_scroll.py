from dataclasses import replace

import pytest
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.events import MouseScrollDown, MouseScrollUp
from textual.widgets import DataTable

from zivo import create_app
from zivo.models import (
    ChildPaneViewState,
    CommandPaletteItemViewState,
    CommandPaletteViewState,
)
from zivo.services import FakeBrowserSnapshotLoader
from zivo.state import BrowserSnapshot, DirectoryEntryState, PaneState
from zivo.ui.child_pane import ChildPane
from zivo.ui.command_palette import CommandPalette


def _large_snapshot(path: str) -> BrowserSnapshot:
    selected_directory = DirectoryEntryState(f"{path}/docs", "docs", "dir")
    current_entries = (selected_directory,) + tuple(
        DirectoryEntryState(
            f"{path}/file-{index:03}.txt",
            f"file-{index:03}.txt",
            "file",
        )
        for index in range(79)
    )
    child_entries = tuple(
        DirectoryEntryState(
            f"{path}/docs/child-{index:03}.txt",
            f"child-{index:03}.txt",
            "file",
        )
        for index in range(80)
    )
    parent_entries = tuple(
        DirectoryEntryState(
            f"/tmp/parent-{index:03}",
            f"parent-{index:03}",
            "dir",
        )
        for index in range(80)
    )
    return BrowserSnapshot(
        current_path=path,
        parent_pane=PaneState("/tmp", parent_entries, cursor_path=path),
        current_pane=PaneState(
            path,
            current_entries,
            cursor_path=selected_directory.path,
        ),
        child_pane=PaneState(f"{path}/docs", child_entries),
    )


@pytest.mark.asyncio
async def test_issue_1174_browser_panes_expand_to_mouse_scroll_without_selection_change() -> None:
    path = "/tmp/zivo-issue-1174-browser"
    app = create_app(
        snapshot_loader=FakeBrowserSnapshotLoader(
            snapshots={path: _large_snapshot(path)},
        ),
        initial_path=path,
    )

    async with app.run_test(size=(120, 20)) as pilot:
        await pilot.pause(0.2)
        cursor_path = app.app_state.current_pane.cursor_path
        current_table = app.query_one("#current-pane-table", DataTable)
        parent_scroll = app.query_one("#parent-pane-list-scroll", VerticalScroll)
        child_scroll = app.query_one("#child-pane-list-scroll", VerticalScroll)

        assert current_table.scrollbar_size_vertical == 0
        assert parent_scroll.scrollbar_size_vertical == 0
        assert child_scroll.scrollbar_size_vertical == 0
        assert current_table.row_count < 80

        await pilot._post_mouse_events([MouseScrollDown], widget="#current-pane-table")
        await pilot.pause(0.05)
        assert current_table.row_count == 80
        assert current_table.scroll_y > 0
        assert app.app_state.current_pane.cursor_path == cursor_path
        current_scroll_y = current_table.scroll_y
        await pilot._post_mouse_events([MouseScrollUp], widget="#current-pane-table")
        await pilot.pause(0.05)
        assert current_table.scroll_y < current_scroll_y

        await pilot._post_mouse_events([MouseScrollDown], widget="#parent-pane-list-scroll")
        await pilot.pause(0.05)
        assert parent_scroll.virtual_size.height == 80
        assert parent_scroll.scroll_y > 0
        parent_scroll_y = parent_scroll.scroll_y
        await pilot._post_mouse_events([MouseScrollUp], widget="#parent-pane-list-scroll")
        await pilot.pause(0.05)
        assert parent_scroll.scroll_y < parent_scroll_y

        await pilot._post_mouse_events([MouseScrollDown], widget="#child-pane-list-scroll")
        await pilot.pause(0.05)
        assert child_scroll.virtual_size.height == 80
        assert child_scroll.scroll_y > 0
        child_scroll_y = child_scroll.scroll_y
        await pilot._post_mouse_events([MouseScrollUp], widget="#child-pane-list-scroll")
        await pilot.pause(0.05)
        assert child_scroll.scroll_y < child_scroll_y


class _ScrollPaletteHarness(App[None]):
    CSS = """
    #command-palette { display: block; height: 10; width: 50; }
    #command-palette-items-scroll { height: 1fr; max-height: 1fr; scrollbar-size: 1 1; }
    #command-palette.-result-list #command-palette-items-scroll { scrollbar-size: 0 0; }
    """

    def __init__(self, state: CommandPaletteViewState) -> None:
        super().__init__()
        self.state = state

    def compose(self) -> ComposeResult:
        yield CommandPalette(self.state, id="command-palette")


@pytest.mark.asyncio
@pytest.mark.parametrize("title", ("Find All", "Grep", "Replace Text"))
async def test_issue_1174_search_and_replace_results_hide_scrollbar_and_reach_tail(
    title: str,
) -> None:
    visible = tuple(
        CommandPaletteItemViewState(
            label=f"result-{index:03}",
            shortcut=None,
            enabled=True,
            selected=index == 0,
        )
        for index in range(10)
    )
    all_results = tuple(
        CommandPaletteItemViewState(
            label=f"result-{index:03}",
            shortcut=None,
            enabled=True,
            selected=index == 0,
        )
        for index in range(80)
    )
    state = CommandPaletteViewState(
        title=title,
        query="needle",
        items=visible,
        empty_message="No results",
        has_more_items=True,
        scroll_items=all_results,
        scroll_key=f"{title}:needle",
        cursor_index=0,
    )
    app = _ScrollPaletteHarness(state)

    async with app.run_test(size=(60, 20)) as pilot:
        await pilot.pause()
        scroll = app.query_one("#command-palette-items-scroll", VerticalScroll)
        assert scroll.scrollbar_size_vertical == 0
        await pilot._post_mouse_events([MouseScrollDown], widget="#command-palette-items-scroll")
        await pilot.pause(0.05)
        assert scroll.virtual_size.height == 80
        assert scroll.scroll_y > 0
        scroll_y = scroll.scroll_y
        await pilot._post_mouse_events([MouseScrollUp], widget="#command-palette-items-scroll")
        await pilot.pause(0.05)
        assert scroll.scroll_y < scroll_y


@pytest.mark.asyncio
async def test_issue_1174_result_cursor_preserves_manual_scroll_when_row_is_visible() -> None:
    visible = tuple(
        CommandPaletteItemViewState(
            label=f"result-{index:03}",
            shortcut=None,
            enabled=True,
            selected=index == 0,
        )
        for index in range(10)
    )
    all_results = tuple(
        CommandPaletteItemViewState(
            label=f"result-{index:03}",
            shortcut=None,
            enabled=True,
            selected=index == 0,
        )
        for index in range(80)
    )
    state = CommandPaletteViewState(
        title="Find All",
        query="needle",
        items=visible,
        empty_message="No results",
        has_more_items=True,
        scroll_items=all_results,
        scroll_key="Find All:needle",
        cursor_index=0,
    )
    app = _ScrollPaletteHarness(state)

    async with app.run_test(size=(60, 20)) as pilot:
        await pilot.pause()
        scroll = app.query_one("#command-palette-items-scroll", VerticalScroll)
        await pilot._post_mouse_events(
            [MouseScrollDown], widget="#command-palette-items-scroll"
        )
        for _ in range(24):
            await pilot._post_mouse_events(
                [MouseScrollDown], widget="#command-palette-items-scroll"
            )
        await pilot.pause(0.05)
        scroll_y = scroll.scroll_y
        assert scroll_y > 10

        palette = app.query_one("#command-palette", CommandPalette)
        selected_index = int(scroll_y) + 2
        next_items = tuple(
            replace(item, selected=index == selected_index)
            for index, item in enumerate(visible)
        )
        next_scroll_items = tuple(
            replace(item, selected=index == selected_index)
            for index, item in enumerate(all_results)
        )
        palette.set_state(
            replace(
                state,
                items=next_items,
                scroll_items=next_scroll_items,
                cursor_index=selected_index,
            )
        )
        await pilot.pause(0.05)

        assert scroll.scroll_y == scroll_y


@pytest.mark.asyncio
async def test_issue_1174_preview_and_normal_palette_keep_scrollbars() -> None:
    preview = ChildPane(
        ChildPaneViewState(
            title="Preview",
            preview_content="\n".join(f"line {index}" for index in range(80)),
            view_kind="preview",
        ),
        id="child-pane",
    )

    class _PreviewHarness(App[None]):
        CSS = """
        #child-pane { height: 12; width: 40; }
        .pane-preview-scroll { height: 1fr; scrollbar-size: 1 1; }
        .pane-preview { height: auto; }
        .pane-preview-help { height: 1; }
        .pane-metadata-bar { height: 1; }
        """

        def compose(self) -> ComposeResult:
            yield preview

    async with _PreviewHarness().run_test(size=(50, 20)) as pilot:
        await pilot.pause()
        preview_scroll = preview.query_one("#child-pane-preview-scroll", VerticalScroll)
        assert preview_scroll.scrollbar_size_vertical == 1

    normal_items = tuple(
        CommandPaletteItemViewState(
            label=f"command-{index}",
            shortcut=None,
            enabled=True,
            selected=index == 0,
        )
        for index in range(30)
    )
    normal_app = _ScrollPaletteHarness(
        CommandPaletteViewState(
            title="Command Palette",
            query="",
            items=normal_items,
            empty_message="No commands",
            has_more_items=True,
        )
    )
    async with normal_app.run_test(size=(60, 20)) as pilot:
        await pilot.pause()
        scroll = normal_app.query_one("#command-palette-items-scroll", VerticalScroll)
        assert scroll.scrollbar_size_vertical == 1
