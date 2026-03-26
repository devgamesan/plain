from dataclasses import replace

from plain.models import PasteConflict, PasteRequest
from plain.state import (
    BeginCommandPalette,
    BeginCreateInput,
    BeginFilterInput,
    ConfirmFilterInput,
    CutTargets,
    DeleteConfirmationState,
    DirectoryEntryState,
    NameConflictState,
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
    select_child_entries,
    select_command_palette_state,
    select_conflict_dialog_state,
    select_current_entries,
    select_current_summary_state,
    select_help_bar_state,
    select_input_bar_state,
    select_parent_entries,
    select_shell_data,
    select_status_bar_state,
    select_target_paths,
    select_visible_current_entry_states,
)
from tests.state_test_helpers import entry, pane, reduce_state


def _reduce_state(state, action):
    return reduce_state(state, action)


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


def test_select_current_entries_hides_hidden_by_default() -> None:
    state = replace(
        build_initial_app_state(),
        current_pane=PaneState(
            directory_path="/home/tadashi/develop/plain",
            entries=(
                DirectoryEntryState(
                    "/home/tadashi/develop/plain/.env",
                    ".env",
                    "file",
                    hidden=True,
                ),
                DirectoryEntryState("/home/tadashi/develop/plain/docs", "docs", "dir"),
            ),
            cursor_path="/home/tadashi/develop/plain/docs",
        ),
    )

    entries = select_current_entries(state)

    assert [entry.name for entry in entries] == ["docs"]


def test_select_visible_current_entries_sorts_by_modified_with_missing_values_last() -> None:
    state = replace(
        build_initial_app_state(),
        current_pane=pane(
            "/home/tadashi/develop/plain",
            (
                entry(
                    "/home/tadashi/develop/plain/alpha.txt",
                    modified_at=None,
                ),
                entry(
                    "/home/tadashi/develop/plain/beta.txt",
                    modified_at=build_initial_app_state().current_pane.entries[3].modified_at,
                ),
                entry(
                    "/home/tadashi/develop/plain/gamma.txt",
                    modified_at=build_initial_app_state().current_pane.entries[4].modified_at,
                ),
            ),
            cursor_path="/home/tadashi/develop/plain/alpha.txt",
        ),
        sort=replace(build_initial_app_state().sort, field="modified", descending=True),
    )

    entries = select_visible_current_entry_states(state)

    assert [entry.name for entry in entries] == ["alpha.txt", "beta.txt", "gamma.txt"]


def test_select_visible_current_entries_sorts_by_size_without_directories_first() -> None:
    state = replace(
        build_initial_app_state(),
        current_pane=pane(
            "/home/tadashi/develop/plain",
            (
                entry("/home/tadashi/develop/plain/docs", kind="dir"),
                entry("/home/tadashi/develop/plain/alpha.txt", size_bytes=500),
                entry("/home/tadashi/develop/plain/beta.txt", size_bytes=2_000),
            ),
            cursor_path="/home/tadashi/develop/plain/docs",
        ),
        sort=replace(
            build_initial_app_state().sort,
            field="size",
            descending=True,
            directories_first=False,
        ),
    )

    entries = select_visible_current_entry_states(state)

    assert [entry.name for entry in entries] == ["docs", "beta.txt", "alpha.txt"]


def test_select_parent_and_child_entries_hide_hidden_unless_enabled() -> None:
    state = replace(
        build_initial_app_state(),
        parent_pane=PaneState(
            directory_path="/tmp",
            entries=(
                DirectoryEntryState("/tmp/.cache", ".cache", "dir", hidden=True),
                DirectoryEntryState("/tmp/plain", "plain", "dir"),
            ),
            cursor_path="/tmp/plain",
        ),
        current_pane=PaneState(
            directory_path="/home/tadashi/develop/plain",
            entries=(DirectoryEntryState("/home/tadashi/develop/plain/docs", "docs", "dir"),),
            cursor_path="/home/tadashi/develop/plain/docs",
        ),
        child_pane=PaneState(
            directory_path="/home/tadashi/develop/plain/docs",
            entries=(
                DirectoryEntryState(
                    "/home/tadashi/develop/plain/docs/.draft.md",
                    ".draft.md",
                    "file",
                    hidden=True,
                ),
                DirectoryEntryState(
                    "/home/tadashi/develop/plain/docs/spec.md",
                    "spec.md",
                    "file",
                ),
            ),
        ),
    )

    assert [entry.name for entry in select_parent_entries(state)] == ["plain"]
    assert [entry.name for entry in select_child_entries(state)] == ["spec.md"]

    visible_state = replace(state, show_hidden=True)

    assert [entry.name for entry in select_parent_entries(visible_state)] == [".cache", "plain"]
    assert [entry.name for entry in select_child_entries(visible_state)] == [
        ".draft.md",
        "spec.md",
    ]


