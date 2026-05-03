from dataclasses import replace

from tests.state_test_helpers import reduce_state
from zivo.models import (
    TextReplacePreviewEntry,
    TextReplacePreviewResult,
    TextReplaceRequest,
    TextReplaceResult,
)
from zivo.state import (
    DirectoryEntryState,
    FileSearchResultState,
    GrepSearchResultState,
    LoadBrowserSnapshotEffect,
    NotificationState,
    PaneState,
    ReplacePreviewPaletteState,
    ReplacePreviewResultState,
    RunFileSearchEffect,
    RunGrepSearchEffect,
    RunTextReplaceApplyEffect,
    RunTextReplacePreviewEffect,
    build_initial_app_state,
    reduce_app_state,
)
from zivo.state.actions import (
    BeginCommandPalette,
    BeginFindAndReplace,
    BeginGrepReplace,
    BeginGrepReplaceSelected,
    BeginTextReplace,
    CancelCommandPalette,
    ConfirmReplaceTargets,
    CycleFindReplaceField,
    CycleReplaceField,
    FileSearchCompleted,
    GrepSearchCompleted,
    MoveCommandPaletteCursor,
    SetCommandPaletteQuery,
    SetFindReplaceField,
    SetGrepReplaceField,
    SetGrepReplaceSelectedField,
    SetReplaceField,
    SubmitCommandPalette,
    TextReplaceApplied,
    TextReplaceApplyFailed,
    TextReplacePreviewCompleted,
    TextReplacePreviewFailed,
)
from zivo.state.reducer_common import browser_snapshot_invalidation_paths


def _reduce_state(state, action):
    return reduce_state(state, action)


def _viewport_test_entries(
    path: str,
    count: int,
    *,
    hidden_indexes: frozenset[int] = frozenset(),
) -> tuple[DirectoryEntryState, ...]:
    return tuple(
        DirectoryEntryState(
            f"{path}/item_{index:02d}",
            f"item_{index:02d}",
            "file",
            hidden=index in hidden_indexes,
        )
        for index in range(count)
    )


def test_begin_text_replace_enters_replace_mode() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginTextReplace(target_paths=("/home/tadashi/develop/zivo/README.md",)),
    )

    assert state.ui_mode == "PALETTE"
    assert state.command_palette is not None
    assert state.command_palette.source == "replace_text"
    assert state.command_palette.replace_preview.target_paths == (
        "/home/tadashi/develop/zivo/README.md",
    )

def test_set_replace_field_starts_preview_effect() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginTextReplace(target_paths=("/home/tadashi/develop/zivo/README.md",)),
    )

    result = reduce_app_state(state, SetReplaceField(field="find", value="todo"))

    assert result.state.command_palette is not None
    assert result.state.pending_replace_preview_request_id == 1
    assert result.effects == (
        RunTextReplacePreviewEffect(
            request_id=1,
            request=TextReplaceRequest(
                paths=("/home/tadashi/develop/zivo/README.md",),
                find_text="todo",
                replace_text="",
            ),
        ),
    )

def test_cycle_replace_field_switches_active_input() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginTextReplace(target_paths=("/home/tadashi/develop/zivo/README.md",)),
    )

    next_state = _reduce_state(state, CycleReplaceField(delta=1))

    assert next_state.command_palette is not None
    assert next_state.command_palette.replace_preview.active_field == "replace"

