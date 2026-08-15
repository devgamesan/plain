"""Selector tests for command palette and search workspaces."""

from tests.support.selectors import (
    AppConfig,
    BeginCommandPalette,
    BookmarkConfig,
    CommandPaletteItem,
    CommandPaletteState,
    DirectoryEntryState,
    FileSearchPaletteState,
    FileSearchResultState,
    GrepSearchPaletteState,
    GrepSearchResultState,
    HistoryState,
    PaneState,
    ReplacePreviewPaletteState,
    ReplacePreviewResultState,
    UndoDeletePathStep,
    UndoEntry,
    _reduce_state,
    _select_command_palette_window,
    build_initial_app_state,
    command_palette_module,
    replace,
    select_command_palette_state,
    selectors_module,
)


class TestCommandPaletteDynamicWindow:
    """コマンドパレットの動的表示ウィンドウ計算のテスト."""

    def test_default_command_palette_keeps_discoverable_command_catalog(self) -> None:
        """空クエリは文脈候補の下に全コマンドを保持する."""

        state = replace(
            _reduce_state(build_initial_app_state(), BeginCommandPalette()),
            terminal_height=24,
        )

        palette_state = select_command_palette_state(state)

        assert palette_state is not None
        assert len(palette_state.items) > 5
        assert all(item.category == "Suggested" for item in palette_state.items[:5])
        assert palette_state.has_more_items is True

class TestComputeSearchVisibleWindow:
    """Tests for dynamic search window size calculation."""

    def test_default_terminal_height(self) -> None:
        assert selectors_module.compute_search_visible_window(24) == 14

    def test_large_terminal(self) -> None:
        assert selectors_module.compute_search_visible_window(48) == 38

    def test_very_large_terminal(self) -> None:
        assert selectors_module.compute_search_visible_window(80) == 70

    def test_small_terminal_uses_minimum(self) -> None:
        assert selectors_module.compute_search_visible_window(10) == 3

    def test_tiny_terminal_uses_minimum(self) -> None:
        assert selectors_module.compute_search_visible_window(1) == 3

    def test_extra_rows_reduce_visible_window(self) -> None:
        assert selectors_module.compute_search_visible_window(24, extra_rows=2) == 12

