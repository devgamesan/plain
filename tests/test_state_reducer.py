from dataclasses import replace

from plain.models import (
    CreatePathRequest,
    FileMutationResult,
    PasteConflict,
    PasteRequest,
    PasteSummary,
    RenameRequest,
    TrashDeleteRequest,
)
from plain.state import (
    BeginCommandPalette,
    BeginCreateInput,
    BeginDeleteTargets,
    BeginFilterInput,
    BeginRenameInput,
    BrowserSnapshot,
    BrowserSnapshotFailed,
    BrowserSnapshotLoaded,
    CancelCommandPalette,
    CancelDeleteConfirmation,
    CancelFilterInput,
    CancelPasteConflict,
    CancelPendingInput,
    ChildPaneSnapshotFailed,
    ChildPaneSnapshotLoaded,
    ClearSelection,
    ClipboardPasteCompleted,
    ClipboardPasteNeedsResolution,
    ConfirmDeleteTargets,
    ConfirmFilterInput,
    CopyTargets,
    CutTargets,
    DeleteConfirmationState,
    DirectoryEntryState,
    EnterCursorDirectory,
    FileMutationCompleted,
    FileMutationFailed,
    GoToParentDirectory,
    LoadBrowserSnapshotEffect,
    LoadChildPaneSnapshotEffect,
    LoadRecursiveFilterEffect,
    MoveCommandPaletteCursor,
    MoveCursor,
    NotificationState,
    PaneState,
    PasteClipboard,
    PasteConflictState,
    PendingInputState,
    RecursiveFilterLoaded,
    ReloadDirectory,
    RequestBrowserSnapshot,
    ResolvePasteConflict,
    RunClipboardPasteEffect,
    RunFileMutationEffect,
    SetCommandPaletteQuery,
    SetCursorPath,
    SetFilterQuery,
    SetPendingInputValue,
    SetSort,
    SetUiMode,
    SubmitCommandPalette,
    SubmitPendingInput,
    ToggleHiddenFiles,
    ToggleSelection,
    ToggleSelectionAndAdvance,
    build_initial_app_state,
    reduce_app_state,
)


def _reduce_state(state, action):
    return reduce_app_state(state, action).state


def test_set_ui_mode_updates_only_mode() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(state, SetUiMode("FILTER"))

    assert next_state.ui_mode == "FILTER"
    assert next_state.current_pane == state.current_pane
    assert next_state.filter == state.filter


def test_toggle_selection_uses_absolute_paths() -> None:
    state = build_initial_app_state()
    path = "/home/tadashi/develop/plain/README.md"

    selected_state = _reduce_state(state, ToggleSelection(path))
    cleared_state = _reduce_state(selected_state, ToggleSelection(path))

    assert selected_state.current_pane.selected_paths == frozenset({path})
    assert cleared_state.current_pane.selected_paths == frozenset()


def test_clear_selection_empties_selection() -> None:
    state = build_initial_app_state()
    selected_state = _reduce_state(
        state,
        ToggleSelection("/home/tadashi/develop/plain/README.md"),
    )

    next_state = _reduce_state(selected_state, ClearSelection())

    assert next_state.current_pane.selected_paths == frozenset()


def test_set_filter_query_returns_new_state_without_mutating_input() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(state, SetFilterQuery("readme"))

    assert next_state.filter.query == "readme"
    assert next_state.filter.active is True
    assert state.filter.query == ""
    assert state.filter.active is False


def test_set_filter_query_queues_recursive_search_when_enabled() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        filter=replace(state.filter, recursive=True),
    )

    result = reduce_app_state(state, SetFilterQuery("spec"))

    assert result.state.filter.query == "spec"
    assert result.state.pending_recursive_filter_request_id == 1
    assert result.effects == (
        LoadRecursiveFilterEffect(
            request_id=1,
            path="/home/tadashi/develop/plain",
            query="spec",
        ),
    )