def test_text_replace_preview_completed_updates_palette_results() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginTextReplace(target_paths=("/home/tadashi/develop/zivo/README.md",)),
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
                    paths=("/home/tadashi/develop/zivo/README.md",),
                    find_text="todo",
                    replace_text="done",
                ),
                changed_entries=(
                    TextReplacePreviewEntry(
                        path="/home/tadashi/develop/zivo/README.md",
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
    assert next_state.child_pane.preview_path == "/home/tadashi/develop/zivo/README.md"
    assert next_state.pending_replace_preview_request_id is None

def test_move_palette_cursor_updates_replace_preview_diff() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginTextReplace(
            target_paths=(
                "/home/tadashi/develop/zivo/README.md",
                "/home/tadashi/develop/zivo/docs/notes.md",
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
                    path="/home/tadashi/develop/zivo/README.md",
                    display_path="README.md",
                    diff_text="--- README\n+++ README\n@@\n-todo\n+done\n",
                    match_count=1,
                    first_match_line_number=1,
                    first_match_before="todo",
                    first_match_after="done",
                ),
                ReplacePreviewResultState(
                    path="/home/tadashi/develop/zivo/docs/notes.md",
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
            preview_path="/home/tadashi/develop/zivo/README.md",
            preview_title="Replace Preview",
            preview_content="--- README\n+++ README\n@@\n-todo\n+done\n",
        ),
    )

    result = reduce_app_state(state, MoveCommandPaletteCursor(delta=1))

    assert result.state.command_palette is not None
    assert result.state.command_palette.cursor_index == 1
    assert result.state.child_pane.preview_path == "/home/tadashi/develop/zivo/docs/notes.md"
    assert result.state.child_pane.preview_content == (
        "--- notes\n+++ notes\n@@\n-todo\n+done\n"
    )

def test_text_replace_preview_failed_sets_inline_error_for_invalid_regex() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginTextReplace(target_paths=("/home/tadashi/develop/zivo/README.md",)),
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
        BeginTextReplace(target_paths=("/home/tadashi/develop/zivo/README.md",)),
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
                    path="/home/tadashi/develop/zivo/README.md",
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
        current_path="/home/tadashi/develop/zivo",
        current_pane=replace(
            build_initial_app_state().current_pane,
            cursor_path="/home/tadashi/develop/zivo/README.md",
        ),
    )

    result = reduce_app_state(
        state,
        TextReplaceApplied(
            request_id=6,
            result=TextReplaceResult(
                request=TextReplaceRequest(
                    paths=("/home/tadashi/develop/zivo/README.md",),
                    find_text="todo",
                    replace_text="done",
                ),
                changed_paths=("/home/tadashi/develop/zivo/README.md",),
                total_match_count=3,
                message="Replaced 3 match(es) in 1 file(s)",
            ),
        ),
    )

    assert result.state.post_reload_notification == NotificationState(
        level="info",
        message="Replaced 3 match(es) in 1 file(s)",
    )
    assert result.effects == (
        LoadBrowserSnapshotEffect(
            request_id=1,
            path="/home/tadashi/develop/zivo",
            cursor_path="/home/tadashi/develop/zivo/README.md",
            blocking=True,
            invalidate_paths=browser_snapshot_invalidation_paths(
                "/home/tadashi/develop/zivo",
                "/home/tadashi/develop/zivo/README.md",
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
            cursor_path="/home/tadashi/develop/zivo/README.md",
        ),
    )

    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.command_palette is not None
    assert result.state.command_palette.source == "replace_text"
    assert result.state.command_palette.replace_preview.target_paths == (
        "/home/tadashi/develop/zivo/README.md",
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
            root_path="/home/tadashi/develop/zivo",
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
                        path="/home/tadashi/develop/zivo/README.md",
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
                paths=("/home/tadashi/develop/zivo/README.md",),
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
                    path="/home/tadashi/develop/zivo/README.md",
                    display_path="README.md",
                ),
            ),
        ),
    )

    assert next_state.command_palette is not None
    assert next_state.command_palette.rff.file_results == (
        FileSearchResultState(
            path="/home/tadashi/develop/zivo/README.md",
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
                    path="/home/tadashi/develop/zivo/README.md",
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
                        path="/home/tadashi/develop/zivo/README.md",
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
                    paths=("/home/tadashi/develop/zivo/README.md",),
                    find_text="todo",
                    replace_text="done",
                ),
                changed_entries=(
                    TextReplacePreviewEntry(
                        path="/home/tadashi/develop/zivo/README.md",
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
                        path="/home/tadashi/develop/zivo/README.md",
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


# ---------------------------------------------------------------------------
# Grep replace (grf) tests
# ---------------------------------------------------------------------------

def test_begin_grep_replace_enters_grf_mode() -> None:
    state = _reduce_state(build_initial_app_state(), BeginGrepReplace())
    assert state.ui_mode == "PALETTE"
    assert state.command_palette is not None
    assert state.command_palette.source == "replace_in_grep_files"
    assert state.command_palette.grf.active_field == "keyword"

def test_set_grf_keyword_field_starts_grep_search() -> None:
    state = _reduce_state(build_initial_app_state(), BeginGrepReplace())
    result = reduce_app_state(state, SetGrepReplaceField(field="keyword", value="todo"))

    assert result.state.pending_grep_search_request_id is not None
    assert result.state.command_palette.grf.keyword == "todo"
    effects = [e for e in result.effects if isinstance(e, RunGrepSearchEffect)]
    assert len(effects) == 1
    assert effects[0].query == "todo"

def test_set_grf_keyword_clear_triggers_no_search() -> None:
    state = _reduce_state(build_initial_app_state(), BeginGrepReplace())
    state = _reduce_state(state, SetGrepReplaceField(field="keyword", value="todo"))
    result = reduce_app_state(state, SetGrepReplaceField(field="keyword", value=""))

    assert result.state.pending_grep_search_request_id is None
    assert result.state.command_palette.grf.grep_results == ()

def test_set_grf_replace_field_with_grep_results_starts_preview() -> None:
    state = _reduce_state(build_initial_app_state(), BeginGrepReplace())
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            grf=replace(
                state.command_palette.grf,
                keyword="todo",
                grep_results=(
                    GrepSearchResultState(
                        path="/home/tadashi/develop/zivo/README.md",
                        display_path="README.md",
                        line_number=1,
                        line_text="todo item",
                    ),
                ),
            ),
        ),
    )
    result = reduce_app_state(state, SetGrepReplaceField(field="replace", value="done"))

    assert result.state.pending_replace_preview_request_id is not None
    effects = [e for e in result.effects if isinstance(e, RunTextReplacePreviewEffect)]
    assert len(effects) == 1
    assert effects[0].request.paths == ("/home/tadashi/develop/zivo/README.md",)
    assert effects[0].request.find_text == "todo"

def test_set_grf_replace_field_without_grep_results_no_preview() -> None:
    state = _reduce_state(build_initial_app_state(), BeginGrepReplace())
    result = reduce_app_state(state, SetGrepReplaceField(field="replace", value="done"))

    assert result.state.pending_replace_preview_request_id is None
    assert result.state.command_palette.grf.preview_results == ()

def test_grf_grep_search_completed_stores_results() -> None:
    state = _reduce_state(build_initial_app_state(), BeginGrepReplace())
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            grf=replace(state.command_palette.grf, keyword="todo"),
        ),
        pending_grep_search_request_id=10,
        next_request_id=11,
    )
    results = (
        GrepSearchResultState(
            path="/home/tadashi/develop/zivo/README.md",
            display_path="README.md",
            line_number=1,
            line_text="todo item",
        ),
    )
    result = reduce_app_state(
        state, GrepSearchCompleted(request_id=10, query="todo", results=results)
    )

    assert result.state.command_palette.grf.grep_results == results
    assert result.state.pending_grep_search_request_id is None

