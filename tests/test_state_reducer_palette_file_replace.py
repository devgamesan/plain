"""Test State Reducer Palette File Replace tests."""
from tests.support.paths import TEST_PROJECT_ROOT
from tests.support.reducer_palette_replace import (
    BeginCommandPalette,
    BeginFindAndReplace,
    BeginReplaceFromSearchResults,
    BeginTextReplace,
    CancelCommandPalette,
    CommandPaletteState,
    ConfirmReplaceTargets,
    CycleFindReplaceField,
    CycleReplaceField,
    DirectoryEntryState,
    FileSearchCompleted,
    FileSearchResultState,
    LoadCurrentPaneEffect,
    MoveCommandPaletteCursor,
    NotificationState,
    PaneState,
    ReplacePreviewPaletteState,
    ReplacePreviewResultState,
    RunFileSearchEffect,
    RunTextReplaceApplyEffect,
    RunTextReplacePreviewEffect,
    SetCommandPaletteQuery,
    SetFindReplaceField,
    SetReplaceField,
    SetReplaceScope,
    SubmitCommandPalette,
    TextReplaceApplied,
    TextReplaceApplyFailed,
    TextReplacePreviewCompleted,
    TextReplacePreviewEntry,
    TextReplacePreviewFailed,
    TextReplacePreviewResult,
    TextReplaceRequest,
    TextReplaceResult,
    _reduce_state,
    browser_snapshot_invalidation_paths,
    build_initial_app_state,
    reduce_app_state,
    replace,
)


def test_begin_text_replace_enters_replace_mode() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginTextReplace(target_paths=(TEST_PROJECT_ROOT + '/README.md',)),
    )

    assert state.ui_mode == "PALETTE"
    assert state.command_palette is not None
    assert state.command_palette.source == "replace_text"
    assert state.command_palette.replace_preview.target_paths == (
        TEST_PROJECT_ROOT + '/README.md',
    )

def test_begin_replace_from_find_results_uses_search_results_scope() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="file_search",
            query="readme",
            file_search=replace(
                CommandPaletteState().file_search,
                results=(
                    FileSearchResultState("/tmp/README.md", "README.md", "file"),
                    FileSearchResultState("/tmp/docs", "docs", "directory"),
                ),
            ),
        ),
    )

    result = reduce_app_state(state, BeginReplaceFromSearchResults())

    assert result.state.command_palette is not None
    preview = result.state.command_palette.replace_preview
    assert result.state.command_palette.source == "replace_text"
    assert preview.scope == "search_results"
    assert preview.find_text == "readme"
    assert preview.target_paths == ("/tmp/README.md",)
    assert preview.result_origin == "find"
    assert preview.result_query == "readme"
    assert preview.result_file_count == 1

def test_begin_text_replace_prefers_selected_files_scope() -> None:
    path = TEST_PROJECT_ROOT + '/README.md'
    state = replace(
        build_initial_app_state(),
        current_pane=PaneState(
            directory_path=TEST_PROJECT_ROOT,
            entries=(DirectoryEntryState(path, "README.md", "file"),),
            cursor_path=path,
            selected_paths=frozenset({path}),
        ),
    )

    result = reduce_app_state(state, BeginTextReplace())

    assert result.state.command_palette is not None
    assert result.state.command_palette.replace_preview.scope == "selected_files"
    assert result.state.command_palette.replace_preview.target_paths == (path,)

def test_replace_scope_reports_unavailable_selected_files() -> None:
    state = _reduce_state(build_initial_app_state(), BeginTextReplace())

    result = reduce_app_state(state, SetReplaceScope(scope="selected_files"))

    assert result.state.notification == NotificationState(
        level="warning",
        message="Selected files requires one or more selected files",
    )

def test_replace_scope_can_change_with_left_or_right_navigation() -> None:
    state = _reduce_state(build_initial_app_state(), BeginTextReplace())

    result = reduce_app_state(state, SetReplaceScope(scope="found_files"))

    assert result.state.command_palette is not None
    assert result.state.command_palette.replace_preview.scope == "found_files"
    assert result.state.command_palette.replace_preview.active_field == "scope"
    assert result.state.command_palette.cursor_index == 0

