from dataclasses import replace

from plain.state import (
    NotificationState,
    PaneState,
    SetCursorPath,
    SetFilterQuery,
    SetFilterRecursive,
    SetNotification,
    SetSort,
    ToggleSelection,
    build_initial_app_state,
    reduce_app_state,
    select_child_entries,
    select_current_entries,
    select_shell_data,
    select_status_bar_state,
    select_target_paths,
)


def _reduce_state(state, action):
    return reduce_app_state(state, action).state


def test_select_current_entries_applies_filter_and_sort() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, SetFilterQuery("t"))
    state = _reduce_state(
        state,
        SetSort(field="name", descending=True, directories_first=False),
    )

    entries = select_current_entries(state)

    assert [entry.name for entry in entries] == ["tests", "pyproject.toml"]


def test_select_status_bar_counts_selected_absolute_paths() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, ToggleSelection("/home/tadashi/develop/plain/README.md"))
    state = _reduce_state(state, ToggleSelection("/home/tadashi/develop/plain/tests"))

    status = select_status_bar_state(state)

    assert status.selected_count == 2
    assert status.item_count == 5


def test_select_target_paths_prefers_selection_in_entry_order() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, ToggleSelection("/home/tadashi/develop/plain/README.md"))
    state = _reduce_state(state, ToggleSelection("/home/tadashi/develop/plain/docs"))

    assert select_target_paths(state) == (
        "/home/tadashi/develop/plain/docs",
        "/home/tadashi/develop/plain/README.md",
    )


def test_select_target_paths_falls_back_to_cursor() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, SetCursorPath("/home/tadashi/develop/plain/tests"))

    assert select_target_paths(state) == ("/home/tadashi/develop/plain/tests",)


def test_select_target_paths_returns_empty_tuple_for_empty_directory() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        current_pane=PaneState(directory_path=state.current_path, entries=(), cursor_path=None),
    )

    assert select_target_paths(state) == ()


def test_select_current_entries_marks_selected_rows() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, ToggleSelection("/home/tadashi/develop/plain/README.md"))

    entries = select_current_entries(state)

    assert entries[0].selected is False
    assert entries[4].name == "README.md"
    assert entries[4].selected is True
    assert entries[4].selection_marker == "*"


def test_select_child_entries_is_empty_when_cursor_is_file() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, SetCursorPath("/home/tadashi/develop/plain/README.md"))

    assert select_child_entries(state) == ()


def test_select_shell_data_exposes_visible_cursor_index() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, SetCursorPath("/home/tadashi/develop/plain/tests"))

    shell = select_shell_data(state)

    assert shell.current_path == "/home/tadashi/develop/plain"
    assert shell.current_cursor_index == 2


def test_select_status_bar_keeps_summary_format() -> None:
    state = build_initial_app_state()

    status = select_status_bar_state(state)

    assert (
        f"{status.item_count} items | {status.selected_count} selected | "
        f"sort: {status.sort_label} | filter: {status.filter_label}"
    ) == "5 items | 0 selected | sort: name asc | filter: none"


def test_recursive_filter_label_is_reflected_in_status_bar() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, SetFilterQuery("md"))
    state = _reduce_state(state, SetFilterRecursive(True))

    status = select_status_bar_state(state)

    assert status.filter_label == "md (recursive)"


def test_select_status_bar_exposes_notification_level() -> None:
    state = build_initial_app_state()
    state = _reduce_state(
        state,
        SetNotification(NotificationState(level="error", message="load failed")),
    )

    status = select_status_bar_state(state)

    assert status.message == "load failed"
    assert status.message_level == "error"