def test_select_current_summary_counts_selected_absolute_paths() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, ToggleSelection("/home/tadashi/develop/plain/README.md"))
    state = _reduce_state(state, ToggleSelection("/home/tadashi/develop/plain/tests"))

    summary = select_current_summary_state(state)

    assert summary.selected_count == 2
    assert summary.item_count == 5


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


def test_select_target_paths_ignores_hidden_selected_entries_when_hidden_files_are_off() -> None:
    hidden_path = "/home/tadashi/develop/plain/.env"
    visible_path = "/home/tadashi/develop/plain/docs"
    state = replace(
        build_initial_app_state(),
        current_pane=pane(
            "/home/tadashi/develop/plain",
            (
                entry(hidden_path, hidden=True),
                entry(visible_path, kind="dir"),
            ),
            cursor_path=visible_path,
            selected_paths=(hidden_path, visible_path),
        ),
    )

    assert select_target_paths(state) == (visible_path,)


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


def test_select_parent_and_child_entries_keep_fixed_name_sort() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        parent_pane=PaneState(
            directory_path="/tmp",
            entries=(
                DirectoryEntryState("/tmp/beta.txt", "beta.txt", "file"),
                DirectoryEntryState("/tmp/alpha", "alpha", "dir"),
                DirectoryEntryState("/tmp/gamma", "gamma", "dir"),
            ),
            cursor_path="/tmp/alpha",
        ),
        current_pane=PaneState(
            directory_path="/home/tadashi/develop/plain",
            entries=state.current_pane.entries,
            cursor_path="/home/tadashi/develop/plain/docs",
        ),
        child_pane=PaneState(
            directory_path="/home/tadashi/develop/plain/docs",
            entries=(
                DirectoryEntryState(
                    "/home/tadashi/develop/plain/docs/readme.txt",
                    "readme.txt",
                    "file",
                ),
                DirectoryEntryState(
                    "/home/tadashi/develop/plain/docs/archive",
                    "archive",
                    "dir",
                ),
            ),
        ),
        sort=replace(state.sort, field="modified", descending=True, directories_first=False),
    )
    state = _reduce_state(
        state,
        SetSort(field="modified", descending=True, directories_first=False),
    )

    parent_entries = select_parent_entries(state)
    child_entries = select_child_entries(state)

    assert [entry.name for entry in parent_entries] == ["alpha", "gamma", "beta.txt"]
    assert [entry.name for entry in child_entries] == ["archive", "readme.txt"]


def test_select_shell_data_exposes_visible_cursor_index() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, SetCursorPath("/home/tadashi/develop/plain/tests"))

    shell = select_shell_data(state)

    assert shell.current_path == "/home/tadashi/develop/plain"
    assert shell.current_cursor_index == 2


def test_select_shell_data_includes_selected_cut_and_contextual_models() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        ToggleSelection("/home/tadashi/develop/plain/README.md"),
    )
    state = _reduce_state(state, CutTargets(("/home/tadashi/develop/plain/docs",)))
    state = replace(
        state,
        filter=replace(state.filter, query="read", active=True),
        notification=NotificationState(level="info", message="Ready"),
    )

    shell = select_shell_data(state)

    assert [entry.name for entry in shell.current_entries] == ["README.md"]
    assert shell.current_entries[0].selected is True
    assert shell.parent_entries[0].cut is False
    assert shell.current_context_input is not None
    assert shell.current_context_input.value == "read"
    assert shell.current_summary.sort_label == "name asc dirs:on"
    assert shell.status.message == "Ready"


def test_select_current_summary_state_keeps_summary_format() -> None:
    state = build_initial_app_state()

    summary = select_current_summary_state(state)

    assert (
        f"{summary.item_count} items | {summary.selected_count} selected | "
        f"sort: {summary.sort_label}"
    ) == "5 items | 0 selected | sort: name asc dirs:on"


