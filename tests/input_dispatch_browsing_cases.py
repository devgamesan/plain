# ruff: noqa: F403,F405

import os

from .input_dispatch_helpers import *
from .state_test_helpers import reduce_state


def _reduce_state(state, action):
    return reduce_state(state, action)


def test_browsing_down_dispatches_move_cursor() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="down")

    assert actions[0] == SetNotification(None)
    assert actions[1] == MoveCursor(
        delta=1,
        visible_paths=(
            "/home/tadashi/develop/zivo/docs",
            "/home/tadashi/develop/zivo/src",
            "/home/tadashi/develop/zivo/tests",
            "/home/tadashi/develop/zivo/pyproject.toml",
            "/home/tadashi/develop/zivo/README.md",
        ),
    )


def test_iter_bound_keys_includes_printable_text_input_keys() -> None:
    keys = iter_bound_keys()

    assert "e" in keys
    assert "T" in keys
    assert "/" in keys
    assert ":" in keys
    assert "space" in keys
    assert "a" in keys
    assert "g" in keys
    assert "b" in keys
    assert "." in keys
    assert "enter" in keys
    assert "shift+up" in keys
    assert "shift+down" in keys
    assert "shift+delete" in keys
    assert "{" in keys
    assert "}" in keys
    assert "m" in keys


def test_browsing_j_dispatches_move_cursor() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="j", character="j")

    assert actions[0] == SetNotification(None)
    assert actions[1] == MoveCursor(
        delta=1,
        visible_paths=(
            "/home/tadashi/develop/zivo/docs",
            "/home/tadashi/develop/zivo/src",
            "/home/tadashi/develop/zivo/tests",
            "/home/tadashi/develop/zivo/pyproject.toml",
            "/home/tadashi/develop/zivo/README.md",
        ),
    )


def test_browsing_k_dispatches_move_cursor() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="k", character="k")

    assert actions[0] == SetNotification(None)
    assert actions[1] == MoveCursor(
        delta=-1,
        visible_paths=(
            "/home/tadashi/develop/zivo/docs",
            "/home/tadashi/develop/zivo/src",
            "/home/tadashi/develop/zivo/tests",
            "/home/tadashi/develop/zivo/pyproject.toml",
            "/home/tadashi/develop/zivo/README.md",
        ),
    )


def test_search_workspace_enter_warns_when_no_cursor() -> None:
    state = replace(
        build_initial_app_state(),
        search_workspace=SearchWorkspaceState(
            kind="find",
            root_path="/home/tadashi/develop/zivo",
            query="readme",
        ),
        current_pane=PaneState(
            directory_path="/home/tadashi/develop/zivo",
            entries=(),
            cursor_path=None,
        ),
    )

    actions = dispatch_key_input(state, key="enter")

    assert len(actions) == 1
    assert isinstance(actions[0], SetNotification)
    assert actions[0].notification.level == "warning"
    assert "No file selected" in actions[0].notification.message


def test_search_workspace_enter_opens_file() -> None:
    state = replace(
        build_initial_app_state(),
        search_workspace=SearchWorkspaceState(
            kind="find",
            root_path="/home/tadashi/develop/zivo",
            query="readme",
        ),
        current_pane=PaneState(
            directory_path="/home/tadashi/develop/zivo",
            entries=(
                DirectoryEntryState(
                    path="/home/tadashi/develop/zivo/README.md",
                    name="README.md",
                    kind="file",
                ),
            ),
            cursor_path="/home/tadashi/develop/zivo/README.md",
        ),
    )

    actions = dispatch_key_input(state, key="enter")

    assert actions[0] == SetNotification(None)
    assert actions[1] == OpenPathWithDefaultApp("/home/tadashi/develop/zivo/README.md")


