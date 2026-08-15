"""Test State Reducer Palette Grep Replace tests."""
from tests.support.paths import TEST_PROJECT_ROOT
from tests.support.reducer_palette_replace import (
    BeginGrepReplace,
    BeginGrepReplaceSelected,
    BeginReplaceFromSearchResults,
    CancelCommandPalette,
    CommandPaletteState,
    ConfirmReplaceTargets,
    GrepSearchCompleted,
    GrepSearchResultState,
    ReplacePreviewResultState,
    RunGrepSearchEffect,
    RunTextReplaceApplyEffect,
    RunTextReplacePreviewEffect,
    SetGrepReplaceField,
    SetGrepReplaceSelectedField,
    SubmitCommandPalette,
    TextReplacePreviewCompleted,
    TextReplacePreviewEntry,
    TextReplacePreviewResult,
    TextReplaceRequest,
    _reduce_state,
    build_initial_app_state,
    reduce_app_state,
    replace,
)


def test_begin_replace_from_grep_results_deduplicates_files_and_counts_matches() -> None:
    path = "/tmp/README.md"
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="grep_search",
            grep_search=replace(
                CommandPaletteState().grep_search,
                keyword="TODO",
                results=(
                    GrepSearchResultState(path, "README.md", 1, "TODO one"),
                    GrepSearchResultState(path, "README.md", 4, "TODO two"),
                    GrepSearchResultState("/tmp/src.py", "src.py", 2, "TODO three"),
                ),
            ),
        ),
    )

    result = reduce_app_state(state, BeginReplaceFromSearchResults())

    assert result.state.command_palette is not None
    preview = result.state.command_palette.replace_preview
    assert preview.scope == "search_results"
    assert preview.find_text == "TODO"
    assert preview.target_paths == (path, "/tmp/src.py")
    assert preview.result_origin == "grep"
    assert preview.result_file_count == 2
    assert preview.result_match_count == 3

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
                        path=TEST_PROJECT_ROOT + '/README.md',
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
    assert effects[0].request.paths == (TEST_PROJECT_ROOT + '/README.md',)
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
            path=TEST_PROJECT_ROOT + '/README.md',
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
            path=TEST_PROJECT_ROOT + '/README.md',
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
                        path=TEST_PROJECT_ROOT + '/README.md',
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
            paths=(TEST_PROJECT_ROOT + '/README.md',),
            find_text="todo",
            replace_text="done",
        ),
        changed_entries=(
            TextReplacePreviewEntry(
                path=TEST_PROJECT_ROOT + '/README.md',
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
                        path=TEST_PROJECT_ROOT + '/README.md',
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
                        path=TEST_PROJECT_ROOT + '/README.md',
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
            path=TEST_PROJECT_ROOT + '/README.md',
            display_path="README.md",
            line_number=1,
            line_text="todo item 1",
        ),
        GrepSearchResultState(
            path=TEST_PROJECT_ROOT + '/README.md',
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
    assert effects[0].request.paths == (TEST_PROJECT_ROOT + '/README.md',)

def test_begin_grep_replace_selected_enters_grs_mode() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginGrepReplaceSelected(
            target_paths=(TEST_PROJECT_ROOT + '/a.py', TEST_PROJECT_ROOT + '/b.py')
        ),
    )
    assert state.ui_mode == "PALETTE"
    assert state.command_palette is not None
    assert state.command_palette.source == "grep_replace_selected"
    assert state.command_palette.grs.active_field == "keyword"
    assert state.command_palette.grs.target_paths == (
        TEST_PROJECT_ROOT + '/a.py',
        TEST_PROJECT_ROOT + '/b.py',
    )

def test_set_grs_keyword_field_starts_grep_search() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginGrepReplaceSelected(target_paths=(TEST_PROJECT_ROOT + '/a.py',)),
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
        BeginGrepReplaceSelected(target_paths=(TEST_PROJECT_ROOT + '/a.py',)),
    )
    state = _reduce_state(state, SetGrepReplaceSelectedField(field="keyword", value="todo"))
    result = reduce_app_state(state, SetGrepReplaceSelectedField(field="keyword", value=""))

    assert result.state.pending_grep_search_request_id is None
    assert result.state.command_palette.grs.grep_results == ()

