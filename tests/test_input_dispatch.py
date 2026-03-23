from dataclasses import replace

from plain.state import (
    BeginCreateInput,
    BeginDeleteTargets,
    BeginFilterInput,
    BeginRenameInput,
    CancelDeleteConfirmation,
    CancelFilterInput,
    CancelPasteConflict,
    CancelPendingInput,
    ClearSelection,
    ConfirmDeleteTargets,
    ConfirmFilterInput,
    CopyTargets,
    CutTargets,
    DeleteConfirmationState,
    EnterCursorDirectory,
    GoToParentDirectory,
    MoveCursor,
    NotificationState,
    PasteClipboard,
    PendingInputState,
    ReloadDirectory,
    ResolvePasteConflict,
    SetFilterQuery,
    SetFilterRecursive,
    SetNotification,
    SetPendingInputValue,
    SubmitPendingInput,
    ToggleSelectionAndAdvance,
    build_initial_app_state,
    dispatch_key_input,
)


def test_browsing_down_dispatches_move_cursor() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="down")

    assert actions[0] == SetNotification(None)
    assert actions[1] == MoveCursor(
        delta=1,
        visible_paths=(
            "/home/tadashi/develop/plain/docs",
            "/home/tadashi/develop/plain/src",
            "/home/tadashi/develop/plain/tests",
            "/home/tadashi/develop/plain/pyproject.toml",
            "/home/tadashi/develop/plain/README.md",
        ),
    )


def test_browsing_space_toggles_selection_and_advances_cursor() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="space")

    assert actions[0] == SetNotification(None)
    assert actions[1] == ToggleSelectionAndAdvance(
        path="/home/tadashi/develop/plain/docs",
        visible_paths=(
            "/home/tadashi/develop/plain/docs",
            "/home/tadashi/develop/plain/src",
            "/home/tadashi/develop/plain/tests",
            "/home/tadashi/develop/plain/pyproject.toml",
            "/home/tadashi/develop/plain/README.md",
        ),
    )


def test_browsing_escape_clears_selection() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="escape")

    assert actions == (SetNotification(None), ClearSelection())


def test_browsing_slash_enters_filter_mode() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="/", character="/")

    assert actions == (SetNotification(None), BeginFilterInput())


def test_browsing_ctrl_f_is_unbound() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="ctrl+f")

    assert actions == ()


def test_browsing_y_dispatches_copy_targets() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="y", character="y")

    assert actions == (
        SetNotification(None),
        CopyTargets(("/home/tadashi/develop/plain/docs",)),
    )


def test_browsing_x_dispatches_cut_targets() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="x", character="x")

    assert actions == (
        SetNotification(None),
        CutTargets(("/home/tadashi/develop/plain/docs",)),
    )


def test_browsing_p_dispatches_paste_clipboard() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="p", character="p")

    assert actions == (SetNotification(None), PasteClipboard())


def test_browsing_right_enters_directory() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="right")

    assert actions == (SetNotification(None), EnterCursorDirectory())


def test_browsing_enter_on_file_shows_warning() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        current_pane=replace(
            state.current_pane,
            cursor_path="/home/tadashi/develop/plain/README.md",
        ),
    )

    actions = dispatch_key_input(state, key="enter")

    assert actions == (
        SetNotification(
            NotificationState(level="warning", message="Opening files is not implemented yet")
        ),
    )


def test_browsing_backspace_goes_to_parent_directory() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="backspace")

    assert actions == (SetNotification(None), GoToParentDirectory())


def test_browsing_ctrl_h_goes_to_parent_directory() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="ctrl+h")

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
        BeginRenameInput("/home/tadashi/develop/plain/docs"),
    )


def test_browsing_f2_warns_for_multiple_targets() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        current_pane=replace(
            state.current_pane,
            selected_paths=frozenset(
                {
                    "/home/tadashi/develop/plain/docs",
                    "/home/tadashi/develop/plain/src",
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


def test_browsing_ctrl_n_begins_file_create_mode() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="ctrl+n")

    assert actions == (SetNotification(None), BeginCreateInput("file"))


def test_browsing_ctrl_shift_n_begins_directory_create_mode() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="ctrl+shift+n")

    assert actions == (SetNotification(None), BeginCreateInput("dir"))


def test_browsing_delete_dispatches_delete_targets() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="delete")

    assert actions == (
        SetNotification(None),
        BeginDeleteTargets(("/home/tadashi/develop/plain/docs",)),
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
        filter=replace(state.filter, query="rea", recursive=False, active=True),
    )

    actions = dispatch_key_input(state, key="backspace")

    assert actions == (SetNotification(None), SetFilterQuery("re", active=True))


def test_filter_space_toggles_recursive_flag() -> None:
    state = build_initial_app_state()
    state = replace(state, ui_mode="FILTER")

    actions = dispatch_key_input(state, key="space")

    assert actions == (SetNotification(None), SetFilterRecursive(True))


def test_filter_enter_confirms_filter() -> None:
    state = build_initial_app_state()
    state = replace(state, ui_mode="FILTER")

    actions = dispatch_key_input(state, key="enter")

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
                "/home/tadashi/develop/plain/docs",
                "/home/tadashi/develop/plain/src",
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
            paths=("/home/tadashi/develop/plain/docs",),
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