def test_search_workspace_enter_opens_grep_result() -> None:
    # Grep workspace uses encoded paths: "path\x00line_number"
    encoded_path = "/home/tadashi/develop/zivo/README.md\x0042"
    state = replace(
        build_initial_app_state(),
        search_workspace=SearchWorkspaceState(
            kind="grep",
            root_path="/home/tadashi/develop/zivo",
            query="TODO",
        ),
        current_pane=PaneState(
            directory_path="/home/tadashi/develop/zivo",
            entries=(
                DirectoryEntryState(
                    path=encoded_path,
                    name="README.md:42: TODO: implement this",
                    kind="file",
                ),
            ),
            cursor_path=encoded_path,
        ),
    )

    actions = dispatch_key_input(state, key="enter")

    assert actions[0] == SetNotification(None)
    assert actions[1] == OpenPathInGuiEditor(
        "/home/tadashi/develop/zivo/README.md", line_number=42, column_number=1
    )


def test_search_workspace_copy_paths_uses_system_clipboard_action() -> None:
    state = replace(
        build_initial_app_state(),
        search_workspace=SearchWorkspaceState(
            kind="find",
            root_path="/home/tadashi/develop/zivo",
            query="readme",
        ),
    )

    actions = dispatch_key_input(state, key="C", character="C")

    assert actions == (SetNotification(None), CopyPathsToClipboard())


def test_search_workspace_colon_opens_command_palette() -> None:
    state = replace(
        build_initial_app_state(),
        search_workspace=SearchWorkspaceState(
            kind="find",
            root_path="/home/tadashi/develop/zivo",
            query="readme",
        ),
    )

    actions = dispatch_key_input(state, key=":", character=":")

    assert actions == (SetNotification(None), BeginCommandPalette())


def test_search_workspace_colon_character_opens_command_palette() -> None:
    state = replace(
        build_initial_app_state(),
        search_workspace=SearchWorkspaceState(
            kind="find",
            root_path="/home/tadashi/develop/zivo",
            query="readme",
        ),
    )

    actions = dispatch_key_input(state, key="shift+semicolon", character=":")

    assert actions == (SetNotification(None), BeginCommandPalette())


def test_search_workspace_grep_m_toggles_match_and_file_views() -> None:
    state = replace(
        build_initial_app_state(),
        search_workspace=SearchWorkspaceState(
            kind="grep",
            root_path="/home/tadashi/develop/zivo",
            query="TODO",
        ),
    )

    actions = dispatch_key_input(state, key="m", character="m")

    assert actions == (SetNotification(None), ToggleSearchWorkspaceGrepDisplayMode())


def test_search_workspace_escape_clears_filter_when_active() -> None:
    base = build_initial_app_state()
    state = replace(
        base,
        search_workspace=SearchWorkspaceState(
            kind="find",
            root_path="/home/tadashi/develop/zivo",
            query="readme",
        ),
        filter=replace(base.filter, query="docs", active=True),
    )

    actions = dispatch_key_input(state, key="escape")

    assert actions == (SetNotification(None), CancelFilterInput())


def test_search_workspace_escape_clears_selection_when_no_filter() -> None:
    state = replace(
        build_initial_app_state(),
        search_workspace=SearchWorkspaceState(
            kind="find",
            root_path="/home/tadashi/develop/zivo",
            query="readme",
        ),
    )

    actions = dispatch_key_input(state, key="escape")

    assert actions == (SetNotification(None), ClearSelection())


def test_browsing_prefix_key_starts_multi_key_sequence(monkeypatch) -> None:
    monkeypatch.setattr(
        input_module,
        "_MULTI_KEY_COMMAND_DISPATCH",
        {
            ("y", "y"): lambda _state, ctx: (
                SetNotification(None),
                CopyTargets(ctx.target_paths),
            )
        },
    )
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="y", character="y")

    assert actions == (
        SetNotification(None),
        SetPendingKeySequence(keys=("y",), possible_next_keys=("y",)),
    )