class TestSelectCommandPaletteWindow:
    """Tests for _select_command_palette_window scrolling algorithm."""

    def test_empty_list(self) -> None:
        """空リストの場合は空のタプルが返されること"""
        items: tuple[CommandPaletteItem, ...] = ()
        result, title = _select_command_palette_window(items, 0)

        assert result == ()
        assert title == "Command Palette"

    def test_short_list(self) -> None:
        """ウィンドウサイズ以下の場合は全アイテムが表示されること"""
        items = tuple(
            CommandPaletteItem(id=f"item_{i}", label=f"Item {i}", shortcut=None, enabled=True)
            for i in range(5)
        )
        result, title = _select_command_palette_window(items, 2)

        assert len(result) == 5
        assert title == "Command Palette"
        assert result[2][0] == 2  # カーソル位置が2であること

    def test_exact_window_size(self) -> None:
        """ウィンドウサイズと同じ長さの場合は全アイテムが表示されること"""
        items = tuple(
            CommandPaletteItem(id=f"item_{i}", label=f"Item {i}", shortcut=None, enabled=True)
            for i in range(8)
        )
        result, title = _select_command_palette_window(items, 4)

        assert len(result) == 8
        assert title == "Command Palette"

    def test_center_alignment(self) -> None:
        """中央付近のアイテム選択時に中央揃えが維持されること"""
        items = tuple(
            CommandPaletteItem(id=f"item_{i}", label=f"Item {i}", shortcut=None, enabled=True)
            for i in range(20)
        )
        # 中央のアイテム（インデックス10）を選択
        result, title = _select_command_palette_window(items, 10)

        assert len(result) == 8  # ウィンドウサイズ
        assert title == "Command Palette (7-14 / 20)"
        # カーソルが中央に配置されること
        cursor_position_in_window = next(i for i, (idx, _) in enumerate(result) if idx == 10)
        assert cursor_position_in_window == 4  # ウィンドウの中央（0始まりで4）

    def test_top_boundary(self) -> None:
        """先頭付近のアイテム選択時に先頭から表示されること"""
        items = tuple(
            CommandPaletteItem(id=f"item_{i}", label=f"Item {i}", shortcut=None, enabled=True)
            for i in range(20)
        )
        # 先頭のアイテム（インデックス0）を選択
        result, title = _select_command_palette_window(items, 0)

        assert len(result) == 8
        assert title == "Command Palette (1-8 / 20)"
        assert result[0][0] == 0  # 先頭から表示

    def test_bottom_boundary(self) -> None:
        """末尾付近のアイテム選択時に末尾が見えること（主要なバグ修正）"""
        items = tuple(
            CommandPaletteItem(id=f"item_{i}", label=f"Item {i}", shortcut=None, enabled=True)
            for i in range(14)
        )
        # 最後のアイテム（インデックス13）を選択
        result, title = _select_command_palette_window(items, 13)

        assert len(result) == 8
        assert title == "Command Palette (7-14 / 14)"
        # 最後のアイテムが表示されていること
        assert result[-1][0] == 13
        assert result[-1][1].label == "Item 13"

    def test_last_item_visible(self) -> None:
        """最後のアイテムが必ず表示されること"""
        items = tuple(
            CommandPaletteItem(id=f"item_{i}", label=f"Item {i}", shortcut=None, enabled=True)
            for i in range(15)
        )
        # 最後のアイテム（インデックス14）を選択
        result, title = _select_command_palette_window(items, 14)

        assert len(result) == 8
        assert result[-1][0] == 14  # 最後のアイテムが表示されている
        assert result[0][0] == 7  # 先頭はインデックス7

    def test_second_last_item_visible(self) -> None:
        """最後から2番目のアイテムと最後のアイテムが両方表示されること"""
        items = tuple(
            CommandPaletteItem(id=f"item_{i}", label=f"Item {i}", shortcut=None, enabled=True)
            for i in range(14)
        )
        # 最後から2番目のアイテム（インデックス12）を選択
        result, title = _select_command_palette_window(items, 12)

        assert len(result) == 8
        # 最後から2番目と最後のアイテムが両方表示されていること
        visible_indices = [idx for idx, _ in result]
        assert 12 in visible_indices
        assert 13 in visible_indices
        assert result[-1][0] == 13  # 最後のアイテムが表示されている

class TestSelectSearchWindowWithDynamicSize:
    """Tests for _select_file_search_window with dynamic terminal height."""

    def test_large_terminal_shows_more_items(self) -> None:
        results = tuple(
            FileSearchResultState(
                path=f"/home/tadashi/develop/zivo/src/module_{index}.py",
                display_path=f"src/module_{index}.py",
            )
            for index in range(30)
        )
        state = _reduce_state(
            replace(build_initial_app_state(), terminal_height=48),
            BeginCommandPalette(),
        )
        state = replace(
            state,
            command_palette=CommandPaletteState(
                source="file_search",
                query=".py",
                cursor_index=15,
                file_search=FileSearchPaletteState(results=results),
            ),
        )

        palette_state = select_command_palette_state(state)

        assert palette_state is not None
        assert len(palette_state.items) == 30
        assert palette_state.items[15].selected is True
        assert palette_state.has_more_items is False

def test_command_palette_enables_undo_item_when_stack_is_present() -> None:
    state = replace(
        _reduce_state(build_initial_app_state(), BeginCommandPalette()),
        undo_stack=(UndoEntry(kind="paste_copy", steps=(UndoDeletePathStep("/tmp/copied"),)),),
    )
    state = replace(state, command_palette=replace(state.command_palette, query="undo"))

    items = {
        item.label: item for item in command_palette_module.get_command_palette_items(state)
    }
    assert items["Undo last file operation"].enabled is True

