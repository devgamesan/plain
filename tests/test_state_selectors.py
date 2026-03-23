from dataclasses import replace

from plain.models import PasteConflict, PasteRequest
from plain.state import (
    BeginCreateInput,
    CutTargets,
    DeleteConfirmationState,
    DirectoryEntryState,
    NotificationState,
    PaneState,
    PasteConflictState,
    PendingInputState,
    SetCursorPath,
    SetFilterQuery,
    SetFilterRecursive,
    SetNotification,
    SetSort,
    ToggleSelection,
    build_initial_app_state,
    reduce_app_state,
    select_child_entries,
    select_conflict_dialog_state,
    select_current_entries,
    select_help_bar_state,
    select_input_bar_state,
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


def test_select_current_entries_uses_recursive_results_when_enabled() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        filter=replace(state.filter, query="md", active=True, recursive=True),
        recursive_entries=(
            DirectoryEntryState(
                "/home/tadashi/develop/plain/docs/spec_mvp.md",
                "spec_mvp.md",
                "file",
            ),
            DirectoryEntryState("/home/tadashi/develop/plain/docs/notes.md", "notes.md", "file"),
        ),
        current_pane=replace(
            state.current_pane,
            cursor_path="/home/tadashi/develop/plain/docs/spec_mvp.md",
        ),
    )

    entries = select_current_entries(state)

    assert [entry.name for entry in entries] == ["notes.md", "spec_mvp.md"]


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


def test_select_target_paths_prefers_recursive_selection_in_visible_order() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        filter=replace(state.filter, query="md", active=True, recursive=True),
        recursive_entries=(
            DirectoryEntryState(
                "/home/tadashi/develop/plain/docs/spec_mvp.md",
                "spec_mvp.md",
                "file",
            ),
            DirectoryEntryState("/home/tadashi/develop/plain/README.md", "README.md", "file"),
        ),
        current_pane=replace(
            state.current_pane,
            selected_paths=frozenset(
                {
                    "/home/tadashi/develop/plain/README.md",
                    "/home/tadashi/develop/plain/docs/spec_mvp.md",
                }
            ),
        ),
    )

    assert select_target_paths(state) == (
        "/home/tadashi/develop/plain/README.md",
        "/home/tadashi/develop/plain/docs/spec_mvp.md",
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


def test_select_current_entries_marks_cut_rows() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, CutTargets(("/home/tadashi/develop/plain/docs",)))

    entries = select_current_entries(state)

    assert entries[0].name == "docs"
    assert entries[0].cut is True
    assert entries[1].cut is False


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


def test_select_help_bar_defaults_to_browsing_shortcuts() -> None:
    state = build_initial_app_state()

    help_state = select_help_bar_state(state)

    assert help_state.text == (
        "/ filter | Space select | y copy | x cut | p paste | "
        "F2 rename | ctrl+n file | ctrl+shift+n dir"
    )


def test_select_input_bar_state_for_create_mode() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCreateInput("file"))
    state = replace(
        state,
        pending_input=PendingInputState(prompt="New file: ", value="notes.txt", create_kind="file"),
    )

    input_bar = select_input_bar_state(state)

    assert input_bar is not None
    assert input_bar.mode_label == "NEW FILE"
    assert input_bar.prompt == "New file: "
    assert input_bar.value == "notes.txt"


def test_select_conflict_dialog_state_formats_first_conflict() -> None:
    conflict = PasteConflict(
        source_path="/home/tadashi/develop/plain/docs",
        destination_path="/home/tadashi/develop/plain/docs",
    )
    state = replace(
        build_initial_app_state(),
        paste_conflict=PasteConflictState(
            request=PasteRequest(
                mode="copy",
                source_paths=("/home/tadashi/develop/plain/docs",),
                destination_dir="/home/tadashi/develop/plain",
            ),
            conflicts=(conflict,),
            first_conflict=conflict,
        ),
    )

    dialog = select_conflict_dialog_state(state)

    assert dialog is not None
    assert dialog.title == "Paste Conflict"
    assert "o overwrite" in dialog.options


def test_select_conflict_dialog_state_formats_delete_confirmation() -> None:
    state = replace(
        build_initial_app_state(),
        delete_confirmation=DeleteConfirmationState(
            paths=(
                "/home/tadashi/develop/plain/docs",
                "/home/tadashi/develop/plain/src",
            )
        ),
    )

    dialog = select_conflict_dialog_state(state)

    assert dialog is not None
    assert dialog.title == "Delete Confirmation"
    assert dialog.options == ("enter confirm", "esc cancel")


def test_select_help_bar_for_delete_confirmation() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        delete_confirmation=DeleteConfirmationState(
            paths=("/home/tadashi/develop/plain/docs",),
        ),
    )

    help_state = select_help_bar_state(state)

    assert help_state.text == "enter confirm delete | esc cancel"