def test_browsing_prefix_key_completion_dispatches_handler(monkeypatch) -> None:
    monkeypatch.setattr(
        input_module,
        "_MULTI_KEY_COMMAND_DISPATCH",
        {
            ("y", "y"): lambda _state, ctx: (
                SetNotification(None),
                CopyTargets(ctx.target_paths),
            )
        },
    )
    state = replace(
        build_initial_app_state(),
        pending_key_sequence=PendingKeySequenceState(
            keys=("y",),
            possible_next_keys=("y",),
        ),
    )

    actions = dispatch_key_input(state, key="y", character="y")

    assert actions == (
        SetNotification(None),
        ClearPendingKeySequence(),
        CopyTargets(("/home/tadashi/develop/zivo/docs",)),
    )


def test_browsing_prefix_key_escape_clears_sequence(monkeypatch) -> None:
    monkeypatch.setattr(
        input_module,
        "_MULTI_KEY_COMMAND_DISPATCH",
        {
            ("y", "y"): lambda _state, ctx: (
                SetNotification(None),
                CopyTargets(ctx.target_paths),
            )
        },
    )
    state = replace(
        build_initial_app_state(),
        pending_key_sequence=PendingKeySequenceState(
            keys=("y",),
            possible_next_keys=("y",),
        ),
    )

    actions = dispatch_key_input(state, key="escape")

    assert actions == (SetNotification(None), ClearPendingKeySequence())


def test_browsing_prefix_key_invalid_followup_warns_and_clears(monkeypatch) -> None:
    monkeypatch.setattr(
        input_module,
        "_MULTI_KEY_COMMAND_DISPATCH",
        {
            ("y", "y"): lambda _state, ctx: (
                SetNotification(None),
                CopyTargets(ctx.target_paths),
            )
        },
    )
    state = replace(
        build_initial_app_state(),
        pending_key_sequence=PendingKeySequenceState(
            keys=("y",),
            possible_next_keys=("y",),
        ),
    )

    actions = dispatch_key_input(state, key="x", character="x")

    assert actions == (
        SetNotification(
            NotificationState(level="warning", message="No multi-key command matches 'yx'")
        ),
        ClearPendingKeySequence(),
    )


def test_browsing_shift_down_dispatches_range_selection_move() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="shift+down")

    assert actions[0] == SetNotification(None)
    assert actions[1] == MoveCursorAndSelectRange(
        delta=1,
        visible_paths=(
            "/home/tadashi/develop/zivo/docs",
            "/home/tadashi/develop/zivo/src",
            "/home/tadashi/develop/zivo/tests",
            "/home/tadashi/develop/zivo/pyproject.toml",
            "/home/tadashi/develop/zivo/README.md",
        ),
    )


def test_browsing_down_clears_range_selection_before_moving_cursor() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        current_pane=replace(
            state.current_pane,
            selected_paths=frozenset(
                {
                    "/home/tadashi/develop/zivo/docs",
                    "/home/tadashi/develop/zivo/src",
                }
            ),
            selection_anchor_path="/home/tadashi/develop/zivo/docs",
        ),
    )

    actions = dispatch_key_input(state, key="down")

    assert actions == (
        SetNotification(None),
        ClearSelection(),
        MoveCursor(
            delta=1,
            visible_paths=(
                "/home/tadashi/develop/zivo/docs",
                "/home/tadashi/develop/zivo/src",
                "/home/tadashi/develop/zivo/tests",
                "/home/tadashi/develop/zivo/pyproject.toml",
                "/home/tadashi/develop/zivo/README.md",
            ),
        ),
    )


def test_browsing_space_toggles_selection_and_advances_cursor() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="space")

    assert actions[0] == SetNotification(None)
    assert actions[1] == ToggleSelectionAndAdvance(
        path="/home/tadashi/develop/zivo/docs",
        visible_paths=(
            "/home/tadashi/develop/zivo/docs",
            "/home/tadashi/develop/zivo/src",
            "/home/tadashi/develop/zivo/tests",
            "/home/tadashi/develop/zivo/pyproject.toml",
            "/home/tadashi/develop/zivo/README.md",
        ),
    )


def test_browsing_escape_clears_selection() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="escape")

    assert actions == (SetNotification(None), ClearSelection())


