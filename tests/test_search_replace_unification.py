from dataclasses import replace

from tests.state_test_helpers import reduce_state
from zivo.state import (
    CommandPaletteState,
    ReplacePreviewPaletteState,
    ReplacePreviewResultState,
    build_initial_app_state,
    select_command_palette_state,
    select_conflict_dialog_state,
)
from zivo.state.actions import SubmitCommandPalette


def _search_results_replace_state():
    initial = build_initial_app_state()
    return replace(
        initial,
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="replace_text",
            replace_preview=ReplacePreviewPaletteState(
                find_text="TODO",
                replacement_text="DONE",
                scope="search_results",
                result_origin="grep",
                result_query="TODO",
                result_file_count=2,
                result_match_count=3,
                target_paths=("/tmp/a.py", "/tmp/b.py"),
                preview_results=(
                    ReplacePreviewResultState(
                        path="/tmp/a.py",
                        display_path="a.py",
                        diff_text="-TODO\n+DONE\n",
                        match_count=2,
                        first_match_line_number=1,
                        first_match_before="TODO",
                        first_match_after="DONE",
                    ),
                ),
                total_match_count=3,
            ),
        ),
    )


def test_search_results_replace_view_exposes_origin_and_counts() -> None:
    state = _search_results_replace_state()

    view = select_command_palette_state(state)

    assert view is not None
    assert view.title.startswith('Replace Search Results · Grep "TODO"')
    assert [field.value for field in view.input_fields] == [
        "Search results",
        "TODO",
        "DONE",
    ]
    assert view.footer_message == "Grep \"TODO\" · 2 file(s) / 3 match(es) · preview before apply"


def test_search_results_confirmation_keeps_origin_context() -> None:
    result = reduce_state(_search_results_replace_state(), SubmitCommandPalette())

    assert result.replace_confirmation is not None
    assert result.replace_confirmation.result_origin == "grep"
    assert result.replace_confirmation.result_query == "TODO"
    dialog = select_conflict_dialog_state(result)
    assert dialog is not None
    assert dialog.message.startswith('Grep "TODO": Replace')