def test_grf_grep_search_completed_auto_triggers_preview_when_replace_text_present() -> None:
    state = _reduce_state(build_initial_app_state(), BeginGrepReplace())
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            grf=replace(
                state.command_palette.grf,
                keyword="todo",
                replacement_text="done",
            ),
        ),
        pending_grep_search_request_id=10,
        next_request_id=11,
    )
    results = (
        GrepSearchResultState(
            path="/home/tadashi/develop/zivo/README.md",
            display_path="README.md",
            line_number=1,
            line_text="todo item",
        ),
    )
    result = reduce_app_state(
        state, GrepSearchCompleted(request_id=10, query="todo", results=results)
    )

    assert result.state.command_palette.grf.grep_results == results
    assert result.state.pending_replace_preview_request_id is not None
    effects = [e for e in result.effects if isinstance(e, RunTextReplacePreviewEffect)]
    assert len(effects) == 1

def test_grf_preview_completed_stores_results() -> None:
    state = _reduce_state(build_initial_app_state(), BeginGrepReplace())
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            grf=replace(
                state.command_palette.grf,
                keyword="todo",
                replacement_text="done",
                grep_results=(
                    GrepSearchResultState(
                        path="/home/tadashi/develop/zivo/README.md",
                        display_path="README.md",
                        line_number=1,
                        line_text="todo item",
                    ),
                ),
            ),
        ),
        pending_replace_preview_request_id=10,
        next_request_id=11,
    )
    preview_result = TextReplacePreviewResult(
        request=TextReplaceRequest(
            paths=("/home/tadashi/develop/zivo/README.md",),
            find_text="todo",
            replace_text="done",
        ),
        changed_entries=(
            TextReplacePreviewEntry(
                path="/home/tadashi/develop/zivo/README.md",
                diff_text="- todo + done",
                match_count=1,
                first_match_line_number=1,
                first_match_before="todo",
                first_match_after="done",
            ),
        ),
        total_match_count=1,
        skipped_paths=(),
    )
    result = reduce_app_state(
        state, TextReplacePreviewCompleted(request_id=10, result=preview_result)
    )

    assert len(result.state.command_palette.grf.preview_results) == 1
    assert result.state.command_palette.grf.total_match_count == 1
    assert result.state.pending_replace_preview_request_id is None

