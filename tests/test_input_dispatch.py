from dataclasses import replace

import zivo.state.input as input_module
from zivo.models import AppConfig, BookmarkConfig, CreateZipArchiveRequest
from zivo.state import (
    ActivateNextTab,
    ActivatePreviousTab,
    AddBookmark,
    BeginBookmarkSearch,
    BeginCommandPalette,
    BeginCreateInput,
    BeginDeleteTargets,
    BeginFileSearch,
    BeginFilterInput,
    BeginGoToPath,
    BeginGrepSearch,
    BeginHistorySearch,
    BeginRenameInput,
    CancelCommandPalette,
    CancelDeleteConfirmation,
    CancelFilterInput,
    CancelPasteConflict,
    CancelPendingInput,
    CancelZipCompressConfirmation,
    ClearPendingKeySequence,
    ClearSelection,
    CloseCurrentTab,
    CommandPaletteState,
    ConfigEditorState,
    ConfirmDeleteTargets,
    ConfirmFilterInput,
    ConfirmZipCompress,
    CopyPathsToClipboard,
    CopyTargets,
    CutTargets,
    CycleConfigEditorValue,
    CycleGrepSearchField,
    DeleteConfirmationState,
    DismissAttributeDialog,
    DismissConfigEditor,
    DismissNameConflict,
    EnterCursorDirectory,
    ExitCurrentPath,
    GoBack,
    GoForward,
    GoToHomeDirectory,
    GoToParentDirectory,
    MoveCommandPaletteCursor,
    MoveConfigEditorCursor,
    MoveCursor,
    MoveCursorAndSelectRange,
    MovePendingInputCursor,
    NameConflictState,
    NotificationState,
    OpenFindResultInEditor,
    OpenGrepResultInEditor,
    OpenNewTab,
    OpenPathInEditor,
    OpenPathWithDefaultApp,
    PasteClipboard,
    PendingInputState,
    PendingKeySequenceState,
    ReloadDirectory,
    RemoveBookmark,
    ResolvePasteConflict,
    SaveConfigEditor,
    SelectAllVisibleEntries,
    SendSplitTerminalInput,
    SetCommandPaletteQuery,
    SetFilterQuery,
    SetGrepSearchField,
    SetNotification,
    SetPendingInputValue,
    SetPendingKeySequence,
    SetSort,
    ShowAttributes,
    SubmitCommandPalette,
    SubmitPendingInput,
    ToggleHiddenFiles,
    ToggleSelectionAndAdvance,
    ToggleSplitTerminal,
    UndoLastOperation,
    ZipCompressConfirmationState,
    build_initial_app_state,
    dispatch_key_input,
    iter_bound_keys,
)


def _focused_split_terminal_state():
    state = build_initial_app_state()
    return replace(
        state,
        split_terminal=replace(
            state.split_terminal,
            visible=True,
            status="running",
            focus_target="terminal",
        ),
    )


def _reduce_go_to_path_state(
    *,
    query: str,
    candidates: tuple[str, ...],
    current_path: str,
    cursor_index: int = 0,
):
    state = replace(
        build_initial_app_state(),
        current_path=current_path,
    )
    state = replace(
        state,
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="go_to_path",
            query=query,
            cursor_index=cursor_index,
            go_to_path_candidates=candidates,
        ),
    )
    return state


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

    assert actions == (SetNotification(None), ExitCurrentPath())


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


def test_filter_q_updates_query_instead_of_exiting() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        ui_mode="FILTER",
    )

    actions = dispatch_key_input(state, key="q", character="q")

    assert actions == (SetNotification(None), SetFilterQuery("q", active=True))


def test_filter_bound_space_without_character_is_rejected() -> None:
    state = replace(build_initial_app_state(), ui_mode="FILTER")

    actions = dispatch_key_input(state, key="space")

    assert actions == (
        SetNotification(
            NotificationState(
                level="warning",
                message="This key is unavailable while editing the filter",
            )
        ),
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


def test_browsing_lowercase_t_toggles_split_terminal() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="t")

    assert actions == (SetNotification(None), ToggleSplitTerminal())


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


def test_palette_enter_submits_selected_command() -> None:
    state = replace(build_initial_app_state(), ui_mode="PALETTE")

    actions = dispatch_key_input(state, key="enter")

    assert actions == (SetNotification(None), SubmitCommandPalette())


