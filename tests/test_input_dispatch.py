from dataclasses import replace

from peneo.state import (
    BeginCommandPalette,
    BeginDeleteTargets,
    BeginFileSearch,
    BeginFilterInput,
    BeginGrepSearch,
    BeginRenameInput,
    CancelCommandPalette,
    CancelDeleteConfirmation,
    CancelFilterInput,
    CancelPasteConflict,
    CancelPendingInput,
    ClearSelection,
    ConfigEditorState,
    ConfirmDeleteTargets,
    ConfirmFilterInput,
    CopyTargets,
    CutTargets,
    CycleConfigEditorValue,
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
    JumpCursor,
    MoveCommandPaletteCursor,
    MoveConfigEditorCursor,
    MoveCursor,
    NameConflictState,
    NotificationState,
    OpenPathInEditor,
    OpenPathWithDefaultApp,
    PasteClipboard,
    PendingInputState,
    ReloadDirectory,
    ResolvePasteConflict,
    SaveConfigEditor,
    SendSplitTerminalInput,
    SetCommandPaletteQuery,
    SetFilterQuery,
    SetNotification,
    SetPendingInputValue,
    SetSort,
    SubmitCommandPalette,
    SubmitPendingInput,
    ToggleSelectionAndAdvance,
    ToggleSplitTerminal,
    build_initial_app_state,
    dispatch_key_input,
    iter_bound_keys,
)


def test_browsing_down_dispatches_move_cursor() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="down")

    assert actions[0] == SetNotification(None)
    assert actions[1] == MoveCursor(
        delta=1,
        visible_paths=(
            "/home/tadashi/develop/peneo/docs",
            "/home/tadashi/develop/peneo/src",
            "/home/tadashi/develop/peneo/tests",
            "/home/tadashi/develop/peneo/pyproject.toml",
            "/home/tadashi/develop/peneo/README.md",
        ),
    )


def test_iter_bound_keys_includes_printable_text_input_keys() -> None:
    keys = iter_bound_keys()

    assert "e" in keys
    assert "T" in keys
    assert "/" in keys
    assert ":" in keys
    assert "space" in keys
    assert "ctrl+g" in keys
    assert "enter" in keys


def test_browsing_j_dispatches_move_cursor() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="j", character="j")

    assert actions[0] == SetNotification(None)
    assert actions[1] == MoveCursor(
        delta=1,
        visible_paths=(
            "/home/tadashi/develop/peneo/docs",
            "/home/tadashi/develop/peneo/src",
            "/home/tadashi/develop/peneo/tests",
            "/home/tadashi/develop/peneo/pyproject.toml",
            "/home/tadashi/develop/peneo/README.md",
        ),
    )


def test_browsing_k_dispatches_move_cursor() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="k", character="k")

    assert actions[0] == SetNotification(None)
    assert actions[1] == MoveCursor(
        delta=-1,
        visible_paths=(
            "/home/tadashi/develop/peneo/docs",
            "/home/tadashi/develop/peneo/src",
            "/home/tadashi/develop/peneo/tests",
            "/home/tadashi/develop/peneo/pyproject.toml",
            "/home/tadashi/develop/peneo/README.md",
        ),
    )


def test_browsing_space_toggles_selection_and_advances_cursor() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="space")

    assert actions[0] == SetNotification(None)
    assert actions[1] == ToggleSelectionAndAdvance(
        path="/home/tadashi/develop/peneo/docs",
        visible_paths=(
            "/home/tadashi/develop/peneo/docs",
            "/home/tadashi/develop/peneo/src",
            "/home/tadashi/develop/peneo/tests",
            "/home/tadashi/develop/peneo/pyproject.toml",
            "/home/tadashi/develop/peneo/README.md",
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


def test_browsing_ctrl_f_begins_file_search() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="ctrl+f")

    assert len(actions) == 2
    assert isinstance(actions[1], BeginFileSearch)


def test_browsing_ctrl_g_begins_grep_search() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="ctrl+g")

    assert len(actions) == 2
    assert isinstance(actions[1], BeginGrepSearch)


def test_filter_q_updates_query_instead_of_exiting() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        ui_mode="FILTER",
    )

    actions = dispatch_key_input(state, key="q", character="q")

    assert actions == (SetNotification(None), SetFilterQuery("q", active=True))


def test_browsing_y_dispatches_copy_targets() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="y", character="y")

    assert actions == (
        SetNotification(None),
        CopyTargets(("/home/tadashi/develop/peneo/docs",)),
    )


def test_browsing_x_dispatches_cut_targets() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="x", character="x")

    assert actions == (
        SetNotification(None),
        CutTargets(("/home/tadashi/develop/peneo/docs",)),
    )


def test_browsing_p_dispatches_paste_clipboard() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="p", character="p")

    assert actions == (SetNotification(None), PasteClipboard())


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
            cursor_path="/home/tadashi/develop/peneo/README.md",
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
            cursor_path="/home/tadashi/develop/peneo/README.md",
        ),
    )

    actions = dispatch_key_input(state, key="enter")

    assert actions == (
        SetNotification(None),
        OpenPathWithDefaultApp("/home/tadashi/develop/peneo/README.md"),
    )