def test_submit_grf_palette_warns_when_no_replace_text() -> None:
    state = _reduce_state(build_initial_app_state(), BeginGrepReplace())
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            grf=replace(
                state.command_palette.grf,
                keyword="todo",
                grep_results=(
                    GrepSearchResultState(
                        path="/home/tadashi/develop/zivo/README.md",
                        display_path="README.md",
                        line_number=1,
                        line_text="todo item",
                    ),
                ),
            ),
        ),
    )
    result = reduce_app_state(state, SubmitCommandPalette())
    assert result.state.notification is not None
    assert result.state.notification.level == "warning"

def test_submit_grf_palette_warns_when_no_preview_results() -> None:
    state = _reduce_state(build_initial_app_state(), BeginGrepReplace())
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            grf=replace(
                state.command_palette.grf,
                keyword="todo",
                replacement_text="done",
                grep_results=(
                    GrepSearchResultState(
                        path="/home/tadashi/develop/zivo/README.md",
                        display_path="README.md",
                        line_number=1,
                        line_text="todo item",
                    ),
                ),
            ),
        ),
    )
    result = reduce_app_state(state, SubmitCommandPalette())
    assert result.state.notification is not None
    assert result.state.notification.level == "warning"

def test_cancel_grf_returns_to_browsing() -> None:
    state = _reduce_state(build_initial_app_state(), BeginGrepReplace())
    assert state.ui_mode == "PALETTE"

    state = _reduce_state(state, CancelCommandPalette())
    assert state.ui_mode == "BROWSING"
    assert state.command_palette is None

def test_submit_command_palette_begins_grep_replace() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCommandPalette())
    state = _reduce_state(state, SetCommandPaletteQuery(query="replace text in grep"))

    result = reduce_app_state(state, SubmitCommandPalette())
    assert result.state.command_palette is not None
    assert result.state.command_palette.source == "replace_in_grep_files"

def test_grf_grep_search_completed_deduplicates_file_paths() -> None:
    state = _reduce_state(build_initial_app_state(), BeginGrepReplace())
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            grf=replace(
                state.command_palette.grf,
                keyword="todo",
                replacement_text="done",
            ),
        ),
        pending_grep_search_request_id=10,
        next_request_id=11,
    )
    results = (
        GrepSearchResultState(
            path="/home/tadashi/develop/zivo/README.md",
            display_path="README.md",
            line_number=1,
            line_text="todo item 1",
        ),
        GrepSearchResultState(
            path="/home/tadashi/develop/zivo/README.md",
            display_path="README.md",
            line_number=5,
            line_text="todo item 2",
        ),
    )
    result = reduce_app_state(
        state, GrepSearchCompleted(request_id=10, query="todo", results=results)
    )

    effects = [e for e in result.effects if isinstance(e, RunTextReplacePreviewEffect)]
    assert len(effects) == 1
    assert effects[0].request.paths == ("/home/tadashi/develop/zivo/README.md",)


# ---------------------------------------------------------------------------
# Grep replace selected (grs) tests
# ---------------------------------------------------------------------------

def test_begin_grep_replace_selected_enters_grs_mode() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginGrepReplaceSelected(
            target_paths=("/home/tadashi/develop/zivo/a.py", "/home/tadashi/develop/zivo/b.py")
        ),
    )
    assert state.ui_mode == "PALETTE"
    assert state.command_palette is not None
    assert state.command_palette.source == "grep_replace_selected"
    assert state.command_palette.grs.active_field == "keyword"
    assert state.command_palette.grs.target_paths == (
        "/home/tadashi/develop/zivo/a.py",
        "/home/tadashi/develop/zivo/b.py",
    )