def test_command_palette_exposes_one_dynamic_narrow_view_command() -> None:
    state = replace(
        build_initial_app_state(),
        terminal_width=72,
        command_palette=CommandPaletteState(query="preview"),
    )

    items = command_palette_module.get_command_palette_items(state)
    narrow_items = [item for item in items if item.id == "toggle_narrow_pane_view"]

    assert len(narrow_items) == 1
    assert narrow_items[0].label == "Show preview or contents"
    assert narrow_items[0].shortcut == "tab"
    assert narrow_items[0].enabled is True

    details = replace(
        state,
        narrow_pane_view="details",
        command_palette=replace(state.command_palette, query="preview"),
    )
    details_item = next(
        item
        for item in command_palette_module.get_command_palette_items(details)
        if item.id == "toggle_narrow_pane_view"
    )
    assert details_item.label == "Back to file list"

def test_command_palette_includes_undo_item_and_disables_when_empty() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = replace(state, command_palette=replace(state.command_palette, query="undo"))

    items = {
        item.label: item for item in command_palette_module.get_command_palette_items(state)
    }
    assert items["Undo last file operation"].shortcut == "z"
    assert items["Undo last file operation"].enabled is False
    assert items["Undo last file operation"].disabled_reason == "No operation to undo"

def test_select_command_palette_state_disables_select_all_without_visible_entries() -> None:
    state = replace(
        build_initial_app_state(),
        current_pane=PaneState(
            directory_path="/home/tadashi/develop/zivo",
            entries=(
                DirectoryEntryState(
                    "/home/tadashi/develop/zivo/.env",
                    ".env",
                    "file",
                    hidden=True,
                ),
            ),
            cursor_path=None,
        ),
    )
    palette_state = select_command_palette_state(
        replace(
            _reduce_state(state, BeginCommandPalette()),
            command_palette=replace(CommandPaletteState(), query="select all"),
        )
    )

    assert palette_state is not None
    assert [item.label for item in palette_state.items] == ["Select all"]
    assert palette_state.items[0].enabled is False

def test_select_command_palette_state_enables_history_navigation_items() -> None:
    state = replace(
        _reduce_state(build_initial_app_state(), BeginCommandPalette()),
        history=HistoryState(
            back=("/tmp/a",),
            forward=("/tmp/b",),
        ),
        command_palette=replace(
            _reduce_state(build_initial_app_state(), BeginCommandPalette()).command_palette,
            query="go",
        ),
    )

    palette_state = select_command_palette_state(state)

    assert palette_state is not None
    assert any(item.label == "Go back" and item.enabled for item in palette_state.items)
    assert any(item.label == "Go forward" and item.enabled for item in palette_state.items)

def test_select_command_palette_state_enables_select_all_with_visible_entries() -> None:
    state = select_command_palette_state(
        replace(
            _reduce_state(build_initial_app_state(), BeginCommandPalette()),
            command_palette=replace(CommandPaletteState(), query="select all"),
        )
    )

    assert state is not None
    assert [item.label for item in state.items] == ["Select all"]
    assert state.items[0].enabled is True
    assert state.items[0].shortcut == "a"

def test_select_command_palette_state_filters_query() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = replace(
        state,
            command_palette=replace(state.command_palette, query="create"),
    )

    palette_state = select_command_palette_state(state)

    assert palette_state is not None
    assert [item.label for item in palette_state.items] == ["Create"]

def test_select_command_palette_state_for_file_search_results() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = replace(
        state,
        command_palette=CommandPaletteState(
            source="file_search",
            query="read",
            file_search=FileSearchPaletteState(
                results=(
                    FileSearchResultState(
                        path="/home/tadashi/develop/zivo/README.md",
                        display_path="README.md",
                    ),
                ),
            ),
        ),
    )

    palette_state = select_command_palette_state(state)

    assert palette_state is not None
    assert palette_state.title == "Find All (1-1 / 1)"
    assert palette_state.empty_message == "No matching files"
    assert [item.label for item in palette_state.items] == ["README.md"]

def test_select_command_palette_state_for_grep_search_includes_input_fields() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="grep_search",
            query="todo",
            grep_search=GrepSearchPaletteState(
                keyword="todo",
                filename_filter="main",
                include_extensions="py,ts",
                exclude_extensions="log",
                active_field="exclude",
            ),
        ),
    )

    palette_state = select_command_palette_state(state)

    assert palette_state is not None
    assert [field.label for field in palette_state.input_fields] == [
        "Keyword",
        "Scope",
        "Filter: Filename",
        "Include extensions",
        "Exclude extensions",
    ]
    assert [field.value for field in palette_state.input_fields] == [
        "todo", "current directory", "main", "py,ts", "log"
    ]
    assert [field.active for field in palette_state.input_fields] == [
        False,
        False,
        False,
        False,
        True,
    ]