def test_palette_escape_closes_command_palette() -> None:
    state = replace(build_initial_app_state(), ui_mode="PALETTE")

    actions = dispatch_key_input(state, key="escape")

    assert actions == (SetNotification(None), CancelCommandPalette())


def test_palette_down_moves_cursor() -> None:
    state = replace(build_initial_app_state(), ui_mode="PALETTE")

    actions = dispatch_key_input(state, key="down")

    assert actions == (SetNotification(None), MoveCommandPaletteCursor(delta=1))


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


def test_palette_ctrl_e_opens_grep_result_in_editor() -> None:
    from zivo.state.models import CommandPaletteState
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="grep_search",
            query="test",
        ),
    )

    actions = dispatch_key_input(state, key="ctrl+e")

    assert actions == (SetNotification(None), OpenGrepResultInEditor())


def test_palette_ctrl_e_opens_find_result_in_editor() -> None:
    from zivo.state.models import CommandPaletteState
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="file_search",
            query="test",
        ),
    )

    actions = dispatch_key_input(state, key="ctrl+e")

    assert actions == (SetNotification(None), OpenFindResultInEditor())


def test_palette_e_key_does_not_open_editor_for_other_sources() -> None:
    from zivo.state.models import CommandPaletteState
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="commands",
            query="test",
        ),
    )

    actions = dispatch_key_input(state, key="e", character="e")

    # e キーは commands では OpenFindResultInEditor を生成せず、文字として扱われる
    assert actions == (SetNotification(None), SetCommandPaletteQuery("teste"))


def test_palette_ctrl_n_moves_cursor_down_in_grep_palette() -> None:
    from zivo.state.models import CommandPaletteState
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="grep_search",
            query="test",
        ),
    )

    actions = dispatch_key_input(state, key="ctrl+n")

    assert actions == (SetNotification(None), MoveCommandPaletteCursor(delta=1))


def test_palette_ctrl_p_moves_cursor_up_in_grep_palette() -> None:
    from zivo.state.models import CommandPaletteState
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="grep_search",
            query="test",
        ),
    )

    actions = dispatch_key_input(state, key="ctrl+p")

    assert actions == (SetNotification(None), MoveCommandPaletteCursor(delta=-1))


def test_palette_ctrl_n_moves_cursor_down_in_file_search_palette() -> None:
    from zivo.state.models import CommandPaletteState
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="file_search",
            query="test",
        ),
    )

    actions = dispatch_key_input(state, key="ctrl+n")

    assert actions == (SetNotification(None), MoveCommandPaletteCursor(delta=1))


def test_palette_ctrl_p_moves_cursor_up_in_file_search_palette() -> None:
    from zivo.state.models import CommandPaletteState
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="file_search",
            query="test",
        ),
    )

    actions = dispatch_key_input(state, key="ctrl+p")

    assert actions == (SetNotification(None), MoveCommandPaletteCursor(delta=-1))


def test_palette_printable_key_updates_query() -> None:
    state = replace(build_initial_app_state(), ui_mode="PALETTE")

    actions = dispatch_key_input(state, key="f", character="f")

    assert actions == (SetNotification(None), SetCommandPaletteQuery("f"))


def test_palette_space_updates_query() -> None:
    state = replace(build_initial_app_state(), ui_mode="PALETTE")

    actions = dispatch_key_input(state, key="space", character=" ")

    assert actions == (SetNotification(None), SetCommandPaletteQuery(" "))


def test_palette_bound_space_without_character_updates_query() -> None:
    state = replace(build_initial_app_state(), ui_mode="PALETTE")

    actions = dispatch_key_input(state, key="space")

    assert actions == (SetNotification(None), SetCommandPaletteQuery(" "))


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

    assert actions == (SetNotification(None), SetCommandPaletteQuery("docs/"))


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


def test_palette_pageup_moves_cursor_by_page() -> None:
    state = replace(build_initial_app_state(), ui_mode="PALETTE")

    actions = dispatch_key_input(state, key="pageup")

    assert actions == (SetNotification(None), MoveCommandPaletteCursor(delta=-14))