def test_set_replace_field_starts_preview_effect() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginTextReplace(target_paths=(TEST_PROJECT_ROOT + '/README.md',)),
    )

    result = reduce_app_state(state, SetReplaceField(field="find", value="todo"))

    assert result.state.command_palette is not None
    assert result.state.pending_replace_preview_request_id == 1
    assert result.effects == (
        RunTextReplacePreviewEffect(
            request_id=1,
            request=TextReplaceRequest(
                paths=(TEST_PROJECT_ROOT + '/README.md',),
                find_text="todo",
                replace_text="",
            ),
        ),
    )

def test_cycle_replace_field_switches_active_input() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginTextReplace(target_paths=(TEST_PROJECT_ROOT + '/README.md',)),
    )

    next_state = _reduce_state(state, CycleReplaceField(delta=1))

    assert next_state.command_palette is not None
    assert next_state.command_palette.replace_preview.active_field == "replace"

def test_text_replace_preview_completed_updates_palette_results() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginTextReplace(target_paths=(TEST_PROJECT_ROOT + '/README.md',)),
    )
    state = replace(
        state,
        pending_replace_preview_request_id=4,
        command_palette=replace(
            state.command_palette,
            replace_preview=replace(
                state.command_palette.replace_preview,
                find_text="todo",
            ),
        ),
    )

    next_state = _reduce_state(
        state,
        TextReplacePreviewCompleted(
            request_id=4,
            result=TextReplacePreviewResult(
                request=TextReplaceRequest(
                    paths=(TEST_PROJECT_ROOT + '/README.md',),
                    find_text="todo",
                    replace_text="done",
                ),
                changed_entries=(
                    TextReplacePreviewEntry(
                        path=TEST_PROJECT_ROOT + '/README.md',
                        diff_text="--- before\n+++ after\n@@\n-todo item\n+done item\n",
                        match_count=2,
                        first_match_line_number=12,
                        first_match_before="todo item",
                        first_match_after="done item",
                    ),
                ),
                total_match_count=2,
                diff_text="--- before\n+++ after\n@@\n-todo item\n+done item\n",
            ),
        ),
    )

    assert next_state.command_palette is not None
    assert next_state.command_palette.replace_preview.total_match_count == 2
    assert next_state.command_palette.replace_preview.preview_results[0].display_path == "README.md"
    assert next_state.command_palette.replace_preview.preview_results[0].diff_text == (
        "--- before\n+++ after\n@@\n-todo item\n+done item\n"
    )
    assert next_state.child_pane.preview_title == "Replace Preview"
    assert next_state.child_pane.preview_content == (
        "--- before\n+++ after\n@@\n-todo item\n+done item\n"
    )
    assert next_state.child_pane.preview_path == TEST_PROJECT_ROOT + '/README.md'
    assert next_state.pending_replace_preview_request_id is None

def test_move_palette_cursor_updates_replace_preview_diff() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginTextReplace(
            target_paths=(
                TEST_PROJECT_ROOT + '/README.md',
                TEST_PROJECT_ROOT + '/docs/notes.md',
            )
        ),
    )
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            replace_preview=ReplacePreviewPaletteState(
                preview_results=(
                ReplacePreviewResultState(
                    path=TEST_PROJECT_ROOT + '/README.md',
                    display_path="README.md",
                    diff_text="--- README\n+++ README\n@@\n-todo\n+done\n",
                    match_count=1,
                    first_match_line_number=1,
                    first_match_before="todo",
                    first_match_after="done",
                ),
                ReplacePreviewResultState(
                    path=TEST_PROJECT_ROOT + '/docs/notes.md',
                    display_path="docs/notes.md",
                    diff_text="--- notes\n+++ notes\n@@\n-todo\n+done\n",
                    match_count=1,
                    first_match_line_number=2,
                    first_match_before="todo",
                    first_match_after="done",
                ),
            ),
                total_match_count=2,
            ),
        ),
        child_pane=PaneState(
            directory_path=state.current_path,
            entries=(),
            mode="preview",
            preview_path=TEST_PROJECT_ROOT + '/README.md',
            preview_title="Replace Preview",
            preview_content="--- README\n+++ README\n@@\n-todo\n+done\n",
        ),
    )

    result = reduce_app_state(state, MoveCommandPaletteCursor(delta=1))

    assert result.state.command_palette is not None
    assert result.state.command_palette.cursor_index == 1
    assert result.state.child_pane.preview_path == TEST_PROJECT_ROOT + '/docs/notes.md'
    assert result.state.child_pane.preview_content == (
        "--- notes\n+++ notes\n@@\n-todo\n+done\n"
    )

