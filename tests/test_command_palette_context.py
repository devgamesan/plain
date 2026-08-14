from dataclasses import replace

import pytest
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static

from tests.state_test_helpers import reduce_state
from zivo.models import (
    ActionsConfig,
    AppConfig,
    CommandPaletteItemViewState,
    CommandPaletteViewState,
    CustomActionConfig,
)
from zivo.state import (
    DirectoryEntryState,
    PaneState,
    build_initial_app_state,
    select_command_palette_state,
)
from zivo.state.actions import BeginCommandPalette, SubmitCommandPalette
from zivo.state.command_palette import get_command_palette_items
from zivo.state.models import ClipboardState, FilterState, ForegroundOperationState
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


def test_empty_palette_starts_with_contextual_suggestions() -> None:
    state = reduce_state(build_initial_app_state(), BeginCommandPalette())

    items = get_command_palette_items(state)

    assert len(items) > 5
    suggested = items[:5]
    assert 0 < len(suggested) <= 5
    assert all(item.enabled for item in suggested)
    assert all(item.category == "Suggested" for item in suggested)
    assert len({item.id for item in items}) == len(items)
    assert {item.category for item in items} >= {"Navigate", "File", "Search", "View", "System"}


def _palette_state_with_entries(
    entries: tuple[DirectoryEntryState, ...],
    *,
    cursor_path: str | None,
    selected_paths: frozenset[str] = frozenset(),
):
    state = build_initial_app_state()
    state = replace(
        state,
        current_pane=replace(
            state.current_pane,
            entries=entries,
            cursor_path=cursor_path,
            selected_paths=selected_paths,
        ),
    )
    return reduce_state(state, BeginCommandPalette())


def test_empty_palette_suggests_file_operations_for_a_focused_file() -> None:
    path = "/tmp/README.md"
    state = _palette_state_with_entries(
        (DirectoryEntryState(path, "README.md", "file"),),
        cursor_path=path,
    )

    assert [item.label for item in get_command_palette_items(state)[:5]] == [
        "Open",
        "Edit with terminal editor",
        "Copy",
        "Rename",
        "Move to trash",
    ]


def test_empty_palette_suggests_enter_folder_for_a_focused_directory() -> None:
    path = "/tmp/docs"
    state = _palette_state_with_entries(
        (DirectoryEntryState(path, "docs", "dir"),),
        cursor_path=path,
    )

    assert [item.label for item in get_command_palette_items(state)[:5]] == [
        "Enter folder",
        "Copy",
        "Rename",
        "Compress as zip",
        "Move to trash",
    ]


def test_empty_palette_suggests_common_operations_for_multiple_mixed_targets() -> None:
    file_path = "/tmp/README.md"
    dir_path = "/tmp/docs"
    state = _palette_state_with_entries(
        (
            DirectoryEntryState(file_path, "README.md", "file"),
            DirectoryEntryState(dir_path, "docs", "dir"),
        ),
        cursor_path=dir_path,
        selected_paths=frozenset({file_path, dir_path}),
    )

    labels = [item.label for item in get_command_palette_items(state)[:5]]

    assert labels == ["Copy", "Cut", "Rename 2 items", "Compress as zip", "Move to trash"]
    assert "Open" not in labels
    assert "Edit with terminal editor" not in labels


def test_empty_palette_explains_selection_and_focus_mismatch() -> None:
    selected_path = "/tmp/README.md"
    focused_path = "/tmp/LICENSE"
    state = _palette_state_with_entries(
        (
            DirectoryEntryState(selected_path, "README.md", "file"),
            DirectoryEntryState(focused_path, "LICENSE", "file"),
        ),
        cursor_path=focused_path,
        selected_paths=frozenset({selected_path}),
    )

    view = select_command_palette_state(state)

    assert view is not None
    assert view.context_lines == (
        "Selection: 1 item (1 file)",
        "Focus: LICENSE — not included",
    )


def test_empty_palette_shows_current_folder_actions_without_a_target() -> None:
    state = _palette_state_with_entries((), cursor_path=None)
    state = replace(
        state,
        clipboard=ClipboardState(paths=("/tmp/source.txt", "/tmp/source-2.txt")),
        filter=FilterState(query="missing", active=True),
        command_palette=replace(state.command_palette, query=""),
    )

    labels = [item.label for item in get_command_palette_items(state)[:4]]

    assert labels == [
        "Create",
        "Paste 2 items here",
        "Clear filter",
        "Open current directory with terminal",
    ]
    assert select_command_palette_state(state).context_lines == (
        f"Current folder: {state.current_path}",
    )


def test_empty_palette_suggests_show_hidden_for_a_hidden_only_directory() -> None:
    hidden_path = "/tmp/.secrets"
    state = _palette_state_with_entries(
        (DirectoryEntryState(hidden_path, ".secrets", "dir", hidden=True),),
        cursor_path=None,
    )

    labels = [item.label for item in get_command_palette_items(state)]

    assert "Show hidden files" in labels