def test_palette_pagedown_moves_cursor_by_page() -> None:
    state = replace(build_initial_app_state(), ui_mode="PALETTE")

    actions = dispatch_key_input(state, key="pagedown")

    assert actions == (SetNotification(None), MoveCommandPaletteCursor(delta=14))


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


def test_palette_unbound_key_shows_guidance() -> None:
    state = replace(build_initial_app_state(), ui_mode="PALETTE")

    actions = dispatch_key_input(state, key="delete")

    assert actions == (
        SetNotification(
            NotificationState(
                level="warning",
                message="Use arrows, type to filter, Enter to run, or Esc to cancel",
            )
        ),
    )


def test_split_terminal_focus_sends_printable_input() -> None:
    state = _focused_split_terminal_state()

    actions = dispatch_key_input(state, key="a", character="a")

    assert actions == (SetNotification(None), SendSplitTerminalInput("a"))


def test_split_terminal_focus_sends_bound_space_without_character() -> None:
    state = _focused_split_terminal_state()

    actions = dispatch_key_input(state, key="space")

    assert actions == (SetNotification(None), SendSplitTerminalInput(" "))


def test_split_terminal_focus_sends_delete_sequence() -> None:
    state = _focused_split_terminal_state()

    actions = dispatch_key_input(state, key="delete")

    assert actions == (SetNotification(None), SendSplitTerminalInput("\x1b[3~"))


def test_split_terminal_focus_sends_navigation_sequences() -> None:
    state = _focused_split_terminal_state()

    assert dispatch_key_input(state, key="home") == (
        SetNotification(None),
        SendSplitTerminalInput("\x1b[H"),
    )
    assert dispatch_key_input(state, key="end") == (
        SetNotification(None),
        SendSplitTerminalInput("\x1b[F"),
    )
    assert dispatch_key_input(state, key="pageup") == (
        SetNotification(None),
        SendSplitTerminalInput("\x1b[5~"),
    )
    assert dispatch_key_input(state, key="pagedown") == (
        SetNotification(None),
        SendSplitTerminalInput("\x1b[6~"),
    )

def test_split_terminal_focus_sends_tab() -> None:
    state = _focused_split_terminal_state()

    actions = dispatch_key_input(state, key="tab")

    assert actions == (SetNotification(None), SendSplitTerminalInput("\t"))


def test_split_terminal_focus_takes_priority_over_browsing_navigation() -> None:
    state = _focused_split_terminal_state()

    actions = dispatch_key_input(state, key="left")

    assert actions == (SetNotification(None), SendSplitTerminalInput("\x1b[D"))


def test_split_terminal_focus_sends_ctrl_shortcuts_except_ctrl_v() -> None:
    state = _focused_split_terminal_state()

    assert dispatch_key_input(state, key="ctrl+d") == (
        SetNotification(None),
        SendSplitTerminalInput("\x04"),
    )
    assert dispatch_key_input(state, key="ctrl+t") == (
        SetNotification(None),
        SendSplitTerminalInput("\x14"),
    )
    assert dispatch_key_input(state, key="ctrl+l") == (
        SetNotification(None),
        SendSplitTerminalInput("\x0c"),
    )


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


def test_filter_character_dispatches_query_update() -> None:
    state = build_initial_app_state()
    state = replace(state, ui_mode="FILTER")

    actions = dispatch_key_input(state, key="r", character="r")

    assert actions == (SetNotification(None), SetFilterQuery("r", active=True))


def test_filter_backspace_updates_query() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        ui_mode="FILTER",
        filter=replace(state.filter, query="rea", active=True),
    )

    actions = dispatch_key_input(state, key="backspace")

    assert actions == (SetNotification(None), SetFilterQuery("re", active=True))


def test_filter_space_is_unavailable() -> None:
    state = build_initial_app_state()
    state = replace(state, ui_mode="FILTER")

    actions = dispatch_key_input(state, key="space")

    assert actions == (
        SetNotification(
            NotificationState(
                level="warning",
                message="This key is unavailable while editing the filter",
            )
        ),
    )


def test_filter_enter_confirms_filter() -> None:
    state = build_initial_app_state()
    state = replace(state, ui_mode="FILTER")

    actions = dispatch_key_input(state, key="enter")

    assert actions == (SetNotification(None), ConfirmFilterInput())