def test_select_command_palette_state_for_grep_search_results() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = replace(
        state,
        command_palette=CommandPaletteState(
            source="grep_search",
            query="todo",
            grep_search=GrepSearchPaletteState(
                results=(
                    GrepSearchResultState(
                        path="/home/tadashi/develop/zivo/src/zivo/app.py",
                        display_path="src/zivo/app.py",
                        line_number=42,
                        line_text="TODO: update palette",
                    ),
                ),
            ),
        ),
    )

    palette_state = select_command_palette_state(state)

    assert palette_state is not None
    assert palette_state.title == "Grep (1-1 / 1)"
    assert [item.label for item in palette_state.items] == [
        "src/zivo/app.py:42: TODO: update palette"
    ]

def test_select_command_palette_state_for_text_replace_includes_input_fields() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="replace_text",
            replace_preview=ReplacePreviewPaletteState(
                find_text="todo",
                replacement_text="done",
                active_field="replace",
                preview_results=(
                    ReplacePreviewResultState(
                        path="/home/tadashi/develop/zivo/README.md",
                        display_path="README.md",
                        diff_text="--- before\n+++ after\n@@\n-todo item\n+done item\n",
                        match_count=2,
                        first_match_line_number=8,
                        first_match_before="todo item",
                        first_match_after="done item",
                    ),
                ),
                total_match_count=2,
                target_paths=("/home/tadashi/develop/zivo/README.md",),
            ),
        ),
    )

    palette_state = select_command_palette_state(state)

    assert palette_state is not None
    assert palette_state.title == "Replace Text (1 file(s), 2 match(es)) (1-1 / 1)"
    assert [field.label for field in palette_state.input_fields] == [
        "Scope",
        "Find",
        "Replace",
        "Filter: Filename",
        "Include extensions",
        "Exclude extensions",
    ]
    assert [field.value for field in palette_state.input_fields] == [
        "Current directory",
        "todo",
        "done",
        "",
        "",
        "",
    ]
    assert [field.active for field in palette_state.input_fields] == [
        False,
        False,
        True,
        False,
        False,
        False,
    ]
    assert [item.label for item in palette_state.items] == [
        "README.md (2): 8: todo item"
    ]
    assert palette_state.empty_message == "Preview shown in right pane. Press Enter to apply."

def test_select_command_palette_state_marks_selected_and_enabled_items() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())

    palette_state = select_command_palette_state(state)

    assert palette_state is not None
    assert palette_state.title.startswith("Command Palette")
    assert len(palette_state.items) > 5
    assert all(item.category == "Suggested" for item in palette_state.items[:5])
    assert palette_state.items[0].selected is True
    assert palette_state.items[0].enabled is True
    assert palette_state.context_lines
    assert palette_state.category_hint is None

def test_select_command_palette_state_shows_compress_as_zip_for_multiple_targets() -> None:
    state = replace(
        build_initial_app_state(),
        current_pane=replace(
            build_initial_app_state().current_pane,
            selected_paths=frozenset(
                {
                    "/home/tadashi/develop/zivo/docs",
                    "/home/tadashi/develop/zivo/src",
                }
            ),
        ),
    )
    palette_state = select_command_palette_state(
        replace(
            _reduce_state(state, BeginCommandPalette()),
            command_palette=replace(CommandPaletteState(), query="compress"),
        )
    )

    assert palette_state is not None
    assert [item.label for item in palette_state.items] == ["Compress as zip"]

def test_select_command_palette_state_shows_copy_path_shortcut() -> None:
    state = select_command_palette_state(
        replace(
            _reduce_state(build_initial_app_state(), BeginCommandPalette()),
            command_palette=replace(CommandPaletteState(), query="copy path"),
        )
    )

    assert state is not None
    assert [item.label for item in state.items] == ["Copy path"]
    assert state.items[0].shortcut is None