def test_recursive_filter_loaded_updates_recursive_entries_and_cursor() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        filter=replace(state.filter, query="md", active=True, recursive=True),
        current_pane=replace(state.current_pane, cursor_path="/missing"),
        pending_recursive_filter_request_id=7,
        next_request_id=8,
    )

    result = reduce_app_state(
        state,
        RecursiveFilterLoaded(
            request_id=7,
            entries=(
                DirectoryEntryState(
                    "/home/tadashi/develop/plain/docs/spec_mvp.md",
                    "spec_mvp.md",
                    "file",
                ),
                DirectoryEntryState("/home/tadashi/develop/plain/README.md", "README.md", "file"),
            ),
        ),
    )

    assert result.state.recursive_entries == (
        DirectoryEntryState(
            "/home/tadashi/develop/plain/docs/spec_mvp.md",
            "spec_mvp.md",
            "file",
        ),
        DirectoryEntryState("/home/tadashi/develop/plain/README.md", "README.md", "file"),
    )
    assert result.state.current_pane.cursor_path == "/home/tadashi/develop/plain/docs/spec_mvp.md"
    assert result.state.pending_recursive_filter_request_id is None


def test_browser_snapshot_loaded_queues_recursive_search_for_active_recursive_filter() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        filter=replace(state.filter, query="md", active=True, recursive=True),
        pending_browser_snapshot_request_id=3,
        next_request_id=4,
    )
    snapshot = BrowserSnapshot(
        current_path="/home/tadashi/develop/plain",
        parent_pane=state.parent_pane,
        current_pane=state.current_pane,
        child_pane=state.child_pane,
    )

    result = reduce_app_state(
        state,
        BrowserSnapshotLoaded(
            request_id=3,
            snapshot=snapshot,
            blocking=False,
        ),
    )

    assert result.state.pending_recursive_filter_request_id == 4
    assert result.effects == (
        LoadRecursiveFilterEffect(
            request_id=4,
            path="/home/tadashi/develop/plain",
            query="md",
        ),
    )


def test_set_sort_returns_new_state_without_mutating_input() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(
        state,
        SetSort(field="modified", descending=True, directories_first=False),
    )

    assert next_state.sort.field == "modified"
    assert next_state.sort.descending is True
    assert next_state.sort.directories_first is False
    assert state.sort.field == "name"
    assert state.sort.descending is False
    assert state.sort.directories_first is True


def test_set_sort_keeps_cursor_on_same_visible_path() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, SetCursorPath("/home/tadashi/develop/plain/README.md"))

    next_state = _reduce_state(
        state,
        SetSort(field="modified", descending=True, directories_first=False),
    )

    assert next_state.current_pane.cursor_path == "/home/tadashi/develop/plain/README.md"


def test_set_sort_normalizes_cursor_to_first_visible_path_when_hidden() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, SetFilterQuery("py"))

    next_state = _reduce_state(
        state,
        SetSort(field="name", descending=False, directories_first=True),
    )

    assert next_state.current_pane.cursor_path == "/home/tadashi/develop/plain/pyproject.toml"


def test_set_cursor_path_ignores_unknown_path() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(state, SetCursorPath("/missing"))

    assert next_state == state


def test_enter_cursor_directory_requests_blocking_snapshot() -> None:
    state = build_initial_app_state()

    result = reduce_app_state(state, EnterCursorDirectory())

    assert result.state.pending_browser_snapshot_request_id == 1
    assert result.state.ui_mode == "BUSY"
    assert result.effects == (
        LoadBrowserSnapshotEffect(
            request_id=1,
            path="/home/tadashi/develop/plain/docs",
            cursor_path=None,
            blocking=True,
        ),
    )


def test_go_to_parent_directory_restores_cursor_to_previous_child() -> None:
    state = build_initial_app_state()

    result = reduce_app_state(state, GoToParentDirectory())

    assert result.state.pending_browser_snapshot_request_id == 1
    assert result.state.ui_mode == "BUSY"
    assert len(result.effects) == 1
    assert result.effects[0].path == "/home/tadashi/develop"
    assert result.effects[0].cursor_path == "/home/tadashi/develop/plain"
    assert result.effects[0].blocking is True


