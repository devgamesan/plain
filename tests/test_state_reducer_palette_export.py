"""Tests for saving grep results from the command palette."""

from dataclasses import replace

from zivo.state import GrepSearchResultState, build_initial_app_state, reduce_app_state
from zivo.state.actions import GrepExportCompleted, GrepExportFailed, SaveGrepResults
from zivo.state.effects import RunGrepExportEffect
from zivo.state.models import CommandPaletteState


def _state_with_grep_results():
    state = build_initial_app_state()
    return replace(
        state,
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="grep_search",
            grep_search=replace(
                CommandPaletteState().grep_search,
                keyword="hello",
                results=(
                    GrepSearchResultState(
                        path="/root/src/main.py",
                        display_path="src/main.py",
                        line_number=10,
                        line_text="def hello():",
                    ),
                ),
            ),
        ),
    )


def test_save_grep_results_emits_effect_using_preview_context_setting(tmp_path) -> None:
    state = replace(_state_with_grep_results(), current_path=str(tmp_path))

    result = reduce_app_state(state, SaveGrepResults())

    assert result.state.ui_mode == "PALETTE"
    assert result.state.pending_grep_export_request_id == state.next_request_id
    assert len(result.effects) == 1
    effect = result.effects[0]
    assert isinstance(effect, RunGrepExportEffect)
    assert effect.output_path == str(tmp_path / "grep_results.txt")
    assert effect.context_lines == state.config.display.grep_preview_context_lines
    assert len(effect.results) == 1


def test_save_grep_results_warns_when_no_results() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(source="grep_search"),
    )

    result = reduce_app_state(state, SaveGrepResults())

    assert result.effects == ()
    assert result.state.notification is not None
    assert result.state.notification.level == "warning"
    assert "No grep results" in result.state.notification.message


def test_save_grep_results_preserves_existing_file(tmp_path) -> None:
    output = tmp_path / "grep_results.txt"
    output.write_text("existing")
    state = replace(_state_with_grep_results(), current_path=str(tmp_path))

    result = reduce_app_state(state, SaveGrepResults())

    assert result.effects == ()
    assert result.state.notification is not None
    assert "already exists" in result.state.notification.message


def test_grep_export_completion_and_failure_notify() -> None:
    state = replace(build_initial_app_state(), pending_grep_export_request_id=42)

    completed = reduce_app_state(
        state,
        GrepExportCompleted(request_id=42, destination_path="/tmp/out.txt", exported_results=3),
    )
    assert completed.state.notification is not None
    assert "Exported 3 results" in completed.state.notification.message

    failed = reduce_app_state(
        state,
        GrepExportFailed(request_id=42, message="Permission denied"),
    )
    assert failed.state.notification is not None
    assert failed.state.notification.level == "error"