def test_select_command_palette_state_shows_extract_archive_for_supported_file() -> None:
    archive_path = "/home/tadashi/develop/zivo/archive.tar.gz"
    state = replace(
        build_initial_app_state(),
        current_pane=PaneState(
            directory_path="/home/tadashi/develop/zivo",
            entries=(
                DirectoryEntryState(archive_path, "archive.tar.gz", "file"),
            ),
            cursor_path=archive_path,
        ),
    )
    palette_state = select_command_palette_state(
        replace(
            _reduce_state(state, BeginCommandPalette()),
            command_palette=replace(CommandPaletteState(), query="extract"),
        )
    )

    assert palette_state is not None
    assert [item.label for item in palette_state.items] == ["Extract archive"]

def test_select_command_palette_state_shows_grep_searching_message() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = replace(
        state,
        command_palette=CommandPaletteState(
            source="grep_search",
            query="todo",
            grep_search=GrepSearchPaletteState(results=()),
        ),
        pending_grep_search_request_id=9,
    )

    palette_state = select_command_palette_state(state)

    assert palette_state is not None
    assert palette_state.title == "Grep"
    assert palette_state.empty_message == "Searching matches..."

def test_select_command_palette_state_shows_regex_error_message() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = replace(
        state,
        command_palette=CommandPaletteState(
            source="file_search",
            query="re:[",
            file_search=FileSearchPaletteState(
                error_message="Invalid regex: unterminated character set",
            ),
        ),
    )

    palette_state = select_command_palette_state(state)

    assert palette_state is not None
    assert palette_state.title == "Find All"
    assert palette_state.empty_message == "Invalid regex: unterminated character set"
    assert palette_state.items == ()

def test_select_command_palette_state_shows_replace_text_for_cursor_file() -> None:
    state = replace(
        build_initial_app_state(),
        current_pane=replace(
            build_initial_app_state().current_pane,
            cursor_path="/home/tadashi/develop/zivo/README.md",
        ),
    )
    palette_state = select_command_palette_state(
        replace(
            _reduce_state(state, BeginCommandPalette()),
            command_palette=replace(CommandPaletteState(), query="replace text"),
        )
    )

    assert palette_state is not None
    assert [item.label for item in palette_state.items] == ["Replace text"]
    assert palette_state.items[0].enabled is True

def test_select_command_palette_state_shows_replace_text_for_selected_files() -> None:
    state = replace(
        build_initial_app_state(),
        current_pane=PaneState(
            directory_path="/home/tadashi/develop/zivo",
            entries=(
                DirectoryEntryState("/home/tadashi/develop/zivo/README.md", "README.md", "file"),
                DirectoryEntryState("/home/tadashi/develop/zivo/src", "src", "dir"),
            ),
            cursor_path="/home/tadashi/develop/zivo/README.md",
            selected_paths=frozenset({"/home/tadashi/develop/zivo/README.md"}),
        ),
    )
    palette_state = select_command_palette_state(
        replace(
            _reduce_state(state, BeginCommandPalette()),
            command_palette=replace(CommandPaletteState(), query="replace text"),
        )
    )

    assert palette_state is not None
    assert [item.label for item in palette_state.items] == ["Replace text"]
    assert palette_state.items[0].enabled is True

def test_select_command_palette_state_shows_searching_message_while_file_search_is_pending(
) -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = replace(
        state,
        command_palette=CommandPaletteState(
            source="file_search",
            query=".py",
            file_search=FileSearchPaletteState(),
        ),
        pending_file_search_request_id=7,
    )

    palette_state = select_command_palette_state(state)

    assert palette_state is not None
    assert palette_state.title == "Find All"
    assert palette_state.empty_message == "Searching files..."
    assert palette_state.items == ()

def test_select_command_palette_state_shows_single_target_commands_when_filtered() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = replace(
        state,
        command_palette=replace(state.command_palette, query="rename"),
    )

    palette_state = select_command_palette_state(state)

    assert palette_state is not None
    assert [item.label for item in palette_state.items] == ["Rename"]
    assert palette_state.items[0].enabled is True