def test_text_replace_preview_failed_sets_inline_error_for_invalid_regex() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginTextReplace(target_paths=(TEST_PROJECT_ROOT + '/README.md',)),
    )
    state = replace(state, pending_replace_preview_request_id=4)

    next_state = _reduce_state(
        state,
        TextReplacePreviewFailed(
            request_id=4,
            message="missing )",
            invalid_query=True,
        ),
    )

    assert next_state.command_palette is not None
    assert next_state.command_palette.replace_preview.error_message == "missing )"
    assert next_state.pending_replace_preview_request_id is None

def test_submit_command_palette_applies_replace_when_preview_exists() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginTextReplace(target_paths=(TEST_PROJECT_ROOT + '/README.md',)),
    )
    state = replace(
        state,
        next_request_id=8,
        command_palette=replace(
            state.command_palette,
            replace_preview=replace(
                state.command_palette.replace_preview,
                find_text="todo",
                replacement_text="done",
                total_match_count=2,
                preview_results=(
                ReplacePreviewResultState(
                    path=TEST_PROJECT_ROOT + '/README.md',
                    display_path="README.md",
                    diff_text="--- before\n+++ after\n@@\n-todo item\n+done item\n",
                    match_count=2,
                    first_match_line_number=12,
                    first_match_before="todo item",
                    first_match_after="done item",
                ),
            ),
            ),
        ),
    )

    result = reduce_app_state(state, SubmitCommandPalette())

    # Check that confirmation dialog is shown
    assert result.state.ui_mode == "CONFIRM"
    assert result.state.replace_confirmation is not None
    assert result.state.replace_confirmation.find_text == "todo"
    assert result.state.replace_confirmation.replacement_text == "done"
    assert result.state.replace_confirmation.total_match_count == 2

    # Confirm the replace operation
    result = reduce_app_state(result.state, ConfirmReplaceTargets())

    assert result.state.pending_replace_apply_request_id == 8
    # ui_mode is BUSY because blocking snapshot request
    assert result.state.ui_mode in ("BROWSING", "BUSY")
    assert any(isinstance(e, RunTextReplaceApplyEffect) for e in result.effects)

def test_text_replace_applied_refreshes_current_directory() -> None:
    state = replace(
        build_initial_app_state(),
        pending_replace_apply_request_id=6,
        current_path=TEST_PROJECT_ROOT,
        current_pane=replace(
            build_initial_app_state().current_pane,
            cursor_path=TEST_PROJECT_ROOT + '/README.md',
        ),
    )

    result = reduce_app_state(
        state,
        TextReplaceApplied(
            request_id=6,
            result=TextReplaceResult(
                request=TextReplaceRequest(
                    paths=(TEST_PROJECT_ROOT + '/README.md',),
                    find_text="todo",
                    replace_text="done",
                ),
                changed_paths=(TEST_PROJECT_ROOT + '/README.md',),
                total_match_count=3,
                message="Replaced 3 match(es) in 1 file(s)",
            ),
        ),
    )

    assert result.state.post_reload_notification == NotificationState(
        level="info",
        message="Replaced 3 match(es) in 1 file(s)",
        auto_dismiss=True,
    )
    assert result.effects == (
        LoadCurrentPaneEffect(
            request_id=1,
            path=TEST_PROJECT_ROOT,
            cursor_path=TEST_PROJECT_ROOT + '/README.md',
            invalidate_paths=browser_snapshot_invalidation_paths(
                TEST_PROJECT_ROOT,
                TEST_PROJECT_ROOT + '/README.md',
            ),
        ),
    )

