import pytest
from textual.widgets import DataTable, Label, ListView

from plain import create_app
from plain.ui import StatusBar


def test_create_app_returns_plain_app() -> None:
    app = create_app()

    assert app.title == "Plain"
    assert app.sub_title == "Three-pane shell"


@pytest.mark.asyncio
async def test_app_renders_three_pane_shell() -> None:
    app = create_app()

    async with app.run_test():
        parent_list = app.query_one("#parent-pane-list", ListView)
        current_table = app.query_one("#current-pane-table", DataTable)
        child_list = app.query_one("#child-pane-list", ListView)
        status_bar = app.query_one("#status-bar", StatusBar)
        parent_entries = [str(item.query_one(Label).renderable) for item in parent_list.children]
        child_entries = [str(item.query_one(Label).renderable) for item in child_list.children]
        headers = [str(column.label) for column in current_table.ordered_columns]

        assert parent_entries == ["develop", "downloads", "notes.txt"]
        assert headers == ["種別", "名前", "サイズ", "更新日時"]
        assert current_table.row_count == 5
        assert child_entries == ["spec_mvp.md", "notes.md", "wireframes"]
        assert str(status_bar.renderable) == (
            "/home/tadashi/develop/plain | 5 items | 0 selected | "
            "sort: name asc | filter: none"
        )


@pytest.mark.asyncio
async def test_app_can_start_in_narrow_headless_mode() -> None:
    app = create_app()

    async with app.run_test(size=(72, 20)):
        assert app.query_one("#body")