def test_recursive_filter_does_not_change_current_summary_format() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, SetFilterQuery("md"))
    state = _reduce_state(state, SetFilterRecursive(True))

    summary = select_current_summary_state(state)

    assert summary.sort_label == "name asc dirs:on"


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
        "/ filter | s sort | d dirs | Space select | y copy | x cut | p paste | "
        "F2 rename | : palette"
    )


def test_select_help_bar_for_busy_mode() -> None:
    state = replace(build_initial_app_state(), ui_mode="BUSY")

    help_state = select_help_bar_state(state)

    assert help_state.text == "processing..."


def test_select_command_palette_state_marks_selected_and_disabled_items() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())

    palette_state = select_command_palette_state(state)

    assert palette_state is not None
    assert [item.label for item in palette_state.items[:3]] == [
        "Create file",
        "Create directory",
        "Copy path",
    ]
    assert palette_state.items[0].selected is True
    assert palette_state.items[2].enabled is False
    assert any(item.label == "Open terminal here" and item.enabled for item in palette_state.items)


def test_select_command_palette_state_filters_query() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = replace(
        state,
        command_palette=replace(state.command_palette, query="dir"),
    )

    palette_state = select_command_palette_state(state)

    assert palette_state is not None
    assert [item.label for item in palette_state.items] == ["Create directory"]


def test_select_command_palette_state_uses_hidden_toggle_label_from_state() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = replace(
        state,
        command_palette=replace(state.command_palette, query="hidden"),
    )

    palette_state = select_command_palette_state(state)

    assert palette_state is not None
    assert [item.label for item in palette_state.items] == ["Show hidden files"]

    visible_state = replace(state, show_hidden=True)
    visible_palette_state = select_command_palette_state(visible_state)

    assert visible_palette_state is not None
    assert [item.label for item in visible_palette_state.items] == ["Hide hidden files"]


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
    assert input_bar.hint == "enter apply | esc cancel"


def test_select_input_bar_state_for_filter_mode() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFilterInput())
    state = _reduce_state(state, SetFilterQuery("spec"))
    state = _reduce_state(state, SetFilterRecursive(True))

    input_bar = select_input_bar_state(state)

    assert input_bar is not None
    assert input_bar.mode_label == "FILTER"
    assert input_bar.prompt == "Filter: "
    assert input_bar.value == "spec"
    assert input_bar.hint == "space recursive:on | enter apply | esc cancel"


def test_select_input_bar_state_keeps_active_filter_visible_after_confirm() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFilterInput())
    state = _reduce_state(state, SetFilterQuery("spec"))
    state = _reduce_state(state, ConfirmFilterInput())

    input_bar = select_input_bar_state(state)

    assert input_bar is not None
    assert input_bar.mode_label == "FILTER"
    assert input_bar.prompt == "Filter: "
    assert input_bar.value == "spec"
    assert input_bar.hint == "active"


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


def test_select_conflict_dialog_state_formats_rename_conflict() -> None:
    state = replace(
        build_initial_app_state(),
        name_conflict=NameConflictState(kind="rename", name="src"),
    )

    dialog = select_conflict_dialog_state(state)

    assert dialog is not None
    assert dialog.title == "Rename Conflict"
    assert dialog.options == ("enter return to input", "esc return to input")


def test_select_conflict_dialog_state_formats_create_directory_conflict() -> None:
    state = replace(
        build_initial_app_state(),
        name_conflict=NameConflictState(kind="create_dir", name="docs"),
    )

    dialog = select_conflict_dialog_state(state)

    assert dialog is not None
    assert dialog.title == "Create Directory Conflict"
    assert "creating the directory" in dialog.message


def test_select_help_bar_for_paste_conflict_uses_generic_guidance() -> None:
    conflict = PasteConflict(
        source_path="/home/tadashi/develop/plain/docs",
        destination_path="/home/tadashi/develop/plain/docs",
    )
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
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

    help_state = select_help_bar_state(state)

    assert help_state.text == "resolve conflict in dialog"


def test_select_help_bar_for_name_conflict() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        name_conflict=NameConflictState(kind="create_file", name="docs"),
    )

    help_state = select_help_bar_state(state)

    assert help_state.text == "enter return to input | esc return to input"


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