def test_set_grs_keyword_field_starts_grep_search() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginGrepReplaceSelected(target_paths=("/home/tadashi/develop/zivo/a.py",)),
    )
    result = reduce_app_state(
        state, SetGrepReplaceSelectedField(field="keyword", value="todo")
    )

    assert result.state.pending_grep_search_request_id is not None
    assert result.state.command_palette.grs.keyword == "todo"
    effects = [e for e in result.effects if isinstance(e, RunGrepSearchEffect)]
    assert len(effects) == 1
    assert effects[0].query == "todo"

def test_set_grs_keyword_clear_triggers_no_search() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginGrepReplaceSelected(target_paths=("/home/tadashi/develop/zivo/a.py",)),
    )
    state = _reduce_state(state, SetGrepReplaceSelectedField(field="keyword", value="todo"))
    result = reduce_app_state(state, SetGrepReplaceSelectedField(field="keyword", value=""))

    assert result.state.pending_grep_search_request_id is None
    assert result.state.command_palette.grs.grep_results == ()

def test_grs_grep_search_completed_filters_to_target_paths() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginGrepReplaceSelected(
            target_paths=("/home/tadashi/develop/zivo/a.py", "/home/tadashi/develop/zivo/c.py")
        ),
    )
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            grs=replace(state.command_palette.grs, keyword="todo"),
        ),
        pending_grep_search_request_id=10,
        next_request_id=11,
    )
    all_results = (
        GrepSearchResultState(
            path="/home/tadashi/develop/zivo/a.py",
            display_path="a.py",
            line_number=1,
            line_text="todo in a",
        ),
        GrepSearchResultState(
            path="/home/tadashi/develop/zivo/b.py",
            display_path="b.py",
            line_number=3,
            line_text="todo in b",
        ),
        GrepSearchResultState(
            path="/home/tadashi/develop/zivo/c.py",
            display_path="c.py",
            line_number=5,
            line_text="todo in c",
        ),
    )
    result = reduce_app_state(
        state, GrepSearchCompleted(request_id=10, query="todo", results=all_results)
    )

    assert len(result.state.command_palette.grs.grep_results) == 2
    assert result.state.command_palette.grs.grep_results[0].path == (
        "/home/tadashi/develop/zivo/a.py"
    )
    assert result.state.command_palette.grs.grep_results[1].path == (
        "/home/tadashi/develop/zivo/c.py"
    )
    assert result.state.pending_grep_search_request_id is None

def test_grs_grep_search_completed_auto_triggers_preview_when_replace_text_present() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginGrepReplaceSelected(target_paths=("/home/tadashi/develop/zivo/a.py",)),
    )
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            grs=replace(
                state.command_palette.grs,
                keyword="todo",
                replacement_text="done",
            ),
        ),
        pending_grep_search_request_id=10,
        next_request_id=11,
    )
    results = (
        GrepSearchResultState(
            path="/home/tadashi/develop/zivo/a.py",
            display_path="a.py",
            line_number=1,
            line_text="todo item",
        ),
    )
    result = reduce_app_state(
        state, GrepSearchCompleted(request_id=10, query="todo", results=results)
    )

    assert result.state.command_palette.grs.grep_results == results
    assert result.state.pending_replace_preview_request_id is not None
    effects = [e for e in result.effects if isinstance(e, RunTextReplacePreviewEffect)]
    assert len(effects) == 1
    assert effects[0].request.paths == ("/home/tadashi/develop/zivo/a.py",)

def test_set_grs_replace_field_with_grep_results_starts_preview() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginGrepReplaceSelected(target_paths=("/home/tadashi/develop/zivo/a.py",)),
    )
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            grs=replace(
                state.command_palette.grs,
                keyword="todo",
                grep_results=(
                    GrepSearchResultState(
                        path="/home/tadashi/develop/zivo/a.py",
                        display_path="a.py",
                        line_number=1,
                        line_text="todo item",
                    ),
                ),
            ),
        ),
    )
    result = reduce_app_state(
        state, SetGrepReplaceSelectedField(field="replace", value="done")
    )

    assert result.state.pending_replace_preview_request_id is not None
    effects = [e for e in result.effects if isinstance(e, RunTextReplacePreviewEffect)]
    assert len(effects) == 1
    assert effects[0].request.paths == ("/home/tadashi/develop/zivo/a.py",)
    assert effects[0].request.find_text == "todo"