def test_select_command_palette_state_shows_single_target_shortcuts() -> None:
    state = select_command_palette_state(
        replace(
            _reduce_state(build_initial_app_state(), BeginCommandPalette()),
            command_palette=replace(CommandPaletteState(), query="attributes"),
        )
    )

    assert state is not None
    assert [item.label for item in state.items] == ["Show attributes"]
    assert [item.shortcut for item in state.items] == [None]

def test_select_command_palette_state_switches_bookmark_command_label() -> None:
    state = build_initial_app_state()
    palette_state = select_command_palette_state(
        replace(
            _reduce_state(state, BeginCommandPalette()),
            command_palette=replace(CommandPaletteState(), query="bookmark"),
        )
    )

    assert palette_state is not None
    assert any(item.label == "Bookmark this directory" for item in palette_state.items)
    assert any(
        item.label == "Bookmark this directory" and item.shortcut is None
        for item in palette_state.items
    )

    bookmarked_state = build_initial_app_state(
        config=AppConfig(
            bookmarks=BookmarkConfig(
                paths=("/home/tadashi/develop/zivo",)
            )
        )
    )
    bookmarked_palette_state = select_command_palette_state(
        replace(
            _reduce_state(bookmarked_state, BeginCommandPalette()),
            command_palette=replace(CommandPaletteState(), query="bookmark"),
        )
    )

    assert bookmarked_palette_state is not None
    assert any(item.label == "Remove bookmark" for item in bookmarked_palette_state.items)
    assert any(
        item.label == "Remove bookmark" and item.shortcut is None
        for item in bookmarked_palette_state.items
    )

def test_select_command_palette_state_uses_hidden_toggle_label_from_state() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = replace(
        state,
        command_palette=replace(state.command_palette, query="hidden"),
    )

    palette_state = select_command_palette_state(state)

    assert palette_state is not None
    assert [item.label for item in palette_state.items] == ["Show hidden files"]
    assert palette_state.items[0].shortcut == "."

    visible_state = replace(state, show_hidden=True)
    visible_palette_state = select_command_palette_state(visible_state)

    assert visible_palette_state is not None
    assert [item.label for item in visible_palette_state.items] == ["Hide hidden files"]
    assert visible_palette_state.items[0].shortcut == "."

def test_select_command_palette_state_windows_large_file_search_results() -> None:
    results = tuple(
        FileSearchResultState(
            path=f"/home/tadashi/develop/zivo/src/module_{index}.py",
            display_path=f"src/module_{index}.py",
        )
        for index in range(20)
    )
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = replace(
        state,
        command_palette=CommandPaletteState(
            source="file_search",
            query=".py",
            cursor_index=10,
            file_search=FileSearchPaletteState(results=results),
        ),
    )

    palette_state = select_command_palette_state(state)

    assert palette_state is not None
    assert palette_state.title == "Find All (6-16 / 20)"
    assert [item.label for item in palette_state.items] == [
        "src/module_5.py",
        "src/module_6.py",
        "src/module_7.py",
        "src/module_8.py",
        "src/module_9.py",
        "src/module_10.py",
        "src/module_11.py",
        "src/module_12.py",
        "src/module_13.py",
        "src/module_14.py",
        "src/module_15.py",
    ]
    assert palette_state.items[5].selected is True
    assert palette_state.has_more_items is True

def test_select_command_palette_state_windows_large_grep_search_results() -> None:
    results = tuple(
        GrepSearchResultState(
            path=f"/home/tadashi/develop/zivo/src/module_{index}.py",
            display_path=f"src/module_{index}.py",
            line_number=index + 1,
            line_text="TODO: update palette",
        )
        for index in range(20)
    )
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = replace(
        state,
        command_palette=CommandPaletteState(
            source="grep_search",
            query="todo",
            cursor_index=10,
            grep_search=GrepSearchPaletteState(results=results),
        ),
    )

    palette_state = select_command_palette_state(state)

    assert palette_state is not None
    assert palette_state.title == "Grep (6-16 / 20)"
    assert len(palette_state.items) == 11
    assert palette_state.items[5].selected is True
    assert palette_state.has_more_items is True