def test_browsing_escape_clears_active_filter_before_selection() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        filter=replace(state.filter, query="docs", active=True),
    )

    actions = dispatch_key_input(state, key="escape")

    assert actions == (SetNotification(None), CancelFilterInput())


def test_browsing_slash_enters_filter_mode() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="/", character="/")

    assert actions == (SetNotification(None), BeginFilterInput())


def test_browsing_q_dispatches_exit_current_path() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="q", character="q")

    assert actions == (SetNotification(None), BeginExitCurrentPath())


def test_browsing_uppercase_printable_key_is_ignored() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="X", character="X")

    assert actions == ()


def test_browsing_lowercase_f_begins_file_search() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="f")

    assert len(actions) == 2
    assert isinstance(actions[1], BeginFileSearch)


def test_browsing_lowercase_g_begins_grep_search() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="g")

    assert len(actions) == 2
    assert isinstance(actions[1], BeginGrepSearch)


def test_browsing_lowercase_b_begins_bookmark_search() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="b")

    assert len(actions) == 2
    assert isinstance(actions[1], BeginBookmarkSearch)


def test_browsing_lowercase_n_begins_create_file() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="n")

    assert len(actions) == 2
    assert isinstance(actions[1], BeginCreateInput)
    assert actions[1].kind == "file"


def test_browsing_capital_N_begins_create_directory() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="N")

    assert len(actions) == 2
    assert isinstance(actions[1], BeginCreateInput)
    assert actions[1].kind == "dir"


def test_browsing_capital_B_adds_bookmark_for_current_directory() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="B")

    assert actions == (
        SetNotification(None),
        AddBookmark(path="/home/tadashi/develop/zivo"),
    )


def test_browsing_capital_B_removes_bookmark_for_current_directory() -> None:
    state = build_initial_app_state(
        config=AppConfig(bookmarks=BookmarkConfig(paths=("/home/tadashi/develop/zivo",)))
    )

    actions = dispatch_key_input(state, key="B")

    assert actions == (
        SetNotification(None),
        RemoveBookmark(path="/home/tadashi/develop/zivo"),
    )


def test_browsing_lowercase_c_dispatches_copy_targets() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="c", character="c")

    assert actions == (
        SetNotification(None),
        CopyTargets(("/home/tadashi/develop/zivo/docs",)),
    )


def test_browsing_x_dispatches_cut_targets() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="x", character="x")

    assert actions == (
        SetNotification(None),
        CutTargets(("/home/tadashi/develop/zivo/docs",)),
    )


def test_browsing_v_dispatches_paste_clipboard() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="v", character="v")

    assert actions == (SetNotification(None), PasteClipboard())


def test_browsing_z_dispatches_undo_last_operation() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="z", character="z")

    assert actions == (SetNotification(None), UndoLastOperation())


def test_browsing_capital_C_dispatches_copy_paths_to_clipboard() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="C")

    assert actions == (SetNotification(None), CopyPathsToClipboard())


def test_browsing_i_dispatches_show_attributes() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="i", character="i")

    assert actions == (SetNotification(None), ShowAttributes())


def test_browsing_dot_toggles_hidden_files() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key=".", character=".")

    assert actions == (SetNotification(None), ToggleHiddenFiles())


def test_browsing_h_goes_to_parent_directory() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="h", character="h")

    assert actions == (SetNotification(None), GoToParentDirectory())


def test_browsing_right_enters_directory() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="right")

    assert actions == (SetNotification(None), EnterCursorDirectory())


def test_browsing_l_enters_directory() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="l", character="l")

    assert actions == (SetNotification(None), EnterCursorDirectory())


def test_browsing_right_on_file_does_nothing() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        current_pane=replace(
            state.current_pane,
            cursor_path="/home/tadashi/develop/zivo/README.md",
        ),
    )

    actions = dispatch_key_input(state, key="right")

    assert actions == ()