def test_go_to_parent_directory_uses_current_path_parent() -> None:
    state = build_initial_app_state()
    state = _reduce_state(
        state,
        BrowserSnapshotLoaded(
            request_id=99,
            snapshot=BrowserSnapshot(
                current_path="/tmp/work/project",
                parent_pane=state.parent_pane,
                current_pane=state.current_pane,
                child_pane=state.child_pane,
            ),
        ),
    )
    state = _reduce_state(state, RequestBrowserSnapshot("/tmp/work/project"))
    state = _reduce_state(
        state,
        BrowserSnapshotLoaded(
            request_id=1,
            snapshot=BrowserSnapshot(
                current_path="/tmp/work/project",
                parent_pane=state.parent_pane,
                current_pane=state.current_pane,
                child_pane=state.child_pane,
            ),
            blocking=True,
        ),
    )

    result = reduce_app_state(state, GoToParentDirectory())

    assert len(result.effects) == 1
    assert result.effects[0].path == "/tmp/work"
    assert result.effects[0].cursor_path == "/tmp/work/project"


def test_reload_directory_requests_snapshot_with_current_cursor() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, SetCursorPath("/home/tadashi/develop/plain/src"))

    result = reduce_app_state(state, ReloadDirectory())

    assert result.state.pending_browser_snapshot_request_id == 2
    assert result.state.ui_mode == "BUSY"
    assert len(result.effects) == 1
    assert result.effects[0].path == "/home/tadashi/develop/plain"
    assert result.effects[0].cursor_path == "/home/tadashi/develop/plain/src"
    assert result.effects[0].blocking is True


def test_begin_filter_input_switches_mode_without_mutating_query() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(state, BeginFilterInput())

    assert next_state.ui_mode == "FILTER"
    assert next_state.filter == state.filter


def test_begin_rename_input_sets_initial_value_from_target_name() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(state, BeginRenameInput("/home/tadashi/develop/plain/docs"))

    assert next_state.ui_mode == "RENAME"
    assert next_state.pending_input == PendingInputState(
        prompt="Rename: ",
        value="docs",
        target_path="/home/tadashi/develop/plain/docs",
    )


def test_begin_create_input_sets_mode_and_kind() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(state, BeginCreateInput("dir"))

    assert next_state.ui_mode == "CREATE"
    assert next_state.pending_input == PendingInputState(
        prompt="New directory: ",
        value="",
        create_kind="dir",
    )


def test_begin_command_palette_sets_mode_and_empty_query() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(state, BeginCommandPalette())

    assert next_state.ui_mode == "PALETTE"
    assert next_state.command_palette is not None
    assert next_state.command_palette.query == ""
    assert next_state.command_palette.cursor_index == 0


def test_move_command_palette_cursor_clamps_to_visible_commands() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())

    next_state = _reduce_state(state, MoveCommandPaletteCursor(delta=10))

    assert next_state.command_palette is not None
    assert next_state.command_palette.cursor_index == 6


def test_set_command_palette_query_resets_cursor() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, MoveCommandPaletteCursor(delta=3))

    next_state = _reduce_state(state, SetCommandPaletteQuery("dir"))

    assert next_state.command_palette is not None
    assert next_state.command_palette.query == "dir"
    assert next_state.command_palette.cursor_index == 0


def test_submit_command_palette_runs_create_file_flow() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())

    next_state = _reduce_state(state, SubmitCommandPalette())

    assert next_state.ui_mode == "CREATE"
    assert next_state.command_palette is None
    assert next_state.pending_input == PendingInputState(
        prompt="New file: ",
        value="",
        create_kind="file",
    )


def test_submit_command_palette_warns_for_disabled_command() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, MoveCommandPaletteCursor(delta=2))

    next_state = _reduce_state(state, SubmitCommandPalette())

    assert next_state.ui_mode == "PALETTE"
    assert next_state.notification == NotificationState(
        level="warning",
        message="Copy path is not available yet",
    )


def test_submit_command_palette_toggles_hidden_files() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery("hidden"))

    next_state = _reduce_state(state, SubmitCommandPalette())

    assert next_state.ui_mode == "BROWSING"
    assert next_state.command_palette is None
    assert next_state.show_hidden is True
    assert next_state.notification == NotificationState(
        level="info",
        message="Hidden files shown",
    )