def test_filter_down_confirms_filter() -> None:
    state = build_initial_app_state()
    state = replace(state, ui_mode="FILTER")

    actions = dispatch_key_input(state, key="down")

    assert actions == (SetNotification(None), ConfirmFilterInput())


def test_filter_escape_cancels_filter() -> None:
    state = build_initial_app_state()
    state = replace(state, ui_mode="FILTER")

    actions = dispatch_key_input(state, key="escape")

    assert actions == (SetNotification(None), CancelFilterInput())


def test_confirm_escape_returns_to_browsing() -> None:
    state = build_initial_app_state()
    state = replace(state, ui_mode="CONFIRM")

    actions = dispatch_key_input(state, key="escape")

    assert actions == (SetNotification(None), CancelPasteConflict())


def test_name_conflict_confirm_enter_returns_to_input() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        name_conflict=NameConflictState(kind="rename", name="docs"),
    )

    actions = dispatch_key_input(state, key="enter")

    assert actions == (SetNotification(None), DismissNameConflict())


def test_name_conflict_confirm_escape_returns_to_input() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        name_conflict=NameConflictState(kind="create_file", name="docs"),
    )

    actions = dispatch_key_input(state, key="escape")

    assert actions == (SetNotification(None), DismissNameConflict())


def test_detail_enter_closes_attribute_dialog() -> None:
    state = replace(build_initial_app_state(), ui_mode="DETAIL")

    actions = dispatch_key_input(state, key="enter")

    assert actions == (SetNotification(None), DismissAttributeDialog())


def test_config_down_moves_cursor() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
        ),
    )

    actions = dispatch_key_input(state, key="down")

    assert actions == (SetNotification(None), MoveConfigEditorCursor(delta=1))


def test_config_ctrl_n_moves_cursor() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
        ),
    )

    actions = dispatch_key_input(state, key="ctrl+n")

    assert actions == (SetNotification(None), MoveConfigEditorCursor(delta=1))


def test_config_ctrl_p_moves_cursor() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
        ),
    )

    actions = dispatch_key_input(state, key="ctrl+p")

    assert actions == (SetNotification(None), MoveConfigEditorCursor(delta=-1))


def test_config_enter_cycles_selected_value() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
        ),
    )

    actions = dispatch_key_input(state, key="enter")

    assert actions == (SetNotification(None), CycleConfigEditorValue(delta=1))


def test_config_s_saves_editor() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
        ),
    )

    actions = dispatch_key_input(state, key="s", character="s")

    assert actions == (SetNotification(None), SaveConfigEditor())


def test_config_e_opens_config_file_in_editor() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
        ),
    )

    actions = dispatch_key_input(state, key="e", character="e")

    assert actions == (SetNotification(None), OpenPathInEditor("/tmp/zivo/config.toml"))


def test_config_escape_closes_editor() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
        ),
    )

    actions = dispatch_key_input(state, key="escape")

    assert actions == (SetNotification(None), DismissConfigEditor())


def test_config_unbound_key_shows_guidance() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
        ),
    )

    actions = dispatch_key_input(state, key="x", character="x")

    assert actions == (
        SetNotification(
            NotificationState(
                level="warning",
                message=(
                    "Use ↑↓ or Ctrl+n/p to choose, ←→ or Enter to change, "
                    "s to save, e to edit the file, r to reset help, or Esc to close"
                ),
            )
        ),
    )


def test_confirm_o_selects_overwrite_resolution() -> None:
    state = replace(build_initial_app_state(), ui_mode="CONFIRM")

    actions = dispatch_key_input(state, key="o", character="o")

    assert actions == (SetNotification(None), ResolvePasteConflict("overwrite"))


def test_delete_confirm_enter_dispatches_confirmation() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        delete_confirmation=DeleteConfirmationState(
            paths=(
                "/home/tadashi/develop/zivo/docs",
                "/home/tadashi/develop/zivo/src",
            )
        ),
    )

    actions = dispatch_key_input(state, key="enter")

    assert actions == (SetNotification(None), ConfirmDeleteTargets())


def test_delete_confirm_escape_cancels_confirmation() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        delete_confirmation=DeleteConfirmationState(
            paths=("/home/tadashi/develop/zivo/docs",),
        ),
    )

    actions = dispatch_key_input(state, key="escape")

    assert actions == (SetNotification(None), CancelDeleteConfirmation())


