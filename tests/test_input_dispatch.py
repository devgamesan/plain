from dataclasses import replace

from plain.state import (
    BeginFilterInput,
    CancelFilterInput,
    ClearSelection,
    ConfirmFilterInput,
    EnterCursorDirectory,
    GoToParentDirectory,
    MoveCursor,
    NotificationState,
    ReloadDirectory,
    SetFilterQuery,
    SetFilterRecursive,
    SetNotification,
    SetUiMode,
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


def test_browsing_ctrl_f_enters_filter_mode() -> None:
    state = build_initial_app_state()

    actions = dispatch_key_input(state, key="ctrl+f")

    assert actions == (SetNotification(None), BeginFilterInput())


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

    assert actions == (SetNotification(None), SetUiMode("BROWSING"))


def test_busy_key_shows_warning_message() -> None:
    state = build_initial_app_state()
    state = replace(state, ui_mode="BUSY")

    actions = dispatch_key_input(state, key="x", character="x")

    assert actions == (
        SetNotification(
            NotificationState(level="warning", message="Input ignored while processing")
        ),
    )