def test_toggle_hidden_files_normalizes_cursor_and_selection() -> None:
    hidden_path = "/home/tadashi/develop/plain/.env"
    visible_path = "/home/tadashi/develop/plain/docs"
    state = replace(
        build_initial_app_state(),
        show_hidden=True,
        current_pane=PaneState(
            directory_path="/home/tadashi/develop/plain",
            entries=(
                DirectoryEntryState(hidden_path, ".env", "file", hidden=True),
                DirectoryEntryState(visible_path, "docs", "dir"),
            ),
            cursor_path=hidden_path,
            selected_paths=frozenset({hidden_path, visible_path}),
        ),
    )

    next_state = _reduce_state(state, ToggleHiddenFiles())

    assert next_state.show_hidden is False
    assert next_state.current_pane.cursor_path == visible_path
    assert next_state.current_pane.selected_paths == frozenset({visible_path})
    assert next_state.notification == NotificationState(
        level="info",
        message="Hidden files hidden",
    )


def test_cancel_command_palette_returns_to_browsing() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())

    next_state = _reduce_state(state, CancelCommandPalette())

    assert next_state.ui_mode == "BROWSING"
    assert next_state.command_palette is None


def test_begin_delete_targets_single_runs_file_mutation() -> None:
    state = build_initial_app_state()

    result = reduce_app_state(
        state,
        BeginDeleteTargets(("/home/tadashi/develop/plain/docs",)),
    )

    assert result.state.ui_mode == "BUSY"
    assert result.effects == (
        RunFileMutationEffect(
            request_id=1,
            request=TrashDeleteRequest(paths=("/home/tadashi/develop/plain/docs",)),
        ),
    )


def test_begin_delete_targets_multiple_enters_confirm_mode() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(
        state,
        BeginDeleteTargets(
            (
                "/home/tadashi/develop/plain/docs",
                "/home/tadashi/develop/plain/src",
            )
        ),
    )

    assert next_state.ui_mode == "CONFIRM"
    assert next_state.delete_confirmation == DeleteConfirmationState(
        paths=(
            "/home/tadashi/develop/plain/docs",
            "/home/tadashi/develop/plain/src",
        )
    )


def test_cancel_pending_input_returns_to_browsing() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="RENAME",
        pending_input=PendingInputState(prompt="Rename: ", value="docs"),
    )

    next_state = _reduce_state(state, CancelPendingInput())

    assert next_state.ui_mode == "BROWSING"
    assert next_state.pending_input is None


def test_confirm_delete_targets_runs_file_mutation() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        delete_confirmation=DeleteConfirmationState(
            paths=(
                "/home/tadashi/develop/plain/docs",
                "/home/tadashi/develop/plain/src",
            )
        ),
        next_request_id=4,
    )

    result = reduce_app_state(state, ConfirmDeleteTargets())

    assert result.state.ui_mode == "BUSY"
    assert result.effects == (
        RunFileMutationEffect(
            request_id=4,
            request=TrashDeleteRequest(
                paths=(
                    "/home/tadashi/develop/plain/docs",
                    "/home/tadashi/develop/plain/src",
                )
            ),
        ),
    )


def test_cancel_delete_confirmation_returns_to_browsing_with_warning() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        delete_confirmation=DeleteConfirmationState(
            paths=("/home/tadashi/develop/plain/docs",),
        ),
    )

    next_state = _reduce_state(state, CancelDeleteConfirmation())

    assert next_state.ui_mode == "BROWSING"
    assert next_state.notification == NotificationState(level="warning", message="Delete cancelled")


def test_set_pending_input_value_updates_current_value() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CREATE",
        pending_input=PendingInputState(prompt="New file: ", value="", create_kind="file"),
    )

    next_state = _reduce_state(state, SetPendingInputValue("notes.txt"))

    assert next_state.pending_input is not None
    assert next_state.pending_input.value == "notes.txt"


def test_submit_pending_input_rejects_duplicate_name() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CREATE",
        pending_input=PendingInputState(
            prompt="New file: ",
            value="README.md",
            create_kind="file",
        ),
    )

    next_state = _reduce_state(state, SubmitPendingInput())

    assert next_state.ui_mode == "CREATE"
    assert next_state.pending_input is not None
    assert next_state.notification == NotificationState(
        level="error",
        message="An entry named 'README.md' already exists",
    )