def test_browsing_enter_on_file_dispatches_open_with_default_app() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        current_pane=replace(
            state.current_pane,
            cursor_path="/home/tadashi/develop/zivo/README.md",
        ),
    )

    actions = dispatch_key_input(state, key="enter")

    assert actions == (
        SetNotification(None),
        OpenPathWithDefaultApp("/home/tadashi/develop/zivo/README.md"),
    )


def test_browsing_shift_m_dispatches_open_file_manager() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="M", character="M")

    assert actions == (
        SetNotification(None),
        OpenPathWithDefaultApp("/home/tadashi/develop/zivo"),
    )


def test_browsing_e_on_file_dispatches_open_in_editor() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        current_pane=replace(
            state.current_pane,
            cursor_path="/home/tadashi/develop/zivo/README.md",
        ),
    )

    actions = dispatch_key_input(state, key="e", character="e")

    assert actions == (
        SetNotification(None),
        OpenPathInEditor("/home/tadashi/develop/zivo/README.md"),
    )


def test_browsing_shift_o_on_file_dispatches_open_in_gui_editor() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        current_pane=replace(
            state.current_pane,
            cursor_path="/home/tadashi/develop/zivo/README.md",
        ),
    )

    actions = dispatch_key_input(state, key="O", character="O")

    assert actions == (
        SetNotification(None),
        OpenPathInGuiEditor("/home/tadashi/develop/zivo/README.md"),
    )


def test_browsing_e_on_directory_warns() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="e", character="e")

    assert actions == (
        SetNotification(
            NotificationState(level="warning", message="Editor launch requires a file")
        ),
    )


def test_browsing_capital_R_reloads_current_directory() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="R")

    assert actions == (SetNotification(None), ReloadDirectory())


def test_browsing_lowercase_r_begins_rename_for_single_target() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="r")

    assert actions == (
        SetNotification(None),
        BeginRenameInput("/home/tadashi/develop/zivo/docs"),
    )


def test_browsing_lowercase_r_warns_for_multiple_targets() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        current_pane=replace(
            state.current_pane,
            selected_paths=frozenset(
                {
                    "/home/tadashi/develop/zivo/docs",
                    "/home/tadashi/develop/zivo/src",
                }
            ),
        ),
    )

    actions = dispatch_key_input(state, key="r")

    assert actions == (
        SetNotification(
            NotificationState(level="warning", message="Rename requires a single target")
        ),
    )


def test_browsing_colon_opens_command_palette() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key=":", character=":")

    assert actions == (SetNotification(None), BeginCommandPalette())


def test_browsing_colon_character_opens_command_palette() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="shift+semicolon", character=":")

    assert actions == (SetNotification(None), BeginCommandPalette())


def test_browsing_o_opens_new_tab() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="o", character="o")

    assert actions == (SetNotification(None), OpenNewTab())


def test_browsing_w_closes_current_tab() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="w", character="w")

    assert actions == (SetNotification(None), CloseCurrentTab())


def test_browsing_tab_activates_next_tab() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="tab")

    assert actions == (SetNotification(None), ActivateNextTab())


def test_browsing_shift_tab_activates_previous_tab() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="shift+tab")

    assert actions == (SetNotification(None), ActivatePreviousTab())


def test_browsing_number_activates_direct_tab() -> None:
    state = _reduce_state(build_initial_app_state(), OpenNewTab())

    actions = dispatch_key_input(state, key="1", character="1")

    assert actions == (SetNotification(None), ActivateTabByIndex(0))


def test_browsing_zero_activates_tenth_tab() -> None:
    state = build_initial_app_state()
    for _ in range(9):
        state = _reduce_state(state, OpenNewTab())

    actions = dispatch_key_input(state, key="0", character="0")

    assert actions == (SetNotification(None), ActivateTabByIndex(9))


def test_browsing_number_warns_when_target_tab_is_missing() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="2", character="2")

    assert actions == (
        SetNotification(NotificationState(level="warning", message="Tab 2 is not open")),
    )


def test_browsing_p_toggles_transfer_mode() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="p", character="p")

    assert actions == (SetNotification(None), ToggleTransferMode())