def test_zip_compress_confirm_enter_dispatches_confirmation() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        zip_compress_confirmation=ZipCompressConfirmationState(
            request=CreateZipArchiveRequest(
                source_paths=("/home/tadashi/develop/zivo/docs",),
                destination_path="/home/tadashi/develop/zivo/docs.zip",
                root_dir="/home/tadashi/develop/zivo",
            ),
            total_entries=3,
        ),
    )

    actions = dispatch_key_input(state, key="enter")

    assert actions == (SetNotification(None), ConfirmZipCompress())


def test_zip_compress_confirm_escape_cancels_confirmation() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        zip_compress_confirmation=ZipCompressConfirmationState(
            request=CreateZipArchiveRequest(
                source_paths=("/home/tadashi/develop/zivo/docs",),
                destination_path="/home/tadashi/develop/zivo/docs.zip",
                root_dir="/home/tadashi/develop/zivo",
            ),
            total_entries=3,
        ),
    )

    actions = dispatch_key_input(state, key="escape")

    assert actions == (SetNotification(None), CancelZipCompressConfirmation())


def test_rename_character_dispatches_input_update() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        ui_mode="RENAME",
        pending_input=PendingInputState(prompt="Rename: ", value="doc", cursor_pos=3),
    )

    actions = dispatch_key_input(state, key="s", character="s")

    assert actions == (SetNotification(None), SetPendingInputValue("docs", cursor_pos=4))


def test_create_space_dispatches_input_update() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        ui_mode="CREATE",
        pending_input=PendingInputState(
            prompt="New file: ", value="new", cursor_pos=3, create_kind="file"
        ),
    )

    actions = dispatch_key_input(state, key="space", character=" ")

    assert actions == (SetNotification(None), SetPendingInputValue("new ", cursor_pos=4))


def test_zip_enter_dispatches_submit_pending_input() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="ZIP",
        pending_input=PendingInputState(
            prompt="Compress to: ",
            value="/tmp/output.zip",
            zip_source_paths=("/home/tadashi/develop/zivo/docs",),
        ),
    )

    actions = dispatch_key_input(state, key="enter")

    assert actions == (SetNotification(None), SubmitPendingInput())


def test_zip_printable_character_dispatches_input_update() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="ZIP",
        pending_input=PendingInputState(
            prompt="Compress to: ",
            value="/tmp/output",
            cursor_pos=11,
            zip_source_paths=("/home/tadashi/develop/zivo/docs",),
        ),
    )

    actions = dispatch_key_input(state, key="z", character="z")

    assert actions == (SetNotification(None), SetPendingInputValue("/tmp/outputz", cursor_pos=12))


def test_pending_input_backspace_updates_value() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        ui_mode="RENAME",
        pending_input=PendingInputState(prompt="Rename: ", value="docs", cursor_pos=4),
    )

    actions = dispatch_key_input(state, key="backspace")

    assert actions == (SetNotification(None), SetPendingInputValue("doc", cursor_pos=3))


def test_pending_input_enter_submits() -> None:
    state = replace(build_initial_app_state(), ui_mode="RENAME")

    actions = dispatch_key_input(state, key="enter")

    assert actions == (SetNotification(None), SubmitPendingInput())


def test_pending_input_escape_cancels() -> None:
    state = replace(build_initial_app_state(), ui_mode="RENAME")

    actions = dispatch_key_input(state, key="escape")

    assert actions == (SetNotification(None), CancelPendingInput())


def test_pending_input_unbound_key_shows_guidance() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        ui_mode="RENAME",
        pending_input=PendingInputState(prompt="Rename: ", value="docs", cursor_pos=4),
    )

    actions = dispatch_key_input(state, key="left")

    assert actions == (SetNotification(None), MovePendingInputCursor(delta=-1))


def test_busy_key_shows_warning_message() -> None:
    state = build_initial_app_state()
    state = replace(state, ui_mode="BUSY")

    actions = dispatch_key_input(state, key="x", character="x")

    assert actions == (
        SetNotification(
            NotificationState(level="warning", message="Input ignored while processing")
        ),
    )