def test_submit_pending_input_treats_unchanged_rename_as_noop() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="RENAME",
        pending_input=PendingInputState(
            prompt="Rename: ",
            value="docs",
            target_path="/home/tadashi/develop/plain/docs",
        ),
    )

    next_state = _reduce_state(state, SubmitPendingInput())

    assert next_state.ui_mode == "BROWSING"
    assert next_state.pending_input is None
    assert next_state.notification == NotificationState(level="info", message="Name unchanged")


def test_submit_pending_input_emits_file_mutation_effect() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="RENAME",
        pending_input=PendingInputState(
            prompt="Rename: ",
            value="manuals",
            target_path="/home/tadashi/develop/plain/docs",
        ),
    )

    result = reduce_app_state(state, SubmitPendingInput())

    assert result.state.ui_mode == "BUSY"
    assert result.state.pending_file_mutation_request_id == 1
    assert result.effects == (
        RunFileMutationEffect(
            request_id=1,
            request=RenameRequest(
                source_path="/home/tadashi/develop/plain/docs",
                new_name="manuals",
            ),
        ),
    )


def test_submit_pending_input_emits_create_effect() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CREATE",
        pending_input=PendingInputState(
            prompt="New file: ",
            value="notes.txt",
            create_kind="file",
        ),
    )

    result = reduce_app_state(state, SubmitPendingInput())

    assert result.effects == (
        RunFileMutationEffect(
            request_id=1,
            request=CreatePathRequest(
                parent_dir="/home/tadashi/develop/plain",
                name="notes.txt",
                kind="file",
            ),
        ),
    )


def test_confirm_filter_input_returns_to_browsing() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, SetUiMode("FILTER"))

    next_state = _reduce_state(state, ConfirmFilterInput())

    assert next_state.ui_mode == "BROWSING"


def test_cancel_filter_input_clears_query_and_recursive_flag() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, SetUiMode("FILTER"))
    state = _reduce_state(state, SetFilterQuery("readme"))

    next_state = _reduce_state(state, CancelFilterInput())

    assert next_state.ui_mode == "BROWSING"
    assert next_state.filter.query == ""
    assert next_state.filter.active is False
    assert next_state.filter.recursive is False


def test_copy_targets_updates_clipboard_state() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(state, CopyTargets(("/home/tadashi/develop/plain/docs",)))

    assert next_state.clipboard.mode == "copy"
    assert next_state.clipboard.paths == ("/home/tadashi/develop/plain/docs",)


def test_paste_clipboard_emits_paste_effect_and_sets_busy() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        CopyTargets(("/home/tadashi/develop/plain/docs",)),
    )

    result = reduce_app_state(state, PasteClipboard())

    assert result.state.ui_mode == "BUSY"
    assert result.state.pending_paste_request_id == 1
    assert result.effects == (
        RunClipboardPasteEffect(
            request_id=1,
            request=result.effects[0].request,
        ),
    )
    assert result.effects[0].request.destination_dir == "/home/tadashi/develop/plain"


def test_paste_needs_resolution_enters_confirm_mode() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        CopyTargets(("/home/tadashi/develop/plain/docs",)),
    )
    requested = reduce_app_state(state, PasteClipboard()).state

    conflict = PasteConflict(
        source_path="/home/tadashi/develop/plain/docs",
        destination_path="/home/tadashi/develop/plain/docs",
    )
    next_state = _reduce_state(
        requested,
        ClipboardPasteNeedsResolution(
            request_id=1,
            request=PasteRequest(
                mode="copy",
                source_paths=("/home/tadashi/develop/plain/docs",),
                destination_dir="/home/tadashi/develop/plain",
            ),
            conflicts=(conflict,),
        ),
    )

    assert next_state.ui_mode == "CONFIRM"
    assert isinstance(next_state.paste_conflict, PasteConflictState)
    assert next_state.paste_conflict.first_conflict == conflict


def test_resolve_paste_conflict_restarts_paste_with_resolution() -> None:
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
        next_request_id=2,
    )
    state = replace(
        state,
        notification=None,
    )

    result = reduce_app_state(state, ResolvePasteConflict("rename"))

    assert result.state.ui_mode == "BUSY"
    assert result.effects == (
        RunClipboardPasteEffect(
            request_id=2,
            request=PasteRequest(
                mode="copy",
                source_paths=("/home/tadashi/develop/plain/docs",),
                destination_dir="/home/tadashi/develop/plain",
                conflict_resolution="rename",
            ),
        ),
    )


