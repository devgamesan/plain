from dataclasses import replace

import pytest
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll

from tests.state_test_helpers import reduce_state
from zivo.models import (
    ActionsConfig,
    AppConfig,
    CommandPaletteItemViewState,
    CommandPaletteViewState,
    CustomActionConfig,
)
from zivo.state import (
    build_initial_app_state,
    select_command_palette_state,
)
from zivo.state.actions import BeginCommandPalette
from zivo.state.command_palette import get_command_palette_items
from zivo.ui.command_palette import CommandPalette


class _PaletteHarness(App[None]):
    CSS = """
    #command-palette { display: block; height: 10; width: 50; }
    #command-palette-items-scroll { height: 1fr; max-height: 1fr; }
    """

    def __init__(self, state: CommandPaletteViewState) -> None:
        super().__init__()
        self.palette_state = state

    def compose(self) -> ComposeResult:
        yield CommandPalette(self.palette_state, id="command-palette")


def test_empty_palette_starts_with_fixed_categories() -> None:
    state = reduce_state(build_initial_app_state(), BeginCommandPalette())

    items = get_command_palette_items(state)

    assert [item.category for item in items] == sorted(
        (item.category for item in items),
        key=lambda category: ("Navigate", "File", "Search", "View", "System").index(category),
    )


def test_command_palette_matches_aliases_and_is_deterministic() -> None:
    state = reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = replace(state, command_palette=replace(state.command_palette, query="duplicate"))

    items = get_command_palette_items(state)
    assert items[0].id == "copy_targets"
    assert items[0].keywords

    fuzzy_state = replace(state, command_palette=replace(state.command_palette, query="gth"))
    first = tuple(item.id for item in get_command_palette_items(fuzzy_state))
    second = tuple(item.id for item in get_command_palette_items(fuzzy_state))
    assert first == second


def test_disabled_command_reason_is_shared_by_selector_and_submit_path() -> None:
    state = reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = replace(state, command_palette=replace(state.command_palette, query="go forward"))

    item = get_command_palette_items(state)[0]
    view = select_command_palette_state(state)

    assert item.enabled is False
    assert item.disabled_reason == "No directory history in this direction"
    assert view is not None
    assert view.footer_message == item.disabled_reason
    assert view.items[0].disabled_reason == item.disabled_reason


def test_custom_actions_remain_searchable_by_name() -> None:
    state = replace(
        build_initial_app_state(),
        config=AppConfig(
            actions=ActionsConfig(
                custom=(CustomActionConfig(name="Optimize PNG", command=("optipng",)),)
            )
        ),
    )
    state = reduce_state(state, BeginCommandPalette())
    state = replace(state, command_palette=replace(state.command_palette, query="optimize"))

    items = get_command_palette_items(state)
    assert [item.id for item in items] == ["custom_action:0"]
    assert items[0].category == "Custom actions"


def test_context_mismatched_custom_action_remains_visible_with_reason() -> None:
    state = replace(
        build_initial_app_state(),
        config=AppConfig(
            actions=ActionsConfig(
                custom=(
                    CustomActionConfig(
                        name="Lint Python file",
                        command=("ruff", "check", "{file}"),
                        when="single_file",
                        extensions=("py",),
                    ),
                )
            )
        ),
    )
    state = reduce_state(state, BeginCommandPalette())

    item = next(
        item
        for item in get_command_palette_items(state)
        if item.id == "custom_action:0"
    )

    assert item.enabled is False
    assert item.disabled_reason == "Select one matching file for this custom action"


@pytest.mark.asyncio
async def test_command_palette_scrolls_to_a_selected_tail_command() -> None:
    categories = ("Navigate", "File", "Search", "View", "System")
    state = CommandPaletteViewState(
        title="Command Palette",
        query="",
        items=tuple(
            CommandPaletteItemViewState(
                label=f"Command {index}",
                shortcut=None,
                enabled=True,
                selected=index == 29,
                category=categories[min(index // 6, len(categories) - 1)],
            )
            for index in range(30)
        ),
        empty_message="No matching commands",
        has_more_items=True,
    )

    app = _PaletteHarness(state)
    async with app.run_test(size=(60, 20)) as pilot:
        await pilot.pause()
        scroll = app.query_one("#command-palette-items-scroll", VerticalScroll)
        assert scroll.virtual_size.height > scroll.region.height
        assert scroll.scroll_y == scroll.max_scroll_y