def test_search_palette_j_key_updates_query() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(source="file_search", query="ab"),
    )

    actions = dispatch_key_input(state, key="j", character="j")

    assert actions == (SetNotification(None), SetCommandPaletteQuery("abj"))


def test_search_palette_k_key_updates_query() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="grep_search",
            query="ab",
            grep_search_keyword="ab",
        ),
    )

    actions = dispatch_key_input(state, key="k", character="k")

    assert actions == (
        SetNotification(None),
        SetGrepSearchField(field="keyword", value="abk"),
    )


def test_grep_palette_tab_cycles_active_field() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(source="grep_search"),
    )

    actions = dispatch_key_input(state, key="tab")

    assert actions == (SetNotification(None), CycleGrepSearchField(delta=1))


def test_grep_palette_shift_tab_cycles_active_field_backwards() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(source="grep_search"),
    )

    actions = dispatch_key_input(state, key="shift+tab")

    assert actions == (SetNotification(None), CycleGrepSearchField(delta=-1))


def test_grep_palette_printable_key_updates_include_field() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="grep_search",
            grep_search_active_field="include",
            grep_search_include_extensions="p",
        ),
    )

    actions = dispatch_key_input(state, key="y", character="y")

    assert actions == (
        SetNotification(None),
        SetGrepSearchField(field="include", value="py"),
    )


def test_grep_palette_printable_key_updates_filename_field() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="grep_search",
            grep_search_active_field="filename",
            grep_search_filename_filter="READ",
        ),
    )

    actions = dispatch_key_input(state, key="m", character="m")

    assert actions == (
        SetNotification(None),
        SetGrepSearchField(field="filename", value="READm"),
    )


def test_commands_palette_j_key_moves_cursor() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(source="commands", query=""),
    )

    actions = dispatch_key_input(state, key="j", character="j")

    assert actions == (SetNotification(None), MoveCommandPaletteCursor(delta=1))


def test_search_palette_down_moves_cursor() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(source="file_search", query=""),
    )

    actions = dispatch_key_input(state, key="down")

    assert actions == (SetNotification(None), MoveCommandPaletteCursor(delta=1))


def test_go_to_path_palette_tab_completes_selected_candidate() -> None:
    state = _reduce_go_to_path_state(
        query="do",
        candidates=("/tmp/project/docs", "/tmp/project/downloads"),
        cursor_index=1,
        current_path="/tmp/project",
    )

    actions = dispatch_key_input(state, key="tab")

    assert actions == (SetNotification(None), SetCommandPaletteQuery("downloads"))


def test_go_to_path_palette_tab_appends_separator_for_single_candidate() -> None:
    state = _reduce_go_to_path_state(
        query="do",
        candidates=("/tmp/project/docs",),
        current_path="/tmp/project",
    )

    actions = dispatch_key_input(state, key="tab")

    assert actions == (SetNotification(None), SetCommandPaletteQuery(f"docs{os.sep}"))


def test_go_to_path_palette_tab_warns_without_candidates() -> None:
    state = _reduce_go_to_path_state(
        query="missing",
        candidates=(),
        current_path="/tmp/project",
    )

    actions = dispatch_key_input(state, key="tab")

    assert actions == (
        SetNotification(
            NotificationState(
                level="warning",
                message="No matching directory to complete",
            )
        ),
    )


def test_grep_palette_pageup_accounts_for_extra_input_rows() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(source="grep_search"),
    )

    actions = dispatch_key_input(state, key="pageup")

    assert actions == (SetNotification(None), MoveCommandPaletteCursor(delta=-12))


def test_grep_palette_pagedown_accounts_for_extra_input_rows() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(source="grep_search"),
    )

    actions = dispatch_key_input(state, key="pagedown")

    assert actions == (SetNotification(None), MoveCommandPaletteCursor(delta=12))


def test_browsing_s_cycles_sort_state() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="s", character="s")

    assert actions == (
        SetNotification(None),
        SetSort(field="name", descending=True),
    )