def test_clipboard_paste_completed_for_cut_clears_clipboard_and_requests_reload() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        CutTargets(("/home/tadashi/develop/plain/docs",)),
    )
    state = replace(state, pending_paste_request_id=4)

    result = reduce_app_state(
        state,
        ClipboardPasteCompleted(
            request_id=4,
            summary=PasteSummary(
                mode="cut",
                destination_dir="/home/tadashi/develop/plain",
                total_count=1,
                success_count=1,
                skipped_count=0,
            ),
        ),
    )

    assert result.state.clipboard.mode == "none"
    assert result.state.pending_browser_snapshot_request_id == 1


def test_file_mutation_completed_requests_reload_with_result_cursor() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        pending_file_mutation_request_id=4,
        pending_input=PendingInputState(
            prompt="New file: ",
            value="notes.txt",
            create_kind="file",
        ),
    )

    result = reduce_app_state(
        state,
        FileMutationCompleted(
            request_id=4,
            result=FileMutationResult(
                path="/home/tadashi/develop/plain/notes.txt",
                message="Created file notes.txt",
            ),
        ),
    )

    assert result.state.ui_mode == "BROWSING"
    assert result.state.pending_input is None
    assert result.state.pending_browser_snapshot_request_id == 1
    assert result.effects == (
        LoadBrowserSnapshotEffect(
            request_id=1,
            path="/home/tadashi/develop/plain",
            cursor_path="/home/tadashi/develop/plain/notes.txt",
            blocking=False,
        ),
    )


def test_delete_file_mutation_completed_requests_reload_without_deleted_cursor() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        pending_file_mutation_request_id=7,
        current_pane=replace(
            build_initial_app_state().current_pane,
            cursor_path="/home/tadashi/develop/plain/docs",
        ),
    )

    result = reduce_app_state(
        state,
        FileMutationCompleted(
            request_id=7,
            result=FileMutationResult(
                path=None,
                message="Trashed 1 item",
                removed_paths=("/home/tadashi/develop/plain/docs",),
            ),
        ),
    )

    assert result.state.ui_mode == "BROWSING"
    assert result.effects == (
        LoadBrowserSnapshotEffect(
            request_id=1,
            path="/home/tadashi/develop/plain",
            cursor_path="/home/tadashi/develop/plain/src",
            blocking=False,
        ),
    )


def test_file_mutation_failed_keeps_input_value_and_returns_error() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        pending_file_mutation_request_id=3,
        pending_input=PendingInputState(
            prompt="Rename: ",
            value="docs copy",
            target_path="/home/tadashi/develop/plain/docs",
        ),
    )

    next_state = _reduce_state(state, FileMutationFailed(request_id=3, message="permission denied"))

    assert next_state.ui_mode == "RENAME"
    assert next_state.pending_input is not None
    assert next_state.pending_input.value == "docs copy"
    assert next_state.notification == NotificationState(
        level="error",
        message="permission denied",
    )


def test_delete_file_mutation_failed_returns_to_browsing() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        pending_file_mutation_request_id=5,
    )

    next_state = _reduce_state(state, FileMutationFailed(request_id=5, message="trash failed"))

    assert next_state.ui_mode == "BROWSING"
    assert next_state.notification == NotificationState(
        level="error",
        message="trash failed",
    )


def test_cancel_paste_conflict_returns_to_browsing_with_warning() -> None:
    state = replace(build_initial_app_state(), ui_mode="CONFIRM")

    next_state = _reduce_state(state, CancelPasteConflict())

    assert next_state.ui_mode == "BROWSING"
    assert next_state.notification == NotificationState(level="warning", message="Paste cancelled")