def test_text_replace_apply_failed_sets_error_notification() -> None:
    state = replace(
        build_initial_app_state(),
        pending_replace_apply_request_id=3,
    )

    next_state = _reduce_state(
        state,
        TextReplaceApplyFailed(request_id=3, message="permission denied"),
    )

    assert next_state.pending_replace_apply_request_id is None
    assert next_state.notification == NotificationState(
        level="error",
        message="permission denied",
    )

def test_run_replace_text_command_uses_cursor_file_when_nothing_is_selected() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = replace(
        state,
        command_palette=replace(state.command_palette, query="replace text"),
        current_pane=replace(
            state.current_pane,
            selected_paths=frozenset(),
            cursor_path=TEST_PROJECT_ROOT + '/README.md',
        ),
    )

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.command_palette is not None
    assert result.state.command_palette.source == "replace_text"
    assert result.state.command_palette.replace_preview.target_paths == (
        TEST_PROJECT_ROOT + '/README.md',
    )

def test_begin_find_and_replace_enters_rff_mode() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFindAndReplace())

    assert state.ui_mode == "PALETTE"
    assert state.command_palette is not None
    assert state.command_palette.source == "replace_in_found_files"
    assert state.command_palette.rff.active_field == "filename"

def test_set_rff_filename_field_starts_file_search() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFindAndReplace())

    result = reduce_app_state(state, SetFindReplaceField(field="filename", value="readme"))

    assert result.state.command_palette is not None
    assert result.state.command_palette.rff.filename_query == "readme"
    assert result.state.pending_file_search_request_id == 1
    assert result.effects == (
        RunFileSearchEffect(
            request_id=1,
            root_path=TEST_PROJECT_ROOT,
            query="readme",
            show_hidden=False,
        ),
    )

def test_set_rff_filename_clear_triggers_no_search() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFindAndReplace())

    result = reduce_app_state(
        state,
        SetFindReplaceField(field="filename", value=""),
    )

    assert result.state.command_palette is not None
    assert result.state.pending_file_search_request_id is None
    assert result.effects == ()

def test_set_rff_find_field_with_file_results_starts_preview() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFindAndReplace())
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            rff=replace(
                state.command_palette.rff,
                filename_query="readme",
                file_results=(
                    FileSearchResultState(
                        path=TEST_PROJECT_ROOT + '/README.md',
                        display_path="README.md",
                    ),
                ),
            ),
        ),
    )

    result = reduce_app_state(state, SetFindReplaceField(field="find", value="todo"))

    assert result.state.command_palette is not None
    assert result.state.command_palette.rff.find_text == "todo"
    assert result.state.pending_replace_preview_request_id == 1
    assert result.effects == (
        RunTextReplacePreviewEffect(
            request_id=1,
            request=TextReplaceRequest(
                paths=(TEST_PROJECT_ROOT + '/README.md',),
                find_text="todo",
                replace_text="",
            ),
        ),
    )

def test_set_rff_find_field_without_file_results_no_preview() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFindAndReplace())

    result = reduce_app_state(state, SetFindReplaceField(field="find", value="todo"))

    assert result.state.command_palette is not None
    assert result.state.pending_replace_preview_request_id is None
    assert result.effects == ()

def test_cycle_find_replace_field_cycles_through_three_fields() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFindAndReplace())

    assert state.command_palette is not None
    assert state.command_palette.rff.active_field == "filename"

    state = _reduce_state(state, CycleFindReplaceField(delta=1))
    assert state.command_palette is not None
    assert state.command_palette.rff.active_field == "find"

    state = _reduce_state(state, CycleFindReplaceField(delta=1))
    assert state.command_palette is not None
    assert state.command_palette.rff.active_field == "replace"

    state = _reduce_state(state, CycleFindReplaceField(delta=1))
    assert state.command_palette is not None
    assert state.command_palette.rff.active_field == "filename"

def test_cycle_find_replace_field_reverse() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFindAndReplace())

    state = _reduce_state(state, CycleFindReplaceField(delta=-1))
    assert state.command_palette is not None
    assert state.command_palette.rff.active_field == "replace"

