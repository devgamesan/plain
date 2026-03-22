from plain.state import (
    NotificationState,
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
    select_status_bar_state,
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


def test_select_child_entries_is_empty_when_cursor_is_file() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, SetCursorPath("/home/tadashi/develop/plain/README.md"))

    assert select_child_entries(state) == ()


def test_select_status_bar_keeps_existing_format() -> None:
    state = build_initial_app_state()

    status = select_status_bar_state(state)

    assert (
        f"{status.path} | {status.item_count} items | {status.selected_count} selected | "
        f"sort: {status.sort_label} | filter: {status.filter_label}"
    ) == "/home/tadashi/develop/plain | 5 items | 0 selected | sort: name asc | filter: none"


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