def test_palette_home_jumps_to_start() -> None:
    state = replace(build_initial_app_state(), ui_mode="PALETTE")

    actions = dispatch_key_input(state, key="home")

    assert actions == (SetNotification(None), MoveCommandPaletteCursor(delta=-999999))


def test_palette_end_jumps_to_end() -> None:
    state = replace(build_initial_app_state(), ui_mode="PALETTE")

    actions = dispatch_key_input(state, key="end")

    assert actions == (SetNotification(None), MoveCommandPaletteCursor(delta=999999))


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


def test_browsing_open_bracket_dispatches_go_back() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="[")

    assert actions == (SetNotification(None), GoBack())


def test_browsing_close_bracket_dispatches_go_forward() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="]")

    assert actions == (SetNotification(None), GoForward())


# ---------------------------------------------------------------------------
# Split terminal escape key and extended key tests (Issue #573)
# ---------------------------------------------------------------------------


def test_split_terminal_escape_sends_esc_byte() -> None:
    state = _focused_split_terminal_state()

    actions = dispatch_key_input(state, key="escape")

    assert actions == (SetNotification(None), SendSplitTerminalInput("\x1b"))


def test_split_terminal_ctrl_q_closes_terminal() -> None:
    state = _focused_split_terminal_state()

    actions = dispatch_key_input(state, key="ctrl+q")

    assert actions == (SetNotification(None), ToggleSplitTerminal())


def test_split_terminal_function_keys_send_sequences() -> None:
    state = _focused_split_terminal_state()

    assert dispatch_key_input(state, key="f1") == (
        SetNotification(None),
        SendSplitTerminalInput("\x1bOP"),
    )
    assert dispatch_key_input(state, key="f5") == (
        SetNotification(None),
        SendSplitTerminalInput("\x1b[15~"),
    )
    assert dispatch_key_input(state, key="f12") == (
        SetNotification(None),
        SendSplitTerminalInput("\x1b[24~"),
    )


def test_split_terminal_insert_sends_sequence() -> None:
    state = _focused_split_terminal_state()

    actions = dispatch_key_input(state, key="insert")

    assert actions == (SetNotification(None), SendSplitTerminalInput("\x1b[2~"))


def test_split_terminal_modified_arrows_send_sequences() -> None:
    state = _focused_split_terminal_state()

    assert dispatch_key_input(state, key="shift+up") == (
        SetNotification(None),
        SendSplitTerminalInput("\x1b[1;2A"),
    )
    assert dispatch_key_input(state, key="ctrl+left") == (
        SetNotification(None),
        SendSplitTerminalInput("\x1b[1;5D"),
    )
    assert dispatch_key_input(state, key="ctrl+shift+right") == (
        SetNotification(None),
        SendSplitTerminalInput("\x1b[1;6C"),
    )


def test_split_terminal_modified_navigation_sends_sequences() -> None:
    state = _focused_split_terminal_state()

    assert dispatch_key_input(state, key="ctrl+home") == (
        SetNotification(None),
        SendSplitTerminalInput("\x1b[1;5H"),
    )
    assert dispatch_key_input(state, key="shift+end") == (
        SetNotification(None),
        SendSplitTerminalInput("\x1b[1;2F"),
    )
    assert dispatch_key_input(state, key="ctrl+pagedown") == (
        SetNotification(None),
        SendSplitTerminalInput("\x1b[6;5~"),
    )


def test_split_terminal_shift_delete_sends_sequence() -> None:
    state = _focused_split_terminal_state()

    actions = dispatch_key_input(state, key="shift+delete")

    assert actions == (SetNotification(None), SendSplitTerminalInput("\x1b[3;2~"))


def test_split_terminal_ctrl_q_is_not_sent_as_control_character() -> None:
    """Ctrl+Q should close terminal, not send the XON byte (\\x11)."""
    state = _focused_split_terminal_state()

    actions = dispatch_key_input(state, key="ctrl+q")

    assert actions == (SetNotification(None), ToggleSplitTerminal())


def test_split_terminal_iter_bound_keys_includes_new_keys() -> None:
    keys = iter_bound_keys()

    assert "ctrl+q" in keys
    assert "f1" in keys
    assert "f12" in keys
    assert "insert" in keys
    assert "ctrl+up" in keys
    assert "shift+left" in keys
    assert "ctrl+shift+right" in keys