def test_toggle_selection_and_advance_moves_cursor_to_next_visible_entry() -> None:
    state = build_initial_app_state()
    current_path = "/home/tadashi/develop/plain/docs"
    visible_paths = (
        "/home/tadashi/develop/plain/docs",
        "/home/tadashi/develop/plain/src",
        "/home/tadashi/develop/plain/tests",
        "/home/tadashi/develop/plain/README.md",
        "/home/tadashi/develop/plain/pyproject.toml",
    )

    result = reduce_app_state(
        state,
        ToggleSelectionAndAdvance(path=current_path, visible_paths=visible_paths),
    )

    assert result.state.current_pane.selected_paths == frozenset({current_path})
    assert result.state.current_pane.cursor_path == "/home/tadashi/develop/plain/src"
    assert result.state.pending_child_pane_request_id == 1
    assert result.effects == (
        LoadChildPaneSnapshotEffect(
            request_id=1,
            current_path="/home/tadashi/develop/plain",
            cursor_path="/home/tadashi/develop/plain/src",
        ),
    )


def test_request_browser_snapshot_returns_effect_and_updates_pending_request() -> None:
    state = build_initial_app_state()

    result = reduce_app_state(state, RequestBrowserSnapshot("/tmp/example"))

    assert result.state.pending_browser_snapshot_request_id == 1
    assert result.state.pending_child_pane_request_id is None
    assert result.state.next_request_id == 2
    assert len(result.effects) == 1
    assert result.effects[0].path == "/tmp/example"
    assert result.effects[0].request_id == 1


def test_browser_snapshot_loaded_ignores_stale_request() -> None:
    state = build_initial_app_state()
    state = _reduce_state(state, RequestBrowserSnapshot("/tmp/example"))
    snapshot = BrowserSnapshot(
        current_path="/tmp/new",
        parent_pane=state.parent_pane,
        current_pane=state.current_pane,
        child_pane=state.child_pane,
    )

    next_state = _reduce_state(
        state,
        BrowserSnapshotLoaded(request_id=99, snapshot=snapshot),
    )

    assert next_state == state


def test_browser_snapshot_loaded_applies_snapshot_and_clears_error() -> None:
    state = build_initial_app_state()
    requested = reduce_app_state(state, RequestBrowserSnapshot("/tmp/example")).state
    requested = _reduce_state(
        requested,
        BrowserSnapshotFailed(request_id=1, message="boom"),
    )
    snapshot = BrowserSnapshot(
        current_path="/tmp/example",
        parent_pane=requested.parent_pane,
        current_pane=requested.current_pane,
        child_pane=requested.child_pane,
    )
    requested = _reduce_state(requested, RequestBrowserSnapshot("/tmp/example"))

    next_state = _reduce_state(
        requested,
        BrowserSnapshotLoaded(request_id=2, snapshot=snapshot),
    )

    assert next_state.current_path == "/tmp/example"
    assert next_state.notification is None
    assert next_state.pending_browser_snapshot_request_id is None


def test_browser_snapshot_loaded_preserves_remaining_selection_on_reload() -> None:
    state = build_initial_app_state()
    state = _reduce_state(
        state,
        ToggleSelection("/home/tadashi/develop/plain/docs"),
    )
    state = _reduce_state(
        state,
        ToggleSelection("/home/tadashi/develop/plain/README.md"),
    )
    requested = reduce_app_state(
        state,
        RequestBrowserSnapshot("/home/tadashi/develop/plain", blocking=True),
    ).state

    snapshot = BrowserSnapshot(
        current_path="/home/tadashi/develop/plain",
        parent_pane=requested.parent_pane,
        current_pane=PaneState(
            directory_path="/home/tadashi/develop/plain",
            entries=(
                DirectoryEntryState("/home/tadashi/develop/plain/docs", "docs", "dir"),
                DirectoryEntryState("/home/tadashi/develop/plain/src", "src", "dir"),
            ),
            cursor_path="/home/tadashi/develop/plain/src",
        ),
        child_pane=PaneState(directory_path="/home/tadashi/develop/plain/src", entries=()),
    )

    next_state = _reduce_state(
        requested,
        BrowserSnapshotLoaded(request_id=1, snapshot=snapshot, blocking=True),
    )

    assert next_state.current_pane.selected_paths == frozenset(
        {"/home/tadashi/develop/plain/docs"}
    )