def test_set_grs_replace_field_without_grep_results_no_preview() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginGrepReplaceSelected(target_paths=("/home/tadashi/develop/zivo/a.py",)),
    )
    result = reduce_app_state(
        state, SetGrepReplaceSelectedField(field="replace", value="done")
    )

    assert result.state.pending_replace_preview_request_id is None
    assert result.state.command_palette.grs.preview_results == ()

def test_grs_preview_completed_stores_results() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginGrepReplaceSelected(target_paths=("/home/tadashi/develop/zivo/a.py",)),
    )
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            grs=replace(
                state.command_palette.grs,
                keyword="todo",
                replacement_text="done",
                grep_results=(
                    GrepSearchResultState(
                        path="/home/tadashi/develop/zivo/a.py",
                        display_path="a.py",
                        line_number=1,
                        line_text="todo item",
                    ),
                ),
            ),
        ),
        pending_replace_preview_request_id=10,
        next_request_id=11,
    )
    preview_result = TextReplacePreviewResult(
        request=TextReplaceRequest(
            paths=("/home/tadashi/develop/zivo/a.py",),
            find_text="todo",
            replace_text="done",
        ),
        changed_entries=(
            TextReplacePreviewEntry(
                path="/home/tadashi/develop/zivo/a.py",
                diff_text="- todo + done",
                match_count=1,
                first_match_line_number=1,
                first_match_before="todo",
                first_match_after="done",
            ),
        ),
        total_match_count=1,
        skipped_paths=(),
    )
    result = reduce_app_state(
        state, TextReplacePreviewCompleted(request_id=10, result=preview_result)
    )

    assert len(result.state.command_palette.grs.preview_results) == 1
    assert result.state.command_palette.grs.total_match_count == 1
    assert result.state.pending_replace_preview_request_id is None

def test_submit_grs_palette_applies_replacement() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginGrepReplaceSelected(target_paths=("/home/tadashi/develop/zivo/a.py",)),
    )
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            grs=replace(
                state.command_palette.grs,
                keyword="todo",
                replacement_text="done",
                grep_results=(
                    GrepSearchResultState(
                        path="/home/tadashi/develop/zivo/a.py",
                        display_path="a.py",
                        line_number=1,
                        line_text="todo item",
                    ),
                ),
                preview_results=(
                    ReplacePreviewResultState(
                        path="/home/tadashi/develop/zivo/a.py",
                        display_path="a.py",
                        diff_text="- todo + done",
                        match_count=1,
                        first_match_line_number=1,
                        first_match_before="todo",
                        first_match_after="done",
                    ),
                ),
                total_match_count=1,
            ),
        ),
    )
    result = reduce_app_state(state, SubmitCommandPalette())

    # Check that confirmation dialog is shown
    assert result.state.ui_mode == "CONFIRM"
    assert result.state.replace_confirmation is not None
    assert result.state.replace_confirmation.mode == "grep_replace_selected"

    # Confirm the replace operation
    result = reduce_app_state(result.state, ConfirmReplaceTargets())

    effects = [e for e in result.effects if isinstance(e, RunTextReplaceApplyEffect)]
    assert len(effects) == 1
    assert effects[0].request.paths == ("/home/tadashi/develop/zivo/a.py",)
    assert effects[0].request.find_text == "todo"
    assert effects[0].request.replace_text == "done"
    assert result.state.command_palette is None

def test_submit_grs_palette_warns_when_no_keyword() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginGrepReplaceSelected(target_paths=("/home/tadashi/develop/zivo/a.py",)),
    )
    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.notification is not None
    assert result.state.notification.level == "warning"