def test_browsing_e_on_file_dispatches_open_in_editor() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        current_pane=replace(
            state.current_pane,
            cursor_path="/home/tadashi/develop/peneo/README.md",
        ),
    )

    actions = dispatch_key_input(state, key="e", character="e")

    assert actions == (
        SetNotification(None),
        OpenPathInEditor("/home/tadashi/develop/peneo/README.md"),
    )


def test_browsing_e_on_directory_warns() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="e", character="e")

    assert actions == (
        SetNotification(
            NotificationState(level="warning", message="Editor launch requires a file")
        ),
    )


def test_browsing_backspace_goes_to_parent_directory() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="backspace")

    assert actions == (SetNotification(None), GoToParentDirectory())


def test_browsing_f5_reloads_current_directory() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="f5")

    assert actions == (SetNotification(None), ReloadDirectory())


def test_browsing_f2_begins_rename_for_single_target() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="f2")

    assert actions == (
        SetNotification(None),
        BeginRenameInput("/home/tadashi/develop/peneo/docs"),
    )


def test_browsing_f2_warns_for_multiple_targets() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        current_pane=replace(
            state.current_pane,
            selected_paths=frozenset(
                {
                    "/home/tadashi/develop/peneo/docs",
                    "/home/tadashi/develop/peneo/src",
                }
            ),
        ),
    )

    actions = dispatch_key_input(state, key="f2")

    assert actions == (
        SetNotification(
            NotificationState(level="warning", message="Rename requires a single target")
        ),
    )


def test_browsing_colon_opens_command_palette() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key=":", character=":")

    assert actions == (SetNotification(None), BeginCommandPalette())


def test_browsing_ctrl_t_toggles_split_terminal() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="ctrl+t")

    assert actions == (SetNotification(None), ToggleSplitTerminal())


def test_browsing_tab_is_unbound() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="tab")

    assert actions == ()


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


def test_palette_printable_key_updates_query() -> None:
    state = replace(build_initial_app_state(), ui_mode="PALETTE")

    actions = dispatch_key_input(state, key="f", character="f")

    assert actions == (SetNotification(None), SetCommandPaletteQuery("f"))


def test_palette_pageup_moves_cursor_by_page() -> None:
    state = replace(build_initial_app_state(), ui_mode="PALETTE")

    actions = dispatch_key_input(state, key="pageup")

    assert actions == (SetNotification(None), MoveCommandPaletteCursor(delta=-7))


def test_palette_pagedown_moves_cursor_by_page() -> None:
    state = replace(build_initial_app_state(), ui_mode="PALETTE")

    actions = dispatch_key_input(state, key="pagedown")

    assert actions == (SetNotification(None), MoveCommandPaletteCursor(delta=7))


def test_split_terminal_focus_sends_printable_input() -> None:
    state = replace(
        build_initial_app_state(),
        split_terminal=replace(
            build_initial_app_state().split_terminal,
            visible=True,
            status="running",
            focus_target="terminal",
        ),
    )

    actions = dispatch_key_input(state, key="a", character="a")

    assert actions == (SetNotification(None), SendSplitTerminalInput("a"))


def test_split_terminal_focus_sends_tab_for_completion() -> None:
    state = replace(
        build_initial_app_state(),
        split_terminal=replace(
            build_initial_app_state().split_terminal,
            visible=True,
            status="running",
            focus_target="terminal",
        ),
    )

    actions = dispatch_key_input(state, key="tab")

    assert actions == (SetNotification(None), SendSplitTerminalInput("\t"))


def test_split_terminal_focus_sends_delete_sequence() -> None:
    state = replace(
        build_initial_app_state(),
        split_terminal=replace(
            build_initial_app_state().split_terminal,
            visible=True,
            status="running",
            focus_target="terminal",
        ),
    )

    actions = dispatch_key_input(state, key="delete")

    assert actions == (SetNotification(None), SendSplitTerminalInput("\x1b[3~"))


def test_split_terminal_focus_sends_navigation_sequences() -> None:
    state = replace(
        build_initial_app_state(),
        split_terminal=replace(
            build_initial_app_state().split_terminal,
            visible=True,
            status="running",
            focus_target="terminal",
        ),
    )

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


def test_split_terminal_focus_sends_ctrl_shortcuts_except_ctrl_t() -> None:
    state = replace(
        build_initial_app_state(),
        split_terminal=replace(
            build_initial_app_state().split_terminal,
            visible=True,
            status="running",
            focus_target="terminal",
        ),
    )

    assert dispatch_key_input(state, key="ctrl+d") == (
        SetNotification(None),
        SendSplitTerminalInput("\x04"),
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


def test_browsing_d_toggles_directories_first() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="d", character="d")

    assert actions == (
        SetNotification(None),
        SetSort(field="name", descending=False, directories_first=False),
    )