def test_browser_snapshot_loaded_clears_selection_when_directory_changes() -> None:
    state = build_initial_app_state()
    state = _reduce_state(
        state,
        ToggleSelection("/home/tadashi/develop/plain/docs"),
    )
    requested = reduce_app_state(
        state,
        RequestBrowserSnapshot("/home/tadashi/develop/plain/docs", blocking=True),
    ).state

    snapshot = BrowserSnapshot(
        current_path="/home/tadashi/develop/plain/docs",
        parent_pane=PaneState(
            directory_path="/home/tadashi/develop/plain",
            entries=state.current_pane.entries,
            cursor_path="/home/tadashi/develop/plain/docs",
        ),
        current_pane=PaneState(
            directory_path="/home/tadashi/develop/plain/docs",
            entries=(
                DirectoryEntryState(
                    "/home/tadashi/develop/plain/docs/spec.md",
                    "spec.md",
                    "file",
                ),
            ),
            cursor_path="/home/tadashi/develop/plain/docs/spec.md",
        ),
        child_pane=PaneState(directory_path="/home/tadashi/develop/plain/docs", entries=()),
    )

    next_state = _reduce_state(
        requested,
        BrowserSnapshotLoaded(request_id=1, snapshot=snapshot, blocking=True),
    )

    assert next_state.current_pane.selected_paths == frozenset()


def test_browser_snapshot_failed_sets_error_notification() -> None:
    state = build_initial_app_state()
    requested = reduce_app_state(state, RequestBrowserSnapshot("/tmp/example")).state

    next_state = _reduce_state(
        requested,
        BrowserSnapshotFailed(request_id=1, message="load failed"),
    )

    assert next_state.notification == NotificationState(
        level="error",
        message="load failed",
    )
    assert next_state.pending_browser_snapshot_request_id is None


def test_move_cursor_emits_child_snapshot_effect_only_when_target_changes() -> None:
    state = build_initial_app_state()
    visible_paths = (
        "/home/tadashi/develop/plain/docs",
        "/home/tadashi/develop/plain/src",
        "/home/tadashi/develop/plain/tests",
    )

    result = reduce_app_state(state, SetCursorPath("/home/tadashi/develop/plain/docs"))
    assert result.effects == ()

    moved = reduce_app_state(state, SetCursorPath("/home/tadashi/develop/plain/src"))

    assert moved.state.pending_child_pane_request_id == 1
    assert moved.effects == (
        LoadChildPaneSnapshotEffect(
            request_id=1,
            current_path="/home/tadashi/develop/plain",
            cursor_path="/home/tadashi/develop/plain/src",
        ),
    )

    down = reduce_app_state(state, MoveCursor(delta=1, visible_paths=visible_paths))

    assert down.state.current_pane.cursor_path == "/home/tadashi/develop/plain/src"
    assert down.effects == (
        LoadChildPaneSnapshotEffect(
            request_id=1,
            current_path="/home/tadashi/develop/plain",
            cursor_path="/home/tadashi/develop/plain/src",
        ),
    )


def test_set_cursor_path_to_file_clears_child_pane_without_effect() -> None:
    state = build_initial_app_state()

    result = reduce_app_state(state, SetCursorPath("/home/tadashi/develop/plain/README.md"))

    assert result.state.child_pane.directory_path == "/home/tadashi/develop/plain"
    assert result.state.child_pane.entries == ()
    assert result.effects == ()


def test_child_pane_snapshot_loaded_ignores_stale_request() -> None:
    state = build_initial_app_state()
    requested = reduce_app_state(state, SetCursorPath("/home/tadashi/develop/plain/src")).state

    next_state = _reduce_state(
        requested,
        ChildPaneSnapshotLoaded(
            request_id=99,
            pane=requested.child_pane,
        ),
    )

    assert next_state == requested


def test_child_pane_snapshot_failure_sets_error_and_clears_entries() -> None:
    state = build_initial_app_state()
    requested = reduce_app_state(state, SetCursorPath("/home/tadashi/develop/plain/src")).state

    next_state = _reduce_state(
        requested,
        ChildPaneSnapshotFailed(request_id=1, message="permission denied"),
    )

    assert next_state.child_pane.directory_path == "/home/tadashi/develop/plain"
    assert next_state.child_pane.entries == ()
    assert next_state.notification == NotificationState(
        level="error",
        message="permission denied",
    )