def test_submit_grs_palette_warns_when_no_preview_results() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginGrepReplaceSelected(target_paths=("/home/tadashi/develop/zivo/a.py",)),
    )
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            grs=replace(
                state.command_palette.grs,
                keyword="todo",
                replacement_text="done",
                grep_results=(
                    GrepSearchResultState(
                        path="/home/tadashi/develop/zivo/a.py",
                        display_path="a.py",
                        line_number=1,
                        line_text="todo item",
                    ),
                ),
            ),
        ),
    )
    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.notification is not None
    assert result.state.notification.level == "warning"

def test_cancel_grs_returns_to_browsing() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginGrepReplaceSelected(target_paths=("/home/tadashi/develop/zivo/a.py",)),
    )
    assert state.ui_mode == "PALETTE"

    state = _reduce_state(state, CancelCommandPalette())
    assert state.ui_mode == "BROWSING"
    assert state.command_palette is None

def test_grs_grep_search_completed_filters_non_target_results() -> None:
    """Verify that grep results not in target_paths are excluded."""
    state = _reduce_state(
        build_initial_app_state(),
        BeginGrepReplaceSelected(target_paths=("/home/tadashi/develop/zivo/a.py",)),
    )
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            grs=replace(state.command_palette.grs, keyword="todo"),
        ),
        pending_grep_search_request_id=10,
        next_request_id=11,
    )
    all_results = (
        GrepSearchResultState(
            path="/home/tadashi/develop/zivo/a.py",
            display_path="a.py",
            line_number=1,
            line_text="todo in a",
        ),
        GrepSearchResultState(
            path="/home/tadashi/develop/zivo/b.py",
            display_path="b.py",
            line_number=3,
            line_text="todo in b",
        ),
    )
    result = reduce_app_state(
        state, GrepSearchCompleted(request_id=10, query="todo", results=all_results)
    )

    assert len(result.state.command_palette.grs.grep_results) == 1
    assert result.state.command_palette.grs.grep_results[0].path == (
        "/home/tadashi/develop/zivo/a.py"
    )
    # Preview is triggered even with empty replace text to show find matches
    assert result.state.pending_replace_preview_request_id is not None


def test_grf_filename_filter_with_invalid_regex_single_backslash() -> None:
    """Test that single backslash in regex mode shows error and clears results."""
    from dataclasses import replace

    state = _reduce_state(build_initial_app_state(), BeginGrepReplace())
    # First, set up grep results
    all_results = (
        GrepSearchResultState(
            path="/home/tadashi/develop/zivo/a.py",
            display_path="a.py",
            line_number=1,
            line_text="todo in a",
        ),
    )
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            grf=replace(
                state.command_palette.grf,
                keyword="todo",
                grep_results=all_results,
            ),
        ),
    )

    # Now test invalid filename filter
    result = reduce_app_state(state, SetGrepReplaceField(field="filename", value="re:\\"))

    assert result.state.command_palette is not None
    assert result.state.command_palette.grf.filename_filter == "re:\\"
    assert result.state.command_palette.grf.error_message is not None
    assert "Invalid regex pattern" in result.state.command_palette.grf.error_message
    assert result.state.command_palette.grf.preview_results == ()
    assert result.state.command_palette.grf.total_match_count == 0


def test_grf_filename_filter_with_valid_regex_backslash() -> None:
    """Test that valid regex with backslash works correctly for grep replace."""
    from dataclasses import replace

    state = _reduce_state(build_initial_app_state(), BeginGrepReplace())
    # First, set up grep results
    all_results = (
        GrepSearchResultState(
            path="/home/tadashi/develop/zivo/a.py",
            display_path="a.py",
            line_number=1,
            line_text="todo in a",
        ),
        GrepSearchResultState(
            path="/home/tadashi/develop/zivo/b.txt",
            display_path="b.txt",
            line_number=1,
            line_text="todo in b",
        ),
    )
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            grf=replace(
                state.command_palette.grf,
                keyword="todo",
                replacement_text="done",
                grep_results=all_results,
            ),
        ),
    )

    # Test valid filename filter
    result = reduce_app_state(state, SetGrepReplaceField(field="filename", value="re:\\.py$"))

    assert result.state.command_palette is not None
    assert result.state.command_palette.grf.filename_filter == "re:\\.py$"
    assert result.state.command_palette.grf.error_message is None
    # Results should be filtered to .py files only
    assert result.state.pending_replace_preview_request_id == 1