def test_grs_grep_search_completed_filters_to_target_paths() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginGrepReplaceSelected(
            target_paths=(TEST_PROJECT_ROOT + '/a.py', TEST_PROJECT_ROOT + '/c.py')
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
            path=TEST_PROJECT_ROOT + '/a.py',
            display_path="a.py",
            line_number=1,
            line_text="todo in a",
        ),
        GrepSearchResultState(
            path=TEST_PROJECT_ROOT + '/b.py',
            display_path="b.py",
            line_number=3,
            line_text="todo in b",
        ),
        GrepSearchResultState(
            path=TEST_PROJECT_ROOT + '/c.py',
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
        TEST_PROJECT_ROOT + '/a.py'
    )
    assert result.state.command_palette.grs.grep_results[1].path == (
        TEST_PROJECT_ROOT + '/c.py'
    )
    assert result.state.pending_grep_search_request_id is None

def test_grs_grep_search_completed_auto_triggers_preview_when_replace_text_present() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginGrepReplaceSelected(target_paths=(TEST_PROJECT_ROOT + '/a.py',)),
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
            path=TEST_PROJECT_ROOT + '/a.py',
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
    assert effects[0].request.paths == (TEST_PROJECT_ROOT + '/a.py',)

def test_set_grs_replace_field_with_grep_results_starts_preview() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginGrepReplaceSelected(target_paths=(TEST_PROJECT_ROOT + '/a.py',)),
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
                        path=TEST_PROJECT_ROOT + '/a.py',
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
    assert effects[0].request.paths == (TEST_PROJECT_ROOT + '/a.py',)
    assert effects[0].request.find_text == "todo"

def test_set_grs_replace_field_without_grep_results_no_preview() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginGrepReplaceSelected(target_paths=(TEST_PROJECT_ROOT + '/a.py',)),
    )
    result = reduce_app_state(
        state, SetGrepReplaceSelectedField(field="replace", value="done")
    )

    assert result.state.pending_replace_preview_request_id is None
    assert result.state.command_palette.grs.preview_results == ()

def test_grs_preview_completed_stores_results() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginGrepReplaceSelected(target_paths=(TEST_PROJECT_ROOT + '/a.py',)),
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
                        path=TEST_PROJECT_ROOT + '/a.py',
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
            paths=(TEST_PROJECT_ROOT + '/a.py',),
            find_text="todo",
            replace_text="done",
        ),
        changed_entries=(
            TextReplacePreviewEntry(
                path=TEST_PROJECT_ROOT + '/a.py',
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
        BeginGrepReplaceSelected(target_paths=(TEST_PROJECT_ROOT + '/a.py',)),
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
                        path=TEST_PROJECT_ROOT + '/a.py',
                        display_path="a.py",
                        line_number=1,
                        line_text="todo item",
                    ),
                ),
                preview_results=(
                    ReplacePreviewResultState(
                        path=TEST_PROJECT_ROOT + '/a.py',
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
    assert effects[0].request.paths == (TEST_PROJECT_ROOT + '/a.py',)
    assert effects[0].request.find_text == "todo"
    assert effects[0].request.replace_text == "done"
    assert result.state.command_palette is None

def test_submit_grs_palette_warns_when_no_keyword() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginGrepReplaceSelected(target_paths=(TEST_PROJECT_ROOT + '/a.py',)),
    )
    result = reduce_app_state(state, SubmitCommandPalette())

    assert result.state.notification is not None
    assert result.state.notification.level == "warning"

def test_submit_grs_palette_warns_when_no_preview_results() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        BeginGrepReplaceSelected(target_paths=(TEST_PROJECT_ROOT + '/a.py',)),
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
                        path=TEST_PROJECT_ROOT + '/a.py',
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
        BeginGrepReplaceSelected(target_paths=(TEST_PROJECT_ROOT + '/a.py',)),
    )
    assert state.ui_mode == "PALETTE"

    state = _reduce_state(state, CancelCommandPalette())
    assert state.ui_mode == "BROWSING"
    assert state.command_palette is None

def test_grs_grep_search_completed_filters_non_target_results() -> None:
    """Verify that grep results not in target_paths are excluded."""
    state = _reduce_state(
        build_initial_app_state(),
        BeginGrepReplaceSelected(target_paths=(TEST_PROJECT_ROOT + '/a.py',)),
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
            path=TEST_PROJECT_ROOT + '/a.py',
            display_path="a.py",
            line_number=1,
            line_text="todo in a",
        ),
        GrepSearchResultState(
            path=TEST_PROJECT_ROOT + '/b.py',
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
        TEST_PROJECT_ROOT + '/a.py'
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
            path=TEST_PROJECT_ROOT + '/a.py',
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
            path=TEST_PROJECT_ROOT + '/a.py',
            display_path="a.py",
            line_number=1,
            line_text="todo in a",
        ),
        GrepSearchResultState(
            path=TEST_PROJECT_ROOT + '/b.txt',
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