def test_rff_file_search_completed_stores_results() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFindAndReplace())
    state = replace(
        state,
        pending_file_search_request_id=3,
        command_palette=replace(
            state.command_palette,
            rff=replace(
                state.command_palette.rff,
                filename_query="readme",
            ),
        ),
    )

    next_state = _reduce_state(
        state,
        FileSearchCompleted(
            request_id=3,
            query="readme",
            results=(
                FileSearchResultState(
                    path=TEST_PROJECT_ROOT + '/README.md',
                    display_path="README.md",
                ),
            ),
        ),
    )

    assert next_state.command_palette is not None
    assert next_state.command_palette.rff.file_results == (
        FileSearchResultState(
            path=TEST_PROJECT_ROOT + '/README.md',
            display_path="README.md",
        ),
    )
    assert next_state.pending_file_search_request_id is None

def test_rff_file_search_completed_auto_triggers_preview_when_find_text_present() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFindAndReplace())
    state = replace(
        state,
        pending_file_search_request_id=3,
        command_palette=replace(
            state.command_palette,
            rff=replace(
                state.command_palette.rff,
                filename_query="readme",
                find_text="todo",
            ),
        ),
    )

    result = reduce_app_state(
        state,
        FileSearchCompleted(
            request_id=3,
            query="readme",
            results=(
                FileSearchResultState(
                    path=TEST_PROJECT_ROOT + '/README.md',
                    display_path="README.md",
                ),
            ),
        ),
    )

    assert result.state.pending_replace_preview_request_id is not None
    assert len(result.effects) == 1
    assert isinstance(result.effects[0], RunTextReplacePreviewEffect)

def test_rff_preview_completed_stores_results() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFindAndReplace())
    state = replace(
        state,
        pending_replace_preview_request_id=4,
        command_palette=replace(
            state.command_palette,
            rff=replace(
                state.command_palette.rff,
                find_text="todo",
                replacement_text="done",
                file_results=(
                    FileSearchResultState(
                        path=TEST_PROJECT_ROOT + '/README.md',
                        display_path="README.md",
                    ),
                ),
            ),
        ),
    )

    next_state = _reduce_state(
        state,
        TextReplacePreviewCompleted(
            request_id=4,
            result=TextReplacePreviewResult(
                request=TextReplaceRequest(
                    paths=(TEST_PROJECT_ROOT + '/README.md',),
                    find_text="todo",
                    replace_text="done",
                ),
                changed_entries=(
                    TextReplacePreviewEntry(
                        path=TEST_PROJECT_ROOT + '/README.md',
                        diff_text="-todo\n+done",
                        match_count=1,
                        first_match_line_number=5,
                        first_match_before="todo",
                        first_match_after="done",
                    ),
                ),
                total_match_count=1,
                diff_text="-todo\n+done",
            ),
        ),
    )

    assert next_state.command_palette is not None
    assert next_state.command_palette.rff.total_match_count == 1
    assert len(next_state.command_palette.rff.preview_results) == 1
    assert next_state.command_palette.rff.preview_results[0].display_path == "README.md"
    assert next_state.child_pane.preview_title == "Replace Preview"
    assert next_state.pending_replace_preview_request_id is None

def test_submit_rff_palette_warns_when_no_find_text() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFindAndReplace())

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.notification == NotificationState(
        level="warning",
        message="Find text is required",
    )

def test_submit_rff_palette_warns_when_no_preview_results() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFindAndReplace())
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            rff=replace(
                state.command_palette.rff,
                find_text="todo",
                file_results=(
                    FileSearchResultState(
                        path=TEST_PROJECT_ROOT + '/README.md',
                        display_path="README.md",
                    ),
                ),
            ),
        ),
    )

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.notification is not None
    assert result.state.notification.level == "warning"

def test_cancel_rff_returns_to_browsing() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFindAndReplace())
    assert state.ui_mode == "PALETTE"

    state = _reduce_state(state, CancelCommandPalette())
    assert state.ui_mode == "BROWSING"
    assert state.command_palette is None

def test_submit_command_palette_begins_unified_replace() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery(query="replace text"))

    result = reduce_app_state(state, SubmitCommandPalette())
    assert result.state.command_palette is not None
    assert result.state.command_palette.source == "replace_text"