def test_browsing_s_cycles_from_name_desc_to_modified_desc() -> None:
    state = replace(
        build_initial_app_state(),
        sort=replace(build_initial_app_state().sort, field="name", descending=True),
    )

    actions = dispatch_key_input(state, key="s", character="s")

    assert actions == (
        SetNotification(None),
        SetSort(field="modified", descending=True),
    )


def test_browsing_d_dispatches_delete_targets() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="d", character="d")

    assert actions == (
        SetNotification(None),
        BeginDeleteTargets(("/home/tadashi/develop/zivo/docs",)),
    )


def test_browsing_d_warns_when_no_target_exists() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        current_pane=replace(state.current_pane, entries=(), cursor_path=None),
    )

    actions = dispatch_key_input(state, key="d", character="d")

    assert actions == (
        SetNotification(NotificationState(level="warning", message="Nothing to delete")),
    )


def test_browsing_delete_dispatches_delete_targets() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="delete")

    assert actions == (
        SetNotification(None),
        BeginDeleteTargets(("/home/tadashi/develop/zivo/docs",)),
    )


def test_browsing_delete_warns_when_no_target_exists() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        current_pane=replace(state.current_pane, entries=(), cursor_path=None),
    )

    actions = dispatch_key_input(state, key="delete")

    assert actions == (
        SetNotification(NotificationState(level="warning", message="Nothing to delete")),
    )


def test_browsing_shift_delete_dispatches_permanent_delete_targets() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="shift+delete")

    assert actions == (
        SetNotification(None),
        BeginDeleteTargets(("/home/tadashi/develop/zivo/docs",), mode="permanent"),
    )


def test_browsing_uppercase_D_dispatches_permanent_delete_targets() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="D", character="D")

    assert actions == (
        SetNotification(None),
        BeginDeleteTargets(("/home/tadashi/develop/zivo/docs",), mode="permanent"),
    )


def test_browsing_uppercase_D_warns_when_no_target_exists() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        current_pane=replace(state.current_pane, entries=(), cursor_path=None),
    )

    actions = dispatch_key_input(state, key="D", character="D")

    assert actions == (
        SetNotification(
            NotificationState(level="warning", message="Nothing to permanently delete")
        ),
    )


def test_browsing_shift_delete_warns_when_no_target_exists() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        current_pane=replace(state.current_pane, entries=(), cursor_path=None),
    )

    actions = dispatch_key_input(state, key="shift+delete")

    assert actions == (
        SetNotification(
            NotificationState(level="warning", message="Nothing to permanently delete")
        ),
    )


def test_browsing_lowercase_a_selects_all_visible_entries() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="a", character="a")

    assert actions == (
        SetNotification(None),
        SelectAllVisibleEntries(
            (
                "/home/tadashi/develop/zivo/docs",
                "/home/tadashi/develop/zivo/src",
                "/home/tadashi/develop/zivo/tests",
                "/home/tadashi/develop/zivo/pyproject.toml",
                "/home/tadashi/develop/zivo/README.md",
            )
        ),
    )


def test_browsing_tilde_goes_to_home_directory() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="~")

    assert actions == (SetNotification(None), GoToHomeDirectory())


def test_browsing_capital_H_begins_history_search() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="H")

    assert len(actions) == 2
    assert isinstance(actions[1], BeginHistorySearch)


def test_browsing_capital_G_begins_go_to_path() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="G")

    assert len(actions) == 2
    assert isinstance(actions[1], BeginGoToPath)


def test_browsing_open_bracket_is_reserved_for_preview_scroll() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="[")

    assert actions == ()


def test_browsing_close_bracket_is_reserved_for_preview_scroll() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="]")

    assert actions == ()


def test_browsing_open_brace_dispatches_go_back() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="{")

    assert actions == (SetNotification(None), GoBack())


def test_browsing_close_brace_dispatches_go_forward() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="}")

    assert actions == (SetNotification(None), GoForward())