def test_browsing_delete_dispatches_delete_targets() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="delete")

    assert actions == (
        SetNotification(None),
        BeginDeleteTargets(("/home/tadashi/develop/peneo/docs",)),
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
        build_initial_app_state(config_path="/tmp/peneo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/peneo/config.toml",
            draft=build_initial_app_state().config,
        ),
    )

    actions = dispatch_key_input(state, key="down")

    assert actions == (SetNotification(None), MoveConfigEditorCursor(delta=1))


def test_config_enter_cycles_selected_value() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/peneo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/peneo/config.toml",
            draft=build_initial_app_state().config,
        ),
    )

    actions = dispatch_key_input(state, key="enter")

    assert actions == (SetNotification(None), CycleConfigEditorValue(delta=1))


def test_config_s_saves_editor() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/peneo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/peneo/config.toml",
            draft=build_initial_app_state().config,
        ),
    )

    actions = dispatch_key_input(state, key="s", character="s")

    assert actions == (SetNotification(None), SaveConfigEditor())


def test_config_e_opens_config_file_in_editor() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/peneo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/peneo/config.toml",
            draft=build_initial_app_state().config,
        ),
    )

    actions = dispatch_key_input(state, key="e", character="e")

    assert actions == (SetNotification(None), OpenPathInEditor("/tmp/peneo/config.toml"))


def test_config_escape_closes_editor() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/peneo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/peneo/config.toml",
            draft=build_initial_app_state().config,
        ),
    )

    actions = dispatch_key_input(state, key="escape")

    assert actions == (SetNotification(None), DismissConfigEditor())


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
                "/home/tadashi/develop/peneo/docs",
                "/home/tadashi/develop/peneo/src",
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
            paths=("/home/tadashi/develop/peneo/docs",),
        ),
    )

    actions = dispatch_key_input(state, key="escape")

    assert actions == (SetNotification(None), CancelDeleteConfirmation())


def test_rename_character_dispatches_input_update() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        ui_mode="RENAME",
        pending_input=PendingInputState(prompt="Rename: ", value="doc"),
    )

    actions = dispatch_key_input(state, key="s", character="s")

    assert actions == (SetNotification(None), SetPendingInputValue("docs"))


def test_create_space_dispatches_input_update() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        ui_mode="CREATE",
        pending_input=PendingInputState(prompt="New file: ", value="new", create_kind="file"),
    )

    actions = dispatch_key_input(state, key="space", character=" ")

    assert actions == (SetNotification(None), SetPendingInputValue("new "))


def test_pending_input_backspace_updates_value() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        ui_mode="RENAME",
        pending_input=PendingInputState(prompt="Rename: ", value="docs"),
    )

    actions = dispatch_key_input(state, key="backspace")

    assert actions == (SetNotification(None), SetPendingInputValue("doc"))


def test_pending_input_enter_submits() -> None:
    state = replace(build_initial_app_state(), ui_mode="RENAME")

    actions = dispatch_key_input(state, key="enter")

    assert actions == (SetNotification(None), SubmitPendingInput())


def test_pending_input_escape_cancels() -> None:
    state = replace(build_initial_app_state(), ui_mode="RENAME")

    actions = dispatch_key_input(state, key="escape")

    assert actions == (SetNotification(None), CancelPendingInput())


def test_busy_key_shows_warning_message() -> None:
    state = build_initial_app_state()
    state = replace(state, ui_mode="BUSY")

    actions = dispatch_key_input(state, key="x", character="x")

    assert actions == (
        SetNotification(
            NotificationState(level="warning", message="Input ignored while processing")
        ),
    )


def test_browsing_home_dispatches_jump_cursor_start() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="home")

    assert actions[0] == SetNotification(None)
    assert actions[1] == JumpCursor(
        position="start",
        visible_paths=(
            "/home/tadashi/develop/peneo/docs",
            "/home/tadashi/develop/peneo/src",
            "/home/tadashi/develop/peneo/tests",
            "/home/tadashi/develop/peneo/pyproject.toml",
            "/home/tadashi/develop/peneo/README.md",
        ),
    )


def test_browsing_end_dispatches_jump_cursor_end() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="end")

    assert actions[0] == SetNotification(None)
    assert actions[1] == JumpCursor(
        position="end",
        visible_paths=(
            "/home/tadashi/develop/peneo/docs",
            "/home/tadashi/develop/peneo/src",
            "/home/tadashi/develop/peneo/tests",
            "/home/tadashi/develop/peneo/pyproject.toml",
            "/home/tadashi/develop/peneo/README.md",
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


def test_browsing_alt_left_dispatches_go_back() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="alt+left")

    assert actions == (SetNotification(None), GoBack())


def test_browsing_alt_right_dispatches_go_forward() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="alt+right")

    assert actions == (SetNotification(None), GoForward())


def test_browsing_alt_home_dispatches_go_to_home_directory() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="alt+home")

    assert actions == (SetNotification(None), GoToHomeDirectory())