def test_typing_a_query_restores_the_full_searchable_command_set() -> None:
    state = reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = replace(state, command_palette=replace(state.command_palette, query="go back"))

    items = get_command_palette_items(state)

    assert [item.id for item in items] == ["go_back"]
    assert items[0].enabled is False


def test_command_palette_matches_aliases_and_is_deterministic() -> None:
    state = reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = replace(state, command_palette=replace(state.command_palette, query="duplicate"))

    items = get_command_palette_items(state)
    assert items[0].id == "duplicate_targets"
    assert items[0].keywords

    fuzzy_state = replace(state, command_palette=replace(state.command_palette, query="gth"))
    first = tuple(item.id for item in get_command_palette_items(fuzzy_state))
    second = tuple(item.id for item in get_command_palette_items(fuzzy_state))
    assert first == second


def test_duplicate_command_is_available_for_a_focused_target_without_a_fixed_key() -> None:
    state = reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = replace(state, command_palette=replace(state.command_palette, query="duplicate"))

    item = next(item for item in get_command_palette_items(state) if item.id == "duplicate_targets")

    assert item.enabled is True
    assert item.shortcut is None
    assert "clone" in item.keywords


def test_duplicate_command_is_disabled_in_search_workspace() -> None:
    state = reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = replace(
        state,
        current_path="search://readme?target=files&hidden=false&root=%2Ftmp",
        command_palette=replace(state.command_palette, query="duplicate"),
    )

    item = next(item for item in get_command_palette_items(state) if item.id == "duplicate_targets")

    assert item.enabled is False
    assert item.disabled_reason == "Unavailable in Search Workspace"


def test_mutating_commands_are_disabled_while_long_running_operation_is_active() -> None:
    state = reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = replace(
        state,
        foreground_operation=ForegroundOperationState(operation_id=9, kind="move"),
    )

    def item_for(query: str):
        queried = replace(state, command_palette=replace(state.command_palette, query=query))
        return get_command_palette_items(queried)[0]

    assert item_for("rename").disabled_reason == "Move is in progress"
    assert item_for("paste").disabled_reason == "Move is in progress"
    assert item_for("replace").disabled_reason == "Move is in progress"
    assert item_for("open").disabled_reason == "Move is in progress"
    assert item_for("find").enabled is True
    assert item_for("attributes").enabled is True


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


def test_search_workspace_exposes_replace_selected_results_for_file_targets() -> None:
    state = reduce_state(build_initial_app_state(), BeginCommandPalette())
    path = "/tmp/README.md"
    state = replace(
        state,
        current_path="search://readme?target=files&hidden=false&root=%2Ftmp",
        current_pane=PaneState(
            directory_path="search://readme?target=files&hidden=false&root=%2Ftmp",
            entries=(DirectoryEntryState(path, "README.md", "file"),),
            cursor_path=path,
            selected_paths=frozenset({path}),
        ),
        command_palette=replace(state.command_palette, query="replace"),
    )

    item = next(item for item in get_command_palette_items(state) if item.id == "replace_text")

    assert item.label == "Replace selected results"
    assert item.enabled is True


def test_search_workspace_replace_uses_selected_results_scope() -> None:
    state = reduce_state(build_initial_app_state(), BeginCommandPalette())
    path = "/tmp/README.md"
    state = replace(
        state,
        current_path="search://readme?target=files&hidden=false&root=%2Ftmp",
        current_pane=PaneState(
            directory_path="search://readme?target=files&hidden=false&root=%2Ftmp",
            entries=(DirectoryEntryState(path, "README.md", "file"),),
            cursor_path=path,
            selected_paths=frozenset({path}),
        ),
        command_palette=replace(state.command_palette, query="replace selected results"),
    )

    result = reduce_state(state, SubmitCommandPalette())

    assert result.command_palette is not None
    preview = result.command_palette.replace_preview
    assert preview.scope == "search_results"
    assert preview.result_origin == "workspace"
    assert preview.result_query == "readme"
    assert preview.target_paths == (path,)


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
    state = replace(state, command_palette=replace(state.command_palette, query="lint"))

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


@pytest.mark.asyncio
async def test_command_palette_renders_target_context_without_redundant_search_hint() -> None:
    state = CommandPaletteViewState(
        title="Command Palette",
        query="",
        items=(
            CommandPaletteItemViewState(
                label="Open",
                shortcut="enter",
                enabled=True,
                selected=True,
                category="Suggested",
            ),
        ),
        empty_message="No matching commands",
        context_lines=("Target: README.md — focused file",),
    )

    app = _PaletteHarness(state)
    async with app.run_test(size=(60, 20)) as pilot:
        await pilot.pause()
        context = app.query_one("#command-palette-context", Static)
        assert context.display is True
        assert "Target: README.md" in str(context.renderable)
        assert "Search all commands" not in str(context.renderable)
